#!/usr/bin/env python3
"""
VCD 智能流式查询工具 v5
核心策略（精简两阶段）：
1. 阶段 1: 定位异常时间窗口
   - 用户指定 → 直接使用
   - 用户未指定 → 全时间扫描找异常点
2. 阶段 2: 迭代追踪依赖信号
   - 只在异常时间点往前查窗口
   - 查到结果就停止

特性：
- mmap 加速 + 直接字节比较
- 时间窗口查询（核心）
- 行为分析（找异常点）
"""

import sys
import os
import mmap
from typing import Optional, Dict, List, Tuple


class VCDSmartStream:
    """VCD 智能流式查询器"""
    
    def __init__(self, vcd_file: str):
        self.vcd_file = vcd_file
        self.signals = {}  # name -> id
        self.signal_ids = {}  # id -> name
        self.signal_widths = {}  # name -> width
        self.file_size = os.path.getsize(vcd_file)
        self.mm = None
        self.data_start = 0
        
    def __enter__(self):
        self.mm = mmap.mmap(os.open(self.vcd_file, os.O_RDONLY), 0, access=mmap.ACCESS_READ)
        return self
        
    def __exit__(self, *args):
        if self.mm:
            self.mm.close()
    
    def parse_header_fast(self) -> bool:
        """快速解析文件头"""
        end_pos = self.mm.find(b'$enddefinitions $end')
        if end_pos == -1:
            return False
        
        header = self.mm[:end_pos].decode('ascii', errors='ignore')
        
        for line in header.split('\n'):
            if line.startswith('$var'):
                parts = line.split()
                if len(parts) >= 5:
                    width = int(parts[2]) if parts[2].isdigit() else 1
                    signal_id = parts[3]
                    signal_name = parts[4]
                    
                    self.signals[signal_name] = signal_id
                    self.signal_ids[signal_id] = signal_name
                    self.signal_widths[signal_name] = width
        
        self.data_start = end_pos + len(b'$enddefinitions $end') + 1
        self.mm.seek(self.data_start)
        return True
    
    def _resolve_signal(self, target_name: str) -> Optional[str]:
        """解析信号名（精确匹配 + 模糊匹配）"""
        # 精确匹配
        if target_name in self.signals:
            return self.signals[target_name]
        
        # 模糊匹配
        for name, sig_id in self.signals.items():
            if target_name in name or name.endswith(f'.{target_name}'):
                return sig_id
        
        return None
    
    def query_window(self, target_name: str, start_time: int = 0, end_time: int = None, 
                     max_changes: int = None) -> List[Tuple[int, str]]:
        """
        时间窗口查询（核心功能）
        
        Args:
            target_name: 信号名
            start_time: 开始时间 (ps)
            end_time: 结束时间 (ps)，None 表示查到文件末尾
            max_changes: 最大返回变化数，None 表示不限
        
        Returns:
            [(time1, value1), (time2, value2), ...]
        """
        target_id = self._resolve_signal(target_name)
        if not target_id:
            return []
        
        changes = []
        current_time = 0
        target_id_bytes = target_id.encode()
        
        self.mm.seek(self.data_start)
        
        while True:
            line = self.mm.readline()
            if not line:
                break
            
            line = line.strip()
            
            # 时间戳（快速判断）
            if line and line[0:1] == b'#':
                try:
                    current_time = int(line[1:])
                except:
                    pass
                
                # 超过结束时间，提前退出
                if end_time is not None and current_time > end_time:
                    break
                continue
            
            # 跳过开始时间之前的数据
            if current_time < start_time:
                continue
            
            # 单比特信号（快速路径）
            if line and line[0:1] in (b'0', b'1', b'x', b'X', b'z', b'Z'):
                value = line[0:1]
                rest = line[1:].lstrip()
                sig_id = rest.split()[0] if rest else b''
                
                if sig_id == target_id_bytes:
                    changes.append((current_time, value.decode()))
                    if max_changes and len(changes) >= max_changes:
                        break
            
            # 多比特信号
            elif line.startswith(b'b'):
                parts = line.split()
                if len(parts) >= 2:
                    value = parts[0][1:].decode()
                    sig_id = parts[1].decode()
                    if sig_id == target_id:
                        changes.append((current_time, value))
                        if max_changes and len(changes) >= max_changes:
                            break
        
        return changes
    
    def find_anomaly_window(self, target_name: str, target_behavior: str = 'toggling',
                             max_time: int = None) -> Optional[Tuple[int, int]]:
        """
        查找异常行为的时间窗口（用于用户未指定时间时）
        
        Args:
            target_name: 信号名
            target_behavior: 目标行为（'toggling'|'pulse'|'constant'）
            max_time: 最大搜索时间 (ps)，None 表示查全文件
        
        Returns:
            (window_start, window_end) 或 None
        
        策略：
        1. 先做全时间行为分析
        2. 找到第一个异常点
        3. 返回包含该点的小窗口（±100ns）
        """
        # 全时间行为分析
        behavior = self.analyze_behavior(target_name, 0, max_time)
        
        if behavior['behavior'] == 'silent':
            return None  # 始终无变化
        
        # 找到第一个变化点
        if behavior['first_change'] is not None:
            t = behavior['first_change']
            tolerance = 100000  # 100ns
            return (max(0, t - tolerance), t + tolerance)
        
        return None
    
    def find_first_edge(self, target_name: str, after_time: int = 0, 
                        target_value: str = '1', max_search: int = 10000000000) -> Optional[int]:
        """
        查找第一个跳变沿
        
        Args:
            target_name: 信号名
            after_time: 在此时间之后查找 (ps)
            target_value: 目标值
            max_search: 最大搜索范围 (ps)
        
        Returns:
            跳变沿时间
        """
        # 逐步扩大搜索窗口（指数增长）
        window_size = 1000  # 初始 1ns
        current_start = after_time
        
        for i in range(20):  # 最多 20 次迭代
            current_end = current_start + window_size
            
            # 查询窗口内是否有目标值
            changes = self.query_window(target_name, current_start, current_end, max_changes=100)
            
            for time, value in changes:
                if value == target_value:
                    return time
            
            # 扩大窗口
            current_start = current_end
            window_size *= 2
            
            if window_size > max_search:
                break
        
        return None
    
    def analyze_behavior(self, target_name: str, window_start: int = 0, 
                         window_end: int = None) -> Dict:
        """
        分析信号行为
        
        Returns:
            {
                'behavior': 'silent'|'constant'|'toggling'|'pulse',
                'changes': int,
                'first_change': int|None,
                'last_change': int|None,
                'values': set,
                'has_pulse': bool
            }
        """
        changes = self.query_window(target_name, window_start, window_end)
        
        if not changes:
            return {
                'behavior': 'silent',
                'changes': 0,
                'first_change': None,
                'last_change': None,
                'values': set(),
                'has_pulse': False
            }
        
        values = set(v for t, v in changes)
        
        # 判断行为
        has_pulse = False
        if len(values) == 1:
            behavior = 'constant'
        else:
            # 检查是否有脉冲（0→1→0 或 1→0→1）
            value_list = [v for t, v in changes]
            for i in range(len(value_list) - 2):
                if value_list[i] == value_list[i+2] and value_list[i] != value_list[i+1]:
                    has_pulse = True
                    break
            
            behavior = 'pulse' if has_pulse else 'toggling'
        
        return {
            'behavior': behavior,
            'changes': len(changes),
            'first_change': changes[0][0] if changes else None,
            'last_change': changes[-1][0] if changes else None,
            'values': values,
            'has_pulse': has_pulse
        }


