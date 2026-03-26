"""
RTL Debugger - 标准包接口

使用方式:
    from rtl_debugger import analyze_axi4, analyze_pulse, InteractiveDebugger, RTLDependencyAnalyzer

功能:
- 深度信号分析：脉冲/时钟/总线/状态机
- 协议解析：AXI4/APB/AHB
- 交互式调试：自动追踪根因
- RTL 依赖分析：单步/完整/跨模块追踪
"""

import sys
import os

# 添加 tools 到路径
src_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(src_dir)
tools_dir = os.path.join(skill_dir, 'tools')
sys.path.insert(0, tools_dir)

# 导入深度分析函数
from vcd_analyze import (
    analyze_pulse,
    analyze_clock,
    analyze_bus,
    analyze_fsm
)

# 导入协议解析函数
from vcd_protocol import (
    analyze_axi4,
    analyze_apb,
    analyze_ahb
)

# 导入流式查询
from vcd_smart import VCDSmartStream

# 导入交互式调试器
from interactive_debugger import InteractiveDebugger

# 导入 RTL 依赖分析器
from rtl_query import RTLDependencyAnalyzer

# 导出所有公共 API
__all__ = [
    # 深度分析
    'analyze_pulse',
    'analyze_clock',
    'analyze_bus',
    'analyze_fsm',
    
    # 协议解析
    'analyze_axi4',
    'analyze_apb',
    'analyze_ahb',
    
    # 工具类
    'VCDSmartStream',
    'InteractiveDebugger',
    'RTLDependencyAnalyzer'
]

# 版本信息
__version__ = '1.5.0'
__author__ = '木叶村克劳'
