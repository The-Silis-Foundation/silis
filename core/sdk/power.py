"""
silis/core/sdk/power.py
IEEE 1801 (UPF 3.0) Multi-Voltage Power Intent Representation.
Provides strongly-typed PowerDomain, PowerNetwork, IsolationRule,
LevelShifterRule, PowerSwitch, and PowerStateTable object models
matching the Silis Master Specification.
Zero emojis.
"""

import math
import os
import re
from typing import List, Dict, Any, Optional, Tuple

from .exceptions import IllegalVoltageError, DRCViolationError


class IsolationRule:
    """IEEE 1801 set_isolation rule specification."""
    def __init__(self, name: str, domain: str, clamp_value: int = 0, applies_to: str = "outputs"):
        self.name = name
        self.domain = domain
        c_val = int(clamp_value)
        if c_val not in (0, 1):
            raise ValueError(f"Isolation clamp_value must be binary 0 or 1, got {clamp_value}")
        self.clamp_value = c_val
        app_to = str(applies_to).lower().strip()
        if app_to not in ("inputs", "outputs", "both"):
            raise ValueError(f"Isolation applies_to must be 'inputs', 'outputs', or 'both', got '{applies_to}'")
        self.applies_to = app_to

    def __repr__(self):
        return f"<IsolationRule {self.name} domain={self.domain} clamp={self.clamp_value} applies_to={self.applies_to}>"


class LevelShifterRule:
    """
    IEEE 1801 set_level_shifter rule specification.
    Supports directional isolation/shifting (step-up, step-down, both),
    source and sink domain scoping, and custom cell mapping.
    """
    def __init__(
        self,
        name: str,
        domain: str,
        direction: str = "both",
        sink_domain: Optional[str] = None,
        shifter_cell: Optional[str] = None,
        rule_type: Optional[str] = None,
        location: str = "self"
    ):
        self.name = name
        self.domain = domain
        d = str(direction).lower().strip()
        if d not in ("input", "output", "both"):
            raise ValueError(f"Level shifter direction must be 'input', 'output', or 'both', got '{direction}'")
        self.direction = d
        self.sink_domain = sink_domain
        self.shifter_cell = shifter_cell
        if rule_type is not None:
            rt = str(rule_type).lower().strip()
            if rt not in ("low_to_high", "high_to_low", "both"):
                raise ValueError(f"Level shifter rule_type must be 'low_to_high', 'high_to_low', or 'both', got '{rule_type}'")
            self.rule_type = rt
        else:
            self.rule_type = "both"
        loc = str(location).lower().strip()
        if loc not in ("self", "parent", "fanout"):
            raise ValueError(f"Level shifter location must be 'self', 'parent', or 'fanout', got '{location}'")
        self.location = loc

    def is_step_up(self) -> bool:
        """Returns True if rule supports low-to-high step-up shifting."""
        return self.rule_type in ("low_to_high", "both")

    def is_step_down(self) -> bool:
        """Returns True if rule supports high-to-low step-down shifting."""
        return self.rule_type in ("high_to_low", "both")

    def __repr__(self):
        return f"<LevelShifterRule {self.name} domain={self.domain} sink={self.sink_domain} dir={self.direction} type={self.rule_type}>"


class PowerSwitch:
    """
    IEEE 1801 create_power_switch specification.
    Supports input/output supply ports, control signals, acknowledgment ports,
    and daisy-chain stages to limit inrush current.
    """
    def __init__(
        self,
        name: str,
        domain: str,
        cell_master: str = "POWER_SWITCH",
        input_supply_port: str = "vin",
        input_supply_net: str = "VDD",
        output_supply_port: str = "vout",
        output_supply_net: Optional[str] = None,
        control_port: str = "sleep",
        control_net: Optional[str] = None,
        ack_port: Optional[str] = None,
        ack_net: Optional[str] = None,
        on_state: Optional[str] = None,
        stage_index: int = 0
    ):
        self.name = name
        self.domain = domain
        self.cell_master = cell_master
        self.input_supply_port = input_supply_port
        self.input_supply_net = input_supply_net
        self.output_supply_port = output_supply_port
        self.output_supply_net = output_supply_net or f"VDD_{domain}"
        self.control_port = control_port
        self.control_net = control_net or f"{domain.lower()}_sleep"
        self.ack_port = ack_port
        self.ack_net = ack_net
        self.on_state = on_state or f"ON {input_supply_port} {{!{control_port}}}"
        self.stage_index = int(stage_index)

    def __repr__(self):
        return (
            f"<PowerSwitch {self.name} domain={self.domain} in={self.input_supply_net} "
            f"out={self.output_supply_net} ctrl={self.control_net} stage={self.stage_index}>"
        )


