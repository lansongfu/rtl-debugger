---
name: rtl-debugger
version: 1.5.0
description: RTL 波形分析调试工具 - 智能流式查询、深度信号分析、AXI4/APB 协议解析
author: 木叶村克劳
license: MIT
homepage: https://github.com/lansongfu/rtl-debugger
repository: https://github.com/lansongfu/rtl-debugger
tags: ["RTL", "Verilog", "debug", "waveform", "VCD", "AXI", "APB"]
metadata: {"clawdbot":{"emoji":"🔬"}}
---

# RTL Debugger Skill

> 🎯 **让 AI Agent 都能使用的 RTL 调试工具**  
> ⚡ 性能：毫秒级查询，30,000 倍加速  
> 📦 版本：v1.5.0 (标准 Python 包)

---

## 📥 输入要求（必读！）

**使用本技能前，必须获取以下信息：**

| 参数 | 必需 | 说明 | 常见值 |
|------|------|------|--------|
| **filelist 路径** | ✅ 必需 | RTL 文件列表 | `sim/filelist.f`, `run.f`, `compile.f` |
| **VCD 文件路径** | ⚠️ 可选 | 波形文件（用于波形分析） | `sim/output/testbench.vcd`, `waves/*.vcd` |
| **信号名称** | ✅ 必需 | 要分析的信号名 | `transfer_done`, `axi_wvalid` |

---

## 🤖 Agent 调用指南（重要！）

### 第一步：检查必要信息

在调用本技能前，**必须确认**：
1. ✅ filelist 文件路径
2. ✅ 信号名称
3. ⚠️ VCD 文件路径（如果需要波形分析）

### 第二步：缺少信息时主动询问

**如果用户没有提供 filelist：**
```
❌ 错误做法：直接调用技能（会失败）
✅ 正确做法：询问用户

"请提供 filelist 文件路径，例如：
   - sim/filelist.f
   - run.f
   - compile.f
   
或者提供项目根目录，我可以自动查找。"
```

**如果用户没有提供 VCD（需要波形分析时）：**
```
❌ 错误做法：跳过 VCD 分析
✅ 正确做法：询问用户

"请提供 VCD 波形文件路径，例如：
   - sim/output/testbench.vcd
   - waves/simulation.vcd
   
或者提供仿真输出目录，我可以自动查找。"
```

### 第三步：调用技能

获取到必要信息后，根据任务类型选择合适的工具：

| 任务 | 工具 | 示例 |
|------|------|------|
| 查 RTL 依赖 | `rtl_query.py --signal` | `rtl_query.py -f design.f -s transfer_done` |
| 全局搜索 | `rtl_query.py --global` | `rtl_query.py -f design.f -g "*valid*"` |
| 跨模块追踪 | `rtl_query.py --cross` | `rtl_query.py -f design.f -c data_out -m top` |
| VCD 波形查询 | `VCDSmartStream` | Python API |
| 协议分析 | `analyze_axi4` | Python API |

---

## 📋 技能描述

**RTL Debugger** 是一个专业的 RTL 波形分析调试工具，为 AI Agent 提供：

- 🔍 **快速信号查询** - 时间窗口查询（0.2-2ms）
- 📊 **深度信号分析** - 脉冲/时钟/总线/状态机分析
- 🌐 **协议解析** - AXI4/APB/AHB 协议自动分析
- 🤖 **智能调试** - 自动追踪依赖，定位根因

---

## 🎯 触发词

**自动触发：**
- "调试.*信号"
- "分析.*波形"
- "为什么.*不跳"
- "时序.*问题"
- "AXI.*问题"
- "协议.*违规"

**手动调用：**
- `rtl-debug`
- `rtl-debugger`
- `analyze-axi`
- `analyze-pulse`

---

## 🛠️ 功能列表

### 1. 深度信号分析

```python
from rtl_debugger import analyze_pulse, analyze_clock, analyze_bus, analyze_fsm

# 脉冲分析
result = analyze_pulse('waveform.vcd', 'interrupt')
# 返回：脉冲数量、脉宽、周期、占空比

# 时钟分析
result = analyze_clock('waveform.vcd', 'clk')
# 返回：频率、周期、占空比、抖动、稳定性

# 总线分析
result = analyze_bus('waveform.vcd', {'data': 'wdata', 'valid': 'wvalid'})
# 返回：事务数、Burst 数、利用率、延迟

# 状态机分析
result = analyze_fsm('waveform.vcd', ['state[0]', 'state[1]'])
# 返回：状态转移、循环、死状态
```

### 2. 协议解析

