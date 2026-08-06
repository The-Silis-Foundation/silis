import os
import sys
import json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *


class SSAForge:
    """
    Silis Standard Aliases (SSA) - The Forge
    Decouples the IDE from specific PDK naming conventions.
    """
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
        """Loads aliases from disk. Checks CWD first, then the script's own directory."""
        paths_to_check = [os.path.abspath(json_filename)]
        if hasattr(sys, 'argv') and sys.argv:
            script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            paths_to_check.append(os.path.join(script_dir, json_filename))
        loaded = False
        for path in paths_to_check:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
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
        pdk_name = str(pdk_name).lower() if pdk_name else ""
        lib_path = str(lib_path).lower() if lib_path else ""
        for key in SSAForge.ALIASES:
            key_lower = key.lower()
            if key_lower == pdk_name: return key
            if key_lower in pdk_name: return key
            if lib_path and key_lower in os.path.basename(lib_path):
                return key
        if "sky130" in pdk_name or "sky130" in lib_path:
            return "sky130_fd_sc_hd"
        return SSAForge.DEFAULT_PDK

    @staticmethod
    def get(pdk_name, key, lib_path=None):
        family = SSAForge.resolve_pdk_key(pdk_name, lib_path)
        val = SSAForge.ALIASES.get(family, {}).get(key, "")
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
        self.crawl_volare()

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
        self.configs = [c for c in self.configs if c['name'] != config_data['name']]
        self.configs.insert(0, config_data)
        self.save_cache()

    def delete_config(self, name):
        self.configs = [c for c in self.configs if c['name'] != name]
        self.save_cache()

    def add_manual_config(self, name, tlef, lef, lib, gds):
        entry = {
            "name": name,
            "tlef": tlef,
            "lef": lef,
            "lib": lib,
            "gds": gds,
            "corner": "Manual"
        }
        self.configs = [c for c in self.configs if c['name'] != name]
        self.configs.insert(0, entry)
        self.save_cache()

    def crawl_volare(self):
        import glob
        volare_base = os.path.expanduser("~/.volare/volare/sky130/versions")
        if not os.path.exists(volare_base):
            return False
        
        versions = os.listdir(volare_base)
        if not versions:
            return False
            
        latest_version = versions[-1] # Simplistic, just pick the last one
        pdk_path = os.path.join(volare_base, latest_version, "sky130A")
        
        # Standard paths for sky130_fd_sc_hd
        tlef = glob.glob(os.path.join(pdk_path, "libs.ref", "sky130_fd_sc_hd", "techlef", "*.tlef"))
        lef = glob.glob(os.path.join(pdk_path, "libs.ref", "sky130_fd_sc_hd", "lef", "*.lef"))
        gds = glob.glob(os.path.join(pdk_path, "libs.ref", "sky130_fd_sc_hd", "gds", "*.gds"))
        tech = glob.glob(os.path.join(pdk_path, "libs.tech", "magic", "*.tech"))
        
        libs = glob.glob(os.path.join(pdk_path, "libs.ref", "sky130_fd_sc_hd", "lib", "*.lib"))
        
        corners = {}
        for l in libs:
            bn = os.path.basename(l).replace('.lib', '')
            if "ccsnoise" in bn: continue # Skip ccsnoise for general timing
            parts = bn.split("__")
            if len(parts) > 1:
                corners[parts[1]] = l
                
        # Default lib for 'lib' key to keep old code working
        default_lib = ""
        for k in ["tt_025C_1v80", "tt_100C_1v80"]:
            if k in corners:
                default_lib = corners[k]
                break
        if not default_lib and libs:
            default_lib = libs[0]
            
        # RC Corners
        rc_corners = {"nom": "default"}
                
        config = {
            "name": f"Volare_sky130A_{latest_version[:8]}",
            "tlef": tlef[0] if tlef else "",
            "lef": lef[0] if lef else "",
            "gds": gds[0] if gds else "",
            "tech": tech[0] if tech else "",
            "lib": default_lib,
            "corners": corners,
            "rc_corners": rc_corners
        }
        
        self.update_config(config)
        return True


class ManualPDKDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("PDK Configuration Editor")
        self.resize(800, 500)
        self.layout = QFormLayout(self)

        self.e_name = QLineEdit(config['name'] if config else "Custom PDK")
        self.layout.addRow("<b>Config Name:</b>", self.e_name)

        self.e_tlef = QLineEdit(config.get('tlef', '') if config else '')
        b_tlef = QPushButton("Browse Tech LEF (.tlef)"); b_tlef.clicked.connect(lambda: self.browse(self.e_tlef, "Tech LEF (*.tlef *.lef)"))
        self.layout.addRow(b_tlef, self.e_tlef)

        self.e_lef = QLineEdit(config.get('lef', '') if config else '')
        b_lef = QPushButton("Browse Macro LEF (.lef)"); b_lef.clicked.connect(lambda: self.browse(self.e_lef, "Macro LEF (*.lef)"))
        self.layout.addRow(b_lef, self.e_lef)

        self.e_lib = QLineEdit(config.get('lib', '') if config else '')
        b_lib = QPushButton("Browse Timing (.lib)"); b_lib.clicked.connect(lambda: self.browse(self.e_lib, "Liberty (*.lib)"))
        self.layout.addRow(b_lib, self.e_lib)

        self.e_gds = QLineEdit(config.get('gds', '') if config else '')
        b_gds = QPushButton("Browse Std Cell GDS (.gds)"); b_gds.clicked.connect(lambda: self.browse(self.e_gds, "GDSII (*.gds)"))
        self.layout.addRow(b_gds, self.e_gds)

        self.e_tech = QLineEdit(config.get('tech', '') if config else '')
        b_tech = QPushButton("Browse Magic Tech (.tech)"); b_tech.clicked.connect(lambda: self.browse(self.e_tech, "Magic Tech (*.tech)"))
        self.layout.addRow(b_tech, self.e_tech)

        btn_save = QPushButton("Save Configuration")
        btn_save.setStyleSheet("background: #00AA00; color: white; font-weight: bold; padding: 12px;")
        btn_save.clicked.connect(self.validate_and_accept)
        self.layout.addRow(btn_save)

    def browse(self, line_edit, filter_str):
        f, _ = QFileDialog.getOpenFileName(self, "Select File", "", filter_str)
        if f: line_edit.setText(f)

    def validate_and_accept(self):
        if not all([self.e_tlef.text(), self.e_lef.text(), self.e_lib.text(), self.e_gds.text(), self.e_tech.text()]):
            QMessageBox.warning(self, "Incomplete", "All 5 files (TLEF, LEF, LIB, GDS, TECH) are required for the full flow.")
            return
        self.accept()

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

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search configs...")
        self.search.textChanged.connect(self.populate)
        layout.addWidget(self.search)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Name", "Tech LEF", "Macro LEF", "Lib", "GDS", "Magic Tech"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(self.accept_selection)
        layout.addWidget(self.table)

        btn_lay = QHBoxLayout()
        btn_add = QPushButton("➕ Add New")
        btn_add.setStyleSheet("color: #2da44e; font-weight: bold;")
        btn_add.clicked.connect(self.trigger_add)
        btn_auto = QPushButton("🚀 Auto-Crawl Volare")
        btn_auto.setStyleSheet("color: #00bcd4; font-weight: bold;")
        btn_auto.clicked.connect(self.trigger_crawl)
        btn_edit = QPushButton("✏️ Edit Selected")
        btn_edit.clicked.connect(self.trigger_edit)
        btn_del = QPushButton("🗑️ Delete Selected")
        btn_del.setStyleSheet("color: #cf222e;")
        btn_del.clicked.connect(self.trigger_delete)
        self.btn_ok = QPushButton("Select (Enter)")
        self.btn_ok.clicked.connect(self.accept_selection)
        self.btn_ok.setDefault(True)
        btn_lay.addWidget(btn_add)
        btn_lay.addWidget(btn_auto)
        btn_lay.addWidget(btn_edit)
        btn_lay.addWidget(btn_del)
        btn_lay.addStretch()
        btn_lay.addWidget(self.btn_ok)
        layout.addLayout(btn_lay)

        self.populate()
        self.table.setFocus()

    def trigger_crawl(self):
        if self.mgr.crawl_volare():
            QMessageBox.information(self, "Success", "Crawled Volare PDK successfully!")
            self.populate()
        else:
            QMessageBox.warning(self, "Error", "Could not find Volare PDK at ~/.volare/volare/sky130/versions")

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
        res = QMessageBox.question(self, "Delete", f"Delete config '{cfg['name']}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
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
        else:
            super().keyPressEvent(event)
