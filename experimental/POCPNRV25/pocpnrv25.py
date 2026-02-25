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
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath, QTransform, QFont, QFontMetrics, QPolygonF
# Corrected Imports for PyQt6:
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPathItem, QGraphicsPolygonItem
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
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
                             QGraphicsPolygonItem, QGraphicsPathItem, QScrollArea, QListWidget, QFrame, QTabWidget, QGridLayout, QListWidgetItem)
from PyQt6.QtCore import (Qt, QTimer, QSize, pyqtSignal, QThread, QDir, 
                          QEvent, QProcess, QRectF, QPointF)
from PyQt6.QtGui import (QAction, QFont, QColor, QSyntaxHighlighter, 
                         QTextCharFormat, QTextFormat, QPixmap, QPainter, QImage, QBrush, QPen,
                         QFileSystemModel, QKeySequence, QShortcut, QImageReader, 
                         QTransform, QPolygonF, QIcon, QPainterPath, QFontMetrics)
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtSvg import QSvgRenderer
import gdstk

from PyQt6.QtGui import QPen, QBrush, QColor, QPolygonF, QPainter # Ensure these are imported

# [NEW CLASS] Smart Polygon with Level of Detail (LOD)
class LODPolygonItem(QGraphicsPolygonItem):
    # 0.5 = Aggressive (Fastest)
    # 0.1 = Standard
    LOD_THRESHOLD = 0.5 

    def __init__(self, polygon, parent=None):
        super().__init__(polygon, parent)
        # 1. Cache the bounding rect (Massive speedup for 100k items)
        self._rect = polygon.boundingRect()
        # 2. Disable selection/collision checks if you don't need them
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self):
        return self._rect

    def shape(self):
        # 3. Cheat: Return a box instead of a complex polygon shape
        # This makes "itemAt" queries 100x faster
        path = QPainterPath()
        path.addRect(self._rect)
        return path

    def paint(self, painter, option, widget):
        # 4. The LOD Check
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod < self.LOD_THRESHOLD:
            return # Skip drawing completely
            
        super().paint(painter, option, widget)
        
class GDSViewerWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Optimization Flags for Speed
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False) 
        self.setOptimizationFlags(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing | 
                                  QGraphicsView.OptimizationFlag.DontSavePainterState)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor("#000000")) 
        
        self.layer_colors = {}
        self.layer_groups = {} 
        self.loaded_file = None

    def get_color(self, layer, datatype):
        key = (layer, datatype)
        if key not in self.layer_colors:
            import hashlib
            hash_bytes = hashlib.md5(f"{layer}-{datatype}".encode()).digest()
            self.layer_colors[key] = QColor(hash_bytes[0], hash_bytes[1], hash_bytes[2], 180)
        return self.layer_colors[key]

    def load_gds(self, gds_path):
        if not os.path.exists(gds_path): return
        
        self.scene.clear()
        self.layer_groups.clear()
        self.loaded_file = gds_path
        
        try:
            library = gdstk.read_gds(gds_path)
            top_cells = library.top_level()
            if not top_cells: return
            self.render_cell(top_cells[0])
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        except Exception as e:
            print(f"GDS Load Error: {e}")

    def render_cell(self, cell):
        flat_cell = cell.flatten()
        layer_buckets = {}
        
        # Bucketing for fast layer toggling
        for polygon in flat_cell.polygons:
            key = (polygon.layer, polygon.datatype)
            if key not in layer_buckets: layer_buckets[key] = []
            
            points = [QPointF(pt[0], -pt[1]) for pt in polygon.points]
            if not points: continue
            
            # Use our custom LOD Item
            item = LODPolygonItem(QPolygonF(points))
            
            col = self.get_color(*key)
            item.setBrush(QBrush(col))
            
            # [FIXED] Correct syntax for NoPen in PyQt6
            item.setPen(QPen(Qt.PenStyle.NoPen))
            
            layer_buckets[key].append(item)
            
        # Group items by layer for the sidebar toggle
        for key, items in layer_buckets.items():
            group = self.scene.createItemGroup(items)
            self.layer_groups[key] = group

    def set_layer_visible(self, layer, datatype, visible):
        key = (layer, datatype)
        if key in self.layer_groups:
            self.layer_groups[key].setVisible(visible)

    def get_layers(self):
        return sorted(list(self.layer_groups.keys()))

    def wheelEvent(self, event):
        zoom_in = 1.25
        old_pos = self.mapToScene(event.position().toPoint())
        if event.angleDelta().y() > 0: self.scale(zoom_in, zoom_in)
        else: self.scale(1/zoom_in, 1/zoom_in)
        new_pos = self.mapToScene(event.position().toPoint())
        self.translate(new_pos.x() - old_pos.x(), new_pos.y() - old_pos.y())

# ================= PDK MANAGEMENT SYSTEM =================

class SSAForge:
    """
    Silis Standard Aliases (SSA) - The Forge
    Decouples the IDE from specific PDK naming conventions.
    """
    # 1. HARDCODED DEFAULTS (Failsafe)
    DEFAULT_PDK = "sky130_fd_sc_hd"
    ALIASES = {
        "sky130_fd_sc_hd": {
            "desc": "SkyWater 130nm High Density",
            "tap_cell": "sky130_fd_sc_hd__tapvpwrvgnd_1",
            "tap_dist": 14,
            "cts_root": "sky130_fd_sc_hd__clkbuf_16",
            "cts_leaf": "sky130_fd_sc_hd__clkbuf_4",
            "fill": "sky130_fd_sc_hd__fill_*",
            "tie_hi": "sky130_fd_sc_hd__conb_1",
            "tie_lo": "sky130_fd_sc_hd__conb_1",
            "min_layer": "met1",
            "max_layer": "met5",
            "driver": "sky130_fd_sc_hd__buf_1"
        }
    }

    @staticmethod
    def load_aliases(json_filename="pdk_aliases.json"):
        """
        Loads aliases from disk. 
        Checks CWD first, then the script's own directory.
        """
        # 1. Check Current Working Directory
        paths_to_check = [os.path.abspath(json_filename)]
        
        # 2. Check Script Directory (Crucial for execution from other folders)
        if hasattr(sys, 'argv') and sys.argv:
            script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            paths_to_check.append(os.path.join(script_dir, json_filename))

        loaded = False
        for path in paths_to_check:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        # Update existing, don't overwrite blindly
                        SSAForge.ALIASES.update(data) 
                        print(f"[SSA] Loaded aliases from: {path}")
                        loaded = True
                        break
                except Exception as e:
                    print(f"[SSA] Error parsing {path}: {e}")
        
        if not loaded:
            print(f"[SSA] No external JSON found. Using built-in defaults.")

    @staticmethod
    def resolve_pdk_key(pdk_name, lib_path=None):
        """Matches a name or file path to a known PDK key."""
        # 1. Clean inputs
        pdk_name = str(pdk_name).lower() if pdk_name else ""
        lib_path = str(lib_path).lower() if lib_path else ""

        # 2. Search Keys
        for key in SSAForge.ALIASES:
            key_lower = key.lower()
            # Strict check first
            if key_lower == pdk_name: return key
            
            # Fuzzy name check
            if key_lower in pdk_name: return key
            
            # File path check (e.g. "sky130_fd_sc_hd__tt.lib")
            if lib_path and key_lower in os.path.basename(lib_path):
                return key

        # 3. Fallback: If "sky130" is anywhere, assume HD
        if "sky130" in pdk_name or "sky130" in lib_path:
            return "sky130_fd_sc_hd"

        return SSAForge.DEFAULT_PDK

    @staticmethod
    def get(pdk_name, key, lib_path=None):
        family = SSAForge.resolve_pdk_key(pdk_name, lib_path)
        val = SSAForge.ALIASES.get(family, {}).get(key, "")
        
        # If specific key missing in found family, try default family
        if not val and family != SSAForge.DEFAULT_PDK:
             val = SSAForge.ALIASES.get(SSAForge.DEFAULT_PDK, {}).get(key, "")
             
        return val

    @staticmethod
    def get_tap_cmd(pdk_name, lib_path=None):
        cell = SSAForge.get(pdk_name, "tap_cell", lib_path)
        dist = SSAForge.get(pdk_name, "tap_dist", lib_path)
        if not cell: return "# [SSA ERROR] No TAP cell defined in aliases"
        return f"tapcell -distance {dist} -tapcell_master {cell}; make_tracks"

    @staticmethod
    def get_cts_cmd(pdk_name, lib_path=None):
        root = SSAForge.get(pdk_name, "cts_root", lib_path)
        leaf = SSAForge.get(pdk_name, "cts_leaf", lib_path)
        if not root: return "clock_tree_synthesis; detailed_placement"
        return f"clock_tree_synthesis -root_buf {root} -buf_list {leaf}; detailed_placement"



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
            except: 
                self.configs = []

    def save_cache(self):
        with open(self.cache_file, 'w') as f: 
            json.dump(self.configs, f, indent=2)
    
    def update_config(self, config_data):
        # Remove existing if name matches (Edit Mode)
        self.configs = [c for c in self.configs if c['name'] != config_data['name']]
        # Insert new at top
        self.configs.insert(0, config_data)
        self.save_cache()
    
    def delete_config(self, name):
        self.configs = [c for c in self.configs if c['name'] != name]
        self.save_cache()
    def add_manual_config(self, name, tlef, lef, lib, gds):
        # Insert at top
        entry = {
            "name": name, 
            "tlef": tlef, 
            "lef": lef, 
            "lib": lib, 
            "gds": gds, # The missing link for GDS generation
            "corner": "Manual"
        }
        # Remove duplicates based on name to avoid clutter
        self.configs = [c for c in self.configs if c['name'] != name]
        self.configs.insert(0, entry)
        self.save_cache()

class ManualPDKDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("PDK Configuration Editor")
        self.resize(800, 500)
        self.layout = QFormLayout(self)
        
        # Name
        self.e_name = QLineEdit(config['name'] if config else "Custom PDK")
        self.layout.addRow("<b>Config Name:</b>", self.e_name)
        
        # 1. Tech LEF
        self.e_tlef = QLineEdit(config.get('tlef', '') if config else '')
        b_tlef = QPushButton("Browse Tech LEF (.tlef)"); b_tlef.clicked.connect(lambda: self.browse(self.e_tlef, "Tech LEF (*.tlef *.lef)"))
        self.layout.addRow(b_tlef, self.e_tlef)
        
        # 2. Macro LEF
        self.e_lef = QLineEdit(config.get('lef', '') if config else '')
        b_lef = QPushButton("Browse Macro LEF (.lef)"); b_lef.clicked.connect(lambda: self.browse(self.e_lef, "Macro LEF (*.lef)"))
        self.layout.addRow(b_lef, self.e_lef)
        
        # 3. Liberty
        self.e_lib = QLineEdit(config.get('lib', '') if config else '')
        b_lib = QPushButton("Browse Timing (.lib)"); b_lib.clicked.connect(lambda: self.browse(self.e_lib, "Liberty (*.lib)"))
        self.layout.addRow(b_lib, self.e_lib)

        # 4. GDS (The Meat)
        self.e_gds = QLineEdit(config.get('gds', '') if config else '')
        b_gds = QPushButton("Browse Std Cell GDS (.gds)"); b_gds.clicked.connect(lambda: self.browse(self.e_gds, "GDSII (*.gds)"))
        self.layout.addRow(b_gds, self.e_gds)

        # 5. Magic Tech File (The Key to GDS Merge)
        self.e_tech = QLineEdit(config.get('tech', '') if config else '')
        b_tech = QPushButton("Browse Magic Tech (.tech)"); b_tech.clicked.connect(lambda: self.browse(self.e_tech, "Magic Tech (*.tech)"))
        self.layout.addRow(b_tech, self.e_tech)
        
        btn_save = QPushButton("Save Configuration"); btn_save.setStyleSheet("background: #00AA00; color: white; font-weight: bold; padding: 12px;")
        btn_save.clicked.connect(self.validate_and_accept)
        self.layout.addRow(btn_save)

    def browse(self, line_edit, filter_str):
        f, _ = QFileDialog.getOpenFileName(self, "Select File", "", filter_str)
        if f: line_edit.setText(f)

    def validate_and_accept(self):
        # Enforce all 5 files for a working Magic flow
        if not all([self.e_tlef.text(), self.e_lef.text(), self.e_lib.text(), self.e_gds.text(), self.e_tech.text()]):
            QMessageBox.warning(self, "Incomplete", "All 5 files (TLEF, LEF, LIB, GDS, TECH) are required for the full flow.")
            return
        self.accept()
    
    def update_config(self, config_data):
        # Remove existing if name matches (Edit Mode)
        self.configs = [c for c in self.configs if c['name'] != config_data['name']]
        # Insert new at top
        self.configs.insert(0, config_data)
        self.save_cache()
    
    def delete_config(self, name):
        self.configs = [c for c in self.configs if c['name'] != name]
        self.save_cache()

    def get_data(self):
        return {
            "name": self.e_name.text(),
            "tlef": self.e_tlef.text(),
            "lef": self.e_lef.text(),
            "lib": self.e_lib.text(),
            "gds": self.e_gds.text(),
            "tech": self.e_tech.text(),
            "corner": "Manual"
        }
class PDKSelector(QDialog):
    def __init__(self, pdk_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDK Management")
        self.resize(1100, 500)
        self.mgr = pdk_manager
        self.selected_config = None
        
        layout = QVBoxLayout(self)
        
        # Search
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search configs...")
        self.search.textChanged.connect(self.populate)
        layout.addWidget(self.search)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Name", "Tech LEF", "Macro LEF", "Lib", "GDS", "Magic Tech"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(self.accept_selection)
        layout.addWidget(self.table)
        
        # --- CRUD BUTTONS ---
        btn_lay = QHBoxLayout()
        
        btn_add = QPushButton("➕ Add New")
        btn_add.setStyleSheet("color: #2da44e; font-weight: bold;")
        btn_add.clicked.connect(self.trigger_add)
        
        btn_edit = QPushButton("✏️ Edit Selected")
        btn_edit.clicked.connect(self.trigger_edit)
        
        btn_del = QPushButton("🗑️ Delete Selected")
        btn_del.setStyleSheet("color: #cf222e;")
        btn_del.clicked.connect(self.trigger_delete)
        
        self.btn_ok = QPushButton("Select (Enter)")
        self.btn_ok.clicked.connect(self.accept_selection)
        self.btn_ok.setDefault(True)
        
        btn_lay.addWidget(btn_add)
        btn_lay.addWidget(btn_edit)
        btn_lay.addWidget(btn_del)
        btn_lay.addStretch()
        btn_lay.addWidget(self.btn_ok)
        layout.addLayout(btn_lay)
        
        self.populate()
        self.table.setFocus()

    def populate(self):
        self.table.setRowCount(0)
        txt = self.search.text().lower()
        for cfg in self.mgr.configs:
            if txt and txt not in cfg['name'].lower(): continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(cfg['name']))
            self.table.setItem(r, 1, QTableWidgetItem(os.path.basename(cfg['tlef'])))
            self.table.setItem(r, 2, QTableWidgetItem(os.path.basename(cfg['lef'])))
            self.table.setItem(r, 3, QTableWidgetItem(os.path.basename(cfg['lib'])))
            self.table.setItem(r, 4, QTableWidgetItem(os.path.basename(cfg.get('gds', '-'))))
            self.table.setItem(r, 5, QTableWidgetItem(os.path.basename(cfg.get('tech', '-'))))
            self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, cfg)
        if self.table.rowCount() > 0: self.table.selectRow(0)

    def trigger_add(self):
        d = ManualPDKDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.mgr.update_config(d.get_data())
            self.populate()

    def trigger_edit(self):
        r = self.table.currentRow()
        if r < 0: return
        cfg = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
        d = ManualPDKDialog(self, config=cfg)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.mgr.update_config(d.get_data())
            self.populate()

    def trigger_delete(self):
        r = self.table.currentRow()
        if r < 0: return
        cfg = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
        res = QMessageBox.question(self, "Delete", f"Delete config '{cfg['name']}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            self.mgr.delete_config(cfg['name'])
            self.populate()

    def accept_selection(self):
        r = self.table.currentRow()
        if r >= 0:
            self.selected_config = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
            self.accept()
        elif self.table.rowCount() > 0:
            self.selected_config = self.table.item(0, 0).data(Qt.ItemDataRole.UserRole)
            self.accept()

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key.Key_Enter, Qt.Key.Key_Return]:
            self.accept_selection()
            event.accept()
        else: super().keyPressEvent(event)


# ================= ROBUST DEF PARSER =================






