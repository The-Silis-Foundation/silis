# =============================PEAK!===============================

class HeaderFactory:
    """Central factory for the ASCII branding."""
    ASCII_ART = """
███████╗ ██╗ ██╗      ██╗ ███████╗
██╔════╝ ██║ ██║      ██║ ██╔════╝
███████╗ ██║ ██║      ██║ ███████╗
╚════██║ ██║ ██║      ██║ ╚════██║
███████║ ██║ ███████╗ ██║ ███████║
╚══════╝ ╚═╝ ╚══════╝ ╚═╝ ╚══════╝
    """
    TAGLINE = "Silis — Silicon Scaffold"
    COPYRIGHT = "© 2026 The Silis Foundation"
    LICENSE = "Licensed under AGPL-3.0"

    @staticmethod
    def get_raw_header():
        return f"{HeaderFactory.ASCII_ART}\n{HeaderFactory.TAGLINE}\n{HeaderFactory.COPYRIGHT}\n{HeaderFactory.LICENSE}\n"

import sys
import os
import subprocess
import threading
import queue
import glob
import re
import shutil
import json
import random
import xml.etree.ElementTree as ET
from contextlib import suppress
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtGui import QPalette

# ================= PYQT6 IMPORTS =================
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QTreeView, QTabWidget,
                             QPlainTextEdit, QTextEdit, QToolBar, QPushButton, 
                             QLabel, QLineEdit, QFileDialog, QMessageBox, 
                             QInputDialog, QGraphicsView, QGraphicsScene, 
                             QGraphicsPixmapItem, QMenu, QFrame, QDockWidget,
                             QSizePolicy, QDialog, QFormLayout, QComboBox, 
                             QGraphicsRectItem, QTableWidget, QTableWidgetItem,
                             QHeaderView, QAbstractItemView, QCheckBox, QGroupBox,
                             QToolButton, QStackedWidget, QButtonGroup, 
                             QGraphicsPolygonItem, QGraphicsPathItem, QScrollArea, QListWidget, QFrame, QTabWidget, QGridLayout)
from PyQt6.QtCore import (Qt, QTimer, QSize, pyqtSignal, QThread, QDir, 
                          QEvent, QProcess, QRectF, QPointF)
from PyQt6.QtGui import (QAction, QFont, QColor, QSyntaxHighlighter, 
                         QTextCharFormat, QTextFormat, QPixmap, QPainter, QImage, QBrush, QPen,
                         QFileSystemModel, QKeySequence, QShortcut, QImageReader, 
                         QTransform, QPolygonF, QIcon, QPainterPath, QFontMetrics)
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtSvg import QSvgRenderer

# ================= PDK MANAGEMENT SYSTEM =================

class PDKManager:
    def __init__(self):
        self.cache_file = os.path.expanduser("~/.silis_pdk_cache.json")
        self.configs = []
        self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    self.configs = json.load(f)
            except: self.configs = []

    def save_cache(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.configs, f, indent=2)

    def add_manual_config(self, name, tlef, lef, lib):
        entry = {
            "name": name,
            "tlef": os.path.abspath(tlef),
            "lef": os.path.abspath(lef),
            "lib": os.path.abspath(lib),
            "corner": "Manual"
        }
        self.configs = [c for c in self.configs if c['name'] != name]
        self.configs.insert(0, entry)
        self.save_cache()
        return entry

    def scan_root(self, root_path):
        found = []
        for root, dirs, files in os.walk(root_path):
            for file in files:
                if file.endswith(".lib") and not "pruned" in file:
                    lib_path = os.path.join(root, file)
                    parts = root.split(os.sep)
                    sc_type = "unknown"
                    for p in parts:
                        if "sc_" in p: sc_type = p; break
                    
                    base_dir = os.path.dirname(os.path.dirname(root)) 
                    lef_path = None
                    tlef_path = None
                    
                    for r2, d2, f2 in os.walk(base_dir):
                        for f_cand in f2:
                            full_cand = os.path.join(r2, f_cand)
                            if f_cand.endswith(".tlef"):
                                tlef_path = full_cand
                            elif f_cand.endswith(".lef"):
                                if "magic" in f_cand: continue
                                if "tech" in f_cand: continue 
                                if sc_type in f_cand:
                                    lef_path = full_cand
                    
                    if lib_path and lef_path and tlef_path:
                        entry = {
                            "name": f"{sc_type} ({file.split('.')[0]})",
                            "lib": lib_path,
                            "lef": lef_path,
                            "tlef": tlef_path,
                            "corner": file.split(".")[0]
                        }
                        found.append(entry)
        
        manuals = [c for c in self.configs if c.get("corner") == "Manual"]
        self.configs = manuals + found
        self.save_cache()
        return len(found)

class ManualPDKDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manual PDK Override")
        self.resize(700, 300)
        self.layout = QFormLayout(self)
        
        self.e_name = QLineEdit("My Custom Config")
        self.layout.addRow("Config Name:", self.e_name)
        
        self.e_tlef = QLineEdit()
        b_tlef = QPushButton("Browse Tech LEF (.tlef)"); b_tlef.clicked.connect(lambda: self.browse(self.e_tlef, "Tech LEF (*.tlef *.lef)"))
        self.layout.addRow(b_tlef, self.e_tlef)
        
        self.e_lef = QLineEdit()
        b_lef = QPushButton("Browse Macro LEF (.lef)"); b_lef.clicked.connect(lambda: self.browse(self.e_lef, "Macro LEF (*.lef)"))
        self.layout.addRow(b_lef, self.e_lef)
        
        self.e_lib = QLineEdit()
        b_lib = QPushButton("Browse Timing (.lib)"); b_lib.clicked.connect(lambda: self.browse(self.e_lib, "Liberty (*.lib)"))
        self.layout.addRow(b_lib, self.e_lib)
        
        btn_save = QPushButton("Save & Select"); btn_save.setStyleSheet("background: #00AA00; color: white; font-weight: bold; padding: 10px;")
        btn_save.clicked.connect(self.validate_and_accept)
        self.layout.addRow(btn_save)

    def browse(self, line_edit, filter_str):
        f, _ = QFileDialog.getOpenFileName(self, "Select File", "", filter_str)
        if f: line_edit.setText(f)

    def validate_and_accept(self):
        if not all([self.e_tlef.text(), self.e_lef.text(), self.e_lib.text()]):
            QMessageBox.warning(self, "Error", "All three files (Tech LEF, Macro LEF, Lib) are required.")
            return
        self.accept()

    def get_data(self):
        return self.e_name.text(), self.e_tlef.text(), self.e_lef.text(), self.e_lib.text()

class PDKSelector(QDialog):
    def __init__(self, pdk_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Technology Configuration")
        self.resize(1000, 400)
        self.mgr = pdk_manager
        self.selected_config = None
        
        layout = QVBoxLayout(self)
        
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter (e.g., 'hd', 'tt', '1v80')...")
        self.search.textChanged.connect(self.filter_list)
        layout.addWidget(self.search)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Config Name", "Corner", "Macro LEF", "Tech LEF"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(self.accept_selection)
        layout.addWidget(self.table)
        
        btn_lay = QHBoxLayout()
        btn_scan = QPushButton("Scan Root..."); btn_scan.clicked.connect(self.trigger_scan)
        
        btn_manual = QPushButton("Pick Custom..."); 
        btn_manual.setStyleSheet("color: red; font-weight: bold;")
        btn_manual.clicked.connect(self.trigger_manual)
        
        btn_ok = QPushButton("Select (Enter)"); btn_ok.clicked.connect(self.accept_selection)
        
        btn_lay.addWidget(btn_scan); btn_lay.addWidget(btn_manual); btn_lay.addStretch(); btn_lay.addWidget(btn_ok)
        layout.addLayout(btn_lay)
        
        self.populate()
        self.search.setFocus()

    def populate(self):
        self.table.setRowCount(0)
        filter_txt = self.search.text().lower()
        for cfg in self.mgr.configs:
            if filter_txt and filter_txt not in cfg['name'].lower(): continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(cfg['name']))
            self.table.setItem(row, 1, QTableWidgetItem(cfg['corner']))
            self.table.setItem(row, 2, QTableWidgetItem(os.path.basename(cfg['lef'])))
            self.table.setItem(row, 3, QTableWidgetItem(os.path.basename(cfg['tlef'])))
            
            if "tlef" in os.path.basename(cfg['tlef']):
                self.table.item(row, 3).setForeground(QBrush(QColor("green")))
            else:
                self.table.item(row, 3).setForeground(QBrush(QColor("red")))
            
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, cfg)
        
        if self.table.rowCount() > 0:
            self.table.selectRow(0)

    def filter_list(self): self.populate()

    def trigger_scan(self):
        d = QFileDialog.getExistingDirectory(self, "Select PDK Root (e.g. volare/sky130A)")
        if d:
            n = self.mgr.scan_root(d)
            QMessageBox.information(self, "Scan", f"Found {n} VALID configurations.")
            self.populate()

    def trigger_manual(self):
        d = ManualPDKDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            name, tlef, lef, lib = d.get_data()
            self.mgr.add_manual_config(name, tlef, lef, lib)
            self.search.clear()
            self.populate()
            self.table.selectRow(0)
            self.table.setFocus()

    def accept_selection(self):
        r = self.table.currentRow()
        if r >= 0:
            self.selected_config = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
            self.accept()

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key.Key_Down, Qt.Key.Key_Up]:
            self.table.setFocus()
            self.table.keyPressEvent(event)
        elif event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return:
            self.accept_selection()
        else:
            super().keyPressEvent(event)

# ================= ROBUST DEF PARSER =================

