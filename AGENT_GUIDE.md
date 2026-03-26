# RTL Debugger - Agent 使用指南

> 🎯 **让 AI Agent 都能使用的 RTL 调试工具**  
> 📚 版本：v1.4.0  
> ⚡ 性能：毫秒级查询，30,000 倍加速

---

## 🔄 标准调试流程（必读！）

**核心原则：默认只查上一级，逐步定位问题**

```
用户：A 信号异常
   ↓
Agent: 调用 VCD 查看 A 信号波形
   ↓ 发现 t=1000ns 异常
   ↓
Agent: 调用 rtl_query --signal A（默认模式，只查上一级）
   ↓ 返回：A ← B, C, D
   ↓
Agent: 调用 VCD 查看 B/C/D 在 t=1000ns 的波形
   ↓ 发现 D 异常
   ↓
Agent: 调用 rtl_query --signal D（默认模式，只查上一级）
   ↓ 返回：D ← E, F
   ↓
Agent: 调用 VCD 查看 E/F...
   ↓
逐步定位到根因！
```

**为什么这样设计？**
- ✅ **单步定位** - 每次只看直接驱动信号，避免信息过载
- ✅ **VCD 联动** - Agent 自主决定何时调用 VCD 验证
- ✅ **高效排查** - 通常 2-3 步就能定位到根因

**完整依赖树（可选）**
```bash
# 需要时才用 --full 查看完整链路
rtl_query.py --filelist design.f --signal data_out --full
```

---

## 🎯 工具选择决策树（必读！）

**根据你的任务类型，快速选择正确工具：**

```
┌─────────────────────────────────────────────────────────────┐
│  你的任务是什么？                                            │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   查看波形           分析 RTL 代码        智能诊断
   (VCD 文件)          (Verilog 源文件)     (自动找根因)
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐  ┌───────────────┐  ┌─────────────────┐
│ VCDSmartStream│  │ rtl_query.py  │  │ interactive_    │
│ - query_window│  │ --signal      │  │ debug_analyzer  │
│ - analyze_    │  │ --trace       │  │ --expected      │
│   behavior    │  │               │  │                 │
└───────────────┘  └───────────────┘  └─────────────────┘
        │                 │                 │
        ▼                 ▼                 ▼
   0.2-2ms           0.04s              1.8s
   极快！             快速               完整诊断
```

### 📋 快速参考表

| 任务类型 | 推荐工具 | 调用方式 | 耗时 |
|----------|----------|----------|------|
| **查看信号值变化** | `VCDSmartStream.query_window()` | Python API | 0.2-2ms |
| **分析信号是否正常** | `VCDSmartStream.analyze_behavior()` | Python API | 1-5ms |
| **追踪信号根因** | `InteractiveDebugger.run()` | Python API | 1-2s |
| **查 RTL 驱动关系** | `rtl_query.py --signal` | 命令行 | 0.04s |
| **AXI 协议分析** | `analyze_axi4()` | Python API | 50-100ms |
| **脉冲/时钟分析** | `analyze_pulse()` / `analyze_clock()` | Python API | 1-10ms |
| **Bug 自动诊断** | `interactive_debug_analyzer.py` | 命令行 | 1-2s |

---

## 🔧 rtl_query.py - RTL 依赖分析工具（独立使用指南）

**核心问题：** 这个信号的跳转变化条件是什么？谁驱动了它？

### 安装后位置
```
/root/.openclaw/workspace/skills/rtl-debugger/tools/rtl_query.py
```

### 命令行调用（推荐）

