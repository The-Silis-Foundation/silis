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
from PyQt6.QtWidgets import QCheckBox, QGroupBox

# ================= PYQT6 IMPORTS =================
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QTreeView, QTabWidget,
                             QPlainTextEdit, QTextEdit, QToolBar, QPushButton, 
                             QLabel, QLineEdit, QFileDialog, QMessageBox, 
                             QInputDialog, QGraphicsView, QGraphicsScene, 
                             QGraphicsPixmapItem, QMenu, QFrame, QDockWidget,
                             QSizePolicy, QDialog, QFormLayout, QComboBox, 
                             QGraphicsRectItem, QTableWidget, QTableWidgetItem,
                             QHeaderView, QAbstractItemView)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QThread, QDir, QEvent, QProcess, QRectF
from PyQt6.QtGui import (QAction, QFont, QColor, QSyntaxHighlighter, 
                         QTextCharFormat, QPixmap, QPainter, QImage, QBrush, QPen,
                         QFileSystemModel, QKeySequence, QShortcut, QImageReader, QTransform)
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

# ================= LIGHTWEIGHT DEF PARSER =================

# ================= ROBUST DEF PARSER & PEEKER =================

from PyQt6.QtWidgets import QCheckBox, QGroupBox # Add these to imports

# ================= HIGH-PERFORMANCE DEF PARSER =================

# ================= BULLDOZER DEF PARSER (v4.20) =================

# ================= 2. SAFER PARSER =================

class DEFParser:
    def __init__(self, def_path):
        self.path = def_path
        self.die_rect = QRectF(0,0,0,0)
        self.comps_map = {}  # { 'instName': QRectF } -> O(1) Lookup
        self.comp_types = {} # { 'instName': 'STD'/'TAP' }
        self.pins = []       # List of (QRectF, name)
        self.nets = []       # List of [(x1,y1), (x2,y2)] lines
        self.dbu = 1000.0    
        
        if os.path.exists(def_path):
            self.parse()

    def parse(self):
        with open(self.path, 'r') as f: content = f.read()

        # 1. DBU
        m_dbu = re.search(r'UNITS\s+DISTANCE\s+MICRONS\s+(\d+)', content)
        if m_dbu: self.dbu = float(m_dbu.group(1))

        # 2. Die Area
        m_die = re.search(r'DIEAREA\s+\(\s+(-?\d+)\s+(-?\d+)\s+\)\s+\(\s+(-?\d+)\s+(-?\d+)\s+\)', content)
        if m_die:
            x1, y1, x2, y2 = map(int, m_die.groups())
            self.die_rect = QRectF(x1, y1, x2-x1, y2-y1)

        # 3. Components (Capture Name + Coords)
        # Format: - instName model + STATUS ( x y ) ...
        pattern = r'-\s+(\S+)\s+(\S+)\s+\+\s+(?:PLACED|FIXED|COVER)\s+\(\s+(-?\d+)\s+(-?\d+)\s+\)'
        comps = re.findall(pattern, content)
        
        std_w = 5 * self.dbu 
        std_h = 2.72 * self.dbu 
        
        for name, model, x, y in comps:
            rect = QRectF(int(x), int(y), std_w, std_h)
            self.comps_map[name] = rect
            self.comp_types[name] = "TAP" if "tap" in model.lower() or "fill" in model.lower() else "STD"

        # 4. Pins (Capture Name + Coords)
        # - pinName + NET netName + ... PLACED ( x y ) ...
        pin_pat = r'-\s+(\S+)\s+\+\s+NET\s+\S+.*\+\s+PLACED\s+\(\s+(-?\d+)\s+(-?\d+)\s+\)'
        pins = re.findall(pin_pat, content)
        pin_sz = 1 * self.dbu
        for name, x, y in pins:
            self.pins.append((QRectF(int(x), int(y), pin_sz, pin_sz), name))

        # 5. Nets (Ratsnest) - Simplified
        # Extracts connections: ( instName pinName ) ( instName pinName )
        # This regex finds groups of connections inside NET definitions
        net_blocks = re.findall(r'-\s+\S+\s+(?:\( \S+\s+\S+\s+\)\s*)+;', content)
        
        for block in net_blocks:
            # Extract all instances in this net: ( instName pin )
            conns = re.findall(r'\(\s+(\S+)\s+\S+\s+\)', block)
            points = []
            for inst in conns:
                if inst in self.comps_map:
                    r = self.comps_map[inst]
                    points.append((r.center().x(), r.center().y()))
            
            # Create lines connecting sequential points (Daisy Chain visual)
            if len(points) > 1:
                for i in range(len(points)-1):
                    self.nets.append((points[i], points[i+1]))

# ================= 3. CRASH-PROOF SILICON PEEKER =================