class DEFParser:
    def __init__(self, def_path):
        self.path = def_path
        self.die_rect = QRectF(0,0,0,0)
        self.comps_map = {}   
        self.comp_types = {}  
        self.module_map = {}  
        self.pins = []       
        self.power_rails = [] 
        self.power_routes = [] 
        self.signal_routes = [] # Store signals here
        self.dbu = 1000.0    
        self.component_count = 0
        if os.path.exists(def_path):
            self.parse()

    def parse(self):
        if not os.path.exists(self.path): return

        with open(self.path, 'r') as f:
            lines = f.readlines()

        current_section = None
        std_w, std_h = 5.0, 2.72 
        
        current_comp_name = None
        current_comp_model = None
        current_pin_name = None
        
        # Route State
        current_route_width = 0
        current_route_points = []
        parsing_route = False

        for line in lines:
            try:
                line = line.strip()
                if not line or line.startswith('#'): continue

                # --- GLOBAL ---
                if line.startswith("UNITS DISTANCE MICRONS"):
                    parts = line.split()
                    if len(parts) >= 4:
                        self.dbu = float(parts[3])
                        std_w = 5 * self.dbu 
                        std_h = 2.72 * self.dbu 

                elif line.startswith("DIEAREA"):
                    nums = re.findall(r'(-?\d+)', line)
                    if len(nums) >= 4:
                        x1, y1, x2, y2 = map(int, nums[:4])
                        self.die_rect = QRectF(x1, y1, x2-x1, y2-y1)

                # --- SECTIONS ---
                elif line.startswith("COMPONENTS"): current_section = "COMPONENTS"
                elif line.startswith("PINS"): current_section = "PINS"
                elif line.startswith("SPECIALNETS"): current_section = "SPECIALNETS"
                elif line.startswith("NETS") and "SPECIAL" not in line: current_section = "NETS"
                elif line.startswith("END"): 
                    current_section = None
                    current_comp_name = None
                    parsing_route = False
                    # Flush routes
                    if len(current_route_points) >= 2:
                        if current_section == "SPECIALNETS":
                            self.power_routes.append((current_route_width, current_route_points))
                        elif current_section == "NETS":
                            self.signal_routes.append(current_route_points)
                    current_route_points = []

                # --- COMPONENTS ---
                elif current_section == "COMPONENTS":
                    parts = line.split()
                    if line.startswith("-"):
                        if len(parts) >= 3:
                            current_comp_name = parts[1]
                            current_comp_model = parts[2]
                    
                    if current_comp_name:
                        if "PLACED" in line or "FIXED" in line or "COVER" in line:
                            coord_match = re.search(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                            if coord_match:
                                x = int(coord_match.group(1))
                                y = int(coord_match.group(2))
                                self.comps_map[current_comp_name] = QRectF(x, y, std_w, std_h)
                                
                                is_tap = "tap" in current_comp_model.lower() or "fill" in current_comp_model.lower()
                                self.comp_types[current_comp_name] = "TAP" if is_tap else "STD"
                                # Basic grouping for coloring
                                self.module_map[current_comp_name] = "STD_LOGIC" 
                                self.component_count += 1
                                current_comp_name = None

                # --- PINS ---
                elif current_section == "PINS":
                    parts = line.split()
                    if line.startswith("-"):
                        if len(parts) > 2:
                            current_pin_name = parts[1]
                    
                    if current_pin_name:
                        if "PLACED" in line or "FIXED" in line:
                            coord_match = re.search(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                            if coord_match:
                                x = int(coord_match.group(1))
                                y = int(coord_match.group(2))
                                pin_sz = 1 * self.dbu 
                                self.pins.append((QRectF(x, y, pin_sz, pin_sz), current_pin_name))
                                current_pin_name = None 

                # --- SPECIALNETS (Power) ---
                elif current_section == "SPECIALNETS":
                    if "RECT" in line:
                        nums = re.findall(r'(-?\d+)', line)
                        if len(nums) >= 4:
                            rx1, ry1, rx2, ry2 = map(int, nums[-4:])
                            w = abs(rx2 - rx1)
                            h = abs(ry2 - ry1)
                            if w > 50 * self.dbu or h > 50 * self.dbu:
                                self.power_rails.append(QRectF(min(rx1,rx2), min(ry1,ry2), w, h))
                    
                    if "ROUTED" in line:
                        parsing_route = True
                        if len(current_route_points) >= 2:
                            self.power_routes.append((current_route_width, current_route_points))
                        current_route_points = []
                        w_match = re.search(r'ROUTED\s+\S+\s+(\d+)', line)
                        if w_match: current_route_width = int(w_match.group(1))

                    if parsing_route:
                        if "NEW" in line:
                            if len(current_route_points) >= 2:
                                self.power_routes.append((current_route_width, current_route_points))
                            current_route_points = []

                        if line.startswith("-") or ";" in line:
                            parsing_route = False
                            if len(current_route_points) >= 2:
                                self.power_routes.append((current_route_width, current_route_points))
                            current_route_points = []
                        
                        pts_match = re.findall(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                        for p in pts_match:
                            current_route_points.append(QPointF(int(p[0]), int(p[1])))

                # --- NETS (Signals - THIS WAS MISSING) ---
                elif current_section == "NETS":
                    if "ROUTED" in line:
                        parsing_route = True
                        if len(current_route_points) >= 2:
                            self.signal_routes.append(current_route_points)
                        current_route_points = []

                    if parsing_route:
                        if "NEW" in line or ";" in line or line.startswith("-"):
                            if len(current_route_points) >= 2:
                                self.signal_routes.append(current_route_points)
                            current_route_points = []
                            if line.startswith("-") or ";" in line:
                                parsing_route = False
                        
                        pts_match = re.findall(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                        for p in pts_match:
                            current_route_points.append(QPointF(int(p[0]), int(p[1])))

            except Exception as inner_e:
                continue
        
        # Final Flush
        if len(current_route_points) >= 2:
             if current_section == "SPECIALNETS":
                 self.power_routes.append((current_route_width, current_route_points))
             elif current_section == "NETS":
                 self.signal_routes.append(current_route_points)

        print(f"DEBUG: Parsed {self.component_count} comps, {len(self.power_routes)} pwr_segs, {len(self.signal_routes)} sig_nets.")


# ================= 2. SILICON PEEKER (Thinner Lines) =================

class SiliconPeeker(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Enable GPU Acceleration
        self.setViewport(QOpenGLWidget())
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QColor("#FFFFFF")) 
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # --- THE FIX FOR "BREAKING APART" ---
        # Disables pixel-shifting optimization. Forces a clean redraw of the HUD every frame.
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        
        self.scale(1, -1) 
        
        self.def_data = None
        self.first_load = True
        
        self.show_insts = True
        self.show_pins = True
        self.show_nets = True 
        self.show_power = True
        self.show_heatmap = False
        self.show_territory = False

    def wheelEvent(self, event):
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor
        oldPos = self.mapToScene(event.position().toPoint())
        if event.angleDelta().y() > 0: self.scale(zoomInFactor, zoomInFactor)
        else: self.scale(zoomOutFactor, zoomOutFactor)
        newPos = self.mapToScene(event.position().toPoint())
        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())
        event.accept()
        self.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.viewport().update()

    def drawForeground(self, painter, rect):
        if not self.def_data: return
        
        # --- HUD MODE ---
        painter.save()
        painter.resetTransform()
        
        view_transform = self.transform()
        zoom_level = view_transform.m11() 
        pixels_per_dbu = zoom_level
        pixels_per_micron = pixels_per_dbu * self.def_data.dbu
        
        if pixels_per_micron <= 0.000001:
            painter.restore()
            return

        target_px_width = 150
        target_microns = target_px_width / pixels_per_micron
        
        if target_microns >= 100: display_val = 100
        elif target_microns >= 50: display_val = 50
        elif target_microns >= 10: display_val = 10
        elif target_microns >= 5: display_val = 5
        elif target_microns >= 1: display_val = 1
        elif target_microns >= 0.5: display_val = 0.5
        elif target_microns >= 0.1: display_val = 0.1
        else: display_val = 0.05
        
        bar_width_px = display_val * pixels_per_micron
        
        view_w = self.viewport().width()
        view_h = self.viewport().height()
        
        x_start = view_w - bar_width_px - 20
        y_pos = view_h - 30
        
        # STYLE: BRIGHT RED HUD
        hud_color = QColor("#FF0000") 
        pen = QPen(hud_color, 3) 
        pen.setCosmetic(False) 
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Bracket
        painter.drawLine(int(x_start), int(y_pos), int(x_start + bar_width_px), int(y_pos)) 
        painter.drawLine(int(x_start), int(y_pos), int(x_start), int(y_pos - 8)) 
        painter.drawLine(int(x_start + bar_width_px), int(y_pos), int(x_start + bar_width_px), int(y_pos - 8)) 
        
        # Text
        unit = "µm"
        if display_val < 1: 
            display_val *= 1000
            unit = "nm"
            
        text = f"{int(display_val) if display_val >= 1 else display_val} {unit}"
        
        painter.setPen(hud_color)
        font = QFont("Consolas", 12, QFont.Weight.Bold)
        painter.setFont(font)
        
        # Center Text
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(text)
        text_x = x_start + (bar_width_px - text_w) / 2
        
        painter.drawText(int(text_x), int(y_pos - 12), text)
        
        painter.restore()

    def fit_with_slack(self):
        rect = self.scene.itemsBoundingRect()
        if rect.isNull(): return
        margin = max(rect.width(), rect.height()) * 0.1
        slack_rect = rect.adjusted(-margin, -margin, margin, margin)
        self.fitInView(slack_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def load_def_file(self, path):
        if not os.path.exists(path): return
        try:
            self.def_data = DEFParser(path)
            self.redraw()
            if self.first_load:
                self.fit_with_slack()
                self.first_load = False
        except Exception as e: 
            print(f"Peeker Load Error: {e}")

    def redraw(self):
        try:
            current_transform = self.transform()
            self.scene.clear()
            if not self.def_data: return

            # 1. Die Background
            d = self.def_data.die_rect
            die = QGraphicsRectItem(d)
            die.setPen(QPen(QColor("#000000"), 0))
            die.setBrush(QBrush(QColor("#bebebe"))) 
            die.setZValue(-100)
            self.scene.addItem(die)

            if self.def_data.component_count == 0 and d.width() > 0:
                t = self.scene.addText(f"Parsed {self.def_data.component_count} components")
                t.setPos(d.center().x(), d.center().y())
                t.setTransform(QTransform().scale(100, -100))
                t.setDefaultTextColor(QColor("red"))

            if self.show_heatmap:
                self.draw_organic_heatmap(d)
            else:
                # POWER
                if self.show_power:
                    for r in self.def_data.power_rails:
                        item = QGraphicsRectItem(r)
                        item.setPen(QPen(Qt.PenStyle.NoPen))
                        item.setBrush(QBrush(QColor("#ffaa00"))) 
                        item.setZValue(-5)
                        self.scene.addItem(item)
                    
                    thin_width = d.width() / 1200.0
                    for width, points in self.def_data.power_routes:
                        path = QPainterPath()
                        path.moveTo(points[0])
                        for p in points[1:]: path.lineTo(p)
                        
                        pen = QPen(QColor("#ffaa00"), thin_width)
                        pen.setCapStyle(Qt.PenCapStyle.FlatCap) 
                        item = QGraphicsPathItem(path)
                        item.setPen(pen)
                        item.setZValue(-5)
                        self.scene.addItem(item)

                # NETS
                if self.show_nets:
                    path = QPainterPath()
                    for points in self.def_data.signal_routes:
                        if not points: continue
                        path.moveTo(points[0])
                        for p in points[1:]: path.lineTo(p)
                    
                    pen = QPen(QColor("#AAAAAA"), 0) 
                    item = QGraphicsPathItem(path)
                    item.setPen(pen)
                    item.setZValue(-5) 
                    self.scene.addItem(item)

                # CELLS
                if self.show_insts:
                    for name, rect in self.def_data.comps_map.items():
                        ctype = self.def_data.comp_types[name]
                        item = QGraphicsRectItem(rect)
                        if ctype == "TAP":
                            item.setPen(QPen(Qt.PenStyle.NoPen)) 
                            item.setBrush(QBrush(QColor("#000000"))) 
                            item.setZValue(-4) 
                        else:
                            if self.show_territory:
                                mod_name = self.def_data.module_map.get(name, "misc")
                                h = hash(mod_name)
                                hue = h % 360
                                color = QColor.fromHsl(hue, 150, 200) 
                                item.setPen(QPen(color.darker(150), 0))
                                item.setBrush(QBrush(color))
                            else:
                                item.setPen(QPen(QColor("#00509d"), 0)) 
                                item.setBrush(QBrush(QColor("#4cc9f0"))) 
                            item.setZValue(10)
                        self.scene.addItem(item)

            # PINS
            if self.show_pins:
                for rect, name in self.def_data.pins:
                    cx, cy = rect.center().x(), rect.center().y()
                    sz = max(5 * self.def_data.dbu, d.width() / 150)
                    poly = QPolygonF([QPointF(cx, cy + sz), QPointF(cx - sz/2, cy), QPointF(cx + sz/2, cy)])
                    item = QGraphicsPolygonItem(poly)
                    item.setPen(QPen(QColor("#000000"), 0)) 
                    item.setBrush(QBrush(QColor("#ff0000")))
                    item.setZValue(30)
                    self.scene.addItem(item)
                    
                    text = self.scene.addText(name)
                    text.setPos(cx, cy)
                    sf = d.width() / 1200.0 if d.width() > 0 else 1.0
                    text.setTransform(QTransform().scale(sf, -sf)) 
                    text.setDefaultTextColor(QColor("black"))
                    text.setZValue(31)

            self.setTransform(current_transform)
            
        except Exception as e:
            print(f"Redraw Exception: {e}")

    def draw_organic_heatmap(self, die_rect):
        expansion = 8 * self.def_data.dbu 
        color = QColor(255, 0, 0, 8) 
        brush = QBrush(color)
        
        count = 0
        for rect in self.def_data.comps_map.values():
            count += 1
            if count > 40000: break
            
            big_rect = rect.adjusted(-expansion, -expansion, expansion, expansion)
            final_rect = big_rect.intersected(die_rect)
            
            if not final_rect.isEmpty():
                item = QGraphicsRectItem(final_rect)
                item.setPen(QPen(Qt.PenStyle.NoPen))
                item.setBrush(brush)
                item.setZValue(20)
                self.scene.addItem(item)

# ================= 1. FRONTEND COMPONENTS (Tabs) =================

class SilisExplorer(QTreeView):
    fileOpened = pyqtSignal(str)
    dirChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(QDir.currentPath())
        self.setModel(self.fs_model)
        self.setRootIndex(self.fs_model.index(QDir.currentPath()))
        
        # UI Setup
        for i in range(1, 4): self.setColumnHidden(i, True)
        self.setHeaderHidden(True)
        self.setAnimated(False)
        self.setIndentation(15)
        self.setDragEnabled(False)
        
        # --- CRITICAL FIX: CONNECT MOUSE CLICK ---
        self.doubleClicked.connect(self.on_double_click)

    def on_double_click(self, index):
        path = self.fs_model.filePath(index)
        if self.fs_model.isDir(index):
            self.dirChanged.emit(path)
        else:
            self.fileOpened.emit(path)

    def set_cwd(self, path):
        self.setRootIndex(self.fs_model.index(path))

    def keyPressEvent(self, event):
        idx = self.currentIndex()
        path = self.fs_model.filePath(idx)
        key = event.key()

        if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            if self.fs_model.isDir(idx): self.dirChanged.emit(path) 
            else: self.fileOpened.emit(path) 
            event.accept()
        elif key in [Qt.Key.Key_Backspace, Qt.Key.Key_Escape]:
            # UX: Go up one directory
            parent_dir = os.path.dirname(self.fs_model.filePath(self.rootIndex()))
            self.dirChanged.emit(parent_dir)
            event.accept()
        elif key == Qt.Key.Key_Delete:
            # UX: Delete file protection
            self.ask_delete(path)
            event.accept()
        else:
            super().keyPressEvent(event)

    def ask_delete(self, path):
        if not path or not os.path.exists(path): return
        name = os.path.basename(path)
        reply = QMessageBox.question(self, "Delete", f"Are you sure you want to delete '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isdir(path): shutil.rmtree(path)
                else: os.remove(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete: {e}")
class SilisSchematic(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor("#FFFFFF")) 
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    def load_schematic(self, path):
        self.scene.clear()
        if os.path.exists(path):
            if path.endswith(".svg"):
                item = QGraphicsSvgItem(path)
                self.scene.addItem(item)
                self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            else:
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    self.scene.addPixmap(pixmap)
                    self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0: self.scale(1.25, 1.25)
        else: self.scale(0.8, 0.8)

    # --- PORTED UX: KEYBOARD NAV ---
    def keyPressEvent(self, event):
        key = event.key()
        # Zoom
        if key in [Qt.Key.Key_Plus, Qt.Key.Key_Equal]: self.scale(1.2, 1.2)
        elif key == Qt.Key.Key_Minus: self.scale(0.8, 0.8)
        # Pan (Arrows + WASD support)
        elif key in [Qt.Key.Key_Left, Qt.Key.Key_A]: 
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 20)
        elif key in [Qt.Key.Key_Right, Qt.Key.Key_D]: 
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 20)
        elif key in [Qt.Key.Key_Up, Qt.Key.Key_W]: 
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 20)
        elif key in [Qt.Key.Key_Down, Qt.Key.Key_S]: 
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 20)
        # Reset/Fit
        elif key == Qt.Key.Key_0 or key == Qt.Key.Key_F:
             self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else: 
            super().keyPressEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self.setFont(QFont("Consolas", 11))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()): self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(0, int(top), self.lineNumberArea.width() - 5, self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)
            block = block.next(); top = bottom; bottom = top + self.blockBoundingRect(block).height(); blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(Qt.GlobalColor.yellow).lighter(160))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor); self.codeEditor = editor
    def sizeHint(self): return QSize(self.codeEditor.lineNumberAreaWidth(), 0)
    def paintEvent(self, event): self.codeEditor.lineNumberAreaPaintEvent(event)

