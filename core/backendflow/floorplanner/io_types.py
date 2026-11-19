"""
Silis Physical Design Studio - Unified I/O & Pad Ring Core Types and Helpers.
Provides manufacturing grid snapping, natural sorting, pad cell mappings,
pin/pad QGraphics canvas items, and Verilog netlist pin extraction.
"""

import os
import re
from typing import Dict, Any, List, Optional
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QTransform, QFont
from PyQt6.QtWidgets import (
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem
)


def natural_sort_key(s: str) -> List[Any]:
    """Sort strings containing numbers in human/natural numerical order: a[0], a[1], ... a[10]."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]


def snap_to_grid(val: float, grid: float = 0.005) -> float:
    """Snap coordinate to standard manufacturing grid (default Sky130 5nm / 0.005 um)."""
    return round(round(float(val) / grid) * grid, 3)


PAD_CELL_MAP: Dict[str, str] = {
    "GPIO (top_gpiov2)": "sky130_fd_io__top_gpiov2",
    "Core VDD 1.8V (top_power_lvc)": "sky130_fd_io__top_power_lvc_wpad",
    "Core VSS Ground (top_ground_lvc)": "sky130_fd_io__top_ground_lvc_wpad",
    "I/O VDDIO 3.3V (top_power_hvc)": "sky130_fd_io__top_power_hvc_wpad",
    "I/O VSSIO Ground (top_ground_hvc)": "sky130_fd_io__top_ground_hvc_wpad",
    "Analog / ESD Pad (analog_pad)": "sky130_ef_io__analog_pad",
}

PAD_CELL_DISPLAY_LIST: List[str] = list(PAD_CELL_MAP.keys())


class PinItem(QGraphicsRectItem):
    """
    Represents an I/O Port or I/O Pad placed along the die boundary.
    Supports magnetic snapping along perimeter edges.
    """
    def __init__(self, pin_name: str, direction: str, width: float, height: float, placer_dialog, parent=None):
        super().__init__(-width/2, -height/2, width, height, parent)
        self.pin_name = pin_name
        self.direction = direction  # input, output, inout, power, ground
        self.w = width
        self.h = height
        self.dialog = placer_dialog
        self.edge = "bottom"  # bottom, top, left, right
        self.layer = "met3"
        self.assigned_box = "All Edges"

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self._apply_color()

        # Visual indicator for power pads
        if self.direction in ("power", "ground"):
            self.setPen(QPen(QColor("#f38ba8" if self.direction == "power" else "#89b4fa"), 2))
        else:
            self.setPen(QPen(QColor("#11111b"), 1))

        self.text_item = QGraphicsTextItem(pin_name, self)
        font = self.text_item.font()
        font.setPointSize(7)
        font.setBold(True)
        self.text_item.setFont(font)
        self.text_item.setDefaultTextColor(QColor("#cdd6f4"))
        self.text_item.setTransform(QTransform.fromScale(1, -1))
        tbr = self.text_item.boundingRect()
        self.text_item.setPos(-tbr.width()/2, tbr.height()/2 + 4)

    def set_pad_dimensions(self, width: float, height: float):
        self.w = width
        self.h = height
        self.setRect(-width/2, -height/2, width, height)
        tbr = self.text_item.boundingRect()
        self.text_item.setPos(-tbr.width()/2, tbr.height()/2 + 4)

    def _apply_color(self):
        # Harmonized Catppuccin Mocha EDA palette
        if self.direction == "input":
            fill = QColor("#a6e3a1")  # Green
        elif self.direction == "output":
            fill = QColor("#89b4fa")  # Blue
        elif self.direction == "inout":
            fill = QColor("#cba6f7")  # Mauve
        elif self.direction in ["power", "ground"]:
            fill = QColor("#f9e2af")  # Yellow
        else:
            fill = QColor("#89dceb")  # Sky
        self.setBrush(QBrush(fill))
        self.setPen(QPen(QColor("#11111b"), 1))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            self.manually_dragged = True
            # Magnetic Snap to Die Edge
            die_rect = getattr(self.dialog, "die_rect", QRectF())
            if die_rect.isValid() and die_rect.width() > 0:
                snapped_pos = self._snap_to_edge(new_pos, die_rect)
                if hasattr(self.dialog, "pins_data") and self.pin_name in self.dialog.pins_data:
                    self.dialog.pins_data[self.pin_name]["x"] = round(snapped_pos.x(), 3)
                    self.dialog.pins_data[self.pin_name]["y"] = round(snapped_pos.y(), 3)
                    self.dialog.pins_data[self.pin_name]["edge"] = self.edge
                    self.dialog.pins_data[self.pin_name]["placed"] = True
                if hasattr(self.dialog, "_user_set_edges"):
                    self.dialog._user_set_edges.add(self.pin_name)
                return snapped_pos
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value:
                self.setPen(QPen(QColor("#00FFFF"), 2))
                if hasattr(self.dialog, "on_pin_selected_in_canvas") and not getattr(self.dialog, "_syncing_selection", False):
                    self.dialog.on_pin_selected_in_canvas(self.pin_name)
            else:
                self.setPen(QPen(QColor("#F0F6FC"), 1))
        return super().itemChange(change, value)

    def _snap_to_edge(self, pt: QPointF, die_rect: QRectF) -> QPointF:
        x = pt.x()
        y = pt.y()
        x_min, x_max = min(die_rect.left(), die_rect.right()), max(die_rect.left(), die_rect.right())
        y_min, y_max = min(die_rect.top(), die_rect.bottom()), max(die_rect.top(), die_rect.bottom())

        dl = abs(x - x_min)
        dr = abs(x - x_max)
        db = abs(y - y_min)
        dt = abs(y - y_max)
        min_d = min(dl, dr, db, dt)

        grid = self.dialog.sp_spacing.value() if hasattr(self.dialog, 'sp_spacing') else 2.0
        if grid < 0.05:
            grid = 0.05

        is_pad = hasattr(self.dialog, "rb_chip") and self.dialog.rb_chip.isChecked()

        if min_d == dl:
            self.edge = "left"
            if is_pad:
                self.set_pad_dimensions(200.0, 80.0)
            y_snap = round(y / grid) * grid
            min_y_bound = (y_min + 214.0 + self.h/2) if is_pad else (y_min + self.h/2 + 2)
            max_y_bound = (y_max - 204.0 - self.h/2) if is_pad else (y_max - self.h/2 - 2)
            y_snap = max(min_y_bound, min(max_y_bound, y_snap))
            if hasattr(self.dialog, "_legalize_edge_pos"):
                y_snap = self.dialog._legalize_edge_pos(self.pin_name, "left", y_snap, self.h)
            x_pos = (x_min + self.w/2 + 10.0) if is_pad else x_min
            return QPointF(x_pos, y_snap)
        elif min_d == dr:
            self.edge = "right"
            if is_pad:
                self.set_pad_dimensions(200.0, 80.0)
            y_snap = round(y / grid) * grid
            min_y_bound = (y_min + 214.0 + self.h/2) if is_pad else (y_min + self.h/2 + 2)
            max_y_bound = (y_max - 204.0 - self.h/2) if is_pad else (y_max - self.h/2 - 2)
            y_snap = max(min_y_bound, min(max_y_bound, y_snap))
            if hasattr(self.dialog, "_legalize_edge_pos"):
                y_snap = self.dialog._legalize_edge_pos(self.pin_name, "right", y_snap, self.h)
            x_pos = (x_max - self.w/2 - 10.0) if is_pad else x_max
            return QPointF(x_pos, y_snap)
        elif min_d == dt:
            self.edge = "top"
            if is_pad:
                self.set_pad_dimensions(80.0, 200.0)
            x_snap = round(x / grid) * grid
            min_x_bound = (x_min + 210.0 + self.w/2) if is_pad else (x_min + self.w/2 + 2)
            max_x_bound = (x_max - 210.0 - self.w/2) if is_pad else (x_max - self.w/2 - 2)
            x_snap = max(min_x_bound, min(max_x_bound, x_snap))
            if hasattr(self.dialog, "_legalize_edge_pos"):
                x_snap = self.dialog._legalize_edge_pos(self.pin_name, "top", x_snap, self.w)
            y_pos = (y_max - self.h/2 - 10.0) if is_pad else y_max
            return QPointF(x_snap, y_pos)
        else:
            self.edge = "bottom"
            if is_pad:
                self.set_pad_dimensions(80.0, 200.0)
            x_snap = round(x / grid) * grid
            min_x_bound = (x_min + 210.0 + self.w/2) if is_pad else (x_min + self.w/2 + 2)
            max_x_bound = (x_max - 210.0 - self.w/2) if is_pad else (x_max - self.w/2 - 2)
            x_snap = max(min_x_bound, min(max_x_bound, x_snap))
            if hasattr(self.dialog, "_legalize_edge_pos"):
                x_snap = self.dialog._legalize_edge_pos(self.pin_name, "bottom", x_snap, self.w)
            y_pos = (y_min + self.h/2 + 10.0) if is_pad else y_min
            return QPointF(x_snap, y_pos)


class EdgeConstraintBox(QGraphicsRectItem):
    """
    Visual perimeter edge constraint region where a group of pins is constrained.
    """
    def __init__(self, name: str, edge: str, start_um: float, end_um: float, die_rect: QRectF, parent=None):
        super().__init__(parent)
        self.box_name = name
        self.edge = edge  # top, bottom, left, right
        self.start_um = start_um
        self.end_um = end_um
        self.die_rect = die_rect

        self.setZValue(-5)
        self.setBrush(QBrush(QColor(137, 180, 250, 50)))  # Catppuccin Blue subtle fill
        self.setPen(QPen(QColor("#89b4fa"), 1.5, Qt.PenStyle.DashLine))

        self.label_item = QGraphicsTextItem(name, self)
        font = self.label_item.font()
        font.setPointSize(8)
        font.setBold(True)
        self.label_item.setFont(font)
        self.label_item.setDefaultTextColor(QColor("#89b4fa"))
        self.label_item.setTransform(QTransform.fromScale(1, -1))

        self.update_geometry(die_rect)

    def update_geometry(self, die_rect: QRectF):
        self.die_rect = die_rect
        x_min, x_max = min(die_rect.left(), die_rect.right()), max(die_rect.left(), die_rect.right())
        y_min, y_max = min(die_rect.top(), die_rect.bottom()), max(die_rect.top(), die_rect.bottom())
        depth = 30.0  # Constraint strip depth in um
        if self.edge == "bottom":
            x1 = self.start_um
            w = max(10.0, self.end_um - self.start_um)
            self.setRect(x1, y_min - depth, w, depth)
            self.label_item.setPos(x1 + 4, y_min - 4)
        elif self.edge == "top":
            x1 = self.start_um
            w = max(10.0, self.end_um - self.start_um)
            self.setRect(x1, y_max, w, depth)
            self.label_item.setPos(x1 + 4, y_max + depth - 4)
        elif self.edge == "left":
            y1 = self.start_um
            h = max(10.0, self.end_um - self.start_um)
            self.setRect(x_min - depth, y1, depth, h)
            self.label_item.setPos(x_min - depth + 4, y1 + h - 4)
        elif self.edge == "right":
            y1 = self.start_um
            h = max(10.0, self.end_um - self.start_um)
            self.setRect(x_max, y1, depth, h)
            self.label_item.setPos(x_max + 4, y1 + h - 4)


def parse_verilog_netlist_pins(project_config: Any, proj_root: str) -> Dict[str, Dict[str, Any]]:
    """
    Extracts pin names and directions from synthesized Verilog netlist if DEF pins are unpopulated.
    """
    pins = {}
    candidates = []
    top = project_config.get("top_module", "") if isinstance(project_config, dict) else ""
    if top:
        candidates.append(os.path.join(proj_root, "netlist", f"{top}_netlist.v"))
        candidates.append(os.path.join(proj_root, "netlist", f"{top}_scan.v"))
    candidates.append(os.path.join(proj_root, "results", "synth.v"))
    netlist_dir = os.path.join(proj_root, "netlist")
    if os.path.isdir(netlist_dir):
        for f in sorted(os.listdir(netlist_dir)):
            if f.endswith(".v"):
                candidates.append(os.path.join(netlist_dir, f))

    for sdir in [os.path.join(proj_root, "rtl"), os.path.join(proj_root, "source")]:
        if os.path.isdir(sdir):
            if top:
                for ext in [".v", ".sv"]:
                    cand_top = os.path.join(sdir, f"{top}{ext}")
                    if os.path.isfile(cand_top):
                        candidates.append(cand_top)
            for f in sorted(os.listdir(sdir)):
                if f.endswith((".v", ".sv")) and not any(t in f.lower() for t in ["tb_", "_tb", "test_"]):
                    candidates.append(os.path.join(sdir, f))

    netlist_path = next((p for p in candidates if os.path.isfile(p)), None)
    if not netlist_path:
        return pins

    try:
        with open(netlist_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        target_block = content
        if top:
            m_top = re.search(rf"module\s+{top}\b(?:\s*#\s*\(.*?\))?\s*\((.*?)\);(.*?)(?:endmodule)", content, re.DOTALL)
            if m_top:
                header_ports = m_top.group(1)
                body_content = m_top.group(2)
                target_block = header_ports + "\n" + body_content

        for m in re.finditer(r"(?:^|[;,(\s])\s*(input|output|inout)\s+(?:wire\s+|reg\s+)?(?:signed\s+)?(?:\[(\d+):(\d+)\]\s+)?([^;,)]+)", target_block, re.MULTILINE):
            direction = m.group(1).lower()
            msb = m.group(2)
            lsb = m.group(3)
            names_str = m.group(4)
            names = [n.strip() for n in names_str.split(",") if n.strip()]

            for name in names:
                name = re.sub(r'//.*$', '', name).strip()
                if not name or name.startswith("//"):
                    continue
                if msb is not None and lsb is not None:
                    high, low = int(msb), int(lsb)
                    step = 1 if high >= low else -1
                    for idx in range(low, high + step, step):
                        pin_name = f"{name}[{idx}]"
                        pins[pin_name] = {"dir": direction, "edge": "bottom", "x": 0.0, "y": 0.0, "box": "All Edges"}
                else:
                    pins[name] = {"dir": direction, "edge": "bottom", "x": 0.0, "y": 0.0, "box": "All Edges"}
    except Exception as e:
        print(f"[io_types] Note parsing verilog netlist: {e}")

    return pins
