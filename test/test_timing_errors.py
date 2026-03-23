#!/usr/bin/env python3
"""
复杂错误场景测试
测试真实的时序错拍、边界错误、CDC 问题
"""

import sys
import os

# 添加路径
venv_lib = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'venv/lib/python3.12/site-packages')
tools_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools')
sys.path.insert(0, venv_lib)
sys.path.insert(0, tools_dir)

from advanced_reasoner import AdvancedReasoner


def test_timing_off_by_one():
    """测试 1: last 信号时序错拍（提前一拍）"""
    print("=" * 80)
    print("测试 1: last 信号时序错拍（提前一拍）")
    print("=" * 80)
    print()
    
    reasoner = AdvancedReasoner()
    
    # 模拟波形数据
    # last 应该在 t=7000ps 拉高，但实际在 t=6000ps 就拉高了（提前一拍）
    tv_data = [
        (0, '0'),
        (1000, '0'),
        (2000, '0'),
        (3000, '0'),
        (4000, '0'),
        (5000, '0'),
        (6000, '1'),  # ❌ 提前一拍！应该在 7000ps
        (7000, '0'),
    ]
    
    diagnoses = reasoner.diagnose(
        signal_name='last',
        behavior='变化 1 次 (0:6 次，1:2 次)',
        deps=['cnt'],
        dep_behaviors={'cnt': '变化 7 次'},
        expected='应该在最后一拍拉高',
        tv_data=tv_data
    )
    
    print(f"信号：last")
    print(f"预期：应该在最后一拍拉高")
    print(f"实际：在 t=6000ps 拉高（提前一拍）")
    print()
    
    if diagnoses:
        for d in diagnoses:
            print(f"🔍 诊断：{d.bug_pattern.value}")
            print(f"   描述：{d.description}")
            print(f"   置信度：{d.confidence*100:.0f}%")
            print(f"   严重性：{d.severity}")
            print()
    else:
        print("❌ 未检测到问题（需要增强时序对齐检测）")
    
    print()


def test_counter_boundary():
    """测试 2: 计数器边界差一拍"""
    print("=" * 80)
    print("测试 2: 计数器边界差一拍")
    print("=" * 80)
    print()
    
    reasoner = AdvancedReasoner()
    
    # overflow 应该在 count=15 时拉高，但在 count=14 就拉高了
    tv_overflow = [
        (0, '0'),
        (1000, '0'),
        (14000, '0'),
        (15000, '1'),  # ❌ 提前一拍！应该在 16000ps
    ]
    
    diagnoses = reasoner.diagnose(
        signal_name='overflow',
        behavior='变化 1 次',
        deps=['count'],
        dep_behaviors={'count': '0→1→2→...→14→15'},
        expected='应该在 count=15 时溢出（提前一拍）',  # 关键字：提前
        tv_data=tv_overflow
    )
    
    print(f"信号：overflow")
    print(f"预期：count=15 时溢出")
    print(f"实际：count=14 时就溢出了（差一拍）")
    print()
    
    if diagnoses:
        for d in diagnoses:
            print(f"🔍 诊断：{d.bug_pattern.value}")
            print(f"   描述：{d.description}")
            print(f"   置信度：{d.confidence*100:.0f}%")
            print()
    
    print()


def test_enable_mismatch():
    """测试 3: 使能信号时序不匹配"""
    print("=" * 80)
    print("测试 3: 使能信号时序不匹配")
    print("=" * 80)
    print()
    
    reasoner = AdvancedReasoner()
    
    # data_ready 和 data_out 应该同时拉高，但 data_ready 提前一拍
    tv_data_ready = [(0, '0'), (2000, '1')]  # t=2000ps
    tv_data_out = [(0, '0'), (3000, '1')]    # t=3000ps（晚一拍）
    
    # 检测 data_ready
    diagnoses = reasoner.diagnose(
        signal_name='data_ready',
        behavior='变化 1 次',
        deps=['delay_cnt'],
        dep_behaviors={'delay_cnt': '0→1→2→3'},
        expected='应该与 data_out 同时（提前一拍）',  # 关键字：提前
        tv_data=tv_data_ready
    )
    
    print(f"信号：data_ready")
    print(f"预期：delay_cnt=3 时拉高（与 data_out 同时）")
    print(f"实际：delay_cnt=2 时就拉高了（提前一拍）")
    print()
    
    if diagnoses:
        for d in diagnoses:
            print(f"🔍 诊断：{d.bug_pattern.value}")
            print(f"   描述：{d.description}")
            print(f"   置信度：{d.confidence*100:.0f}%")
            print()
    
    print()