```bash
# 方式 1: 直接指定 Verilog 文件
./venv/bin/python tools/rtl_query.py src/design.v --signal transfer_done

# 方式 2: 使用 filelist（多文件项目）
./venv/bin/python tools/rtl_query.py --filelist src/filelist.f --signal transfer_done

# 方式 3: 递归追踪依赖链
./venv/bin/python tools/rtl_query.py --filelist src/filelist.f --trace transfer_done

# 方式 4: 全局搜索信号（不知道信号在哪个模块时）
./venv/bin/python tools/rtl_query.py --filelist chip.f --global "*transfer*"

# 方式 5: 跨模块追踪（追踪到子模块）
./venv/bin/python tools/rtl_query.py --filelist design.f --cross data_out --module top

# 方式 6: 完整依赖树（查看端到端连接）
./venv/bin/python tools/rtl_query.py --filelist design.f --signal data_out --full
```

### 命令行参数

| 参数 | 短参 | 说明 | 默认值 |
|------|------|------|--------|
| `--signal` | `-s` | 查询信号依赖 | - |
| `--trace` | `-t` | 追踪信号（同 --signal） | - |
| `--filelist` | `-f` | filelist 文件路径 | - |
| `--module` | `-m` | 指定模块名 | 所有模块 |
| `--cross` | `-c` | 跨模块追踪信号 | - |
| `--global` | `-g` | 全局搜索信号（支持 `*` `?`） | - |
| `--regex` | `-r` | 使用正则表达式搜索 | 关闭 |
| `--full` | | 追踪完整依赖树到源头 | 单步模式 |
| `--depth` | `-d` | 最大追踪深度 | 10 |

### 输出示例

#### 单步查询（默认）

```bash
./venv/bin/python tools/rtl_query.py --filelist design.f --signal transfer_done
```

```
🔍 信号查询：transfer_done

📦 模块：dma_ctrl
   类型：internal
   驱动：assign/always
   ⏰ 时钟：clk
   🔄 异步复位：rst_n
   🎛️  控制信号:
      ⚡ rst_n
      ⚡ enable
   📋 条件表达式:
      [if] !rst_n
      [if] enable
   📊 数据信号:
      ← all_b_received

🔗 依赖链（上一级）:
transfer_done ← all_b_received
```

#### 全局搜索

```bash
./venv/bin/python tools/rtl_query.py --filelist chip.f --global "*transfer*"
```

```
🔍 全局搜索：*transfer*

找到 3 个匹配:
1. top.dma_ctrl.transfer_done (internal)
   ← all_b_received
2. top.axi_master.transfer_done (output)
   ← dma_ctrl.transfer_done
3. top.soc_top.transfer_done (input)
   ← axi_master.transfer_done
```

#### 跨模块追踪

```bash
./venv/bin/python tools/rtl_query.py --filelist design.f --cross data_out --module top
```

```
🔗 跨模块追踪：data_out (从 top 开始)

第 0 层：top.data_out
  ← mid_data (wire)

第 1 层：sub_module.data_out (通过 u_sub 连接)
  ← data_in (时序逻辑，clk=clk)

第 2 层：sub_module.data_in (port)
  ← top.data_in (顶层输入)

📊 追踪了 3 层连接，到达顶层接口
```

#### 完整依赖树

```bash
./venv/bin/python tools/rtl_query.py --filelist design.f --signal data_out --full
```

```
🔗 完整依赖树：data_out

data_out
  ← mid_data (组合)
    ← sub_module.data_out (时序，clk=clk)
      ← sub_module.data_in (组合)
        ← top.data_in (primary input)

🎯 关键路径：data_in → sub_module → data_out (1 拍延迟)
```
  使能条件：cmd_valid, cmd_ready

all_b_received ← rx_byte_cnt, CMD_B_BYTES
  驱动类型：combinational (组合逻辑)
  条件：state == READ_B
```

### Python API 调用

```python
import sys
sys.path.insert(0, 'tools')
from rtl_query import RTLDependencyAnalyzer

analyzer = RTLDependencyAnalyzer()
analyzer.parse_file('src/design.v')

# 查询信号依赖
deps = analyzer.get_signal_deps('transfer_done')
print(deps)