def test_basic_query(q: VCDSmartStream):
    """测试基本查询"""
    print("\n" + "=" * 80)
    print("测试 1: 基本时间窗口查询")
    print("=" * 80)
    
    import time
    
    # 测试 1: 小窗口查询
    start = time.time()
    changes = q.query_window('transfer_done', 0, 100000)
    elapsed = time.time() - start
    print(f"✅ 查询 t=0-100ns: {len(changes)} 次变化，耗时 {elapsed*1000:.1f}ms")
    
    # 测试 2: 中等窗口
    start = time.time()
    changes = q.query_window('transfer_done', 0, 1000000)
    elapsed = time.time() - start
    print(f"✅ 查询 t=0-1μs: {len(changes)} 次变化，耗时 {elapsed*1000:.1f}ms")
    
    # 测试 3: 大窗口
    start = time.time()
    changes = q.query_window('transfer_done', 0, 10000000)
    elapsed = time.time() - start
    print(f"✅ 查询 t=0-10μs: {len(changes)} 次变化，耗时 {elapsed*1000:.1f}ms")


def test_anomaly_window(q: VCDSmartStream):
    """测试异常窗口定位"""
    print("\n" + "=" * 80)
    print("测试 2: 异常窗口定位（用户未指定时间时）")
    print("=" * 80)
    
    import time
    
    # 测试：查找 transfer_done 的异常窗口
    start = time.time()
    window = q.find_anomaly_window('transfer_done')
    elapsed = time.time() - start
    
    if window:
        print(f"✅ 找到异常窗口：t={window[0]}-{window[1]} ps，耗时 {elapsed*1000:.1f}ms")
    else:
        print(f"⚠️  未找到异常窗口，耗时 {elapsed*1000:.1f}ms")


