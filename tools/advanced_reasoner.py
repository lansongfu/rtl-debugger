#!/usr/bin/env python3
"""
增强版问题追踪定位引擎
核心能力：
1. 更多 Bug 模式（时序、CDC、竞争冒险）
2. 时序分析（建立/保持时间）
3. 跨模块追踪
4. 根因评分排序
5. 自动修复建议生成
"""

from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import re


class BugPattern(Enum):
    """Bug 模式枚举"""
    # 原有模式
    MISSING_RESET = "missing_reset"
    WRONG_ENABLE = "wrong_enable"
    STUCK_STATE = "stuck_state"
    DEAD_SIGNAL = "dead_signal"
    CONSTANT_DRIVER = "constant_driver"
    MISSING_CLOCK = "missing_clock"
    LOGIC_ERROR = "logic_error"
    
    # 新增模式
    TIMING_VIOLATION = "timing_violation"  # 时序违例
    CDC_ISSUE = "cdc_issue"  # 跨时钟域问题
    RACE_CONDITION = "race_condition"  # 竞争冒险
    INCOMPLETE_ASSIGN = "incomplete_assign"  # 不完整赋值
    SENSITIVITY_LIST = "sensitivity_list"  # 敏感列表不完整
    BLOCKING_NONBLOCKING = "blocking_nonblocking"  # 阻塞/非阻塞混用
    GENERATE_ISSUE = "generate_issue"  # generate 问题
    PARAMETER_MISMATCH = "parameter_mismatch"  # 参数不匹配


@dataclass
class Diagnosis:
    """诊断结果"""
    bug_pattern: BugPattern
    confidence: float
    severity: str  # critical/high/medium/low
    description: str
    root_cause: str
    fix_suggestions: List[str]
    code_example: Optional[str] = None
    related_signals: List[str] = field(default_factory=list)
    auto_fix_patch: Optional[str] = None


