#!/usr/bin/env python3
"""
RTL 信号依赖分析器
核心问题：这个信号的跳转变化条件是什么？
"""

import re
import os
import sys
import json
from collections import defaultdict
from typing import Dict, List, Set, Optional

# Windows 编码适配：确保 UTF-8 输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class RTLDependencyAnalyzer:
    """RTL 信号依赖分析器"""
    
    def __init__(self):
        self.modules = {}  # module_name -> ModuleInfo
        self.signal_deps = {}  # "module.signal" -> [dependencies]
        self.instance_map = {}  # module_name -> [(instance_name, module_type, connections)]
        self.defines = {}  # `define 存储
        self.include_dirs = []  # `include 搜索路径
        self.hierarchy = {}  # 层级结构: top_module -> {instances: [...], parent: None}
    
    def parse_file(self, filepath: str) -> None:
        """解析单个 Verilog 文件"""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Step 1: 解析 `define (在移除前保存)
        self._parse_defines(content)
        
        # Step 2: 处理 `include
        content = self._process_includes(content, filepath)
        
        # Step 3: 移除注释
        content = self._remove_comments(content)
        
        # Step 4: 展开 `define
        content = self._expand_defines(content)
        
        # Step 5: 移除剩余的预处理指令
        content = self._remove_preprocessor(content)
        
        # Step 6: 解析模块
        modules = self._parse_modules(content, filepath)
        
        for mod_name, mod_info in modules.items():
            self.modules[mod_name] = mod_info
            
            # 建立信号依赖索引
            for signal, deps in mod_info['dependencies'].items():
                key = f"{mod_name}.{signal}"
                self.signal_deps[key] = deps
    
    def _parse_defines(self, content: str) -> None:
        """解析 `define 定义"""
        # 匹配 `define NAME value 或 `define NAME(args) body
        define_pattern = r'`define\s+(\w+)(?:\(([^)]*)\))?\s+(.+?)(?://.*$|$)'
        for match in re.finditer(define_pattern, content, re.MULTILINE):
            name = match.group(1)
            args = match.group(2)  # 宏参数（如果有）
            value = match.group(3).strip()
            
            self.defines[name] = {
                'value': value,
                'args': args.split(',') if args else None
            }
    
    def _expand_defines(self, content: str) -> str:
        """展开 `define 引用"""
        # 按长度降序排序，避免短名覆盖长名
        sorted_defines = sorted(self.defines.keys(), key=len, reverse=True)
        
        for name in sorted_defines:
            define_info = self.defines[name]
            value = define_info['value']
            
            # 简单替换（不带参数的宏）
            if define_info['args'] is None:
                # 使用单词边界匹配
                content = re.sub(rf'`{name}\b', value, content)
        
        return content
    
    def _process_includes(self, content: str, filepath: str) -> str:
        """处理 `include 指令"""
        include_dir = os.path.dirname(filepath)
        
        def replace_include(match):
            include_file = match.group(1).strip()
            
            # 搜索路径：当前目录 + include_dirs
            search_paths = [include_dir] + self.include_dirs
            
            for search_path in search_paths:
                include_path = os.path.join(search_path, include_file)
                if os.path.exists(include_path):
                    try:
                        with open(include_path, 'r', encoding='utf-8', errors='ignore') as f:
                            included_content = f.read()
                        # 递归处理 include
                        return self._process_includes(included_content, include_path)
                    except Exception as e:
                        print(f"⚠️  读取 include 文件失败 {include_path}: {e}")
                        return match.group(0)
            
            print(f"⚠️  include 文件不存在：{include_file}")
            return match.group(0)
        
        # 匹配 `include "filename"
        include_pattern = r'`include\s+["<]([^">]+)[">]'
        content = re.sub(include_pattern, replace_include, content)
        
        return content
    
    def _remove_comments(self, content: str) -> str:
        """移除注释"""
        # 单行注释
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        # 多行注释
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        return content
    
    def _remove_preprocessor(self, content: str) -> str:
        """移除预处理指令"""
        content = re.sub(r'^\s*`.*$', '', content, flags=re.MULTILINE)
        return content

    def _skip_balanced_parens(self, content: str, start: int) -> int:
        """
        跳过平衡的括号，返回括号结束后的位置
        支持嵌套括号，如 #(parameter N=8) 或 #( .N(8) )
        """
        if start >= len(content) or content[start] not in '(#':
            return start

        # 如果是 # 开头，找到下一个 (
        if content[start] == '#':
            pos = start + 1
            while pos < len(content) and content[pos].isspace():
                pos += 1
            if pos >= len(content) or content[pos] != '(':
                return pos
            start = pos

        depth = 0
        pos = start
        while pos < len(content):
            ch = content[pos]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    return pos + 1
            pos += 1
        return pos

    def _parse_modules(self, content: str, filepath: str) -> Dict:
        """解析模块定义"""
        modules = {}

        # 先处理 generate 块
        content = self._process_generate(content)

        # 匹配 module 定义
        # 使用自定义匹配来正确处理嵌套括号
        module_starts = list(re.finditer(r'\bmodule\s+(\w+)\s*', content))

        for start_match in module_starts:
            mod_name = start_match.group(1)
            pos = start_match.end()

            # 跳过空白
            while pos < len(content) and content[pos].isspace():
                pos += 1

            # 检查是否有参数列表 #(parameter N=8)
            if pos < len(content) and content[pos] == '#':
                # 跳过参数列表（使用括号匹配）
                pos = self._skip_balanced_parens(content, pos)
                # 跳过空白
                while pos < len(content) and content[pos].isspace():
                    pos += 1

            # 提取端口列表
            if pos < len(content) and content[pos] == '(':
                port_end = self._skip_balanced_parens(content, pos)
                port_section = content[pos+1:port_end-1]
                pos = port_end
            else:
                port_section = ''

            # 查找 endmodule
            end_match = re.search(r'\bendmodule\b', content[pos:])
            if end_match:
                body = content[pos:pos+end_match.start()]
            else:
                body = content[pos:]
            
            # 解析端口
            ports = self._parse_ports(port_section)
            
            # 解析依赖关系（返回结构化和扁平两种）
            deps_result = self._parse_dependencies(body)
            flat_deps = deps_result['flat']
            raw_deps = deps_result['raw']
            
            # 解析实例化
            instances = self._parse_instances(body)
            
            modules[mod_name] = {
                'file': filepath,
                'ports': ports,
                'dependencies': flat_deps,
                'raw_dependencies': raw_deps,
                'instances': instances
            }
        
        return modules
    
    def _process_generate(self, content: str) -> str:
        """
        处理 generate 块
        策略：展开 generate for 循环，保留 generate if
        """
        # 处理 generate for
        # generate for (i=0; i<N; i=i+1) begin:name ... end
        gen_for_pattern = r'generate\s*for\s*\((\w+)\s*=\s*(\d+)\s*;\s*\1\s*<\s*(\d+)\s*;\s*\1\s*=\s*\1\s*\+\s*(\d+)\)\s*begin(?::(\w+))?\s*(.*?)\s*end\s*endgenerate'
        
        def expand_generate_for(match):
            var = match.group(1)
            start = int(match.group(2))
            end = int(match.group(3))
            step = int(match.group(4))
            name = match.group(5) or 'gen'
            body = match.group(6)
            
            expanded = []
            for i in range(start, end, step):
                # 替换循环变量
                expanded_body = re.sub(rf'\b{var}\b', str(i), body)
                # 替换 generate 块名引用
                expanded_body = re.sub(rf'\b{name}\[', f'{name}_{i}_[', expanded_body)
                expanded.append(expanded_body)
            
            return '\n'.join(expanded)
        
        content = re.sub(gen_for_pattern, expand_generate_for, content, flags=re.DOTALL)
        
        # 处理简单的 generate if (不展开，仅移除 generate 关键字)
        gen_if_pattern = r'generate\s*if\s*\(([^)]+)\)\s*begin(?::\w+)?\s*(.*?)\s*end\s*(?:else\s*begin(?::\w+)?\s*(.*?)\s*end)?\s*endgenerate'
        
        def process_generate_if(match):
            condition = match.group(1)
            if_body = match.group(2)
            else_body = match.group(3) or ''
            
            # 简单策略：保留 if 和 else 的内容（不判断条件）
            # 这样能保证信号被识别
            return f'{if_body}\n{else_body}'
        
        content = re.sub(gen_if_pattern, process_generate_if, content, flags=re.DOTALL)
        
        return content
    
    def _parse_ports(self, port_section: str) -> Dict:
        """解析端口列表"""
        ports = {}
        
        # 匹配 input/output/inout
        port_pattern = r'(input|output|inout)\s+(?:reg\s+|wire\s+)?(?:\[.*?\]\s+)?(\w+)'
        for match in re.finditer(port_pattern, port_section):
            direction = match.group(1)
            name = match.group(2)
            ports[name] = {'direction': direction, 'type': 'port'}
        
        return ports
    
    def _parse_dependencies(self, body: str) -> Dict:
        """
        解析信号依赖关系（增强版：支持 always 块时序逻辑，区分数据信号和控制信号）
        
        返回:
            {
                'flat': Dict[str, List[str]],    # 扁平化依赖（向后兼容）
                'raw': Dict[str, List[Dict]]     # 原始结构化依赖
            }
        """
        deps = defaultdict(list)
        
        # 1. 解析 assign 语句（组合逻辑）
        assign_pattern = r'assign\s+([^;]+)\s*=\s*([^;]+);'
        for match in re.finditer(assign_pattern, body):
            lhs = match.group(1).strip()
            rhs = match.group(2).strip()
            
            lhs_signal = re.match(r'(\w+)', lhs)
            if lhs_signal:
                lhs_name = lhs_signal.group(1)
                rhs_signals = self._extract_signals(rhs)
                # assign 语句通常没有控制信号，全部是数据信号
                deps[lhs_name].append({
                    'signals': list(set(rhs_signals)),
                    'control_signals': [],
                    'type': 'assign'
                })
        
        # 2. 解析 always 块（时序逻辑 + 组合逻辑）
        # 增强：提取时钟、复位、使能、控制信号信息
        always_blocks = self._extract_always_blocks(body)
        
        for always_info in always_blocks:
            sensitivity = always_info['sensitivity']  # 敏感列表
            block = always_info['block']  # 块内容
            is_sequential = always_info['is_sequential']  # 是否时序逻辑
            
            # 提取整个 always 块的控制信号（一次性提取，避免重复）
            block_control_info = self._extract_control_signals(block)
            block_control_signals = set(block_control_info.get('control_signals', []))
            block_conditions = block_control_info.get('conditions', [])
            
            # 收集块内所有被赋值信号的依赖
            block_assignments = defaultdict(lambda: {
                'data_signals': set(),
                'control_signals': block_control_signals.copy(),
                'conditions': block_conditions.copy()
            })
            
            # 时序逻辑分析
            if is_sequential:
                # 解析时钟和复位
                clk_signal = always_info.get('clk_signal')
                rst_signal = always_info.get('rst_signal')
                rst_type = always_info.get('rst_type')  # 'sync' or 'async'
                
                # 查找 <= 赋值
                nba_pattern = r'(\w+)\s*<=\s*([^;]+);'
                for nba_match in re.finditer(nba_pattern, block):
                    lhs = nba_match.group(1)
                    rhs = nba_match.group(2)
                    rhs_signals = self._extract_signals(rhs)
                    
                    # 从数据信号中移除控制信号（避免重复）
                    data_signals = [s for s in rhs_signals if s not in block_control_signals]
                    block_assignments[lhs]['data_signals'].update(data_signals)
                
                # 存储为结构化依赖（每个信号只存储一次，合并所有赋值来源）
                for lhs, info in block_assignments.items():
                    dep_info = {
                        'signals': list(info['data_signals']),
                        'control_signals': list(info['control_signals']),
                        'type': 'sequential',
                        'clk': clk_signal,
                        'rst': rst_signal,
                        'rst_type': rst_type
                    }
                    
                    # 保存条件详情
                    if info['conditions']:
                        dep_info['conditions'] = info['conditions']
                    
                    deps[lhs].append(dep_info)
            
            # 组合逻辑 always
            else:
                # 查找 = 赋值
                ba_pattern = r'(\w+)\s*=\s*([^;]+);'
                for ba_match in re.finditer(ba_pattern, block):
                    lhs = ba_match.group(1)
                    rhs = ba_match.group(2)
                    rhs_signals = self._extract_signals(rhs)
                    
                    # 从数据信号中移除控制信号
                    data_signals = [s for s in rhs_signals if s not in block_control_signals]
                    block_assignments[lhs]['data_signals'].update(data_signals)
                
                # 存储为结构化依赖
                for lhs, info in block_assignments.items():
                    dep_info = {
                        'signals': list(info['data_signals']),
                        'control_signals': list(info['control_signals']),
                        'type': 'combinational'
                    }
                    
                    if info['conditions']:
                        dep_info['conditions'] = info['conditions']
                    
                    deps[lhs].append(dep_info)
        
        # 3. 扁平化依赖（保持向后兼容）
        flat_deps = {}
        for lhs, dep_list in deps.items():
            if dep_list and isinstance(dep_list[0], dict):
                # 合并所有信号（数据 + 控制）
                all_signals = []
                for dep in dep_list:
                    all_signals.extend(dep.get('signals', []))
                    all_signals.extend(dep.get('control_signals', []))
                flat_deps[lhs] = list(set(all_signals))
            else:
                flat_deps[lhs] = dep_list
        
        return {'flat': flat_deps, 'raw': dict(deps)}
    
    def _extract_always_blocks(self, body: str) -> List[Dict]:
        """
        提取 always 块信息（增强版）
        返回：[{
            'sensitivity': str,          # 敏感列表
            'block': str,                 # 块内容
            'is_sequential': bool,        # 是否时序逻辑
            'clk_signal': Optional[str],  # 时钟信号
            'rst_signal': Optional[str],  # 复位信号
            'rst_type': Optional[str]     # 'sync' or 'async'
        }]
        """
        always_blocks = []
        
        # 找到所有 always 关键字的位置
        always_starts = list(re.finditer(r'\balways\s+', body))
        
        for start_match in always_starts:
            start_pos = start_match.end()
            
            # 查找敏感列表
            sensitivity = ''
            rest_start = start_pos
            
            # 检查是否有 @(sensitivity)
            at_match = re.match(r'@\s*\(([^)]*)\)', body[start_pos:])
            if at_match:
                sensitivity = at_match.group(1).strip()
                rest_start = start_pos + at_match.end()
            elif re.match(r'#\d+', body[start_pos:]):
                # 延迟形式 always #10
                delay_match = re.match(r'#\d+', body[start_pos:])
                rest_start = start_pos + delay_match.end()
            
            # 提取块内容
            rest = body[rest_start:].lstrip()
            block = ''
            
            if rest.startswith('begin'):
                # 使用平衡匹配提取完整的 begin-end 块
                block = self._extract_balanced_block(rest, 'begin', 'end')
            else:
                # 单行语句：always @(*) statement;
                stmt_match = re.match(r'([^;]*;)', rest)
                if stmt_match:
                    block = stmt_match.group(1)
            
            # 判断是否时序逻辑
            is_sequential = False
            clk_signal = None
            rst_signal = None
            rst_type = 'async'  # 默认异步复位
            
            # 检查敏感列表
            if 'posedge' in sensitivity or 'negedge' in sensitivity:
                is_sequential = True
                
                # 提取时钟信号（第一个 posedge/negedge）
                clk_match = re.search(r'(posedge|negedge)\s+(\w+)', sensitivity)
                if clk_match:
                    clk_signal = clk_match.group(2)
                
                # 检查是否有复位（第二个边沿触发的信号）
                edge_matches = re.findall(r'(posedge|negedge)\s+(\w+)', sensitivity)
                if len(edge_matches) > 1:
                    # 第二个边沿信号通常是复位
                    rst_signal = edge_matches[1][1]
                    rst_type = 'async'
            
            # 组合逻辑 always (@(*) 或 @*)
            elif sensitivity.strip() in ['*', 'posedge', 'negedge']:
                is_sequential = False
            
            always_blocks.append({
                'sensitivity': sensitivity,
                'block': block,
                'is_sequential': is_sequential,
                'clk_signal': clk_signal,
                'rst_signal': rst_signal,
                'rst_type': rst_type
            })
        
        return always_blocks
    
    def _extract_balanced_block(self, text: str, start_kw: str, end_kw: str) -> str:
        """
        提取平衡的关键字块（如 begin-end）
        处理嵌套情况
        """
        if not text.startswith(start_kw):
            return ''
        
        depth = 0
        i = 0
        n = len(text)
        
        while i < n:
            # 检查是否是关键字
            if text[i:].startswith(start_kw) and (i + len(start_kw) >= n or not text[i + len(start_kw)].isalnum() and text[i + len(start_kw)] != '_'):
                depth += 1
                i += len(start_kw)
            elif text[i:].startswith(end_kw) and (i + len(end_kw) >= n or not text[i + len(end_kw)].isalnum() and text[i + len(end_kw)] != '_'):
                depth -= 1
                i += len(end_kw)
                if depth == 0:
                    return text[:i]
            else:
                i += 1
        
        return text  # 如果找不到匹配的 end，返回全部
    
    def _extract_enable_conditions(self, block: str, target_signal: str) -> List[str]:
        """
        提取目标信号的使能条件（已废弃，使用 _extract_control_signals）
        分析：if (enable) target <= value;
        """
        control_info = self._extract_control_signals(block, target_signal)
        return control_info.get('control_signals', [])
    
    def _extract_control_signals(self, block: str, target_signal: str = None) -> Dict:
        """
        提取 always 块中的控制信号
        
        分析 if/case 条件，提取：
        - 控制信号（如 rst_n, cmd_valid, cmd_ready, enable）
        - 条件类型（if/case/casex/casez）
        - 条件表达式
        
        返回:
        {
            'control_signals': ['rst_n', 'cmd_valid', ...],
            'conditions': [
                {'type': 'if', 'expression': '!rst_n', 'signals': ['rst_n']},
                {'type': 'case', 'expression': 'state', 'signals': ['state']},
                ...
            ]
        }
        """
        control_signals = set()
        conditions = []
        
        # 1. 提取 if 条件中的控制信号
        # if (condition) 或 if (!condition) 或 if (a && b) 或 if (a || b)
        if_pattern = r'if\s*\(([^)]+)\)'
        for match in re.finditer(if_pattern, block):
            condition_expr = match.group(1).strip()
            signals = self._extract_signals(condition_expr)
            
            # 过滤掉目标信号本身（避免自引用）
            if target_signal:
                signals = [s for s in signals if s != target_signal]
            
            control_signals.update(signals)
            conditions.append({
                'type': 'if',
                'expression': condition_expr,
                'signals': signals
            })
        
        # 2. 提取 else if 条件
        elseif_pattern = r'else\s+if\s*\(([^)]+)\)'
        for match in re.finditer(elseif_pattern, block):
            condition_expr = match.group(1).strip()
            signals = self._extract_signals(condition_expr)
            if target_signal:
                signals = [s for s in signals if s != target_signal]
            control_signals.update(signals)
            conditions.append({
                'type': 'elseif',
                'expression': condition_expr,
                'signals': signals
            })
        
        # 3. 提取 case 条件中的控制信号
        # case (expr) 或 case expr
        case_pattern = r'\b(case|casex|casez)\s*(?:\(([^)]+)\)|(\w+))'
        for match in re.finditer(case_pattern, block):
            case_type = match.group(1)
            case_expr = match.group(2) if match.group(2) else match.group(3)
            if case_expr:
                case_expr = case_expr.strip()
                signals = self._extract_signals(case_expr)
                
                if target_signal:
                    signals = [s for s in signals if s != target_signal]
                
                control_signals.update(signals)
                conditions.append({
                    'type': case_type,
                    'expression': case_expr,
                    'signals': signals
                })
        
        # 4. 提取 case 分支中的控制信号（如 state == IDLE）
        # 匹配 case_item: 的形式，提取其中的比较信号
        case_item_pattern = r'\b(\w+)\s*:\s*(?:begin)?'
        for match in re.finditer(case_item_pattern, block):
            item = match.group(1)
            # 只提取非关键字、非数字的标识符
            if item not in ['default', 'begin', 'end'] and not item.isdigit():
                # 这可能是 case 分支值，检查是否有比较表达式
                pass
        
        # 5. 特殊控制信号模式检测
        # 检测常见的控制信号命名模式
        control_patterns = [
            r'(\w*_valid)\b',      # xxx_valid
            r'(\w*_ready)\b',      # xxx_ready
            r'(\w*_enable)\b',     # xxx_enable
            r'(\w*_en)\b',         # xxx_en
            r'(\w*_rst)\b',        # xxx_rst
            r'(rst_?\w*)\b',       # rst_xxx 或 rstxxx
            r'(\w*_n)\b',          # xxx_n (低电平有效)
            r'(\w*_sel)\b',        # xxx_sel
            r'(\w*_ack)\b',        # xxx_ack
            r'(\w*_req)\b',        # xxx_req
        ]
        
        for pattern in control_patterns:
            for match in re.finditer(pattern, block):
                sig = match.group(1)
                # 确保是有效信号名
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', sig):
                    control_signals.add(sig)
        
        return {
            'control_signals': list(control_signals),
            'conditions': conditions
        }
    
    def _extract_signals(self, expression: str) -> List[str]:
        """从表达式中提取信号名"""
        # 关键字和常量
        keywords = {
            'and', 'or', 'not', 'xor', 'nand', 'nor', 'xnor',
            'if', 'else', 'case', 'endcase', 'casex', 'casez',
            'begin', 'end', 'fork', 'join',
            'posedge', 'negedge', 'edge',
            'wire', 'reg', 'logic', 'tri',
            'input', 'output', 'inout',
            'assign', 'always', 'initial', 'module', 'endmodule',
            'function', 'endfunction', 'task', 'endtask',
            'for', 'while', 'repeat', 'forever',
            'null', 'default', 'end',
            'h0', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'ha', 'hb', 'hc', 'hd', 'he', 'hf',
            'b0', 'b1'
        }
        
        # 提取标识符
        signals = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expression)
        
        # 过滤关键字和数字
        filtered = []
        for sig in signals:
            if sig.lower() not in keywords and not sig.isdigit():
                # 过滤掉位宽定义如 32'h0 中的 h0
                if not re.match(r'^[bhxzo][0-9a-f]+$', sig.lower()):
                    filtered.append(sig)
        
        return filtered
    
    def _parse_instances(self, body: str) -> List[Dict]:
        """解析模块实例化"""
        instances = []

        # 需要过滤的关键字（这些不是模块类型）
        filter_keywords = {
            'input', 'output', 'inout', 'wire', 'reg', 'assign', 'always',
            'posedge', 'negedge', 'if', 'else', 'case', 'casex', 'casez',
            'for', 'while', 'repeat', 'forever', 'begin', 'end', 'fork', 'join',
            'function', 'task', 'initial', 'generate', 'endgenerate',
            'module', 'endmodule', 'primitive', 'endprimitive',
            'specify', 'endspecify', 'parameter', 'localparam', 'genvar'
        }

        # 匹配 module_type inst_name (.port(signal), ...)
        # 使用自定义匹配来处理嵌套括号
        inst_starts = list(re.finditer(r'\b(\w+)\s+(?:#\s*\(.*?\)\s*)?(\w+)\s*\(', body, re.DOTALL))

        for start_match in inst_starts:
            mod_type = start_match.group(1)
            inst_name = start_match.group(2)

            # 跳过关键字
            if mod_type.lower() in filter_keywords:
                continue

            # 提取连接字符串（需要匹配完整的括号）
            paren_start = start_match.end() - 1  # ( 的位置
            paren_end = self._skip_balanced_parens(body, paren_start)
            connections_str = body[paren_start+1:paren_end-1]

            # 解析端口连接（支持位选和拼接）
            connections = self._parse_port_connections(connections_str)

            instances.append({
                'type': mod_type,
                'name': inst_name,
                'connections': connections
            })

        return instances

    def _parse_port_connections(self, connections_str: str) -> Dict:
        """
        解析端口连接，支持：
        - 简单连接：.port(signal)
        - 位选：.port(signal[3:0])
        - 拼接：.port({a, b})
        - 常量：.port(4'b0)
        """
        connections = {}

        # 找到所有 .port(xxx) 形式的连接
        pos = 0
        while pos < len(connections_str):
            # 查找 .port
            port_match = re.match(r'\s*\.(\w+)\s*\(', connections_str[pos:])
            if not port_match:
                pos += 1
                continue

            port_name = port_match.group(1)
            pos += port_match.end()

            # 使用括号匹配找到连接表达式
            if pos <= len(connections_str) and connections_str[pos-1] == '(':
                # 找到匹配的右括号
                depth = 1
                start = pos
                while pos < len(connections_str) and depth > 0:
                    ch = connections_str[pos]
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                    pos += 1
                signal_expr = connections_str[start:pos-1].strip()
                connections[port_name] = signal_expr

            # 跳过逗号
            while pos < len(connections_str) and connections_str[pos] in ' \t\n,':
                pos += 1

        return connections
    
    def query_signal(self, signal_name: str, module_name: Optional[str] = None) -> List[Dict]:
        """
        查询信号的依赖关系
        核心问题：这个信号的跳转变化条件是什么？
        
        返回结构化信息，区分数据信号和控制信号
        """
        results = []
        
        # 搜索范围
        search_modules = [module_name] if module_name else list(self.modules.keys())
        
        for mod_name in search_modules:
            if mod_name not in self.modules:
                continue
            
            mod_info = self.modules[mod_name]
            
            # 检查信号是否存在
            if signal_name in mod_info['ports'] or signal_name in mod_info['dependencies']:
                # 获取原始依赖列表（可能有结构化信息）
                raw_deps = self._get_raw_dependencies(mod_name, signal_name)
                flat_deps = mod_info['dependencies'].get(signal_name, [])
                port_info = mod_info['ports'].get(signal_name, {})
                
                results.append({
                    'module': mod_name,
                    'signal': signal_name,
                    'type': 'port' if signal_name in mod_info['ports'] else 'internal',
                    'direction': port_info.get('direction', 'internal'),
                    'dependencies': flat_deps,
                    'structured_deps': raw_deps,
                    'driver': 'assign/always' if flat_deps else 'primary_input'
                })
        
        return results
    
    def _get_raw_dependencies(self, module_name: str, signal_name: str) -> List[Dict]:
        """
        获取信号的原始结构化依赖信息
        包含数据信号、控制信号、时序信息等
        """
        if module_name not in self.modules:
            return []
        
        mod_info = self.modules[module_name]
        
        # 从原始解析结果中获取（需要存储结构化信息）
        # 目前返回空列表，后续需要修改 _parse_modules 来存储原始依赖
        return mod_info.get('raw_dependencies', {}).get(signal_name, [])
    
    def trace_signal(self, signal_name: str, max_depth: int = 5, full: bool = False) -> List[Dict]:
        """
        递归追踪信号依赖链
        回答：这个信号为什么变化？它的上游是什么？
        
        参数:
            signal_name: 信号名称
            max_depth: 最大追踪深度
            full: True - 追踪完整依赖树到源头; False - 只查上一级依赖（单步）
        """
        chain = []
        visited = set()
        
        def trace(sig: str, mod: str, depth: int, parent: Optional[str] = None):
            if depth > max_depth:
                chain.append({
                    'signal': sig,
                    'module': mod,
                    'depth': depth,
                    'note': '达到最大深度'
                })
                return
            
            key = f"{mod}.{sig}"
            if key in visited:
                chain.append({
                    'signal': sig,
                    'module': mod,
                    'depth': depth,
                    'note': '循环依赖'
                })
                return
            
            visited.add(key)
            
            # 查询当前信号依赖
            results = self.query_signal(sig, mod)
            
            if not results:
                # 可能是通过实例化连接的信号
                # 查找哪个实例输出这个信号
                for other_mod, other_info in self.modules.items():
                    if other_mod == mod:
                        continue
                    for inst in other_info['instances']:
                        if inst['type'] == mod:
                            for port, connected_sig in inst['connections'].items():
                                if connected_sig == sig:
                                    # 找到连接，追踪到子模块
                                    trace(port, inst['type'], depth, parent=f"{mod}.{sig}")
                return
            
            for result in results:
                deps = result['dependencies']
                chain.append({
                    'signal': sig,
                    'module': mod,
                    'depth': depth,
                    'dependencies': deps,
                    'type': result['type'],
                    'direction': result['direction']
                })
                
                # 只有 full 模式才递归追踪依赖
                if full:
                    for dep in deps:
                        trace(dep, mod, depth + 1, parent=f"{mod}.{sig}")
        
        # 从所有模块开始追踪
        for mod_name in self.modules.keys():
            trace(signal_name, mod_name, 0)
        
        return chain
    
    def trace_cross_module(self, signal_name: str, module_name: str, max_depth: int = 10) -> Dict:
        """
        跨模块追踪信号（核心功能）
        自动追踪实例化端口连接，支持层级追踪（top → sub1 → sub2）
        一路追到顶层接口或模块边界
        
        参数:
            signal_name: 起始信号名
            module_name: 起始模块名
            max_depth: 最大追踪深度
            
        返回:
            {
                'path': [
                    {'module': 'xxx', 'signal': 'xxx', 'port': 'xxx', 'instance': 'xxx', 'direction': 'up/down'},
                    ...
                ],
                'boundary': 'top_port' | 'module_boundary' | 'max_depth',
                'summary': '追踪结果摘要'
            }
        """
        result = {
            'path': [],
            'boundary': None,
            'summary': ''
        }
        
        visited = set()
        
        def find_port_connection(sig: str, mod: str) -> Optional[Dict]:
            """查找信号连接到哪个实例的哪个端口"""
            mod_info = self.modules.get(mod)
            if not mod_info:
                return None
            
            # 检查是否是当前模块的端口
            if sig in mod_info['ports']:
                return {
                    'type': 'port',
                    'direction': mod_info['ports'][sig]['direction'],
                    'module': mod,
                    'signal': sig
                }
            
            # 检查是否连接到某个实例
            for inst in mod_info['instances']:
                for port, connected_sig in inst['connections'].items():
                    # 处理拼接和位选情况
                    if sig in str(connected_sig):
                        return {
                            'type': 'instance_port',
                            'instance': inst['name'],
                            'instance_type': inst['type'],
                            'port': port,
                            'connected_signal': connected_sig,
                            'parent_module': mod
                        }
            
            return None
        
        def trace_up(sig: str, mod: str, depth: int, path_key: str) -> bool:
            """向上追踪（从子模块到父模块）"""
            if depth > max_depth:
                result['boundary'] = 'max_depth'
                return False
            
            # 查找父模块
            for parent_mod, parent_info in self.modules.items():
                for inst in parent_info['instances']:
                    if inst['type'] == mod:
                        # 找到父模块，检查端口连接
                        for port, connected_sig in inst['connections'].items():
                            # 检查当前信号是否是这个端口的输出
                            mod_info = self.modules.get(mod)
                            if mod_info and sig in mod_info['ports']:
                                port_dir = mod_info['ports'][sig]['direction']
                                if port_dir == 'output':
                                    # 追踪到父模块
                                    result['path'].append({
                                        'from_module': mod,
                                        'from_signal': sig,
                                        'from_port': sig,
                                        'to_module': parent_mod,
                                        'to_signal': connected_sig,
                                        'via_instance': inst['name'],
                                        'via_port': port,
                                        'direction': 'up',
                                        'depth': depth
                                    })
                                    
                                    new_key = f"{parent_mod}.{connected_sig}"
                                    if new_key in visited:
                                        return True
                                    visited.add(new_key)
                                    
                                    # 继续向上追踪
                                    return trace_up(connected_sig, parent_mod, depth + 1, new_key)
            
            # 没有找到父模块，到达顶层
            mod_info = self.modules.get(mod)
            if mod_info and sig in mod_info['ports']:
                result['boundary'] = 'top_port'
                result['path'].append({
                    'module': mod,
                    'signal': sig,
                    'type': 'top_port',
                    'direction': mod_info['ports'][sig]['direction'],
                    'depth': depth
                })
            else:
                result['boundary'] = 'module_boundary'
            
            return True
        
        def trace_down(sig: str, mod: str, depth: int, path_key: str) -> bool:
            """向下追踪（从父模块到子模块）"""
            if depth > max_depth:
                result['boundary'] = 'max_depth'
                return False
            
            mod_info = self.modules.get(mod)
            if not mod_info:
                return False
            
            # 检查实例化连接
            for inst in mod_info['instances']:
                for port, connected_sig in inst['connections'].items():
                    if sig == connected_sig or sig in str(connected_sig):
                        # 找到连接，追踪到子模块
                        sub_mod = inst['type']
                        sub_mod_info = self.modules.get(sub_mod)
                        
                        if sub_mod_info and port in sub_mod_info['ports']:
                            port_dir = sub_mod_info['ports'][port]['direction']
                            
                            result['path'].append({
                                'from_module': mod,
                                'from_signal': sig,
                                'to_module': sub_mod,
                                'to_signal': port,
                                'to_port': port,
                                'via_instance': inst['name'],
                                'via_port': port,
                                'direction': 'down',
                                'depth': depth
                            })
                            
                            new_key = f"{sub_mod}.{port}"
                            if new_key in visited:
                                return True
                            visited.add(new_key)
                            
                            # 继续向下追踪
                            return trace_down(port, sub_mod, depth + 1, new_key)
            
            # 没有找到子模块连接，到达边界
            result['boundary'] = 'module_boundary'
            return True
        
        # 开始追踪
        start_key = f"{module_name}.{signal_name}"
        visited.add(start_key)
        
        # 获取信号信息
        mod_info = self.modules.get(module_name)
        if not mod_info:
            result['summary'] = f"模块 '{module_name}' 不存在"
            return result
        
        signal_info = find_port_connection(signal_name, module_name)
        
        if signal_info is None:
            # 内部信号，查找其驱动
            if signal_name in mod_info['dependencies']:
                result['path'].append({
                    'module': module_name,
                    'signal': signal_name,
                    'type': 'internal',
                    'dependencies': mod_info['dependencies'][signal_name],
                    'depth': 0
                })
                result['summary'] = f"内部信号，依赖: {mod_info['dependencies'][signal_name]}"
            else:
                result['summary'] = f"信号 '{signal_name}' 在模块 '{module_name}' 中未找到"
            return result
        
        if signal_info['type'] == 'port':
            direction = signal_info['direction']
            
            if direction == 'input':
                # 输入端口，向上追踪
                trace_up(signal_name, module_name, 0, start_key)
            elif direction == 'output':
                # 输出端口，检查是否来自子模块或内部逻辑
                if signal_name in mod_info['dependencies']:
                    # 来自内部逻辑
                    result['path'].append({
                        'module': module_name,
                        'signal': signal_name,
                        'type': 'output_from_logic',
                        'dependencies': mod_info['dependencies'][signal_name],
                        'depth': 0
                    })
                # 继续向下追踪
                trace_down(signal_name, module_name, 0, start_key)
            else:
                # inout
                trace_up(signal_name, module_name, 0, start_key)
                trace_down(signal_name, module_name, 0, start_key)
        
        # 生成摘要
        if result['path']:
            top_info = result['path'][0]
            if result['boundary'] == 'top_port':
                result['summary'] = f"追踪到顶层端口: {top_info.get('module')}.{top_info.get('signal')}"
            elif result['boundary'] == 'max_depth':
                result['summary'] = f"达到最大追踪深度 ({max_depth})"
            else:
                result['summary'] = f"追踪了 {len(result['path'])} 层连接"
        else:
            result['summary'] = "未找到跨模块连接"
        
        return result
    
    def search_global(self, signal_pattern: str, use_regex: bool = False) -> List[Dict]:
        """
        全局搜索信号
        搜索所有模块中匹配的信号，返回完整路径
        
        参数:
            signal_pattern: 信号名模式（支持通配符 * 和 ?，或正则表达式）
            use_regex: 是否使用正则表达式模式
            
        返回:
            [
                {
                    'path': 'module.signal',
                    'module': 'xxx',
                    'signal': 'xxx',
                    'type': 'port' | 'internal',
                    'direction': 'input' | 'output' | 'inout' | 'internal',
                    'line': 行号（如果有）
                },
                ...
            ]
        """
        results = []
        
        # 构建匹配模式
        if use_regex:
            pattern = re.compile(signal_pattern)
        else:
            # 转换通配符到正则
            regex_pattern = signal_pattern.replace('.', r'\.')
            regex_pattern = regex_pattern.replace('*', '.*')
            regex_pattern = regex_pattern.replace('?', '.')
            regex_pattern = f"^{regex_pattern}$"
            pattern = re.compile(regex_pattern, re.IGNORECASE)
        
        # 搜索所有模块
        for mod_name, mod_info in self.modules.items():
            # 搜索端口
            for port_name, port_info in mod_info['ports'].items():
                if pattern.match(port_name):
                    results.append({
                        'path': f"{mod_name}.{port_name}",
                        'module': mod_name,
                        'signal': port_name,
                        'type': 'port',
                        'direction': port_info['direction'],
                        'dependencies': mod_info['dependencies'].get(port_name, [])
                    })
            
            # 搜索内部信号（依赖中的左侧信号）
            for signal_name in mod_info['dependencies'].keys():
                if signal_name not in mod_info['ports']:  # 避免重复
                    if pattern.match(signal_name):
                        results.append({
                            'path': f"{mod_name}.{signal_name}",
                            'module': mod_name,
                            'signal': signal_name,
                            'type': 'internal',
                            'direction': 'internal',
                            'dependencies': mod_info['dependencies'][signal_name]
                        })
        
        return results
    
    def build_hierarchy(self, top_module: Optional[str] = None) -> Dict:
        """
        构建模块层级结构
        
        参数:
            top_module: 指定顶层模块（可选，不指定则自动检测）
            
        返回:
            {
                'top': 'top_module_name',
                'hierarchy': {
                    'module_name': {
                        'instances': [{'name': 'xxx', 'type': 'xxx'}, ...],
                        'parent': 'parent_module_name',
                        'children': ['child_module_1', ...]
                    },
                    ...
                }
            }
        """
        hierarchy = {}
        
        # 第一遍：收集所有实例关系
        for mod_name, mod_info in self.modules.items():
            hierarchy[mod_name] = {
                'instances': [],
                'parent': None,
                'children': []
            }
            
            for inst in mod_info['instances']:
                hierarchy[mod_name]['instances'].append({
                    'name': inst['name'],
                    'type': inst['type']
                })
                
                # 记录子模块
                sub_mod = inst['type']
                if sub_mod in self.modules:
                    if sub_mod not in hierarchy:
                        hierarchy[sub_mod] = {
                            'instances': [],
                            'parent': None,
                            'children': []
                        }
                    hierarchy[sub_mod]['parent'] = mod_name
                    if sub_mod not in hierarchy[mod_name]['children']:
                        hierarchy[mod_name]['children'].append(sub_mod)
        
        # 检测顶层模块
        if top_module:
            detected_top = top_module
        else:
            # 没有父模块的就是顶层
            top_candidates = [m for m, h in hierarchy.items() if h['parent'] is None]
            detected_top = top_candidates[0] if len(top_candidates) == 1 else None
        
        return {
            'top': detected_top,
            'hierarchy': hierarchy
        }
    
    def print_trace(self, signal_name: str, module_name: Optional[str] = None, full: bool = False) -> None:
        """打印信号追踪结果（增强版：区分数据信号和控制信号）"""
        results = self.query_signal(signal_name, module_name)
        
        if not results:
            print(f"❌ 未找到信号 '{signal_name}'")
            return
        
        print(f"\n🔍 信号查询：{signal_name}")
        print("=" * 80)
        
        for r in results:
            print(f"\n📦 模块：{r['module']}")
            print(f"   类型：{r['type']} ({r['direction']})")
            print(f"   驱动：{r['driver']}")
            
            # 获取结构化依赖信息
            structured_deps = r.get('structured_deps', [])
            
            if structured_deps:
                # 有结构化信息，区分显示
                for dep_info in structured_deps:
                    dep_type = dep_info.get('type', 'unknown')
                    
                    # 显示时序信息
                    if dep_type == 'sequential':
                        clk = dep_info.get('clk')
                        rst = dep_info.get('rst')
                        rst_type = dep_info.get('rst_type')
                        
                        if clk:
                            print(f"   ⏰ 时钟：{clk}")
                        if rst:
                            rst_label = '同步复位' if rst_type == 'sync' else '异步复位'
                            print(f"   🔄 {rst_label}：{rst}")
                    
                    # 区分数据信号和控制信号
                    data_signals = dep_info.get('signals', [])
                    control_signals = dep_info.get('control_signals', [])
                    conditions = dep_info.get('conditions', [])
                    
                    if control_signals:
                        print(f"   🎛️  控制信号:")
                        for ctrl in control_signals:
                            print(f"      ⚡ {ctrl}")
                    
                    if conditions:
                        print(f"   📋 条件表达式:")
                        for cond in conditions:
                            cond_type = cond.get('type', 'if')
                            expr = cond.get('expression', '')
                            sigs = cond.get('signals', [])
                            print(f"      [{cond_type}] {expr}")
                            if sigs and len(sigs) > 1:
                                print(f"              信号: {', '.join(sigs)}")
                    
                    if data_signals:
                        print(f"   📊 数据信号:")
                        for sig in data_signals:
                            print(f"      ← {sig}")
                    elif not control_signals and not conditions:
                        print(f"   变化条件：无 (原始输入)")
            else:
                # 无结构化信息，使用扁平列表
                if r['dependencies']:
                    print(f"   依赖信号:")
                    for dep in r['dependencies']:
                        print(f"      ← {dep}")
                else:
                    print(f"   变化条件：无 (原始输入)")
        
        # 递归追踪
        print(f"\n🔗 完整依赖链:")
        chain = self.trace_signal(signal_name, full=full)
        
        if not chain:
            print("   (无更多依赖)")
            return
        
        for item in chain:
            indent = "  " * item['depth']
            if 'note' in item:
                print(f"{indent}{item['signal']} ⚠️ {item['note']}")
            elif item['dependencies']:
                deps_str = ", ".join(item['dependencies'][:3])
                if len(item['dependencies']) > 3:
                    deps_str += f"... (+{len(item['dependencies'])-3})"
                print(f"{indent}{item['signal']} ← {deps_str}")
            else:
                print(f"{indent}{item['signal']} (叶信号)")
    
    def print_summary(self) -> None:
        """打印模块摘要"""
        print("=" * 80)
        print("RTL 模块摘要")
        print("=" * 80)
        
        for mod_name, mod_info in self.modules.items():
            print(f"\n📦 {mod_name}")
            print(f"   文件：{mod_info['file']}")
            print(f"   端口：{len(mod_info['ports'])} 个")
            print(f"   信号依赖：{len(mod_info['dependencies'])} 个")
            
            if mod_info['instances']:
                print(f"   实例化：{len(mod_info['instances'])} 个")
                for inst in mod_info['instances'][:3]:
                    print(f"      {inst['type']} {inst['name']}")
    
    def print_cross_module_trace(self, signal_name: str, module_name: str, max_depth: int = 10) -> None:
        """打印跨模块追踪结果"""
        result = self.trace_cross_module(signal_name, module_name, max_depth)
        
        print(f"\n🔍 跨模块追踪：{signal_name} (模块: {module_name})")
        print("=" * 80)
        
        if result['path']:
            for i, step in enumerate(result['path']):
                if step.get('type') == 'top_port':
                    print(f"\n  [{i}] 🏠 顶层端口")
                    print(f"      模块: {step['module']}")
                    print(f"      信号: {step['signal']}")
                    print(f"      方向: {step['direction']}")
                elif step.get('type') == 'internal':
                    print(f"\n  [{i}] 🔧 内部信号")
                    print(f"      模块: {step['module']}")
                    print(f"      信号: {step['signal']}")
                    print(f"      依赖: {step.get('dependencies', [])}")
                elif step.get('type') == 'output_from_logic':
                    print(f"\n  [{i}] 📤 输出端口（来自逻辑）")
                    print(f"      模块: {step['module']}")
                    print(f"      信号: {step['signal']}")
                    print(f"      依赖: {step.get('dependencies', [])}")
                elif 'direction' in step:
                    direction_emoji = '⬆️' if step['direction'] == 'up' else '⬇️'
                    print(f"\n  [{i}] {direction_emoji} {'向上追踪' if step['direction'] == 'up' else '向下追踪'}")
                    print(f"      从: {step.get('from_module', '')}.{step.get('from_signal', '')}")
                    print(f"      到: {step.get('to_module', '')}.{step.get('to_signal', '')}")
                    print(f"      实例: {step.get('via_instance', '')} (端口: {step.get('via_port', '')})")
        else:
            print(f"  未找到跨模块连接")
        
        print(f"\n📍 边界: {result['boundary'] or '未知'}")
        print(f"📝 摘要: {result['summary']}")
    
    def print_global_search(self, signal_pattern: str, use_regex: bool = False) -> None:
        """打印全局搜索结果"""
        results = self.search_global(signal_pattern, use_regex)
        
        print(f"\n🔍 全局搜索：{signal_pattern}")
        if use_regex:
            print("   模式: 正则表达式")
        print("=" * 80)
        
        if results:
            print(f"找到 {len(results)} 个匹配:\n")
            for r in results:
                type_emoji = '🔌' if r['type'] == 'port' else '📡'
                dir_str = f"({r['direction']})" if r['direction'] != 'internal' else ""
                print(f"  {type_emoji} {r['path']} {dir_str}")
                if r.get('dependencies'):
                    deps_str = ", ".join(r['dependencies'][:5])
                    if len(r['dependencies']) > 5:
                        deps_str += f"... (+{len(r['dependencies'])-5})"
                    print(f"      ← {deps_str}")
        else:
            print("未找到匹配的信号")


