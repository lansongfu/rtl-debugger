#!/usr/bin/env python3
"""
VCD 波形查询工具
核心问题：这些信号在波形中是什么行为？
"""

import sys
import os
import re

# 添加 vcdvcd 到路径
venv_lib = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                        'venv/lib/python3.12/site-packages')
sys.path.insert(0, venv_lib)

from vcdvcd import vcdvcd
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

class VCDQuery:
    """VCD 波形查询器"""
    
    def __init__(self):
        self.vcd_data = None
        self.signals = {}  # signal_name -> signal_info
    
    def load(self, vcd_file: str) -> bool:
        """加载 VCD 文件"""
        try:
            print(f"📂 加载 VCD 文件：{vcd_file}")
            self.vcd_data = vcdvcd.VCDVCD(vcd_file)
            
            # vcdvcd 的 data 是字典：id -> Signal 对象
            for signal_id, signal_info in self.vcd_data.data.items():
                # Signal 对象有 attributes: endtime, references, size, tv, var_type
                refs = signal_info.references if hasattr(signal_info, 'references') else signal_info['references']
                size = signal_info.size if hasattr(signal_info, 'size') else signal_info['size']
                tv = signal_info.tv if hasattr(signal_info, 'tv') else signal_info['tv']
                
                for ref in refs:
                    self.signals[ref] = {
                        'id': signal_id,
                        'name': ref,
                        'width': int(size) if size else 1,
                        'tv': tv if tv else []
                    }
            
            print(f"✅ 加载完成：{len(self.signals)} 个信号")
            return True
            
        except Exception as e:
            print(f"❌ 加载失败：{e}")
            return False
    
    def query_signal(self, signal_name: str) -> Optional[Dict]:
        """查询特定信号的波形"""
        # 模糊匹配信号名
        matched = None
        for name, info in self.signals.items():
            if signal_name in name or name.endswith(f'.{signal_name}'):
                matched = info
                break
        
        if not matched:
            return None
        
        return {
            'name': matched['name'],
            'width': matched['width'],
            'changes': len(matched['tv']),
            'tv': matched['tv']
        }
    
    def get_signal_behavior(self, signal_name: str) -> str:
        """获取信号行为描述"""
        result = self.query_signal(signal_name)
        
        if not result:
            return f"❌ 未找到信号 '{signal_name}'"
        
        # 分析行为
        tv = result['tv']
        if len(tv) == 0:
            return f"{result['name']}: 始终无变化 (静默信号)"
        
        # 获取初始值和最终值
        initial = tv[0][1]
        final = tv[-1][1]
        
        # 判断行为模式
        unique_values = set(v for t, v in tv)
        
        if len(unique_values) == 1:
            return f"{result['name']}: 始终为 {initial} (恒定信号)"
        
        # 统计 0 和 1 的次数
        if result['width'] == 1:
            zeros = sum(1 for t, v in tv if v == '0')
            ones = sum(1 for t, v in tv if v == '1')
            return f"{result['name']}: 变化 {len(tv)} 次 (0:{zeros}次，1:{ones}次)"
        
        # 多比特信号
        return f"{result['name']}: 变化 {len(tv)} 次 ({len(unique_values)} 个不同值)"
    
    def compare_signals(self, signal_names: List[str]) -> str:
        """比较多个信号的行为"""
        results = []
        for name in signal_names:
            behavior = self.get_signal_behavior(name)
            results.append(behavior)
        
        return "\n".join(results)
    
    def get_summary(self) -> str:
        """获取 VCD 文件摘要"""
        if not self.vcd_data:
            return "未加载 VCD 文件"
        
        total_changes = sum(len(info['tv']) for info in self.signals.values())
        
        # 找出最活跃的信号
        active_signals = sorted(
            self.signals.items(),
            key=lambda x: len(x[1]['tv']),
            reverse=True
        )[:10]
        
        summary = [
            "=" * 80,
            "VCD 文件摘要",
            "=" * 80,
            f"信号总数：{len(self.signals)}",
            f"总变化次数：{total_changes}",
            f"时间范围：{self.vcd_data.begintime} - {self.vcd_data.endtime} ps",
            "",
            "最活跃的信号 (Top 10):"
        ]
        
        for name, info in active_signals:
            changes = len(info['tv'])
            summary.append(f"  {name}: {changes} 次变化")
        
        return "\n".join(summary)
    
    def print_trace(self, signal_name: str, time_range: Optional[Tuple[int, int]] = None) -> None:
        """打印信号的详细时序"""
        result = self.query_signal(signal_name)
        
        if not result:
            print(f"❌ 未找到信号 '{signal_name}'")
            return
        
        print(f"\n🔍 信号时序：{result['name']}")
        print("=" * 80)
        print(f"位宽：{result['width']} bits")
        print(f"变化次数：{result['changes']}")
        
        tv = result['tv']
        if tv:
            print(f"首次变化：t={tv[0][0]} ps")
            print(f"最后变化：t={tv[-1][0]} ps")
        
        # 打印时序
        print(f"\n时序详情 (前 20 个变化):")
        
        # 时间范围过滤
        if time_range:
            start, end = time_range
            tv = [(t, v) for t, v in tv if start <= t <= end]
        
        # 只显示前 20 个变化
        display_count = min(20, len(tv))
        for i in range(display_count):
            time_ns = tv[i][0] / 1000  # ps -> ns
            print(f"  t={time_ns:>10.1f}ns: {signal_name} = {tv[i][1]}")
        
        if len(tv) > display_count:
            print(f"  ... 还有 {len(tv) - display_count} 个变化")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='VCD 波形查询工具')
    parser.add_argument('vcd_file', help='VCD 文件路径')
    parser.add_argument('--signal', help='查询特定信号')
    parser.add_argument('--signals', help='查询多个信号 (逗号分隔)')
    parser.add_argument('--summary', action='store_true', help='显示 VCD 摘要')
    parser.add_argument('--trace', help='显示信号详细时序')
    parser.add_argument('--time-range', help='时间范围 (start:end) ps')
    
    args = parser.parse_args()
    
    # 创建查询器
    query = VCDQuery()
    
    # 加载 VCD
    if not query.load(args.vcd_file):
        sys.exit(1)
    
    # 显示摘要
    if args.summary:
        print(query.get_summary())
        sys.exit(0)
    
    # 查询单个信号
    if args.signal:
        print(query.get_signal_behavior(args.signal))
        
        if args.trace:
            time_range = None
            if args.time_range:
                start, end = map(int, args.time_range.split(':'))
                time_range = (start, end)
            query.print_trace(args.signal, time_range)
        
        sys.exit(0)
    
    # 查询多个信号
    if args.signals:
        signal_list = [s.strip() for s in args.signals.split(',')]
        print(query.compare_signals(signal_list))
        sys.exit(0)
    
    # 默认显示摘要
    print(query.get_summary())


if __name__ == '__main__':
    main()
