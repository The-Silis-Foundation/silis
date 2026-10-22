"""
Source Scanner for SILIS Intake Engine.
Crawls directories, identifies HDL dialects, parses declared and required units,
and detects verification testbenches.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Tuple, Set


@dataclass(eq=False)
class SourceFile:
    path: str
    lang: str                  # 'vhdl' | 'sv' | 'verilog'
    std: str = "08"            # e.g., '08', '2012'
    declared_units: List[str] = field(default_factory=list)
    required_units: List[str] = field(default_factory=list)
    is_testbench: bool = False
    tier: int = 0              # Topological compilation tier

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        if not isinstance(other, SourceFile):
            return False
        return self.path == other.path


# --- Language Detection ---
def detect_language(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.vhd', '.vhdl', '.vhd2008'):
        return 'vhdl'
    elif ext in ('.sv', '.svh'):
        return 'sv'
    elif ext in ('.v', '.vh'):
        return 'verilog'
    return 'unknown'


# --- Unit Extraction ---
def extract_vhdl_units(content: str) -> Tuple[List[str], List[str]]:
    """
    Extracts declared entities/packages and required dependencies from VHDL.
    """
    declared = []
    required = []

    # Strip line comments
    clean_lines = []
    for line in content.splitlines():
        line_no_comment = line.split('--')[0]
        clean_lines.append(line_no_comment)
    clean_text = "\n".join(clean_lines)

    # Declared entities: entity <name> is
    for m in re.finditer(r'\bentity\s+(\w+)\s+is\b', clean_text, re.IGNORECASE):
        declared.append(m.group(1).lower())

    # Declared packages: package <name> is
    for m in re.finditer(r'\bpackage\s+(\w+)\s+is\b', clean_text, re.IGNORECASE):
        pkg_name = m.group(1).lower()
        if "body" not in clean_text[max(0, m.start()-10):m.start()].lower():
            declared.append(pkg_name)

    # Dependencies: use work.<pkg>.all or use <lib>.<pkg>.all
    for m in re.finditer(r'\buse\s+(?:\w+)\.(\w+)(?:\.all)?\b', clean_text, re.IGNORECASE):
        pkg = m.group(1).lower()
        if pkg not in ('std_logic_1164', 'numeric_std', 'numeric_std_unsigned', 'std_logic_arith', 'std_logic_unsigned'):
            required.append(pkg)

    # Direct entity instantiations: <label>: entity <work>.<entity_name>
    for m in re.finditer(r':\s*entity\s+(?:\w+)\.(\w+)\b', clean_text, re.IGNORECASE):
        required.append(m.group(1).lower())

    # Component declarations: component <name> is ... or component <name> port ...
    for m in re.finditer(r'\bcomponent\s+(\w+)\b', clean_text, re.IGNORECASE):
        cname = m.group(1).lower()
        if cname not in declared and cname not in required:
            required.append(cname)

    return list(dict.fromkeys(declared)), list(dict.fromkeys(required))


def extract_verilog_units(content: str) -> Tuple[List[str], List[str]]:
    """
    Extracts declared modules/packages/interfaces and instantiations from Verilog / SystemVerilog.
    """
    declared = []
    required = []

    # Strip single line comments and block comments
    clean_text = re.sub(r'//.*', '', content)
    clean_text = re.sub(r'/\*.*?\*/', '', clean_text, flags=re.DOTALL)

    # Declared modules
    for m in re.finditer(r'\bmodule\s+(\w+)\b', clean_text):
        declared.append(m.group(1))

    # Declared SystemVerilog packages
    for m in re.finditer(r'\bpackage\s+(\w+)\b', clean_text):
        declared.append(m.group(1))

    # Declared interfaces
    for m in re.finditer(r'\binterface\s+(\w+)\b', clean_text):
        declared.append(m.group(1))

    # SV package imports: import <pkg>::*;
    for m in re.finditer(r'\bimport\s+(\w+)::\*;', clean_text):
        required.append(m.group(1))

    # Standard instantiation patterns: child_module #(...) inst_name (...)
    # Match word followed by #(...) or word followed by identifier and (
    for m in re.finditer(r'^\s*([A-Za-z_]\w*)\s*(?:#\s*\(.*?\)\s*)?([A-Za-z_]\w*)\s*\(', clean_text, re.MULTILINE):
        cell_or_mod = m.group(1)
        # Filter standard verilog keywords
        if cell_or_mod not in ('module', 'always', 'initial', 'assign', 'function', 'task', 'if', 'else', 'case', 'for', 'generate'):
            required.append(cell_or_mod)

    return list(dict.fromkeys(declared)), list(dict.fromkeys(required))


# --- Testbench Classifier ---
def is_testbench_content(path: str, lang: str, content: str, declared_units: List[str]) -> bool:
    name = os.path.basename(path).lower()

    # 1. Filename heuristic
    if any(pat in name for pat in ('_tb.', 'testbench.', '_sim.', 'tb_', '_test.')):
        return True

    # Clean text
    clean_text = re.sub(r'//.*', '', content)
    clean_text = re.sub(r'--.*', '', clean_text)
    clean_text = re.sub(r'/\*.*?\*/', '', clean_text, flags=re.DOTALL)

    if lang == 'vhdl':
        # VHDL testbenches almost universally have an entity with NO ports
        for unit in declared_units:
            m = re.search(rf'\bentity\s+{re.escape(unit)}\s+is\s*(?:generic\s*\([^)]*\)\s*;)?\s*end\b', clean_text, re.IGNORECASE)
            if m:
                return True
        # Simulation delay or file operations
        if re.search(r'\bwait\s+for\s+\d+\s*(?:ns|ps|us|ms)\b', clean_text, re.IGNORECASE):
            return True

    elif lang in ('sv', 'verilog'):
        # Empty port list or simulation tasks
        if re.search(r'\bmodule\s+\w+\s*;\s*', clean_text):
            return True
        if any(sim_kw in clean_text for sim_kw in ('$dumpfile', '$dumpvars', '$finish', '$stop', '#10', '#100')):
            return True

    return False


# --- Main Scanner Entry ---
def scan_sources(paths: List[str]) -> List[SourceFile]:
    """
    Crawls directories or list of file paths, tags files, and extracts units.
    """
    file_list = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in ('.vhd', '.vhdl', '.vhd2008', '.sv', '.svh', '.v', '.vh'):
                        file_list.append(os.path.join(root, f))
        elif os.path.isfile(p):
            file_list.append(p)

    results: List[SourceFile] = []
    for fpath in sorted(list(dict.fromkeys(file_list))):
        fpath = os.path.abspath(fpath)
        lang = detect_language(fpath)
        if lang == 'unknown':
            continue

        try:
            with open(fpath, 'r', errors='ignore') as f:
                content = f.read()
        except Exception:
            continue

        if lang == 'vhdl':
            declared, required = extract_vhdl_units(content)
        else:
            declared, required = extract_verilog_units(content)

        tb = is_testbench_content(fpath, lang, content, declared)

        results.append(SourceFile(
            path=fpath,
            lang=lang,
            std="08" if lang == 'vhdl' else "2012",
            declared_units=declared,
            required_units=required,
            is_testbench=tb
        ))

    return results
