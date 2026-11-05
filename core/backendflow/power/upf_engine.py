"""
UPF & CPF Low-Power Intent Engine for Silis.
Provides parsing, generation, and voltage domain models for multi-voltage / power-gated designs.
All public SDK functions and models use all-lowercase naming per convention.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any


@dataclass
class power_domain:
    """
    Representation of an IEEE 1801 UPF / CPF power domain.
    All properties use lowercase identifiers.
    """
    name: str
    elements: List[str] = field(default_factory=list)
    voltage: float = 1.80
    gated: bool = False
    area: Optional[Tuple[float, float, float, float]] = None # (llx, lly, urx, ury) in um
    power_switch_master: Optional[str] = None
    isolation_clamp: int = 0
    is_top: bool = False
    domain_type: str = "Always-On"  # "Always-On", "Internally Gated", "Dedicated External Pad"
    supply_net: Optional[str] = None

    @property
    def eda_voltage_color(self) -> str:
        """Standard industrial EDA canvas color based on operational voltage level."""
        if self.voltage >= 2.5:
            return "#b58900"  # Deep amber (High Voltage I/O / Padring)
        if self.voltage >= 1.6:
            return "#268bd2"  # Subtle cyan (Nominal Core Logic)
        if self.voltage >= 0.8:
            return "#6c71c4"  # Slate purple / Indigo (Gated Core Logic)
        return "#2aa198"      # Muted teal (Ultra-low voltage island)


def create_default_upf(output_path: str, top_module: str = "top") -> str:
    """
    Generates a default IEEE 1801 UPF template file with a baseline PD_TOP domain.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    content = f"""# Silis Power Intent Specification (IEEE 1801 UPF)
# Project Top Module: {top_module}
# Auto-generated baseline configuration

# Primary Top-Level Always-On Domain
create_power_domain PD_TOP -include_scope

# Primary Supply Nets
create_supply_port VDD -direction in
create_supply_port VSS -direction in
create_supply_net VDD -domain PD_TOP
create_supply_net VSS -domain PD_TOP
set_domain_supply_net PD_TOP -primary_power_net VDD -primary_ground_net VSS

# --- Example Power-Gated Domain Configuration ---
# create_power_domain PD_GATED -elements {{u_gated_block}}
# create_supply_net VDD_GATED -domain PD_GATED
# set_domain_supply_net PD_GATED -primary_power_net VDD_GATED -primary_ground_net VSS
# set_isolation iso_gated -domain PD_GATED -applies_to outputs -clamp_value 0
"""
    with open(output_path, "w") as f:
        f.write(content)
    return output_path