# 递归追踪
chain = analyzer.trace_dependency('transfer_done')
print(chain)
```

### 支持的解析特性

✅ 基础 assign/always 解析  
✅ 嵌套 filelist（无限层）  
✅ 环境变量支持（$VAR / ${VAR}）  
✅ `define 宏展开  
✅ parameter/localparam  
✅ `include 文件包含  
✅ generate for/if块  
✅ 时序逻辑条件提取（if/case 使能）  
✅ 时钟/复位信号识别  
✅ 循环依赖检测  

---

## 📖 快速开始

### 1. 安装 Skill

```bash
# 克隆仓库
git clone https://github.com/lansongfu/rtl-debugger.git
cd rtl-debugger

# 安装依赖
pip install -r requirements.txt
```

### 2. 导入工具（标准方式）

```python
# 标准导入（推荐）
from rtl_debugger import analyze_axi4, analyze_pulse, InteractiveDebugger

# 使用
result = analyze_axi4('waveform.vcd', signals)
```

### 3. 命令行使用

```bash
# 脉冲分析
python -m rtl_debugger analyze-pulse waveform.vcd signal_name

# 时钟分析
python -m rtl_debugger analyze-clock waveform.vcd clk

# AXI4 分析
python -m rtl_debugger analyze-axi waveform.vcd --prefix axi

# 快速查询
python -m rtl_debugger query waveform.vcd signal_name --start-time 0 --end-time 100000
```

---

## 🛠️ 核心功能

### 功能 1: 时间窗口查询（最快！0.2-2ms）

**使用场景：** 已知问题时间范围，快速查看信号行为

```python
from tools.vcd_smart import VCDSmartStream

with VCDSmartStream('waveform.vcd') as q:
    q.parse_header_fast()
    
    # 查询指定时间窗口
    changes = q.query_window('transfer_done', 
                             start_time=0, 
                             end_time=100000)  # ps
    
    print(f"找到 {len(changes)} 次变化:")
    for time, value in changes[:5]:
        print(f"  t={time}ps: {value}")
```

**返回示例：**
```
找到 3 次变化:
  t=0ps: 0
  t=50000ps: 1
  t=100000ps: 0
```

---

### 功能 2: 行为分析（快速判断）

**使用场景：** 快速判断信号是否正常

```python
from tools.vcd_smart import VCDSmartStream

with VCDSmartStream('waveform.vcd') as q:
    q.parse_header_fast()
    
    # 分析信号行为
    behavior = q.analyze_behavior('clk', 0, 1000000)
    
    print(f"行为：{behavior['behavior']}")
    # silent: 始终无变化
    # constant: 恒定值
    # toggling: 跳变
    # pulse: 脉冲
```

---

### 功能 3: 脉冲分析

**使用场景：** 分析脉冲宽度、周期、占空比

```python
from tools.vcd_analyze import analyze_pulse

result = analyze_pulse('waveform.vcd', 
                       signal='interrupt',
                       window=(0, 1000000))

print(f"脉冲数量：{result['pulse_count']}")
print(f"最小脉宽：{result['min_width_ps']} ps")
print(f"最大脉宽：{result['max_width_ps']} ps")
print(f"平均脉宽：{result['avg_width_ps']} ps")
print(f"占空比：{result['duty_cycle']:.2%}")
```

**返回数据结构：**
```json
{
  "pulse_count": 10,
  "min_width_ps": 1000,
  "max_width_ps": 5000,
  "avg_width_ps": 2500,
  "periods_ps": [10000, 10000, 10000],
  "duty_cycle": 0.25,
  "first_pulse_ps": 1000,
  "last_pulse_ps": 95000
}
```

---

### 功能 4: 时钟分析

**使用场景：** 分析时钟频率、抖动、稳定性

```python
from tools.vcd_analyze import analyze_clock

result = analyze_clock('waveform.vcd', 
                       signal='clk',
                       window=(0, 1000000))