# ================= IMPROVED IMPORTS =================

# [KEEP DEFParser CLASS FROM v4.18 HERE]

# ================= ZOOMABLE SILICON PEEKER =================

class SiliconPeeker(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QColor("#FFFFFF")) 
        # Use ScrollHandDrag for panning with left mouse button
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Important: Flip Y axis so (0,0) is bottom-left (EDA convention)
        self.scale(1, -1) 
        
        self.def_data = None
        self.first_load = True # Flag for initial fit
        
        # Visibility Flags
        self.show_insts = True
        self.show_pins = True
        self.show_nets = False
        self.show_heatmap = False

    # --- ZOOM CONTROLS ---
    def wheelEvent(self, event):
        """Handles mouse wheel zooming."""
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor

        # Save the scene pos under the mouse to anchor the zoom
        oldPos = self.mapToScene(event.position().toPoint())

        # Zoom
        if event.angleDelta().y() > 0:
            self.scale(zoomInFactor, zoomInFactor)
        else:
            self.scale(zoomOutFactor, zoomOutFactor)

        # Get the new position and translate back to keep mouse anchored
        newPos = self.mapToScene(event.position().toPoint())
        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())
        
        event.accept()

    def fit_with_slack(self):
        """Fits content to view with a nice margin."""
        rect = self.scene.itemsBoundingRect()
        if rect.isNull(): return
        # Add 10% slack on all sides
        margin = max(rect.width(), rect.height()) * 0.1
        slack_rect = rect.adjusted(-margin, -margin, margin, margin)
        self.fitInView(slack_rect, Qt.AspectRatioMode.KeepAspectRatio)

    # --- LOADING & DRAWING ---
    def load_def_file(self, path):
        if not os.path.exists(path): return
        try:
            self.def_data = DEFParser(path)
            self.redraw()
            
            # Only auto-fit on the very first load to set a good baseline.
            # Subsequent reloads (e.g. after CTS) maintain user's zoom/pan.
            if self.first_load:
                self.fit_with_slack()
                self.first_load = False
        except Exception as e: print(f"Parser Err: {e}")

    def redraw(self):
        # Save current transform to restore pan/zoom state after clearing scene
        current_transform = self.transform()
        self.scene.clear()
        if not self.def_data: return

        # 1. Die Background (Z = -10)
        d = self.def_data.die_rect
        die = QGraphicsRectItem(d)
        die.setPen(QPen(QColor("#000000"), 0))
        die.setBrush(QBrush(QColor("#f9f9f9")))
        die.setZValue(-10)
        self.scene.addItem(die)

        # 2. Instances (Z = 0)
        if self.show_insts:
            for name, rect in self.def_data.comps_map.items():
                ctype = self.def_data.comp_types[name]
                item = QGraphicsRectItem(rect)
                if ctype == "TAP":
                    item.setPen(Qt.PenStyle.NoPen)
                    item.setBrush(QBrush(QColor("#dddddd"))) 
                else:
                    item.setPen(QPen(QColor("#00509d"), 0))
                    item.setBrush(QBrush(QColor("#4cc9f0"))) 
                item.setZValue(0)
                self.scene.addItem(item)

        # 3. Nets (Flylines) (Z = 5)
        if self.show_nets:
            pen = QPen(QColor(0, 0, 0, 60), 0)
            for p1, p2 in self.def_data.nets:
                line = self.scene.addLine(p1[0], p1[1], p2[0], p2[1], pen)
                line.setZValue(5)

        # 4. Pins & Labels (Z = 10)
        if self.show_pins:
            for rect, name in self.def_data.pins:
                # Pad
                item = QGraphicsRectItem(rect)
                item.setPen(QPen(QColor("#a4161a"), 0))
                item.setBrush(QBrush(QColor("#f25c54")))
                item.setZValue(10)
                self.scene.addItem(item)
                
                # Text Label (Flip Y back so text isn't upside down)
                text = self.scene.addText(name)
                text.setPos(rect.x(), rect.y())
                # Scale text so it's readable regardless of zoom
                scale_factor = rect.width() / 40.0 if rect.width() > 0 else 1.0
                text.setTransform(QTransform().scale(scale_factor, -scale_factor)) 
                text.setDefaultTextColor(QColor("black"))
                text.setZValue(11)

        # 5. Heatmap Overlay (Z = 20, Top Layer)
        if self.show_heatmap:
            self.draw_heatmap(d)

        # Restore previous zoom/pan state
        self.setTransform(current_transform)

    def draw_heatmap(self, die_rect):
        if die_rect.width() <= 0 or die_rect.height() <= 0: return
        
        # 20x20 Grid
        cols, rows = 20, 20
        grid_w = die_rect.width() / cols
        grid_h = die_rect.height() / rows
        counts = [[0]*cols for _ in range(rows)]
        
        # Bin component centers
        for rect in self.def_data.comps_map.values():
            cx = rect.center().x()
            cy = rect.center().y()
            c = int((cx - die_rect.x()) / grid_w)
            r = int((cy - die_rect.y()) / grid_h)
            if 0 <= c < cols and 0 <= r < rows:
                counts[r][c] += 1
        
        # Find max density for normalization
        max_c = 0
        for r in range(rows):
            for c in range(cols):
                 max_c = max(max_c, counts[r][c])
        if max_c == 0: max_c = 1
        
        # Draw grid cells
        for r in range(rows):
            for c in range(cols):
                val = counts[r][c] / max_c
                if val > 0.01: # Only draw if there's something there
                    g_rect = QRectF(die_rect.x() + c*grid_w, die_rect.y() + r*grid_h, grid_w, grid_h)
                    item = QGraphicsRectItem(g_rect)
                    item.setPen(Qt.PenStyle.NoPen)
                    # Gradient: Green (low) -> Yellow -> Red (high)
                    # Alpha behaves strangely with QColor HSL, using RGB with fixed alpha
                    red = int(min(255, val * 2 * 255))
                    green = int(min(255, (1 - val) * 2 * 255))
                    # Semi-transparent overlay
                    color = QColor(red, green, 0, 150) 
                    item.setBrush(QBrush(color))
                    item.setZValue(20) # Ensure it's on top
                    self.scene.addItem(item)


                    
                    # Optional: Draw count text inside macro-pixels if zoomed in?
                    # (Skipped for performance/clarity)


