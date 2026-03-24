#!/usr/bin/env python3
"""
VCD 深度分析工具 v5 - 信号分析函数库

定位：供其他 Agent 调用的分析函数库
使用方式：
    from vcd_analyze import analyze_pulse, analyze_clock, analyze_bus
    
特性：
- 基于 vcd_smart.py 流式查询（毫秒级）
- 纯函数式接口（输入→输出）
- 返回结构化数据（dict/JSON）
- 无可视化依赖
"""

import sys
import os

# Windows 编码适配
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 导入流式查询核心
from vcd_smart import VCDSmartStream
from typing import Dict, List, Tuple, Optional
from collections import defaultdict


def analyze_pulse(vcd_file: str, signal: str, 
                  window: Optional[Tuple[int, int]] = None) -> Dict:
    """
    脉冲分析
    
    Args:
        vcd_file: VCD 文件路径
        signal: 信号名
        window: 时间窗口 (start_ps, end_ps)，None 表示全时间
    
    Returns:
        {
            'pulse_count': int,              # 脉冲数量
            'min_width_ps': float,           # 最小脉宽 (ps)
            'max_width_ps': float,           # 最大脉宽 (ps)
            'avg_width_ps': float,           # 平均脉宽 (ps)
            'periods_ps': List[float],       # 周期列表 (ps)
            'duty_cycle': float,             # 占空比
            'first_pulse_ps': float,         # 第一个脉冲时间
            'last_pulse_ps': float           # 最后一个脉冲时间
        }
    """
    with VCDSmartStream(vcd_file) as q:
        q.parse_header_fast()
        
        # 流式查询
        start_time = window[0] if window else 0
        end_time = window[1] if window else None
        changes = q.query_window(signal, start_time, end_time)
        
        # 分析脉冲
        pulse_widths = []
        periods = []
        last_rising = None
        last_falling = None
        
        for time, value in changes:
            if value == '1':
                if last_rising is None:
                    last_rising = time
                elif last_falling is not None:
                    # 新周期
                    periods.append(time - last_rising)
                    last_rising = time
                    last_falling = None
            elif value == '0':
                if last_rising is not None:
                    pulse_widths.append(time - last_rising)
                    last_falling = time
                    last_rising = None
        
        # 计算统计值
        if not pulse_widths:
            return {
                'pulse_count': 0,
                'min_width_ps': 0,
                'max_width_ps': 0,
                'avg_width_ps': 0,
                'periods_ps': [],
                'duty_cycle': 0,
                'first_pulse_ps': None,
                'last_pulse_ps': None
            }
        
        # 占空比计算
        total_high = sum(pulse_widths)
        total_period = sum(periods) if periods else total_high
        duty_cycle = total_high / total_period if total_period > 0 else 0
        
        return {
            'pulse_count': len(pulse_widths),
            'min_width_ps': min(pulse_widths),
            'max_width_ps': max(pulse_widths),
            'avg_width_ps': sum(pulse_widths) / len(pulse_widths),
            'periods_ps': periods,
            'duty_cycle': duty_cycle,
            'first_pulse_ps': changes[0][0] if changes else None,
            'last_pulse_ps': changes[-1][0] if changes else None
        }


