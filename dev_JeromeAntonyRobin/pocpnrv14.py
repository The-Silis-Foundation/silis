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
                             QGraphicsPolygonItem, QGraphicsPathItem, QScrollArea)
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
        current_route_width = 0
        current_route_points = []
        parsing_route = False

        for line in lines:
            try:
                line = line.strip()
                if not line or line.startswith('#'): continue

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

                elif line.startswith("COMPONENTS"): current_section = "COMPONENTS"
                elif line.startswith("PINS"): current_section = "PINS"
                elif line.startswith("SPECIALNETS"): current_section = "SPECIALNETS"
                elif line.startswith("NETS") and "SPECIAL" not in line: current_section = "NETS"
                elif line.startswith("END"): 
                    current_section = None
                    current_comp_name = None
                    parsing_route = False
                    if len(current_route_points) >= 2:
                        if current_section == "SPECIALNETS":
                            self.power_routes.append((current_route_width, current_route_points))
                        elif current_section == "NETS":
                            self.signal_routes.append(current_route_points)
                    current_route_points = []

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
                                self.module_map[current_comp_name] = "STD_LOGIC" 
                                self.component_count += 1
                                current_comp_name = None

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
        self.setViewport(QOpenGLWidget())
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QColor("#FFFFFF")) 
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
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
        painter.save()
        painter.resetTransform()
        view_transform = self.transform()
        zoom_level = view_transform.m11() 
        pixels_per_dbu = zoom_level
        pixels_per_micron = pixels_per_dbu * self.def_data.dbu
        if pixels_per_micron <= 0.000001: painter.restore(); return

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
        
        hud_color = QColor("#FF0000") 
        pen = QPen(hud_color, 3) 
        pen.setCosmetic(False) 
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(int(x_start), int(y_pos), int(x_start + bar_width_px), int(y_pos)) 
        painter.drawLine(int(x_start), int(y_pos), int(x_start), int(y_pos - 8)) 
        painter.drawLine(int(x_start + bar_width_px), int(y_pos), int(x_start + bar_width_px), int(y_pos - 8)) 
        
        unit = "µm"
        if display_val < 1: display_val *= 1000; unit = "nm"
        text = f"{int(display_val) if display_val >= 1 else display_val} {unit}"
        
        painter.setPen(hud_color)
        font = QFont("Consolas", 12, QFont.Weight.Bold)
        painter.setFont(font)
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
        except Exception as e: print(f"Peeker Load Error: {e}")

    def redraw(self):
        try:
            current_transform = self.transform()
            self.scene.clear()
            if not self.def_data: return

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
        for i in range(1, 4): self.setColumnHidden(i, True)
        self.setHeaderHidden(True)
        self.setAnimated(False)
        self.setIndentation(15)
        self.setDragEnabled(False)
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
            parent_dir = os.path.dirname(self.fs_model.filePath(self.rootIndex()))
            self.dirChanged.emit(parent_dir)
            event.accept()
        elif key == Qt.Key.Key_Delete:
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
            size_mb = os.path.getsize(path) / (1024 * 1024)
            if size_mb > 5.0:
                text = self.scene.addText(f"Schematic Too Large ({size_mb:.2f} MB)\n\nFile saved to:\n{path}")
                text.setDefaultTextColor(Qt.GlobalColor.red); text.setScale(2); return

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

    def keyPressEvent(self, event):
        key = event.key()
        if key in [Qt.Key.Key_Plus, Qt.Key.Key_Equal]: self.scale(1.2, 1.2)
        elif key == Qt.Key.Key_Minus: self.scale(0.8, 0.8)
        elif key in [Qt.Key.Key_Left, Qt.Key.Key_A]: 
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 20)
        elif key in [Qt.Key.Key_Right, Qt.Key.Key_D]: 
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 20)
        elif key in [Qt.Key.Key_Up, Qt.Key.Key_W]: 
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 20)
        elif key in [Qt.Key.Key_Down, Qt.Key.Key_S]: 
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 20)
        elif key == Qt.Key.Key_0 or key == Qt.Key.Key_F:
             self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else: super().keyPressEvent(event)

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
class VCDParser:
    def __init__(self, path):
        self.signals = {}; self.timescale = 1; self.end_time = 0
        if os.path.exists(path): self.parse(path)
    def parse(self, path):
        id_map = {}; curr_t = 0
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                if line.startswith("$var"):
                    parts = line.split()
                    if len(parts) >= 5:
                        if parts[2] == "1": 
                            id_map[parts[3]] = parts[4]; self.signals[parts[4]] = []
                elif line.startswith("#"):
                    try: curr_t = int(line[1:]); self.end_time = max(self.end_time, curr_t)
                    except: pass
                elif line[0] in "01xz" and len(line) > 1:
                    val = line[0]; sig_id = line[1:]
                    if sig_id in id_map:
                        nm = id_map[sig_id]
                        if not self.signals[nm] or self.signals[nm][-1][1] != val:
                            self.signals[nm].append((curr_t, val))

class WaveformCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.data = None; self.zoom = 10.0; self.offset_x = 0; self.cursor_time = 0
        self.setBackgroundRole(QPalette.ColorRole.Base); self.setAutoFillBackground(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) 

    def set_data(self, parser): self.data = parser; self.update()

    def paintEvent(self, event):
        painter = QPainter(self); painter.fillRect(self.rect(), QColor("#1e1e1e"))
        if not self.data: 
            painter.setPen(QColor("#555")); painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Data (Load VCD)")
            return
        
        y = 40; font = QFont("Consolas", 10); painter.setFont(font)
        
        for name, trans in self.data.signals.items():
            painter.setPen(QColor("#fff")); painter.drawText(10, y + 5, name)
            prev_x = 100 - self.offset_x; prev_val = 'x'
            if trans and trans[0][0] == 0: prev_val = trans[0][1]
            draw_trans = trans + [(self.data.end_time, prev_val)]
            
            for t, val in draw_trans:
                x = 100 + (t * self.zoom) - self.offset_x
                if x < 100: prev_x = x; prev_val = val; continue
                if prev_x > self.width(): break
                c = QColor("#00ff00") if prev_val == '1' else QColor("#008800") if prev_val == '0' else QColor("red")
                h_y = y - 10 if prev_val == '1' else y + 10 if prev_val == '0' else y
                painter.setPen(QPen(c, 2)); painter.drawLine(int(prev_x), int(h_y), int(x), int(h_y))
                painter.setPen(QColor("#555"))
                new_h = y - 10 if val == '1' else y + 10 if val == '0' else y
                if val in '01' and prev_val in '01': painter.drawLine(int(x), int(h_y), int(x), int(new_h))
                prev_x = x; prev_val = val
            y += 40
            
        cx = 100 + (self.cursor_time * self.zoom) - self.offset_x
        if cx > 100:
            painter.setPen(QPen(QColor("yellow"), 1, Qt.PenStyle.DashLine)); painter.drawLine(int(cx), 0, int(cx), self.height())
            painter.drawText(int(cx)+5, 20, f"{self.cursor_time}ns")

    def mouseMoveEvent(self, e):
        if e.pos().x() > 100: self.cursor_time = int((e.pos().x() - 100 + self.offset_x) / self.zoom); self.update()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0: self.zoom *= 1.1
        else: self.zoom *= 0.9
        self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal: self.zoom *= 1.2
        elif key == Qt.Key.Key_Minus: self.zoom *= 0.8
        elif key == Qt.Key.Key_Left: self.offset_x = max(0, self.offset_x - 50)
        elif key == Qt.Key.Key_Right: self.offset_x += 50
        elif key == Qt.Key.Key_F: self.parent().parent().fit_view()
        self.update()

class SignalPeeker(QWidget):
    def __init__(self, ide):
        super().__init__()
        self.ide = ide; lay = QVBoxLayout(self)
        tb = QHBoxLayout()
        btn_load = QPushButton("Load VCD"); btn_load.clicked.connect(self.load)
        btn_fit = QPushButton("Fit (F)"); btn_fit.clicked.connect(self.fit_view)
        tb.addWidget(btn_load); tb.addWidget(btn_fit); tb.addStretch()
        
        self.cvs = WaveformCanvas()
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.cvs)
        self.scroll.setWidgetResizable(True)
        lay.addLayout(tb); lay.addWidget(self.scroll)

    def load(self):
        t, _ = QFileDialog.getOpenFileName(self, "Open VCD", self.ide.cwd, "*.vcd")
        if t: 
            parser = VCDParser(t)
            self.cvs.set_data(parser)
            self.fit_view()
            self.cvs.setFocus() 

    def fit_view(self):
        if self.cvs.data and self.cvs.data.end_time > 0:
            w = self.scroll.width() - 150
            self.cvs.zoom = w / self.cvs.data.end_time
            self.cvs.offset_x = 0
            self.cvs.update()

