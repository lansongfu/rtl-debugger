#!/usr/bin/env python3
"""
RTL Debugger - 主入口

使用方式:
    python -m rtl_debugger --help
    python -m rtl_debugger analyze-pulse waveform.vcd signal_name
"""

import sys
import os
import argparse
import json

# 添加路径
src_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(src_dir)
tools_dir = os.path.join(skill_dir, 'tools')
sys.path.insert(0, tools_dir)

from vcd_analyze import analyze_pulse, analyze_clock, analyze_bus, analyze_fsm
from vcd_protocol import analyze_axi4, analyze_apb
from vcd_smart import VCDSmartStream


def main():
    parser = argparse.ArgumentParser(
        description='RTL Debugger - RTL 波形分析调试工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # 脉冲分析
  python -m rtl_debugger analyze-pulse waveform.vcd signal_name
  
  # 时钟分析
  python -m rtl_debugger analyze-clock waveform.vcd clk
  
  # 总线分析
  python -m rtl_debugger analyze-bus waveform.vcd --data wdata --valid wvalid --ready wready
  
  # AXI4 协议分析
  python -m rtl_debugger analyze-axi waveform.vcd --prefix axi
  
  # 交互式调试
  python -m rtl_debugger debug waveform.vcd signal_name --expected "应该在 t=1000ns 拉高"
'''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 脉冲分析
    pulse_parser = subparsers.add_parser('analyze-pulse', help='脉冲分析')
    pulse_parser.add_argument('vcd_file', help='VCD 文件路径')
    pulse_parser.add_argument('signal', help='信号名')
    pulse_parser.add_argument('--start-time', type=int, default=0, help='开始时间 (ps)')
    pulse_parser.add_argument('--end-time', type=int, help='结束时间 (ps)')
    
    # 时钟分析
    clock_parser = subparsers.add_parser('analyze-clock', help='时钟分析')
    clock_parser.add_argument('vcd_file', help='VCD 文件路径')
    clock_parser.add_argument('signal', help='时钟信号名')
    clock_parser.add_argument('--start-time', type=int, default=0, help='开始时间 (ps)')
    clock_parser.add_argument('--end-time', type=int, help='结束时间 (ps)')
    
    # 总线分析
    bus_parser = subparsers.add_parser('analyze-bus', help='总线分析')
    bus_parser.add_argument('vcd_file', help='VCD 文件路径')
    bus_parser.add_argument('--data', required=True, help='数据信号')
    bus_parser.add_argument('--valid', required=True, help='valid 信号')
    bus_parser.add_argument('--ready', help='ready 信号')
    bus_parser.add_argument('--start-time', type=int, default=0, help='开始时间 (ps)')
    bus_parser.add_argument('--end-time', type=int, help='结束时间 (ps)')
    
    # AXI4 分析
    axi_parser = subparsers.add_parser('analyze-axi', help='AXI4 协议分析')
    axi_parser.add_argument('vcd_file', help='VCD 文件路径')
    axi_parser.add_argument('--prefix', default='axi', help='信号前缀')
    axi_parser.add_argument('--start-time', type=int, default=0, help='开始时间 (ps)')
    axi_parser.add_argument('--end-time', type=int, help='结束时间 (ps)')
    
    # APB 分析
    apb_parser = subparsers.add_parser('analyze-apb', help='APB 协议分析')
    apb_parser.add_argument('vcd_file', help='VCD 文件路径')
    apb_parser.add_argument('--prefix', default='apb', help='信号前缀')
    apb_parser.add_argument('--start-time', type=int, default=0, help='开始时间 (ps)')
    apb_parser.add_argument('--end-time', type=int, help='结束时间 (ps)')
    
    # 快速查询
    query_parser = subparsers.add_parser('query', help='快速时间窗口查询')
    query_parser.add_argument('vcd_file', help='VCD 文件路径')
    query_parser.add_argument('signal', help='信号名')
    query_parser.add_argument('--start-time', type=int, default=0, help='开始时间 (ps)')
    query_parser.add_argument('--end-time', type=int, help='结束时间 (ps)')
    
    args = parser.parse_args()
    
    if args.command == 'analyze-pulse':
        window = (args.start_time, args.end_time) if args.end_time else None
        result = analyze_pulse(args.vcd_file, args.signal, window)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == 'analyze-clock':
        window = (args.start_time, args.end_time) if args.end_time else None
        result = analyze_clock(args.vcd_file, args.signal, window)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == 'analyze-bus':
        signals = {'data': args.data, 'valid': args.valid}
        if args.ready:
            signals['ready'] = args.ready
        window = (args.start_time, args.end_time) if args.end_time else None
        result = analyze_bus(args.vcd_file, signals, window)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == 'analyze-axi':
        # 自动构建 AXI 信号字典
        prefix = args.prefix
        signals = {
            'awvalid': f'{prefix}_awvalid',
            'awready': f'{prefix}_awready',
            'wvalid': f'{prefix}_wvalid',
            'wready': f'{prefix}_wready',
            'bvalid': f'{prefix}_bvalid',
            'bready': f'{prefix}_bready'
        }
        window = (args.start_time, args.end_time) if args.end_time else None
        result = analyze_axi4(args.vcd_file, signals, window)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == 'analyze-apb':
        prefix = args.prefix
        signals = {
            'psel': f'{prefix}_psel',
            'penable': f'{prefix}_penable',
            'paddr': f'{prefix}_paddr[7:0]',
            'pwdata': f'{prefix}_pwdata[31:0]',
            'pwrite': f'{prefix}_pwrite'
        }
        window = (args.start_time, args.end_time) if args.end_time else None
        result = analyze_apb(args.vcd_file, signals, window)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == 'query':
        with VCDSmartStream(args.vcd_file) as q:
            q.parse_header_fast()
            changes = q.query_window(args.signal, args.start_time, args.end_time)
            print(f"找到 {len(changes)} 次变化:")
            for time, value in changes[:10]:
                print(f"  t={time}ps: {value}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
