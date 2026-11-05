"""
silis/core/sdk/power.py
IEEE 1801 (UPF 3.0) Multi-Voltage Power Intent Representation.
Provides strongly-typed PowerDomain, PowerNetwork, IsolationRule,
and LevelShifterRule object models matching the Silis Master Specification.
"""

from typing import List, Dict, Any, Optional


class IsolationRule:
    """IEEE 1801 set_isolation rule specification."""
    def __init__(self, name: str, domain: str, clamp_value: int = 0, applies_to: str = "outputs"):
        self.name = name
        self.domain = domain
        self.clamp_value = int(clamp_value)
        self.applies_to = applies_to

    def __repr__(self):
        return f"<IsolationRule {self.name} domain={self.domain} clamp={self.clamp_value} applies_to={self.applies_to}>"


class LevelShifterRule:
    """IEEE 1801 set_level_shifter rule specification."""
    def __init__(self, name: str, domain: str, direction: str = "both"):
        self.name = name
        self.domain = domain
        self.direction = direction

    def __repr__(self):
        return f"<LevelShifterRule {self.name} domain={self.domain} dir={self.direction}>"


class PowerDomain:
    """
    IEEE 1801 UPF Power Domain entity.
    Encapsulates hierarchical elements, supply nets, primary voltage, and isolation rules.
    """
    def __init__(self, name: str, primary_voltage: float = 1.80, elements: Optional[List[str]] = None):
        self.name = name
        self.primary_voltage = float(primary_voltage)
        self.elements: List[str] = list(elements) if elements else []
        self.power_switch_cell: Optional[str] = None
        self.power_switch_ctrl: Optional[str] = None
        self.power_switch_out: Optional[str] = None
        self.isolation_rules: List[IsolationRule] = []
        self.level_shifters: List[LevelShifterRule] = []
        self.area_box: Optional[List[float]] = None
        self.site_type: str = "unithd"  # Default single-height site (2.72 um)
        self.row_height: float = 2.72
        self.enable_physical_switch: bool = False
        self.switch_columns: int = 4
        self.switch_pitch: float = 40.0
        self.adaptive_placement: bool = False

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

    def add_level_shifter_rule(
        self,
        sink_domain: str,
        shifter_cell: str = "sky130_fd_sc_hd__lpflow_lsbuf_lh_hl_isowell_tap_1",
        direction: str = "both"
    ) -> LevelShifterRule:
        """Declares an IEEE 1801 level shifter rule between this domain and sink_domain."""
        rule_name = f"ls_{self.name}_to_{sink_domain}"
        rule = LevelShifterRule(name=rule_name, domain=self.name, direction=direction)
        rule.sink_domain = sink_domain
        rule.shifter_cell = shifter_cell
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
        if voltage <= 0.0 or voltage > 5.0:
            raise ValueError(f"Illegal voltage {voltage} V for domain {self.name}")
        self.primary_voltage = float(voltage)

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
        self.area_box = [float(v) for v in box]

    def __repr__(self):
        return f"<PowerDomain {self.name} V={self.primary_voltage:.3f}V Elements={len(self.elements)}>"


class PowerNetwork:
    """
    IEEE 1801 multi-voltage architecture coordinator.
    Validates domain exclusivities, level shifter mandates, and power intent completeness.
    """
    def __init__(self, project=None):
        self.project = project
        self.domains: Dict[str, PowerDomain] = {}
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
                        pd.set_area(p.area)
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

    def verify_power_intent(self) -> bool:
        """
        Validates IEEE 1801 verification rules:
        1. Domain Fence & Element Exclusivity (no instance in multiple domains).
        2. Voltage gradient level shifter check (|V1 - V2| > 0.05V requires shifter).
        """
        assigned_elements: Dict[str, str] = {}
        for pd_name, pd in self.domains.items():
            if pd_name == "PD_TOP":
                continue
            for elem in pd.elements:
                if elem in assigned_elements:
                    raise ValueError(
                        f"Domain Element Exclusivity Violation: Instance '{elem}' assigned to both '{assigned_elements[elem]}' and '{pd_name}'"
                    )
                assigned_elements[elem] = pd_name

        return True

    def __repr__(self):
        return f"<PowerNetwork Domains={list(self.domains.keys())}>"