def parse_filelist(filelist_path: str, base_dir: Optional[str] = None, visited: Optional[Set[str]] = None, depth: int = 0) -> RTLDependencyAnalyzer:
    """
    解析 filelist 文件，支持无限层嵌套和环境变量
    filelist 中可以包含：
    - 源文件 (.v, .sv)
    - 嵌套的 filelist (-f filelist.f)
    - 编译选项 (+incdir, +define+)
    - 环境变量 ($VAR 或 ${VAR})
    
    参数:
        depth: 当前嵌套深度（用于调试输出）
    """
    analyzer = RTLDependencyAnalyzer()
    
    if visited is None:
        visited = set()
    
    # 防止循环引用
    filelist_abs = os.path.abspath(filelist_path)
    if filelist_abs in visited:
        print(f"{'  ' * depth}⚠️  跳过循环引用：{filelist_path}")
        return analyzer
    
    visited.add(filelist_abs)
    
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(filelist_path))
    
    indent = '  ' * depth
    print(f"{indent}📋 解析 filelist: {filelist_path} (深度 {depth})")
    
    with open(filelist_path, 'r') as f:
        for line in f:
            line = line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue
            
            # Step 1: 展开环境变量
            line = _expand_env_vars(line)
            
            # Step 2: 处理嵌套 filelist
            if line.startswith('-f '):
                nested_filelist = line[3:].strip()
                # 相对路径转换为绝对路径
                if not os.path.isabs(nested_filelist):
                    nested_filelist = os.path.join(base_dir, nested_filelist)
                
                if os.path.exists(nested_filelist):
                    # 递归解析嵌套的 filelist（无深度限制）
                    nested_analyzer = parse_filelist(nested_filelist, base_dir, visited, depth + 1)
                    # 合并结果
                    for mod_name, mod_info in nested_analyzer.modules.items():
                        analyzer.modules[mod_name] = mod_info
                    analyzer.signal_deps.update(nested_analyzer.signal_deps)
                else:
                    print(f"{indent}❌ 嵌套 filelist 不存在：{nested_filelist}")
                continue
            
            # Step 3: 处理 +incdir 选项
            if line.startswith('+incdir='):
                inc_dir = line[8:].strip()
                analyzer.include_dirs.append(inc_dir)
                print(f"{indent}   +incdir: {inc_dir}")
                continue
            
            # Step 4: 处理 +define+ 选项
            if line.startswith('+define+'):
                define = line[8:].strip()
                # 解析 DEFINE=VALUE 格式
                if '=' in define:
                    name, value = define.split('=', 1)
                    analyzer.defines[name] = {'value': value, 'args': None}
                else:
                    analyzer.defines[define] = {'value': '1', 'args': None}
                print(f"{indent}   +define: {define}")
                continue
            
            # 其他 + 选项跳过
            if line.startswith('+'):
                continue
            
            # Step 5: 源文件
            if not os.path.isabs(line):
                line = os.path.join(base_dir, line)
            
            if os.path.exists(line):
                print(f"{indent}📄 解析：{line}")
                analyzer.parse_file(line)
            else:
                print(f"{indent}⚠️  文件不存在：{line}")
    
    return analyzer