```python
from rtl_debugger import analyze_axi4, analyze_apb

# AXI4 协议分析
result = analyze_axi4('waveform.vcd', {
    'awvalid': 'axi_awvalid',
    'wvalid': 'axi_wvalid',
    'bvalid': 'axi_bvalid'
})
# 返回：事务列表、违规检测、性能统计

# APB 协议分析
result = analyze_apb('waveform.vcd', {
    'psel': 'apb_psel',
    'penable': 'apb_penable'
})
# 返回：事务列表、错误检测
```

### 3. 交互式调试

```python
from rtl_debugger import InteractiveDebugger

debugger = InteractiveDebugger('design.f', 'waveform.vcd')
debugger.run('transfer_done', expected='应该在 t=1000ns 拉高')
# 自动追踪依赖，定位根因
```

### 4. 快速查询

```python
from rtl_debugger import VCDSmartStream

with VCDSmartStream('waveform.vcd') as q:
    q.parse_header_fast()
    changes = q.query_window('signal', 0, 100000)
    # 毫秒级查询
```

---

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/lansongfu/rtl-debugger.git
cd rtl-debugger

# 安装依赖
pip install -r requirements.txt

# 验证安装
python -m rtl_debugger --help
```

---

## 📚 完整示例

### 示例 1: 用户主动提供所有信息

**用户输入：**
```
帮我看看 transfer_done 信号，filelist 是 sim/filelist.f
```

**Agent 操作：**
```bash
rtl_query.py --filelist sim/filelist.f --signal transfer_done
```

---

### 示例 2: 用户未提供 filelist（需要询问）

**用户输入：**
```
transfer_done 信号为什么没变化？
```

**Agent 操作：**
```
❌ 错误：直接调用技能

✅ 正确：询问用户
"请提供 filelist 文件路径，例如 sim/filelist.f 或 run.f"
```

**用户提供后：**
```
sim/filelist.f
```

**Agent 操作：**
```bash
rtl_query.py --filelist sim/filelist.f --signal transfer_done
```

---

### 示例 3: 需要 VCD 波形分析

**用户输入：**
```
axi_wvalid 在 t=1000ns 应该拉高，但没反应
```

**Agent 操作：**
```
✅ 正确：询问 VCD 路径
"请提供 VCD 波形文件路径，例如 sim/output/testbench.vcd"
```

**用户提供后：**
```
sim/output/testbench.vcd
```

**Agent 操作：**
```python
from rtl_debugger import VCDSmartStream

with VCDSmartStream('sim/output/testbench.vcd') as q:
    q.parse_header_fast()
    changes = q.query_window('axi_wvalid', 0, 2000000)
    print(f"axi_wvalid 变化：{changes}")
```

---

## 🚀 使用示例

```python
from rtl_debugger import analyze_clock

result = analyze_clock('waveform.vcd', 'clk')

if result['stable']:
    print(f"✅ 时钟稳定：{result['frequency_mhz']:.2f} MHz")
else:
    print(f"⚠️  时钟不稳定！抖动：{result['jitter_ps']:.2f} ps")
```

### 场景 2: AXI 总线性能

```python
from rtl_debugger import analyze_axi4

result = analyze_axi4('axi_waveform.vcd', signals)

if result['violations']:
    print(f"⚠️  检测到 {len(result['violations'])} 次协议违规")
```

### 场景 3: 自动调试

```python
from rtl_debugger import InteractiveDebugger

debugger = InteractiveDebugger('design.f', 'waveform.vcd')
debugger.run('transfer_done', expected='应该在 t=1000ns 拉高')
```

### 场景 4: 命令行使用

```bash
# 脉冲分析
python -m rtl_debugger analyze-pulse waveform.vcd interrupt

# 时钟分析
python -m rtl_debugger analyze-clock waveform.vcd clk

# AXI4 分析
python -m rtl_debugger analyze-axi waveform.vcd --prefix axi
```

---

## 📊 性能参考

| 功能 | 数据量 | 耗时 |
|------|--------|------|
| 时间窗口查询 | 100ns 窗口 | **0.2ms** |
| 脉冲分析 | 100 个脉冲 | **1-5ms** |
| 时钟分析 | 1000 个周期 | **5-10ms** |
| 总线分析 | 100 次事务 | **10-50ms** |
| AXI4 解析 | 50 次事务 | **50-100ms** |

---

## 🔧 依赖

- Python 3.10+
- vcdvcd>=1.0.0
- Windows/Linux/macOS 跨平台支持

---

## 📚 文档

- **AGENT_GUIDE.md** - Agent 使用指南
- **README.md** - 项目说明
- **GitHub:** https://github.com/lansongfu/rtl-debugger

---

## 🍃 出品

**木叶村克劳** - 让 RTL 调试像聊天一样简单
