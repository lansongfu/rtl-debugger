#!/usr/bin/env python3
"""
真正的交互式调试器
核心：AI 根据实际工具返回结果，一步步迭代追踪

流程：
1. 用户提问
2. AI 查 RTL 依赖
3. AI 查 VCD 行为
4. AI 判断是否异常
5. 如果异常，继续追依赖
6. 如果正常，回溯找其他分支
7. 直到找到根因
"""

import subprocess
import sys
import os
import re

# 添加路径
skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(skill_dir, 'venv/lib/python3.12/site-packages'))


class InteractiveDebugger:
    """真正的交互式调试器（v5 智能流式查询）"""
    
    def __init__(self, filelist, vcd_file):
        self.filelist = filelist
        self.vcd_file = vcd_file
        self.visited = set()  # 已追踪的信号
        self.trace_path = []  # 追踪路径
        self.max_depth = 20  # 最大深度
        self.vcd_loaded = False  # VCD 是否已加载
        self.anomaly_window = None  # 异常时间窗口（用户未指定时自动定位）
        
    def locate_anomaly_window(self, signal_name):
        """
        定位异常时间窗口（用户未指定时间时使用）
        
        策略：
        1. 全时间扫描信号行为
        2. 找到第一个异常点
        3. 返回窗口（异常点 ±100ns）
        """
        cmd = [
            sys.executable,
            os.path.join(skill_dir, 'tools', 'vcd_smart.py'),
            self.vcd_file,
            '--signal', signal_name,
            '--analyze'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 解析首次变化时间
        for line in result.stdout.split('\n'):
            if '首次变化：t=' in line:
                match = re.search(r'首次变化：t=(\d+) ps', line)
                if match:
                    first_change = int(match.group(1))
                    tolerance = 100000  # 100ns
                    self.anomaly_window = (
                        max(0, first_change - tolerance),
                        first_change + tolerance
                    )
                    return self.anomaly_window
        
        return None
        
    def query_rtl(self, signal_name):
        """查询 RTL 依赖"""
        cmd = [
            sys.executable,
            os.path.join(skill_dir, 'tools', 'rtl_query.py'),
            '--filelist', self.filelist,
            '--signal', signal_name
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 解析依赖
        deps = []
        for line in result.stdout.split('\n'):
            if '←' in line and '信号查询' not in line:
                parts = line.split('←')
                if len(parts) >= 2:
                    dep_list = [d.strip() for d in parts[1].split(',')]
                    deps.extend(dep_list)
        
        return deps
    
    def query_vcd(self, signal_name, start_time=None, end_time=None):
        """
        查询 VCD 行为（使用智能流式查询 v5）
        
        Args:
            signal_name: 信号名
            start_time: 开始时间 (ps)，None 表示从头开始
            end_time: 结束时间 (ps)，None 表示查到末尾
        """
        cmd = [
            sys.executable,
            os.path.join(skill_dir, 'tools', 'vcd_smart.py'),
            self.vcd_file,
            '--signal', signal_name,
        ]
        
        # 如果指定时间窗口，使用窗口查询
        if start_time is not None and end_time is not None:
            cmd.extend(['--start-time', str(start_time), '--end-time', str(end_time)])
        else:
            # 否则做行为分析
            cmd.append('--analyze')
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 解析行为（只保留关键信息）
        output = result.stdout.strip()
        
        # 提取行为描述
        behavior_line = ""
        for line in output.split('\n'):
            if '始终为' in line or '始终无变化' in line or '变化' in line or '行为：' in line:
                behavior_line = line.strip()
                break
        
        if not behavior_line:
            behavior_line = output.split('\n')[-1] if output.split('\n') else "unknown"
        
        # 解析具体行为
        if '始终为' in behavior_line:
            match = re.search(r'始终为 (\d+)', behavior_line)
            value = match.group(1) if match else 'unknown'
            return {'behavior': 'constant', 'value': value, 'raw': behavior_line}
        elif '始终无变化' in behavior_line or 'silent' in behavior_line:
            return {'behavior': 'silent', 'value': None, 'raw': behavior_line}
        elif '变化' in behavior_line or 'toggling' in behavior_line:
            return {'behavior': 'toggling', 'value': None, 'raw': behavior_line}
        else:
            return {'behavior': 'unknown', 'value': None, 'raw': behavior_line}
    
    def is_anomaly(self, signal_name, vcd_result, expected=None):
        """判断是否异常"""
        behavior = vcd_result['behavior']
        
        # 恒定信号可能是异常
        if behavior == 'constant':
            # 如果预期有变化，就是异常
            if expected and '应该有变化' in expected:
                return True, f"信号始终为{vcd_result['value']}，但预期应该有变化"
        
        # 静默信号通常是异常
        if behavior == 'silent':
            return True, "信号完全无变化（静默）"
        
        return False, None
    
    def debug(self, target_signal, expected=None, time_window=None, depth=0):
        """
        交互式调试核心方法（v5 智能流式查询）
        
        策略：
        1. 用户指定时间窗口 → 直接使用
        2. 用户未指定 → 先定位异常窗口
        3. 查 RTL 依赖
        4. 查 VCD 行为（时间窗口内）
        5. 判断是否异常
        6. 如果异常，继续追依赖（同一窗口或提前窗口）
        7. 直到根因
        """
        
        # 防止无限递归
        if target_signal in self.visited or depth > self.max_depth:
            return {'status': 'max_depth', 'signal': target_signal}
        
        self.visited.add(target_signal)
        indent = "  " * depth
        
        print(f"\n{indent}🔍 步骤 {len(self.trace_path) + 1}: 分析 {target_signal}")
        self.trace_path.append(target_signal)
        
        # 如果用户未指定时间窗口，第一次调用时定位
        if time_window is None and self.anomaly_window is None and expected:
            print(f"{indent}   🕒 用户未指定时间窗口，正在定位异常点...")
            self.locate_anomaly_window(target_signal)
            if self.anomaly_window:
                time_window = self.anomaly_window
                print(f"{indent}   ✅ 定位异常窗口：t={time_window[0]}-{time_window[1]} ps")
            else:
                print(f"{indent}   ⚠️  未找到异常窗口，使用全时间窗口")
        
        # Step 1: 查 RTL 依赖
        print(f"{indent}   📊 查询 RTL 依赖...")
        deps = self.query_rtl(target_signal)
        if deps:
            print(f"{indent}   📝 依赖：{', '.join(deps)}")
        else:
            print(f"{indent}   📝 无依赖（叶信号）")
        
        # Step 2: 查 VCD 行为（时间窗口内）
        print(f"{indent}   📈 查询 VCD 行为...")
        if time_window:
            print(f"{indent}   🕒 时间窗口：t={time_window[0]}-{time_window[1]} ps")
            vcd_result = self.query_vcd(target_signal, time_window[0], time_window[1])
        else:
            vcd_result = self.query_vcd(target_signal)
        print(f"{indent}   📝 行为：{vcd_result['raw']}")
        
        # Step 3: 判断是否异常
        is_anom, reason = self.is_anomaly(target_signal, vcd_result, expected)
        
        if is_anom:
            print(f"{indent}   ⚠️  发现异常：{reason}")
            
            # Step 4: 如果有依赖，继续追
            if deps:
                print(f"{indent}   🔗 继续追踪依赖...")
                
                # 计算下一个时间窗口（提前 100ns）
                next_window = None
                if time_window:
                    advance = 100000  # 100ns
                    next_window = (max(0, time_window[0] - advance), time_window[1])
                
                # 对每个依赖递归调试
                for dep in deps:
                    result = self.debug(dep, expected, next_window, depth + 1)
                    
                    # 如果找到根因，返回
                    if result['status'] == 'root_cause':
                        return result
                
                # 如果所有依赖都追完了，当前信号就是根因
                return {
                    'status': 'root_cause',
                    'signal': target_signal,
                    'behavior': vcd_result['raw'],
                    'reason': reason,
                    'deps': deps
                }
            else:
                # 无依赖，就是根因
                return {
                    'status': 'root_cause',
                    'signal': target_signal,
                    'behavior': vcd_result['raw'],
                    'reason': reason,
                    'deps': []
                }
        else:
            print(f"{indent}   ✅ 行为正常")
            
            # 如果正常但有依赖，也可以继续看看（可选）
            # 这里选择不再继续，因为当前信号正常
        
        return {'status': 'normal', 'signal': target_signal}
    
    def run(self, target_signal, expected=None):
        """运行调试"""
        print("=" * 80)
        print(f"🔍 交互式调试：{target_signal}")
        print("=" * 80)
        
        if expected:
            print(f"📋 预期行为：{expected}")
        
        print("\n🚀 开始追踪...\n")
        
        # 执行调试
        result = self.debug(target_signal, expected)
        
        # 输出结果
        print("\n" + "=" * 80)
        print("🎯 调试结果")
        print("=" * 80)
        
        if result['status'] == 'root_cause':
            print(f"\n🔴 找到根因：{result['signal']}")
            print(f"   行为：{result['behavior']}")
            print(f"   原因：{result['reason']}")
            
            if result['deps']:
                print(f"   依赖：{', '.join(result['deps'])}")
            
            print(f"\n📋 追踪路径：")
            for i, sig in enumerate(self.trace_path, 1):
                print(f"   {i}. {sig}")
            
            print(f"\n💡 建议：")
            print(f"   1. 检查 {result['signal']} 的驱动逻辑")
            print(f"   2. 查看相关控制信号")
            print(f"   3. 对比 RTL 预期和 VCD 实际")
            
        elif result['status'] == 'max_depth':
            print(f"\n⚠️  达到最大追踪深度 ({self.max_depth})")
            print(f"   最后信号：{result['signal']}")
            
        else:
            print(f"\n✅ 未发现明显异常")
        
        print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='真正的交互式调试器')
    parser.add_argument('target', help='目标信号')
    parser.add_argument('--filelist', required=True, help='RTL filelist')
    parser.add_argument('--vcd', required=True, help='VCD 文件')
    parser.add_argument('--expected', help='预期行为')
    
    args = parser.parse_args()
    
    debugger = InteractiveDebugger(args.filelist, args.vcd)
    debugger.run(args.target, args.expected)


if __name__ == '__main__':
    main()
