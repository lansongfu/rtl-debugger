#!/usr/bin/env python3
"""
交互式调试分析器
核心特性：
1. 用户确认机制 - 询问是否需要 CDC/时序分析
2. 可选分析模式 - 默认只做基础分析
3. 自动时钟域提取 - 从 RTL 分析
4. 按需深度分析
"""

import sys
import os
import subprocess
import re
from typing import Dict, List, Optional, Tuple

# 添加路径
tools_dir = os.path.dirname(os.path.abspath(__file__))
venv_lib = os.path.join(os.path.dirname(tools_dir), 'venv/lib/python3.12/site-packages')
sys.path.insert(0, venv_lib)

from vcdvcd import vcdvcd
from advanced_reasoner import AdvancedReasoner


class InteractiveDebugAnalyzer:
    """交互式调试分析器"""
    
    def __init__(self, rtl_filelist=None, vcd_file=None):
        self.rtl_filelist = rtl_filelist
        self.vcd_file = vcd_file
        self.vcd_data = None
        self.vcd_signals = {}
        self.rtl_content = ""
        self.clock_domains = {}  # 信号→时钟映射
        self.reasoner = AdvancedReasoner()
        
        # 分析选项
        self.enable_cdc = False
        self.enable_timing = False
        self.enable_race = False
    
    def load_vcd(self):
        """加载 VCD 文件"""
        if not self.vcd_file:
            return False
        
        print(f"📂 加载 VCD: {self.vcd_file}")
        try:
            self.vcd_data = vcdvcd.VCDVCD(self.vcd_file)
            
            for signal_id, signal_info in self.vcd_data.data.items():
                refs = signal_info.references if hasattr(signal_info, 'references') else signal_info['references']
                size = signal_info.size if hasattr(signal_info, 'size') else signal_info['size']
                tv = signal_info.tv if hasattr(signal_info, 'tv') else signal_info['tv']
                
                for ref in refs:
                    self.vcd_signals[ref] = {
                        'width': int(size) if size else 1,
                        'tv': tv if tv else []
                    }
            
            print(f"✅ VCD 加载完成：{len(self.vcd_signals)} 个信号\n")
            return True
        except Exception as e:
            print(f"❌ VCD 加载失败：{e}\n")
            return False
    
    def load_rtl(self):
        """加载 RTL 文件并提取时钟域"""
        if not self.rtl_filelist:
            return False
        
        print(f"📂 加载 RTL: {self.rtl_filelist}")
        
        try:
            # 读取 filelist
            with open(self.rtl_filelist, 'r') as f:
                rtl_files = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            # 读取所有 RTL 文件
            self.rtl_content = ""
            for rtl_file in rtl_files:
                if os.path.exists(rtl_file) and (rtl_file.endswith('.v') or rtl_file.endswith('.sv')):
                    with open(rtl_file, 'r') as f:
                        self.rtl_content += f.read() + "\n"
            
            print(f"✅ RTL 加载完成：{len(rtl_files)} 个文件")
            
            # 自动提取时钟域
            self._extract_clock_domains()
            return True
        except Exception as e:
            print(f"❌ RTL 加载失败：{e}\n")
            return False
    
    def _extract_clock_domains(self):
        """从 RTL 自动提取时钟域信息"""
        print("🔍 自动提取时钟域...")
        
        # 查找 always @(posedge clk_xxx)
        clock_pattern = r'always\s*@\s*\((?:posedge|negedge)\s+(\w+)'
        clocks = set(re.findall(clock_pattern, self.rtl_content))
        
        print(f"   发现时钟：{', '.join(clocks)}")
        
        # 简化的时钟域提取（实际应该更复杂）
        # 这里只是示例，实际需要根据 always 块中的信号分配
        for clock in clocks:
            self.clock_domains[f'*{clock}*'] = clock
        
        print(f"   时钟域映射：{len(self.clock_domains)} 个\n")
    
    def ask_analysis_options(self):
        """询问用户是否需要高级分析"""
        print("=" * 80)
        print("🔧 分析选项配置")
        print("=" * 80)
        print()
        print("可选的高级分析功能：")
        print("  1. CDC 跨时钟域分析 - 检测跨时钟域未同步问题")
        print("  2. 时序分析 - 检测建立/保持时间违例")
        print("  3. 竞争冒险分析 - 检测多信号同时变化风险")
        print()
        print("⚠️  注意：高级分析会增加分析时间")
        print()
        
        # 默认不启用，需要用户确认
        self.enable_cdc = False
        self.enable_timing = False
        self.enable_race = False
        
        # 如果有 RTL 且检测到多个时钟，建议开启 CDC
        if len(self.clock_domains) > 1:
            print(f"💡 建议：检测到 {len(self.clock_domains)} 个时钟域，推荐开启 CDC 分析")
            print()
        
        print("分析模式：")
        print(f"  ✅ 基础分析 - 始终启用（Bug 模式检测、依赖追踪）")
        print(f"  {'✅' if self.enable_cdc else '❌'} CDC 分析 - 未启用")
        print(f"  {'✅' if self.enable_timing else '❌'} 时序分析 - 未启用")
        print(f"  {'✅' if self.enable_race else '❌'} 竞争分析 - 未启用")
        print()
        print("如需启用高级分析，请使用命令行参数：")
        print("  --cdc      启用 CDC 分析")
        print("  --timing   启用时序分析")
        print("  --race     启用竞争分析")
        print("  --all      启用所有分析")
        print()
    
    def get_vcd_behavior(self, signal_name):
        """获取 VCD 波形行为"""
        matched_name = None
        for name in self.vcd_signals:
            if signal_name in name or name.endswith(f'.{signal_name}'):
                matched_name = name
                break
        
        if not matched_name:
            return None, None, None
        
        info = self.vcd_signals[matched_name]
        tv = info['tv']
        width = info['width']
        
        if len(tv) == 0:
            behavior = "始终无变化 (静默信号)"
            behavior_type = "silent"
        elif len(set(v for t, v in tv)) == 1:
            value = tv[0][1]
            behavior = f"始终为 {value} (恒定信号)"
            behavior_type = "constant"
            behavior_value = value
        elif width == 1:
            zeros = sum(1 for t, v in tv if v == '0')
            ones = sum(1 for t, v in tv if v == '1')
            behavior = f"变化 {len(tv)} 次 (0:{zeros}次，1:{ones}次)"
            behavior_type = "toggling"
            behavior_value = None
        else:
            unique = len(set(v for t, v in tv))
            behavior = f"变化 {len(tv)} 次 ({unique} 个不同值)"
            behavior_type = "toggling"
            behavior_value = None
        
        return matched_name, {
            'behavior': behavior,
            'type': behavior_type,
            'value': behavior_value,
            'changes': len(tv),
            'tv': tv
        }, behavior_type
    
    def query_rtl(self, signal_name):
        """查询 RTL 依赖"""
        cmd = [
            sys.executable,
            os.path.join(tools_dir, 'rtl_query.py'),
            '--filelist', self.rtl_filelist,
            '--signal', signal_name
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        deps = []
        if result.stdout:
            for line in result.stdout.split('\n'):
                if '←' in line and '信号查询' not in line:
                    parts = line.split('←')
                    if len(parts) >= 2:
                        dep_list = [d.strip() for d in parts[1].split(',')]
                        deps.extend(dep_list)
        
        return deps
    
    def analyze(self, target_signal, expected_behavior=None):
        """执行分析"""
        print("=" * 80)
        print(f"🔍 调试分析：{target_signal}")
        print("=" * 80)
        
        if expected_behavior:
            print(f"📋 预期行为：{expected_behavior}")
        print()
        
        # Step 1: 询问分析选项
        self.ask_analysis_options()
        
        # Step 2: 基础分析（始终执行）
        print("=" * 80)
        print("📊 Step 1: 基础分析")
        print("=" * 80)
        print()
        
        deps = self.query_rtl(target_signal)
        vcd_name, vcd_info, behavior_type = self.get_vcd_behavior(target_signal)
        
        print(f"目标信号：{target_signal}")
        if vcd_info:
            print(f"VCD 名称：{vcd_name}")
            print(f"行为：{vcd_info['behavior']}")
        if deps:
            print(f"RTL 依赖：{', '.join(deps)}")
        print()
        
        # Step 3: 高级分析（可选）
        if self.enable_cdc or self.enable_timing or self.enable_race:
            print("=" * 80)
            print("📈 Step 2: 高级分析")
            print("=" * 80)
            print()
        
        # 准备诊断数据
        dep_behaviors = {}
        tv_data = vcd_info['tv'] if vcd_info else []
        
        for dep in deps:
            _, dep_info, _ = self.get_vcd_behavior(dep)
            dep_behaviors[dep] = dep_info['behavior'] if dep_info else "未知"
        
        # 执行诊断
        diagnoses = self.reasoner.diagnose(
            signal_name=target_signal,
            behavior=vcd_info['behavior'] if vcd_info else "未知",
            deps=deps,
            dep_behaviors=dep_behaviors,
            expected=expected_behavior,
            tv_data=tv_data,
            clock_info=self.clock_domains if self.enable_cdc else None
        )
        
        # 过滤诊断（只保留启用的分析类型）
        if not self.enable_cdc:
            diagnoses = [d for d in diagnoses if d.bug_pattern.value != 'cdc_issue']
        if not self.enable_timing:
            diagnoses = [d for d in diagnoses if d.bug_pattern.value != 'timing_violation']
        if not self.enable_race:
            diagnoses = [d for d in diagnoses if d.bug_pattern.value != 'race_condition']
        
        # Step 4: 生成报告
        if diagnoses:
            print("=" * 80)
            print("🏥 Step 3: 智能诊断报告")
            print("=" * 80)
            print()
            
            report = self.reasoner.generate_priority_report(
                target_signal,
                diagnoses,
                [(target_signal, vcd_info['behavior'] if vcd_info else "未知")]
            )
            print(report)
        else:
            print("=" * 80)
            print("🎯 分析结论")
            print("=" * 80)
            print()
            print("✅ 未发现问题")
            print()
        
        # Step 5: 总结
        print("=" * 80)
        print("📋 分析总结")
        print("=" * 80)
        print()
        print(f"分析模式：{'高级' if (self.enable_cdc or self.enable_timing or self.enable_race) else '基础'}")
        print(f"启用功能：")
        print(f"  ✅ 基础分析")
        if self.enable_cdc:
            print(f"  ✅ CDC 分析")
        if self.enable_timing:
            print(f"  ✅ 时序分析")
        if self.enable_race:
            print(f"  ✅ 竞争分析")
        print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='交互式调试分析器')
    parser.add_argument('target', help='目标信号名')
    parser.add_argument('--filelist', help='RTL filelist 文件')
    parser.add_argument('--vcd', help='VCD 波形文件')
    parser.add_argument('--expected', help='预期行为描述')
    
    # 分析选项
    parser.add_argument('--cdc', action='store_true', help='启用 CDC 分析')
    parser.add_argument('--timing', action='store_true', help='启用时序分析')
    parser.add_argument('--race', action='store_true', help='启用竞争分析')
    parser.add_argument('--all', action='store_true', help='启用所有分析')
    
    args = parser.parse_args()
    
    # 创建分析器
    analyzer = InteractiveDebugAnalyzer(
        rtl_filelist=args.filelist,
        vcd_file=args.vcd
    )
    
    # 加载数据
    if args.vcd:
        analyzer.load_vcd()
    if args.filelist:
        analyzer.load_rtl()
    
    # 设置分析选项
    if args.all:
        analyzer.enable_cdc = True
        analyzer.enable_timing = True
        analyzer.enable_race = True
    else:
        analyzer.enable_cdc = args.cdc
        analyzer.enable_timing = args.timing
        analyzer.enable_race = args.race
    
    # 执行分析
    analyzer.analyze(args.target, expected_behavior=args.expected)


if __name__ == '__main__':
    main()