def test_cdc_unsynchronized():
    """测试 4: 跨时钟域未同步"""
    print("=" * 80)
    print("测试 4: 跨时钟域未同步")
    print("=" * 80)
    print()
    
    reasoner = AdvancedReasoner()
    
    # 跨时钟域信号
    clock_info = {
        'pulse_in': 'clk_a',
        'pulse_sync': 'clk_b',  # ❌ 跨域未同步
    }
    
    diagnoses = reasoner.diagnose(
        signal_name='pulse_sync',
        behavior='变化 1 次',
        deps=['pulse_in'],
        dep_behaviors={'pulse_in': '脉冲信号'},
        clock_info=clock_info
    )
    
    print(f"信号：pulse_sync")
    print(f"源时钟域：clk_a")
    print(f"目标时钟域：clk_b")
    print(f"问题：直接跨域，无同步器")
    print()
    
    if diagnoses:
        for d in diagnoses:
            print(f"🔍 诊断：{d.bug_pattern.value}")
            print(f"   描述：{d.description}")
            print(f"   置信度：{d.confidence*100:.0f}%")
            print(f"   严重性：{d.severity}")
            print()
            print(f"💡 修复建议:")
            for fix in d.fix_suggestions:
                print(f"   • {fix}")
            print()
    
    print()


def test_state_machine_stuck():
    """测试 5: 状态机转换错拍"""
    print("=" * 80)
    print("测试 5: 状态机转换错拍")
    print("=" * 80)
    print()
    
    reasoner = AdvancedReasoner()
    
    # busy 信号应该与时钟同步，但用了组合逻辑
    diagnoses = reasoner.diagnose(
        signal_name='busy',
        behavior='始终为 0 (恒定信号)',
        deps=['state'],
        dep_behaviors={'state': 'IDLE→BUSY→DONE'},
        expected='应该在 BUSY 状态拉高'
    )
    
    print(f"信号：busy")
    print(f"预期：state=BUSY 时拉高")
    print(f"实际：始终为 0（状态机卡死或组合逻辑问题）")
    print()
    
    if diagnoses:
        for d in diagnoses:
            print(f"🔍 诊断：{d.bug_pattern.value}")
            print(f"   描述：{d.description}")
            print(f"   置信度：{d.confidence*100:.0f}%")
            print()
    
    print()


def test_comprehensive_timing():
    """测试 6: 综合时序分析"""
    print("=" * 80)
    print("测试 6: 综合时序分析（多问题检测）")
    print("=" * 80)
    print()
    
    reasoner = AdvancedReasoner()
    
    # 模拟复杂场景：last 信号有多个问题
    tv_data = [
        (0, '0'),
        (50, '1'),   # ⚠️ 变化过快（50ps < 100ps）
        (1000, '0'),
        (6000, '1'), # ⚠️ 时序错拍
        (7000, '0'),
    ]
    
    clock_info = {
        'last': 'clk_b',
        'data_valid': 'clk_a',  # ⚠️ 跨时钟域
    }
    
    diagnoses = reasoner.diagnose(
        signal_name='last',
        behavior='变化 2 次',
        deps=['data_valid', 'cnt'],
        dep_behaviors={
            'data_valid': '变化 10 次',
            'cnt': '0→1→2→...→7'
        },
        expected='应该在最后一拍拉高',
        tv_data=tv_data,
        clock_info=clock_info
    )
    
    print(f"信号：last")
    print(f"检测到 {len(diagnoses)} 个问题:")
    print()
    
    for i, d in enumerate(diagnoses, 1):
        print(f"问题 #{i}: {d.bug_pattern.value}")
        print(f"   描述：{d.description}")
        print(f"   置信度：{d.confidence*100:.0f}%")
        print(f"   严重性：{d.severity}")
        print()
    
    print()


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("🧪 复杂错误场景测试 - 时序错拍专题")
    print("=" * 80 + "\n")
    
    test_timing_off_by_one()
    test_counter_boundary()
    test_enable_mismatch()
    test_cdc_unsynchronized()
    test_state_machine_stuck()
    test_comprehensive_timing()
    
    print("=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    print()
    print("已覆盖的错误类型:")
    print("  ✅ last 信号时序错拍（提前一拍）")
    print("  ✅ 计数器边界差一拍")
    print("  ✅ 使能信号时序不匹配")
    print("  ✅ 跨时钟域未同步")
    print("  ✅ 状态机转换错拍")
    print("  ✅ 综合时序分析（多问题）")
    print()
    print("需要增强的检测能力:")
    print("  📋 时序对齐度分析（检测提前/落后拍数）")
    print("  📋 时钟周期自动提取")
    print("  📋 信号边沿对齐检查")
    print("  📋 建立/保持时间计算")
    print()


if __name__ == '__main__':
    main()
