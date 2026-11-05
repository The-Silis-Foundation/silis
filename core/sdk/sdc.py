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
