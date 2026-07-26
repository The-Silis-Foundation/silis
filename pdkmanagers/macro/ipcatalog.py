import os
import re
import json
import glob
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from backendflow.floorplanner.floorplanner import InteractiveGraphicsView, HoverTextItem

class MacroPickerWidget(QDialog):
    def __init__(self, pdk_cfg, pdk_mgr, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Macro IP Catalog (Shopping Cart)")
        self.resize(1000, 700)
        self.pdk_cfg = pdk_cfg
        self.pdk_mgr = pdk_mgr
        self.macros = {} 
        self.selected_macro_lef = None
        self.pins_data = {}

        self.scan_macros()

        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search Macros...")
        self.search_box.textChanged.connect(self.filter_macros)
        left_layout.addWidget(self.search_box)
        
        self.list_widget = QListWidget()
        self.list_widget.addItems(list(self.macros.keys()))
        self.list_widget.currentItemChanged.connect(self.on_macro_selected)
        left_layout.addWidget(self.list_widget)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.view = InteractiveGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        right_layout.addWidget(QLabel("Macro Pinout Preview:"))
        right_layout.addWidget(self.view, stretch=2)

        right_layout.addWidget(QLabel("Verilog Stub (Black-Box):"))
        self.stub_editor = QTextEdit()
        self.stub_editor.setFontFamily("monospace")
        self.stub_editor.setReadOnly(True)
        right_layout.addWidget(self.stub_editor, stretch=1)
        
        ctrl_layout = QHBoxLayout()
        self.cb_auto_stub = QCheckBox("Auto-Generate Verilog Stub on Checkout")
        self.cb_auto_stub.setChecked(True)
        ctrl_layout.addWidget(self.cb_auto_stub)
        
        btn_add = QPushButton("Add to Project (Checkout)")
        btn_add.setStyleSheet("background: #0078D7; color: white; font-weight: bold;")
        btn_add.clicked.connect(self.accept)
        ctrl_layout.addWidget(btn_add)
        
        right_layout.addLayout(ctrl_layout)
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 700])

    def scan_macros(self):
        if not self.pdk_cfg: return
        lib_path = self.pdk_cfg.get('lib', '')
        if "libs.ref" not in lib_path: return
        try:
            volare_base = lib_path.split("libs.ref")[0]
            stdcell_name = lib_path.split("libs.ref/")[1].split("/")[0]
            search_path = os.path.join(volare_base, "libs.ref", "*", "lef", "*.lef")
            for lef in glob.glob(search_path):
                if stdcell_name not in lef:
                    name = os.path.basename(lef).replace('.lef', '')
                    self.macros[name] = lef
        except Exception:
            pass

    def filter_macros(self, text):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def on_macro_selected(self, item, prev):
        if not item: return
        name = item.text()
        self.selected_macro_lef = self.macros.get(name)
        self.parse_lef(self.selected_macro_lef, name)
        self.draw_symbol(name)
        self.generate_stub(name)

    def parse_lef(self, lef_path, macro_name):
        self.pins_data = {'input': [], 'output': [], 'inout': [], 'power': [], 'ground': []}
        if not lef_path or not os.path.exists(lef_path): return
        with open(lef_path, 'r') as f:
            content = f.read()
        
        pin_blocks = re.findall(r'^\s*PIN\s+(\S+)(.*?)(?:^\s*END\s+\1)', content, re.DOTALL | re.MULTILINE)
        
        for pin_name, pin_body in pin_blocks:
            dir_match = re.search(r'DIRECTION\s+(\S+)\s*;', pin_body)
            use_match = re.search(r'USE\s+(\S+)\s*;', pin_body)
            
            direction = dir_match.group(1).lower() if dir_match else "input"
            use = use_match.group(1).lower() if use_match else "signal"
            
            if use == "power":
                self.pins_data['power'].append(pin_name)
            elif use == "ground":
                self.pins_data['ground'].append(pin_name)
            elif direction == "output":
                self.pins_data['output'].append(pin_name)
            elif direction == "inout":
                self.pins_data['inout'].append(pin_name)
            else:
                self.pins_data['input'].append(pin_name)

    def draw_symbol(self, name):
        self.scene.clear()
        self.view.setBackgroundBrush(QBrush(QColor("#1E1E1E")))
        
        in_pins = self.pins_data['input']
        out_pins = self.pins_data['output'] + self.pins_data['inout']
        pwr_pins = self.pins_data['power'] + self.pins_data['ground']
        
        max_edge = max(len(in_pins), len(out_pins))
        spacing = max(6, min(20, 800 // max(1, max_edge)))
        font_sz = max(5, min(10, spacing - 2))
        
        h = max_edge * spacing + 40
        w = max(150, len(pwr_pins) * 30 + 40)
        
        box = self.scene.addRect(0, 0, w, h, QPen(QColor("#4A5568"), 2), QBrush(QColor("#2D323A")))
        box.setZValue(-1)
        
        t = self.scene.addText(name)
        f = t.font()
        f.setPointSize(12)
        f.setBold(True)
        t.setFont(f)
        t.setDefaultTextColor(QColor("#E2E8F0"))
        t.setPos(w/2 - t.boundingRect().width()/2, h/2 - t.boundingRect().height()/2)
        
        y = 20
        for p in in_pins:
            self.scene.addLine(-15, y, 0, y, QPen(QColor("#A0AEC0")))
            pt = HoverTextItem(p, "#E2E8F0")
            font = pt.font(); font.setPointSize(font_sz); pt.setFont(font)
            self.scene.addItem(pt)
            pt.setPos(-pt.boundingRect().width() - 15, y - pt.boundingRect().height()/2)
            y += spacing
            
        y = 20
        for p in out_pins:
            self.scene.addLine(w, y, w+15, y, QPen(QColor("#A0AEC0")))
            pt = HoverTextItem(p, "#E2E8F0")
            font = pt.font(); font.setPointSize(font_sz); pt.setFont(font)
            self.scene.addItem(pt)
            pt.setPos(w + 15, y - pt.boundingRect().height()/2)
            y += spacing
            
        x = 20
        for p in pwr_pins:
            self.scene.addLine(x, -15, x, 0, QPen(QColor("#A0AEC0")))
            pt = HoverTextItem(p, "#E2E8F0")
            font = pt.font(); font.setPointSize(font_sz); pt.setFont(font)
            self.scene.addItem(pt)
            pt.setPos(x - pt.boundingRect().width()/2, -15 - pt.boundingRect().height())
            x += 30
            
        rect = self.scene.itemsBoundingRect()
        rect.adjust(-50, -50, 50, 50)
        self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def generate_stub(self, name):
        def group_buses(pins):
            scalars = []
            buses = {}
            for p in pins:
                m = re.match(r'^(.+)\[(\d+)\]$', p)
                if m:
                    bname, idx = m.group(1), int(m.group(2))
                    if bname not in buses: buses[bname] = []
                    buses[bname].append(idx)
                else:
                    scalars.append(p)
            
            res = []
            for bname, idxs in buses.items():
                res.append(f"[{max(idxs)}:{min(idxs)}] {bname}")
            return scalars + res

        stub = f"module {name} (\n"
        ports = []
        
        power_ports = group_buses(self.pins_data['power'] + self.pins_data['ground'])
        if power_ports:
            stub += "`ifdef USE_POWER_PINS\n"
            for p in power_ports:
                stub += f"    inout {p},\n"
            stub += "`endif\n"
            
        for p in group_buses(self.pins_data['input']):
            ports.append(f"    input {p}")
        for p in group_buses(self.pins_data['output']):
            ports.append(f"    output {p}")
        for p in group_buses(self.pins_data['inout']):
            ports.append(f"    inout {p}")
            
        stub += ",\n".join(ports)
        stub += "\n);\n"
        stub += "    // Black-box stub auto-generated by Silis Shopping Cart\n"
        stub += f"endmodule\n"
        
        self.stub_editor.setPlainText(stub)

    def get_selected_macro(self):
        item = self.list_widget.currentItem()
        if not item: return None, None, False
        return item.text(), self.stub_editor.toPlainText(), self.cb_auto_stub.isChecked()