class PowerStateTable:
    """
    IEEE 1801 create_pst and add_pst_state representation.
    Models concurrent power states across multiple domain rails.
    """
    def __init__(self, name: str, supplies: List[str]):
        if not name or not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
            raise ValueError(f"Invalid PST name: '{name}'")
        if not supplies or len(supplies) < 2:
            raise ValueError(f"PST '{name}' must specify at least 2 supply nets, got {supplies}")
        self.name = name
        self.supplies = list(supplies)
        self.states: Dict[str, List[str]] = {}

    def add_state(self, state_name: str, supply_states: List[str]) -> None:
        if not state_name or not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', state_name):
            raise ValueError(f"Invalid PST state name: '{state_name}'")
        if len(supply_states) != len(self.supplies):
            raise ValueError(
                f"PST state '{state_name}' has {len(supply_states)} supply states, "
                f"expected {len(self.supplies)} matching supplies {self.supplies}"
            )
        valid_states = {"ON", "OFF", "SLEEP", "RETENTION", "STBY"}
        for s in supply_states:
            s_up = str(s).upper()
            if s_up not in valid_states:
                raise ValueError(
                    f"Invalid supply state '{s}' in PST state '{state_name}'. Expected one of {valid_states}"
                )
        self.states[state_name] = [str(s).upper() for s in supply_states]

    def get_states(self) -> Dict[str, List[str]]:
        return dict(self.states)

    def export_upf_commands(self) -> List[str]:
        lines = [f"create_pst {self.name} -supplies {{ {' '.join(self.supplies)} }}"]
        for sname, svals in self.states.items():
            lines.append(f"add_pst_state {sname} -pst {self.name} -state {{ {' '.join(svals)} }}")
        return lines

    def __repr__(self):
        return f"<PowerStateTable {self.name} supplies={self.supplies} states={list(self.states.keys())}>"