def test_behavior_analysis(q: VCDSmartStream):
    """测试行为分析"""
    print("\n" + "=" * 80)
    print("测试 3: 信号行为分析")
    print("=" * 80)
    
    import time
    
    signals_to_test = ['transfer_done', 'awvalid', 'wvalid', 'bvalid']
    
    for sig in signals_to_test:
        start = time.time()
        behavior = q.analyze_behavior(sig, 0, 10000000)
        elapsed = time.time() - start
        
        print(f"📊 {sig}:")
        print(f"   行为：{behavior['behavior']}")
        print(f"   变化：{behavior['changes']} 次")
        print(f"   有脉冲：{behavior['has_pulse']}")
        print(f"   耗时：{elapsed*1000:.1f}ms")


def main():
    import argparse
    import time
    
    parser = argparse.ArgumentParser(description='VCD 智能流式查询工具 v4')
    parser.add_argument('vcd_file', help='VCD 文件路径')
    parser.add_argument('--signal', '-s', help='查询特定信号')
    parser.add_argument('--start-time', type=int, default=0, help='开始时间 (ps)')
    parser.add_argument('--end-time', type=int, help='结束时间 (ps)')
    parser.add_argument('--analyze', action='store_true', help='分析信号行为')
    parser.add_argument('--test', action='store_true', help='运行测试套件')
    
    args = parser.parse_args()
    
    print(f"📂 加载文件：{args.vcd_file}")
    print(f"📊 文件大小：{os.path.getsize(args.vcd_file) / 1024 / 1024:.1f} MB")
    
    with VCDSmartStream(args.vcd_file) as q:
        print("🔍 解析文件头...")
        if not q.parse_header_fast():
            print("❌ 解析失败")
            return
        
        print(f"✅ 找到 {len(q.signals)} 个信号")
        
        # 运行测试
        if args.test:
            test_basic_query(q)
            test_anomaly_window(q)
            test_behavior_analysis(q)
            return
        
        # 行为分析
        if args.signal and args.analyze:
            print(f"\n🔍 分析信号：{args.signal}")
            behavior = q.analyze_behavior(args.signal, args.start_time, args.end_time)
            
            print(f"   行为：{behavior['behavior']}")
            print(f"   变化：{behavior['changes']} 次")
            print(f"   首次变化：t={behavior['first_change']} ps")
            print(f"   最后变化：t={behavior['last_change']} ps")
            print(f"   有脉冲：{behavior['has_pulse']}")
            return
        
        # 时间窗口查询
        if args.signal and args.end_time:
            print(f"\n🔍 时间窗口查询：{args.signal}")
            print(f"   窗口：t={args.start_time} - {args.end_time} ps")
            
            start = time.time()
            changes = q.query_window(args.signal, args.start_time, args.end_time)
            elapsed = time.time() - start
            
            print(f"✅ 找到 {len(changes)} 次变化")
            if changes:
                print(f"   前 5 个：{changes[:5]}")
            print(f"⏱️  耗时：{elapsed*1000:.1f}ms")
            return
        
        # 普通查询
        if args.signal:
            print(f"\n🔍 查询信号：{args.signal}")
            
            start = time.time()
            behavior = q.analyze_behavior(args.signal)
            elapsed = time.time() - start
            
            print(f"✅ {behavior['behavior']}")
            print(f"   变化：{behavior['changes']} 次")
            if behavior['first_change'] is not None:
                print(f"   首次变化：t={behavior['first_change']} ps")
            print(f"⏱️  耗时：{elapsed*1000:.1f}ms")


if __name__ == '__main__':
    main()