# === TAB 3: SCHEMATIC ===
class SchematicTab(QWidget):
    def __init__(self, ide):
        super().__init__()
        self.ide = ide; lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        tb = QHBoxLayout()
        btn_gen = QPushButton("Generate"); btn_gen.clicked.connect(self.ide.generate_schematic)
        btn_fit = QPushButton("Fit"); btn_fit.clicked.connect(lambda: self.view.fitInView(self.view.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio))
        tb.addWidget(btn_gen); tb.addWidget(btn_fit); tb.addStretch()
        self.view = SilisSchematic(); lay.addLayout(tb); lay.addWidget(self.view)

# === TAB 4: SYNTHESIS ===
class SynthesisTab(QWidget):
    def __init__(self, ide):
        super().__init__()
        self.ide = ide; lay = QVBoxLayout(self)
        pdk_grp = QGroupBox("Technology Mapping"); pdk_lay = QHBoxLayout(pdk_grp)
        self.lbl_pdk = QLabel("Active PDK: None"); btn = QPushButton("Select PDK"); btn.clicked.connect(self.ide.open_pdk_selector)
        pdk_lay.addWidget(self.lbl_pdk); pdk_lay.addStretch(); pdk_lay.addWidget(btn)
        lay.addWidget(pdk_grp)
        btn_run = QPushButton("🚀 Run Synthesis"); btn_run.clicked.connect(self.ide.run_synthesis_flow)
        lay.addWidget(btn_run)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.log_synth = QTextEdit(); self.log_synth.setReadOnly(True); self.log_synth.setStyleSheet("background:#111; color:#0f0;")
        self.log_stats = QTextEdit(); self.log_stats.setReadOnly(True); self.log_stats.setStyleSheet("background:#222; color:#ff0;")
        split.addWidget(self.log_synth); split.addWidget(self.log_stats)
        lay.addWidget(split)

# ================= 2. BACKEND COMPONENT =================

class BackendWidget(QWidget):
    def __init__(self, parent_ide):
        super().__init__(parent_ide)
        self.ide = parent_ide; layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        ribbon = QFrame(); ribbon.setStyleSheet("background: #f0f0f0; border-bottom: 1px solid #ccc;"); ribbon.setFixedHeight(45)
        r_lay = QHBoxLayout(ribbon)
        self.steps = ["Init", "Floorplan", "Tapcells", "PDN", "IO Pins", "Place", "CTS", "Route", "GDS"]
        for step in self.steps:
            btn = QPushButton(step)
            btn.clicked.connect(lambda _, s=step: self.run_step(s)) 
            r_lay.addWidget(btn)
        r_lay.addStretch()
        btn_rst = QPushButton("🔄 Reset"); btn_rst.clicked.connect(self.reset_backend); r_lay.addWidget(btn_rst)
        layout.addWidget(ribbon)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.peeker = SiliconPeeker(); splitter.addWidget(self.peeker)
        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setStyleSheet("background: #000; color: #0f0; font-family: Consolas;"); self.log.setFixedHeight(150)
        splitter.addWidget(self.log)
        layout.addWidget(splitter)
        self.proc = None; self.pending_init = None

    def reset_backend(self):
        if self.proc and self.proc.state() == QProcess.ProcessState.Running:
            self.proc.kill(); self.proc.waitForFinished()
        self.log.clear()
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read_stdout)
        if shutil.which("openroad"): self.proc.start("openroad")
        else: self.log.append("[ERR] OpenROAD binary not found.")

    def read_stdout(self):
        data = self.proc.readAllStandardOutput().data().decode()
        self.log.append(data.strip())
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        if self.pending_init and ("OpenROAD" in data or "openroad>" in data):
            self.send_command_internal(self.pending_init); self.pending_init = None
        if "openroad>" in data: 
             pass

    def send_command_internal(self, cmd):
        self.log.append(f"> {cmd}")
        if self.proc and self.proc.state() == QProcess.ProcessState.Running: 
            self.proc.write(f"{cmd}\n".encode())

    def run_step(self, step_name):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        results_dir = os.path.join(proj_root, "results")
        os.makedirs(results_dir, exist_ok=True)
        def_abs_path = os.path.join(results_dir, "temp.def").replace("\\", "/")
        write_cmd = f"write_def \"{def_abs_path}\""
        
        cmd = ""
        if step_name == "Init":
             self.log.append("[INFO] Init requires logic from IDE context, skipping in prototype.")
             return
        elif step_name == "Floorplan": cmd = f"initialize_floorplan -die_area \"0 0 400 400\" -core_area \"10 10 390 390\" -site unithd; {write_cmd}"
        
        if cmd: self.send_command_internal(cmd)