# === TAB 1: COMPILE ===
class CompileTab(QWidget):
    def __init__(self, ide_parent):
        super().__init__()
        self.ide = ide_parent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.split = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.split)

        # Explorer
        self.explorer_container = QWidget()
        l_lay = QVBoxLayout(self.explorer_container); l_lay.setContentsMargins(0,0,0,0)
        self.explorer = SilisExplorer(self.ide)
        self.explorer.dirChanged.connect(self.ide.change_directory)
        self.explorer.fileOpened.connect(self.ide.open_file_in_editor)
        l_lay.addWidget(QLabel("PROJECT EXPLORER")); l_lay.addWidget(self.explorer)
        self.split.addWidget(self.explorer_container)

        # Right: Code + Terminal
        self.right_split = QSplitter(Qt.Orientation.Vertical)
        self.split.addWidget(self.right_split)
        
        # Code
        self.code_container = QWidget()
        c_lay = QVBoxLayout(self.code_container); c_lay.setContentsMargins(0,0,0,0)
        self.editor = CodeEditor()
        c_lay.addWidget(QLabel("SOURCE CODE")); c_lay.addWidget(self.editor)
        self.right_split.addWidget(self.code_container)
        
        # Terminal
        self.term_container = QWidget()
        t_lay = QVBoxLayout(self.term_container); t_lay.setContentsMargins(0,0,0,0)
        self.term_log = QTextEdit(); self.term_log.setReadOnly(True)
        self.term_log.setStyleSheet("background: #1e1e1e; color: #e0e0e0; font-family: Consolas;")
        self.term_log.setPlainText(HeaderFactory.get_raw_header())
        
        inp_lay = QHBoxLayout()
        self.mode_btn = QPushButton("[SHELL]"); self.mode_btn.clicked.connect(self.ide.toggle_term_mode)
        self.term_input = QLineEdit(); self.term_input.setStyleSheet("background:#333; color:white;")
        self.term_input.returnPressed.connect(self.ide.handle_terminal_input)
        inp_lay.addWidget(self.mode_btn); inp_lay.addWidget(self.term_input)
        
        t_lay.addWidget(QLabel("TERMINAL")); t_lay.addWidget(self.term_log); t_lay.addLayout(inp_lay)
        self.right_split.addWidget(self.term_container)
        
        self.split.setStretchFactor(0, 1); self.split.setStretchFactor(1, 4)
        self.right_split.setStretchFactor(0, 3); self.right_split.setStretchFactor(1, 1)

# === TAB 2: WAVEFORM ===
# === TAB 2: WAVEFORM ENGINE (Refined) ===



# === TAB 2: WAVEFORM ENGINE (Refined) ===

# === TAB 2: WAVEFORM ENGINE (RISC-V Ready) ===

# === TAB 2: WAVEFORM ENGINE (RISC-V/Bus Ready) ===


# === TAB 2: WAVEFORM ENGINE (Crash-Proof & Fixed Nav) ===

class VCDParser:
    def __init__(self, path):
        self.signals = {}     
        self.names = {}       
        self.widths = {}      
        self.id_map = {}      
        self.end_time = 0
        self.timescale = "1ns"
        if os.path.exists(path): self.parse(path)

    def parse(self, path):
        curr_t = 0
        try:
            with open(path, 'r') as f:
                # 1. READ HEADER
                for line in f:
                    line = line.strip()
                    if not line: continue
                    
                    if line.startswith("$var"):
                        parts = line.split()
                        # Strict check: Needs type, width, id, name (at least 5 parts)
                        if len(parts) >= 5:
                            width = int(parts[2])
                            sid = parts[3]
                            name = parts[4]
                            
                            self.names[sid] = name
                            self.widths[sid] = width
                            self.signals[sid] = []
                            self.id_map[name] = sid
                            
                    elif line.startswith("$timescale"):
                        if len(line.split()) > 1: self.timescale = line.split()[1]
                    
                    elif line.startswith("$enddefinitions"):
                        break

                # 2. READ DATA
                for line in f:
                    line = line.strip()
                    if not line: continue
                    
                    if line.startswith("#"):
                        try: 
                            curr_t = int(line[1:])
                            self.end_time = max(self.end_time, curr_t)
                        except: pass
                    
                    elif line.startswith("$dumpvars") or line.startswith("$end"):
                        continue
                        
                    else:
                        if line.startswith('b'):
                            # Vector: b1010 ID
                            parts = line.split()
                            if len(parts) < 2: continue # Skip malformed lines
                            
                            val_bin = parts[0][1:] 
                            sid = parts[1]
                            
                            if sid in self.signals:
                                try: 
                                    val_hex = hex(int(val_bin, 2))[2:].upper()
                                    if len(val_hex) > 1 and len(val_hex) % 2 != 0: val_hex = "0" + val_hex
                                except: 
                                    val_hex = "X" if 'x' in val_bin else "Z"
                                
                                sig = self.signals[sid]
                                if not sig or sig[-1][1] != val_hex:
                                    sig.append((curr_t, val_hex))
                        else:
                            # Scalar: 1# or 1 #
                            # Sometimes no space: '1!', '0!'
                            if len(line) < 2: continue
                            
                            val = line[0]
                            sid = line[1:].strip()
                            
                            if sid in self.signals:
                                sig = self.signals[sid]
                                if not sig or sig[-1][1] != val:
                                    sig.append((curr_t, val))
                                    
        except Exception as e: print(f"VCD Parse Error (Non-Fatal): {e}")