class PowerDomain:
    """
    IEEE 1801 UPF Power Domain entity.
    Encapsulates hierarchical elements, supply nets, primary voltage,
    isolation rules, level shifter rules, power switches, and physical island area.
    """
    def __init__(self, name: str, primary_voltage: float = 1.80, elements: Optional[List[str]] = None):
        if not name or re.search(r'[^A-Za-z0-9_]', name):
            raise ValueError(f"Invalid domain name: '{name}'. Domain names must only contain alphanumeric characters and underscores.")
        self.name = name
        v = float(primary_voltage)
        if math.isnan(v) or math.isinf(v) or v <= 0.0 or v > 5.0:
            raise IllegalVoltageError(f"Illegal voltage {primary_voltage} V for domain {name}")
        self.primary_voltage = v
        self.elements: List[str] = list(dict.fromkeys(elements)) if elements else []
        self.primary_power_net: str = "VDD" if (name == "PD_TOP" or "." in self.elements) else f"VDD_{name}"
        self.primary_ground_net: str = "VSS"
        self.power_switch_cell: Optional[str] = None
        self.power_switch_ctrl: Optional[str] = None
        self.power_switch_out: Optional[str] = None
        self.power_switches: List[PowerSwitch] = []
        self.isolation_rules: List[IsolationRule] = []
        self.level_shifters: List[LevelShifterRule] = []
        self.area_box: Optional[List[float]] = None
        self.site_type: str = "unithd"  # Default single-height site (2.72 um)
        self.row_height: float = 2.72
        self.enable_physical_switch: bool = False
        self.switch_columns: int = 4
        self.switch_pitch: float = 40.0
        self.adaptive_placement: bool = False

    @property
    def voltage(self) -> float:
        """Alias for primary_voltage for GUI and downstream exporter parity."""
        return self.primary_voltage

    @voltage.setter
    def voltage(self, val: float) -> None:
        self.set_primary_voltage(val)

    @property
    def is_top(self) -> bool:
        """Returns True if this is the top-level always-on power domain."""
        return self.name == "PD_TOP" or "." in self.elements

    @property
    def isolation_clamp(self) -> Optional[int]:
        if self.isolation_rules:
            return self.isolation_rules[0].clamp_value
        return None

    def get_isolation_rules(self) -> List[IsolationRule]:
        return list(self.isolation_rules)

    def get_level_shifters(self) -> List[LevelShifterRule]:
        return list(self.level_shifters)

    def get_power_switches(self) -> List[PowerSwitch]:
        return list(self.power_switches)

    def configure_power_switches(
        self,
        cell_master: str = "POWER_SWITCH",
        columns: int = 4,
        pitch_um: float = 40.0,
        control_port: str = "sleep",
        output_net: str = "",
        adaptive_placement: bool = False,
    ) -> None:
        """
        Enables and configures physical power switch insertion for this domain.
        - cell_master: PDK power switch cell (e.g. 'POWER_SWITCH')
        - columns: Number of vertical power switch columns in the domain
        - pitch_um: Horizontal spacing between switch columns in microns
        - adaptive_placement: If True, centers power switch columns around the domain logic centroid.
        """
        self.enable_physical_switch = True
        self.switch_columns = max(1, int(columns))
        self.switch_pitch = float(pitch_um)
        self.adaptive_placement = bool(adaptive_placement)
        self.set_power_switch(master=cell_master, control_port=control_port, output_net=output_net)

    def add_power_switch(
        self,
        name: Optional[str] = None,
        cell_master: str = "POWER_SWITCH",
        input_supply_port: str = "vin",
        input_supply_net: str = "VDD",
        output_supply_port: str = "vout",
        output_supply_net: Optional[str] = None,
        control_port: str = "sleep",
        control_net: Optional[str] = None,
        ack_port: Optional[str] = None,
        ack_net: Optional[str] = None,
        on_state: Optional[str] = None,
        stage_index: int = 0
    ) -> PowerSwitch:
        """Adds a strongly-typed PowerSwitch instance to this domain."""
        sw_name = name or f"pwr_sw_{self.name}_{len(self.power_switches)}"
        sw = PowerSwitch(
            name=sw_name,
            domain=self.name,
            cell_master=cell_master,
            input_supply_port=input_supply_port,
            input_supply_net=input_supply_net,
            output_supply_port=output_supply_port,
            output_supply_net=output_supply_net,
            control_port=control_port,
            control_net=control_net,
            ack_port=ack_port,
            ack_net=ack_net,
            on_state=on_state,
            stage_index=stage_index
        )
        self.power_switches.append(sw)
        self.enable_physical_switch = True
        self.power_switch_cell = cell_master
        self.power_switch_ctrl = control_port
        self.power_switch_out = sw.output_supply_net
        return sw

    def configure_daisy_chain(
        self,
        stages: int,
        cell_master: str = "POWER_SWITCH",
        input_supply_net: str = "VDD",
        output_supply_net: Optional[str] = None,
        base_control_net: Optional[str] = None
    ) -> List[PowerSwitch]:
        """
        Synthesizes an inrush-limiting power switch daisy-chain across multiple stages.
        Stage 0: ctrl = base_control_net, ack = ack_0
        Stage k: ctrl = ack_{k-1}, ack = ack_k
        Stage N-1: ctrl = ack_{N-2}, ack = final_ack
        """
        if stages < 1:
            raise ValueError(f"Daisy chain stages must be >= 1, got {stages}")
        out_net = output_supply_net or f"VDD_{self.name}"
        ctrl_base = base_control_net or f"{self.name.lower()}_sleep"
        switches = []
        for i in range(stages):
            sw_name = f"pwr_sw_{self.name}_stg{i}"
            c_net = ctrl_base if i == 0 else f"{self.name.lower()}_sleep_ack_{i-1}"
            a_net = f"{self.name.lower()}_sleep_ack_{i}" if i < stages - 1 else f"{self.name.lower()}_sleep_ack"
            sw = self.add_power_switch(
                name=sw_name,
                cell_master=cell_master,
                input_supply_net=input_supply_net,
                output_supply_net=out_net,
                control_net=c_net,
                ack_port="sleep_out",
                ack_net=a_net,
                stage_index=i
            )
            switches.append(sw)
        return switches

    def add_level_shifter_rule(
        self,
        sink_domain: str,
        shifter_cell: str = "sky130_fd_sc_hd__lpflow_lsbuf_lh_hl_isowell_tap_1",
        direction: str = "both",
        rule_type: Optional[str] = None,
        location: str = "self"
    ) -> LevelShifterRule:
        """Declares an IEEE 1801 level shifter rule between this domain and sink_domain."""
        rule_name = f"ls_{self.name}_to_{sink_domain}"
        rule = LevelShifterRule(
            name=rule_name,
            domain=self.name,
            direction=direction,
            sink_domain=sink_domain,
            shifter_cell=shifter_cell,
            rule_type=rule_type,
            location=location
        )
        self.level_shifters.append(rule)
        return rule

    def set_row_site(self, site_type: str = "unithd", height: Optional[float] = None) -> None:
        """
        Configures the standard cell row site and height for this power domain.
        - 'unithd' (default): Single-height standard cells (2.72 um)
        - 'unithddbl': Double-height power switch / dense logic cells (5.44 um)
        """
        self.site_type = str(site_type).strip()
        if height is not None:
            self.row_height = float(height)
        elif self.site_type == "unithddbl":
            self.row_height = 5.44
        else:
            self.row_height = 2.72

    def enable_physical_power_switches(self, enable: bool = True) -> None:
        """
        Enables or disables physical power switch cell mapping (POWER_SWITCH) in OpenROAD.
        When disabled (default), power domains use architectural mesh routing matching test-FPS-SoC.
        """
        self.enable_physical_switch = bool(enable)

    def set_primary_voltage(self, voltage: float) -> None:
        v = float(voltage)
        if math.isnan(v) or math.isinf(v) or v <= 0.0 or v > 5.0:
            raise IllegalVoltageError(f"Illegal voltage {voltage} V for domain {self.name}")
        self.primary_voltage = v

    def add_element(self, hierarchical_instance: str) -> None:
        if hierarchical_instance not in self.elements:
            self.elements.append(hierarchical_instance)

    def set_power_switch(self, master: str = "POWER_SWITCH", control_port: str = "sleep", output_net: str = "") -> None:
        self.power_switch_cell = master
        self.power_switch_ctrl = control_port
        self.power_switch_out = output_net or f"VDD_{self.name}"

    def add_isolation_rule(self, clamp_value: int = 0, applies_to: str = "outputs") -> IsolationRule:
        rule_name = f"iso_{self.name}"
        rule = IsolationRule(name=rule_name, domain=self.name, clamp_value=clamp_value, applies_to=applies_to)
        self.isolation_rules.append(rule)
        return rule

    def set_area(self, box: List[float]) -> None:
        """Sets physical voltage island rectangle [x1, y1, x2, y2] in microns."""
        if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError(f"Invalid voltage island box: {box}")
        grid = 0.005
        self.area_box = [round(round(float(v) / grid) * grid, 3) for v in box]

    def __repr__(self):
        return f"<PowerDomain {self.name} V={self.primary_voltage:.3f}V Elements={len(self.elements)}>"