# ================= 3. MAIN APP CONTROLLER =================

class SilisIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silis — Silicon Scaffold v2.0")
        self.resize(1400, 900)
        self.cwd = os.getcwd(); self.current_file = None; self.pdk_path = ""
        self.schem_engine = "Auto"; self.term_mode = "SHELL"; self.queue = queue.Queue()
        
        self.key_map = {
            "focus_explorer": "v",
            "focus_editor": "c",
            "focus_terminal": "x",
            "term_toggle": "s"
        }
        
        self.sk_active = False
        self.sk_timer = QTimer(); self.sk_timer.setSingleShot(True); self.sk_timer.timeout.connect(self.reset_sk)
        
        self.pdk_mgr = PDKManager(); self.active_pdk = None

        self.stack = QStackedWidget(); self.setCentralWidget(self.stack)
        
        self.frontend_tabs = QTabWidget(); self.frontend_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_compile = CompileTab(self)
        self.tab_waves = SignalPeeker(self)
        self.tab_schem = SchematicTab(self)
        self.tab_synth = SynthesisTab(self)
        
        self.frontend_tabs.addTab(self.tab_compile, "1. COMPILE")
        self.frontend_tabs.addTab(self.tab_waves, "2. WAVEFORM")
        self.frontend_tabs.addTab(self.tab_schem, "3. SCHEMATIC")
        self.frontend_tabs.addTab(self.tab_synth, "4. SYNTHESIS")
        self.stack.addWidget(self.frontend_tabs)
        
        self.backend_widget = BackendWidget(self)
        self.stack.addWidget(self.backend_widget)
        
        self.setup_toolbar()
        
        QApplication.instance().installEventFilter(self)
        
        self.queue_timer = QTimer(); self.queue_timer.timeout.connect(self.process_queue); self.queue_timer.start(50)
        self.log_system(f"Silis Initialized. CWD: {self.cwd}")
        self.check_dependencies()

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
        act_settings = QAction("⚙ Settings", self); act_settings.triggered.connect(self.open_settings); tb.addAction(act_settings)


    def switch_world(self, index):
        self.stack.setCurrentIndex(index)
        self.btn_front.setChecked(index == 0); self.btn_back.setChecked(index == 1)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            
            if self.stack.currentIndex() == 0:
                if key == Qt.Key.Key_F1: self.frontend_tabs.setCurrentIndex(0); self.run_simulation(); return True
                elif key == Qt.Key.Key_F2: self.frontend_tabs.setCurrentIndex(1); self.open_waves(); return True
                elif key == Qt.Key.Key_F3: self.frontend_tabs.setCurrentIndex(2); self.generate_schematic(); return True
                elif key == Qt.Key.Key_F4: self.frontend_tabs.setCurrentIndex(3); self.run_synthesis_flow(); return True

            if key == Qt.Key.Key_QuoteLeft:
                self.sk_active = True; self.statusBar().showMessage("SUPER KEY ACTIVE"); self.sk_timer.start(1000); return True
            
            if self.sk_active:
                txt = event.text().lower()
                if txt == '1': self.switch_world(0)
                elif txt == '2': self.switch_world(1)
                elif txt == self.key_map["focus_explorer"]: self.switch_world(0); self.frontend_tabs.setCurrentIndex(0); self.tab_compile.explorer.setFocus()
                elif txt == self.key_map["focus_editor"]: self.switch_world(0); self.frontend_tabs.setCurrentIndex(0); self.tab_compile.editor.setFocus()
                elif txt == self.key_map["focus_terminal"]: self.switch_world(0); self.frontend_tabs.setCurrentIndex(0); self.tab_compile.term_input.setFocus()
                elif txt == self.key_map["term_toggle"]: self.toggle_term_mode()
                
                self.reset_sk(); return True
        return super().eventFilter(source, event)

    def reset_sk(self): self.sk_active = False; self.statusBar().clearMessage()

    def open_settings(self):
        d = QDialog(self); d.setWindowTitle("Silis Settings"); d.resize(400, 300)
        l = QFormLayout(d)
        e_pdk = QLineEdit(self.pdk_path)
        btn_browse = QPushButton("Browse .lib"); btn_browse.clicked.connect(lambda: e_pdk.setText(QFileDialog.getOpenFileName(d, "Select Liberty", "", "*.lib")[0]))
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
        btn_save = QPushButton("Save"); btn_save.clicked.connect(save); l.addRow(btn_save)
        d.exec()

    def log_system(self, msg, tag="SYS"):
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
        pname = f"{base}_project"
        cwd = os.path.abspath(self.cwd)
        if os.path.basename(cwd) == pname: return cwd
        if os.path.basename(cwd) in ["source", "netlist"]: return os.path.dirname(cwd)
        return os.path.join(cwd, pname)

    def prep_workspace(self, base):
        root = self.get_proj_root(base)
        src_dir = os.path.join(root, "source")
        for d in ["source", "netlist", "reports", "results"]: os.makedirs(os.path.join(root, d), exist_ok=True)
        files = [f"{base}.v", f"tb_{base}.v", f"{base}_tb.v", f"test_{base}.v", f"{base}.sv"]
        for fname in files:
            if os.path.exists(fname):
                try: shutil.move(fname, os.path.join(src_dir, fname))
                except: pass
        return root

    def run_simulation(self):
        if self.current_file: self.save_file()
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        src_v = glob.glob(os.path.join(root, "source", "*.v")) + glob.glob(os.path.join(root, "source", "*.sv"))
        if not src_v: self.log_system("No source files!", "ERR"); return
        cmd = ["iverilog", "-g2012", "-o", f"{base}.out"] + src_v
        def task():
            subprocess.run(cmd, cwd=root)
            proc = subprocess.Popen(["vvp", f"{base}.out"], cwd=root, stdout=subprocess.PIPE, text=True, bufsize=1)
            for line in iter(proc.stdout.readline, ''): self.queue.put(line.strip())
        threading.Thread(target=task, daemon=True).start()

    def run_synthesis_flow(self):
        if not self.active_pdk: QMessageBox.warning(self, "Err", "Select PDK!"); return
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        self.pdk_path = self.active_pdk['lib']
        self.run_synthesis_thread(root, base)

    def run_synthesis_thread(self, root, base):
        v_net = f"netlist/{base}_netlist.v"
        src_v = glob.glob(os.path.join(root, "source", "*.v"))
        src_v = [s for s in src_v if "tb_" not in s]
        read_cmd = f"read_verilog {' '.join(src_v)}" if src_v else ""
        
        ys = f"read_liberty -lib {self.pdk_path}\n{read_cmd}\nsynth -top {base}\ndfflibmap -liberty {self.pdk_path}\nabc -liberty {self.pdk_path}\ntee -o reports/area.rpt stat -liberty {self.pdk_path} -json\nwrite_verilog -noattr {v_net}"
        with open(os.path.join(root, "synth.ys"), 'w') as f: f.write(ys)
        
        def task():
            self.queue.put("[SYS] Running Yosys...")
            try:
                p1 = subprocess.Popen(f"yosys synth.ys", shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(p1.stdout.readline, ''): self.queue.put(line.strip())
                p1.wait()
                self.queue.put(("HARVEST", root))
            except Exception as e: self.queue.put(f"[ERR] {e}")
        threading.Thread(target=task, daemon=True).start()

    def generate_schematic(self):
        self.log_system("Generating Schematic...")
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        src = glob.glob(os.path.join(root, "source", "*.v"))
        self.worker = SchematicWorker(root, base, self.schem_engine, src)
        self.worker.log.connect(self.log_system)
        self.worker.finished.connect(self.tab_schem.view.load_schematic)
        self.worker.start()

    def open_waves(self):
        self.frontend_tabs.setCurrentIndex(1); self.tab_waves.load()

    def harvest_logs(self, root):
        p = os.path.join(root, "reports/synthesis.log")
        if os.path.exists(p):
             with open(p) as f: self.tab_synth.log_synth.setPlainText(f.read())
        # Add STA harvest logic here later

    def load_violation_log(self): 
        self.frontend_tabs.setCurrentIndex(3)
        self.harvest_logs(self.get_proj_root(self.get_context()[1] or "design"))
    
    def process_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            if isinstance(msg, tuple): self.harvest_logs(msg[1])
            else: self.log_system(str(msg).strip(), "SYS")
            
    def check_dependencies(self): pass

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