"""
SILIS Intake & Transpilation Framework.
Supports source scanning, dependency graph construction, top-level detection,
and automated lowering for VHDL, SystemVerilog, and Verilog designs.
"""

from .source_scanner import SourceFile, scan_sources
from .dependency_graph import DependencyGraph, topological_sort
from .top_finder import find_top_candidates, classify_testbench
from .port_extractor import PortSpec, extract_ports

__all__ = [
    "SourceFile",
    "scan_sources",
    "DependencyGraph",
    "topological_sort",
    "find_top_candidates",
    "classify_testbench",
    "PortSpec",
    "extract_ports",
]
