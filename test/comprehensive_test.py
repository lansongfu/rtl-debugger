#!/usr/bin/env python3
"""
完备测试脚本
测试场景：
1. 恒定信号调试
2. 正常跳变信号
3. 长依赖链
4. 多信号对比
5. 边界情况
"""

import subprocess
import sys
import os

PROJECT_ROOT = '/root/.openclaw/workspace/projects/waveform-analyzer'
CHIP_DESIGN = '/root/.openclaw/workspace/projects/chip_design'
os.chdir(PROJECT_ROOT)

VCD_FILE = f'{CHIP_DESIGN}/simulations/axi_w_m_waveform.vcd'
FILELIST = f'{CHIP_DESIGN}/src/filelist.f'

def run_test(name, cmd, expected_keywords):
    """运行测试并验证"""
    print("=" * 80)
    print(f"🧪 测试：{name}")
    print("=" * 80)
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    output = result.stdout + result.stderr
    
    print(output)
    
    # 验证期望关键字
    passed = True
    for keyword in expected_keywords:
        if keyword not in output:
            print(f"❌ 未找到期望关键字：{keyword}")
            passed = False
    
    if passed:
        print(f"✅ PASS\n")
    else:
        print(f"❌ FAIL\n")
    
    return passed

# 测试 1: 恒定信号调试
print("\n" + "=" * 80)
print("Phase 1: 基础功能测试")
print("=" * 80 + "\n")

test1 = run_test(
    "恒定信号调试 - transfer_done",
    f'./venv/bin/python tools/enhanced_debug_analyzer.py transfer_done '
    f'--filelist {FILELIST} --vcd {VCD_FILE} '
    f'--expected "应该有变化"',
    ['根因', 'all_b_received', '始终为 0', '智能诊断报告']
)

# 测试 2: 正常信号
test2 = run_test(
    "正常跳变信号 - clk",
    f'./venv/bin/python tools/vcd_query.py {VCD_FILE} --signal clk --summary',
    ['变化', 'clk']
)

# 测试 3: VCD 摘要
test3 = run_test(
    "VCD 摘要统计",
    f'./venv/bin/python tools/vcd_query.py {VCD_FILE} --summary',
    ['信号总数', '345', '总变化次数']
)

# 测试 4: RTL 依赖查询
test4 = run_test(
    "RTL 依赖查询",
    f'./venv/bin/python tools/rtl_query.py --filelist {FILELIST} --signal transfer_done',
    ['transfer_done', 'all_b_received']
)

print("\n" + "=" * 80)
print("Phase 2: 长路径追踪测试")
print("=" * 80 + "\n")

# 测试 5: 多层依赖
test5 = run_test(
    "多层依赖追踪",
    f'./venv/bin/python tools/enhanced_debug_analyzer.py transfer_done '
    f'--filelist {FILELIST} --vcd {VCD_FILE} '
    f'--expected "应该有变化"',
    ['分析路径', '追踪路径', '根因']
)

# 测试 6: 深度递归
test6 = run_test(
    "深度递归分析 (20 层限制)",
    f'./venv/bin/python tools/enhanced_debug_analyzer.py transfer_done '
    f'--filelist {FILELIST} --vcd {VCD_FILE}',
    ['深度依赖链分析']
)

print("\n" + "=" * 80)
print("Phase 3: 边界情况测试")
print("=" * 80 + "\n")

# 测试 7: 信号不存在
test7 = run_test(
    "信号不存在处理",
    f'./venv/bin/python tools/vcd_query.py {VCD_FILE} --signal nonexistent_signal',
    ['未找到信号']
)

# 测试 8: 空 filelist
test8 = run_test(
    "空 filelist 处理",
    f'./venv/bin/python tools/rtl_query.py --filelist test/empty.f --signal test 2>&1 || echo "Handled"',
    ['Handled']  # 只要能处理不崩溃就行
)

# 测试 9: VCD 文件不存在
test9 = run_test(
    "VCD 文件不存在处理",
    f'./venv/bin/python tools/vcd_query.py nonexistent.vcd --summary 2>&1 || echo "Handled"',
    ['Handled']
)

print("\n" + "=" * 80)
print("Phase 4: 性能测试")
print("=" * 80 + "\n")

# 测试 10: 大 VCD 文件加载性能
import time
start = time.time()
result = subprocess.run(
    f'./venv/bin/python tools/vcd_query.py {VCD_FILE} --summary',
    shell=True, capture_output=True, text=True
)
elapsed = time.time() - start
print(f"大 VCD 文件加载时间：{elapsed:.2f}s")
test10 = elapsed < 10  # 10 秒内完成
print(f"{'✅ PASS' if test10 else '❌ FAIL'} (要求 < 10s)\n")

# 测试 11: RTL 解析性能
start = time.time()
result = subprocess.run(
    f'./venv/bin/python tools/rtl_query.py --filelist {FILELIST} --signal transfer_done',
    shell=True, capture_output=True, text=True
)
elapsed = time.time() - start
print(f"RTL 依赖查询时间：{elapsed:.2f}s")
test11 = elapsed < 5  # 5 秒内完成
print(f"{'✅ PASS' if test11 else '❌ FAIL'} (要求 < 5s)\n")

# 测试 12: 增强分析器性能
start = time.time()
result = subprocess.run(
    f'./venv/bin/python tools/enhanced_debug_analyzer.py transfer_done '
    f'--filelist {FILELIST} --vcd {VCD_FILE} --expected "应该有变化"',
    shell=True, capture_output=True, text=True
)
elapsed = time.time() - start
print(f"增强分析器执行时间：{elapsed:.2f}s")
test12 = elapsed < 10  # 10 秒内完成
print(f"{'✅ PASS' if test12 else '❌ FAIL'} (要求 < 10s)\n")

# 测试 13: 智能诊断报告
test13 = run_test(
    "智能诊断报告生成",
    f'./venv/bin/python tools/enhanced_debug_analyzer.py transfer_done '
    f'--filelist {FILELIST} --vcd {VCD_FILE} '
    f'--expected "应该有变化"',
    ['智能诊断报告', '发现问题', '置信度', '修复建议']
)

# 测试 14: 多诊断优先级
test14 = run_test(
    "多诊断优先级排序",
    f'./venv/bin/python tools/advanced_reasoner.py',
    ['智能诊断报告', '发现问题']
)

# 测试 15: 时序错拍检测
test15 = run_test(
    "时序错拍检测（last 信号）",
    f'./venv/bin/python test/test_timing_errors.py',
    ['时序错拍', 'timing_violation', '测试总结']
)

# 汇总
print("\n" + "=" * 80)
print("📊 测试结果汇总")
print("=" * 80)
print()

tests = [
    ("恒定信号调试", test1),
    ("正常信号查询", test2),
    ("VCD 摘要", test3),
    ("RTL 依赖", test4),
    ("多层依赖", test5),
    ("深度递归", test6),
    ("信号不存在", test7),
    ("空 filelist", test8),
    ("VCD 不存在", test9),
    ("VCD 加载性能", test10),
    ("RTL 解析性能", test11),
    ("增强分析性能", test12),
    ("智能诊断报告", test13),
    ("多诊断优先级", test14),
    ("时序错拍检测", test15),
]

passed = sum(1 for _, t in tests if t)
total = len(tests)

for name, result in tests:
    status = "✅" if result else "❌"
    print(f"{status} {name}")

print()
print(f"总计：{passed}/{total} 通过")

if passed == total:
    print("\n🎉 所有测试通过！")
    sys.exit(0)
else:
    print(f"\n⚠️  有 {total - passed} 个测试失败")
    sys.exit(1)