print(f"频率：{result['frequency_mhz']:.2f} MHz")
print(f"周期：{result['period_ps']:.2f} ps")
print(f"占空比：{result['duty_cycle']:.2%}")
print(f"抖动：{result['jitter_ps']:.2f} ps")
print(f"稳定：{result['stable']}")
```

**返回数据结构：**
```json
{
  "frequency_mhz": 100.5,
  "period_ps": 9950.2,
  "duty_cycle": 0.5,
  "jitter_ps": 50.3,
  "stable": true,
  "edges": [(1000, 'rising'), (5000, 'falling'), ...],
  "edge_count": 200
}
```

---

### 功能 5: 总线分析

**使用场景：** 分析 AXI/APB/AHB总线事务

```python
from tools.vcd_analyze import analyze_bus

result = analyze_bus('waveform.vcd', 
                     signals={
                         'data': 'wdata[31:0]',
                         'valid': 'wvalid',
                         'ready': 'wready'
                     },
                     window=(0, 1000000))

print(f"事务数：{result['transaction_count']}")
print(f"Burst 数：{result['burst_count']}")
print(f"平均 Burst 长度：{result['avg_burst_len']:.2f}")
print(f"总线利用率：{result['utilization']:.2%}")
print(f"停顿次数：{result['stalls']}")
print(f"平均延迟：{result['avg_latency_ps']:.2f} ps")
```

**返回数据结构：**
```json
{
  "transactions": [
    {
      "start_time": 1000,
      "end_time": 5000,
      "transfers": 4,
      "stalls": 1,
      "latency_ps": 4000
    }
  ],
  "transaction_count": 10,
  "burst_count": 5,
  "avg_burst_len": 3.2,
  "utilization": 0.75,
  "stalls": 3,
  "avg_latency_ps": 4500.0
}
```

---

### 功能 6: 状态机分析

**使用场景：** 分析状态机状态转移、检测死循环

```python
from tools.vcd_analyze import analyze_fsm

result = analyze_fsm('waveform.vcd', 
                     state_signals=['state[0]', 'state[1]', 'state[2]'],
                     window=(0, 1000000))

print(f"访问状态：{result['states_visited']}")
print(f"唯一状态数：{result['unique_states']}")
print(f"状态转移数：{len(result['transitions'])}")
print(f"循环检测：{result['loops']}")
print(f"死状态：{result['dead_states']}")
```

**返回数据结构：**
```json
{
  "states_visited": ["000", "001", "010", "100"],
  "state_encoding": {
    "STATE_0": "000",
    "STATE_1": "001",
    "STATE_2": "010",
    "STATE_3": "100"
  },
  "transitions": [
    {"from": "000", "to": "001", "time_ps": 1000},
    {"from": "001", "to": "010", "time_ps": 2000}
  ],
  "loops": [{"states": ["001", "010"], "count": 5}],
  "dead_states": ["100"],
  "unique_states": 4
}
```

---

### 功能 7: AXI4 协议分析

**使用场景：** 分析 AXI4 总线事务、检测协议违规

```python
from tools.vcd_protocol import analyze_axi4

result = analyze_axi4('waveform.vcd', 
                      signals={
                          'awvalid': 'axi_awvalid',
                          'awready': 'axi_awready',
                          'wvalid': 'axi_wvalid',
                          'wready': 'axi_wready',
                          'bvalid': 'axi_bvalid',
                          'bready': 'axi_bready'
                      })

print(f"写事务数：{result['write_transactions']}")
print(f"读事务数：{result['read_transactions']}")
print(f"平均写延迟：{result['avg_write_latency_ps']/1000:.2f} ns")
print(f"违规数：{len(result['violations'])}")

if result['violations']:
    print("⚠️  检测到协议违规:")
    for v in result['violations'][:3]:
        print(f"   {v['channel']}: {v['description']}")
```

---

### 功能 8: APB 协议分析

**使用场景：** 分析 APB 总线事务、检测错误

```python
from tools.vcd_protocol import analyze_apb