class WaveformCanvas(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.data = None
        self.zoom = 1.0 
        self.offset_x = 0
        self.cursor_time = 0
        self.sidebar_width = 180 
        
        self.selected_row = 0
        self.visible_ids = []
        
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_data(self, parser): 
        self.data = parser
        if self.data:
            self.visible_ids = list(self.data.signals.keys())
            total_h = (len(self.visible_ids) * 40) + 60
            self.setMinimumHeight(total_h)
            self.resize(self.width(), total_h)
        self.update()

    def format_time(self, t):
        return f"{t} {self.data.timescale}" if self.data else f"{t}"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Backgrounds
        painter.fillRect(self.rect(), QColor("#1e1e1e"))
        painter.fillRect(0, 0, self.sidebar_width, self.height(), QColor("#252526"))
        
        if not self.data: 
            painter.setPen(QColor("#666"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Waveform Loaded")
            return
        
        row_h = 40
        
        # 2. Highlight Active Row
        highlight_y = (self.selected_row * row_h) + 30
        painter.fillRect(0, highlight_y, self.width(), row_h, QColor(255, 255, 255, 15))
        
        # 3. Grid
        painter.setPen(QPen(QColor("#333333"), 1, Qt.PenStyle.DotLine))
        for x in range(self.sidebar_width, self.width(), 100):
            painter.drawLine(x, 0, x, self.height())

        # 4. Draw Signals
        y = 40
        font_main = QFont("Consolas", 10); painter.setFont(font_main)
        
        for i, sid in enumerate(self.visible_ids):
            name = self.data.names[sid]
            width = self.data.widths[sid]
            trans = self.data.signals[sid]
            
            # Sidebar Text
            if i == self.selected_row: painter.setPen(QColor("#ffffff"))
            else: painter.setPen(QColor("#aaaaaa"))
            
            label = f"{name} [{width}]" if width > 1 else name
            elided = self.fontMetrics().elidedText(label, Qt.TextElideMode.ElideMiddle, self.sidebar_width - 10)
            painter.drawText(10, y + 5, elided)
            
            # --- WAVEFORM RENDER ---
            prev_x = self.sidebar_width - self.offset_x
            prev_val = 'x'
            if trans and trans[0][0] == 0: prev_val = trans[0][1]
            elif trans: prev_val = 'x'

            draw_trans = trans + [(self.data.end_time, prev_val)]
            
            for t, val in draw_trans:
                x = self.sidebar_width + (t * self.zoom) - self.offset_x
                
                if x < self.sidebar_width: 
                    prev_x = max(self.sidebar_width, x); prev_val = val; continue
                if prev_x > self.width(): break
                
                # A. SINGLE BIT
                if width == 1:
                    if prev_val == '1': c = QColor("#4EC9B0"); h_curr = y - 10
                    elif prev_val == '0': c = QColor("#2c5d52"); h_curr = y + 10
                    elif prev_val in ['z', 'Z']: c = QColor("#dcdcaa"); h_curr = y
                    else: c = QColor("#f44747"); h_curr = y
                    
                    painter.setPen(QPen(c, 2))
                    painter.drawLine(int(prev_x), int(h_curr), int(x), int(h_curr))
                    
                    if val != prev_val:
                        h_next = y - 10 if val == '1' else (y + 10 if val == '0' else y)
                        painter.setPen(QColor("#555"))
                        painter.drawLine(int(x), int(h_curr), int(x), int(h_next))

                # B. BUS (Hex Shape)
                else:
                    is_valid = not ('X' in str(prev_val) or 'Z' in str(prev_val))
                    c_bus = QColor("#4EC9B0") if is_valid else QColor("#f44747")
                    
                    path = QPainterPath()
                    path.moveTo(prev_x, y)
                    path.lineTo(prev_x + 4, y - 8)
                    path.lineTo(x - 4, y - 8)
                    path.lineTo(x, y)
                    path.lineTo(x - 4, y + 8)
                    path.lineTo(prev_x + 4, y + 8)
                    path.closeSubpath()
                    
                    painter.setPen(QPen(c_bus, 1))
                    painter.setBrush(QColor(c_bus.red(), c_bus.green(), c_bus.blue(), 40))
                    painter.drawPath(path)
                    
                    if (x - prev_x) > 25: 
                        painter.setPen(QColor("#fff")); painter.setFont(QFont("Arial", 8))
                        painter.drawText(QRectF(prev_x, y - 8, x - prev_x, 16), Qt.AlignmentFlag.AlignCenter, str(prev_val))
                        painter.setFont(font_main)

                prev_x = x; prev_val = val
            y += row_h
            
        # 5. Cursor
        cx = self.sidebar_width + (self.cursor_time * self.zoom) - self.offset_x
        if cx > self.sidebar_width:
            painter.setPen(QPen(QColor("#FFD700"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(cx), 0, int(cx), self.height())
            painter.drawText(int(cx)+5, 20, self.format_time(self.cursor_time))
            
        # 6. Sidebar Line
        painter.setPen(QPen(QColor("#444"), 2))
        painter.drawLine(self.sidebar_width, 0, self.sidebar_width, self.height())
        
        # (Watermark removed from here)

    def mouseMoveEvent(self, e):
        if e.pos().x() > self.sidebar_width:
            rel_x = e.pos().x() - self.sidebar_width + self.offset_x
            self.cursor_time = int(max(0, rel_x / self.zoom))
            self.update()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0: self.zoom *= 1.1
        else: self.zoom *= 0.9
        self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Up: self.zoom *= 1.2
        elif key == Qt.Key.Key_Down: self.zoom *= 0.8
        elif key == Qt.Key.Key_W:
            self.selected_row = max(0, self.selected_row - 1)
            self.ensure_row_visible()
        elif key == Qt.Key.Key_S:
            self.selected_row = min(len(self.visible_ids) - 1, self.selected_row + 1)
            self.ensure_row_visible()
        elif key in [Qt.Key.Key_D, Qt.Key.Key_Right]: self.jump_edge(forward=True)
        elif key in [Qt.Key.Key_A, Qt.Key.Key_Left]: self.jump_edge(forward=False)
        elif key == Qt.Key.Key_F: self.controller.fit_view()
        self.update()

    def ensure_row_visible(self):
        row_y = (self.selected_row * 40) + 40
        if self.parentWidget(): self.parentWidget().parentWidget().ensureVisible(0, row_y, 0, 50)

    def jump_edge(self, forward=True):
        if not self.data or not self.visible_ids: return
        sid = self.visible_ids[self.selected_row]
        trans = self.data.signals[sid]
        target = self.cursor_time; found = False
        if forward:
            for t, v in trans:
                if t > self.cursor_time: target = t; found = True; break
            if not found: target = self.data.end_time 
        else:
            for t, v in reversed(trans):
                if t < self.cursor_time: target = t; found = True; break
            if not found: target = 0 
        self.cursor_time = target
        screen_x = self.sidebar_width + (self.cursor_time * self.zoom) - self.offset_x
        if screen_x > self.width(): self.offset_x += (screen_x - self.width()) + 100
        if screen_x < self.sidebar_width: self.offset_x = max(0, (self.cursor_time * self.zoom) - 100)
        self.update()


class SignalPeeker(QWidget):
    def __init__(self, ide):
        super().__init__()
        self.ide = ide; lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        
        tb_widget = QWidget()
        tb_widget.setStyleSheet("background: #252526; border-bottom: 1px solid #333;")
        tb = QHBoxLayout(tb_widget); tb.setContentsMargins(5,5,5,5)
        btn_style = "QPushButton { background: #333; color: white; border: 1px solid #555; padding: 4px 10px; border-radius: 3px; } QPushButton:hover { background: #444; }"
        self.btn_load = QPushButton("📂 Load VCD"); self.btn_load.setStyleSheet(btn_style); self.btn_load.clicked.connect(self.manual_load)
        self.btn_gtk = QPushButton("🌊 GTKWave"); self.btn_gtk.setStyleSheet(btn_style); self.btn_gtk.clicked.connect(self.launch_gtkwave)
        self.btn_fit = QPushButton("↔ Fit (F)"); self.btn_fit.setStyleSheet(btn_style); self.btn_fit.clicked.connect(self.fit_view)
        self.lbl_info = QLabel("No Waveform Loaded"); self.lbl_info.setStyleSheet("color: #888; font-family: Consolas; margin-left: 10px;")
        tb.addWidget(self.btn_load); tb.addWidget(self.btn_gtk); tb.addWidget(self.btn_fit); tb.addWidget(self.lbl_info); tb.addStretch()
        lay.addWidget(tb_widget)
        
        self.cvs = WaveformCanvas(self)
        self.scroll = QScrollArea(); self.scroll.setWidget(self.cvs); self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; }"); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        lay.addWidget(self.scroll)
        self.current_vcd_path = None

    # --- NEW: PAINT EVENT OVERRIDE FOR FLOATING WATERMARK ---
    def paintEvent(self, event):
        # 1. Draw children first (the toolbar and scroll area)
        super().paintEvent(event)
        
        # 2. Draw Overlay
        painter = QPainter(self)
        wm_text = "POWERED BY SIGNALPEEKER"
        painter.setPen(QColor("#00FFFF")) 
        painter.setFont(QFont("Arial", 6, QFont.Weight.Bold)) # Tiny
        painter.setOpacity(0.5) 
        
        # Draw in bottom right of the CONTAINER widget's rect
        painter.drawText(self.rect().adjusted(-5, -5, -25, -5), # Adjusted to not hit scrollbar area
                        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, wm_text)

    def manual_load(self):
        t, _ = QFileDialog.getOpenFileName(self, "Open VCD", self.ide.cwd, "*.vcd")
        if t: self.load_file(t)

    def auto_load(self):
        candidates = glob.glob(os.path.join(self.ide.cwd, "*.vcd"))
        parent_dir = os.path.dirname(self.ide.cwd)
        candidates += glob.glob(os.path.join(parent_dir, "*.vcd"))
        if candidates: self.load_file(max(candidates, key=os.path.getctime))
        else: self.lbl_info.setText("No .vcd files found.")

    def load_file(self, path):
        self.current_vcd_path = path; self.ide.log_system(f"Loading Waves: {os.path.basename(path)}")
        self.lbl_info.setText(f"Active: {os.path.basename(path)}")
        parser = VCDParser(path); self.cvs.set_data(parser); self.fit_view(); self.cvs.setFocus()

    def fit_view(self):
        if self.cvs.data and self.cvs.data.end_time > 0:
            available_w = self.scroll.width() - self.cvs.sidebar_width - 20
            self.cvs.zoom = max(0.0001, available_w / self.cvs.data.end_time)
            self.cvs.offset_x = 0; self.cvs.update()
            
    def launch_gtkwave(self):
        if self.current_vcd_path: subprocess.Popen(["gtkwave", self.current_vcd_path])
        else: QMessageBox.information(self, "Info", "Load a VCD file first.")

# === TAB 3: SCHEMATIC ===
class SchematicTab(QWidget):
    def __init__(self, ide):
        super().__init__()
        self.ide = ide; lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        tb = QHBoxLayout()
        self.btn_gen = QPushButton("Generate Logic View"); self.btn_gen.clicked.connect(self.ide.generate_schematic)
        btn_fit = QPushButton("Fit"); btn_fit.clicked.connect(lambda: self.view.fitInView(self.view.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio))
        tb.addWidget(self.btn_gen); tb.addWidget(btn_fit); tb.addStretch()
        self.view = SilisSchematic(); lay.addLayout(tb); lay.addWidget(self.view)

# === TAB 4: SYNTHESIS ===
# === TAB 4: SYNTHESIS MISSION CONTROL ===

# === TAB 4: SYNTHESIS DASHBOARD (Unified & Clean) ===

# =============================================================================
#  TAB 4: SYNTHESIS & REPORTING ENGINE
# =============================================================================

import re
import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, 
                             QLabel, QPushButton, QTabWidget, QTextEdit, 
                             QListWidget, QGridLayout, QFileDialog)
from PyQt6.QtCore import Qt

# =============================================================================
#  TAB 4: SYNTHESIS & REPORTING ENGINE
# =============================================================================

# =============================================================================
#  TAB 4: SYNTHESIS & REPORTING ENGINE (Power & Timing Enhanced)
# =============================================================================

# ================= REPORTING ENGINE (VISUAL SPLIT) =================

class ReportEngine:
    """Parses logs and generates the 'Visual Split' ASCII report format."""
    
    FOOTER_ART = HeaderFactory.ASCII_ART

    @staticmethod
    def parse_metrics(full_log):
        metrics = {
            "area": "Unknown", "cells": "0", "wires": "0", "bits": "0",
            "wns": "0.00", "status": "UNKNOWN", "clk": "Unknown",
            "critical_path_trace": "No path data found",
            "pwr_seq": ["0", "0", "0", "0", "0%"],
            "pwr_comb": ["0", "0", "0", "0", "0%"],
            "pwr_clk": ["0", "0", "0", "0", "0%"],
            "pwr_mac": ["0", "0", "0", "0", "0%"],
            "pwr_pad": ["0", "0", "0", "0", "0%"],
            "pwr_tot": ["0", "0", "0", "0", "100%"],
            "pwr_pct": ["0%", "0%", "0%"],
            "errors": [], "timing_groups": [], "cell_list": []
        }
        
        # --- 1. DESIGN STATISTICS ---
        if "Number of wires:" in full_log:
            metrics["wires"] = re.search(r"Number of wires:\s+(\d+)", full_log).group(1)
            metrics["bits"] = re.search(r"Number of public wire bits:\s+(\d+)", full_log).group(1)
            metrics["cells"] = re.search(r"Number of cells:\s+(\d+)", full_log).group(1)
            area_m = re.search(r"Chip area for .*?:\s+([\d\.]+)", full_log)
            if area_m: metrics["area"] = area_m.group(1)

        # --- 2. CELL UTILIZATION ---
        raw_cells = re.findall(r"(sky130_fd_sc_hd__\w+)\s+cells:\s+(\d+)", full_log)
        if raw_cells:
            metrics["cell_list"] = sorted([(k, int(v)) for k, v in raw_cells], key=lambda x: x[1], reverse=True)

        # --- 3. TIMING SUMMARY & TRACE ---
        path_blocks = full_log.split("Path Group: ")
        for block in path_blocks[1:]:
            lines = block.split('\n')
            group_name = lines[0].strip()
            slack_line = next((l for l in lines if "slack (" in l), None)
            end_line = next((l for l in lines if "Endpoint:" in l), None)
            
            if slack_line and end_line:
                slack_val = slack_line.split()[0]
                status = "VIOLATED" if "VIOLATED" in slack_line else "MET"
                endpoint = end_line.split("Endpoint: ")[1].split()[0]
                metrics["timing_groups"].append((group_name, slack_val, status, endpoint))
                
                if status == "VIOLATED" and metrics["status"] == "UNKNOWN":
                    metrics["status"] = "VIOLATED"
                    metrics["wns"] = slack_val

        if metrics["status"] == "UNKNOWN": metrics["status"] = "MET"

        trace_match = re.search(r"(Startpoint:.*?slack \(\w+\))", full_log, re.DOTALL)
        if trace_match: metrics["critical_path_trace"] = trace_match.group(1)

        # --- 4. POWER ANALYSIS ---
        for line in full_log.split('\n'):
            parts = line.split()
            if not parts: continue
            if parts[0] == "Sequential" and len(parts)>=6: metrics["pwr_seq"] = parts[1:6]
            elif parts[0] == "Combinational" and len(parts)>=6: metrics["pwr_comb"] = parts[1:6]
            elif parts[0] == "Clock" and len(parts)>=6: metrics["pwr_clk"] = parts[1:6]
            elif parts[0] == "Macro" and len(parts)>=6: metrics["pwr_mac"] = parts[1:6]
            elif parts[0] == "Pad" and len(parts)>=6: metrics["pwr_pad"] = parts[1:6]
            elif parts[0] == "Total" and len(parts)>=6: metrics["pwr_tot"] = parts[1:6]
            elif "%" in parts[0] and len(parts)>=3 and "Total" not in line: metrics["pwr_pct"] = parts[0:3]

        # --- 5. ERRORS ---
        for line in full_log.split('\n'):
            if "Warning:" in line or "ERROR" in line:
                if len(metrics["errors"]) < 10: metrics["errors"].append(line.strip())

        return metrics

    @staticmethod
    def _bar(pct_str):
        try:
            val = float(pct_str.strip('%'))
            blocks = int(val / 10)
            return f"|{'█'*blocks}{'-'*(10-blocks)}| {pct_str}"
        except: return "|----------| 0.0%"

    @staticmethod
    def generate_report(metrics, design_name="riscv_core"):
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        def pr(name, d):
            split_vis = ReportEngine._bar(d[4])
            return f"| {name:<14} | {d[0]:<10} | {d[1]:<10} | {d[2]:<10} | {d[3]:<10} | {d[4]:<6} | {split_vis:<16} |"

        t_table = ""
        for g, s, st, end in metrics["timing_groups"]:
            t_table += f"| {g:<13} | {s+' ns':<11} | {st:<10} | {end:<25} |\n"

        c_table = ""
        total_c = int(metrics["cells"]) if int(metrics["cells"]) > 0 else 1
        for name, count in metrics["cell_list"][:12]: 
            pct = (count / total_c) * 100
            c_table += f"| {name:<30} | {str(count):<6} | {pct:<4.1f}% |\n"

        rpt = f"""################################################################################
#                                            POWER AREA TIMING REPORT
# Design:       {design_name}
# Date:         {now}
# PDK:          Sky130 (High Density)
# Generated by Silis — Silicon Scaffold
# © 2026 The Silis Foundation
################################################################################

================================================================================
  SECTION 1: DESIGN STATISTICS
================================================================================
+---------------------------+-------------------+
| Metric                    | Value             |
+---------------------------+-------------------+
| Total Cells               | {metrics['cells']:<17} |
| Total Area                | {metrics['area'] + ' um^2':<17} |
| Total Wires               | {metrics['wires']:<17} |
| Public Wire Bits          | {metrics['bits']:<17} |
+---------------------------+-------------------+

================================================================================
  SECTION 2: TIMING SUMMARY
================================================================================
+---------------+-------------+------------+---------------------------+
| Path Group    | Slack       | Status     | Critical Endpoint         |
+---------------+-------------+------------+---------------------------+
{t_table}+---------------+-------------+------------+---------------------------+

[ DETAILED TIMING REPORT ]
  Worst Negative Slack (WNS): {metrics['wns']} ns ({metrics['status']})
  
  CRITICAL PATH TRACE:
  {metrics['critical_path_trace'].replace(chr(10), chr(10)+'  ')}

================================================================================
  SECTION 3: POWER ANALYSIS
================================================================================
+----------------+------------+------------+------------+------------+--------+------------------+
| Group          | Internal   | Switching  | Leakage    | Total      | %      | Split            |
|                | Power (W)  | Power (W)  | Power (W)  | Power (W)  |        |                  |
+----------------+------------+------------+------------+------------+--------+------------------+
{pr("Sequential", metrics['pwr_seq'])}
{pr("Combinational", metrics['pwr_comb'])}
{pr("Clock", metrics['pwr_clk'])}
{pr("Macro", metrics['pwr_mac'])}
{pr("Pad", metrics['pwr_pad'])}
+----------------+------------+------------+------------+------------+--------+------------------+
| TOTAL          | {metrics['pwr_tot'][0]:<10} | {metrics['pwr_tot'][1]:<10} | {metrics['pwr_tot'][2]:<10} | {metrics['pwr_tot'][3]:<10} | 100%   | |██████████| 100% |
|                | {metrics['pwr_pct'][0]:<10} | {metrics['pwr_pct'][1]:<10} | {metrics['pwr_pct'][2]:<10} |            |        |                  |
+----------------+------------+------------+------------+------------+--------+------------------+

  Split: {metrics['pwr_pct'][0]} Internal / {metrics['pwr_pct'][1]} Switching

[ WARNINGS ]
{chr(10).join(['  ! '+e for e in metrics['errors']]) if metrics['errors'] else "  (None)"}

================================================================================
  SECTION 4: CELL UTILIZATION (Top 12)
================================================================================
+--------------------------------+--------+-------+
| Cell Name                      | Count  | %     |
+--------------------------------+--------+-------+
{c_table}+--------------------------------+--------+-------+

{ReportEngine.FOOTER_ART}
https://github.com/The-Silis-Foundation/silis
________________________________________________________________________________
Generated by Silis — Silicon Scaffold
© 2026 The Silis Foundation
Licensed under AGPL-3.0
________________________________________________________________________________
=== BACKEND ENGINE CREDITS ===
+-----------------------+----------------------------------------------+
| Component             | Version / Source                             |
+-----------------------+----------------------------------------------+
| Synthesis             | Yosys 0.33+ (git sha1 2584903)               |
| Timing Analysis       | OpenSTA 2.4.0                                |
| PDK Manager           | Silis SSA Forge (PDK Mapping & Alias)        |
+-----------------------+----------------------------------------------+
"""
        return rpt

class SynthesisTab(QWidget):
    def __init__(self, ide):
        super().__init__()
        self.ide = ide
        lay = QHBoxLayout(self) 
        lay.setContentsMargins(10, 10, 10, 10); lay.setSpacing(15)

        # === LEFT COLUMN (LOGS) ===
        left_col = QWidget()
        l_lay = QVBoxLayout(left_col); l_lay.setContentsMargins(0,0,0,0)
        
        ctrl = QFrame(); ctrl.setStyleSheet("background: #f6f8fa; border-radius: 4px; padding: 5px; border: 1px solid #d0d7de;")
        cl = QHBoxLayout(ctrl); cl.setContentsMargins(5,5,5,5)
        self.lbl_pdk = QLabel("Active PDK: Sky130A"); self.lbl_pdk.setStyleSheet("font-weight:bold; color:#24292f;")
        
        btn_style = "QPushButton { background: #ffffff; color: #24292f; border: 1px solid #d0d7de; padding: 5px 15px; border-radius: 3px; } QPushButton:hover { background: #f3f4f6; }"
        run_style = "QPushButton { background: #2da44e; color: white; border: 1px solid #2da44e; padding: 5px 15px; border-radius: 3px; font-weight: bold; } QPushButton:hover { background: #2c974b; }"

        btn_sel = QPushButton("⚙ PDK"); btn_sel.setStyleSheet(btn_style)
        btn_sel.clicked.connect(self.ide.open_pdk_selector)
        self.btn_run = QPushButton("Run Flow"); self.btn_run.setStyleSheet(run_style)
        self.btn_run.clicked.connect(self.ide.run_synthesis_flow)
        
        cl.addWidget(self.lbl_pdk); cl.addStretch(); cl.addWidget(btn_sel); cl.addWidget(self.btn_run)
        l_lay.addWidget(ctrl)
        
        self.log_tabs = QTabWidget()
        self.log_tabs.setStyleSheet("QTabWidget::pane { border: 0; } QTabBar::tab { background: #f6f8fa; color: #57606a; padding: 8px; border: 1px solid #e1e4e8; border-bottom: none; } QTabBar::tab:selected { background: #fff; color: #24292f; border-top: 2px solid #fd8c73; }")
        
        self.log_main = QTextEdit(); self.log_main.setReadOnly(True)
        self.log_main.setStyleSheet("background:#0d1117; color:#c9d1d9; font-family:Consolas; border:none;")
        self.log_tabs.addTab(self.log_main, "Build Output")
        
        # --- UI FIX: WHITE ERRORS TAB ---
        self.list_err = QListWidget()
        # White background, Red text for errors
        self.list_err.setStyleSheet("background:#ffffff; color:#cf222e; font-family:Consolas; border:1px solid #d0d7de; padding: 5px;")
        self.log_tabs.addTab(self.list_err, "Issues / Errors")
        
        l_lay.addWidget(self.log_tabs)
        lay.addWidget(left_col, stretch=2) # Main log gets 2/3 width

        # === RIGHT COLUMN (DASHBOARD) - COMPACTED ===
        right_col = QFrame()
        right_col.setStyleSheet("background: #f6f8fa; border-left: 1px solid #d0d7de;")
        right_col.setFixedWidth(360) # Slightly wider for the Split bars
        r_lay = QVBoxLayout(right_col)
        
        self.card_status = QLabel("READY")
        self.card_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_status.setStyleSheet("background:#eaeef2; color:#57606a; font-size:14px; font-weight:bold; padding:10px; border-radius:6px; border: 1px solid #d0d7de;")
        r_lay.addWidget(self.card_status)
        
        grid_w = QWidget(); grid = QGridLayout(grid_w)
        v_style = "font-weight:bold; font-size:12px; color: #24292f;"
        grid.addWidget(QLabel("WNS (Slack):"), 0, 0); lbl = QLabel("--"); lbl.setStyleSheet(v_style); self.val_wns = lbl; grid.addWidget(lbl, 0, 1)
        grid.addWidget(QLabel("Chip Area:"), 1, 0); lbl2 = QLabel("--"); lbl2.setStyleSheet(v_style); self.val_area = lbl2; grid.addWidget(lbl2, 1, 1)
        grid.addWidget(QLabel("Gate Count:"), 2, 0); lbl3 = QLabel("--"); lbl3.setStyleSheet(v_style); self.val_gates = lbl3; grid.addWidget(lbl3, 2, 1)
        r_lay.addWidget(grid_w)
        
        r_lay.addWidget(QLabel("<b style='color:#24292f'>Report Preview:</b>"))
        self.preview = QTextEdit(); self.preview.setReadOnly(True)
        # Smaller height to keep focus on logs
        self.preview.setMaximumHeight(250) 
        self.preview.setStyleSheet("font-family:Consolas; font-size:8pt; background:#ffffff; color:#333; border:1px solid #d0d7de;")
        self.preview.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        r_lay.addWidget(self.preview)
        
        btn_save = QPushButton("Save .rpt File"); btn_save.setStyleSheet("background:#fff; border:1px solid #ccc; padding:5px;")
        btn_save.clicked.connect(self.save_report)
        r_lay.addWidget(btn_save)
        r_lay.addStretch()
        
        lay.addWidget(right_col, stretch=1)

    def update_dashboard(self):
        full_log = self.log_main.toPlainText()
        _, base = self.ide.get_context()
        m = ReportEngine.parse_metrics(full_log)
        
        if m["status"] == "MET":
            self.card_status.setText("TIMING MET")
            self.card_status.setStyleSheet("background:#2da44e; color:white; font-weight:bold; padding:10px; border-radius:6px;")
        elif m["status"] == "VIOLATED":
            self.card_status.setText("TIMING FAIL")
            self.card_status.setStyleSheet("background:#cf222e; color:white; font-weight:bold; padding:10px; border-radius:6px;")
            
        self.val_wns.setText(f"{m['wns']} ns")
        self.val_area.setText(f"{m['area']} um^2")
        self.val_gates.setText(m['cells'])
        
        self.list_err.clear()
        for e in m['errors']: self.list_err.addItem(e)
        if m['errors']: self.log_tabs.setCurrentIndex(1)
        
        rpt = ReportEngine.generate_report(m, base or "design")
        self.preview.setPlainText(rpt)
        self.last_report = rpt
        
        # --- PRINT TO TERMINAL ---
        self.ide.log_system("Generating Power Area Timing (PAT) Report...", "SYS")
        print(rpt) # This goes to stdout (your console)
        self.ide.log_system("Report generated in background.", "RPT")

    def save_report(self):
        if not hasattr(self, 'last_report'): return
        _, base = self.ide.get_context()
        report_name = f"{base or 'design'}_PAT.rpt"
        path, _ = QFileDialog.getSaveFileName(self, "Save PAT Report", report_name, "Report Files (*.rpt)")
        if path:
            with open(path, 'w') as f: f.write(self.last_report)
            self.ide.log_system(f"Report saved: {os.path.basename(path)}")
# =============================================================================
#  MAIN APPLICATION: SILIS IDE
# =============================================================================


# ================= 2. BACKEND COMPONENT =================

class BackendWidget(QWidget):
    def __init__(self, parent_ide):
        super().__init__(parent_ide)
        self.ide = parent_ide 
        self.pdk_mgr = PDKManager()
        self.active_pdk = None
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        # 1. TOP RIBBON
        self.ribbon = QFrame()
        self.ribbon.setStyleSheet("background: #f0f0f0; border-bottom: 1px solid #ccc;")
        self.ribbon.setFixedHeight(40) 
        r_lay = QHBoxLayout(self.ribbon)
        r_lay.setContentsMargins(5,2,5,2)
        
        self.steps = ["Init", "Floorplan", "Tapcells", "PDN", "IO Pins", "Place", "CTS", "Route", "GDS"]
        for step in self.steps:
            btn = QPushButton(step)
            btn.setStyleSheet("padding: 2px; font-weight: bold; font-size: 11px;")
            btn.clicked.connect(lambda _, s=step: self.run_flow_step(s))
            r_lay.addWidget(btn)
        
        r_lay.addStretch()
        btn_rst = QPushButton("🔄 Reset"); btn_rst.clicked.connect(self.reset_backend); r_lay.addWidget(btn_rst)
        btn_cfg = QPushButton("⚙ PDK"); btn_cfg.clicked.connect(self.open_pdk_selector); r_lay.addWidget(btn_cfg)
        self.layout.addWidget(self.ribbon)
        
        # 2. MAIN SPLIT
        v_split = QSplitter(Qt.Orientation.Vertical)
        
        # 2a. UPPER AREA
        h_widget = QWidget()
        h_lay = QHBoxLayout(h_widget); h_lay.setContentsMargins(0,0,0,0); h_lay.setSpacing(0)
        
        # LEFT SIDEBAR
        sidebar = QFrame()
        sidebar.setFixedWidth(110)
        sidebar.setStyleSheet("background: #e8e8e8; border-right: 1px solid #aaa;")
        s_lay = QVBoxLayout(sidebar); s_lay.setContentsMargins(5,10,5,10)
        
        s_lay.addWidget(QLabel("<b>Layers</b>"))
        self.chk_inst = QCheckBox("Cells"); self.chk_inst.setChecked(True); self.chk_inst.toggled.connect(self.update_view); s_lay.addWidget(self.chk_inst)
        self.chk_pins = QCheckBox("Pins"); self.chk_pins.setChecked(True); self.chk_pins.toggled.connect(self.update_view); s_lay.addWidget(self.chk_pins)
        self.chk_nets = QCheckBox("Nets"); self.chk_nets.setChecked(False); self.chk_nets.toggled.connect(self.update_view); s_lay.addWidget(self.chk_nets)
        self.chk_power = QCheckBox("Power"); self.chk_power.setChecked(True); self.chk_power.toggled.connect(self.update_view); s_lay.addWidget(self.chk_power)
        
        s_lay.addSpacing(15)
        s_lay.addWidget(QLabel("<b>Overlay</b>"))
        self.btn_heat = QPushButton("Heatmap"); self.btn_heat.setCheckable(True); self.btn_heat.toggled.connect(self.update_view)
        self.btn_heat.setStyleSheet("QPushButton:checked { background-color: #ffcccc; color: red; border: 1px solid red; }")
        s_lay.addWidget(self.btn_heat)
        
        s_lay.addStretch()
        btn_gui = QPushButton("Native GUI"); btn_gui.clicked.connect(self.launch_native_gui); s_lay.addWidget(btn_gui)
        btn_ref = QPushButton("Refresh View"); btn_ref.clicked.connect(self.force_refresh_view); s_lay.addWidget(btn_ref)
        
        h_lay.addWidget(sidebar)
        
        # CENTER PEEKER
        self.peeker = SiliconPeeker()
        h_lay.addWidget(self.peeker)
        
        v_split.addWidget(h_widget)
        
        # 2b. LOWER AREA
        term_widget = QWidget()
        t_lay = QVBoxLayout(term_widget); t_lay.setContentsMargins(0,0,0,0)
        
        self.term_log = QTextEdit(); self.term_log.setReadOnly(True)
        self.term_log.setStyleSheet("background: #101010; color: #00FF00; font-family: Consolas; border: none;")
        self.term_in = QLineEdit(); self.term_in.setPlaceholderText("Enter TCL command...")
        self.term_in.setStyleSheet("background: #202020; color: white; border-top: 1px solid #444; font-family: Consolas; padding: 5px;")
        self.term_in.returnPressed.connect(self.send_command)
        
        t_lay.addWidget(self.term_log); t_lay.addWidget(self.term_in)
        v_split.addWidget(term_widget)
        v_split.setStretchFactor(0, 4)
        v_split.setStretchFactor(1, 1)
        
        self.layout.addWidget(v_split)

        self.proc = None
        self.pending_init = None
        self.cmd_active = False

    def update_view(self):
        self.peeker.show_insts = self.chk_inst.isChecked()
        self.peeker.show_pins = self.chk_pins.isChecked()
        self.peeker.show_nets = self.chk_nets.isChecked()
        self.peeker.show_power = self.chk_power.isChecked()
        self.peeker.show_heatmap = self.btn_heat.isChecked()
        self.peeker.redraw()

    def reset_backend(self):
        if self.proc and self.proc.state() == QProcess.ProcessState.Running:
            self.proc.kill(); self.proc.waitForFinished()
        self.term_log.clear()
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read_stdout)
        if shutil.which("openroad"): self.proc.start("openroad")
        else: self.term_log.append("[ERR] OpenROAD binary not found.")

    def read_stdout(self):
        data = self.proc.readAllStandardOutput().data().decode()
        self.term_log.append(data.strip())
        self.term_log.verticalScrollBar().setValue(self.term_log.verticalScrollBar().maximum())
        if self.pending_init and ("OpenROAD" in data or "openroad>" in data):
            self.send_command_internal(self.pending_init); self.pending_init = None
        if self.cmd_active and "openroad>" in data:
            self.cmd_active = False
            self.force_refresh_view()

    def force_refresh_view(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        def_path = os.path.join(proj_root, "results", "temp.def")
        if os.path.exists(def_path): self.peeker.load_def_file(def_path)

    def open_pdk_selector(self):
        dlg = PDKSelector(self.pdk_mgr, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.active_pdk = dlg.selected_config
            self.term_log.append(f"[SYS] Target PDK: {self.active_pdk['name']}")
            return True
        return False

    def launch_native_gui(self):
        if not self.active_pdk: return
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        def_path = os.path.join(proj_root, "results", "temp.def")
        if not os.path.exists(def_path): return
        view_tcl = os.path.join(proj_root, "view.tcl")
        with open(view_tcl, 'w') as f:
            f.write(f'read_lef "{self.active_pdk["tlef"]}"\nread_lef "{self.active_pdk["lef"]}"\nread_def "{def_path}"\n')
        subprocess.Popen(["openroad", "-gui", view_tcl], cwd=proj_root)

    def run_flow_step(self, step_name):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        results_dir = os.path.join(proj_root, "results")
        os.makedirs(results_dir, exist_ok=True)
        def_abs_path = os.path.join(results_dir, "temp.def").replace("\\", "/")
        write_cmd = f"write_def \"{def_abs_path}\""

        if "Init" in step_name:
            if not self.active_pdk:
                if not self.open_pdk_selector(): return 
            tcl_path = os.path.join(proj_root, "init_pdk.tcl")
            ctx = self.ide.get_context()[0] or "top"
            netlist_path = os.path.join(proj_root, "netlist", f"{ctx}_netlist.v")
            if not os.path.exists(netlist_path): netlist_path = self.ide.current_file or "design.v"
            
            tcl_content = f"""
            read_lef "{self.active_pdk['tlef']}"
            read_lef "{self.active_pdk['lef']}"
            read_liberty "{self.active_pdk['lib']}"
            read_verilog "{netlist_path}"
            link_design {ctx}
            """
            try:
                with open(tcl_path, 'w') as f: f.write(tcl_content)
                self.pending_init = f"source {tcl_path}"
                self.term_log.append("[SYS] Rebooting OpenROAD...")
                self.reset_backend() 
            except Exception as e: self.term_log.append(f"[ERR] File Error: {e}")
            return

        cmd = ""
        # === PDN COMMAND (Sky130 Fixed) ===
        if "PDN" in step_name:
            # 1. Match VPWR/VGND (Standard Cells) OR VDD/VSS (Macros)
            # 2. Add Met1 Rails (Followpins)
            # 3. Connect Met1 -> Met4
            cmd_raw = f"""
            add_global_connection -net {{VDD}} -pin_pattern {{^VPWR$|^VDD$}} -power
            add_global_connection -net {{VSS}} -pin_pattern {{^VGND$|^VSS$}} -ground
            set_voltage_domain -name {{Core}} -power {{VDD}} -ground {{VSS}}
            define_pdn_grid -name {{grid}} -voltage_domains {{Core}}
            add_pdn_stripe -grid {{grid}} -layer {{met1}} -width {{0.48}} -followpins
            add_pdn_stripe -grid {{grid}} -layer {{met4}} -width {{1.6}} -pitch {{27.2}} -offset {{13.6}} -extend_to_core_ring
            add_pdn_connect -grid {{grid}} -layers {{met1 met4}}
            pdngen
            {write_cmd}
            """
            # Flatten with SEMICOLONS
            cmd = " ; ".join([line.strip() for line in cmd_raw.split('\n') if line.strip()])

        elif "Floorplan" in step_name: cmd = f"initialize_floorplan -die_area \"0 0 400 400\" -core_area \"10 10 390 390\" -site unithd; {write_cmd}"
        elif "Tapcells" in step_name: cmd = f"tapcell -distance 14 -tapcell_master sky130_fd_sc_hd__tapvpwrvgnd_1; make_tracks; {write_cmd}"
        elif "Pins" in step_name: cmd = f"place_pins -hor_layers met3 -ver_layers met4; {write_cmd}"
        elif "Place" in step_name: cmd = f"global_placement -density 0.6; {write_cmd}"
        elif "CTS" in step_name: cmd = f"clock_tree_synthesis -root_buf sky130_fd_sc_hd__clkbuf_4 -buf_list sky130_fd_sc_hd__clkbuf_4; {write_cmd}"
        elif "Route" in step_name: cmd = f"detailed_route -output_drc reports/drc.rpt; {write_cmd}"
        elif "GDS" in step_name: cmd = f"write_gds results/design.gds"

        text, ok = QInputDialog.getText(self, f"Run {step_name}", "Confirm TCL Command:", text=cmd)
        if ok and text:
            self.send_command_internal(text)

    def send_command(self):
        cmd = self.term_in.text(); self.term_in.clear()
        self.send_command_internal(cmd)

    def send_command_internal(self, cmd):
        self.term_log.append(f"> {cmd}")
        if self.proc.state() == QProcess.ProcessState.Running:
            self.cmd_active = True
            self.proc.write(f"{cmd}\n".encode())
        else:
            self.term_log.append(f"[MOCK] {cmd}")
        self.term_log.verticalScrollBar().setValue(self.term_log.verticalScrollBar().maximum())

# ================= 3. MAIN APP CONTROLLER =================

class SilisIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silis — Silicon Scaffold v2.1")
        self.resize(1400, 900)
        self.cwd = os.getcwd(); self.current_file = None; self.pdk_path = ""
        self.schem_engine = "Auto"; self.term_mode = "SHELL"; self.queue = queue.Queue()
        
        # === UX: Keybind State ===
        self.key_map = {
            "focus_explorer": "v",
            "focus_editor": "c",
            "focus_terminal": "x",
            "term_toggle": "s"
        }
        self.sk_active = False
        self.schem_running = False 
        self.sk_timer = QTimer(); self.sk_timer.setSingleShot(True); self.sk_timer.timeout.connect(self.reset_sk)
        
        self.pdk_mgr = PDKManager(); self.active_pdk = None

        # === UI LAYOUT ===
        self.stack = QStackedWidget(); self.setCentralWidget(self.stack)
        
        # World 1: Frontend Tabs
        self.frontend_tabs = QTabWidget(); self.frontend_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_compile = CompileTab(self)
        self.tab_waves = SignalPeeker(self)
        self.tab_schem = SchematicTab(self)
        self.tab_synth = SynthesisTab(self) # NEW UNIFIED DASHBOARD
        
        self.frontend_tabs.addTab(self.tab_compile, "1. COMPILE")
        self.frontend_tabs.addTab(self.tab_waves, "2. WAVEFORM")
        self.frontend_tabs.addTab(self.tab_schem, "3. SCHEMATIC")
        self.frontend_tabs.addTab(self.tab_synth, "4. SYNTHESIS")
        self.stack.addWidget(self.frontend_tabs)
        
        # World 2: Backend Layout
        self.backend_widget = BackendWidget(self)
        self.stack.addWidget(self.backend_widget)
        
        self.setup_toolbar()
        
        # Global Input Filter
        QApplication.instance().installEventFilter(self)
        
        # Background Timer
        self.queue_timer = QTimer(); self.queue_timer.timeout.connect(self.process_queue); self.queue_timer.start(50)
        
        self.log_system(f"Silis Initialized. CWD: {self.cwd}")
        self.check_dependencies()

    # === UX: SMART SHORTCUTS ===
    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            
            # --- GLOBAL F-KEYS (Smart Toggle) ---
            if self.stack.currentIndex() == 0:
                if key == Qt.Key.Key_F1:
                    if self.frontend_tabs.currentIndex() != 0: self.frontend_tabs.setCurrentIndex(0)
                    else: self.run_simulation()
                    return True
                
                elif key == Qt.Key.Key_F2:
                    if self.frontend_tabs.currentIndex() != 1: 
                        self.frontend_tabs.setCurrentIndex(1)
                        self.tab_waves.auto_load() 
                    else: 
                        self.tab_waves.manual_load() 
                    return True
                
                elif key == Qt.Key.Key_F3:
                    if self.frontend_tabs.currentIndex() != 2: self.frontend_tabs.setCurrentIndex(2)
                    else: self.generate_schematic()
                    return True
                
                elif key == Qt.Key.Key_F4:
                    if self.frontend_tabs.currentIndex() != 3: self.frontend_tabs.setCurrentIndex(3)
                    else:
                        if not self.active_pdk: self.open_pdk_selector()
                        else: self.run_synthesis_flow()
                    return True

            # --- SUPER KEY LOGIC (` + Key) ---
            if key == Qt.Key.Key_QuoteLeft: # Backtick `
                self.sk_active = True
                self.statusBar().showMessage("SUPER KEY ACTIVE")
                self.sk_timer.start(1000)
                return True 
            
            if self.sk_active:
                txt = event.text().lower()
                
                # World Switching
                if txt == '1': self.switch_world(0)
                elif txt == '2': self.switch_world(1)
                
                # Widget Focus (Customizable)
                elif txt == self.key_map["focus_explorer"]: 
                    self.switch_world(0); self.frontend_tabs.setCurrentIndex(0)
                    self.tab_compile.explorer.setFocus()
                elif txt == self.key_map["focus_editor"]: 
                    self.switch_world(0); self.frontend_tabs.setCurrentIndex(0)
                    self.tab_compile.editor.setFocus()
                elif txt == self.key_map["focus_terminal"]: 
                    self.switch_world(0); self.frontend_tabs.setCurrentIndex(0)
                    self.tab_compile.term_input.setFocus()
                elif txt == self.key_map["term_toggle"]: 
                    self.toggle_term_mode()
                
                self.reset_sk(); return True
                
        return super().eventFilter(source, event)

    def reset_sk(self): self.sk_active = False; self.statusBar().clearMessage()

    def switch_world(self, index):
        self.stack.setCurrentIndex(index)
        self.btn_front.setChecked(index == 0)
        self.btn_back.setChecked(index == 1)

    # === CORE LOGIC ===

    def generate_schematic(self):
        if self.schem_running:
            self.log_system("Schematic generation in progress...", "WARN")
            return

        self.log_system("Generating Schematic...")
        _, base = self.get_context()
        if not base: 
            self.log_system("No Top Module found", "ERR"); return
            
        root = self.prep_workspace(base)
        src = glob.glob(os.path.join(root, "source", "*.v"))
        
        # Lock UI
        self.schem_running = True
        self.tab_schem.btn_gen.setEnabled(False)
        self.tab_schem.btn_gen.setText("Crunching...")
        
        self.worker = SchematicWorker(root, base, self.schem_engine, src)
        self.worker.log.connect(self.log_system)
        self.worker.finished.connect(self.on_schematic_done) 
        self.worker.start()

    def on_schematic_done(self, path):
        # Unlock UI
        self.schem_running = False
        self.tab_schem.btn_gen.setEnabled(True)
        self.tab_schem.btn_gen.setText("Generate Logic View")
        self.tab_schem.view.load_schematic(path)

    def run_synthesis_flow(self):
        if not self.active_pdk: 
            QMessageBox.warning(self, "Err", "Select PDK!"); return
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        self.pdk_path = self.active_pdk['lib']
        self.run_synthesis_thread(root, base)

    def run_synthesis_thread(self, root, base):
        # Clear the unified log before starting
        self.tab_synth.log_main.clear()
        self.tab_synth.card_status.setText("RUNNING...")
        self.tab_synth.card_status.setStyleSheet("background:#eaeef2; color:#57606a; font-weight:bold; padding:15px; border-radius:6px; border: 1px solid #d0d7de;")

        v_net = f"netlist/{base}_netlist.v"
        src_v = glob.glob(os.path.join(root, "source", "*.v"))
        src_v = [s for s in src_v if "tb_" not in s]
        read_cmd = f"read_verilog {' '.join(src_v)}" if src_v else ""
        
        ys = f"read_liberty -lib {self.pdk_path}\n{read_cmd}\nsynth -top {base}\ndfflibmap -liberty {self.pdk_path}\nabc -liberty {self.pdk_path}\ntee -o reports/area.rpt stat -liberty {self.pdk_path} -json\nwrite_verilog -noattr {v_net}"
        with open(os.path.join(root, "synth.ys"), 'w') as f: f.write(ys)
        
        tcl = f"read_liberty {self.pdk_path}\nread_verilog {v_net}\nlink_design {base}\nread_sdc netlist/{base}.sdc\nreport_checks\nreport_power\nexit"
        with open(os.path.join(root, "sta.tcl"), 'w') as f: f.write(tcl)

        def task():
            self.queue.put(("[SYS]", "Starting Synthesis Flow..."))
            
            # --- STEP 1: YOSYS ---
            try:
                p1 = subprocess.Popen(f"yosys synth.ys", shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(p1.stdout.readline, ''):
                    line = line.strip()
                    if line:
                        # Stream to Tab 4 (Use new tags)
                        self.queue.put(("[YOSYS]", line)) 
                p1.wait()
                if p1.returncode != 0: raise Exception("Yosys Failed")
            except Exception as e:
                self.queue.put(("[SYS]", f"[ERR] Yosys Crash: {e}")); return

            # --- STEP 2: OPENSTA ---
            try:
                p2 = subprocess.Popen(f"sta sta.tcl", shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(p2.stdout.readline, ''):
                    line = line.strip()
                    if line:
                        self.queue.put(("[STA]", line)) 
                p2.wait()
            except Exception as e:
                self.queue.put(("[SYS]", f"[ERR] STA Crash: {e}")); return

            self.queue.put(("[SYS]", "Synthesis & Timing Complete."))
            self.queue.put(("UPDATE_DASHBOARD", None)) # Trigger UI update
        
        threading.Thread(target=task, daemon=True).start()

    def run_simulation(self):
        if self.current_file: self.save_file()
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        src_v = glob.glob(os.path.join(root, "source", "*.v")) + glob.glob(os.path.join(root, "source", "*.sv"))
        if not src_v: self.log_system("No source files!", "ERR"); return
        cmd = ["iverilog", "-g2012", "-o", f"{base}.out"] + src_v
        def task():
            try:
                self.queue.put("[SYS] Compiling...")
                subprocess.run(cmd, cwd=root, capture_output=True)
                self.queue.put("[SYS] Simulating...")
                proc = subprocess.Popen(["vvp", f"{base}.out"], cwd=root, stdout=subprocess.PIPE, text=True, bufsize=1)
                for line in iter(proc.stdout.readline, ''): self.queue.put(line.strip())
            except Exception as e: self.queue.put(f"[ERR] {e}")
        threading.Thread(target=task, daemon=True).start()

    # --- HELPERS (Copied & Cleaned) ---
    def setup_toolbar(self):
        tb = QToolBar(); self.addToolBar(tb); tb.setMovable(False)
        act_new = QAction("New", self); act_new.setShortcut("Ctrl+N"); act_new.triggered.connect(self.new_file); tb.addAction(act_new)
        act_save = QAction("Save", self); act_save.setShortcut("Ctrl+S"); act_save.triggered.connect(self.save_file); tb.addAction(act_save)
        tb.addSeparator()
        self.btn_front = QPushButton("Frontend"); self.btn_front.setCheckable(True); self.btn_front.setChecked(True)
        self.btn_front.clicked.connect(lambda: self.switch_world(0))
        self.btn_back = QPushButton("Backend"); self.btn_back.setCheckable(True)
        self.btn_back.clicked.connect(lambda: self.switch_world(1))
        tb.addWidget(self.btn_front); tb.addWidget(self.btn_back)
        tb.addSeparator()
        self.lbl_proj = QLabel(" Untitled "); tb.addWidget(self.lbl_proj)
        tb.addSeparator()
        act_set = QAction("⚙ Settings", self); act_set.triggered.connect(self.open_settings); tb.addAction(act_set)

    def open_settings(self):
        d = QDialog(self); d.setWindowTitle("Silis Settings"); d.resize(400, 300); l = QFormLayout(d)
        e_pdk = QLineEdit(self.pdk_path)
        btn_browse = QPushButton("Browse .lib"); btn_browse.clicked.connect(lambda: e_pdk.setText(QFileDialog.getOpenFileName(d, "Select Lib", "", "*.lib")[0]))
        l.addRow("PDK Lib:", e_pdk); l.addRow("", btn_browse)
        l.addRow(QLabel("<b>Keybinds (after ` ):</b>"))
        bind_edits = {}
        for name, key in self.key_map.items():
            e = QLineEdit(key); e.setMaxLength(1); bind_edits[name] = e
            l.addRow(name.replace("_", " ").title() + ":", e)
        def save():
            self.pdk_path = e_pdk.text()
            for name, e in bind_edits.items(): self.key_map[name] = e.text().lower()
            d.accept()
        btn_save = QPushButton("Save"); btn_save.clicked.connect(save); l.addRow(btn_save); d.exec()

    def log_system(self, msg, tag="SYS"):
        # ROUTE SYSTEM MESSAGES TO TAB 1 (Compile Tab)
        color = "#00FFFF" if "ERR" not in tag else "#FF5555"
        self.tab_compile.term_log.append(f'<span style="color:{color};">[{tag}] {msg}</span>')
        self.tab_compile.term_log.verticalScrollBar().setValue(self.tab_compile.term_log.verticalScrollBar().maximum())

    def change_directory(self, path):
        if os.path.exists(path):
            os.chdir(path); self.cwd = os.getcwd(); self.tab_compile.explorer.set_cwd(self.cwd)
            self.log_system(f"CD -> {self.cwd}", "SYS")

    def open_file_in_editor(self, path):
        if os.path.exists(path):
            with open(path) as f: self.tab_compile.editor.setPlainText(f.read())
            self.current_file = path; self.lbl_proj.setText(os.path.basename(path))

    def handle_terminal_input(self):
        cmd = self.tab_compile.term_input.text().strip(); self.tab_compile.term_input.clear()
        if not cmd: return
        self.log_system(f"$ {cmd}", "INPUT")
        if cmd.startswith("cd "): 
            target = cmd[3:].strip()
            if target == "..": target = os.path.dirname(self.cwd)
            elif target == "~": target = os.path.expanduser("~")
            else: target = os.path.join(self.cwd, target)
            self.change_directory(target)
            return
        
        def run():
            try:
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=self.cwd, bufsize=1)
                for line in iter(proc.stdout.readline, ''): self.queue.put(line.strip())
            except Exception as e: self.queue.put(f"[ERR] {e}")
        threading.Thread(target=run, daemon=True).start()

    def toggle_term_mode(self): 
        self.term_mode = "SIM" if self.term_mode == "SHELL" else "SHELL"
        self.tab_compile.mode_btn.setText(f"[{self.term_mode}]")

    def open_pdk_selector(self):
        dlg = PDKSelector(self.pdk_mgr, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.active_pdk = dlg.selected_config
            self.tab_synth.lbl_pdk.setText(f"<b>Active PDK:</b> {self.active_pdk['name']}")
            self.log_system(f"PDK Selected: {self.active_pdk['name']}")
            return True
        return False

    def new_file(self): 
        self.current_file = None; self.tab_compile.editor.clear(); self.lbl_proj.setText("Untitled")

    def save_file(self):
        if not self.current_file:
            f, _ = QFileDialog.getSaveFileName(self, "Save", self.cwd)
            if f: self.current_file = f
        if self.current_file:
            with open(self.current_file, 'w') as f: f.write(self.tab_compile.editor.toPlainText())
            self.log_system(f"Saved {os.path.basename(self.current_file)}")
            self.lbl_proj.setText(os.path.basename(self.current_file))

    def get_context(self):
        content = self.tab_compile.editor.toPlainText()
        m = re.search(r'module\s+(\w+)', content)
        if not m: return None, None
        return m.group(1), m.group(1).replace("tb_", "").replace("_tb", "")

    def get_proj_root(self, base):
        pname = f"{base}_project"; cwd = os.path.abspath(self.cwd)
        if os.path.basename(cwd) == pname: return cwd
        if os.path.basename(cwd) in ["source", "netlist"]: return os.path.dirname(cwd)
        return os.path.join(cwd, pname)

    def prep_workspace(self, base):
        root = self.get_proj_root(base)
        src_dir = os.path.join(root, "source")
        for d in ["source", "netlist", "reports", "results"]: os.makedirs(os.path.join(root, d), exist_ok=True)
        files = [f"{base}.v", f"tb_{base}.v", f"{base}_tb.v", f"test_{base}.v", f"{base}.sv"]
        search_dirs = list(set([os.path.abspath(self.cwd), root]))
        for fname in files:
            if os.path.exists(os.path.join(src_dir, fname)): continue
            found = None
            for s_dir in search_dirs:
                possible = os.path.join(s_dir, fname)
                if os.path.exists(possible): found = possible; break
            if found:
                try: 
                    shutil.move(found, os.path.join(src_dir, fname))
                    self.log_system(f"Moved {fname} -> source/")
                except: pass
        return root

    def open_waves(self):
        self.frontend_tabs.setCurrentIndex(1)
        self.tab_waves.auto_load()

    def harvest_logs(self, root):
        p = os.path.join(root, "reports/synthesis.log")
        if os.path.exists(p):
             with open(p) as f: self.tab_synth.log_main.setPlainText(f.read())
    
    # --- FIXED QUEUE PROCESSOR ---
    def process_queue(self):
        while not self.queue.empty():
            item = self.queue.get()
            
            # Unpack Tuple or String
            if isinstance(item, tuple):
                tag, content = item
            else:
                tag, content = "SYS", str(item)

            # ROUTING LOGIC
            if tag == "UPDATE_DASHBOARD":
                self.tab_synth.update_dashboard()
                
            elif tag in ["[YOSYS]", "[STA]", "SYNTH_LOG", "STA_LOG"]:
                # Route build logs to the Synthesis Tab's Unified Log
                self.tab_synth.log_main.append(content)
                sb = self.tab_synth.log_main.verticalScrollBar()
                sb.setValue(sb.maximum())
                
            elif tag == "[SYS]" or tag == "SYS":
                # Route system messages to Tab 1 (Compile) via log_system
                self.log_system(content)
                
            else:
                # Fallback for plain strings
                self.log_system(str(item))

    def load_violation_log(self): 
        self.frontend_tabs.setCurrentIndex(3)
        self.harvest_logs(self.get_proj_root(self.get_context()[1] or "design"))
        
    def check_dependencies(self):
        if not shutil.which("sta"): self.log_system("OpenSTA not found!", "ERR")
    
    def update_ui_labels(self): pass

# ================= WORKER CLASS =================
class SchematicWorker(QThread):
    finished = pyqtSignal(str); log = pyqtSignal(str, str)
    def __init__(self, root, base, engine, src_files):
        super().__init__(); self.root=root; self.base=base; self.engine=engine; self.src_files=src_files
    def run(self):
        read_cmd = "".join([f"read_verilog {s}; " for s in self.src_files])
        cmd_dot = f"yosys -p '{read_cmd} hierarchy -check -top {self.base}; proc; opt; show -format dot -prefix {self.base}'"
        subprocess.run(cmd_dot, shell=True, cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        dot_path = os.path.join(self.root, f"{self.base}.dot")
        if os.path.exists(dot_path):
            subprocess.run(f"dot -Tsvg {dot_path} -o {self.base}.svg", shell=True, cwd=self.root)
            self.finished.emit(os.path.join(self.root, f"{self.base}.svg"))
        else: self.log.emit("Schematic Gen Failed", "ERROR")

if __name__ == "__main__":
    QImageReader.setAllocationLimit(0)
    app = QApplication(sys.argv)
    w = SilisIDE()
    w.show()
    sys.exit(app.exec())