def analyze_clock(vcd_file: str, signal: str,
                  window: Optional[Tuple[int, int]] = None) -> Dict:
    """
    时钟信号分析
    
    Args:
        vcd_file: VCD 文件路径
        signal: 时钟信号名
        window: 时间窗口 (start_ps, end_ps)
    
    Returns:
        {
            'frequency_mhz': float,          # 频率 (MHz)
            'period_ps': float,              # 周期 (ps)
            'duty_cycle': float,             # 占空比
            'jitter_ps': float,              # 抖动 (ps)
            'stable': bool,                  # 是否稳定
            'edges': List[Tuple[int, str]],  # 跳变沿列表
            'edge_count': int                # 跳变沿总数
        }
    """
    with VCDSmartStream(vcd_file) as q:
        q.parse_header_fast()
        
        start_time = window[0] if window else 0
        end_time = window[1] if window else None
        changes = q.query_window(signal, start_time, end_time)
        
        if not changes:
            return {
                'frequency_mhz': 0,
                'period_ps': 0,
                'duty_cycle': 0,
                'jitter_ps': 0,
                'stable': True,
                'edges': [],
                'edge_count': 0
            }
        
        # 提取边沿
        edges = []
        for i, (time, value) in enumerate(changes):
            if i > 0:
                edge_type = 'rising' if value == '1' else 'falling'
                edges.append((time, edge_type))
        
        # 计算周期
        periods = []
        last_rising = None
        for time, value in changes:
            if value == '1' and last_rising is not None:
                periods.append(time - last_rising)
            if value == '1':
                last_rising = time
        
        if not periods:
            return {
                'frequency_mhz': 0,
                'period_ps': 0,
                'duty_cycle': 0,
                'jitter_ps': 0,
                'stable': True,
                'edges': edges,
                'edge_count': len(edges)
            }
        
        # 频率和抖动
        avg_period = sum(periods) / len(periods)
        frequency_mhz = 1e6 / avg_period if avg_period > 0 else 0
        
        # 抖动（周期标准差）
        jitter = 0
        if len(periods) > 1:
            variance = sum((p - avg_period) ** 2 for p in periods) / len(periods)
            jitter = variance ** 0.5
        
        # 稳定性判断（抖动 < 5% 周期）
        stable = jitter < (avg_period * 0.05) if avg_period > 0 else True
        
        # 占空比
        high_times = []
        low_times = []
        last_rising = None
        for time, value in changes:
            if value == '1':
                last_rising = time
            elif last_rising is not None:
                high_times.append(time - last_rising)
                last_rising = None
                if len(changes) > len(high_times) + 1:
                    low_times.append(changes[changes.index((time, value)) + 1][0] - time if changes.index((time, value)) + 1 < len(changes) else 0)
        
        total_high = sum(high_times) if high_times else 0
        total_low = sum(low_times) if low_times else 0
        duty_cycle = total_high / (total_high + total_low) if (total_high + total_low) > 0 else 0.5
        
        return {
            'frequency_mhz': frequency_mhz,
            'period_ps': avg_period,
            'duty_cycle': duty_cycle,
            'jitter_ps': jitter,
            'stable': stable,
            'edges': edges,
            'edge_count': len(edges)
        }


def analyze_bus(vcd_file: str, signals: Dict[str, str],
                window: Optional[Tuple[int, int]] = None) -> Dict:
    """
    总线分析
    
    Args:
        vcd_file: VCD 文件路径
        signals: 信号字典 {
            'data': 'bus_data[31:0]',
            'valid': 'bus_valid',
            'ready': 'bus_ready',
            'start': 'bus_start'  # 可选
        }
        window: 时间窗口
    
    Returns:
        {
            'transactions': List[Dict],      # 事务列表
            'transaction_count': int,        # 事务总数
            'burst_count': int,              # Burst 数量
            'avg_burst_len': float,          # 平均 Burst 长度
            'utilization': float,            # 总线利用率
            'stalls': int,                   # 停顿次数
            'avg_latency_ps': float          # 平均延迟
        }
    """
    with VCDSmartStream(vcd_file) as q:
        q.parse_header_fast()
        
        start_time = window[0] if window else 0
        end_time = window[1] if window else None
        
        # 查询所有信号
        valid_changes = q.query_window(signals['valid'], start_time, end_time)
        ready_changes = q.query_window(signals['ready'], start_time, end_time) if 'ready' in signals else []
        
        # 事务分析
        transactions = []
        current_txn = None
        burst_len = 0
        stall_count = 0
        
        valid_high = False
        ready_high = False
        
        # 合并时间线
        all_times = sorted(set([t for t, v in valid_changes] + [t for t, v in ready_changes]))
        
        for time in all_times:
            # 更新 valid 状态
            for t, v in valid_changes:
                if t == time:
                    valid_high = (v == '1')
            
            # 更新 ready 状态
            for t, v in ready_changes:
                if t == time:
                    ready_high = (v == '1')
            
            # 检测事务开始
            if valid_high and current_txn is None:
                current_txn = {
                    'start_time': time,
                    'end_time': None,
                    'transfers': 0,
                    'stalls': 0
                }
            
            # 检测传输
            if current_txn is not None and valid_high and ready_high:
                current_txn['transfers'] += 1
                burst_len += 1
            
            # 检测停顿
            if current_txn is not None and valid_high and not ready_high:
                stall_count += 1
                if current_txn:
                    current_txn['stalls'] += 1
            
            # 检测事务结束
            if current_txn is not None and not valid_high:
                current_txn['end_time'] = time
                current_txn['latency_ps'] = time - current_txn['start_time']
                transactions.append(current_txn)
                current_txn = None
        
        # 统计
        txn_count = len(transactions)
        burst_count = sum(1 for t in transactions if t['transfers'] > 1)
        avg_burst = sum(t['transfers'] for t in transactions) / txn_count if txn_count > 0 else 0
        avg_latency = sum(t['latency_ps'] for t in transactions) / txn_count if txn_count > 0 else 0
        
        # 总线利用率
        total_time = (end_time - start_time) if end_time else 0
        active_time = sum(t['end_time'] - t['start_time'] for t in transactions if t['end_time'])
        utilization = active_time / total_time if total_time > 0 else 0
        
        return {
            'transactions': transactions,
            'transaction_count': txn_count,
            'burst_count': burst_count,
            'avg_burst_len': avg_burst,
            'utilization': utilization,
            'stalls': stall_count,
            'avg_latency_ps': avg_latency
        }