# ================= 1. ROBUST DEF PARSER (Full) =================
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
        self.signal_routes = [] 
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
        
        # Routing Context
        last_x = None
        last_y = None

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
                elif line.startswith("COMPONENTS"): 
                    current_section = "COMPONENTS"
                    parsing_route = False
                elif line.startswith("PINS"): 
                    current_section = "PINS"
                    parsing_route = False
                elif line.startswith("SPECIALNETS"): 
                    current_section = "SPECIALNETS"
                elif line.startswith("NETS") and "SPECIAL" not in line: 
                    current_section = "NETS"
                elif line.startswith("END"): 
                    current_section = None
                    if len(current_route_points) >= 2:
                        if current_section == "SPECIALNETS": self.power_routes.append((current_route_width, current_route_points))
                        elif current_section == "NETS": self.signal_routes.append(current_route_points)
                    current_route_points = []
                    parsing_route = False

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
                                
                                model_lower = current_comp_model.lower()
                                is_tap = "tap" in model_lower or "fill" in model_lower
                                is_clock = "clk" in model_lower and not current_comp_name.startswith("_")
                                
                                if is_tap: self.comp_types[current_comp_name] = "TAP"
                                elif is_clock: self.comp_types[current_comp_name] = "CLOCK"
                                else: self.comp_types[current_comp_name] = "STD"
                                
                                self.module_map[current_comp_name] = "STD_LOGIC" 
                                self.component_count += 1
                                current_comp_name = None

                # --- PINS ---
                elif current_section == "PINS":
                    parts = line.split()
                    if line.startswith("-") and len(parts) > 2:
                        current_pin_name = parts[1]
                    
                    if current_pin_name and ("PLACED" in line or "FIXED" in line):
                        coord_match = re.search(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                        if coord_match:
                            x = int(coord_match.group(1))
                            y = int(coord_match.group(2))
                            pin_sz = 1 * self.dbu 
                            self.pins.append((QRectF(x, y, pin_sz, pin_sz), current_pin_name))
                            current_pin_name = None 

                # --- ROUTING (FINAL RECT FIX) ---
                elif current_section in ["NETS", "SPECIALNETS"]:
                    
                    # 1. TRIGGER: Start parsing on ROUTED or NEW
                    if "ROUTED" in line or "NEW" in line:
                        parsing_route = True
                        if len(current_route_points) >= 2:
                            if current_section == "SPECIALNETS": self.power_routes.append((current_route_width, current_route_points))
                            else: self.signal_routes.append(current_route_points)
                        
                        current_route_points = []
                        last_x = None 
                        last_y = None 

                        if current_section == "SPECIALNETS":
                            w_match = re.search(r'ROUTED\s+\S+\s+(\d+)', line)
                            if w_match: current_route_width = int(w_match.group(1))

                    # 2. FILTER: Ignore Shape Definitions (RECT, PORT, VIA definitions)
                    if "RECT" in line or "LAYER" in line:
                        continue 

                    if parsing_route:
                        # Stop if end of statement
                        if line.startswith("-") or ";" in line:
                            parsing_route = False
                            if len(current_route_points) >= 2:
                                if current_section == "SPECIALNETS": self.power_routes.append((current_route_width, current_route_points))
                                else: self.signal_routes.append(current_route_points)
                            current_route_points = []
                            last_x = None
                            last_y = None

                        if "(" in line:
                            # 3. STRICT PARSING: Only look inside ( ... )
                            raw_groups = line.split('(')
                            
                            for group in raw_groups[1:]: 
                                if ")" not in group: continue
                                content = group.split(')')[0]
                                
                                tokens = content.split()
                                if len(tokens) >= 2:
                                    val_x_str = tokens[0]
                                    val_y_str = tokens[1]
                                    
                                    x = None
                                    if val_x_str == "*": x = last_x
                                    elif val_x_str.lstrip('-').isdigit(): x = int(val_x_str)
                                    
                                    y = None
                                    if val_y_str == "*": y = last_y
                                    elif val_y_str.lstrip('-').isdigit(): y = int(val_y_str)
                                    
                                    if x is not None and y is not None:
                                        current_route_points.append(QPointF(x, y))
                                        last_x, last_y = x, y

            except Exception as inner_e:
                continue
        
        # EOF Flush
        if len(current_route_points) >= 2:
             if current_section == "SPECIALNETS":
                 self.power_routes.append((current_route_width, current_route_points))
             elif current_section == "NETS":
                 self.signal_routes.append(current_route_points)
        
        print(f"DEBUG: Parsed {self.component_count} comps, {len(self.power_routes)} pwr_segs, {len(self.signal_routes)} sig_nets.")






# ================= 2. SILICON PEEKER (Visualizer Full) =================

class SiliconPeeker(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        # [FIX] REMOVED OpenGL to stop MESA/libEGL errors and Black Screen
        # self.setViewport(QOpenGLWidget()) 
        
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QColor("#FFFFFF")) 
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Optimization
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setOptimizationFlags(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing)
        
        # Flip Y (CAD Coordinates)
        self.scale(1, -1) 
        
        # Initial Default Scene Rect (Will be overridden by set_die_area)
        self.setSceneRect(0, 0, 1000, 1000)
        
        self.def_data = None
        self.first_load = True
        
        self.show_insts = True
        self.show_pins = True
        self.show_nets = True 
        self.show_power = True
        self.show_heatmap = False

    def set_die_area(self, x1, y1, x2, y2):
        """
        Called by BackendWidget to pre-set the view before DEF is loaded.
        Centers the chip in a scene that is 1.5x larger than the chip itself.
        """
        self.scene.clear()
        
        # Chip Dimensions
        width = x2 - x1
        height = y2 - y1
        
        # [USER REQUEST] New Scene Rect Logic
        # Scene Size = 1.5x Chip Size
        scene_w = width * 1.5
        scene_h = height * 1.5
        
        # Set Scene Rect starting at 0,0
        self.setSceneRect(0, 0, scene_w, scene_h)
        
        # Calculate where to put the Chip so it is centered in that Scene
        # Center of Scene: (scene_w/2, scene_h/2)
        # We want Chip Center (x1 + w/2, y1 + h/2) to land there.
        # Since we draw relative to (0,0), we offset the drawing.
        
        offset_x = (scene_w - width) / 2
        offset_y = (scene_h - height) / 2
        
        # Draw the Die Outline (Offset to center)
        rect = QRectF(offset_x, offset_y, width, height)
        item = QGraphicsRectItem(rect)
        item.setPen(QPen(QColor("#000000"), 2))
        item.setBrush(QBrush(QColor("#eeeeee")))
        self.scene.addItem(item)
        
        # Add a text label
        t = self.scene.addText(f"Die Area: {width:.1f} x {height:.1f}")
        # Position text at geometric center
        t.setPos(offset_x + width/2, offset_y + height/2)
        # Flip text back so it's readable
        t.setTransform(QTransform().scale(1, -1))
        
        # Force the Viewport to look at this centered area
        self.centerOn(offset_x + width/2, offset_y + height/2)
        # Fit, but keep it tight enough to see
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def drawForeground(self, painter, rect):
        # [FIX] CRITICAL GUARD CLAUSE
        # Prevents "Painter not active" errors on startup
        if self.viewport().width() <= 0 or self.viewport().height() <= 0:
            return
            
        if not self.def_data: return
        
        # --- HUD RENDERER ---
        try:
            painter.save()
            painter.resetTransform()
            
            view_transform = self.transform()
            # m11 is the X scale factor. Since we flipped Y, m22 is negative.
            zoom_level = view_transform.m11() 
            
            if self.def_data and self.def_data.dbu > 0:
                pixels_per_micron = zoom_level * self.def_data.dbu
            else:
                pixels_per_micron = zoom_level * 1000 # Fallback
            
            if pixels_per_micron > 0.1:
                target_px = 150
                target_microns = target_px / pixels_per_micron
                
                # Snap to nice numbers
                if target_microns >= 100: d_val = 100
                elif target_microns >= 10: d_val = 10
                elif target_microns >= 1: d_val = 1
                else: d_val = 0.1
                
                bar_w = d_val * pixels_per_micron
                vx, vy = self.viewport().width(), self.viewport().height()
                
                # Draw Red Bar
                painter.setPen(QPen(Qt.GlobalColor.red, 2))
                painter.drawLine(int(vx - bar_w - 20), int(vy - 30), int(vx - 20), int(vy - 30))
                painter.drawText(int(vx - bar_w - 20), int(vy - 40), f"{d_val} µm")

            painter.restore()
        except Exception:
            pass # Suppress painting errors during resize

    def wheelEvent(self, event):
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor
        oldPos = self.mapToScene(event.position().toPoint())
        
        if event.angleDelta().y() > 0:
            self.scale(zoomInFactor, zoomInFactor)
        else:
            self.scale(zoomOutFactor, zoomOutFactor)
            
        newPos = self.mapToScene(event.position().toPoint())
        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())
        event.accept()
        self.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.viewport().update()

    def fit_with_slack(self):
        rect = self.scene.itemsBoundingRect()
        if rect.isNull(): return
        margin = max(rect.width(), rect.height()) * 0.1
        self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.AspectRatioMode.KeepAspectRatio)

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
            
            # [USER REQUEST] Recentering Logic for Actual Chip Data
            # If we previously set a big scene, we want to place this chip in the middle of it.
            # However, DEF data comes with absolute coordinates (e.g. 1000, 1000).
            # We respect the DEF coordinates but ensure the SceneRect covers them + padding.
            
            self.setSceneRect(d.adjusted(-d.width()*0.25, -d.height()*0.25, d.width()*0.25, d.height()*0.25))
            
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

                # NETS (Signal)
                if self.show_nets:
                    path = QPainterPath()
                    for points in self.def_data.signal_routes:
                        if not points: continue
                        path.moveTo(points[0])
                        for p in points[1:]: path.lineTo(p)
                    
                    # Dark Grey for better visibility
                    pen = QPen(QColor("#505050"), 0) 
                    item = QGraphicsPathItem(path)
                    item.setPen(pen)
                    item.setZValue(-5) 
                    self.scene.addItem(item)

                # CELLS
                if self.show_insts:
                    for name, rect in self.def_data.comps_map.items():
                        ctype = self.def_data.comp_types.get(name, "STD")
                        item = QGraphicsRectItem(rect)
                        
                        if ctype == "TAP":
                            item.setPen(QPen(Qt.PenStyle.NoPen)) 
                            item.setBrush(QBrush(QColor("#000000"))) 
                            item.setZValue(-4) 
                        elif ctype == "CLOCK":
                            # Red for Clock Cells (Excluding Yosys internals)
                            item.setPen(QPen(QColor("#800000"), 0)) 
                            item.setBrush(QBrush(QColor("#D00000"))) 
                            item.setZValue(15) # Draw on top
                        else:
                            # Standard Blue
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
        
        # High Quality Rendering Attributes
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # Navigation
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # Clean UI
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor("#FFFFFF")) 

    def load_schematic(self, path):
        self.scene.clear()
        if os.path.exists(path) and path.endswith(".svg"):
            # Render SVG
            item = QGraphicsSvgItem(path)
            self.scene.addItem(item)
            # Auto-Fit to screen on load
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        # Smooth Zoom
        factor = 1.15 if event.angleDelta().y() > 0 else 0.85
        self.scale(factor, factor)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_0 or key == Qt.Key.Key_F:
            # 'F' or '0' to Reset View
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            super().keyPressEvent(event)
            
    def contextMenuEvent(self, event):
        # Right Click Menu
        menu = QMenu(self)
        reset_act = QAction("Fit to View", self)
        reset_act.triggered.connect(lambda: self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio))
        menu.addAction(reset_act)
        menu.exec(event.globalPos())
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
        if self.width() <= 0 or self.height() <= 0:
            return
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

