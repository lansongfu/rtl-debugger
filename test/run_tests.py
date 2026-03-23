#!/usr/bin/env python3
"""
RTL 解析器测试套件
测试所有 P0+P1 功能
"""

import subprocess
import sys
import os

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

VENv_PYTHON = os.path.join(PROJECT_ROOT, 'venv/bin/python')
TOOLS = os.path.join(PROJECT_ROOT, 'tools/rtl_query.py')

tests_passed = 0
tests_failed = 0

def run_test(name, args, expected_in_output):
    """运行单个测试"""
    global tests_passed, tests_failed
    
    print(f"\n{'='*80}")
    print(f"测试：{name}")
    print(f"{'='*80}")
    
    cmd = [VENv_PYTHON, TOOLS] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + result.stderr
    
    # 检查期望的输出
    success = all(exp in output for exp in expected_in_output)
    
    if success:
        print(f"✅ PASS")
        tests_passed += 1
    else:
        print(f"❌ FAIL")
        print(f"期望包含：{expected_in_output}")
        print(f"实际输出:\n{output}")
        tests_failed += 1
    
    return success

# ========== 测试用例 ==========

# 测试 1: 基础 assign 语句
run_test(
    "基础 assign 语句",
    ['test/define_test.v', '--signal', 'data_out'],
    ['data_out', '←', 'result']
)

# 测试 2: 嵌套 filelist（三层）
run_test(
    "嵌套 filelist（三层）",
    ['--filelist', 'test/filelist_main.f', '--signal', 'data_out'],
    ['data_out']
)

# 测试 2b: 环境变量支持（需要设置环境变量）
import os
os.environ['PROJECT_ROOT'] = '/root/.openclaw/workspace/projects'
run_test(
    "环境变量支持 ($VAR)",
    ['--filelist', 'test/env_filelist.f', '--signal', 'data_out'],
    ['data_out', 'result']
)

# 测试 3: `define 展开
run_test(
    "`define 宏定义",
    ['test/define_test.v', '--signal', 'data_out'],
    ['result', 'data_in']
)

# 测试 4: parameter/localparam
run_test(
    "parameter/localparam",
    ['test/param_test.v', '--signal', 'dout'],
    ['dout', 'processed_data', 'data_reg']
)

# 测试 5: `include 文件包含
run_test(
    "`include 文件包含",
    ['test/include_test.v', '--signal', 'out'],
    ['out', 'test_wire', 'global_signal']
)

# 测试 6: 多文件联合分析
run_test(
    "多文件联合分析",
    ['test/define_test.v', 'test/param_test.v', '--signal', 'dout'],
    ['dout', 'processed_data']
)

# ========== 测试结果 ==========

print(f"\n{'='*80}")
print(f"测试结果汇总")
print(f"{'='*80}")
print(f"✅ 通过：{tests_passed}")
print(f"❌ 失败：{tests_failed}")
print(f"总计：{tests_passed + tests_failed}")

if tests_failed > 0:
    sys.exit(1)
else:
    print("\n🎉 所有测试通过！")
    sys.exit(0)
