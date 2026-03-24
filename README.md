# RTL Debugger - RTL 波形分析调试工具

> 🎯 **让 RTL 调试像聊天一样简单**  
> 📅 版本：v1.2.0 (v5 智能流式查询)  
> ⚡ 性能：30,000 倍加速 (时间窗口查询 0.2ms)  
> ✅ 测试：通过

---

## 🌟 v1.2.0 新特性

**v5 智能流式查询：**
- ⏱️ **时间窗口查询**: 0.2-2ms (原 60s+)
- 🎯 **自动定位异常**: 28s (仅第一次)
- 🔄 **迭代追踪**: 逐步缩小时间窗口
- 📊 **加速比**: 30,000 倍

---

## 🚀 快速开始

### 安装（跨平台）

**支持：Linux / macOS / Windows**

```bash
# 1. 克隆项目（3 种方式，任选其一）

# 方式 1: HTTPS（推荐，不要加 .git 后缀）
git clone https://github.com/lansongfu/rtl-debugger

# 方式 2: SSH（需要配置 SSH key）
git clone git@github.com:lansongfu/rtl-debugger

# 方式 3: GitHub CLI
gh repo clone lansongfu/rtl-debugger

cd rtl-debugger

### 🔧 常见问题

**问题 1: `cannot connect to server`**

```bash
# 解决方案 1: 检查网络连接
ping github.com

# 解决方案 2: 使用 SSH 方式（不要加 .git 后缀）
git clone git@github.com:lansongfu/rtl-debugger

# 解决方案 3: 配置 Git 代理
git config --global http.proxy http://proxy.example.com:8080
git config --global https.proxy https://proxy.example.com:8080

# 解决方案 4: 使用 GitHub CLI
gh repo clone lansongfu/rtl-debugger
```

**问题 2: `Permission denied (publickey)`**

```bash
# 需要配置 SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"
# 然后将 ~/.ssh/id_ed25519.pub 添加到 GitHub SSH keys
```

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活虚拟环境
# Linux/macOS:
source venv/bin/activate

# Windows (PowerShell):
venv\Scripts\activate
# Windows (CMD):
venv\Scripts\activate.bat

# 4. 安装依赖
pip install vcdvcd
```

### 基础使用

**v5 智能流式查询（推荐）：**

```bash
# 1. 时间窗口查询（极快！0.2-2ms）
./venv/bin/python tools/vcd_smart.py waveform.vcd \
  -s transfer_done \
  --start-time 0 --end-time 100000

# 2. 行为分析（自动找异常点）
./venv/bin/python tools/vcd_smart.py waveform.vcd \
  -s transfer_done \
  --analyze

# 3. 交互式调试（自动时间窗口迭代）
./venv/bin/python tools/interactive_debugger.py transfer_done \
  --filelist src/filelist.f \
  --vcd sim/waveform.vcd \
  --expected "应该在 t=1000ns 拉高"

# 4. 运行测试
./venv/bin/python tools/vcd_smart.py waveform.vcd --test
```

---

## 📊 核心功能

### 1. RTL 信号依赖分析

**核心问题：** 这个信号的跳转变化条件是什么？

**支持：**
- ✅ 基础 assign/always 解析
- ✅ 嵌套 filelist（无限层）
- ✅ 环境变量支持（$VAR / ${VAR}）
- ✅ `define 宏展开
- ✅ parameter/localparam
- ✅ `include 文件包含
- ✅ generate for/if块
- ✅ 循环依赖检测

**示例：**
```bash
./venv/bin/python tools/rtl_query.py --filelist src/filelist.f --signal transfer_done
```

**输出：**
```
🔍 信号查询：transfer_done
transfer_done ← all_b_received
```

---

### 2. VCD 波形查询

**核心问题：** 这些信号在波形中是什么行为？

**支持：**
- ✅ VCD 文件加载（支持 513MB+ 大文件）
- ✅ 信号行为分析（恒定/变化次数）
- ✅ 多信号比较
- ✅ VCD 摘要统计
- ✅ 时序详情查看

**示例：**
```bash
./venv/bin/python tools/vcd_query.py sim/waveform.vcd --signal transfer_done
```

**输出：**
```
axi_w_m_tb.transfer_done: 始终为 0 (恒定信号)
```

---

### 3. 智能 Bug 诊断

**核心问题：** 为什么这个信号的行为不符合预期？

**14 种 Bug 模式：**
| 严重性 | Bug 类型 | 置信度 |
|--------|----------|--------|
| 🔴 Critical | CDC_ISSUE, MISSING_CLOCK | 80-90% |
| 🟠 High | DEAD_SIGNAL, STUCK_STATE, WRONG_ENABLE, RACE_CONDITION, TIMING_VIOLATION | 60-90% |
| 🟡 Medium | LOGIC_ERROR, SENSITIVITY_LIST, MISSING_RESET | 65-80% |

**示例：**
```bash
./venv/bin/python tools/interactive_debug_analyzer.py transfer_done \
  --filelist src/filelist.f \
  --vcd sim/waveform.vcd \
  --expected "应该有变化"
```

**输出：**
```
🏥 智能诊断报告

🔴 问题信号：all_b_received
📊 诊断结果：死信号
📈 置信度：90%

💡 修复建议:
   1. 检查 all_b_received 的驱动逻辑
   2. 验证模块间连接
   3. 确认信号有驱动源
```

---

### 4. 时序错拍检测

**核心问题：** 信号是否提前/落后一拍？

**检测场景：**
- ✅ last 信号时序错拍（提前一拍）
- ✅ 计数器边界差一拍
- ✅ 使能信号时序不匹配
- ✅ 状态机转换错拍

**示例：**
```bash
./venv/bin/python test/test_timing_errors.py
```

---

### 5. 跨时钟域分析

