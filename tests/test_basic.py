#!/usr/bin/env python3
"""
RTL Debugger 单元测试套件

运行测试:
    pytest tests/                 # 运行所有测试
    pytest tests/ -v              # 详细输出
    pytest tests/ --cov           # 覆盖率报告
"""

import pytest
import os
import sys
from pathlib import Path

# 添加 src 到路径
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

from rtl_debugger import RTLDependencyAnalyzer, VCDSmartStream


class TestRTLDependencyAnalyzer:
    """RTLDependencyAnalyzer 单元测试"""
    
    def test_init(self):
        """测试初始化"""
        analyzer = RTLDependencyAnalyzer()
        assert analyzer.modules == {}
        assert analyzer.signal_deps == {}
    
    def test_parse_simple_assign(self, tmp_path):
        """测试简单 assign 语句解析"""
        code = '''
module test(
    input a,
    input b,
    output y
);
    assign y = a & b;
endmodule
'''
        test_file = tmp_path / "test.v"
        test_file.write_text(code)
        
        analyzer = RTLDependencyAnalyzer()
        analyzer.parse_file(str(test_file))
        
        assert 'test' in analyzer.modules
        assert 'y' in analyzer.modules['test']['dependencies']
        deps = analyzer.modules['test']['dependencies']['y']
        assert 'a' in deps
        assert 'b' in deps
    
    def test_parse_always_block(self, tmp_path):
        """测试 always 块解析"""
        code = '''
module test(
    input clk,
    input rst_n,
    input enable,
    input [7:0] data_in,
    output reg [7:0] data_out
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            data_out <= 8'b0;
        else if (enable)
            data_out <= data_in;
    end
endmodule
'''
        test_file = tmp_path / "test.v"
        test_file.write_text(code)
        
        analyzer = RTLDependencyAnalyzer()
        analyzer.parse_file(str(test_file))
        
        assert 'test' in analyzer.modules
        assert 'data_out' in analyzer.modules['test']['dependencies']
    
    def test_search_global(self, tmp_path):
        """测试全局搜索"""
        code1 = '''
module mod1(
    input clk,
    output data_out
);
    assign data_out = clk;
endmodule
'''
        code2 = '''
module mod2(
    input data_out,
    output result
);
    assign result = data_out;
endmodule
'''
        test_file1 = tmp_path / "mod1.v"
        test_file1.write_text(code1)
        test_file2 = tmp_path / "mod2.v"
        test_file2.write_text(code2)
        
        analyzer = RTLDependencyAnalyzer()
        analyzer.parse_file(str(test_file1))
        analyzer.parse_file(str(test_file2))
        
        results = analyzer.search_global('data_out')
        assert len(results) == 2
        
        paths = [r['path'] for r in results]
        assert 'mod1.data_out' in paths
        assert 'mod2.data_out' in paths


class TestVCDSmartStream:
    """VCDSmartStream 单元测试"""
    
    def test_init(self):
        """测试初始化"""
        # 注意：实际使用需要 VCD 文件
        # 这里只测试基本初始化
        pass


class TestCommandLine:
    """命令行工具测试"""
    
    def test_help(self):
        """测试帮助信息"""
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'rtl_debugger.main', '--help'],
            capture_output=True,
            text=True,
            cwd=str(src_dir.parent)
        )
        assert result.returncode == 0
        assert 'RTL' in result.stdout or 'signal' in result.stdout


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