# ================= BACKEND WIDGET (CONTROLS) =================

class BackendWidget(QWidget):
    def __init__(self, parent_ide):
        super().__init__(parent_ide)
        self.ide = parent_ide 
        self.pdk_mgr = PDKManager()
        self.active_pdk = None
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        # --- RIBBON ---
        self.ribbon = QFrame()
        self.ribbon.setStyleSheet("background: #f0f0f0; border-bottom: 1px solid #ccc;")
        # Increased height for controls
        self.ribbon.setFixedHeight(90) 
        
        r_main_lay = QVBoxLayout(self.ribbon)
        r_main_lay.setContentsMargins(5,5,5,5)
        
        # Row 1: Flow Steps
        r_flow_lay = QHBoxLayout()
        self.steps = ["1. Init", "2. Floorplan", "3. Tapcells", "4. IO Pins", "5. Place", "6. CTS", "7. Route", "8. GDS"]
        for step in self.steps:
            btn = QPushButton(step)
            btn.setStyleSheet("padding: 4px;")
            btn.clicked.connect(lambda _, s=step: self.run_flow_step(s))
            r_flow_lay.addWidget(btn)
        r_flow_lay.addStretch()
        
        # Row 2: View Controls
        r_ctrl_lay = QHBoxLayout()
        
        lbl_view = QLabel("View:"); lbl_view.setStyleSheet("font-weight:bold;")
        r_ctrl_lay.addWidget(lbl_view)
        
        self.chk_inst = QCheckBox("Cells"); self.chk_inst.setChecked(True); self.chk_inst.toggled.connect(self.update_view)
        r_ctrl_lay.addWidget(self.chk_inst)
        
        self.chk_pins = QCheckBox("Pins"); self.chk_pins.setChecked(True); self.chk_pins.toggled.connect(self.update_view)
        r_ctrl_lay.addWidget(self.chk_pins)
        
        self.chk_nets = QCheckBox("Nets"); self.chk_nets.setChecked(False); self.chk_nets.toggled.connect(self.update_view)
            r_ctrl_lay.addWidget(self.chk_nets)
        
        self.chk_heat = QCheckBox("Heatmap"); self.chk_heat.setChecked(False); self.chk_heat.toggled.connect(self.update_view)
        r_ctrl_lay.addWidget(self.chk_heat)
        
        r_ctrl_lay.addStretch()
        
        btn_gui = QPushButton("Native GUI"); btn_gui.clicked.connect(self.launch_native_gui)
        r_ctrl_lay.addWidget(btn_gui)
        
        btn_cfg = QPushButton("⚙ PDK"); btn_cfg.clicked.connect(self.open_pdk_selector)
        r_ctrl_lay.addWidget(btn_cfg)

        r_main_lay.addLayout(r_flow_lay)
        r_main_lay.addLayout(r_ctrl_lay)
        
        self.layout.addWidget(self.ribbon)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.peeker = SiliconPeeker()
        splitter.addWidget(self.peeker)
        
        term_widget = QWidget()
        t_lay = QVBoxLayout(term_widget); t_lay.setContentsMargins(0,0,0,0)
        
        self.term_log = QTextEdit(); self.term_log.setReadOnly(True)
        self.term_log.setStyleSheet("background: #101010; color: #00FF00; font-family: Consolas; border: none;")
        self.term_in = QLineEdit(); self.term_in.setPlaceholderText("Enter TCL command...")
        self.term_in.setStyleSheet("background: #202020; color: white; border-top: 1px solid #444; font-family: Consolas; padding: 5px;")
        self.term_in.returnPressed.connect(self.send_command)
        
        t_lay.addWidget(self.term_log); t_lay.addWidget(self.term_in)
        splitter.addWidget(term_widget)
        splitter.setStretchFactor(0, 3) 
        splitter.setStretchFactor(1, 1) 
        self.layout.addWidget(splitter)

        self.proc = None
        self.pending_init = None
        self.cmd_active = False

    def update_view(self):
        self.peeker.show_insts = self.chk_inst.isChecked()
        self.peeker.show_pins = self.chk_pins.isChecked()
        self.peeker.show_nets = self.chk_nets.isChecked()
        self.peeker.show_heatmap = self.chk_heat.isChecked()
        self.peeker.redraw()

    # ... (Rest of BackendWidget logic: reset_backend, read_stdout, run_flow_step, etc. SAME AS v4.17)
    # Ensure you keep the 'reset_backend', 'read_stdout', 'run_flow_step', 'open_pdk_selector', etc. logic from previous version!
    # I am omitting them here for brevity unless you need the full paste again.
    
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

        if step_name == "1. Init":
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

        cmd_map = {
            "2. Floorplan": f"initialize_floorplan -die_area \"0 0 400 400\" -core_area \"10 10 390 390\" -site unithd; {write_cmd}",
            "3. Tapcells": f"tapcell -distance 14 -tapcell_master sky130_fd_sc_hd__tapvpwrvgnd_1; make_tracks; {write_cmd}",
            "4. IO Pins": f"place_pins -hor_layers met3 -ver_layers met4; {write_cmd}",
            "5. Place": f"global_placement -density 0.6; {write_cmd}",
            "6. CTS": f"clock_tree_synthesis -root_buf sky130_fd_sc_hd__clkbuf_4 -buf_list sky130_fd_sc_hd__clkbuf_4; {write_cmd}",
            "7. Route": f"detailed_route -output_drc reports/drc.rpt; {write_cmd}",
            "8. GDS": "write_gds results/design.gds"
        }
        
        default_cmd = cmd_map.get(step_name, "")
        text, ok = QInputDialog.getText(self, f"Run {step_name}", "Confirm TCL Command:", text=default_cmd)
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

