# RTL Debugger - AI 集成指南 v1.1

> 🎯 **让所有 AI 都能自动调用 RTL 调试工具**
> 
> **v1.1 更新：** 新增真正的交互式调试器（迭代追踪）

---

## 🎯 触发方式

### 方式 1: 自然语言触发（推荐）

**当用户说以下类似内容时，AI 应自动调用 RTL Debugger：**

#### 调试信号
- "为什么 transfer_done 不跳变？"
- "调试一下这个信号"
- "分析这个信号的行为"
- "查看信号依赖关系"

#### 波形分析
- "分析波形中的问题"
- "查看 VCD 文件"
- "为什么波形和预期不符？"
- "信号时序有问题"

#### 时序问题
- "时序错拍了"
- "提前/落后一拍"
- "时序不匹配"
- "建立/保持时间违例"

#### CDC 问题
- "跨时钟域问题"
- "CDC 未同步"
- "亚稳态风险"
- "时钟域转换"

#### **追踪依赖（v1.1 新增）**
- "一路追下去看看"
- "追踪这个信号的依赖"
- "层层往下分析"
- "找到根因"

---

## 💻 AI 调用代码示例

### 方式 1: 真正的交互式调试（v1.1 推荐）

**特点：** 自动迭代追踪，直到找到根因

```python
import subprocess
import os

def debug_rtl_interactive(signal_name, filelist_path, vcd_path, expected=None):
    """
    真正的交互式调试器（v1.1）
    
    核心：AI 根据实际工具返回结果，一步步迭代追踪
    1. 查 RTL 依赖
    2. 查 VCD 行为
    3. 判断是否异常
    4. 如果异常，继续追依赖
    5. 直到找到根因
    """
    
    skill_dir = os.path.expanduser('~/.openclaw/workspace/skills/rtl-debugger')
    
    cmd = [
        os.path.join(skill_dir, 'venv', 'bin', 'python'),
        os.path.join(skill_dir, 'tools', 'interactive_debugger.py'),
        signal_name,
        '--filelist', filelist_path,
        '--vcd', vcd_path
    ]
    
    if expected:
        cmd.extend(['--expected', expected])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    return result.stdout

# 使用示例
output = debug_rtl_interactive(
    signal_name='transfer_done',
    filelist_path='src/filelist.f',
    vcd_path='sim/waveform.vcd',
    expected='应该有变化'
)

print(output)
```

**输出示例：**
```
🔍 步骤 1: 分析 transfer_done
   📊 查询 RTL 依赖...
   📝 依赖：all_b_received
   📈 查询 VCD 行为...
   📝 行为：始终为 0 (恒定信号)
   ⚠️  发现异常
   🔗 继续追踪依赖...

  🔍 步骤 2: 分析 all_b_received
     📊 查询 RTL 依赖...
     📝 无依赖（叶信号）
     📈 查询 VCD 行为...
     📝 行为：始终为 0 (恒定信号)
     ⚠️  发现异常

🎯 找到根因：all_b_received
   行为：始终为 0 (恒定信号)
   追踪路径：transfer_done → all_b_received
```

---

### 方式 2: 手动迭代（v1.0）

**特点：** AI 手动控制每一步，更灵活

```python
def debug_rtl_manual(signal_name, filelist_path, vcd_path):
    """
    手动迭代调试（v1.0）
    
    AI 手动控制：
    1. 调用 rtl_query.py 查依赖
    2. 调用 vcd_query.py 查行为
    3. AI 判断是否继续追
    4. 循环直到找到根因
    """
    
    skill_dir = os.path.expanduser('~/.openclaw/workspace/skills/rtl-debugger')
    
    # Step 1: 查 RTL 依赖
    rtl_cmd = [
        os.path.join(skill_dir, 'venv', 'bin', 'python'),
        os.path.join(skill_dir, 'tools', 'rtl_query.py'),
        '--filelist', filelist_path,
        '--signal', signal_name
    ]
    rtl_result = subprocess.run(rtl_cmd, capture_output=True, text=True)
    
    # Step 2: 查 VCD 行为
    vcd_cmd = [
        os.path.join(skill_dir, 'venv', 'bin', 'python'),
        os.path.join(skill_dir, 'tools', 'vcd_query.py'),
        vcd_path,
        '--signal', signal_name
    ]
    vcd_result = subprocess.run(vcd_cmd, capture_output=True, text=True)
    
    # Step 3: AI 分析结果，决定是否继续追
    # ...（AI 逻辑）
    
    return {
        'rtl': rtl_result.stdout,
        'vcd': vcd_result.stdout
    }
```