def _expand_env_vars(text: str) -> str:
    """
    展开环境变量
    支持格式：$VAR 或 ${VAR}
    """
    # 展开 ${VAR} 格式
    def replace_braced(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))  # 如果不存在，保留原样
    
    text = re.sub(r'\$\{(\w+)\}', replace_braced, text)
    
    # 展开 $VAR 格式（后面跟非字母数字）
    def replace_simple(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))  # 如果不存在，保留原样
    
    text = re.sub(r'\$(\w+)', replace_simple, text)
    
    return text


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='RTL 信号依赖分析器 - 分析信号跳转变化条件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 解析文件并查看摘要
  %(prog)s design.v

  # 解析 filelist
  %(prog)s --filelist design.f

  # 查询信号依赖（单步）
  %(prog)s design.v --signal data_valid

  # 查询完整依赖链
  %(prog)s design.v --signal data_valid --full

  # 跨模块追踪
  %(prog)s design.v --cross data_valid --module sub_module

  # 全局搜索信号（通配符）
  %(prog)s design.v --global "*valid*"

  # 全局搜索信号（正则表达式）
  %(prog)s design.v --global "valid.*" --regex
        '''
    )
    
    parser.add_argument('files', nargs='*', help='Verilog 源文件')
    parser.add_argument('--filelist', '-f', help='filelist 文件路径')
    parser.add_argument('--signal', '-s', help='查询信号依赖')
    parser.add_argument('--trace', '-t', help='追踪信号（同 --signal）')
    parser.add_argument('--module', '-m', help='指定模块名（用于 --cross）')
    parser.add_argument('--cross', '-c', help='跨模块追踪信号')
    parser.add_argument('--global', '-g', dest='global_search', help='全局搜索信号（支持通配符 * 和 ?）')
    parser.add_argument('--regex', '-r', action='store_true', help='使用正则表达式进行全局搜索')
    parser.add_argument('--full', action='store_true', help='追踪完整依赖树到源头（默认只查上一级）')
    parser.add_argument('--depth', '-d', type=int, default=10, help='最大追踪深度（默认 10）')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 格式输出（适合机器解析）')
    
    args = parser.parse_args()
    
    analyzer = RTLDependencyAnalyzer()
    
    # 解析文件
    if args.filelist:
        analyzer = parse_filelist(args.filelist)
    elif args.files:
        for f in args.files:
            if os.path.exists(f):
                print(f"📄 解析：{f}")
                analyzer.parse_file(f)
    else:
        parser.print_help()
        sys.exit(1)
    
    # 执行查询
    if args.signal:
        if args.json:
            # JSON 输出模式
            results = analyzer.query_signal(args.signal)
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            analyzer.print_trace(args.signal, full=args.full)
    elif args.trace:
        if args.json:
            results = analyzer.query_signal(args.trace)
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            analyzer.print_trace(args.trace, full=args.full)
    elif args.cross:
        # 跨模块追踪
        module_name = args.module
        if not module_name:
            # 尝试自动检测模块
            modules = list(analyzer.modules.keys())
            if len(modules) == 1:
                module_name = modules[0]
            else:
                print(f"❌ 请使用 --module 指定模块名。可用模块: {', '.join(modules)}")
                sys.exit(1)
        
        result = analyzer.trace_cross_module(args.cross, module_name, args.depth)
        
        print(f"\n🔍 跨模块追踪：{args.cross} (模块: {module_name})")
        print("=" * 80)
        
        if result['path']:
            for i, step in enumerate(result['path']):
                if step.get('type') == 'top_port':
                    print(f"\n  [{i}] 🏠 顶层端口")
                    print(f"      模块: {step['module']}")
                    print(f"      信号: {step['signal']}")
                    print(f"      方向: {step['direction']}")
                elif step.get('type') == 'internal':
                    print(f"\n  [{i}] 🔧 内部信号")
                    print(f"      模块: {step['module']}")
                    print(f"      信号: {step['signal']}")
                    print(f"      依赖: {step.get('dependencies', [])}")
                elif step.get('type') == 'output_from_logic':
                    print(f"\n  [{i}] 📤 输出端口（来自逻辑）")
                    print(f"      模块: {step['module']}")
                    print(f"      信号: {step['signal']}")
                    print(f"      依赖: {step.get('dependencies', [])}")
                elif 'direction' in step:
                    direction_emoji = '⬆️' if step['direction'] == 'up' else '⬇️'
                    print(f"\n  [{i}] {direction_emoji} {'向上追踪' if step['direction'] == 'up' else '向下追踪'}")
                    print(f"      从: {step.get('from_module', '')}.{step.get('from_signal', '')}")
                    print(f"      到: {step.get('to_module', '')}.{step.get('to_signal', '')}")
                    print(f"      实例: {step.get('via_instance', '')} (端口: {step.get('via_port', '')})")
        else:
            print(f"  未找到跨模块连接")
        
        print(f"\n📍 边界: {result['boundary'] or '未知'}")
        print(f"📝 摘要: {result['summary']}")
        
    elif args.global_search:
        # 全局搜索
        results = analyzer.search_global(args.global_search, use_regex=args.regex)
        
        print(f"\n🔍 全局搜索：{args.global_search}")
        if args.regex:
            print("   模式: 正则表达式")
        print("=" * 80)
        
        if results:
            print(f"找到 {len(results)} 个匹配:\n")
            for r in results:
                type_emoji = '🔌' if r['type'] == 'port' else '📡'
                dir_str = f"({r['direction']})" if r['direction'] != 'internal' else ""
                print(f"  {type_emoji} {r['path']} {dir_str}")
                if r.get('dependencies'):
                    deps_str = ", ".join(r['dependencies'][:5])
                    if len(r['dependencies']) > 5:
                        deps_str += f"... (+{len(r['dependencies'])-5})"
                    print(f"      ← {deps_str}")
        else:
            print("未找到匹配的信号")
    else:
        analyzer.print_summary()
