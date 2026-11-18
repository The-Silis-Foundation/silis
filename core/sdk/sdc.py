"""
silis/sdk/sdc.py
In-Memory Synopsys Design Constraints (SDC) Builder and SC Timing Parser.
Supports programmatic clock, IO delay, and false path generation without touching disk.
"""

import os
import re
from typing import List, Dict, Tuple, Optional, Union, Any


class SDCBuilder:
    """
    Pure Python In-Memory Synopsys Design Constraints (SDC) Builder.
    Allows programmatic constraint generation and bidirectional SC conversion.
    """

    def __init__(self, design_name: str = "top"):
        self.design_name = design_name
        self.clocks: Dict[str, Dict[str, Any]] = {}
        self.input_delays: List[Dict[str, Any]] = []
        self.output_delays: List[Dict[str, Any]] = []
        self.loads: List[Dict[str, Any]] = []
        self.driving_cells: List[Dict[str, Any]] = []
        self.false_paths: List[Dict[str, Any]] = []
        self.multicycle_paths: List[Dict[str, Any]] = []
        self.raw_commands: List[str] = []

    def create_clock(
        self,
        name: str,
        period: float,
        pin: Optional[str] = None,
        waveform: Optional[Tuple[float, float]] = None,
        uncertainty: Optional[float] = None,
        transition: Optional[float] = None,
    ) -> "SDCBuilder":
        """
        Defines a clock constraint with optional uncertainty and transition.
        """
        if period <= 0:
            raise ValueError(f"Clock period must be positive, got {period}")
        wf = waveform if waveform else (0.0, period / 2.0)
        self.clocks[name] = {
            "period": float(period),
            "pin": pin or name,
            "waveform": wf,
            "uncertainty": float(uncertainty) if uncertainty is not None else None,
            "transition": float(transition) if transition is not None else None,
        }
        self._last_clock = name
        return self

    def clock(
        self,
        name: str,
        period: float,
        pin: Optional[str] = None,
        waveform: Optional[Tuple[float, float]] = None,
        uncertainty: Optional[float] = None,
        transition: Optional[float] = None,
    ) -> "SDCBuilder":
        """Concise alias for create_clock with all timing parameters in one line."""
        return self.create_clock(
            name=name,
            period=period,
            pin=pin,
            waveform=waveform,
            uncertainty=uncertainty,
            transition=transition,
        )

    def inputs(
        self,
        delay: float,
        pins: Union[str, List[str]],
        clock: Optional[str] = None,
        max_delay: bool = True,
        min_delay: bool = False,
    ) -> "SDCBuilder":
        """Fluent helper for set_input_delay defaulting to the most recently created clock."""
        clk = clock or getattr(self, "_last_clock", None)
        if not clk and self.clocks:
            clk = list(self.clocks.keys())[-1]
        return self.set_input_delay(value=delay, clock=clk, pins=pins, max_delay=max_delay, min_delay=min_delay)

    def outputs(
        self,
        delay: float,
        pins: Union[str, List[str]],
        clock: Optional[str] = None,
        max_delay: bool = True,
        min_delay: bool = False,
    ) -> "SDCBuilder":
        """Fluent helper for set_output_delay defaulting to the most recently created clock."""
        clk = clock or getattr(self, "_last_clock", None)
        if not clk and self.clocks:
            clk = list(self.clocks.keys())[-1]
        return self.set_output_delay(value=delay, clock=clk, pins=pins, max_delay=max_delay, min_delay=min_delay)

    def set_clock_uncertainty(self, value: float, clock: Optional[str] = None) -> "SDCBuilder":
        """Sets clock uncertainty (jitter). If clock is None, applies globally."""
        if clock and clock in self.clocks:
            self.clocks[clock]["uncertainty"] = float(value)
        else:
            for c in self.clocks.values():
                c["uncertainty"] = float(value)
        return self

    def set_clock_transition(self, rise: float, fall: Optional[float] = None, clock: Optional[str] = None) -> "SDCBuilder":
        """Sets clock transition slew rate."""
        val = float(rise)
        if clock and clock in self.clocks:
            self.clocks[clock]["transition"] = val
        else:
            for c in self.clocks.values():
                c["transition"] = val
        return self

    def set_input_delay(
        self,
        value: float,
        clock: str,
        pins: Union[str, List[str]],
        max_delay: bool = True,
        min_delay: bool = False,
    ) -> "SDCBuilder":
        """Adds set_input_delay constraint."""
        pin_list = [pins] if isinstance(pins, str) else list(pins)
        self.input_delays.append({
            "val": float(value),
            "clock": clock,
            "pins": pin_list,
            "max": max_delay,
            "min": min_delay,
        })
        return self

    def set_output_delay(
        self,
        value: float,
        clock: str,
        pins: Union[str, List[str]],
        max_delay: bool = True,
        min_delay: bool = False,
    ) -> "SDCBuilder":
        """Adds set_output_delay constraint."""
        pin_list = [pins] if isinstance(pins, str) else list(pins)
        self.output_delays.append({
            "val": float(value),
            "clock": clock,
            "pins": pin_list,
            "max": max_delay,
            "min": min_delay,
        })
        return self

    def set_load(self, value: float, pins: Union[str, List[str]]) -> "SDCBuilder":
        """Sets capacitive output load in pF."""
        pin_list = [pins] if isinstance(pins, str) else list(pins)
        self.loads.append({"val": float(value), "pins": pin_list})
        return self

    def set_driving_cell(
        self,
        cell: str,
        pin: Optional[str] = None,
        input_pins: Union[str, List[str]] = "[all_inputs]",
    ) -> "SDCBuilder":
        """Sets driving cell for input ports."""
        pins = [input_pins] if isinstance(input_pins, str) else list(input_pins)
        self.driving_cells.append({"cell": cell, "pin": pin, "pins": pins})
        return self

    def set_false_path(
        self,
        from_pins: Optional[Union[str, List[str]]] = None,
        to_pins: Optional[Union[str, List[str]]] = None,
        through: Optional[Union[str, List[str]]] = None,
    ) -> "SDCBuilder":
        """Defines a false path timing exception."""
        self.false_paths.append({
            "from": [from_pins] if isinstance(from_pins, str) else from_pins,
            "to": [to_pins] if isinstance(to_pins, str) else to_pins,
            "through": [through] if isinstance(through, str) else through,
        })
        return self

    def set_multicycle_path(
        self,
        cycles: int,
        from_pins: Optional[Union[str, List[str]]] = None,
        to_pins: Optional[Union[str, List[str]]] = None,
        setup: bool = True,
        hold: bool = False,
    ) -> "SDCBuilder":
        """Defines a multicycle path timing exception."""
        self.multicycle_paths.append({
            "cycles": int(cycles),
            "from": [from_pins] if isinstance(from_pins, str) else from_pins,
            "to": [to_pins] if isinstance(to_pins, str) else to_pins,
            "setup": setup,
            "hold": hold,
        })
        return self

    def add_raw(self, tcl_cmd: str) -> "SDCBuilder":
        """Appends arbitrary raw SDC/TCL constraint line."""
        self.raw_commands.append(tcl_cmd.strip())
        return self

    def to_string(self) -> str:
        """Serializes the constraints into clean, standard SDC format."""
        lines = [
            f"# ========================================================",
            f"# In-Memory SDC Constraints for: {self.design_name}",
            f"# Generated by Silis SDCBuilder",
            f"# ========================================================",
            f"current_design {self.design_name}\n",
        ]

        # 1. Clocks
        for cname, cdata in self.clocks.items():
            pin_target = f"[get_ports {{{cdata['pin']}}}]" if cdata["pin"] else ""
            lines.append(
                f"create_clock -name {cname} -period {cdata['period']:.3f} "
                f"-waveform {{{cdata['waveform'][0]:.3f} {cdata['waveform'][1]:.3f}}} {pin_target}"
            )
            if cdata.get("uncertainty") is not None:
                lines.append(f"set_clock_uncertainty {cdata['uncertainty']:.3f} [get_clocks {cname}]")
            if cdata.get("transition") is not None:
                lines.append(f"set_clock_transition {cdata['transition']:.3f} [get_clocks {cname}]")

        if self.clocks:
            lines.append("")

        # 2. Driving Cell
        for dc in self.driving_cells:
            pin_opt = f"-pin {dc['pin']}" if dc.get("pin") else ""
            for p in dc["pins"]:
                lines.append(f"set_driving_cell -lib_cell {dc['cell']} {pin_opt} {p}")

        # 3. Input Delays
        for item in self.input_delays:
            flag = "-max" if item["max"] and not item["min"] else ("-min" if item["min"] and not item["max"] else "")
            for p in item["pins"]:
                lines.append(f"set_input_delay {flag} {item['val']:.3f} -clock [get_clocks {item['clock']}] [get_ports {{{p}}}]")

        # 4. Output Delays
        for item in self.output_delays:
            flag = "-max" if item["max"] and not item["min"] else ("-min" if item["min"] and not item["max"] else "")
            for p in item["pins"]:
                lines.append(f"set_output_delay {flag} {item['val']:.3f} -clock [get_clocks {item['clock']}] [get_ports {{{p}}}]")

        # 5. Loads
        for ld in self.loads:
            for p in ld["pins"]:
                lines.append(f"set_load {ld['val']:.3f} [get_ports {{{p}}}]")

        # 6. False Paths
        for fp in self.false_paths:
            cmd = "set_false_path"
            if fp.get("from"):
                cmd += f" -from [get_ports {{{' '.join(fp['from'])}}}]"
            if fp.get("to"):
                cmd += f" -to [get_ports {{{' '.join(fp['to'])}}}]"
            if fp.get("through"):
                cmd += f" -through [get_pins {{{' '.join(fp['through'])}}}]"
            lines.append(cmd)

        # 7. Multicycle Paths
        for mp in self.multicycle_paths:
            flag = "-setup" if mp.get("setup") and not mp.get("hold") else ("-hold" if mp.get("hold") and not mp.get("setup") else "")
            cmd = f"set_multicycle_path {mp['cycles']} {flag}"
            if mp.get("from"):
                cmd += f" -from [get_ports {{{' '.join(mp['from'])}}}]"
            if mp.get("to"):
                cmd += f" -to [get_ports {{{' '.join(mp['to'])}}}]"
            lines.append(cmd)

        # 8. Raw Commands
        for raw in self.raw_commands:
            lines.append(raw)

        return "\n".join(lines) + "\n"

    def write(self, file_path: str) -> str:
        """Writes the in-memory SDC to disk."""
        abs_path = os.path.abspath(file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w") as f:
            f.write(self.to_string())
        return abs_path

    @classmethod
    def from_sc_chip(cls, chip) -> "SDCBuilder":
        """
        Extracts timing constraints and datasheet clock declarations from a
        SiliconCompiler chip object into an in-memory SDCBuilder instance.
        """
        design = getattr(chip, "name", None) or getattr(chip, "design", None) or "top"
        builder = cls(design_name=design)

        # 1. Parse datasheet clock declarations
        try:
            if chip.valid("datasheet", "pin"):
                pins = chip.getkeys("datasheet", "pin")
                for p in pins:
                    ptype = chip.get("datasheet", "pin", p, "type")
                    if ptype == "clock":
                        period_val = chip.get("datasheet", "pin", p, "tperiod")
                        jitter_val = chip.get("datasheet", "pin", p, "tjitter")
                        period = float(period_val) if period_val else 10.0
                        builder.create_clock(name=p, period=period, pin=p)
                        if jitter_val:
                            builder.set_clock_uncertainty(float(jitter_val), clock=p)
        except Exception:
            pass

        # 2. Parse any registered SDC files in SC
        # Check modern SC 0.35+ Design filesets
        sdc_files = []
        try:
            if hasattr(chip, "get_filesets"):
                for d_obj, fset in chip.get_filesets():
                    if fset in ["sdc", "constraint", "constraints"]:
                        try:
                            files = d_obj.get_file(fileset=fset)
                            if files:
                                sdc_files.extend(files)
                        except Exception:
                            pass
        except Exception:
            pass

        # Fallback to legacy SC find_files schema
        if not sdc_files:
            try:
                found = chip.find_files("input", "constraint", "sdc", step="*", index="*")
                if found:
                    sdc_files.extend(found)
            except Exception:
                pass

        for sdc in sdc_files:
            try:
                if os.path.isfile(sdc):
                    with open(sdc, "r") as f:
                        builder.add_raw(f.read())
            except Exception:
                pass

        return builder

    def validate_against_netlist(
        self,
        netlist_path_or_content: str,
        top_module: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validates in-memory SDC clocks against a target netlist."""
        return validate_sdc_clocks_against_netlist(
            sdc_path_or_content=self.to_string(),
            netlist_path_or_content=netlist_path_or_content,
            top_module=top_module
        )


def extract_netlist_clock_ports(
    netlist_path_or_content: str,
    top_module: Optional[str] = None
) -> List[str]:
    """
    Extracts candidate clock input ports from a Verilog netlist file or string.
    Identifies ports classified as clocks or matching clock naming conventions.
    """
    content = netlist_path_or_content
    if os.path.isfile(netlist_path_or_content):
        try:
            with open(netlist_path_or_content, 'r', errors='ignore') as f:
                content = f.read()
        except Exception:
            return []

    clean_text = re.sub(r'//.*', '', content)
    clean_text = re.sub(r'/\*.*?\*/', '', clean_text, flags=re.DOTALL)

    mod_pattern = (
        rf'\bmodule\s+{re.escape(top_module)}\b(?:\s*#\s*\(.*?\))?\s*\((.*?)\);(.*?)\bendmodule\b'
        if top_module
        else r'\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)(?:\s*#\s*\(.*?\))?\s*\((.*?)\);(.*?)\bendmodule\b'
    )
    m = re.search(mod_pattern, clean_text, re.DOTALL)

    if not m:
        header_body = clean_text
    elif top_module:
        header_body = m.group(1) + "\n" + m.group(2)
    else:
        header_body = m.group(2) + "\n" + m.group(3)

    input_ports: List[str] = []
    for pm in re.finditer(
        r'(?:^|[;,(\s])\s*(?:input)\s+(?:wire\s+|reg\s+|logic\s+)?(?:signed\s+)?(?:\[\d+:\d+\]\s+)?([^;,)]+)',
        header_body,
        re.MULTILINE
    ):
        raw_names = pm.group(1)
        for name in raw_names.split(','):
            n = re.sub(r'\s*=.*$', '', name).strip()
            if n and re.match(r'^[A-Za-z_][A-Za-z0-9_$]*$', n):
                if n not in input_ports:
                    input_ports.append(n)

    clock_keywords = (
        "clk", "clock", "aclk", "clk_i", "sys_clk", "clk_p",
        "pclk", "hclk", "mclk", "clk_in", "core_clk", "wb_clk_i"
    )
    clocks: List[str] = []
    for p in input_ports:
        pl = p.lower()
        if any(k == pl or pl.startswith(k + "_") or pl.endswith("_" + k) or ("_" + k + "_") in pl for k in clock_keywords):
            clocks.append(p)

    return clocks if clocks else input_ports


def parse_sdc_clocks(sdc_path_or_content: str) -> List[Dict[str, Any]]:
    """
    Parses SDC text or file to extract all create_clock declarations,
    returning a list of dicts with name, period, and attached port/pin.
    """
    content = sdc_path_or_content
    if os.path.isfile(sdc_path_or_content):
        try:
            with open(sdc_path_or_content, 'r', errors='ignore') as f:
                content = f.read()
        except Exception:
            return []

    clean_text = re.sub(r'#.*', '', content)
    clocks: List[Dict[str, Any]] = []

    lines = clean_text.splitlines()
    merged_lines: List[str] = []
    curr_line = ""
    for line in lines:
        stripped = line.strip()
        if stripped.endswith('\\'):
            curr_line += " " + stripped[:-1]
        else:
            curr_line += " " + stripped
            if curr_line.strip():
                merged_lines.append(curr_line.strip())
            curr_line = ""

    for cmd in merged_lines:
        if not re.search(r'\bcreate_clock\b', cmd):
            continue

        m_name = re.search(r'-name\s+([A-Za-z0-9_$./\[\]]+|\{[^}]+\}|"[^"]+")', cmd)
        clk_name = m_name.group(1).strip('"{ }') if m_name else None

        m_period = re.search(r'-period\s+([-\d.]+)', cmd)
        period = float(m_period.group(1)) if m_period else 10.0

        m_port = re.search(r'\[\s*get_ports\s+(?:\{([^}]+)\}|"([^"]+)"|([A-Za-z0-9_$./\[\]]+))\s*\]', cmd)
        port_name = None
        if m_port:
            port_name = (m_port.group(1) or m_port.group(2) or m_port.group(3)).strip()
        else:
            # Strip recognized flag-value pairs to find positional port argument
            clean_cmd = re.sub(r'-(?:name|period|waveform|uncertainty|transition|add)\s+(?:\{[^}]+\}|"[^"]+"|\S+)', '', cmd)
            clean_cmd = re.sub(r'-\w+', '', clean_cmd)
            clean_cmd = re.sub(r'\bcreate_clock\b', '', clean_cmd).strip()
            if clean_cmd:
                cand = clean_cmd.split()[0].strip('"{ }[]')
                try:
                    float(cand)
                except ValueError:
                    port_name = cand

        if not clk_name and port_name:
            clk_name = port_name

        clocks.append({
            "name": clk_name or "unnamed_clock",
            "period": period,
            "port": port_name,
            "raw_command": cmd
        })

    return clocks


def validate_sdc_clocks_against_netlist(
    sdc_path_or_content: str,
    netlist_path_or_content: str,
    top_module: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verifies that all SDC clock definitions target ports that physically exist
    in the netlist top-level interface.
    """
    netlist_clocks = extract_netlist_clock_ports(netlist_path_or_content, top_module)
    sdc_clocks = parse_sdc_clocks(sdc_path_or_content)

    matched: List[str] = []
    mismatched: List[Dict[str, str]] = []
    errors: List[str] = []

    content = netlist_path_or_content
    if os.path.isfile(netlist_path_or_content):
        try:
            with open(netlist_path_or_content, 'r', errors='ignore') as f:
                content = f.read()
        except Exception:
            pass
    clean_text = re.sub(r'//.*', '', content)
    clean_text = re.sub(r'/\*.*?\*/', '', clean_text, flags=re.DOTALL)

    all_netlist_inputs: List[str] = []
    for pm in re.finditer(
        r'(?:^|[;,(\s])\s*(?:input|inout)\s+(?:wire\s+|reg\s+|logic\s+)?(?:signed\s+)?(?:\[\d+:\d+\]\s+)?([^;,)]+)',
        clean_text,
        re.MULTILINE
    ):
        for name in pm.group(1).split(','):
            n = re.sub(r'\s*=.*$', '', name).strip()
            if n and re.match(r'^[A-Za-z_][A-Za-z0-9_$]*$', n) and n not in all_netlist_inputs:
                all_netlist_inputs.append(n)

    if not all_netlist_inputs and netlist_clocks:
        all_netlist_inputs = list(netlist_clocks)

    constrained_ports: set = set()
    for clk in sdc_clocks:
        port = clk.get("port")
        clk_name = clk.get("name")
        if not port:
            matched.append(clk_name)
            continue

        constrained_ports.add(port)
        if port in all_netlist_inputs:
            matched.append(clk_name)
        else:
            mismatched.append({
                "clock": clk_name,
                "port": port,
                "expected_available": all_netlist_inputs
            })
            errors.append(
                f"SDC clock '{clk_name}' targets port '{port}' which does not exist in netlist "
                f"(available ports: {', '.join(all_netlist_inputs) if all_netlist_inputs else 'none'})"
            )

    unconstrained = [p for p in netlist_clocks if p not in constrained_ports]

    is_valid = len(mismatched) == 0
    return {
        "valid": is_valid,
        "matched_clocks": matched,
        "mismatched_clocks": mismatched,
        "netlist_clock_ports": netlist_clocks,
        "unconstrained_clock_ports": unconstrained,
        "errors": errors
    }