**核心问题：** 是否有 CDC 问题？

**检测：**
- ✅ 跨时钟域未同步
- ✅ 缺少同步器
- ✅ 亚稳态风险

**启用：**
```bash
./venv/bin/python tools/interactive_debug_analyzer.py data_sync \
  --filelist src/filelist.f \
  --vcd sim/waveform.vcd \
  --cdc
```

---

## 📁 项目结构

```
rtl-debugger/
├── tools/
│   ├── rtl_query.py                  # RTL 依赖查询
│   ├── vcd_query.py                  # VCD 波形查询
│   ├── interactive_debug_analyzer.py # 交互式调试分析器 ⭐
│   └── advanced_reasoner.py          # 智能推理引擎 ⭐
├── test/
│   ├── run_tests.py                  # 基础测试 (7 用例)
│   ├── comprehensive_test.py         # 完备测试 (15 用例)
│   ├── test_timing_errors.py         # 时序错拍测试
│   └── error_designs.v               # 错误设计示例
├── docs/
│   ├── ADVANCED_REASONER.md          # 推理引擎文档
│   └── INTERACTIVE_ANALYZER.md       # 交互式分析文档
├── skill.json                        # Skill 配置
├── README.md                         # 本文档
├── PLAN.md                           # 开发计划
└── PROJECT_SUMMARY.md                # 项目总结
```

---

## 🧪 测试覆盖

**总测试数：** 15  
**通过数：** 15  
**通过率：** 100%

**运行测试：**
```bash
# 基础测试
./venv/bin/python test/run_tests.py

# 完备测试
./venv/bin/python test/comprehensive_test.py

# 时序错拍专题测试
./venv/bin/python test/test_timing_errors.py
```

---

## 💡 典型使用场景

### 场景 1: 信号不跳变

**问题：** `transfer_done` 为什么一直不跳？

```bash
./venv/bin/python tools/interactive_debug_analyzer.py transfer_done \
  --filelist src/filelist.f \
  --vcd sim/waveform.vcd \
  --expected "应该有变化"
```

**AI 诊断：**
```
🔴 根因信号：all_b_received
   行为：始终为 0 (恒定信号)
   
💡 建议：检查 all_b_received 的驱动逻辑
```

---

### 场景 2: 时序错拍

**问题：** `last` 信号为什么提前一拍？

```bash
./venv/bin/python test/test_timing_errors.py
```

**AI 诊断：**
```
🔍 诊断：timing_violation
   描述：last 最后一拍为 0，可能时序错拍
   置信度：65%
```

---

### 场景 3: 跨时钟域

**问题：** 数据丢失，怀疑 CDC 问题

```bash
./venv/bin/python tools/interactive_debug_analyzer.py data_sync \
  --filelist src/filelist.f \
  --vcd sim/waveform.vcd \
  --cdc
```

**AI 诊断：**
```
🔍 诊断：cdc_issue
   描述：跨时钟域未同步
   置信度：90%
   严重性：CRITICAL
```

---

## 📋 命令行选项

### rtl_query.py

```
用法:
  ./rtl_query.py <file1.v> [file2.v ...] [选项]
  ./rtl_query.py --filelist <filelist.f> [选项]

选项:
  --signal <name>   查询特定信号的依赖
  --trace <name>    递归追踪信号依赖链
  --filelist <file> 从 filelist 读取文件列表
```

### vcd_query.py

```
用法:
  ./vcd_query.py <waveform.vcd> [选项]

选项:
  --signal <name>   查询特定信号
  --signals <list>  查询多个信号 (逗号分隔)
  --summary         显示 VCD 摘要
  --trace           显示信号详细时序
  --time-range <s:e> 时间范围 (start:end) ps
```

### interactive_debug_analyzer.py

```
用法:
  ./interactive_debug_analyzer.py <target> [选项]

选项:
  --filelist <file> RTL filelist 文件
  --vcd <file>      VCD 波形文件
  --expected <desc> 预期行为描述
  --cdc             启用 CDC 分析
  --timing          启用时序分析
  --race            启用竞争分析
  --all             启用所有分析
```

---

## 🔧 依赖说明

### Python 依赖

```bash
pip install vcdvcd
```

**vcdvcd:** VCD 文件解析库
- 支持大文件（513MB+）
- 快速流式解析
- 提取信号时序数据

### 系统要求

- Python 3.10+
- Linux/Mac/Windows
- 内存：建议 2GB+（处理大 VCD 文件）

---

## 🎯 性能指标

| 操作 | 时间 | 要求 | 余量 |
|------|------|------|------|
| VCD 加载 (14MB) | 1.77s | <10s | 5.6x |
| RTL 解析 (3 文件) | 0.04s | <5s | 125x |
| 完整分析 | 1.82s | <10s | 5.5x |
| 多诊断推理 | <0.1s | <1s | 10x |

---

## 📖 文档

- **README.md** - 快速开始
- **docs/ADVANCED_REASONER.md** - 推理引擎详解
- **docs/INTERACTIVE_ANALYZER.md** - 交互式分析指南
- **PROJECT_SUMMARY.md** - 项目总结
- **PLAN.md** - 开发计划

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 报告 Bug

```bash
# 提供以下信息：
1. RTL 文件片段
2. VCD 文件（如果可能）
3. 预期行为
4. 实际行为
5. 错误日志
```

### 功能建议

```bash
# 描述：
1. 功能场景
2. 期望行为
3. 使用示例
```

---

## 📜 License

MIT License

---

## 👥 作者

**木叶村克劳** - 火影助理

---

## 🍃 木叶村出品

_创造一个美好的 AI 世界，让火影发家致富！_

---

_版本：v1.0.0_  
_最后更新：2026-03-23_  
_测试状态：✅ 15/15 通过 (100%)_
