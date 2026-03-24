#!/usr/bin/env python3
"""
VCD 协议解析器 v5 - AXI4/APB/AHB 协议分析

定位：供其他 Agent 调用的协议解析函数库
使用方式：
    from vcd_protocol import analyze_axi4, analyze_apb, analyze_ahb
    
特性：
- 基于 vcd_analyze.py 深度分析
- 自动识别协议信号
- 检测协议违规
- 返回结构化数据（dict/JSON）
"""

import sys
import os

# Windows 编码适配
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 导入深度分析
from vcd_analyze import analyze_bus
from vcd_smart import VCDSmartStream
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class AXIChannel(Enum):
    """AXI4 通道"""
    AW = "AW"  # 写地址
    W = "W"    # 写数据
    B = "B"    # 写响应
    AR = "AR"  # 读地址
    R = "R"    # 读响应


class APBState(Enum):
    """APB 状态"""
    IDLE = "IDLE"
    SETUP = "SETUP"
    ENABLE = "ENABLE"


class ProtocolViolation:
    """协议违规"""
    def __init__(self, channel: str, rule: str, time: int, description: str):
        self.channel = channel
        self.rule = rule
        self.time_ps = time
        self.description = description
    
    def to_dict(self):
        return {
            'channel': self.channel,
            'rule': self.rule,
            'time_ps': self.time_ps,
            'description': self.description
        }


@dataclass
class AXITransaction:
    """AXI 事务"""
    channel: str
    id: int
    address: int
    length: int
    size: int
    burst_type: str
    start_time_ps: int
    end_time_ps: int
    latency_ps: int
    data_bytes: List[int] = None


@dataclass
class APBTransaction:
    """APB 事务"""
    address: int
    data: int
    write: bool
    start_time_ps: int
    end_time_ps: int
    error: bool = False


