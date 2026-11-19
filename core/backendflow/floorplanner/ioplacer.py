"""
Silis I/O Placement Module — Unified Physical Design & Floorplan Studio Adapter.
Peripheral I/O pin placement and wirebond pad ring synthesis are unified directly
within InteractiveFloorplannerWidget (Tab 3: I/O & Pads).
This module provides backward-compatible re-exports and the IOPlacerDialog adapter.
"""

from typing import Any, Dict, Optional
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import QRectF

from backendflow.floorplanner.io_types import (
    natural_sort_key,
    snap_to_grid,
    PAD_CELL_MAP,
    PAD_CELL_DISPLAY_LIST,
    PinItem,
    EdgeConstraintBox,
    parse_verilog_netlist_pins,
)
from backendflow.floorplanner.floorplanner import InteractiveFloorplannerWidget


class IOPlacerDialog(InteractiveFloorplannerWidget):
    """
    Unified I/O Placer Dialog adapter backed by InteractiveFloorplannerWidget (Tab 3).
    Enables visual peripheral pin distribution, edge grouping, pitch tuning,
    wirebond pad ring generation, and OpenROAD floorplan script synthesis.
    """
    def __init__(self, project_config: Optional[Dict[str, Any]] = None, pdk_mgr: Any = None, parent: Any = None):
        super().__init__(project_config=project_config, pdk_mgr=pdk_mgr, parent=parent)
        self.setWindowTitle("Silis Floorplan & I/O Studio — Peripheral Pads")
        if hasattr(self, "inspector_tabs"):
            self.inspector_tabs.setCurrentIndex(2)

    def auto_distribute_pins(self, reset_edges: bool = False):
        """Unified pin & pad auto-distribution delegating to FPS core engine with staggered multi-tier handling."""
        w = self.die_rect.width() if hasattr(self, "die_rect") and self.die_rect else 1000.0
        h = self.die_rect.height() if hasattr(self, "die_rect") and self.die_rect else 1000.0
        is_pad = hasattr(self, "rb_chip") and self.rb_chip.isChecked()
        is_staggered = is_pad and (getattr(self, "pad_strategy", "single") == "staggered")

        if is_staggered:
            import math
            for item in list(getattr(self, "pin_items", {}).values()):
                try:
                    if item and item.scene() == self.scene:
                        self.scene.removeItem(item)
                except Exception:
                    pass
            self.pin_items.clear()

            all_names = sorted(list(self.pins_data.keys()), key=natural_sort_key)
            edges = {"bottom": [], "top": [], "left": [], "right": []}
            for name in all_names:
                pedge = self.pins_data[name].get("edge", "bottom")
                if pedge not in edges:
                    pedge = "bottom"
                edges[pedge].append(name)

            for edge_name, edge_list in edges.items():
                n = len(edge_list)
                if n == 0:
                    continue
                span = w if edge_name in ("bottom", "top") else h
                n1 = math.ceil(n / 2.0)
                n2 = n - n1
                row_min1 = 280.0
                row_max1 = max(row_min1, span - 280.0 - 80.0)
                max_span1 = max(0.0, row_max1 - row_min1)
                step1 = max(85.0, (max_span1 / (n1 - 1))) if n1 > 1 else 0.0
                start1 = row_min1 if n1 > 1 else (row_min1 + max_span1 / 2.0)

                row_min2 = 500.0
                row_max2 = max(row_min2, span - 500.0 - 80.0)
                max_span2 = max(0.0, row_max2 - row_min2)
                step2 = max(85.0, (max_span2 / (n2 - 1))) if n2 > 1 else 0.0
                start2 = (row_min2 + 45.0) if n2 > 1 else (row_min2 + max_span2 / 2.0)

                idx1, idx2 = 0, 0
                for i, name in enumerate(edge_list):
                    is_inner = (i % 2 == 1)
                    if is_inner:
                        coord = min(row_max2, start2 + idx2 * step2)
                        curr_inset = 210.0
                        idx2 += 1
                    else:
                        coord = min(row_max1, start1 + idx1 * step1)
                        curr_inset = 0.0
                        idx1 += 1
                    coord = min(span - 80.0, max(0.0, coord))

                    if edge_name == "bottom":
                        x, y = coord, curr_inset
                    elif edge_name == "top":
                        x, y = coord, h - curr_inset
                    elif edge_name == "left":
                        x, y = curr_inset, coord
                    elif edge_name == "right":
                        x, y = w - curr_inset, coord
                    self._place_pin_item(name, edge_name, x, y, 80.0, 80.0)
            return

        return self.auto_distribute_pads(reset_edges=reset_edges)

    @staticmethod
    def _parse_verilog_netlist_pins(widget_or_self: Any, proj_root: str) -> Dict[str, Dict[str, Any]]:
        """Extracts pin names and directions from synthesized Verilog netlist."""
        cfg = getattr(widget_or_self, "project_config", {}) if widget_or_self else {}
        return parse_verilog_netlist_pins(cfg, proj_root)