class AdvancedReasoner:
    """高级推理引擎"""
    
    def __init__(self):
        self.knowledge_base = self._build_knowledge_base()
        self.cdc_clocks = {}  # 时钟域信息
    
    def _build_knowledge_base(self) -> Dict[BugPattern, Dict]:
        """构建知识库"""
        return {
            # === 原有模式 ===
            BugPattern.DEAD_SIGNAL: {
                'name': '死信号',
                'severity': 'high',
                'description': '信号没有有效驱动或连接',
                'fix': [
                    '检查信号是否正确实例化',
                    '验证模块端口连接',
                    '确认信号有驱动源',
                    '查看是否有悬空 wire'
                ],
                'code_example': '''// ❌ 错误：wire 无驱动
wire data_out;

// ✅ 正确
wire data_out;
assign data_out = data_reg;'''
            },
            
            # === 新增模式 ===
            BugPattern.TIMING_VIOLATION: {
                'name': '时序违例',
                'severity': 'critical',
                'description': '信号变化时间不满足建立/保持时间要求',
                'symptoms': [
                    '信号在时钟沿附近变化',
                    '建立时间不足',
                    '保持时间不足',
                    '时序收敛失败'
                ],
                'fix': [
                    '检查输入信号是否满足建立时间',
                    '验证输出信号保持时间',
                    '添加输入同步器',
                    '优化组合逻辑路径',
                    '查看时序报告确认违例'
                ],
                'code_example': '''// ❌ 错误：组合逻辑延迟过长
assign out = a && b && c && d && e && f;  // 多级逻辑

// ✅ 正确：流水线优化
always @(posedge clk) begin
    stage1 <= a && b;
    stage2 <= c && d;
    stage3 <= e && f;
    out <= stage1 && stage2 && stage3;
end'''
            },
            
            BugPattern.CDC_ISSUE: {
                'name': '跨时钟域问题',
                'severity': 'critical',
                'description': '信号在不同时钟域之间传输未做同步处理',
                'symptoms': [
                    '信号在两个时钟域间传递',
                    '缺少同步器',
                    '亚稳态风险',
                    '数据丢失或错误'
                ],
                'fix': [
                    '添加两级同步器（打两拍）',
                    '使用握手协议',
                    '使用 FIFO 缓冲',
                    '对于多比特信号使用格雷码',
                    '确认时钟频率关系'
                ],
                'code_example': '''// ❌ 错误：直接跨时钟域
always @(posedge clk_b)
    sync_reg <= src_clk_a_signal;  // 亚稳态风险!

// ✅ 正确：两级同步器
reg sync1, sync2;
always @(posedge clk_b) begin
    sync1 <= src_clk_a_signal;
    sync2 <= sync1;
end
assign synced_signal = sync2;'''
            },
            
            BugPattern.RACE_CONDITION: {
                'name': '竞争冒险',
                'severity': 'high',
                'description': '多个信号同时变化导致不确定行为',
                'symptoms': [
                    '多个信号同时跳变',
                    '输出毛刺',
                    '仿真和综合结果不一致',
                    '时序相关的不确定行为'
                ],
                'fix': [
                    '使用同步设计',
                    '避免组合逻辑反馈',
                    '添加输出寄存器',
                    '检查敏感列表完整性',
                    '使用静态时序分析'
                ],
                'code_example': '''// ❌ 错误：组合逻辑竞争
assign out = enable ? data : 0;
assign enable = ctrl && ready;  // 可能产生毛刺

// ✅ 正确：同步输出
always @(posedge clk)
    if (ctrl && ready)
        out <= data;
    else
        out <= 0;'''
            },
            
            BugPattern.INCOMPLETE_ASSIGN: {
                'name': '不完整赋值',
                'severity': 'high',
                'description': '时序逻辑中未对所有分支赋值，产生 latch',
                'symptoms': [
                    '组合逻辑产生 latch',
                    'if 缺少 else',
                    'case 缺少 default',
                    '输出保持原值'
                ],
                'fix': [
                    '为所有 if 添加 else 分支',
                    '为 case 添加 default',
                    '在 always 开始给默认值',
                    '检查综合报告确认 latch'
                ],
                'code_example': '''// ❌ 错误：产生 latch
always @(*)
    if (enable)
        out = data;
    // 缺少 else，产生 latch

// ✅ 正确：完整赋值
always @(*) begin
    out = 0;  // 默认值
    if (enable)
        out = data;
end

// 或使用时序逻辑
always @(posedge clk)
    if (enable)
        out <= data;'''
            },
            
            BugPattern.SENSITIVITY_LIST: {
                'name': '敏感列表不完整',
                'severity': 'medium',
                'description': '组合逻辑 always 块敏感列表缺少信号',
                'symptoms': [
                    '仿真和综合结果不一致',
                    '缺少输入信号在敏感列表',
                    '输出不随输入变化'
                ],
                'fix': [
                    '使用 always @(*) 自动推断',
                    '手动添加所有输入信号',
                    '检查警告信息',
                    '对比仿真和综合波形'
                ],
                'code_example': '''// ❌ 错误：敏感列表不完整
always @(a or b)  // 缺少 c
    out = a && b && c;

// ✅ 正确：使用 @(*)
always @(*)
    out = a && b && c;'''
            },
            
            BugPattern.BLOCKING_NONBLOCKING: {
                'name': '阻塞/非阻塞混用',
                'severity': 'high',
                'description': '时序逻辑中错误使用阻塞赋值',
                'symptoms': [
                    '时序逻辑使用 = 赋值',
                    '仿真顺序依赖',
                    '综合结果与预期不符'
                ],
                'fix': [
                    '时序逻辑使用 <= 非阻塞赋值',
                    '组合逻辑使用 = 阻塞赋值',
                    '不要混用两种赋值',
                    '检查代码规范'
                ],
                'code_example': '''// ❌ 错误：时序逻辑用阻塞
always @(posedge clk) begin
    q1 = d;      // 错误！
    q2 = q1;     // 使用的是新值
end

// ✅ 正确：时序逻辑用非阻塞
always @(posedge clk) begin
    q1 <= d;     // 正确
    q2 <= q1;    // 使用的是旧值
end'''
            },
            
            BugPattern.MISSING_CLOCK: {
                'name': '缺少时钟',
                'severity': 'critical',
                'description': '时序逻辑缺少时钟或时钟未连接',
                'symptoms': [
                    '时序逻辑不更新',
                    '时钟信号恒定',
                    '时钟网络未连接'
                ],
                'fix': [
                    '检查时钟是否正确连接',
                    '验证时钟源是否工作',
                    '查看时钟门控逻辑',
                    '确认时钟树综合'
                ]
            },
            
            BugPattern.STUCK_STATE: {
                'name': '状态机卡死',
                'severity': 'high',
                'description': '状态机卡在某个状态无法转换',
                'symptoms': [
                    '状态寄存器恒定',
                    '状态转换条件不满足',
                    '缺少状态转换路径'
                ],
                'fix': [
                    '检查状态转换条件',
                    '确保所有状态都有出口',
                    '添加默认转换路径',
                    '验证状态编码',
                    '添加状态机监控'
                ],
                'code_example': '''// ❌ 错误：可能卡死
case (state)
    IDLE: if (start) state <= BUSY;
    BUSY: if (done) state <= IDLE;
endcase

// ✅ 正确：安全状态机
case (state)
    IDLE: if (start) state <= BUSY;
          else state <= IDLE;
    BUSY: if (done) state <= IDLE;
          else state <= BUSY;
    default: state <= IDLE;
endcase'''
            },
        }
    
    def detect_cdc(self, signal_name: str, deps: List[str], 
                   clock_info: Dict[str, str]) -> Optional[Diagnosis]:
        """检测跨时钟域问题"""
        # 检查信号是否跨越时钟域
        src_clock = clock_info.get(signal_name)
        
        for dep in deps:
            dep_clock = clock_info.get(dep)
            if dep_clock and src_clock and dep_clock != src_clock:
                return Diagnosis(
                    bug_pattern=BugPattern.CDC_ISSUE,
                    confidence=0.9,
                    severity='critical',
                    description=f"{signal_name} 从 {dep_clock} 域跨到 {src_clock} 域，未做同步",
                    root_cause="跨时钟域信号未同步",
                    fix_suggestions=self.knowledge_base[BugPattern.CDC_ISSUE]['fix'],
                    code_example=self.knowledge_base[BugPattern.CDC_ISSUE]['code_example'],
                    related_signals=[dep]
                )
        
        return None
    
    def detect_timing(self, signal_name: str, behavior: str, 
                      tv_data: List[Tuple], expected: Optional[str] = None) -> List[Diagnosis]:
        """检测时序问题（返回多个诊断）"""
        diagnoses = []
        
        if not tv_data or len(tv_data) < 2:
            return diagnoses
        
        # 检测 1: 变化间隔过小
        times = [t for t, v in tv_data]
        if len(times) >= 2:
            min_interval = min(times[i+1] - times[i] for i in range(len(times)-1))
            
            if min_interval < 100:  # 小于 100ps
                diagnoses.append(Diagnosis(
                    bug_pattern=BugPattern.TIMING_VIOLATION,
                    confidence=0.7,
                    severity='high',
                    description=f"{signal_name} 变化间隔过小 ({min_interval}ps)，可能时序违例",
                    root_cause="信号变化过快，不满足时序要求",
                    fix_suggestions=self.knowledge_base[BugPattern.TIMING_VIOLATION]['fix'],
                    code_example=self.knowledge_base[BugPattern.TIMING_VIOLATION]['code_example']
                ))
        
        # 检测 2: 时序错拍（提前/落后）
        if expected:
            if '应该在最后一拍' in expected or '应该在最后' in expected:
                # 检查最后一个变化点
                if tv_data:
                    last_time = tv_data[-1][0]
                    last_value = tv_data[-1][1]
                    
                    # 如果最后不是高电平，可能时序错拍
                    if last_value == '0':
                        diagnoses.append(Diagnosis(
                            bug_pattern=BugPattern.TIMING_VIOLATION,
                            confidence=0.65,
                            severity='medium',
                            description=f"{signal_name} 最后一拍为 0，可能时序错拍（应该拉高但未拉高）",
                            root_cause="时序逻辑打拍错误或计数器边界不对",
                            fix_suggestions=[
                                '检查计数器边界值是否正确',
                                '验证 last 信号是否打拍输出',
                                '对比数据 valid 和 last 的时序关系',
                                '检查是否提前或落后一拍'
                            ],
                            code_example='''// ❌ 错误：组合逻辑 last
assign last = (cnt == 7);

// ✅ 正确：时序逻辑 last
reg last_reg;
always @(posedge clk)
    last_reg <= (cnt == 7);'''
                        ))
        
        # 检测 3: 提前/落后检测
        if expected and ('提前' in expected or '落后' in expected):
            diagnoses.append(Diagnosis(
                bug_pattern=BugPattern.TIMING_VIOLATION,
                confidence=0.8,
                severity='high',
                description=f"{signal_name} 时序错拍（{expected}）",
                root_cause="时序逻辑打拍错误或使能信号不匹配",
                fix_suggestions=[
                    '检查信号是否需要对齐',
                    '验证打拍级数是否正确',
                    '对比相关信号的时序关系',
                    '检查计数器或状态机'
                ]
            ))
        
        return diagnoses
    
    def detect_race(self, signal_name: str, deps: List[str],
                    dep_behaviors: Dict[str, str]) -> Optional[Diagnosis]:
        """检测竞争冒险"""
        # 检查是否有多个依赖同时变化
        toggling_deps = [d for d in deps if '变化' in str(dep_behaviors.get(d, ''))]
        
        if len(toggling_deps) >= 3:
            return Diagnosis(
                bug_pattern=BugPattern.RACE_CONDITION,
                confidence=0.6,
                severity='medium',
                description=f"{signal_name} 有{len(toggling_deps)}个依赖同时变化，可能竞争",
                root_cause="多信号同时变化导致竞争冒险",
                fix_suggestions=self.knowledge_base[BugPattern.RACE_CONDITION]['fix'],
                code_example=self.knowledge_base[BugPattern.RACE_CONDITION]['code_example'],
                related_signals=toggling_deps
            )
        
        return None
    
    def diagnose(self, signal_name: str, behavior: str,
                 deps: List[str], dep_behaviors: Dict[str, str],
                 expected: Optional[str] = None,
                 tv_data: List[Tuple] = None,
                 clock_info: Dict[str, str] = None) -> List[Diagnosis]:
        """
        增强版诊断 - 返回多个可能的诊断结果（按优先级排序）
        """
        diagnoses = []
        
        # 1. 检测跨时钟域问题
        if clock_info:
            cdc_diag = self.detect_cdc(signal_name, deps, clock_info)
            if cdc_diag:
                diagnoses.append(cdc_diag)
        
        # 2. 检测时序问题（返回多个）
        if tv_data:
            timing_diags = self.detect_timing(signal_name, behavior, tv_data, expected)
            diagnoses.extend(timing_diags)
        
        # 3. 检测竞争冒险
        race_diag = self.detect_race(signal_name, deps, dep_behaviors)
        if race_diag:
            diagnoses.append(race_diag)
        
        # 4. 原有规则检测
        # 死信号检测
        if not deps and ('始终为' in behavior or '静默' in behavior):
            diagnoses.append(Diagnosis(
                bug_pattern=BugPattern.DEAD_SIGNAL,
                confidence=0.9,
                severity='high',
                description=f"{signal_name} 无依赖且恒定，可能是死信号",
                root_cause=self.knowledge_base[BugPattern.DEAD_SIGNAL]['description'],
                fix_suggestions=self.knowledge_base[BugPattern.DEAD_SIGNAL]['fix'],
                code_example=self.knowledge_base[BugPattern.DEAD_SIGNAL]['code_example']
            ))
        
        # 使能条件错误
        if ('始终为' in behavior or '静默' in behavior) and deps:
            has_toggling_dep = any('变化' in str(dep_behaviors.get(d, '')) for d in deps)
            if has_toggling_dep:
                diagnoses.append(Diagnosis(
                    bug_pattern=BugPattern.WRONG_ENABLE,
                    confidence=0.8,
                    severity='high',
                    description=f"{signal_name} 恒定但依赖有变化，使能条件可能不满足",
                    root_cause="使能信号条件错误或控制逻辑有问题",
                    fix_suggestions=[
                        '检查使能信号的驱动逻辑',
                        '验证控制状态机',
                        '确认使能条件的布尔表达式',
                        '查看是否有死锁条件'
                    ]
                ))
        
        # 状态机卡死
        if any(kw in signal_name.lower() for kw in ['state', 'status', 'mode']):
            if '始终为' in behavior:
                diagnoses.append(Diagnosis(
                    bug_pattern=BugPattern.STUCK_STATE,
                    confidence=0.85,
                    severity='high',
                    description=f"{signal_name} 疑似状态机信号且恒定，可能卡死",
                    root_cause=self.knowledge_base[BugPattern.STUCK_STATE]['description'],
                    fix_suggestions=self.knowledge_base[BugPattern.STUCK_STATE]['fix'],
                    code_example=self.knowledge_base[BugPattern.STUCK_STATE]['code_example']
                ))
        
        # 逻辑错误
        if expected and ('应该有变化' in expected or '应该跳变' in expected):
            if '始终为' in behavior:
                diagnoses.append(Diagnosis(
                    bug_pattern=BugPattern.LOGIC_ERROR,
                    confidence=0.75,
                    severity='medium',
                    description=f"{signal_name} 预期有变化但实际恒定，逻辑可能有误",
                    root_cause="组合逻辑或时序逻辑有错误",
                    fix_suggestions=[
                        '检查布尔表达式',
                        '验证真值表',
                        '查看位宽和符号',
                        '确认操作符优先级'
                    ]
                ))
        
        # 按置信度和严重性排序
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        diagnoses.sort(key=lambda d: (severity_order.get(d.severity, 3), -d.confidence))
        
        return diagnoses
    
    def generate_priority_report(self, signal_name: str, 
                                 diagnoses: List[Diagnosis],
                                 analysis_path: List[Tuple[str, str]]) -> str:
        """生成优先级诊断报告"""
        if not diagnoses:
            return "✅ 未发现问题"
        
        report = []
        report.append("=" * 80)
        report.append("🏥 智能诊断报告 (增强版)")
        report.append("=" * 80)
        report.append('')
        
        report.append(f"🔴 问题信号：{signal_name}")
        report.append(f"📊 发现问题：{len(diagnoses)} 个")
        report.append('')
        
        # 按优先级列出所有诊断
        for i, diag in enumerate(diagnoses, 1):
            kb = self.knowledge_base.get(diag.bug_pattern, {})
            severity_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}.get(diag.severity, '⚪')
            
            report.append("-" * 80)
            report.append(f"问题 #{i} {severity_icon} {kb.get('name', diag.bug_pattern.value)}")
            report.append("-" * 80)
            report.append('')
            
            confidence_bar = "█" * int(diag.confidence * 10) + "░" * (10 - int(diag.confidence * 10))
            report.append(f"📈 置信度：{confidence_bar} {diag.confidence*100:.0f}%")
            report.append(f"⚠️  严重性：{diag.severity.upper()}")
            report.append('')
            
            report.append(f"🔍 诊断：{diag.description}")
            report.append('')
            
            report.append(f"🧠 根因：{diag.root_cause}")
            report.append('')
            
            if diag.related_signals:
                report.append(f"🔗 相关信号：{', '.join(diag.related_signals)}")
                report.append('')
            
            report.append("💡 修复建议:")
            for j, fix in enumerate(diag.fix_suggestions, 1):
                report.append(f"   {j}. {fix}")
            report.append('')
            
            if diag.code_example:
                report.append("📝 代码示例:")
                report.append("   ```verilog")
                for line in diag.code_example.split('\n'):
                    report.append(f"   {line}")
                report.append("   ```")
                report.append('')
        
        # 分析路径
        if analysis_path:
            report.append("=" * 80)
            report.append("🔗 分析路径")
            report.append("=" * 80)
            report.append('')
            
            for i, (sig, beh) in enumerate(analysis_path):
                marker = "🎯 根因" if i == len(analysis_path) - 1 else f"   步骤{i+1}"
                report.append(f"   {marker}: {sig}")
                report.append(f"              行为：{beh}")
            report.append('')
        
        # 总结建议
        report.append("=" * 80)
        report.append("🎯 总结建议")
        report.append("=" * 80)
        report.append('')
        
        if diagnoses:
            top_diag = diagnoses[0]
            report.append(f"优先处理：{top_diag.bug_pattern.value} (置信度{top_diag.confidence*100:.0f}%)")
            report.append('')
            report.append("建议按以下顺序排查:")
            for i, diag in enumerate(diagnoses[:3], 1):
                report.append(f"   {i}. {diag.description}")
            report.append('')
            report.append("📋 行动清单:")
            report.append("   1. 根据优先级修复最严重的问题")
            report.append("   2. 修改后重新仿真验证")
            report.append("   3. 如问题仍存在，继续追踪上游信号")
            report.append("   4. 必要时添加调试信号或波形")
        
        report.append('')
        report.append("=" * 80)
        
        return '\n'.join(report)


def main():
    """测试"""
    reasoner = AdvancedReasoner()
    
    # 测试用例
    diagnoses = reasoner.diagnose(
        signal_name="transfer_done",
        behavior="始终为 0 (恒定信号)",
        deps=["all_b_received"],
        dep_behaviors={"all_b_received": "始终为 0 (恒定信号)"},
        expected="应该有变化"
    )
    
    report = reasoner.generate_priority_report(
        "transfer_done",
        diagnoses,
        [("transfer_done", "始终为 0"), ("all_b_received", "始终为 0")]
    )
    
    print(report)


if __name__ == '__main__':
    main()