#=====================FRONTEND=====================

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
        elif key == Qt.Key.Key_Left: self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 20)
        elif key == Qt.Key.Key_Right: self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 20)
        elif key == Qt.Key.Key_Up: self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 20)
        elif key == Qt.Key.Key_Down: self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 20)
        else: super().keyPressEvent(event)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor); self.codeEditor = editor
    def sizeHint(self): return QSize(self.codeEditor.lineNumberAreaWidth(), 0)
    def paintEvent(self, event): self.codeEditor.lineNumberAreaPaintEvent(event)

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

# ================= MAIN APPLICATION =================

class SilisIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silis QT v4.11 (Real Physical Viewer)")
        self.resize(1400, 900)
        
        self.cwd = os.getcwd()
        self.current_file = None
        self.pdk_path = ""
        self.schem_engine = "Auto"
        self.term_mode = "SHELL"
        self.queue = queue.Queue()
        
        self.sk_active = False
        self.sk_timer = QTimer()
        self.sk_timer.setSingleShot(True)
        self.sk_timer.timeout.connect(self.reset_sk)
        self.key_map = {"focus_editor":"c", "focus_terminal":"x", "focus_files":"v", "focus_schem":"z", "term_toggle":"s"}

        self.setup_ui()
        self.setup_toolbar()
        
        QApplication.instance().installEventFilter(self)
        
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(50)
        
        self.update_ui_labels()
        self.log_system(f"Silis Ready. CWD: {self.cwd}", "SYS")
        self.check_dependencies()

    def setup_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        self.frontend_tab = QWidget()
        self.build_frontend(self.frontend_tab)
        self.tabs.addTab(self.frontend_tab, "Frontend (Logic)")
        
        self.backend_tab = BackendWidget(self)
        self.tabs.addTab(self.backend_tab, "Backend (Physical)")

    def build_frontend(self, parent):
        main_split = QSplitter(Qt.Orientation.Vertical)
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(main_split)
        
        top_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(top_split); main_split.setStretchFactor(0, 4)
        
        self.explorer = SilisExplorer()
        self.explorer.dirChanged.connect(self.change_directory)
        self.explorer.fileOpened.connect(self.open_file_in_editor)
        self.explorer.doubleClicked.connect(lambda idx: self.on_tree_action(idx))
        exp_layout = QVBoxLayout(); widget_exp = QWidget(); widget_exp.setLayout(exp_layout); exp_layout.setContentsMargins(0,0,0,0)
        self.lbl_explorer = QLabel("Explorer"); self.lbl_explorer.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        exp_layout.addWidget(self.lbl_explorer); exp_layout.addWidget(self.explorer)
        top_split.addWidget(widget_exp)
        
        self.editor = CodeEditor()
        ed_layout = QVBoxLayout(); widget_ed = QWidget(); widget_ed.setLayout(ed_layout); ed_layout.setContentsMargins(0,0,0,0)
        self.lbl_code = QLabel("Code"); self.lbl_code.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        ed_layout.addWidget(self.lbl_code); ed_layout.addWidget(self.editor)
        top_split.addWidget(widget_ed); top_split.setStretchFactor(1, 2)
        
        self.schematic = SilisSchematic()
        sch_layout = QVBoxLayout(); widget_sch = QWidget(); widget_sch.setLayout(sch_layout); sch_layout.setContentsMargins(0,0,0,0)
        self.lbl_schem = QLabel("Schematic"); self.lbl_schem.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        sch_layout.addWidget(self.lbl_schem); sch_layout.addWidget(self.schematic)
        top_split.addWidget(widget_sch); top_split.setStretchFactor(2, 1)
        
        bot_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(bot_split); main_split.setStretchFactor(1, 1)
        
        term_layout = QVBoxLayout(); widget_term = QWidget(); widget_term.setLayout(term_layout); term_layout.setContentsMargins(0,0,0,0)
        self.lbl_term = QLabel("Terminal"); self.lbl_term.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        self.term_log = QTextEdit(); self.term_log.setReadOnly(True); self.term_log.setStyleSheet("background: #1e1e1e; color: #e0e0e0; font-family: Consolas;")
        inp_layout = QHBoxLayout()
        self.mode_btn = QPushButton("[SHELL]"); self.mode_btn.setStyleSheet("background: #0d6efd; color: white; font-weight: bold;")
        self.mode_btn.clicked.connect(self.toggle_term_mode)
        self.term_input = QLineEdit(); self.term_input.setStyleSheet("background: #333; color: white; font-family: Consolas;")
        self.term_input.returnPressed.connect(self.handle_terminal_input)
        inp_layout.addWidget(self.mode_btn); inp_layout.addWidget(self.term_input)
        term_layout.addWidget(self.lbl_term); term_layout.addWidget(self.term_log); term_layout.addLayout(inp_layout)
        bot_split.addWidget(widget_term); bot_split.setStretchFactor(0, 2)
        
        viol_layout = QVBoxLayout(); widget_viol = QWidget(); widget_viol.setLayout(viol_layout); viol_layout.setContentsMargins(0,0,0,0)
        self.lbl_viol = QLabel("Violations"); self.lbl_viol.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        self.viol_log = QTextEdit(); self.viol_log.setReadOnly(True); self.viol_log.setStyleSheet("background: #2d2d2d; color: #ff5555; font-family: Consolas;")
        viol_layout.addWidget(self.lbl_viol); viol_layout.addWidget(self.viol_log)
        bot_split.addWidget(widget_viol); bot_split.setStretchFactor(1, 1)

    def setup_toolbar(self):
        self.tb = QToolBar(); self.addToolBar(self.tb)
        act_new = QAction("New", self); act_new.setShortcut("Ctrl+N"); act_new.triggered.connect(self.new_file); self.tb.addAction(act_new)
        act_save = QAction("Save", self); act_save.setShortcut("Ctrl+S"); act_save.triggered.connect(self.save_file); self.tb.addAction(act_save)
        self.tb.addSeparator()
        self.tb.addAction("F1 Compile", self.run_simulation)
        self.tb.addAction("F2 Waves", self.open_waves)
        self.tb.addAction("F3 Schem", self.generate_schematic)
        self.tb.addAction("F4 Synth", self.run_synthesis_flow)
        self.tb.addSeparator()
        self.btn_err = QPushButton("⚠️ Errors"); self.btn_err.setEnabled(False); self.btn_err.setStyleSheet("color:red; font-weight:bold")
        self.btn_err.clicked.connect(self.load_violation_log)
        self.tb.addWidget(self.btn_err)
        empty = QWidget(); empty.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tb.addWidget(empty)
        self.tb.addAction("⚙ Settings", self.open_settings)

    # ================= LOGIC & UTILS =================
    
    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_QuoteLeft:
                self.sk_active = True; self.tb.setStyleSheet("background-color: #00FFFF;")
                self.sk_timer.start(1000); return True
            if self.sk_active:
                txt = event.text().lower()
                if txt == self.key_map["focus_editor"]: self.editor.setFocus()
                elif txt == self.key_map["focus_terminal"]: self.term_input.setFocus()
                elif txt == self.key_map["focus_files"]: self.explorer.setFocus()
                elif txt == self.key_map["focus_schem"]: self.schematic.setFocus()
                elif txt == self.key_map["term_toggle"]: self.toggle_term_mode()
                self.reset_sk(); return True
        return super().eventFilter(source, event)

    def reset_sk(self):
        self.sk_active = False; self.tb.setStyleSheet("")

    def change_directory(self, path):
        if os.path.exists(path):
            os.chdir(path); self.cwd = os.getcwd(); self.explorer.set_cwd(self.cwd)
            self.log_system(f"CD -> {self.cwd}", "SYS")

    def on_tree_action(self, index):
        path = self.explorer.fs_model.filePath(index)
        if self.explorer.fs_model.isDir(index): self.change_directory(path)
        else: self.open_file_in_editor(path)

    def handle_terminal_input(self):
        cmd = self.term_input.text().strip(); self.term_input.clear()
        if not cmd: return
        self.log_system(f"$ {cmd}", "INPUT")
        if cmd.startswith("cd "):
            target = cmd[3:].strip()
            if target == "..": target = os.path.dirname(self.cwd)
            elif target == "~": target = os.path.expanduser("~")
            else: target = os.path.join(self.cwd, target)
            self.change_directory(target); return

        def run():
            try:
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=self.cwd, bufsize=1)
                for line in iter(proc.stdout.readline, ''): self.queue.put(line.strip())
                proc.wait()
            except Exception as e: self.queue.put(f"[EXC] {e}")
        threading.Thread(target=run, daemon=True).start()

    def toggle_term_mode(self):
        self.term_mode = "SIM" if self.term_mode == "SHELL" else "SHELL"
        self.mode_btn.setText(f"[{self.term_mode}]")

    def log_system(self, msg, tag="SYS"):
        color = "#00FFFF"
        if "ERR" in tag or "FAIL" in msg: color = "#FF5555"
        elif "WARN" in tag: color = "#F1FA8C"
        elif "SUCCESS" in tag: color = "#50FA7B"
        elif "INPUT" in tag: color = "#FFFFFF"
        self.term_log.append(f'<span style="color:{color};">[{tag}] {msg}</span>')
        self.term_log.verticalScrollBar().setValue(self.term_log.verticalScrollBar().maximum())

    def process_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            if isinstance(msg, tuple):
                if msg[0] == "HARVEST": self.harvest_logs(msg[1])
            elif msg == "PARSE": self.parse_summary()
            else: self.log_system(str(msg).strip(), "SYS")

    def get_context(self):
        content = self.editor.toPlainText()
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
        for d in ["source", "netlist", "reports"]: os.makedirs(os.path.join(root, d), exist_ok=True)
        
        # Surgical Move
        files_to_organize = [f"{base}.v", f"tb_{base}.v", f"{base}_tb.v", f"test_{base}.v", f"{base}.sv"]
        search_dirs = list(set([os.path.abspath(self.cwd), root]))
        for fname in files_to_organize:
            if os.path.exists(os.path.join(src_dir, fname)): continue
            found_src = None
            for s_dir in search_dirs:
                possible = os.path.join(s_dir, fname)
                if os.path.exists(possible): found_src = possible; break
            if found_src:
                dest = os.path.join(src_dir, fname)
                try:
                    if self.current_file and os.path.abspath(self.current_file) == found_src:
                        shutil.move(found_src, dest); self.current_file = dest; self.setWindowTitle(f"Silis - {fname} (Moved)")
                        self.log_system(f"Moved active {fname} -> source/", "SYS")
                    else:
                        shutil.move(found_src, dest); self.log_system(f"Moved {fname} -> source/", "SYS")
                except Exception as e: self.log_system(f"Move Err: {e}", "ERROR")
        return root

    # --- SIMULATION (SV + V Support) ---
    def run_simulation(self):
        if self.current_file: self.save_file()
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        
        src_v = glob.glob(os.path.join(root, "source", "*.v"))
        src_sv = glob.glob(os.path.join(root, "source", "*.sv"))
        all_src = src_v + src_sv
        if not all_src: self.log_system("No source files found!", "ERROR"); return

        out = f"{base}.out"
        cmd = ["iverilog", "-g2012", "-o", out] + all_src
        
        def task():
            try:
                self.queue.put("[SYS] Compiling (SV Enabled)...")
                res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
                if res.returncode != 0: 
                    self.queue.put(f"[ERROR] Compile:\n{res.stderr}"); return
                self.queue.put("[SYS] Simulating...")
                proc = subprocess.Popen(["vvp", out], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(proc.stdout.readline, ''): self.queue.put(line.strip())
                proc.wait()
                self.queue.put("[SYS] Simulation Finished.")
            except Exception as e: self.queue.put(f"[ERROR] {e}")
        threading.Thread(target=task, daemon=True).start()

    # --- SYNTHESIS (SV Support) ---
    def run_synthesis_flow(self):
        if not self.pdk_path: return QMessageBox.warning(self, "Err", "Set PDK Path!")
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        
        v_net = f"netlist/{base}_netlist.v"
        
        src_v = glob.glob(os.path.join(root, "source", "*.v"))
        src_sv = glob.glob(os.path.join(root, "source", "*.sv"))
        src_v = [s for s in src_v if "tb_" not in s]
        src_sv = [s for s in src_sv if "tb_" not in s]
        
        read_cmd = ""
        if src_v: read_cmd += f"read_verilog {' '.join(src_v)}\n"
        if src_sv: read_cmd += f"read_verilog -sv {' '.join(src_sv)}\n"
        
        ys = f"read_liberty -lib {self.pdk_path}\n{read_cmd}\nsynth -top {base}\ndfflibmap -liberty {self.pdk_path}\nabc -liberty {self.pdk_path}\ntee -o reports/area.rpt stat -liberty {self.pdk_path} -json\nwrite_verilog -noattr {v_net}"
        with open(os.path.join(root, "synth.ys"), 'w') as f: f.write(ys)
        
        sdc = os.path.join(root, "netlist", f"{base}.sdc")
        if not os.path.exists(sdc):
            with open(sdc, 'w') as f: f.write(f"# SDC for {base}\n")
        
        tcl = f"read_liberty {self.pdk_path}\nread_verilog {v_net}\nlink_design {base}\nread_sdc netlist/{base}.sdc\nreport_checks\nreport_power\nexit"
        with open(os.path.join(root, "sta.tcl"), 'w') as f: f.write(tcl)

        def task():
            try:
                self.queue.put("[SYS] Synthesizing (SV Mode)...")
                p1 = subprocess.Popen(f"yosys synth.ys | tee reports/synthesis.log", shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(p1.stdout.readline, ''): self.queue.put(line.strip())
                p1.wait()
                self.queue.put("[SYS] Timing Analysis...")
                p2 = subprocess.Popen(f"sta sta.tcl < /dev/null | tee reports/sta.log", shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(p2.stdout.readline, ''): self.queue.put(line.strip())
                p2.wait()
                self.queue.put(("HARVEST", root)); self.queue.put("PARSE")
            except Exception as e: self.queue.put(f"[ERROR] {e}")
        threading.Thread(target=task, daemon=True).start()

    def harvest_logs(self, root):
        self.viol_log.clear()
        found = False
        for log in ["reports/synthesis.log", "reports/sta.log"]:
            p = os.path.join(root, log)
            if os.path.exists(p):
                self.viol_log.append(f"--- {log} ---")
                with open(p) as f:
                    for l in f:
                        if any(x in l for x in ["Error", "Warning"]):
                            self.viol_log.append(l.strip()); found = True
        self.btn_err.setEnabled(found)
        if found: self.log_system("Violations Found!", "WARN")

    def parse_summary(self):
        self.log_system("Flow Complete. Check Reports.", "SUCCESS")

    def open_waves(self):
        vcds = glob.glob(os.path.join(self.cwd, "*.vcd"))
        if vcds: subprocess.Popen(["gtkwave", max(vcds, key=os.path.getctime)], cwd=self.cwd)

    # --- SCHEMATIC GENERATION (WORKER) ---
    def generate_schematic(self):
        if self.current_file: self.save_file()
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        
        src_v = glob.glob(os.path.join(root, "source", "*.v"))
        src_sv = glob.glob(os.path.join(root, "source", "*.sv"))
        src_v = [s for s in src_v if not ("tb_" in s or "_tb" in s or "test_" in s)]
        src_sv = [s for s in src_sv if not ("tb_" in s or "_tb" in s or "test_" in s)]
        
        if not (src_v or src_sv): self.log_system("No design files found.", "ERROR"); return

        self.worker = SchematicWorker(root, base, self.schem_engine, src_v + src_sv)
        self.worker.log.connect(self.log_system)
        self.worker.finished.connect(self.schematic.load_schematic)
        self.worker.start()

        # ================= MISSING COMMON METHODS =================
    
    def new_file(self): 
        self.current_file = None
        self.editor.clear()
        self.setWindowTitle("Silis - Untitled")

    def save_file(self):
        if not self.current_file:
            f, _ = QFileDialog.getSaveFileName(self, "Save", self.cwd)
            if f: self.current_file = f
        if self.current_file:
            with open(self.current_file, 'w') as f: f.write(self.editor.toPlainText())
            self.log_system(f"Saved {os.path.basename(self.current_file)}", "SUCCESS")
            self.setWindowTitle(f"Silis - {os.path.basename(self.current_file)}")
    
    def open_file_in_editor(self, path):
        if not os.path.exists(path): return
        with open(path) as f: self.editor.setPlainText(f.read())
        self.current_file = path
        self.setWindowTitle(f"Silis - {os.path.basename(path)}")

    def open_settings(self):
        d = QDialog(self); l = QFormLayout(d)
        e_pdk = QLineEdit(self.pdk_path)
        btn = QPushButton("Browse"); btn.clicked.connect(lambda: e_pdk.setText(QFileDialog.getOpenFileName()[0]))
        l.addRow("PDK:", e_pdk); l.addRow(btn)
        combo = QComboBox(); combo.addItems(["Auto", "Graphviz", "NetlistSVG"]); combo.setCurrentText(self.schem_engine)
        l.addRow("Engine:", combo)
        sk_ed = {}
        for k, v in self.key_map.items():
            sk_ed[k] = QLineEdit(v); l.addRow(k, sk_ed[k])
        def save():
            self.pdk_path = e_pdk.text(); self.schem_engine = combo.currentText()
            for k, w in sk_ed.items(): self.key_map[k] = w.text()
            self.update_ui_labels(); d.accept()
        btn_s = QPushButton("Save"); btn_s.clicked.connect(save); l.addRow(btn_s)
        d.exec()

    def update_ui_labels(self):
        self.lbl_explorer.setText(f"Explorer (`+{self.key_map['focus_files']})")
        self.lbl_code.setText(f"Code (`+{self.key_map['focus_editor']})")
        self.lbl_schem.setText(f"Schematic (`+{self.key_map['focus_schem']})")
        self.lbl_term.setText(f"Terminal (`+{self.key_map['focus_terminal']})")
        
    def check_dependencies(self):
        if not shutil.which("sta"): self.log_system("OpenSTA not found!", "ERR")

    def load_violation_log(self): 
        self.harvest_logs(self.get_proj_root(self.get_context()[1] or "design"))

# ================= WORKER CLASS =================
class SchematicWorker(QThread):
    finished = pyqtSignal(str); log = pyqtSignal(str, str)
    def __init__(self, root, base, engine, src_files):
        super().__init__(); self.root=root; self.base=base; self.engine=engine; self.src_files=src_files
    def run(self):
        read_cmd = "".join([f"read_verilog -sv {s}; " if s.endswith(".sv") else f"read_verilog {s}; " for s in self.src_files])
        HIER_CMD = f"hierarchy -check -top {self.base}; proc; clean"
        use_netlist = (self.engine == "NetlistSVG") or (self.engine == "Auto" and shutil.which("netlistsvg"))
        svg_path = os.path.join(self.root, f"{self.base}.svg")
        
        if use_netlist:
            cmd_json = f"yosys -p '{read_cmd} {HIER_CMD}; write_json {self.base}.json'"
            subprocess.run(cmd_json, shell=True, cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(os.path.join(self.root, f"{self.base}.json")):
                env = os.environ.copy(); env["NODE_OPTIONS"] = "--max-old-space-size=4096"
                try:
                    subprocess.run(f"netlistsvg {self.base}.json -o {self.base}.svg", shell=True, cwd=self.root, env=env)
                    if os.path.exists(svg_path): self.patch_svg(svg_path); self.finished.emit(svg_path); return
                except: pass
        
        cmd_dot = f"yosys -p '{read_cmd} {HIER_CMD}; show -format dot -prefix {self.base}'"
        subprocess.run(cmd_dot, shell=True, cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        dot_path = os.path.join(self.root, f"{self.base}.dot")
        if os.path.exists(dot_path):
            subprocess.run(f"dot -Tsvg {dot_path} -o {self.base}.svg", shell=True, cwd=self.root)
            self.finished.emit(svg_path)
        else: self.log.emit("Schematic Gen Failed", "ERROR")

    def patch_svg(self, path):
        try:
            ET.register_namespace('', "http://www.w3.org/2000/svg"); tree = ET.parse(path); root = tree.getroot()
            for e in root.iter():
                if 'stroke' in e.attrib: e.attrib['stroke']='black'
                if 'fill' in e.attrib and e.tag.endswith('text'): e.attrib['fill']='black'
            tree.write(path)
        except: pass

if __name__ == "__main__":
    QImageReader.setAllocationLimit(0)
    app = QApplication(sys.argv)
    w = SilisIDE()
    w.show()
    sys.exit(app.exec())