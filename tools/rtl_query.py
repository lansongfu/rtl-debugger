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
    
    def _parse_modules(self, content: str, filepath: str) -> Dict:
        """解析模块定义"""
        modules = {}
        
        # 先处理 generate 块
        content = self._process_generate(content)
        
        # 匹配 module 定义
        module_pattern = r'module\s+(\w+)\s*(?:#\(.*?\))?\s*\(([^)]*)\)\s*(.*?)(?:endmodule|\Z)'
        
        for match in re.finditer(module_pattern, content, re.DOTALL):
            mod_name = match.group(1)
            port_section = match.group(2)
            body = match.group(3)
            
            # 解析端口
            ports = self._parse_ports(port_section)
            
            # 解析依赖关系
            deps = self._parse_dependencies(body)
            
            # 解析实例化
            instances = self._parse_instances(body)
            
            modules[mod_name] = {
                'file': filepath,
                'ports': ports,
                'dependencies': deps,
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
    
    def _parse_dependencies(self, body: str) -> Dict[str, List[str]]:
        """解析信号依赖关系"""
        deps = defaultdict(list)
        
        # 1. 解析 assign 语句
        # assign lhs = rhs;
        assign_pattern = r'assign\s+([^;]+)\s*=\s*([^;]+);'
        for match in re.finditer(assign_pattern, body):
            lhs = match.group(1).strip()
            rhs = match.group(2).strip()
            
            # 提取 LHS 信号名 (处理位选)
            lhs_signal = re.match(r'(\w+)', lhs)
            if lhs_signal:
                lhs_name = lhs_signal.group(1)
                # 提取 RHS 所有信号
                rhs_signals = self._extract_signals(rhs)
                deps[lhs_name] = list(set(rhs_signals))
        
        # 2. 解析 always 块中的 <= 赋值
        always_pattern = r'always\s*(?:@\s*\([^)]*\)|#\d+)?\s*(?:begin(.*?)end|([^;]+);)'
        for match in re.finditer(always_pattern, body, re.DOTALL):
            block = match.group(1) if match.group(1) else match.group(2)
            if block:
                # 查找 <= 赋值
                nba_pattern = r'(\w+)\s*<=\s*([^;]+);'
                for nba_match in re.finditer(nba_pattern, block):
                    lhs = nba_match.group(1)
                    rhs = nba_match.group(2)
                    rhs_signals = self._extract_signals(rhs)
                    deps[lhs] = list(set(rhs_signals))
                
                # 查找 = 赋值 (组合逻辑)
                ba_pattern = r'(\w+)\s*=\s*([^;]+);'
                for ba_match in re.finditer(ba_pattern, block):
                    lhs = ba_match.group(1)
                    rhs = ba_match.group(2)
                    # 跳过已经匹配的 assign
                    if lhs not in deps:
                        rhs_signals = self._extract_signals(rhs)
                        deps[lhs] = list(set(rhs_signals))
        
        return dict(deps)
    
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
        
        # 匹配 module_type inst_name (.port(signal), ...)
        # 支持多行
        inst_pattern = r'(\w+)\s+(?:#\s*\([^)]*\)\s*)?(\w+)\s*\(([^)]*)\)'
        
        for match in re.finditer(inst_pattern, body, re.DOTALL):
            mod_type = match.group(1)
            inst_name = match.group(2)
            connections_str = match.group(3)
            
            # 跳过关键字
            if mod_type in ['input', 'output', 'inout', 'wire', 'reg', 'assign', 'always']:
                continue
            
            # 解析端口连接
            connections = {}
            conn_pattern = r'\.(\w+)\s*\((\w+)\)'
            for conn_match in re.finditer(conn_pattern, connections_str):
                port = conn_match.group(1)
                signal = conn_match.group(2)
                connections[port] = signal
            
            instances.append({
                'type': mod_type,
                'name': inst_name,
                'connections': connections
            })
        
        return instances
    
    def query_signal(self, signal_name: str, module_name: Optional[str] = None) -> List[Dict]:
        """
        查询信号的依赖关系
        核心问题：这个信号的跳转变化条件是什么？
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
                deps = mod_info['dependencies'].get(signal_name, [])
                port_info = mod_info['ports'].get(signal_name, {})
                
                results.append({
                    'module': mod_name,
                    'signal': signal_name,
                    'type': 'port' if signal_name in mod_info['ports'] else 'internal',
                    'direction': port_info.get('direction', 'internal'),
                    'dependencies': deps,
                    'driver': 'assign/always' if deps else 'primary_input'
                })
        
        return results
    
    def trace_signal(self, signal_name: str, max_depth: int = 5) -> List[Dict]:
        """
        递归追踪信号依赖链
        回答：这个信号为什么变化？它的上游是什么？
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
                
                # 递归追踪依赖
                for dep in deps:
                    trace(dep, mod, depth + 1, parent=f"{mod}.{sig}")
        
        # 从所有模块开始追踪
        for mod_name in self.modules.keys():
            trace(signal_name, mod_name, 0)
        
        return chain
    
    def print_trace(self, signal_name: str, module_name: Optional[str] = None) -> None:
        """打印信号追踪结果"""
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
            
            if r['dependencies']:
                print(f"   变化条件:")
                for dep in r['dependencies']:
                    print(f"      ← {dep}")
            else:
                print(f"   变化条件：无 (原始输入)")
        
        # 递归追踪
        print(f"\n🔗 完整依赖链:")
        chain = self.trace_signal(signal_name)
        
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
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  ./rtl_query.py <file1.v> [file2.v ...] [--signal <name>] [--trace <name>]")
        print("  ./rtl_query.py --filelist <filelist.txt> [--signal <name>]")
        sys.exit(1)
    
    analyzer = RTLDependencyAnalyzer()
    
    # 解析文件
    if '--filelist' in sys.argv:
        idx = sys.argv.index('--filelist')
        if idx + 1 < len(sys.argv):
            analyzer = parse_filelist(sys.argv[idx + 1])
    else:
        files = [f for f in sys.argv[1:] if not f.startswith('--')]
        for f in files:
            if os.path.exists(f):
                print(f"📄 解析：{f}")
                analyzer.parse_file(f)
    
    # 查询信号
    if '--signal' in sys.argv:
        idx = sys.argv.index('--signal')
        if idx + 1 < len(sys.argv):
            signal = sys.argv[idx + 1]
            analyzer.print_trace(signal)
    elif '--trace' in sys.argv:
        idx = sys.argv.index('--trace')
        if idx + 1 < len(sys.argv):
            signal = sys.argv[idx + 1]
            analyzer.print_trace(signal)
    else:
        analyzer.print_summary()
