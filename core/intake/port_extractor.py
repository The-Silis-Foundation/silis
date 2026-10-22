"""
Unified Port & Interface Extractor for SILIS Intake Engine.
Normalizes ports across VHDL, SystemVerilog, and Verilog into PortSpec dataclasses.
Classifies clocks, resets, UART, SPI, GPIO, and buses.
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Optional
from .source_scanner import SourceFile


@dataclass
class PortSpec:
    name: str
    direction: str          # 'input' | 'output' | 'inout'
    width: int = 1          # Number of bits
    port_type: str = "data" # 'clock' | 'reset' | 'data' | 'uart' | 'spi' | 'gpio'
    raw_type: str = ""


CLOCK_KEYWORDS = ("clk", "clock", "aclk", "clk_i", "sys_clk", "clk_p", "pclk", "hclk", "mclk")
RESET_KEYWORDS = ("rst", "reset", "rst_n", "rstn_i", "rstn", "aresetn", "n_rst", "sys_rst")
UART_KEYWORDS  = ("uart_rxd", "uart_txd", "rxd", "txd", "rx", "tx", "uart_rx", "uart_tx")
SPI_KEYWORDS   = ("spi_sclk", "spi_mosi", "spi_miso", "spi_csn", "sclk", "mosi", "miso", "csn")
GPIO_KEYWORDS  = ("gpio", "gpio_in", "gpio_out", "gpi", "gpo")


def classify_port_type(name: str, direction: str) -> str:
    n_lower = name.lower()
    if any(k == n_lower or n_lower.startswith(k + "_") or n_lower.endswith("_" + k) for k in CLOCK_KEYWORDS):
        return "clock"
    if any(k == n_lower or n_lower.startswith(k + "_") or n_lower.endswith("_" + k) for k in RESET_KEYWORDS):
        return "reset"
    if any(k in n_lower for k in UART_KEYWORDS):
        return "uart"
    if any(k in n_lower for k in SPI_KEYWORDS):
        return "spi"
    if any(k in n_lower for k in GPIO_KEYWORDS):
        return "gpio"
    return "data"


def extract_vhdl_ports(content: str, entity_name: str) -> List[PortSpec]:
    ports: List[PortSpec] = []
    clean_lines = [line.split('--')[0] for line in content.splitlines()]
    clean_text = "\n".join(clean_lines)

    # Match: entity <name> is ... port ( ... ); end;
    m_entity = re.search(
        rf'\bentity\s+{re.escape(entity_name)}\s+is\b.*?\bport\s*\((.*?)\)\s*;\s*end\b',
        clean_text,
        re.IGNORECASE | re.DOTALL
    )
    if not m_entity:
        return ports

    port_block = m_entity.group(1)

    # Individual port clauses: name1, name2 : [in|out|inout] type;
    for stmt in port_block.split(';'):
        stmt = stmt.strip()
        if not stmt or ':' not in stmt:
            continue

        parts = stmt.split(':', 1)
        names_str, type_str = parts[0].strip(), parts[1].strip()

        # Extract direction
        dir_match = re.match(r'^(in|out|inout|buffer)\b', type_str, re.IGNORECASE)
        direction = dir_match.group(1).lower() if dir_match else "input"
        if direction == "buffer":
            direction = "output"

        # Calculate bit width
        width = 1
        w_match = re.search(r'\((\d+)\s+downto\s+(\d+)\)', type_str, re.IGNORECASE)
        if w_match:
            hi, lo = int(w_match.group(1)), int(w_match.group(2))
            width = abs(hi - lo) + 1

        for pname in [n.strip() for n in names_str.split(',') if n.strip()]:
            ports.append(PortSpec(
                name=pname,
                direction=direction,
                width=width,
                port_type=classify_port_type(pname, direction),
                raw_type=type_str
            ))

    return ports


def extract_verilog_ports(content: str, module_name: str) -> List[PortSpec]:
    ports: List[PortSpec] = []
    clean_text = re.sub(r'//.*', '', content)
    clean_text = re.sub(r'/\*.*?\*/', '', clean_text, flags=re.DOTALL)

    # Match module definition
    m_mod = re.search(
        rf'\bmodule\s+{re.escape(module_name)}\b(?:\s*#\s*\(.*?\))?\s*\((.*?)\);(.*?)\bendmodule\b',
        clean_text,
        re.DOTALL
    )
    if not m_mod:
        return ports

    header_text, body_text = m_mod.group(1), m_mod.group(2)
    combined = header_text + "\n" + body_text

    for pm in re.finditer(
        r'(?:^|[;,(\s])\s*(input|output|inout)\s+(?:wire\s+|reg\s+|logic\s+)?(?:signed\s+)?(?:\[(\d+):(\d+)\]\s+)?([^;,)]+)',
        combined,
        re.MULTILINE
    ):
        pdir = pm.group(1).lower()
        msb, lsb = pm.group(2), pm.group(3)
        names_str = pm.group(4)
        width = (abs(int(msb) - int(lsb)) + 1) if (msb is not None and lsb is not None) else 1

        for pname in [n.strip() for n in names_str.split(',') if n.strip()]:
            pname = re.sub(r'\s*=.*$', '', pname).strip()
            if not pname or pname.startswith("//"):
                continue
            ports.append(PortSpec(
                name=pname,
                direction=pdir,
                width=width,
                port_type=classify_port_type(pname, pdir),
                raw_type=f"[{msb}:{lsb}]" if msb else "1-bit"
            ))

    return ports


def extract_ports(source_file: SourceFile, top_name: str) -> List[PortSpec]:
    try:
        with open(source_file.path, 'r', errors='ignore') as f:
            content = f.read()
    except Exception:
        return []

    if source_file.lang == 'vhdl':
        return extract_vhdl_ports(content, top_name)
    else:
        return extract_verilog_ports(content, top_name)