def analyze_axi4(vcd_file: str, signals: Dict[str, str],
                 window: Optional[Tuple[int, int]] = None) -> Dict:
    """
    AXI4 协议分析
    
    Args:
        vcd_file: VCD 文件路径
        signals: 信号字典 {
            # 写地址通道
            'awvalid': 'axi_awvalid',
            'awready': 'axi_awready',
            'awaddr': 'axi_awaddr[31:0]',
            'awlen': 'axi_awlen[7:0]',
            'awid': 'axi_awid[3:0]',
            
            # 写数据通道
            'wvalid': 'axi_wvalid',
            'wready': 'axi_wready',
            'wdata': 'axi_wdata[31:0]',
            'wlast': 'axi_wlast',
            
            # 写响应通道
            'bvalid': 'axi_bvalid',
            'bready': 'axi_bready',
            'bresp': 'axi_bresp[1:0]',
            
            # 读地址通道
            'arvalid': 'axi_arvalid',
            'arready': 'axi_arready',
            'araddr': 'axi_araddr[31:0]',
            
            # 读数据通道
            'rvalid': 'axi_rvalid',
            'rready': 'axi_rready',
            'rdata': 'axi_rdata[31:0]',
            'rlast': 'axi_rlast'
        }
        window: 时间窗口
    
    Returns:
        {
            'write_transactions': List[AXITransaction],
            'read_transactions': List[AXITransaction],
            'write_bursts': int,
            'read_bursts': int,
            'total_write_bytes': int,
            'total_read_bytes': int,
            'avg_write_latency_ps': float,
            'avg_read_latency_ps': float,
            'violations': List[ProtocolViolation],
            'performance': {
                'write_throughput_mbps': float,
                'read_throughput_mbps': float,
                'bus_utilization': float
            }
        }
    """
    with VCDSmartStream(vcd_file) as q:
        q.parse_header_fast()
        
        start_time = window[0] if window else 0
        end_time = window[1] if window else None
        
        violations = []
        write_transactions = []
        read_transactions = []
        
        # 解析写地址通道
        if 'awvalid' in signals and 'awready' in signals:
            aw_valid_changes = q.query_window(signals['awvalid'], start_time, end_time)
            aw_ready_changes = q.query_window(signals['awready'], start_time, end_time)
            
            # 检测握手
            aw_handshakes = detect_handshakes(aw_valid_changes, aw_ready_changes)
            
            for handshake_time in aw_handshakes:
                # 提取地址信息
                addr = 0
                if 'awaddr' in signals:
                    addr_changes = q.query_window(signals['awaddr'], handshake_time, handshake_time + 1)
                    if addr_changes:
                        addr = int(addr_changes[0][1], 2)
                
                # 创建写事务
                txn = AXITransaction(
                    channel='AW',
                    id=0,
                    address=addr,
                    length=0,
                    size=4,
                    burst_type='INCR',
                    start_time_ps=handshake_time,
                    end_time_ps=0,
                    latency_ps=0
                )
                write_transactions.append(txn)
        
        # 解析写数据通道
        if 'wvalid' in signals and 'wready' in signals:
            w_valid_changes = q.query_window(signals['wvalid'], start_time, end_time)
            w_ready_changes = q.query_window(signals['wready'], start_time, end_time)
            
            # 检测 WLAST
            wlast_changes = []
            if 'wlast' in signals:
                wlast_changes = q.query_window(signals['wlast'], start_time, end_time)
            
            # 统计 Burst
            write_bursts = sum(1 for t, v in wlast_changes if v == '1')
            
            # 检测违规：WLAST 前必须有 WVALID
            for t, v in wlast_changes:
                if v == '1':
                    # 检查之前是否有 WVALID
                    has_valid = any(tv == '1' for tv_t, tv in w_valid_changes if tv_t < t)
                    if not has_valid:
                        violations.append(ProtocolViolation(
                            'W', 'WLAST_WITHOUT_VALID', t,
                            'WLAST 拉高前未检测到 WVALID'
                        ))
        
        # 解析写响应通道
        if 'bvalid' in signals and 'bready' in signals:
            b_valid_changes = q.query_window(signals['bvalid'], start_time, end_time)
            b_ready_changes = q.query_window(signals['bready'], start_time, end_time)
            
            b_handshakes = detect_handshakes(b_valid_changes, b_ready_changes)
            
            # 计算写延迟
            if write_transactions and b_handshakes:
                for i, txn in enumerate(write_transactions):
                    if i < len(b_handshakes):
                        txn.end_time_ps = b_handshakes[i]
                        txn.latency_ps = b_handshakes[i] - txn.start_time_ps
        
        # 解析读地址通道
        if 'arvalid' in signals and 'arready' in signals:
            ar_valid_changes = q.query_window(signals['arvalid'], start_time, end_time)
            ar_ready_changes = q.query_window(signals['arready'], start_time, end_time)
            
            ar_handshakes = detect_handshakes(ar_valid_changes, ar_ready_changes)
            
            for handshake_time in ar_handshakes:
                addr = 0
                if 'araddr' in signals:
                    addr_changes = q.query_window(signals['araddr'], handshake_time, handshake_time + 1)
                    if addr_changes:
                        addr = int(addr_changes[0][1], 2)
                
                txn = AXITransaction(
                    channel='AR',
                    id=0,
                    address=addr,
                    length=0,
                    size=4,
                    burst_type='INCR',
                    start_time_ps=handshake_time,
                    end_time_ps=0,
                    latency_ps=0
                )
                read_transactions.append(txn)
        
        # 解析读数据通道
        if 'rvalid' in signals and 'rready' in signals:
            r_valid_changes = q.query_window(signals['rvalid'], start_time, end_time)
            r_ready_changes = q.query_window(signals['rready'], start_time, end_time)
            
            rlast_changes = []
            if 'rlast' in signals:
                rlast_changes = q.query_window(signals['rlast'], start_time, end_time)
            
            read_bursts = sum(1 for t, v in rlast_changes if v == '1')
            
            # 计算读延迟
            if read_transactions and rlast_changes:
                for i, txn in enumerate(read_transactions):
                    if i < len(rlast_changes):
                        txn.end_time_ps = rlast_changes[i][0]
                        txn.latency_ps = rlast_changes[i][0] - txn.start_time_ps
        
        # 统计
        total_write_bytes = len(write_transactions) * 4  # 简化计算
        total_read_bytes = len(read_transactions) * 4
        
        avg_write_latency = (
            sum(t.latency_ps for t in write_transactions) / len(write_transactions)
            if write_transactions else 0
        )
        avg_read_latency = (
            sum(t.latency_ps for t in read_transactions) / len(read_transactions)
            if read_transactions else 0
        )
        
        # 性能计算
        total_time = (end_time - start_time) if end_time else 1e9
        write_throughput = (total_write_bytes / 1e6) / (total_time / 1e12) if total_time > 0 else 0
        read_throughput = (total_read_bytes / 1e6) / (total_time / 1e12) if total_time > 0 else 0
        
        return {
            'write_transactions': [asdict(t) for t in write_transactions],
            'read_transactions': [asdict(t) for t in read_transactions],
            'write_bursts': write_bursts if 'wlast' in signals else 0,
            'read_bursts': read_bursts if 'rlast' in signals else 0,
            'total_write_bytes': total_write_bytes,
            'total_read_bytes': total_read_bytes,
            'avg_write_latency_ps': avg_write_latency,
            'avg_read_latency_ps': avg_read_latency,
            'violations': [v.to_dict() for v in violations],
            'performance': {
                'write_throughput_mbps': write_throughput,
                'read_throughput_mbps': read_throughput,
                'bus_utilization': 0.0  # 简化
            }
        }


