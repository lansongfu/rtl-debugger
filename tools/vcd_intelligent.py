#!/usr/bin/env python3
"""
VCD 智能查询工具 v3
核心改进：
1. 时间窗口查询（不查全文件）
2. 增量索引（存关键跳变沿）
3. 智能定位异常窗口
4. 支持迭代调试流程
"""

import sys
# Windows 编码适配：确保 UTF-8 输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import os
import json
import mmap
from typing import Optional, Dict, List, Tuple


class VCDIntelligentQuery:
    """VCD 智能查询器"""
    
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
    
    def query_signal_window(self, target_name: str, start_time: int = 0, end_time: int = None) -> List[Tuple]:
        """
        查询指定时间窗口内的信号行为
        只扫描目标时间段，不查全文件
        """
        if target_name not in self.signals:
            # 模糊匹配
            for name, sig_id in self.signals.items():
                if target_name in name or name.endswith(f'.{target_name}'):
                    target_name = name
                    break
            else:
                return []
        
        target_id = self.signals[target_name]
        changes = []
        current_time = 0
        
        self.mm.seek(self.data_start)
        
        while True:
            line = self.mm.readline()
            if not line:
                break
            
            line = line.strip()
            
            # 时间戳
            if line and line[0:1] == b'#':
                try:
                    current_time = int(line[1:])
                except:
                    pass
                
                # 超过结束时间，提前退出
                if end_time and current_time > end_time:
                    break
                continue
            
            # 跳过开始时间之前的数据
            if current_time < start_time:
                continue
            
            # 单比特信号
            if line and line[0:1] in (b'0', b'1', b'x', b'X', b'z', b'Z'):
                value = line[0:1]
                rest = line[1:].lstrip()
                sig_id = rest.split()[0] if rest else b''
                
                if sig_id == target_id.encode():
                    changes.append((current_time, value.decode()))
            
            # 多比特信号
            elif line.startswith(b'b'):
                parts = line.split()
                if len(parts) >= 2:
                    value = parts[0][1:].decode()
                    sig_id = parts[1].decode()
                    if sig_id == target_id:
                        changes.append((current_time, value))
        
        return changes
    
    def find_nearest_edge(self, target_name: str, target_time: int, direction: str = 'before') -> Optional[int]:
        """
        查找距离目标时间最近的跳变沿
        direction: 'before' (往前找) 或 'after' (往后找)
        """
        if direction == 'before':
            # 往前找：从 target_time - 1000ns 到 target_time
            start = max(0, target_time - 1000000)  # 1ms
            end = target_time
        else:
            # 往后找：从 target_time 到 target_time + 1000ns
            start = target_time
            end = target_time + 1000000
        
        changes = self.query_signal_window(target_name, start, end)
        
        if not changes:
            return None
        
        if direction == 'before':
            return changes[-1][0] if changes else None
        else:
            return changes[0][0] if changes else None
    
    def locate_anomaly_window(self, target_name: str, expected_time: int, tolerance: int = 100000) -> Tuple[int, int]:
        """
        智能定位异常时间窗口
        expected_time: 预期信号变化的时间 (ps)
        tolerance: 容差范围 (默认 100ns = 100000ps)
        
        返回：(window_start, window_end)
        """
        window_start = max(0, expected_time - tolerance)
        window_end = expected_time + tolerance
        
        return (window_start, window_end)
    
    def create_index_enhanced(self, index_file: str) -> Dict:
        """
        创建增强索引
        存储：跳变沿、活跃窗口、脉冲信息
        """
        print(f"📝 创建增强索引：{index_file}")
        
        index = {
            'file': self.vcd_file,
            'file_size': self.file_size,
            'signals': {},
            'signal_count': 0
        }
        
        # 解析文件头
        if not self.parse_header_fast():
            print("❌ 解析文件头失败")
            return {}
        print(f"✅ 解析文件头完成，{len(self.signals)} 个信号")
        
        index['signal_count'] = len(self.signals)
        
        # 预编译查找表
        id_to_idx = {}
        
        print(f"📊 扫描文件（{self.file_size / 1024 / 1024:.1f} MB）...")
        
        current_time = 0
        progress_interval = max(10 * 1024 * 1024, self.file_size // 20)
        last_progress = self.mm.tell()
        line_count = 0
        
        # 第一遍：收集所有跳变沿
        temp_changes = {sig_id: [] for sig_id in self.signal_ids.keys()}
        
        self.mm.seek(self.data_start)
        while True:
            line = self.mm.readline()
            if not line:
                break
            
            line = line.strip()
            line_count += 1
            pos = self.mm.tell()
            
            if line and line[0:1] == b'#':
                try:
                    current_time = int(line[1:])
                except:
                    pass
                continue
            
            if line and line[0:1] in (b'0', b'1', b'x', b'X', b'z', b'Z'):
                value = line[0:1]
                rest = line[1:].lstrip()
                sig_id = rest.split()[0] if rest else b''
                if sig_id in temp_changes:
                    temp_changes[sig_id].append((current_time, value.decode()))
            
            elif line.startswith(b'b'):
                parts = line.split()
                if len(parts) >= 2:
                    value = parts[0][1:].decode()
                    sig_id = parts[1].decode()
                    if sig_id in temp_changes:
                        temp_changes[sig_id].append((current_time, value))
            
            # 进度报告
            if pos - last_progress > progress_interval:
                progress = pos / self.file_size * 100
                print(f"   进度：{progress:.0f}% (已处理{line_count}行)")
                last_progress = pos
        
        print(f"✅ 扫描完成 (共{line_count}行)，构建索引...")
        
        # 第二遍：构建索引
        for name, sig_id in self.signals.items():
            changes = temp_changes.get(sig_id, [])
            
            # 提取关键信息
            key_times = [t for t, v in changes]
            first_time = key_times[0] if key_times else None
            last_time = key_times[-1] if key_times else None
            
            # 判断是否有脉冲（0→1→0 或 1→0→1）
            has_pulse = False
            if len(changes) >= 2:
                values = [v for t, v in changes]
                for i in range(len(values) - 2):
                    if (values[i] == values[i+2] and values[i] != values[i+1]):
                        has_pulse = True
                        break
            
            # 活跃窗口（第一次和最后一次变化之间）
            active_window = None
            if first_time is not None and last_time is not None:
                active_window = [first_time, last_time]
            
            # 限制存储的跳变沿数量（最多 1000 个）
            if len(key_times) > 1000:
                # 均匀采样
                step = len(key_times) // 1000
                key_times = key_times[::step][:1000]
            
            index['signals'][name] = {
                'id': sig_id,
                'width': self.signal_widths.get(name, 1),
                'changes': len(changes),
                'first_time': first_time,
                'last_time': last_time,
                'key_times': key_times,  # 跳变沿列表
                'has_pulse': has_pulse,
                'active_window': active_window
            }
        
        # 保存索引
        with open(index_file, 'w') as f:
            json.dump(index, f, indent=2)
        
        print(f"📁 索引大小：{os.path.getsize(index_file) / 1024:.1f} KB")
        
        return index
    
    def load_index(self, index_file: str) -> Optional[Dict]:
        """加载索引"""
        if not os.path.exists(index_file):
            return None
        
        with open(index_file, 'r') as f:
            return json.load(f)


def main():
    import argparse
    import time
    
    parser = argparse.ArgumentParser(description='VCD 智能查询工具 v3')
    parser.add_argument('vcd_file', help='VCD 文件路径')
    parser.add_argument('--signal', '-s', help='查询特定信号')
    parser.add_argument('--start-time', type=int, default=0, help='开始时间 (ps)')
    parser.add_argument('--end-time', type=int, help='结束时间 (ps)')
    parser.add_argument('--create-index', '-i', action='store_true', help='创建增强索引')
    parser.add_argument('--find-edge', action='store_true', help='查找最近跳变沿')
    parser.add_argument('--direction', choices=['before', 'after'], default='before', help='跳变沿方向')
    parser.add_argument('--target-time', type=int, help='目标时间 (ps)')
    
    args = parser.parse_args()
    
    with VCDIntelligentQuery(args.vcd_file) as q:
        q.parse_header_fast()
        
        # 创建索引
        if args.create_index:
            index_file = args.vcd_file + '.idx'
            start = time.time()
            q.create_index_enhanced(index_file)
            elapsed = time.time() - start
            print(f"⏱️  耗时：{elapsed:.1f}秒")
            return
        
        # 时间窗口查询
        if args.signal and args.end_time:
            print(f"🔍 时间窗口查询：{args.signal}")
            print(f"   窗口：t={args.start_time} - {args.end_time} ps")
            
            start = time.time()
            changes = q.query_signal_window(args.signal, args.start_time, args.end_time)
            elapsed = time.time() - start
            
            print(f"✅ 找到 {len(changes)} 次变化")
            if changes:
                print(f"   前 5 个：{changes[:5]}")
            print(f"⏱️  耗时：{elapsed:.2f}秒")
            return
        
        # 查找跳变沿
        if args.signal and args.find_edge and args.target_time:
            print(f"🔍 查找跳变沿：{args.signal}")
            print(f"   目标时间：t={args.target_time} ps")
            print(f"   方向：{args.direction}")
            
            start = time.time()
            edge_time = q.find_nearest_edge(args.signal, args.target_time, args.direction)
            elapsed = time.time() - start
            
            if edge_time:
                print(f"✅ 找到跳变沿：t={edge_time} ps")
            else:
                print(f"❌ 未找到跳变沿")
            print(f"⏱️  耗时：{elapsed:.2f}秒")
            return
        
        # 普通查询（使用索引）
        if args.signal:
            index_file = args.vcd_file + '.idx'
            index = q.load_index(index_file)
            
            if index and args.signal in index['signals']:
                info = index['signals'][args.signal]
                print(f"📊 {args.signal}:")
                print(f"   变化次数：{info['changes']}")
                print(f"   活跃窗口：t={info['active_window'][0]} - {info['active_window'][1]} ps")
                print(f"   有脉冲：{info['has_pulse']}")
                if info['key_times']:
                    print(f"   前 10 个跳变沿：{info['key_times'][:10]}")
            else:
                print(f"❌ 未找到信号或索引不存在")


if __name__ == '__main__':
    main()