def analyze_fsm(vcd_file: str, state_signals: List[str],
                window: Optional[Tuple[int, int]] = None) -> Dict:
    """
    状态机分析
    
    Args:
        vcd_file: VCD 文件路径
        state_signals: 状态信号列表 [state[0], state[1], ...]
        window: 时间窗口
    
    Returns:
        {
            'states_visited': List[str],     # 访问过的状态
            'state_encoding': Dict[str, str],# 状态编码
            'transitions': List[Dict],       # 状态转移
            'loops': List[Dict],             # 循环检测
            'dead_states': List[str],        # 死状态
            'unique_states': int             # 唯一状态数
        }
    """
    with VCDSmartStream(vcd_file) as q:
        q.parse_header_fast()
        
        start_time = window[0] if window else 0
        end_time = window[1] if window else None
        
        # 查询所有状态位
        state_changes = {}
        for sig in state_signals:
            changes = q.query_window(sig, start_time, end_time)
            state_changes[sig] = changes
        
        # 重建状态序列
        all_times = sorted(set(t for changes in state_changes.values() for t, v in changes))
        
        current_state = {}
        state_sequence = []
        
        for time in all_times:
            # 更新状态位
            for sig, changes in state_changes.items():
                for t, v in changes:
                    if t == time:
                        current_state[sig] = v
            
            # 编码状态
            state_bits = ''.join(current_state.get(sig, '0') for sig in sorted(state_signals))
            state_sequence.append((time, state_bits))
        
        # 分析状态转移
        transitions = []
        states_visited = set()
        transition_counts = defaultdict(int)
        
        for i in range(len(state_sequence) - 1):
            from_state = state_sequence[i][1]
            to_state = state_sequence[i + 1][1]
            time = state_sequence[i + 1][0]
            
            if from_state != to_state:
                transitions.append({
                    'from': from_state,
                    'to': to_state,
                    'time_ps': time
                })
                transition_counts[(from_state, to_state)] += 1
            
            states_visited.add(from_state)
        
        if state_sequence:
            states_visited.add(state_sequence[-1][1])
        
        # 检测循环
        loops = []
        for (from_s, to_s), count in transition_counts.items():
            if (to_s, from_s) in transition_counts and count > 1:
                loops.append({
                    'states': [from_s, to_s],
                    'count': count
                })
        
        # 检测死状态（只进入不离开）
        dead_states = []
        enter_count = defaultdict(int)
        exit_count = defaultdict(int)
        
        for t in transitions:
            enter_count[t['to']] += 1
            exit_count[t['from']] += 1
        
        for state in states_visited:
            if enter_count[state] > 0 and exit_count[state] == 0:
                dead_states.append(state)
        
        # 状态编码映射
        state_encoding = {f"STATE_{i}": bits for i, bits in enumerate(sorted(states_visited))}
        
        return {
            'states_visited': list(states_visited),
            'state_encoding': state_encoding,
            'transitions': transitions,
            'loops': loops,
            'dead_states': dead_states,
            'unique_states': len(states_visited)
        }


# CLI 接口（可选，用于测试）
if __name__ == '__main__':
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='VCD 深度分析工具')
    parser.add_argument('vcd_file', help='VCD 文件路径')
    parser.add_argument('--pulse', help='脉冲分析信号')
    parser.add_argument('--clock', help='时钟分析信号')
    parser.add_argument('--bus', nargs='+', help='总线分析信号')
    parser.add_argument('--fsm', nargs='+', help='状态机分析信号')
    parser.add_argument('--start-time', type=int, default=0, help='开始时间 (ps)')
    parser.add_argument('--end-time', type=int, help='结束时间 (ps)')
    
    args = parser.parse_args()
    
    window = (args.start_time, args.end_time) if args.end_time else None
    
    if args.pulse:
        result = analyze_pulse(args.vcd_file, args.pulse, window)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if args.clock:
        result = analyze_clock(args.vcd_file, args.clock, window)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if args.bus:
        signals = {'data': args.bus[0], 'valid': args.bus[1]}
        if len(args.bus) > 2:
            signals['ready'] = args.bus[2]
        result = analyze_bus(args.vcd_file, signals, window)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if args.fsm:
        result = analyze_fsm(args.vcd_file, args.fsm, window)
        print(json.dumps(result, indent=2, ensure_ascii=False))
