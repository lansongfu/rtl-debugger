#!/usr/bin/env python3
"""
P1 修复验证测试
测试：parameter 端口、实例化误匹配、位选解析
"""

import sys
import os

# 添加路径
test_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(test_dir)
tools_dir = os.path.join(skill_dir, 'tools')
sys.path.insert(0, tools_dir)

from rtl_query import RTLDependencyAnalyzer


def test_parameter_module():
    """测试 parameter 端口模块解析"""
    print("=" * 80)
    print("测试：parameter 端口模块解析")
    print("=" * 80)
    
    code = '''
module fifo #(
    parameter DATA_WIDTH = 8,
    parameter DEPTH = 16
) (
    input clk,
    input rst_n,
    input [DATA_WIDTH-1:0] data_in,
    output [DATA_WIDTH-1:0] data_out
);
    reg [DATA_WIDTH-1:0] data_reg;
    always @(posedge clk) begin
        if (!rst_n)
            data_reg <= 0;
        else
            data_reg <= data_in;
    end
    assign data_out = data_reg;
endmodule
'''
    
    with open('parameter_module_test.v', 'w') as f:
        f.write(code)
    
    analyzer = RTLDependencyAnalyzer()
    analyzer.parse_file('parameter_module_test.v')
    
    # 检查模块是否正确解析
    assert 'fifo' in analyzer.modules, "❌ 模块 'fifo' 未解析"
    
    # 检查端口
    ports = analyzer.modules['fifo']['ports']
    assert 'clk' in ports, "❌ 端口 'clk' 未识别"
    assert 'rst_n' in ports, "❌ 端口 'rst_n' 未识别"
    assert 'data_in' in ports, "❌ 端口 'data_in' 未识别"
    assert 'data_out' in ports, "❌ 端口 'data_out' 未识别"
    
    # 检查依赖
    deps = analyzer.modules['fifo']['dependencies']
    assert 'data_reg' in deps, "❌ 信号 'data_reg' 依赖未解析"
    assert 'data_out' in deps, "❌ 信号 'data_out' 依赖未解析"
    
    print("✅ PASS - parameter 端口模块解析正确")
    print()


def test_instance_parsing():
    """测试实例化解析不误匹配 posedge/if/case"""
    print("=" * 80)
    print("测试：实例化解析（不误匹配 posedge/if/case）")
    print("=" * 80)
    
    code = '''
module top(
    input clk,
    input rst_n,
    input [7:0] data_in,
    output [7:0] data_out
);
    wire [7:0] mid_data;
    
    // 正确的实例化
    fifo #(.DATA_WIDTH(8)) u_fifo (
        .clk(clk),
        .rst_n(rst_n),
        .data_in(data_in),
        .data_out(mid_data)
    );
    
    reg [7:0] data_reg;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            data_reg <= 0;
        else if (data_valid)
            data_reg <= mid_data;
    end
    
    assign data_out = data_reg;
endmodule
'''
    
    with open('instance_test.v', 'w') as f:
        f.write(code)
    
    analyzer = RTLDependencyAnalyzer()
    analyzer.parse_file('instance_test.v')
    
    # 检查模块解析
    assert 'top' in analyzer.modules, "❌ 模块 'top' 未解析"
    assert 'fifo' not in analyzer.modules, "⚠️  实例化模块 'fifo' 被误认为模块定义"
    
    # 检查实例化
    instances = analyzer.modules['top'].get('instances', [])
    assert len(instances) > 0, "❌ 实例化未识别"
    
    # 找到 u_fifo 实例
    u_fifo = None
    for inst in instances:
        if inst.get('name') == 'u_fifo':
            u_fifo = inst
            break
    
    assert u_fifo is not None, "❌ 实例 'u_fifo' 未识别"
    assert u_fifo.get('type') == 'fifo', f"❌ 模块类型识别错误：{u_fifo}"
    
    # 检查端口连接
    connections = u_fifo.get('connections', {})
    assert 'clk' in connections, "❌ 端口连接 '.clk' 未识别"
    assert 'rst_n' in connections, "❌ 端口连接 '.rst_n' 未识别"
    assert 'data_in' in connections, "❌ 端口连接 '.data_in' 未识别"
    assert 'data_out' in connections, "❌ 端口连接 '.data_out' 未识别"
    
    print("✅ PASS - 实例化解析正确，无误匹配")
    print()