---

## 📋 工具选择指南

### 什么时候用哪个工具？

| 工具 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| **interactive_debugger.py** (v1.1) | 快速定位根因 | 自动迭代，无需人工干预 | 控制较少 |
| **rtl_query.py + vcd_query.py** (v1.0) | 深度分析 | 完全控制每一步 | 需要 AI 手动迭代 |
| **interactive_debug_analyzer.py** | 综合分析 | 支持 CDC/时序/竞争分析 | 较重，需要参数 |
| **advanced_reasoner.py** | 多诊断报告 | 14 种 Bug 模式 | 预设规则 |

---

## 🎯 典型场景

### 场景 1: 信号不跳变（推荐用 v1.1）

**用户：** "为什么 transfer_done 一直不跳？"

**AI 响应：**
```python
# 使用真正的交互式调试器（v1.1）
output = debug_rtl_interactive(
    signal_name='transfer_done',
    filelist_path='src/filelist.f',
    vcd_path='sim/waveform.vcd',
    expected='应该有变化'
)

print(output)
```

**输出：**
```
🔍 交互式调试：transfer_done

🔍 步骤 1: 分析 transfer_done
   📊 依赖：all_b_received
   📈 行为：始终为 0 (恒定信号)
   ⚠️  异常！继续追踪...

  🔍 步骤 2: 分析 all_b_received
     📊 依赖：无（叶信号）
     📈 行为：始终为 0 (恒定信号)
     ⚠️  异常！

🎯 找到根因：all_b_received
   行为：始终为 0 (恒定信号)
   追踪路径：transfer_done → all_b_received

💡 建议：
   1. 检查 all_b_received 的驱动逻辑
   2. 查看相关控制信号
```

---

### 场景 2: 深度分析（用 v1.0 手动迭代）

**用户：** "帮我详细分析一下这个信号"

**AI 响应：**
```python
# AI 手动控制每一步
current_signal = 'transfer_done'
trace_path = []

while True:
    # 查 RTL
    rtl = query_rtl(current_signal)
    
    # 查 VCD
    vcd = query_vcd(current_signal)
    
    # AI 判断
    if is_anomaly(vcd):
        trace_path.append(current_signal)
        if rtl['deps']:
            current_signal = rtl['deps'][0]  # 继续追
        else:
            break  # 找到根因
    else:
        break  # 正常

# 输出结果
print(f"追踪路径：{' → '.join(trace_path)}")
```

---

### 场景 3: CDC 问题（用 advanced_reasoner）

**用户：** "怀疑有跨时钟域问题"

**AI 响应：**
```python
# 启用 CDC 分析
cmd.extend(['--cdc'])
result = run_debug(cmd)
```

---

## 🔧 AI 决策树

```
用户问题
    │
    ├─ "为什么 X 不跳？" ──→ interactive_debugger.py (v1.1)
    │
    ├─ "分析 X 信号" ──→ rtl_query.py + vcd_query.py
    │
    ├─ "全面分析" ──→ interactive_debug_analyzer.py --all
    │
    ├─ "CDC 问题" ──→ interactive_debug_analyzer.py --cdc
    │
    ├─ "时序问题" ──→ interactive_debug_analyzer.py --timing
    │
    └─ "一路追下去" ──→ interactive_debugger.py (v1.1)
```