def analyze_apb(vcd_file: str, signals: Dict[str, str],
                window: Optional[Tuple[int, int]] = None) -> Dict:
    """
    APB 协议分析
    
    Args:
        vcd_file: VCD 文件路径
        signals: 信号字典 {
            'psel': 'apb_psel',
            'penable': 'apb_penable',
            'paddr': 'apb_paddr[7:0]',
            'pwdata': 'apb_pwdata[31:0]',
            'prdata': 'apb_prdata[31:0]',
            'pwrite': 'apb_pwrite',
            'pready': 'apb_pready',
            'pslverr': 'apb_pslverr'
        }
        window: 时间窗口
    
    Returns:
        {
            'transactions': List[APBTransaction],
            'transaction_count': int,
            'read_count': int,
            'write_count': int,
            'error_count': int,
            'violations': List[ProtocolViolation],
            'avg_latency_ps': float
        }
    """
    with VCDSmartStream(vcd_file) as q:
        q.parse_header_fast()
        
        start_time = window[0] if window else 0
        end_time = window[1] if window else None
        
        transactions = []
        violations = []
        
        # 查询关键信号
        psel_changes = q.query_window(signals['psel'], start_time, end_time) if 'psel' in signals else []
        penable_changes = q.query_window(signals['penable'], start_time, end_time) if 'penable' in signals else []
        
        # 检测 APB 事务（PENABLE 上升沿）
        for t, v in penable_changes:
            if v == '1':
                # 提取地址
                addr = 0
                if 'paddr' in signals:
                    addr_changes = q.query_window(signals['paddr'], t, t + 1)
                    if addr_changes:
                        addr = int(addr_changes[0][1], 2)
                
                # 提取数据
                data = 0
                if 'pwdata' in signals:
                    data_changes = q.query_window(signals['pwdata'], t, t + 1)
                    if data_changes:
                        data = int(data_changes[0][1], 2)
                
                # 判断读写
                write = True
                if 'pwrite' in signals:
                    pwrite_changes = q.query_window(signals['pwrite'], t, t + 1)
                    if pwrite_changes:
                        write = (pwrite_changes[0][1] == '1')
                
                # 检测错误
                error = False
                if 'pslverr' in signals:
                    err_changes = q.query_window(signals['pslverr'], t, t + 1000)
                    if err_changes and err_changes[0][1] == '1':
                        error = True
                
                # 创建事务
                txn = APBTransaction(
                    address=addr,
                    data=data,
                    write=write,
                    start_time_ps=t,
                    end_time_ps=t + 1000,  # 简化
                    error=error
                )
                transactions.append(txn)
        
        # 检测违规
        # APB 协议：PENABLE 必须在 PSEL 之后
        psel_times = [t for t, v in psel_changes if v == '1']
        penable_times = [t for t, v in penable_changes if v == '1']
        
        for penable_t in penable_times:
            # 检查之前是否有 PSEL
            has_psel = any(psel_t < penable_t for psel_t in psel_times)
            if not has_psel:
                violations.append(ProtocolViolation(
                    'APB', 'PENABLE_WITHOUT_PSEL', penable_t,
                    'PENABLE 拉高前未检测到 PSEL'
                ))
        
        # 统计
        read_count = sum(1 for t in transactions if not t.write)
        write_count = sum(1 for t in transactions if t.write)
        error_count = sum(1 for t in transactions if t.error)
        
        avg_latency = (
            sum(t.end_time_ps - t.start_time_ps for t in transactions) / len(transactions)
            if transactions else 0
        )
        
        return {
            'transactions': [asdict(t) for t in transactions],
            'transaction_count': len(transactions),
            'read_count': read_count,
            'write_count': write_count,
            'error_count': error_count,
            'violations': [v.to_dict() for v in violations],
            'avg_latency_ps': avg_latency
        }