result = analyze_apb('waveform.vcd', 
                     signals={
                         'psel': 'apb_psel',
                         'penable': 'apb_penable',
                         'paddr': 'apb_paddr[7:0]',
                         'pwdata': 'apb_pwdata[31:0]',
                         'pwrite': 'apb_pwrite',
                         'pready': 'apb_pready'
                     })

print(f"事务数：{result['transaction_count']}")
print(f"读事务：{result['read_count']}")
print(f"写事务：{result['write_count']}")
print(f"错误数：{result['error_count']}")
print(f"平均延迟：{result['avg_latency_ps']/1000:.2f} ns")
```

---

### 功能 9: 交互式调试（自动追踪根因）

**使用场景：** 给定异常信号，自动追踪依赖找到根因

```python
from tools.interactive_debugger import InteractiveDebugger

debugger = InteractiveDebugger(
    filelist='design.f',
    vcd_file='waveform.vcd'
)

# 自动调试
debugger.run(
    target_signal='transfer_done',
    expected='应该在 t=1000ns 拉高'
)
```

**输出示例：**
```
================================================================================
🔍 交互式调试：transfer_done
================================================================================
📋 预期行为：应该在 t=1000ns 拉高

🚀 开始追踪...

🔍 步骤 1: 分析 transfer_done
   🕒 定位异常窗口：t=0-100000 ps
   📊 查询 RTL 依赖...
   📝 依赖：all_b_received, b_valid
   📈 查询 VCD 行为...
   📝 行为：始终为 0 (恒定信号)
   ⚠️  发现异常：信号始终为 0，但预期应该有变化
   🔗 继续追踪依赖...

  🔍 步骤 2: 分析 all_b_received
     📊 查询 RTL 依赖...
     📝 依赖：b_valid
     📈 查询 VCD 行为...
     📝 行为：始终为 0
     ⚠️  发现异常...

  🔍 步骤 3: 分析 b_valid
     📊 查询 RTL 依赖...
     📝 无依赖（叶信号）
     📈 查询 VCD 行为...
     📝 行为：始终为 0
     ⚠️  发现异常：b_valid 控制逻辑问题

================================================================================
🎯 调试结果
================================================================================

🔴 找到根因：b_valid
   行为：始终为 0
   原因：b_valid 控制逻辑问题

📋 追踪路径：
   1. transfer_done
   2. all_b_received
   3. b_valid

💡 建议：
   1. 检查 b_valid 的驱动逻辑
   2. 查看相关控制信号
   3. 对比 RTL 预期和 VCD 实际
```

---

## 🎯 典型使用场景

### 场景 1: 用户指定时间窗口

```python
# 用户："transfer_done 在 t=1000ns 应该拉高，但没反应"

from tools.vcd_smart import VCDSmartStream

with VCDSmartStream('waveform.vcd') as q:
    q.parse_header_fast()
    
    # 查询问题窗口
    changes = q.query_window('transfer_done', 900000, 1100000)
    
    if not changes or all(v == '0' for t, v in changes):
        print("❌ 信号确实没有拉高")
        
        # 查询依赖信号
        deps = ['all_b_received', 'b_valid']
        for dep in deps:
            dep_changes = q.query_window(dep, 900000, 1100000)
            print(f"{dep}: {len(dep_changes)} 次变化")
```

---

### 场景 2: 用户未指定时间

```python
# 用户："中断信号异常拉高了，怎么回事？"

from tools.vcd_smart import VCDSmartStream

with VCDSmartStream('waveform.vcd') as q:
    q.parse_header_fast()
    
    # 先找异常点
    behavior = q.analyze_behavior('interrupt', 0, None)
    
    if behavior['first_change']:
        t = behavior['first_change']
        print(f"✅ 首次异常：t={t} ps")
        
        # 查询异常窗口
        window = (max(0, t - 100000), t + 100000)
        changes = q.query_window('interrupt', window[0], window[1])
        print(f"窗口内行为：{changes}")
```

---

### 场景 3: 时钟质量分析

```python
# 用户："这个时钟信号稳定吗？"