---

## 📊 工具对比

### v1.0 vs v1.1

| 特性 | v1.0 | v1.1 |
|------|------|------|
| **调试方式** | 手动迭代 | 自动迭代 |
| **控制度** | 高 | 中 |
| **易用性** | 中 | 高 |
| **适用场景** | 深度分析 | 快速定位 |
| **AI 参与度** | 高（每步决策） | 低（自动完成） |

---

## 📖 完整 API

### interactive_debugger.py (v1.1)

```bash
./venv/bin/python tools/interactive_debugger.py <signal> \
  --filelist <filelist.f> \
  --vcd <waveform.vcd> \
  --expected "<expected_behavior>"
```

**参数：**
- `signal` (必需): 目标信号
- `--filelist` (必需): RTL filelist 文件
- `--vcd` (必需): VCD 波形文件
- `--expected` (可选): 预期行为描述

**输出：**
- 追踪路径
- 每步的 RTL 依赖和 VCD 行为
- 根因定位
- 修复建议

---

### rtl_query.py (v1.0)

```bash
./venv/bin/python tools/rtl_query.py \
  --filelist <filelist.f> \
  --signal <signal_name>
```

**输出：**
- 信号类型（port/wire/reg）
- 依赖关系
- 驱动源

---

### vcd_query.py (v1.0)

```bash
./venv/bin/python tools/vcd_query.py <vcd_file> \
  --signal <signal_name>
```

**输出：**
- 信号行为（恒定/跳变/静默）
- 变化次数
- 时间信息

---

## 🎯 最佳实践

### 1. 优先使用 v1.1

**推荐：**
```python
# 一行代码搞定
output = debug_rtl_interactive(signal, filelist, vcd, expected)
```

**优点：**
- 自动迭代
- 无需 AI 手动控制
- 输出清晰

---

### 2. 复杂问题用 v1.0

**当需要深度分析时：**
```python
# AI 手动控制每一步
while True:
    rtl = query_rtl(signal)
    vcd = query_vcd(signal)
    # AI 决策是否继续
```

---

### 3. 提供预期行为

**有预期行为，诊断更准确：**
```python
# 好
debug_rtl_interactive(signal, filelist, vcd, expected='应该有变化')

# 一般
debug_rtl_interactive(signal, filelist, vcd)
```

---

### 4. 解释追踪路径

**给用户清晰的调试过程：**
```
📋 追踪路径：
   1. transfer_done (目标信号)
   2. all_b_received (依赖)
   3. b_valid_reg (依赖)
   4. ... (继续)

🎯 根因：b_valid_reg
   行为：始终为 0
```

---

## 📁 文件位置

- **Skill 路径:** `~/.openclaw/workspace/skills/rtl-debugger/`
- **v1.1 调试器:** `tools/interactive_debugger.py`
- **v1.0 工具:** `tools/rtl_query.py`, `tools/vcd_query.py`
- **文档:** `AI_INTEGRATION.md`
- **GitHub:** https://github.com/lansongfu/rtl-debugger

---

## 🚀 快速开始

**AI 调用模板：**
```python
import subprocess
import os

def debug_signal(signal, filelist='src/filelist.f', vcd='sim/waveform.vcd', expected=None):
    skill_dir = os.path.expanduser('~/.openclaw/workspace/skills/rtl-debugger')
    
    cmd = [
        os.path.join(skill_dir, 'venv', 'bin', 'python'),
        os.path.join(skill_dir, 'tools', 'interactive_debugger.py'),
        signal,
        '--filelist', os.path.join(skill_dir, '..', '..', filelist),
        '--vcd', os.path.join(skill_dir, '..', '..', vcd)
    ]
    
    if expected:
        cmd.extend(['--expected', expected])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

# 使用
print(debug_signal('transfer_done', expected='应该有变化'))
```

---

_版本：v1.1.0_  
_最后更新：2026-03-23 23:35_  
_适用于：所有 OpenClaw AI Agents_
