"""
silis/core/dft/verifiers.py
Autonomous Pre-Flight Verifiers for Downstream Physical Design & IEEE 1801 UPF Rules.
Enforces:
1. Manufacturing Grid Legalization (0.005 um quantization, 3-decimal format).
2. IEEE 1801 UPF Multi-Voltage Domain Boundaries (JTAG in PD_TOP, MBIST boundary nets isolation clamped).
3. Macro Halo Clearances (MBIST collar standard cells strictly outside macro keepout halos).
Zero emojis.
"""

import math
import re
from typing import List, Dict, Any, Optional, Tuple

from silis.core.sdk.exceptions import (
    GridLegalizationError,
    IllegalVoltageError,
    OverlappingHaloError,
    DRCViolationError,
)


def verify_grid_alignment(
    x: float,
    y: float,
    element: str = "DFT_ELEMENT",
    grid: float = 0.005
) -> Tuple[float, float]:
    """
    Asserts coordinate strictly snaps to manufacturing grid.
    Raises GridLegalizationError if quantization deviates.
    Returns quantized coordinates.
    """
    x_quant = round(round(x / grid) * grid, 3)
    y_quant = round(round(y / grid) * grid, 3)

    if abs(x - x_quant) > 1e-5 or abs(y - y_quant) > 1e-5:
        raise GridLegalizationError(element, x, y, grid)

    return x_quant, y_quant


def verify_scandef_text_grid(scandef_content: str, grid: float = 0.005) -> None:
    """
    Audits SCANDEF 5.8 content for coordinate grid compliance.
    Inspects any ( <x> <y> ) tuples or STOP/START coordinates.
    """
    coord_pattern = re.compile(r"\(\s*([-+]?[0-9]*\.?[0-9]+)\s+([-+]?[0-9]*\.?[0-9]+)\s*\)")
    for match in coord_pattern.finditer(scandef_content):
        x = float(match.group(1))
        y = float(match.group(2))
        verify_grid_alignment(x, y, element="SCANDEF_COORD", grid=grid)


def verify_upf_dft_integrity(
    power_domains: Dict[str, Any],
    dft_instances: List[Dict[str, Any]],
    isolation_rules: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Autonomous verification of IEEE 1801 UPF multi-voltage intent for DFT logic:
    - JTAG TAP & Boundary Scan cells MUST reside in PD_TOP (Always-On 1.8V).
    - MBIST collars inside power-gated domains (PD_COMPUTE, 0.95V) MUST have
      isolation clamping on boundary nets directed to PD_TOP.
    """
    isolation_rules = isolation_rules or []
    clamped_nets = {r.get("net") or r.get("applies_to") or r.get("name") for r in isolation_rules}

    for inst in dft_instances:
        name = inst.get("name", "unknown_inst")
        inst_type = inst.get("type", "scan")
        domain = inst.get("domain", "PD_TOP")

        # Invariant 1: JTAG & Boundary Scan in PD_TOP
        if inst_type in ("jtag", "tap", "boundary_scan", "bsr"):
            if domain != "PD_TOP":
                raise IllegalVoltageError(
                    f"UPF Invariant Violation: JTAG element '{name}' assigned to domain '{domain}'. "
                    f"All JTAG TAP and peripheral boundary scan logic must reside in Always-On 'PD_TOP'."
                )

        # Invariant 2: Gated MBIST Collars must have isolation clamp rules
        if inst_type in ("mbist", "bira", "sram_collar") and domain != "PD_TOP":
            out_nets = inst.get("output_nets", ["bist_done", "bist_fail"])
            for net in out_nets:
                is_clamped = any(net in c for c in clamped_nets if c) or any(
                    r.get("domain") == domain for r in isolation_rules
                )
                if not is_clamped:
                    raise IllegalVoltageError(
                        f"UPF Invariant Violation: MBIST collar '{name}' in power-gated domain '{domain}' "
                        f"has unclamped boundary net '{net}' directed to PD_TOP. Missing IEEE 1801 set_isolation rule."
                    )


def verify_macro_halo_clearance(
    collar_cells: List[Dict[str, Any]],
    macro_instances: List[Dict[str, Any]],
    default_halo: float = 10.0,
) -> None:
    """
    Asserts all MBIST collar standard cells are placed strictly outside
    macro keepout halos to prevent routing channel congestion.
    """
    for macro in macro_instances:
        m_name = macro.get("name", "macro")
        mx = float(macro.get("x", 0.0))
        my = float(macro.get("y", 0.0))
        mw = float(macro.get("width", 0.0))
        mh = float(macro.get("height", 0.0))
        halo = float(macro.get("halo", default_halo))

        # Expanded bounding box including keepout halo
        h_x1 = mx - halo
        h_y1 = my - halo
        h_x2 = mx + mw + halo
        h_y2 = my + mh + halo

        for cell in collar_cells:
            c_name = cell.get("name", "cell")
            cx = float(cell.get("x", 0.0))
            cy = float(cell.get("y", 0.0))
            cw = float(cell.get("width", 0.0))
            ch = float(cell.get("height", 0.0))

            # Check overlap between cell bbox and macro halo bbox
            c_x2 = cx + cw
            c_y2 = cy + ch

            overlaps_x = (cx < h_x2) and (c_x2 > h_x1)
            overlaps_y = (cy < h_y2) and (c_y2 > h_y1)

            if overlaps_x and overlaps_y:
                raise OverlappingHaloError(
                    f"Macro Halo Collision: MBIST collar cell '{c_name}' at ({cx:.3f}, {cy:.3f}) "
                    f"encroaches within {halo:.3f} um keepout halo of macro '{m_name}' "
                    f"halo_box=({h_x1:.3f}, {h_y1:.3f}, {h_x2:.3f}, {h_y2:.3f})."
                )