class PowerNetwork:
    """
    IEEE 1801 multi-voltage architecture coordinator.
    Validates domain exclusivities, level shifter mandates, power switch chains,
    PST consistency, and physical fence DRC compliance.
    """
    def __init__(self, project=None):
        self.project = project
        self.domains: Dict[str, PowerDomain] = {}
        self.psts: Dict[str, PowerStateTable] = {}

        # Populate from project UPF if available
        if project and hasattr(project, "get_power_domains"):
            try:
                p_pds = project.get_power_domains()
                for p in p_pds:
                    pd = self.create_domain(
                        name=p.name,
                        primary_voltage=getattr(p, "voltage", 1.80),
                        elements=getattr(p, "elements", [])
                    )
                    if getattr(p, "gated", False) or getattr(p, "power_switch_master", None):
                        pd.set_power_switch(
                            master=getattr(p, "power_switch_master", "POWER_SWITCH") or "POWER_SWITCH",
                            control_port=getattr(p, "power_switch_control", "sleep") or "sleep",
                            output_net=getattr(p, "power_switch_output", f"VDD_{p.name}") or f"VDD_{p.name}"
                        )
                    if hasattr(p, "area") and p.area:
                        pd.set_area(list(p.area))
            except Exception:
                pass

        # Ensure default TOP always-on domain exists
        if "PD_TOP" not in self.domains:
            self.top_domain = self.create_domain("PD_TOP", primary_voltage=1.80, elements=["."])
        else:
            self.top_domain = self.domains["PD_TOP"]

    def create_domain(self, name: str, primary_voltage: float = 1.80, elements: Optional[List[str]] = None) -> PowerDomain:
        if name in self.domains:
            return self.domains[name]
        pd = PowerDomain(name=name, primary_voltage=primary_voltage, elements=elements)
        self.domains[name] = pd
        return pd

    def get_domain(self, name: str) -> Optional[PowerDomain]:
        return self.domains.get(name)

    def get_domains(self) -> List[PowerDomain]:
        return list(self.domains.values())

    def create_pst(self, name: str, supplies: List[str]) -> PowerStateTable:
        """Declares an IEEE 1801 Power State Table (PST)."""
        if name in self.psts:
            return self.psts[name]
        pst = PowerStateTable(name=name, supplies=supplies)
        self.psts[name] = pst
        return pst

    def get_pst(self, name: str) -> Optional[PowerStateTable]:
        return self.psts.get(name)

    def get_psts(self) -> List[PowerStateTable]:
        return list(self.psts.values())

    def verify_power_intent(self) -> bool:
        """
        Validates IEEE 1801 verification rules:
        1. Domain Fence & Element Exclusivity (no instance in multiple domains).
        2. Voltage gradient level shifter check (|V1 - V2| > 0.05V requires shifter).
        3. Gated domain isolation rule check.
        4. PST supply net integrity.
        5. Daisy-chain control signal continuity.
        """
        assigned_elements: Dict[str, str] = {}
        for pd_name, pd in self.domains.items():
            for elem in pd.elements:
                if elem == ".":
                    continue
                for exist_elem, exist_pd in assigned_elements.items():
                    if exist_pd != pd_name and (elem == exist_elem or elem.startswith(exist_elem + "/") or exist_elem.startswith(elem + "/")):
                        raise ValueError(
                            f"Domain Element Exclusivity Violation: Hierarchical instance '{elem}' in '{pd_name}' collides with '{exist_elem}' in '{exist_pd}'"
                        )
                assigned_elements[elem] = pd_name

        # Check voltage gradient level shifters for disparate domains
        pds = list(self.domains.values())
        for i in range(len(pds)):
            for j in range(i + 1, len(pds)):
                d1 = pds[i]
                d2 = pds[j]
                grad = abs(d1.primary_voltage - d2.primary_voltage)
                if grad > 0.05:
                    matched_rules = []
                    for r in d1.level_shifters + d2.level_shifters:
                        # Direct pairwise connection between d1 and d2
                        if (r.domain == d1.name and getattr(r, "sink_domain", None) == d2.name) or \
                           (r.domain == d2.name and getattr(r, "sink_domain", None) == d1.name):
                            matched_rules.append(r)
                        # Domain-wide rule with no sink_domain restricted
                        elif getattr(r, "sink_domain", None) is None and r.domain in (d1.name, d2.name):
                            matched_rules.append(r)

                    if not matched_rules:
                        raise ValueError(
                            f"Voltage Gradient Violation: Voltage gradient between '{d1.name}' ({d1.primary_voltage:.3f}V) "
                            f"and '{d2.name}' ({d2.primary_voltage:.3f}V) is {grad:.3f}V > 0.05V without level shifter rule."
                        )

        # Check that gated domains have isolation rules declared
        for pd_name, pd in self.domains.items():
            if pd.name != "PD_TOP" and (pd.enable_physical_switch or pd.power_switch_cell or pd.power_switches):
                if not pd.isolation_rules:
                    raise ValueError(
                        f"Isolation Policy Violation: Gated domain '{pd.name}' has 0 isolation rules declared."
                    )

        # Check PST supply validity
        all_supplies = set()
        for pd in self.domains.values():
            all_supplies.add(pd.primary_power_net)
            all_supplies.add(pd.primary_ground_net)
            for sw in pd.power_switches:
                all_supplies.add(sw.input_supply_net)
                all_supplies.add(sw.output_supply_net)

        for pst_name, pst in self.psts.items():
            for sup in pst.supplies:
                if sup not in all_supplies:
                    raise ValueError(
                        f"PST Supply Integrity Violation: Supply '{sup}' in PST '{pst_name}' is not declared in any power domain or switch."
                    )

        # Check daisy-chain stage continuity
        for pd in self.domains.values():
            staged_sw = [s for s in pd.power_switches if s.ack_net is not None or s.stage_index > 0]
            if len(staged_sw) > 1:
                sorted_sw = sorted(staged_sw, key=lambda s: s.stage_index)
                for k in range(1, len(sorted_sw)):
                    prev_sw = sorted_sw[k - 1]
                    curr_sw = sorted_sw[k]
                    if curr_sw.stage_index > prev_sw.stage_index:
                        if prev_sw.ack_net != curr_sw.control_net:
                            raise ValueError(
                                f"Power Switch Daisy-Chain Break in domain '{pd.name}': "
                                f"Stage {curr_sw.stage_index} control_net '{curr_sw.control_net}' does not match "
                                f"Stage {prev_sw.stage_index} ack_net '{prev_sw.ack_net}'."
                            )

        return True

    def validate_fence_drc(
        self,
        core_area: Optional[List[float]] = None,
        grid: float = 0.005
    ) -> List[str]:
        """
        Validates physical voltage island fences against manufacturing rules:
        1. Site row quantization: y1, y2 must snap to domain.row_height multiples.
        2. Manufacturing grid quantization: x1, x2, y1, y2 on 5nm grid.
        3. Sub-domain bounding box non-overlap: no two sub-domains may physically collide.
        4. Core boundary containment: domain fence must sit inside core rectangle.
        Raises DRCViolationError if violations are found.
        """
        violations = []
        sub_domains = [pd for pd in self.domains.values() if not pd.is_top and pd.area_box is not None]

        # 1. Site row and grid alignment
        for pd in sub_domains:
            box = pd.area_box
            x1, y1, x2, y2 = box
            if x2 <= x1 or y2 <= y1:
                violations.append(f"Domain '{pd.name}' has non-positive area: [{x1}, {y1}, {x2}, {y2}]")

            # Grid alignment
            for val, label in [(x1, "x1"), (y1, "y1"), (x2, "x2"), (y2, "y2")]:
                snapped = round(round(val / grid) * grid, 4)
                if abs(val - snapped) > 1e-4:
                    violations.append(
                        f"Domain '{pd.name}' {label}={val} um violates manufacturing grid (g={grid} um)"
                    )

            # Row site alignment (y1 and y2 must snap to row_height)
            row_h = pd.row_height
            for y_val, label in [(y1, "y1"), (y2, "y2")]:
                k = y_val / row_h
                if abs(k - round(k)) > 1e-3:
                    violations.append(
                        f"Domain '{pd.name}' {label}={y_val:.3f} um violates site row alignment (row_height={row_h:.3f} um)"
                    )

        # 2. Sub-domain bounding box non-overlap
        for i in range(len(sub_domains)):
            for j in range(i + 1, len(sub_domains)):
                d1 = sub_domains[i]
                d2 = sub_domains[j]
                b1 = d1.area_box
                b2 = d2.area_box
                x_overlap = max(b1[0], b2[0]) < min(b1[2], b2[2])
                y_overlap = max(b1[1], b2[1]) < min(b1[3], b2[3])
                if x_overlap and y_overlap:
                    violations.append(
                        f"Physical Fence Collision: Domain '{d1.name}' [{b1[0]}, {b1[1]}, {b1[2]}, {b1[3]}] overlaps domain '{d2.name}' [{b2[0]}, {b2[1]}, {b2[2]}, {b2[3]}]"
                    )

        # 3. Core boundary containment
        if core_area and len(core_area) == 4:
            cx1, cy1, cx2, cy2 = core_area
            for pd in sub_domains:
                b = pd.area_box
                if b[0] < cx1 or b[1] < cy1 or b[2] > cx2 or b[3] > cy2:
                    violations.append(
                        f"Core Containment Violation: Domain '{pd.name}' fence [{b[0]}, {b[1]}, {b[2]}, {b[3]}] exceeds core boundary [{cx1}, {cy1}, {cx2}, {cy2}]"
                    )

        if violations:
            raise DRCViolationError(violation_count=len(violations), report_path="; ".join(violations))

        return violations

    def export_upf(self, output_path: str) -> str:
        """Serializes power intent into an atomic IEEE 1801 UPF file."""
        from silis.core.backendflow.power.upf_engine import generate_upf
        return generate_upf(self.get_domains(), output_path, psts=self.get_psts())

    def export_domain_areas_tcl(self, output_path: str) -> str:
        """Serializes domain physical placement boxes into an atomic OpenROAD TCL script."""
        from silis.core.backendflow.power.upf_engine import generate_domain_areas_tcl
        return generate_domain_areas_tcl(self.get_domains(), output_path)

    def __repr__(self):
        return f"<PowerNetwork Domains={list(self.domains.keys())} PSTs={list(self.psts.keys())}>"
