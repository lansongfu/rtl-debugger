#!/usr/bin/env python3
"""
增强版调试分析器
核心能力：
1. 长路径追踪（支持深层依赖链）
2. 智能分析（根据预期逐个分析依赖）
3. 源头定位（找到第一个异常节点）
"""

import sys
# Windows 编码适配：确保 UTF-8 输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import os
import subprocess
from typing import Dict, List, Optional, Set, Tuple

# 添加路径
tools_dir = os.path.dirname(os.path.abspath(__file__))
venv_lib = os.path.join(os.path.dirname(tools_dir), 'venv/lib/python3.12/site-packages')
sys.path.insert(0, venv_lib)

from vcdvcd import vcdvcd
from advanced_reasoner import AdvancedReasoner


class EnhancedDebugAnalyzer:
    """增强版调试分析器"""
    
    def __init__(self, rtl_filelist=None, vcd_file=None):
        self.rtl_filelist = rtl_filelist
        self.vcd_file = vcd_file
        self.vcd_data = None
        self.vcd_signals = {}
        self.rtl_cache = {}  # 缓存 RTL 查询结果
        self.analysis_path = []  # 分析路径记录
        self.reasoner = AdvancedReasoner()  # 高级推理引擎
        
    def load_vcd(self):
        """加载 VCD 文件"""
        if not self.vcd_file:
            return
        
        print(f"📂 加载 VCD: {self.vcd_file}")
        self.vcd_data = vcdvcd.VCDVCD(self.vcd_file)
        
        # 提取信号信息
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
    
    def query_rtl(self, signal_name):
        """查询 RTL 依赖（带缓存）"""
        # 检查缓存
        if signal_name in self.rtl_cache:
            return self.rtl_cache[signal_name]
        
        if not self.rtl_filelist and not os.path.exists(signal_name):
            return None
        
        cmd = [
            sys.executable,
            os.path.join(tools_dir, 'rtl_query.py')
        ]
        
        if self.rtl_filelist:
            cmd.extend(['--filelist', self.rtl_filelist])
        else:
            cmd.append(signal_name)
        
        cmd.extend(['--signal', signal_name])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 解析依赖
        deps = []
        if result.stdout:
            for line in result.stdout.split('\n'):
                if '←' in line and '信号查询' not in line:
                    parts = line.split('←')
                    if len(parts) >= 2:
                        dep_list = [d.strip() for d in parts[1].split(',')]
                        deps.extend(dep_list)
        
        # 缓存结果
        self.rtl_cache[signal_name] = deps
        return deps
    
    def get_vcd_behavior(self, signal_name):
        """获取 VCD 波形行为（返回详细分析）"""
        # 模糊匹配
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
        
        # 详细分析
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
    
    def analyze_dependency_chain(self, target_signal, expected_behavior, depth=0, visited=None, path=None):
        """
        递归分析依赖链，找到第一个异常节点
        
        返回：
        - anomaly_path: 异常路径列表
        - root_cause: 根因信号
        - analysis_log: 分析日志
        """
        if visited is None:
            visited = set()
        if path is None:
            path = []
        
        # 防止无限递归
        if target_signal in visited or depth > 20:
            return [], None, []
        
        visited.add(target_signal)
        current_path = path + [target_signal]
        
        analysis_log = []
        indent = "  " * depth
        
        # Step 1: 查询当前信号
        deps = self.query_rtl(target_signal)
        vcd_name, vcd_info, behavior_type = self.get_vcd_behavior(target_signal)
        
        if not vcd_info:
            analysis_log.append(f"{indent}❓ {target_signal}: VCD 中未找到")
            return [], None, analysis_log
        
        analysis_log.append(f"{indent}🔍 分析：{target_signal}")
        analysis_log.append(f"{indent}   VCD: {vcd_name}")
        analysis_log.append(f"{indent}   行为：{vcd_info['behavior']}")
        
        if deps:
            analysis_log.append(f"{indent}   依赖：{', '.join(deps)}")
        
        # Step 2: 判断当前信号是否异常
        is_anomaly = False
        anomaly_reason = None
        
        if expected_behavior:
            # 预期有变化，但实际恒定
            if '应该有变化' in expected_behavior or '应该跳变' in expected_behavior:
                if behavior_type == 'constant' or behavior_type == 'silent':
                    is_anomaly = True
                    anomaly_reason = f"预期应该有变化，但实际{vcd_info['behavior']}"
            # 预期为特定值
            elif expected_behavior in ['0', '1']:
                if behavior_type == 'constant' and vcd_info['value'] != expected_behavior:
                    is_anomaly = True
                    anomaly_reason = f"预期为{expected_behavior}，但实际为{vcd_info['value']}"
        
        analysis_log.append(f"{indent}   状态：{'❌ 异常' if is_anomaly else '✅ 正常'}")
        
        # Step 3: 如果是异常且没有依赖，这就是根因
        if is_anomaly and not deps:
            analysis_log.append(f"{indent}🎯 找到根因：{target_signal} (无依赖的叶信号)")
            return current_path, target_signal, analysis_log
        
        # Step 4: 如果有依赖，逐个分析
        if deps:
            analysis_log.append(f"{indent}🔗 开始分析依赖...")
            
            found_upstream_anomaly = False
            for dep in deps:
                analysis_log.append(f"{indent}   ↓ 检查依赖：{dep}")
                
                # 递归分析
                anomaly_path, root_cause, sub_log = self.analyze_dependency_chain(
                    dep, expected_behavior, depth + 1, visited, current_path
                )
                
                analysis_log.extend(sub_log)
                
                if anomaly_path:
                    found_upstream_anomaly = True
                    analysis_log.append(f"{indent}   ✅ 发现上游异常：{root_cause}")
                    return anomaly_path, root_cause, analysis_log
            
            # 如果所有依赖都正常，但当前信号异常 → 当前信号是问题点
            if is_anomaly and not found_upstream_anomaly:
                analysis_log.append(f"{indent}🎯 找到根因：{target_signal} (依赖正常，自身异常)")
                analysis_log.append(f"{indent}   可能原因：驱动逻辑问题或使能条件不满足")
                return current_path, target_signal, analysis_log
        
        # Step 5: 如果当前信号正常，继续追踪
        if not is_anomaly and deps:
            for dep in deps:
                anomaly_path, root_cause, sub_log = self.analyze_dependency_chain(
                    dep, expected_behavior, depth + 1, visited, current_path
                )
                analysis_log.extend(sub_log)
                if anomaly_path:
                    return anomaly_path, root_cause, analysis_log
        
        return [], None, analysis_log
    
    def analyze(self, target_signal, expected_behavior=None, question=None):
        """执行完整分析"""
        print("=" * 80)
        print(f"🔍 增强版调试分析：{target_signal}")
        print("=" * 80)
        
        if question:
            print(f"\n❓ 问题：{question}")
        
        if expected_behavior:
            print(f"📋 预期行为：{expected_behavior}")
        
        # 执行深度分析
        print("\n" + "=" * 80)
        print("🧠 深度依赖链分析")
        print("=" * 80)
        print()
        
        anomaly_path, root_cause, analysis_log = self.analyze_dependency_chain(
            target_signal, expected_behavior
        )
        
        # 打印分析日志
        for log in analysis_log:
            print(log)
        
        # 打印分析路径
        print("\n" + "=" * 80)
        print("📊 分析路径总结")
        print("=" * 80)
        print()
        
        if anomaly_path:
            print("追踪路径:")
            for i, sig in enumerate(anomaly_path):
                vcd_name, vcd_info, _ = self.get_vcd_behavior(sig)
                behavior = vcd_info['behavior'] if vcd_info else "未知"
                marker = "🎯 根因" if sig == root_cause else f"   步骤{i+1}"
                print(f"  {marker}: {sig}")
                print(f"            行为：{behavior}")
        else:
            print("✅ 未发现异常路径")
        
        # 根因结论
        print("\n" + "=" * 80)
        print("🎯 根因结论")
        print("=" * 80)
        print()
        
        if root_cause:
            print(f"🔴 根因信号：{root_cause}")
            
            vcd_name, vcd_info, _ = self.get_vcd_behavior(root_cause)
            if vcd_info:
                print(f"   VCD 名称：{vcd_name}")
                print(f"   实际行为：{vcd_info['behavior']}")
            
            print(f"\n💡 建议:")
            print(f"   1. 检查 {root_cause} 的驱动逻辑")
            print(f"   2. 查看 {root_cause} 的控制信号和使能条件")
            print(f"   3. 检查时钟和复位信号")
            print(f"   4. 对比 RTL 预期和 VCD 实际行为")
            
            # 智能诊断报告
            print("\n" + "=" * 80)
            print("🏥 智能诊断报告")
            print("=" * 80)
            print()
            
            # 准备诊断数据
            dep_behaviors = {}
            for dep in self.query_rtl(root_cause) or []:
                _, dep_info, _ = self.get_vcd_behavior(dep)
                dep_behaviors[dep] = dep_info['behavior'] if dep_info else "未知"
            
            # 执行诊断（增强版 - 多个诊断）
            diagnoses = self.reasoner.diagnose(
                signal_name=root_cause,
                behavior=vcd_info['behavior'] if vcd_info else "未知",
                deps=self.query_rtl(root_cause) or [],
                dep_behaviors=dep_behaviors,
                expected=expected_behavior
            )
            
            if diagnoses:
                # 生成优先级报告
                report = self.reasoner.generate_priority_report(
                    root_cause,
                    diagnoses,
                    [(sig, self.get_vcd_behavior(sig)[1]['behavior'] if self.get_vcd_behavior(sig)[1] else "未知") 
                     for sig in anomaly_path]
                )
                print(report)
        else:
            print("✅ 信号行为符合预期，未发现根因")
        
        print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='增强版调试分析器')
    parser.add_argument('target', help='目标信号名')
    parser.add_argument('--filelist', help='RTL filelist 文件')
    parser.add_argument('--vcd', help='VCD 波形文件')
    parser.add_argument('--expected', help='预期行为描述')
    parser.add_argument('--question', help='调试问题描述')
    
    args = parser.parse_args()
    
    # 创建分析器
    analyzer = EnhancedDebugAnalyzer(
        rtl_filelist=args.filelist,
        vcd_file=args.vcd
    )
    
    # 加载 VCD
    if args.vcd:
        analyzer.load_vcd()
    
    # 执行分析
    analyzer.analyze(args.target, expected_behavior=args.expected)


if __name__ == '__main__':
    main()