def parse_upf(upf_path: str) -> List[power_domain]:
    """
    Parses a UPF (or CPF converted) file and extracts declared power domains,
    elements, voltages, and area constraints.
    """
    if not os.path.isfile(upf_path):
        return []

    domains: Dict[str, power_domain] = {}

    with open(upf_path, "r", errors="ignore") as f:
        lines = f.readlines()

    # Pre-process line continuations with backslash
    clean_lines = []
    buf = ""
    for line in lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("#"):
            continue
        if line_s.endswith("\\"):
            buf += " " + line_s[:-1].strip()
        else:
            buf += " " + line_s
            clean_lines.append(buf.strip())
            buf = ""
    if buf:
        clean_lines.append(buf.strip())

    for cmd in clean_lines:
        # Match: create_power_domain <name> [-include_scope] [-elements {e1 e2}]
        if cmd.startswith("create_power_domain"):
            parts = cmd.split()
            if len(parts) >= 2:
                dom_name = parts[1]
                is_top = "-include_scope" in cmd or dom_name in ("PD_TOP", "TOP", "pd_top") or "-elements" not in cmd
                elements = []
                m_elem = re.search(r'-elements\s+\{([^}]+)\}', cmd)
                if not m_elem:
                    m_elem = re.search(r'-elements\s+([^{\s]+)', cmd)
                if m_elem:
                    elements = [e.strip() for e in m_elem.group(1).split() if e.strip()]

                v_level = 1.80 if is_top else 0.90
                is_gated = not is_top
                dtype = "Always-On" if is_top else "Dedicated External Pad"
                domains[dom_name] = power_domain(
                    name=dom_name,
                    elements=elements,
                    voltage=v_level,
                    gated=is_gated,
                    is_top=is_top,
                    domain_type=dtype,
                    supply_net="VDD" if is_top else f"VDD_{dom_name}"
                )

        # Match power switches to identify internally gated domains
        elif cmd.startswith("create_power_switch"):
            m_dom = re.search(r'-domain\s+([A-Za-z0-9_]+)', cmd)
            m_sw = re.search(r'create_power_switch\s+([A-Za-z0-9_]+)', cmd)
            if m_dom and m_dom.group(1) in domains:
                d = domains[m_dom.group(1)]
                d.domain_type = "Internally Gated"
                d.gated = True
                if m_sw:
                    d.power_switch_master = m_sw.group(1)

        # Match voltage levels or supply nets if specified
        elif cmd.startswith("set_domain_supply_net") or cmd.startswith("set_voltage"):
            m_dom = re.search(r'([A-Za-z0-9_]+)', cmd.replace("set_domain_supply_net", ""))
            # Check for explicit voltage declaration like -voltage 0.95 or 1.8
            m_v = re.search(r'-voltage\s+([0-9.]+)', cmd)
            m_pwr = re.search(r'-primary_power_net\s+([A-Za-z0-9_]+)', cmd)
            if m_dom:
                d_name = m_dom.group(1)
                if d_name in domains:
                    if m_v:
                        try:
                            domains[d_name].voltage = float(m_v.group(1))
                        except ValueError:
                            pass
                    if m_pwr:
                        domains[d_name].supply_net = m_pwr.group(1)

        # Match isolation rules
        elif cmd.startswith("set_isolation"):
            m_dom = re.search(r'-domain\s+([A-Za-z0-9_]+)', cmd)
            m_clamp = re.search(r'-clamp_value\s+([01])', cmd)
            if m_dom and m_dom.group(1) in domains:
                dom = domains[m_dom.group(1)]
                if m_clamp:
                    dom.isolation_clamp = int(m_clamp.group(1))

        # Match physical area constraints if already present in UPF / tcl
        elif cmd.startswith("set_domain_area"):
            m_area = re.search(r'set_domain_area\s+([A-Za-z0-9_]+)\s+-area\s+\{([^}]+)\}', cmd)
            if m_area:
                d_name = m_area.group(1)
                coords = [float(x) for x in m_area.group(2).split() if x.strip()]
                if len(coords) == 4 and d_name in domains:
                    domains[d_name].area = (coords[0], coords[1], coords[2], coords[3])

    # If no domains parsed, create default PD_TOP
    if not domains:
        domains["PD_TOP"] = power_domain(name="PD_TOP", is_top=True, voltage=1.80, gated=False)

    return list(domains.values())


def generate_upf(domains: List[power_domain], output_path: str) -> str:
    """
    Serializes a list of power_domain instances into a valid IEEE 1801 UPF file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    lines = [
        "# Silis Power Intent Specification (IEEE 1801 UPF)",
        "# Programmatically generated via Silis Power Engine",
        ""
    ]

    # Ports
    lines.extend([
        "create_supply_port VDD -direction in",
        "create_supply_port VSS -direction in",
        ""
    ])

    for dom in domains:
        if dom.is_top:
            lines.append(f"create_power_domain {dom.name} -include_scope")
            lines.append(f"create_supply_net VDD -domain {dom.name}")
            lines.append(f"create_supply_net VSS -domain {dom.name}")
            lines.append(f"set_domain_supply_net {dom.name} -primary_power_net VDD -primary_ground_net VSS -voltage {dom.voltage:.2f}")
        else:
            elem_str = " ".join(dom.elements)
            lines.append(f"create_power_domain {dom.name} -elements {{{elem_str}}}")
            vnet = f"VDD_{dom.name}"
            lines.append(f"create_supply_net {vnet} -domain {dom.name}")
            lines.append(f"create_supply_net VSS -domain {dom.name}")
            lines.append(f"set_domain_supply_net {dom.name} -primary_power_net {vnet} -primary_ground_net VSS -voltage {dom.voltage:.2f}")
            if dom.power_switch_master:
                lines.append(f"create_power_switch pwr_sw_{dom.name} -domain {dom.name} -output_supply_port {vnet}")
            lines.append(f"set_isolation iso_{dom.name} -domain {dom.name} -applies_to outputs -clamp_value {dom.isolation_clamp}")
        lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    return output_path


def generate_domain_areas_tcl(domains: List[power_domain], output_path: str) -> str:
    """
    Writes physical domain placement bounding boxes into OpenROAD TCL commands (set_domain_area).
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    lines = [
        "# OpenROAD Power Domain Physical Areas",
        "# Auto-generated by Silis Floorplanner / SDK",
        ""
    ]
    for dom in domains:
        if not dom.is_top and dom.area and len(dom.area) == 4:
            x1, y1, x2, y2 = dom.area
            lines.append(f"set_domain_area {dom.name} -area {{{x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f}}}")

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    return output_path
