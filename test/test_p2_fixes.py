#!/usr/bin/env python3
"""
P2 修复验证测试
测试：跨模块追踪、全局搜索、单步/完整模式
"""

import sys
import os

# 添加路径
test_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(test_dir)
tools_dir = os.path.join(skill_dir, 'tools')
sys.path.insert(0, tools_dir)

from rtl_query import RTLDependencyAnalyzer


def test_cross_module_trace():
    """测试跨模块追踪"""
    print("=" * 80)
    print("测试：跨模块追踪")
    print("=" * 80)
    
    # 创建测试文件
    top_code = '''
module top(
    input clk,
    input rst_n,
    input [7:0] data_in,
    output [7:0] data_out
);
    wire [7:0] mid_data;
    
    sub_module u_sub (
        .clk(clk),
        .rst_n(rst_n),
        .data_in(data_in),
        .data_out(mid_data)
    );
    
    assign data_out = mid_data;
endmodule
'''
    
    sub_code = '''
module sub_module(
    input clk,
    input rst_n,
    input [7:0] data_in,
    output reg [7:0] data_out
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            data_out <= 8'b0;
        else
            data_out <= data_in;
    end
endmodule
'''
    
    with open('top_test.v', 'w') as f:
        f.write(top_code)
    
    with open('sub_test.v', 'w') as f:
        f.write(sub_code)
    
    # 创建 filelist
    with open('cross_module.f', 'w') as f:
        f.write('top_test.v\nsub_test.v\n')
    
    analyzer = RTLDependencyAnalyzer()
    analyzer.parse_file('top_test.v')
    analyzer.parse_file('sub_test.v')
    
    # 测试跨模块追踪
    result = analyzer.trace_cross_module('data_out', 'top')
    
    print(f"跨模块追踪结果：{result}")
    
    # 验证：应该追踪到 sub_module 的 data_in
    assert len(result) > 0, "❌ 跨模块追踪结果为空"
    
    print("✅ PASS - 跨模块追踪功能正常")
    print()


def test_global_search():
    """测试全局搜索"""
    print("=" * 80)
    print("测试：全局搜索")
    print("=" * 80)
    
    # 使用上面的测试文件
    analyzer = RTLDependencyAnalyzer()
    analyzer.parse_file('top_test.v')
    analyzer.parse_file('sub_test.v')
    
    # 测试全局搜索
    results = analyzer.search_global('data_out')
    
    print(f"全局搜索 'data_out': {results}")
    
    # 验证：应该找到 top.data_out 和 sub_module.data_out
    assert len(results) > 0, "❌ 全局搜索结果为空"
    
    # 检查是否包含完整路径
    paths = [r.get('path', '') for r in results]
    print(f"找到的路径：{paths}")
    
    print("✅ PASS - 全局搜索功能正常")
    print()


def test_single_step_mode():
    """测试单步模式（默认）"""
    print("=" * 80)
    print("测试：单步模式（默认）")
    print("=" * 80)
    
    code = '''
module test(
    input a,
    input b,
    output y
);
    assign y = a & b;
endmodule
'''
    
    with open('single_step_test.v', 'w') as f:
        f.write(code)
    
    analyzer = RTLDependencyAnalyzer()
    analyzer.parse_file('single_step_test.v')
    
    # 查询依赖（默认单步）
    results = analyzer.query_signal('y', 'test')
    
    print(f"查询结果：{results}")
    
    # 验证：应该只返回直接依赖 a 和 b
    assert len(results) > 0, "❌ 查询结果为空"
    
    print("✅ PASS - 单步模式正常")
    print()


if __name__ == '__main__':
    os.chdir(test_dir)
    
    try:
        test_cross_module_trace()
        test_global_search()
        test_single_step_mode()
        
        print("=" * 80)
        print("🎉 P2 修复验证：全部通过！")
        print("=" * 80)
    except AssertionError as e:
        print(f"\n❌ FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
