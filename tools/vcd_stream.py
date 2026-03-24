#!/usr/bin/env python3
"""
VCD 流式查询工具（优化版）
核心改进：
1. 流式读取，不加载整个文件
2. 只读取目标信号
3. 支持索引加速
4. 支持超大文件（几十 GB）
"""

import sys
# Windows 编码适配：确保 UTF-8 输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import os
import re
import json
from typing import Optional, Dict, List, Tuple


class VCDStreamReader:
    """VCD 流式读取器"""
    
    def __init__(self, vcd_file: str):
        self.vcd_file = vcd_file
        self.signals = {}  # name -> id
        self.signal_ids = {}  # id -> name
        self.signal_widths = {}  # name -> width
        self.file_size = os.path.getsize(vcd_file)
        
    def parse_header(self, f) -> bool:
        """解析 VCD 文件头，提取信号映射"""
        while True:
            line = f.readline()
            if not line:
                return False
            
            line = line.strip()
            
            # 文件头结束
            if line == '$enddefinitions $end':
                return True
            
            # 信号定义
            if line.startswith('$var'):
                parts = line.split()
                if len(parts) >= 5:
                    var_type = parts[1]
                    width = int(parts[2]) if parts[2].isdigit() else 1
                    signal_id = parts[3]
                    signal_name = parts[4]
                    
                    self.signals[signal_name] = signal_id
                    self.signal_ids[signal_id] = signal_name
                    self.signal_widths[signal_name] = width
        
        return True
    
    def query_signal_streaming(self, target_name: str) -> Optional[Dict]:
        """
        流式查询单个信号
        只读取目标信号的变化，不加载整个文件
        """
        with open(self.vcd_file, 'r', errors='ignore') as f:
            if not self.parse_header(f):
                return None
            
            # 检查信号是否存在
            if target_name not in self.signals:
                return None
            
            target_id = self.signals[target_name]
            width = self.signal_widths.get(target_name, 1)
            
            # 流式读取数据段
            changes = []
            current_time = 0
            
            while True:
                line = f.readline()
                if not line:
                    break
                    
                line = line.strip()
                
                # 时间戳
                if line.startswith('#'):
                    current_time = int(line[1:])
                    continue
                
                # 信号值变化
                if line.startswith('b'):
                    # 多比特信号
                    match = re.match(r'b([01xXzZ]+)\s+(\S+)', line)
                    if match:
                        value = match.group(1)
                        sig_id = match.group(2)
                        if sig_id == target_id:
                            changes.append((current_time, value))
                else:
                    # 单比特信号
                    match = re.match(r'([01xXzZ])(\S+)', line)
                    if match:
                        value = match.group(1)
                        sig_id = match.group(2)
                        if sig_id == target_id:
                            changes.append((current_time, value))
            
            return {
                'name': target_name,
                'width': width,
                'changes': len(changes),
                'tv': changes
            }
        
        return None
    
    def create_index(self, index_file: str) -> Dict:
        """
        创建索引文件
        记录每个信号的统计信息
        """
        print(f"📝 创建索引：{index_file}")
        
        index = {
            'file': self.vcd_file,
            'file_size': self.file_size,
            'signals': {},
            'signal_count': 0
        }
        
        # 第一遍：解析文件头
        with open(self.vcd_file, 'r', errors='ignore') as f:
            if not self.parse_header(f):
                return {}
            
            index['signal_count'] = len(self.signals)
            index['signals'] = {
                name: {
                    'id': sig_id,
                    'width': self.signal_widths.get(name, 1),
                    'changes': 0,
                    'first_time': None,
                    'last_time': None
                }
                for name, sig_id in self.signals.items()
            }
            
            # 第二遍：统计每个信号的变化次数
            current_time = 0
            progress_interval = max(1000000, self.file_size // 20)  # 每 5% 或每 1MB 报告一次
            last_progress = 0
            line_count = 0
            
            print(f"📊 扫描文件（{self.file_size / 1024 / 1024:.1f} MB）...")
            
            while True:
                line = f.readline()
                if not line:
                    break
                    
                line = line.strip()
                line_count += 1
                pos = f.tell()
                
                if line.startswith('#'):
                    current_time = int(line[1:])
                    continue
                
                if line.startswith('b'):
                    match = re.match(r'b([01xXzZ]+)\s+(\S+)', line)
                    if match:
                        sig_id = match.group(2)
                        if sig_id in self.signal_ids:
                            name = self.signal_ids[sig_id]
                            info = index['signals'][name]
                            info['changes'] += 1
                            if info['first_time'] is None:
                                info['first_time'] = current_time
                            info['last_time'] = current_time
                else:
                    match = re.match(r'([01xXzZ])(\S+)', line)
                    if match:
                        sig_id = match.group(2)
                        if sig_id in self.signal_ids:
                            name = self.signal_ids[sig_id]
                            info = index['signals'][name]
                            info['changes'] += 1
                            if info['first_time'] is None:
                                info['first_time'] = current_time
                            info['last_time'] = current_time
                
                # 进度报告
                if pos - last_progress > progress_interval:
                    progress = pos / self.file_size * 100
                    print(f"   进度：{progress:.0f}% (已处理{line_count}行)")
                    last_progress = pos
            
            print(f"✅ 索引创建完成 (共{line_count}行)")
        
        # 保存索引
        with open(index_file, 'w') as f:
            json.dump(index, f, indent=2)
        
        print(f"📁 索引大小：{os.path.getsize(index_file) / 1024:.1f} KB")
        
        return index
    
    def load_index(self, index_file: str) -> Optional[Dict]:
        """加载索引文件"""
        if not os.path.exists(index_file):
            return None
        
        with open(index_file, 'r') as f:
            return json.load(f)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='VCD 流式查询工具')
    parser.add_argument('vcd_file', help='VCD 文件路径')
    parser.add_argument('--signal', '-s', help='查询特定信号')
    parser.add_argument('--create-index', '-i', action='store_true', help='创建索引文件')
    parser.add_argument('--index-file', help='索引文件路径（默认：<vcd>.idx）')
    
    args = parser.parse_args()
    
    # 创建读取器
    reader = VCDStreamReader(args.vcd_file)
    
    # 创建索引
    if args.create_index:
        index_file = args.index_file or args.vcd_file + '.idx'
        reader.create_index(index_file)
        return
    
    # 查询信号
    if args.signal:
        print(f"🔍 查询信号：{args.signal}")
        
        # 尝试加载索引
        index_file = args.index_file or args.vcd_file + '.idx'
        index = reader.load_index(index_file)
        
        if index:
            print(f"✅ 使用索引加速")
            if args.signal in index['signals']:
                info = index['signals'][args.signal]
                print(f"   信号：{args.signal}")
                print(f"   位宽：{info['width']}")
                print(f"   变化次数：{info['changes']}")
                if info['first_time'] is not None:
                    print(f"   首次变化：t={info['first_time']} ps")
                    print(f"   最后变化：t={info['last_time']} ps")
            else:
                print(f"❌ 信号不存在")
            return
        
        # 无索引，流式查询
        print(f"📖 流式读取...")
        result = reader.query_signal_streaming(args.signal)
        
        if result:
            print(f"✅ {result['name']}: 变化 {result['changes']} 次")
            
            # 分析行为
            if result['changes'] == 0:
                print(f"   行为：始终无变化 (静默信号)")
            else:
                tv = result['tv']
                unique_values = set(v for t, v in tv)
                
                if len(unique_values) == 1:
                    print(f"   行为：始终为 {tv[0][1]} (恒定信号)")
                elif result['width'] == 1:
                    zeros = sum(1 for t, v in tv if v == '0')
                    ones = sum(1 for t, v in tv if v == '1')
                    print(f"   行为：变化 {len(tv)} 次 (0:{zeros}次，1:{ones}次)")
                else:
                    print(f"   行为：变化 {len(tv)} 次 ({len(unique_values)} 个不同值)")
        else:
            print(f"❌ 未找到信号 '{args.signal}'")


if __name__ == '__main__':
    main()