from tools.vcd_analyze import analyze_clock

result = analyze_clock('waveform.vcd', 'clk')

if result['stable']:
    print(f"✅ 时钟稳定：{result['frequency_mhz']:.2f} MHz")
else:
    print(f"⚠️  时钟不稳定！")
    print(f"   频率：{result['frequency_mhz']:.2f} MHz")
    print(f"   抖动：{result['jitter_ps']:.2f} ps")
    print(f"   占空比：{result['duty_cycle']:.2%}")
```

---

### 场景 4: 总线性能分析

```python
# 用户："AXI 总线性能怎么样？"

from tools.vcd_analyze import analyze_bus

result = analyze_bus('waveform.vcd', {
    'data': 'wdata[31:0]',
    'valid': 'wvalid',
    'ready': 'wready'
})

print(f"📊 总线性能报告:")
print(f"   事务数：{result['transaction_count']}")
print(f"   Burst 数：{result['burst_count']}")
print(f"   利用率：{result['utilization']:.2%}")
print(f"   平均延迟：{result['avg_latency_ps']/1000:.2f} ns")

if result['stalls'] > 0:
    print(f"⚠️  检测到 {result['stalls']} 次停顿")
```

---

## 📊 性能参考

| 功能 | 数据量 | 预期耗时 |
|------|--------|---------|
| 时间窗口查询 | 100ns 窗口 | **0.2ms** |
| 时间窗口查询 | 1μs 窗口 | **0.4ms** |
| 时间窗口查询 | 10μs窗口 | **2.0ms** |
| 脉冲分析 | 100 个脉冲 | **1-5ms** |
| 时钟分析 | 1000 个周期 | **5-10ms** |
| 总线分析 | 100 次事务 | **10-50ms** |
| 状态机分析 | 复杂状态机 | **50-100ms** |
| 全时间扫描 | 512MB VCD | **28s** (仅第一次) |

---

## 🔧 故障排查

### 问题 1: UnicodeEncodeError (Windows)

**现象：**
```
UnicodeEncodeError: 'gbk' codec can't encode character
```

**解决：** 工具已自动适配，确保 Python 3.10+

---

### 问题 2: 信号未找到

**现象：**
```
❌ 未找到信号 'transfer_done'
```

**解决：**
```python
# 检查信号名是否正确
with VCDSmartStream('waveform.vcd') as q:
    q.parse_header_fast()
    print("可用信号:", list(q.signals.keys())[:10])
```

---

### 问题 3: 查询太慢

**现象：** 查询耗时超过 1 秒

**解决：**
```python
# 使用更小的时间窗口
changes = q.query_window('signal', 0, 100000)  # 而不是 0, None
```

---

## 📚 API 参考

### VCDSmartStream 类

```python
class VCDSmartStream:
    def parse_header_fast() -> bool
    def query_window(signal, start_time, end_time, max_changes) -> List[Tuple]
    def analyze_behavior(signal, start_time, end_time) -> Dict
```

### 分析函数

```python
def analyze_pulse(vcd_file, signal, window) -> Dict
def analyze_clock(vcd_file, signal, window) -> Dict
def analyze_bus(vcd_file, signals, window) -> Dict
def analyze_fsm(vcd_file, state_signals, window) -> Dict
```

---

## 🎯 最佳实践

1. **优先使用时间窗口查询** - 最快（0.2-2ms）
2. **用户未指定时间时先定位** - 全时间扫描（28s，仅一次）
3. **迭代追踪时逐步缩小窗口** - 每次提前 100ns
4. **复杂分析用专用函数** - analyze_clock/analyze_bus
5. **自动调试用 InteractiveDebugger** - 自动追踪依赖

---

## 🌟 示例项目

查看完整示例：
- `test/` - 测试用例
- `tools/vcd_smart.py --test` - 运行测试

---

**🍃 木叶村出品，必属精品！**

**有问题？提交 Issue: https://github.com/lansongfu/rtl-debugger/issues**