def test_bit_selection():
    """测试位选和拼接解析"""
    print("=" * 80)
    print("测试：端口连接位选和拼接解析")
    print("=" * 80)
    
    code = '''
module top(
    input [31:0] data_in,
    output [31:0] data_out
);
    wire [7:0] byte0, byte1, byte2, byte3;
    wire [1:0] ctrl;
    
    // 位选连接
    slice_8bit u_slice0 (
        .data_in(data_in[7:0]),
        .data_out(byte0)
    );
    
    slice_8bit u_slice1 (
        .data_in(data_in[15:8]),
        .data_out(byte1)
    );
    
    // 拼接连接
    concat_4x8 u_concat (
        .byte0(byte0),
        .byte1(byte1),
        .byte2(byte2),
        .byte3(byte3),
        .data_out(data_out)
    );
    
    // 复制连接
    wire rst_n = 1'b1;
    reg [3:0] rst_sync;
    assign rst_sync = {4{rst_n}};
    
endmodule

module slice_8bit(
    input [7:0] data_in,
    output [7:0] data_out
);
    assign data_out = data_in;
endmodule
'''
    
    with open('bit_select_test.v', 'w') as f:
        f.write(code)
    
    analyzer = RTLDependencyAnalyzer()
    analyzer.parse_file('bit_select_test.v')
    
    # 检查模块解析
    assert 'top' in analyzer.modules, "❌ 模块 'top' 未解析"
    assert 'slice_8bit' in analyzer.modules, "❌ 模块 'slice_8bit' 未解析"
    
    # 检查实例化
    instances = analyzer.modules['top'].get('instances', [])
    print(f"  实例数量：{len(instances)}")
    for inst in instances:
        print(f"    - {inst.get('name')}")
    
    # 找到 u_slice0 实例（位选）
    u_slice0 = None
    for inst in instances:
        if inst.get('name') == 'u_slice0':
            u_slice0 = inst
            break
    
    assert u_slice0 is not None, f"❌ 实例 'u_slice0' 未识别，实际实例：{[i.get('name') for i in instances]}"
    
    # 检查位选连接
    connections = u_slice0.get('connections', {})
    assert 'data_in' in connections, "❌ 端口 'data_in' 未识别"
    # 检查是否包含位选信息
    data_in_conn = connections['data_in']
    assert '[' in data_in_conn, f"❌ 位选信息丢失：{data_in_conn}"
    
    print("✅ PASS - 位选和拼接解析正确")
    print()


def test_case_statement():
    """测试 case 语句不误匹配为实例化"""
    print("=" * 80)
    print("测试：case 语句不误匹配为实例化")
    print("=" * 80)
    
    code = '''
module fsm(
    input clk,
    input rst_n,
    input [1:0] state_in,
    output reg [1:0] state_out
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state_out <= 2'b00;
        else begin
            case (state_in)
                2'b00: state_out <= 2'b01;
                2'b01: state_out <= 2'b10;
                2'b10: state_out <= 2'b11;
                2'b11: state_out <= 2'b00;
                default: state_out <= 2'b00;
            endcase
        end
    end
endmodule
'''
    
    with open('case_test.v', 'w') as f:
        f.write(code)
    
    analyzer = RTLDependencyAnalyzer()
    analyzer.parse_file('case_test.v')
    
    # 检查模块解析
    assert 'fsm' in analyzer.modules, "❌ 模块 'fsm' 未解析"
    
    # 检查实例化（应该为空，因为没有实例化）
    instances = analyzer.modules['fsm'].get('instances', [])
    assert len(instances) == 0, f"❌ case 语句被误匹配为实例化：{instances}"
    
    print("✅ PASS - case 语句无误匹配")
    print()


if __name__ == '__main__':
    # 确保 test 目录存在
    os.makedirs(test_dir, exist_ok=True)
    os.chdir(test_dir)
    
    try:
        test_parameter_module()
        test_instance_parsing()
        test_bit_selection()
        test_case_statement()
        
        print("=" * 80)
        print("🎉 P1 修复验证：全部通过！")
        print("=" * 80)
    except AssertionError as e:
        print(f"\n❌ FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
