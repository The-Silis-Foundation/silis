"""
silis/core/layer_viewer/inspector_widget.py
Pure native Qt6 Object Property Inspector and Hierarchy Tree.
Displays real-time properties of selected ASIC instances, macros, pins, and nets
with direct navigation and flightline triggering.
"""

import os
# ==============================================================================
# Silis Design Property Inspector
#
# Heartfelt compliments, tribute, and attribution to the incredible OpenROAD
# Project community and contributors (The OpenROAD Authors / Precision Innovations).
# Based on OpenROAD's Inspector panel paradigm.
# ==============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QPushButton, QHeaderView, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontDatabase, QColor


class DesignPropertyInspector(QWidget):
    """
    OpenROAD-grade Object Inspector implemented in pure native Qt6.
    Inspects:
      - Selected Instances (cell master, physical bounds, orientation, power domain, I/O terms)
      - Selected Nets (signal type, driver pin, sink pins, routing status, flightline highlight)
    """
    inspect_net_requested = pyqtSignal(str)
    pan_to_requested = pyqtSignal(float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Header Title
        title_box = QHBoxLayout()
        title_lbl = QLabel("<b>Property Inspector</b>")
        title_lbl.setStyleSheet("font-size: 11px;")
        title_box.addWidget(title_lbl)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFixedHeight(22)
        self.btn_clear.clicked.connect(self.clear_inspector)
        title_box.addWidget(self.btn_clear)
        main_layout.addLayout(title_box)

        # Fast Filter
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter properties / terminals...")
        self.filter_edit.textChanged.connect(self._filter_tree)
        main_layout.addWidget(self.filter_edit)

        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Property", "Value"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.setAlternatingRowColors(True)

        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(9)
        self.tree.setFont(font)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        main_layout.addWidget(self.tree)

        self.dbu = 1000.0
        self.current_data = {}

    def set_dbu(self, dbu: float):
        if dbu > 0.0:
            self.dbu = dbu

    def clear_inspector(self):
        self.tree.clear()
        self.filter_edit.clear()
        self.current_data = {}

    def inspect_instance(self, inst_name: str, master: str, x: float, y: float, w: float, h: float,
                         orient: str = "R0", iterms: list = None, power_domain: str = None):
        """Populates the tree with exhaustive physical and logical attributes."""
        self.tree.clear()
        self.current_data = {
            "name": inst_name,
            "master": master,
            "x": x, "y": y, "w": w, "h": h,
            "orient": orient,
            "iterms": iterms or [],
            "domain": power_domain or "PD_TOP"
        }

        # 1. Identity Group
        id_group = QTreeWidgetItem(self.tree, ["Identity", ""])
        id_group.setExpanded(True)
        QTreeWidgetItem(id_group, ["Instance Name", inst_name])
        QTreeWidgetItem(id_group, ["Master Cell", master])
        QTreeWidgetItem(id_group, ["Power Domain", power_domain or "PD_TOP"])

        # 2. Geometry Group
        geom_group = QTreeWidgetItem(self.tree, ["Geometry", ""])
        geom_group.setExpanded(True)
        QTreeWidgetItem(geom_group, ["Origin (µm)", f"({x / self.dbu:.3f}, {y / self.dbu:.3f})"])
        QTreeWidgetItem(geom_group, ["Width (µm)", f"{w / self.dbu:.3f}"])
        QTreeWidgetItem(geom_group, ["Height (µm)", f"{h / self.dbu:.3f}"])
        QTreeWidgetItem(geom_group, ["Orientation", orient])

        # 3. Terminals / Net Connections Group
        terms_group = QTreeWidgetItem(self.tree, [f"Terminals ({len(iterms or [])})", ""])
        terms_group.setExpanded(True)
        for term in (iterms or []):
            pin_name = term.get("pin", "") if isinstance(term, dict) else str(term)
            net_name = term.get("net", "UNCONNECTED") if isinstance(term, dict) else ""
            item = QTreeWidgetItem(terms_group, [pin_name, net_name])
            if net_name and net_name != "UNCONNECTED":
                item.setData(0, Qt.ItemDataRole.UserRole, ("net", net_name))

    def inspect_net(self, net_name: str, sig_type: str = "SIGNAL", driver: str = None,
                    sinks: list = None, is_routed: bool = False):
        """Displays net hierarchy, driving cell pin, receiver pins, and status."""
        self.tree.clear()
        self.current_data = {
            "net": net_name,
            "type": sig_type,
            "driver": driver,
            "sinks": sinks or [],
            "routed": is_routed
        }

        net_group = QTreeWidgetItem(self.tree, ["Net Attributes", ""])
        net_group.setExpanded(True)
        QTreeWidgetItem(net_group, ["Net Name", net_name])
        QTreeWidgetItem(net_group, ["Signal Type", sig_type])
        QTreeWidgetItem(net_group, ["Status", "ROUTED" if is_routed else "UNROUTED"])

        if driver:
            drv_item = QTreeWidgetItem(net_group, ["Driver", driver])
            drv_item.setData(0, Qt.ItemDataRole.UserRole, ("inst", driver.split("/")[0]))

        sinks_group = QTreeWidgetItem(self.tree, [f"Sinks ({len(sinks or [])})", ""])
        sinks_group.setExpanded(True)
        for s in (sinks or []):
            item = QTreeWidgetItem(sinks_group, ["Sink Pin", s])
            item.setData(0, Qt.ItemDataRole.UserRole, ("inst", s.split("/")[0]))

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        dtype, target = data
        if dtype == "net":
            self.inspect_net_requested.emit(target)
        elif dtype == "inst":
            pass

    def _filter_tree(self, text: str):
        query = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            top_match = query in top.text(0).lower() or query in top.text(1).lower()
            any_child_visible = False
            for j in range(top.childCount()):
                child = top.child(j)
                match = query in child.text(0).lower() or query in child.text(1).lower()
                child.setHidden(not (match or top_match or not query))
                if match:
                    any_child_visible = True
            top.setHidden(not (top_match or any_child_visible or not query))