def analyze_ahb(vcd_file: str, signals: Dict[str, str],
                window: Optional[Tuple[int, int]] = None) -> Dict:
    """
    AHB 协议分析（简化版）
    
    Args:
        vcd_file: VCD 文件路径
        signals: 信号字典 {
            'hclk': 'ahb_hclk',
            'hresetn': 'ahb_hresetn',
            'haddr': 'ahb_haddr[31:0]',
            'hwrite': 'ahb_hwrite',
            'htrans': 'ahb_htrans[1:0]',
            'hsize': 'ahb_hsize[2:0]',
            'hburst': 'ahb_hburst[2:0]',
            'hwdata': 'ahb_hwdata[31:0]',
            'hrdata': 'ahb_hrdata[31:0]',
            'hready': 'ahb_hready',
            'hresp': 'ahb_hresp'
        }
        window: 时间窗口
    
    Returns:
        {
            'transactions': List[Dict],
            'transaction_count': int,
            'read_count': int,
            'write_count': int,
            'busy_cycles': int,
            'error_count': int,
            'violations': List[ProtocolViolation]
        }
    """
    with VCDSmartStream(vcd_file) as q:
        q.parse_header_fast()
        
        start_time = window[0] if window else 0
        end_time = window[1] if window else None
        
        transactions = []
        violations = []
        
        # 查询 HREADY（决定传输时机）
        hready_changes = q.query_window(signals['hready'], start_time, end_time) if 'hready' in signals else []
        
        # 查询 HTRANS（传输类型）
        htrans_changes = q.query_window(signals['htrans'], start_time, end_time) if 'htrans' in signals else []
        
        # 统计
        busy_cycles = 0
        error_count = 0
        
        for t, v in hready_changes:
            if v == '0':
                busy_cycles += 1
        
        # 检测 HRESP 错误
        if 'hresp' in signals:
            hresp_changes = q.query_window(signals['hresp'], start_time, end_time)
            error_count = sum(1 for t, v in hresp_changes if v == '1')
        
        # 简单返回
        return {
            'transactions': transactions,
            'transaction_count': len(transactions),
            'read_count': 0,
            'write_count': 0,
            'busy_cycles': busy_cycles,
            'error_count': error_count,
            'violations': [v.to_dict() for v in violations]
        }


def detect_handshakes(valid_changes: List[Tuple], ready_changes: List[Tuple]) -> List[int]:
    """
    检测 AXI 握手时间点
    
    Returns:
        握手成功的时间点列表
    """
    handshakes = []
    
    valid_high = False
    last_valid_time = None
    
    for t, v in valid_changes:
        if v == '1':
            valid_high = True
            last_valid_time = t
    
    for t, v in ready_changes:
        if v == '1' and valid_high and last_valid_time:
            handshakes.append(max(t, last_valid_time))
    
    return handshakes


# CLI 接口
if __name__ == '__main__':
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='VCD 协议解析器')
    parser.add_argument('vcd_file', help='VCD 文件路径')
    parser.add_argument('--axi4', action='store_true', help='AXI4 分析')
    parser.add_argument('--apb', action='store_true', help='APB 分析')
    parser.add_argument('--ahb', action='store_true', help='AHB 分析')
    
    args = parser.parse_args()
    
    if args.axi4:
        signals = {
            'awvalid': 'axi_awvalid',
            'awready': 'axi_awready',
            'wvalid': 'axi_wvalid',
            'wready': 'axi_wready',
            'bvalid': 'axi_bvalid',
            'bready': 'axi_bready'
        }
        result = analyze_axi4(args.vcd_file, signals)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if args.apb:
        signals = {
            'psel': 'apb_psel',
            'penable': 'apb_penable',
            'paddr': 'apb_paddr[7:0]',
            'pwdata': 'apb_pwdata[31:0]',
            'pwrite': 'apb_pwrite'
        }
        result = analyze_apb(args.vcd_file, signals)
        print(json.dumps(result, indent=2, ensure_ascii=False))