class ReportEngine:
    """Parses generated report files for robust metric extraction."""
    
    FOOTER_ART = HeaderFactory.ASCII_ART

    @staticmethod
    def parse_files(report_dir):
        metrics = {
            "area": "Unknown", "cells": "0", "wires": "Unknown", "bits": "Unknown",
            "wns": "0.00", "status": "UNKNOWN", 
            "critical_path_trace": "No path data found in timing.rpt",
            "pwr_seq": ["0", "0", "0", "0", "0%"],
            "pwr_comb": ["0", "0", "0", "0", "0%"],
            "pwr_clk": ["0", "0", "0", "0", "0%"],
            "pwr_mac": ["0", "0", "0", "0", "0%"],
            "pwr_pad": ["0", "0", "0", "0", "0%"],
            "pwr_tot": ["0", "0", "0", "0", "100%"],
            "pwr_pct": ["0%", "0%", "0%"],
            "errors": [], "timing_groups": [], "cell_list": []
        }

        # 1. PARSE YOSYS LOG (For Cell List & Warnings)
        yosys_log = os.path.join(report_dir, "synthesis.log")
        if os.path.exists(yosys_log):
            with open(yosys_log, 'r') as f:
                log_content = f.read()
                raw_cells = re.findall(r"(sky130_fd_sc_hd__\w+)\s+cells:\s+(\d+)", log_content)
                if raw_cells:
                    metrics["cell_list"] = sorted([(k, int(v)) for k, v in raw_cells], key=lambda x: x[1], reverse=True)
                
                for line in log_content.split('\n'):
                    if "ERROR" in line or "Warning:" in line:
                        if len(metrics["errors"]) < 10: metrics["errors"].append(line.strip())

        # 2. PARSE AREA REPORT (Yosys JSON Format)
        area_rpt = os.path.join(report_dir, "area.rpt")
        if os.path.exists(area_rpt):
            with open(area_rpt, 'r') as f:
                content = f.read()
                
                # Parse JSON keys specifically
                m_area = re.search(r'"area":\s+([\d\.]+)', content)
                if m_area: metrics["area"] = m_area.group(1)
                
                m_cells = re.search(r'"num_cells":\s+(\d+)', content)
                if m_cells: metrics["cells"] = m_cells.group(1)
                
                m_wires = re.search(r'"num_wires":\s+(\d+)', content)
                if m_wires: metrics["wires"] = m_wires.group(1)
                
                m_bits = re.search(r'"num_pub_wire_bits":\s+(\d+)', content)
                if m_bits: metrics["bits"] = m_bits.group(1)

        # 3. PARSE TIMING REPORT (OpenSTA)
        timing_rpt = os.path.join(report_dir, "timing.rpt")
        if os.path.exists(timing_rpt):
            with open(timing_rpt, 'r') as f:
                content = f.read()
                
                trace_match = re.search(r"(Startpoint:.*?slack \([A-Z]+\))", content, re.DOTALL)
                if trace_match:
                    metrics["critical_path_trace"] = trace_match.group(1)

                slacks = re.findall(r"([-+]?\d+\.\d+)\s+slack\s+\((VIOLATED|MET)\)", content)
                if slacks:
                    worst_slack = min(slacks, key=lambda x: float(x[0]))
                    metrics["wns"] = worst_slack[0]
                    metrics["status"] = worst_slack[1]
                else:
                    metrics["status"] = "MET" 

                chunks = content.split("Path Group: ")
                seen_groups = set()
                for chunk in chunks[1:]: 
                    lines = chunk.strip().split('\n')
                    g_name = lines[0].strip()
                    if g_name in seen_groups: continue
                    seen_groups.add(g_name)
                    
                    m_slack = re.search(r"([-+]?\d+\.\d+)\s+slack\s+\((VIOLATED|MET)\)", chunk)
                    m_end = re.search(r"Endpoint:\s+(\S+)", chunk)
                    
                    if m_slack:
                        s_val = m_slack.group(1)
                        s_stat = m_slack.group(2)
                        end_p = m_end.group(1) if m_end else "Unknown"
                        metrics["timing_groups"].append((g_name, s_val, s_stat, end_p))

        # 4. PARSE POWER REPORT (OpenSTA)
        power_rpt = os.path.join(report_dir, "power.rpt")
        if os.path.exists(power_rpt):
            with open(power_rpt, 'r') as f:
                for line in f:
                    parts = line.split()
                    if not parts: continue
                    if parts[0] == "Sequential" and len(parts)>=6: metrics["pwr_seq"] = parts[1:6]
                    elif parts[0] == "Combinational" and len(parts)>=6: metrics["pwr_comb"] = parts[1:6]
                    elif parts[0] == "Clock" and len(parts)>=6: metrics["pwr_clk"] = parts[1:6]
                    elif parts[0] == "Macro" and len(parts)>=6: metrics["pwr_mac"] = parts[1:6]
                    elif parts[0] == "Pad" and len(parts)>=6: metrics["pwr_pad"] = parts[1:6]
                    elif parts[0] == "Total" and len(parts)>=6: metrics["pwr_tot"] = parts[1:6]
                    elif "%" in parts[0] and len(parts)>=3 and "Total" not in line: metrics["pwr_pct"] = parts[0:3]

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
            t_table += f"| {g:<13} | {s:<11} | {st:<10} | {end:<25} |\n"

        c_table = ""
        total_c = int(metrics["cells"]) if int(metrics["cells"]) > 0 else 1
        for name, count in metrics["cell_list"][:15]: 
            pct = (count / total_c) * 100
            c_table += f"| {name:<30} | {str(count):<6} | {pct:<4.1f}% |\n"

        rpt = f"""################################################################################
#                                            POST SYNTHESIS REPORT
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
  SECTION 4: CELL UTILIZATION (Top 15)
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
        self.list_err.setStyleSheet("background:#ffffff; color:#cf222e; font-family:Consolas; border:1px solid #d0d7de; padding: 5px;")
        self.log_tabs.addTab(self.list_err, "Issues / Errors")
        
        l_lay.addWidget(self.log_tabs)
        lay.addWidget(left_col, stretch=2) 

        # === RIGHT COLUMN (DASHBOARD) - COMPACTED ===
        right_col = QFrame()
        right_col.setStyleSheet("background: #f6f8fa; border-left: 1px solid #d0d7de;")
        right_col.setFixedWidth(360) 
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
        # NEW: Parse from FILES in the report directory
        _, base = self.ide.get_context()
        if not base: return
        root = self.ide.get_proj_root(base)
        report_dir = os.path.join(root, "reports")
        
        m = ReportEngine.parse_files(report_dir)
        
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
        
        self.ide.log_system("Generating Post Synthesis Report...", "SYS")
        print(rpt) 
        self.ide.log_system("Report generated in background.", "RPT")

    def save_report(self):
        if not hasattr(self, 'last_report'): return
        _, base = self.ide.get_context()
        report_name = f"{base or 'design'}_synthesis_report.rpt"
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
        
        # --- 1. INITIALIZE WIDGETS ---
        self.peeker = SiliconPeeker()
        self.gds_viewer = GDSViewerWidget()
        
        self.def_ctrl_widget = QWidget()
        def_layout = QVBoxLayout(self.def_ctrl_widget); def_layout.setContentsMargins(0,0,0,0)
        
        self.chk_inst = QCheckBox("Cells"); self.chk_inst.setChecked(True)
        self.chk_pins = QCheckBox("Pins"); self.chk_pins.setChecked(True)
        self.chk_nets = QCheckBox("Nets"); self.chk_nets.setChecked(False)
        self.chk_power = QCheckBox("Power"); self.chk_power.setChecked(True)
        
        self.btn_heat = QPushButton("Heatmap"); self.btn_heat.setCheckable(True)
        self.btn_heat.setStyleSheet("QPushButton:checked { background-color: #ffcccc; color: red; border: 1px solid red; }")
        
        def_layout.addWidget(QLabel("<b>DEF Layers</b>"))
        def_layout.addWidget(self.chk_inst); def_layout.addWidget(self.chk_pins)
        def_layout.addWidget(self.chk_nets); def_layout.addWidget(self.chk_power)
        def_layout.addSpacing(10); def_layout.addWidget(QLabel("<b>Overlay</b>"))
        def_layout.addWidget(self.btn_heat); def_layout.addStretch()

        self.gds_ctrl_widget = QWidget()
        self.gds_ctrl_widget.setVisible(False)
        gds_layout = QVBoxLayout(self.gds_ctrl_widget); gds_layout.setContentsMargins(0,0,0,0)
        
        self.layer_list = QListWidget()
        self.layer_list.setStyleSheet("QListWidget { font-size: 10px; border: none; background: #f0f0f0; }")
        self.layer_list.itemChanged.connect(self.on_layer_toggle)
        
        gds_layout.addWidget(QLabel("<b>GDS Layers</b>"))
        gds_layout.addWidget(self.layer_list)

        # [UPDATE] Added Magic GUI Button
        self.btn_gui = QPushButton("Native GUI (OpenROAD)")
        self.btn_magic = QPushButton("✨ Magic GUI")
        self.btn_magic.setStyleSheet("color: #5a32a3; font-weight: bold;") # Magic purple branding
        
        self.btn_ref = QPushButton("Refresh View")
        self.btn_load = QPushButton("📂 Load Routed")
        
        self.term_log = QTextEdit(); self.term_log.setReadOnly(True)
        self.term_log.setStyleSheet("background: #101010; color: #00FF00; font-family: Consolas; border: none;")
        self.term_in = QLineEdit(); self.term_in.setPlaceholderText("Enter TCL command...")
        self.term_in.setStyleSheet("background: #202020; color: white; border-top: 1px solid #444; font-family: Consolas; padding: 5px;")

        # --- 2. LAYOUT ---
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0,0,0,0)
        
        self.ribbon = QFrame(); self.ribbon.setStyleSheet("background: #f0f0f0; border-bottom: 1px solid #ccc;"); self.ribbon.setFixedHeight(40) 
        r_lay = QHBoxLayout(self.ribbon); r_lay.setContentsMargins(5,2,5,2)
        
        self.steps = ["Init", "Floorplan", "Tapcells", "PDN", "IO Pins", "Place", "CTS", "Route", "GDS"]
        self.signoff_steps = ["Antenna", "STA", "DRC"] 
        
        for step in self.steps:
            btn = QPushButton(step); btn.setStyleSheet("padding: 2px; font-weight: bold; font-size: 11px;")
            btn.clicked.connect(lambda _, s=step: self.run_flow_step(s))
            r_lay.addWidget(btn)
            
        line = QFrame(); line.setFrameShape(QFrame.Shape.VLine); line.setFrameShadow(QFrame.Shadow.Sunken)
        r_lay.addWidget(line)
        
        for step in self.signoff_steps:
            btn = QPushButton(step); btn.setStyleSheet("padding: 2px; font-weight: bold; font-size: 11px; color: #880000;")
            btn.clicked.connect(lambda _, s=step: self.run_flow_step(s))
            r_lay.addWidget(btn)

        r_lay.addStretch()
        btn_rst = QPushButton("🔄 Reset"); btn_rst.clicked.connect(self.reset_backend); r_lay.addWidget(btn_rst)
        btn_cfg = QPushButton("⚙ PDK Config"); btn_cfg.clicked.connect(self.open_pdk_selector); r_lay.addWidget(btn_cfg)
        self.layout.addWidget(self.ribbon)
        
        v_split = QSplitter(Qt.Orientation.Vertical)
        h_widget = QWidget(); h_lay = QHBoxLayout(h_widget); h_lay.setContentsMargins(0,0,0,0); h_lay.setSpacing(0)
        
        sidebar = QFrame(); sidebar.setFixedWidth(140); sidebar.setStyleSheet("background: #e8e8e8; border-right: 1px solid #aaa;")
        s_lay = QVBoxLayout(sidebar); s_lay.setContentsMargins(5,10,5,10)
        s_lay.addWidget(self.def_ctrl_widget)
        s_lay.addWidget(self.gds_ctrl_widget)
        
        # [UPDATE] Add buttons to sidebar
        s_lay.addWidget(self.btn_gui)
        s_lay.addWidget(self.btn_magic)
        s_lay.addWidget(self.btn_ref)
        s_lay.addWidget(self.btn_load)
        h_lay.addWidget(sidebar)
        
        self.viz_tabs = QTabWidget(); self.viz_tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.viz_tabs.addTab(self.peeker, "Live Floorplan (DEF)")
        self.viz_tabs.addTab(self.gds_viewer, "Final Chip (GDS)")
        h_lay.addWidget(self.viz_tabs)
        v_split.addWidget(h_widget)
        
        term_widget = QWidget(); t_lay = QVBoxLayout(term_widget); t_lay.setContentsMargins(0,0,0,0)
        t_lay.addWidget(self.term_log); t_lay.addWidget(self.term_in)
        v_split.addWidget(term_widget)
        v_split.setStretchFactor(0, 4); v_split.setStretchFactor(1, 1)
        self.layout.addWidget(v_split)

        # --- 3. CONNECTIONS ---
        self.chk_inst.toggled.connect(self.update_view)
        self.chk_pins.toggled.connect(self.update_view)
        self.chk_nets.toggled.connect(self.update_view)
        self.chk_power.toggled.connect(self.update_view)
        self.btn_heat.toggled.connect(self.update_view)
        
        self.btn_gui.clicked.connect(self.launch_native_gui)
        self.btn_magic.clicked.connect(self.launch_magic_gui) # [UPDATE] Connect signal
        self.btn_ref.clicked.connect(self.force_refresh_view)
        self.btn_load.clicked.connect(self.load_routed_design)
        
        self.viz_tabs.currentChanged.connect(self.on_tab_changed)
        self.term_in.returnPressed.connect(self.send_command)

        # --- 4. STARTUP ---
        self.proc = None
        self.pending_init = None
        self.cmd_active = False
        
        self.reset_backend() 
        self.viz_tabs.setCurrentIndex(0)

    # === [NEW] MAGIC GUI LAUNCHER ===
    def launch_magic_gui(self):
        """Launches Magic VLSI in GUI mode with the correct Tech file."""
        if not shutil.which("magic"):
            self.term_log.append("[ERR] Magic not found.")
            return

        if not self.active_pdk: 
            self.term_log.append("[ERR] No PDK Active.")
            return

        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        gds_path = os.path.join(proj_root, "results", "design.gds")
        
        if not os.path.exists(gds_path): 
             self.term_log.append("[ERR] GDS not found. Run 'GDS' step first.")
             return

        pdk_tech = self.active_pdk.get('tech', '')
        if not os.path.exists(pdk_tech):
             self.term_log.append("[ERR] Magic Tech file not found in PDK config.")
             return

        self.term_log.append(f"[SYS] Launching Magic GUI for {os.path.basename(gds_path)}...")
        # -d XR uses the X11 Cairo renderer (faster/better looking than default)
        # -T loads the tech file
        subprocess.Popen(["magic", "-d", "XR", "-T", pdk_tech, gds_path], cwd=proj_root)

    # === KEEP ALL EXISTING HELPERS BELOW ===
    # (ask_command, reset_backend, on_tab_changed, populate_gds_layers, on_layer_toggle, 
    # view_final_gds, run_flow_step, trigger_magic_drc, trigger_magic_merge, open_pdk_selector, 
    # read_stdout, send_command, send_command_internal, update_view, load_routed_design, 
    # launch_native_gui, force_refresh_view, load_checkpoint, save_checkpoint)
    
    def ask_command(self, title, label, text):
        dlg = QInputDialog(None)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setTextValue(text)
        dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        dlg.resize(600, 200) 
        if dlg.exec(): return dlg.textValue(), True
        return "", False

    def reset_backend(self):
        if self.proc:
            if self.proc.state() == QProcess.ProcessState.Running: self.proc.kill()
            self.proc = None
        self.term_log.clear()
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read_stdout)
        if shutil.which("openroad"): self.proc.start("openroad")
        else: self.term_log.append("[ERR] OpenROAD binary not found.")

    def on_tab_changed(self, index):
        if index == 0:
            self.def_ctrl_widget.setVisible(True); self.gds_ctrl_widget.setVisible(False)
        else: 
            self.def_ctrl_widget.setVisible(False); self.gds_ctrl_widget.setVisible(True)
            self.view_final_gds()

    def populate_gds_layers(self):
        self.layer_list.clear()
        layers = self.gds_viewer.get_layers()
        for layer, datatype in layers:
            item = QListWidgetItem(f"{layer}/{datatype}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, (layer, datatype))
            self.layer_list.addItem(item)

    def on_layer_toggle(self, item):
        layer, datatype = item.data(Qt.ItemDataRole.UserRole)
        visible = (item.checkState() == Qt.CheckState.Checked)
        self.gds_viewer.set_layer_visible(layer, datatype, visible)

    def view_final_gds(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        gds_path = os.path.join(proj_root, "results", "design.gds")
        if os.path.exists(gds_path):
            if self.gds_viewer.loaded_file != gds_path:
                self.term_log.append(f"[SYS] Loading GDS: {gds_path}...")
                self.gds_viewer.load_gds(gds_path)
                self.populate_gds_layers()
        else:
            self.term_log.append(f"[ERR] GDS not found. Run 'GDS' step first.")

    def run_flow_step(self, step_name):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        results_dir = os.path.join(proj_root, "results"); os.makedirs(results_dir, exist_ok=True)
        reports_dir = os.path.join(proj_root, "reports"); os.makedirs(reports_dir, exist_ok=True)
        def_abs_path = os.path.join(results_dir, "temp.def").replace("\\", "/")
        write_cmd = f"write_def \"{def_abs_path}\""

        if step_name == "Antenna":
            self.term_log.append("\n[SIGNOFF] Running Antenna Check...")
            self.send_command_internal("check_antennas -report_file reports/antenna.rpt; puts \"Antenna Violations: [check_antennas]\"")
            return

        if step_name == "STA":
            if not self.active_pdk: QMessageBox.critical(self, "Error", "PDK not active."); return
            self.term_log.append("\n[SIGNOFF] Running Signoff Timing Analysis...")
            lib_cmd = f"read_liberty \"{self.active_pdk['lib']}\""
            cmd = f"{lib_cmd}\nreport_checks -path_delay max -format full_clock_expanded -fields {{slew cap input_pins fanout}} -digits 4\nreport_worst_slack -max\nreport_tns\nreport_wns"
            self.send_command_internal(cmd)
            return

        if step_name == "DRC":
            if not self.active_pdk or 'gds' not in self.active_pdk: QMessageBox.critical(self, "Error", "PDK GDS Required."); return
            gds_file = os.path.join(results_dir, "design.gds")
            if not os.path.exists(gds_file): self.term_log.append("[ERR] Generate GDS first!"); return
            self.trigger_magic_drc(proj_root, gds_file)
            return

        if step_name == "Init":
            db_path = os.path.join(results_dir, "checkpoint.odb")
            if os.path.exists(db_path):
                reply = QMessageBox.question(self, "Resume?", "Found saved checkpoint. Load it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes: self.load_checkpoint(); return
            if not self.active_pdk: 
                 if not self.open_pdk_selector(): return
            tcl_path = os.path.join(proj_root, "init_pdk.tcl")
            ctx = self.ide.get_context()[0] or "top"
            netlist_path = os.path.join(proj_root, "netlist", f"{ctx}_netlist.v")
            if not os.path.exists(netlist_path): netlist_path = self.ide.current_file or "design.v"
            sdc_path = os.path.join(proj_root, "netlist", f"{ctx}.sdc")
            if not os.path.exists(sdc_path):
               with open(sdc_path, 'w') as f: f.write("create_clock -name clk -period 10.0 [get_ports clk]\nset_input_delay 2.0 -clock clk [all_inputs]\nset_output_delay 2.0 -clock clk [all_outputs]\n")
            tcl_content = f"""read_lef "{self.active_pdk['tlef']}"\nread_lef "{self.active_pdk['lef']}"\nread_liberty "{self.active_pdk['lib']}"\nread_verilog "{netlist_path}"\nlink_design {ctx}\nread_sdc "{sdc_path}" """
            try:
                with open(tcl_path, 'w') as f: f.write(tcl_content)
                self.pending_init = f"source {tcl_path}"
                self.term_log.append("[SYS] Rebooting OpenROAD...")
                self.reset_backend() 
            except Exception as e: self.term_log.append(f"[ERR] File Error: {e}")
            return

        if step_name == "GDS":
            if not self.active_pdk or 'gds' not in self.active_pdk: QMessageBox.critical(self, "Error", "No GDS defined."); return
            self.term_log.append("[SYS] Starting GDS Generation Flow...")
            final_def = os.path.join(results_dir, "final_routed.def").replace("\\", "/")
            self.send_command_internal(f"write_def \"{final_def}\"")
            QTimer.singleShot(2000, lambda: self.trigger_magic_merge(proj_root, final_def))
            return

        cmd = ""
        if not SSAForge.ALIASES: SSAForge.load_aliases()
        pdk_name = self.active_pdk.get('name', SSAForge.DEFAULT_PDK) if self.active_pdk else SSAForge.DEFAULT_PDK
        lib_path = self.active_pdk.get('lib', None) if self.active_pdk else None

        if step_name == "Floorplan": cmd = f"initialize_floorplan -die_area \"0 0 400 400\" -core_area \"10 10 390 390\" -site unithd; {write_cmd}"
        elif step_name == "Tapcells": cmd = SSAForge.get_tap_cmd(pdk_name, lib_path) + f"; {write_cmd}"
        elif step_name == "PDN": cmd = "add_global_connection -net {VDD} -pin_pattern {^VPWR$|^VDD$} -power; add_global_connection -net {VSS} -pin_pattern {^VGND$|^VSS$} -ground; set_voltage_domain -name {Core} -power {VDD} -ground {VSS}; define_pdn_grid -name {grid} -voltage_domains {Core}; add_pdn_stripe -grid {grid} -layer {met1} -width {0.48} -followpins; add_pdn_stripe -grid {grid} -layer {met4} -width {1.6} -pitch {27.2} -offset {13.6} -extend_to_core_ring; add_pdn_connect -grid {grid} -layers {met1 met4}; pdngen; " + write_cmd
        elif step_name == "IO Pins": cmd = f"place_pins -hor_layers met3 -ver_layers met4; {write_cmd}"
        elif step_name == "Place": cmd = f"global_placement -density 0.6; detailed_placement; {write_cmd}"
        elif step_name == "CTS": cmd = SSAForge.get_cts_cmd(pdk_name, lib_path) + f"; {write_cmd}"
        elif step_name == "Route":
            guide_path = os.path.join(results_dir, "route.guide").replace("\\", "/")
            drc_path = os.path.join(reports_dir, "drc.rpt").replace("\\", "/")
            fix_script = os.path.join(proj_root, "fix.tcl").replace("\\", "/")
            try: 
                with open(fix_script, 'w') as f: f.write("set db [ord::get_db]; set chip [$db getChip]; set block [$chip getBlock]; set net_names {zero_ one_ logic0 logic1}; foreach name $net_names { set net [$block findNet $name]; if {$net != \"NULL\"} { $net setSigType \"SIGNAL\" } }")
            except: pass
            cmd = f"source \"{fix_script}\"; global_route -guide_file \"{guide_path}\" -congestion_iterations 50 -verbose; detailed_route -output_drc \"{drc_path}\"; {write_cmd}"

        if cmd:
            text, ok = self.ask_command(f"Run {step_name}", "Confirm TCL Command:", cmd)
            if ok and text: self.send_command_internal(text)

    def trigger_magic_drc(self, root, gds_path):
        if not shutil.which("magic"): self.ide.queue.put(("[BACKEND]", "[ERR] 'magic' not found.")); return
        pdk_tech = self.active_pdk.get('tech', '')
        if not os.path.exists(pdk_tech): self.ide.queue.put(("[BACKEND]", "[ERR] Missing Tech file.")); return
        script_content = f"drc off\ngds read {gds_path}\ndrc style drc(fast)\ndrc on\ndrc check\ndrc catchup\nset count [drc list count]\nputs \"SILIS_DRC_VIOLATIONS: $count\"\nif {{$count > 0}} {{ drc list all }}\nquit"
        script_path = os.path.join(root, "run_drc.tcl")
        with open(script_path, 'w') as f: f.write(script_content)
        self.term_log.append(f"\n[SIGNOFF] Running Magic DRC on {os.path.basename(gds_path)}...")
        def run_drc():
            try:
                cmd = ["magic", "-noconsole", "-dnull", "-T", pdk_tech, script_path]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                import re
                for line in iter(proc.stdout.readline, ''):
                    line = line.strip()
                    if "SILIS_DRC_VIOLATIONS" in line:
                        m = re.search(r'(\d+)\s*\}?$', line); count = m.group(1) if m else "Unknown"
                        if count == "0": self.ide.queue.put(("[BACKEND]", "🟢 DRC CLEAN (0 Violations)"))
                        else: self.ide.queue.put(("[BACKEND]", f"🔴 DRC FAILED: {count} Violations Found"))
                    elif "Error:" in line or "error" in line.lower(): self.ide.queue.put(("[BACKEND]", f"[DRC ERR] {line}"))
                proc.wait()
                self.ide.queue.put(("[BACKEND]", "DRC Run Complete."))
            except Exception as e: self.ide.queue.put(("[BACKEND]", f"[ERR] DRC Execution Failed: {e}"))
        threading.Thread(target=run_drc, daemon=True).start()

    def trigger_magic_merge(self, root, def_path):
        if not shutil.which("magic"): self.ide.queue.put(("[BACKEND]", "[ERR] 'magic' executable not found.")); return
        pdk_gds = self.active_pdk.get('gds', ''); pdk_tech = self.active_pdk.get('tech', '')
        pdk_tlef = self.active_pdk.get('tlef', ''); pdk_lef = self.active_pdk.get('lef', '')   
        output_gds = os.path.join(root, "results", "design.gds").replace("\\", "/")
        if not all(os.path.exists(p) for p in [pdk_gds, pdk_tech, pdk_tlef, pdk_lef]): self.ide.queue.put(("[BACKEND]", f"[ERR] Missing PDK files.")); return
        script_content = f"drc off\nlocking off\ngds readonly true\ngds rescale false\nlef read {pdk_tlef}\nlef read {pdk_lef}\ngds read {pdk_gds}\ndef read {def_path}\ngds write {output_gds}\nquit"
        script_path = os.path.join(root, "merge_magic.tcl")
        with open(script_path, 'w') as f: f.write(script_content)
        self.term_log.append(f"[SYS] Magic: Merging with LEF support...")
        def run_magic():
            try:
                cmd = ["magic", "-noconsole", "-dnull", "-T", pdk_tech, script_path]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode == 0 and os.path.exists(output_gds): self.ide.queue.put(("[BACKEND]", f"Saved: {output_gds}"))
                else: self.ide.queue.put(("[BACKEND]", f"[ERR] Magic Failed:\n{proc.stderr}\n{proc.stdout}"))
            except Exception as e: self.ide.queue.put(("[BACKEND]", f"[ERR] Magic Execution Error: {e}"))
        threading.Thread(target=run_magic, daemon=True).start()

    def open_pdk_selector(self):
        dlg = PDKSelector(self.pdk_mgr, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.active_pdk = dlg.selected_config; self.term_log.append(f"[SYS] Target PDK: {self.active_pdk['name']}"); return True
        return False

    def read_stdout(self):
        data = self.proc.readAllStandardOutput().data().decode()
        self.term_log.append(data.strip())
        self.term_log.verticalScrollBar().setValue(self.term_log.verticalScrollBar().maximum())
        if self.pending_init and ("OpenROAD" in data or "openroad>" in data): self.send_command_internal(self.pending_init); self.pending_init = None
        if self.cmd_active and "openroad>" in data: self.cmd_active = False; self.force_refresh_view()

    def send_command(self): cmd = self.term_in.text(); self.term_in.clear(); self.send_command_internal(cmd)
        
    def send_command_internal(self, cmd):
        self.term_log.append(f"> {cmd}")
        if "initialize_floorplan" in cmd:
            import re
            m = re.search(r'-die_area\s+"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"', cmd)
            if m:
                x1, y1, x2, y2 = map(float, m.groups())
                try: self.peeker.set_die_area(x1, y1, x2, y2)
                except: pass
        if self.proc and self.proc.state() == QProcess.ProcessState.Running: self.cmd_active = True; self.proc.write(f"{cmd}\n".encode())
        else: self.term_log.append(f"[ERR] Backend not running. Click Reset.")
    
    def update_view(self):
        try:
            self.peeker.show_insts = self.chk_inst.isChecked(); self.peeker.show_pins = self.chk_pins.isChecked()
            self.peeker.show_nets = self.chk_nets.isChecked(); self.peeker.show_power = self.chk_power.isChecked()
            if hasattr(self, 'btn_heat'): self.peeker.show_heatmap = self.btn_heat.isChecked()
            self.peeker.redraw()
        except: pass
    
    def load_routed_design(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        def_path = os.path.join(proj_root, "results", "final_routed.def")
        if os.path.exists(def_path): 
            self.term_log.append(f"[SYS] Loading Routed Design from: {def_path}")
            self.peeker.load_def_file(def_path); self.chk_nets.setChecked(True); self.peeker.show_nets = True; self.peeker.redraw(); self.viz_tabs.setCurrentIndex(0)
        else: self.term_log.append(f"[ERR] Routed file not found at: {def_path}")

    def launch_native_gui(self):
        if not self.active_pdk: return
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        def_path = os.path.join(proj_root, "results", "temp.def")
        if not os.path.exists(def_path): return
        view_tcl = os.path.join(proj_root, "view.tcl")
        with open(view_tcl, 'w') as f: f.write(f'read_lef "{self.active_pdk["tlef"]}"\nread_lef "{self.active_pdk["lef"]}"\nread_def "{def_path}"\n')
        subprocess.Popen(["openroad", "-gui", view_tcl], cwd=proj_root)
    
    def force_refresh_view(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        def_path = os.path.join(proj_root, "results", "temp.def")
        if os.path.exists(def_path): self.peeker.load_def_file(def_path)

    def load_checkpoint(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        db_path = os.path.join(proj_root, "results", "checkpoint.odb").replace("\\", "/")
        if os.path.exists(db_path):
            self.term_log.append(f"[SYS] Loading Checkpoint from {db_path}...")
            self.send_command_internal(f"read_db \"{db_path}\"")
            self.force_refresh_view(); return True
        return False

    def save_checkpoint(self):
        if not self.proc: return
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        db_path = os.path.join(proj_root, "results", "checkpoint.odb").replace("\\", "/")
        self.term_log.append(f"[SYS] Saving Checkpoint to {db_path}...")
        self.send_command_internal(f"write_db \"{db_path}\"")



# ================= 4. VOLARE PDK MANAGER (Full Implementation) =================

class VolareWorker(QThread):
    finished = pyqtSignal(str, str) # cmd_type, output
    log = pyqtSignal(str)

    def __init__(self, cmd_type, args=[]):
        super().__init__()
        self.cmd_type = cmd_type
        self.args = args

    def run(self):
        cmd = ["volare"] + self.args
        try:
            self.log.emit(f"[VOLARE] Running: {' '.join(cmd)}...")
            
            # Run Subprocess
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            out, _ = proc.communicate()
            
            # === [FIX] Graceful Handling for "Not Found" ===
            if proc.returncode != 0:
                # If checking path/active fails, it just means it's not installed yet.
                # Don't treat it as a crash.
                if self.cmd_type in ["path", "output"]:
                    self.finished.emit(self.cmd_type, "Not Installed / Not Configured")
                    return

                # Real Error for other commands
                self.log.emit(f"[VOLARE] Error (Code {proc.returncode}):\n{out}")
                self.finished.emit("error", out)
            else:
                self.finished.emit(self.cmd_type, out)
                
        except FileNotFoundError:
            self.finished.emit("error", "Volare executable not found. Please install: pip install volare")
        except Exception as e:
            self.finished.emit("error", str(e))

class VolareManagerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # --- 1. PDK Selector ---
        top_frame = QFrame()
        top_frame.setStyleSheet("background: #e1e4e8; padding: 5px; border-radius: 4px;")
        hl = QHBoxLayout(top_frame)
        
        self.combo_pdk = QComboBox()
        self.combo_pdk.addItems(["sky130", "gf180mcu"])
        
        hl.addWidget(QLabel("<b>Target PDK Family:</b>"))
        hl.addWidget(self.combo_pdk)
        hl.addStretch()
        self.layout.addWidget(top_frame)

        # --- 2. Raw Output Display (The Terminal) ---
        self.term = QTextEdit()
        self.term.setReadOnly(True)
        self.term.setStyleSheet("background: #1e1e1e; color: #00ff00; font-family: Consolas; font-size: 10pt;")
        self.term.setPlaceholderText("Volare output will appear here...")
        self.layout.addWidget(self.term)

        # --- 3. Command Grid ---
        btn_grid = QGridLayout()
        
        # Row 1: Information
        btn_ls = QPushButton("List Installed (ls)"); btn_ls.clicked.connect(lambda: self.run_volare("ls"))
        btn_rem = QPushButton("List Remote (ls-remote)"); btn_rem.clicked.connect(lambda: self.run_volare("ls-remote"))
        btn_path = QPushButton("Show Path"); btn_path.clicked.connect(lambda: self.run_volare("path"))
        btn_curr = QPushButton("Show Active"); btn_curr.clicked.connect(lambda: self.run_volare("output"))
        
        # Row 2: Actions
        btn_enable = QPushButton("⚡ Enable Version..."); btn_enable.clicked.connect(self.ask_enable)
        btn_enable.setStyleSheet("background: #2da44e; color: white; font-weight: bold;")
        
        btn_build = QPushButton("⬇ Build/Install..."); btn_build.clicked.connect(self.ask_build)
        btn_build.setStyleSheet("background: #00509d; color: white; font-weight: bold;")
        
        btn_prune = QPushButton("✂ Prune Old"); btn_prune.clicked.connect(self.ask_prune)
        
        btn_grid.addWidget(btn_ls, 0, 0)
        btn_grid.addWidget(btn_rem, 0, 1)
        btn_grid.addWidget(btn_path, 0, 2)
        btn_grid.addWidget(btn_curr, 0, 3)
        
        btn_grid.addWidget(btn_enable, 1, 0, 1, 2) # Span 2 cols
        btn_grid.addWidget(btn_build, 1, 2, 1, 2)
        btn_grid.addWidget(btn_prune, 2, 0, 1, 4)

        self.layout.addLayout(btn_grid)
        
        # --- 4. Manual Command Line ---
        bg_cmd = QHBoxLayout()
        self.cmd_in = QLineEdit()
        self.cmd_in.setPlaceholderText("Manual arguments (e.g. enable <hash>)")
        self.cmd_in.returnPressed.connect(self.run_manual)
        btn_run = QPushButton("Run Manual"); btn_run.clicked.connect(self.run_manual)
        
        bg_cmd.addWidget(QLabel("Manual:"))
        bg_cmd.addWidget(self.cmd_in)
        bg_cmd.addWidget(btn_run)
        self.layout.addLayout(bg_cmd)

    def log(self, text):
        self.term.append(text)
        self.term.verticalScrollBar().setValue(self.term.verticalScrollBar().maximum())

    def run_volare(self, action, extra_args=[]):
        pdk = self.combo_pdk.currentText()
        args = [action, "--pdk", pdk] + extra_args
        
        self.term.append(f"\n> volare {' '.join(args)}")
        
        self.worker = VolareWorker(action, args)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(lambda _, out: self.log(f"\n[DONE]\n{out}"))
        self.worker.start()

    def ask_enable(self):
        text, ok = QInputDialog.getText(self, "Enable Version", "Enter Version Hash (or tag):")
        if ok and text:
            self.run_volare("enable", [text])

    def ask_build(self):
        text, ok = QInputDialog.getText(self, "Build/Install", "Enter Version Hash to Install:")
        if ok and text:
            self.run_volare("build", [text])

    def ask_prune(self):
        if QMessageBox.question(self, "Prune", "Delete all UNUSED versions?") == QMessageBox.StandardButton.Yes:
            self.run_volare("prune")

    def run_manual(self):
        txt = self.cmd_in.text().strip()
        if txt:
            self.run_volare(txt.split()[0], txt.split()[1:])
            self.cmd_in.clear()



class SettingsDialog(QDialog):
    def __init__(self, parent_ide):
        super().__init__(parent_ide)
        self.ide = parent_ide
        self.setWindowTitle("Silis Configuration Hub")
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # --- TAB 1: General (Keybinds) ---
        t_gen = QWidget(); form = QFormLayout(t_gen)
        
        # Fallback Lib
        self.e_pdk = QLineEdit(self.ide.pdk_path)
        btn_b = QPushButton("..."); btn_b.clicked.connect(lambda: self.e_pdk.setText(QFileDialog.getOpenFileName(self, "Lib", "", "*.lib")[0]))
        form.addRow("Fallback Lib:", self.e_pdk)
        form.addRow("", btn_b)
        
        # Keybinds
        self.bind_edits = {}
        form.addRow(QLabel("<b>Shortcut Keys (Post-Backtick `):</b>"))
        for name, key in self.ide.key_map.items():
            e = QLineEdit(key); e.setMaxLength(1); self.bind_edits[name] = e
            form.addRow(name.replace("_", " ").title() + ":", e)
            
        self.tabs.addTab(t_gen, "General Settings")
        
        # --- TAB 2: Volare Manager ---
        self.volare_wid = VolareManagerWidget(self)
        self.tabs.addTab(self.volare_wid, "Volare (PDK Version Control)")
        
        # --- Bottom Buttons ---
        bbox = QHBoxLayout()
        btn_save = QPushButton("Save & Close"); btn_save.setStyleSheet("padding: 8px;")
        btn_save.clicked.connect(self.save_and_close)
        bbox.addStretch(); bbox.addWidget(btn_save)
        layout.addLayout(bbox)

    def save_and_close(self):
        self.ide.pdk_path = self.e_pdk.text()
        for name, e in self.bind_edits.items():
            self.ide.key_map[name] = e.text().lower()
        self.accept()




# ================= 3. MAIN APP CONTROLLER =================

class SilisIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silis — Silicon Scaffold v2.1")
        self.resize(1400, 900)
        if os.path.exists("/usr/share/pixmaps/silis.png"):
            self.setWindowIcon(QIcon("/usr/share/pixmaps/silis.png"))
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

    def closeEvent(self, event):
        """
        Intercepts the window close event to save the OpenROAD state.
        """
        # Only ask if the backend is actually running/dirty
        if self.backend_widget.proc and self.backend_widget.proc.state() == QProcess.ProcessState.Running:
            reply = QMessageBox.question(
                self, 
                'Save Session?', 
                "Do you want to save the current Routing/Placement state?\n(Loads instantly next time)", 
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore() # Don't close
                return
            
            if reply == QMessageBox.StandardButton.Yes:
                self.backend_widget.save_checkpoint()
                # Give it a moment to write (simple block)
                self.backend_widget.proc.waitForReadyRead(3000) 
        
        event.accept()

    def reset_sk(self): self.sk_active = False; self.statusBar().clearMessage()

    def switch_world(self, index):
        self.stack.setCurrentIndex(index)
        self.btn_front.setChecked(index == 0)
        self.btn_back.setChecked(index == 1)

    # === CORE LOGIC ===

    # === REPLACE IN SilisIDE CLASS ===
    def generate_schematic(self):
        if self.schem_running:
            self.log_system("Schematic generation in progress...", "WARN")
            return

        self.log_system("Generating Schematic...")
        _, base = self.get_context()
        if not base: 
            self.log_system("No Top Module found", "ERR"); return
            
        root = self.prep_workspace(base)
        
        # [FIX] Grab all files, BUT filter out testbenches
        all_src = glob.glob(os.path.join(root, "source", "*.v")) + glob.glob(os.path.join(root, "source", "*.sv"))
        
        # Filter: Exclude files containing 'tb_', '_tb', or 'test_'
        src = [f for f in all_src if not any(x in os.path.basename(f).lower() for x in ["tb_", "_tb", "test_"])]
        
        if not src:
            self.log_system("No synthesis sources found (Check file naming).", "ERR")
            return

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
        
        # --- 1. YOSYS SCRIPT (With Explicit File Dumps) ---
        # Note the 'tee -o reports/area.rpt' to save area stats to a file
        ys = f"""
        read_liberty -lib {self.pdk_path}
        {read_cmd}
        synth -top {base}
        dfflibmap -liberty {self.pdk_path}
        abc -liberty {self.pdk_path}
        tee -o reports/area.rpt stat -liberty {self.pdk_path} -json
        write_verilog -noattr {v_net}
        """
        with open(os.path.join(root, "synth.ys"), 'w') as f: f.write(ys)
        
        # --- 2. STA SCRIPT (With Explicit File Dumps) ---
        # Redirects output (>) to timing.rpt and power.rpt
        tcl = f"""
        read_liberty {self.pdk_path}
        read_verilog {v_net}
        link_design {base}
        read_sdc netlist/{base}.sdc
        report_checks -path_delay max -fields {{slew cap input_pins nets fanout}} -format full_clock_expanded -group_count 100 > reports/timing.rpt
        report_power > reports/power.rpt
        exit
        """
        with open(os.path.join(root, "sta.tcl"), 'w') as f: f.write(tcl)

        def task():
            self.queue.put(("[SYS]", "Starting Synthesis Flow..."))
            
            # --- STEP 1: YOSYS ---
            try:
                # We pipe output to a file AND the GUI queue
                log_path = os.path.join(root, "reports/synthesis.log")
                with open(log_path, "w") as log_file:
                    p1 = subprocess.Popen(f"yosys synth.ys", shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                    
                    for line in iter(p1.stdout.readline, ''):
                        line = line.strip()
                        if line:
                            self.queue.put(("[YOSYS]", line)) 
                            log_file.write(line + "\n")
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
        dlg = SettingsDialog(self)
        dlg.exec()
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
    # === REPLACE IN SilisIDE CLASS ===
    def process_queue(self):
        while not self.queue.empty():
            item = self.queue.get()
            
            if isinstance(item, tuple): tag, content = item
            else: tag, content = "SYS", str(item)

            # [NEW] Route Backend-specific messages to Backend Terminal
            if tag == "[BACKEND]":
                self.backend_widget.term_log.append(content)
                self.backend_widget.term_log.verticalScrollBar().setValue(self.backend_widget.term_log.verticalScrollBar().maximum())

            # Existing Routing...
            elif tag == "UPDATE_DASHBOARD":
                self.tab_synth.update_dashboard()
                
            elif tag in ["[YOSYS]", "[STA]", "SYNTH_LOG", "STA_LOG"]:
                self.tab_synth.log_main.append(content)
                sb = self.tab_synth.log_main.verticalScrollBar()
                sb.setValue(sb.maximum())
                
            elif tag == "[SYS]" or tag == "SYS":
                self.log_system(content)
                
            else:
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
        super().__init__()
        self.root = root
        self.base = base
        self.src_files = src_files

    def run(self):
        # 1. Check for Graphviz (The Painter)
        if not shutil.which("dot"):
            self.log.emit("Graphviz ('dot') not found!", "ERR")
            self.log.emit("Run: sudo apt install graphviz", "TIP")
            return

        # Prepare paths
        read_cmd = "".join([f"read_verilog {s}; " for s in self.src_files])
        dot_base = os.path.join(self.root, self.base) # Yosys adds .dot automatically
        dot_file = dot_base + ".dot"
        svg_file = dot_base + ".svg"
        
        if os.path.exists(dot_file): os.remove(dot_file)

        # === STRATEGY 1: High-Level RTL (Best for reading) ===
        # 'proc' converts processes to logic. 'memory' handles arrays.
        # We explicitly use -prefix to control the output filename.
        cmd_rtl = f"yosys -p '{read_cmd} hierarchy -check -top {self.base}; proc; opt; show -colors 2 -width -stretch -format dot -prefix {dot_base}'"
        
        # === STRATEGY 2: Structural (Fallback if logic is too complex) ===
        # No optimization, just raw connectivity.
        cmd_raw = f"yosys -p '{read_cmd} hierarchy -auto-top; proc; show -colors 2 -width -stretch -format dot -prefix {dot_base}'"

        try:
            self.log.emit("Generating logic graph...", "SYS")
            
            # Try elegant RTL view first
            res = subprocess.run(cmd_rtl, shell=True, cwd=self.root, capture_output=True, text=True)
            
            # If RTL view failed (or produced empty dot), try raw view
            if not os.path.exists(dot_file):
                self.log.emit("Complex render failed. Trying structural view...", "WARN")
                subprocess.run(cmd_raw, shell=True, cwd=self.root, capture_output=True, text=True)

            # 3. Convert DOT to SVG (The Visualizer)
            if os.path.exists(dot_file):
                self.log.emit("Rendering SVG...", "SYS")
                # -Grankdir=LR makes it flow Left-to-Right (Standard Schematic style)
                subprocess.run(f"dot -Tsvg {dot_file} -o {svg_file} -Grankdir=LR", shell=True, cwd=self.root)
                
                if os.path.exists(svg_file):
                    self.finished.emit(svg_file)
                    self.log.emit("Schematic Ready.", "SYS")
                else:
                    self.log.emit("Graphviz failed to convert DOT to SVG.", "ERR")
            else:
                self.log.emit("Yosys failed to generate graph. Check syntax.", "ERR")
                self.log.emit(f"Yosys Stderr: {res.stderr[:200]}...", "DBG")

        except Exception as e:
            self.log.emit(f"Schematic Engine Crash: {e}", "ERR")





if __name__ == "__main__":
    # 1. Allow high-res icon loading
    QImageReader.setAllocationLimit(0)
    
    app = QApplication(sys.argv)
    
    # === THE FIX: ESTABLISH IDENTITY ===
    # This string MUST match the name of your .desktop file (silis.desktop)
    app.setDesktopFileName("silis.desktop") 
    
    # This string MUST match the 'StartupWMClass' we will add to the installer
    app.setApplicationName("silis") 
    # ===================================

    w = SilisIDE()
    w.show()
    sys.exit(app.exec())
