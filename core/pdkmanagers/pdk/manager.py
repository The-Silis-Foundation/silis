import os
import sys
import json
import glob
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QFileDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QLabel, QGroupBox, QComboBox, QCheckBox, QScrollArea, QWidget,
    QHeaderView, QAbstractItemView, QFrame, QPlainTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush


class SSAForge:
    """
    Silis Standard Aliases (SSA) - The Forge
    Decouples the IDE from specific PDK naming conventions.
    """
    DEFAULT_PDK = "sky130_fd_sc_hd"
    ALIASES = {
        "sky130_fd_sc_hd": {
            "desc": "SkyWater 130nm High Density",
            "site": "unithd",
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
        },
        "gf180mcu_fd_sc_mcu9t5v0": {
            "desc": "GlobalFoundries 180nm MCU 9-Track 5V",
            "site": "GF018hv5v_green_sc9",
            "tap_cell": "gf180mcu_fd_sc_mcu9t5v0__filltie",
            "tap_dist": 20,
            "cts_root": "gf180mcu_fd_sc_mcu9t5v0__clkbuf_16",
            "cts_leaf": "gf180mcu_fd_sc_mcu9t5v0__clkbuf_4",
            "fill": "gf180mcu_fd_sc_mcu9t5v0__fill_*",
            "tie_hi": "gf180mcu_fd_sc_mcu9t5v0__tieh",
            "tie_lo": "gf180mcu_fd_sc_mcu9t5v0__tiel",
            "min_layer": "Metal1",
            "max_layer": "Metal5",
            "driver": "gf180mcu_fd_sc_mcu9t5v0__buf_4"
        },
        "gf180mcu_fd_sc_mcu7t5v0": {
            "desc": "GlobalFoundries 180nm MCU 7-Track 5V",
            "site": "GF018hv5v_green_sc7",
            "tap_cell": "gf180mcu_fd_sc_mcu7t5v0__filltie",
            "tap_dist": 20,
            "cts_root": "gf180mcu_fd_sc_mcu7t5v0__clkbuf_16",
            "cts_leaf": "gf180mcu_fd_sc_mcu7t5v0__clkbuf_4",
            "fill": "gf180mcu_fd_sc_mcu7t5v0__fill_*",
            "tie_hi": "gf180mcu_fd_sc_mcu7t5v0__tieh",
            "tie_lo": "gf180mcu_fd_sc_mcu7t5v0__tiel",
            "min_layer": "Metal1",
            "max_layer": "Metal5",
            "driver": "gf180mcu_fd_sc_mcu7t5v0__buf_4"
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
        if "gf180" in pdk_name or "gf180" in lib_path:
            if "7t" in pdk_name or "7t" in lib_path:
                return "gf180mcu_fd_sc_mcu7t5v0"
            return "gf180mcu_fd_sc_mcu9t5v0"
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
    """
    Manages PDK discoveries, hierarchical master catalog resolution,
    and multi-corner PVT characterization settings.
    """
    def __init__(self):
        self.cache_file = os.path.expanduser("~/.silis_pdk_cache.json")
        self.configs = []
        self.catalog = {}
        self.master_catalog_path = None
        
        # Priority 1: Fast load from master JSON catalog (zero filesystem traversal)
        loaded = self.load_master_catalog()
        if not loaded or not self.configs:
            self.load_cache()
            self.crawl_volare()

    def get_tap_cmd(self, pdk_name, lib_path=None):
        return SSAForge.get_tap_cmd(pdk_name, lib_path)

    def get_cts_cmd(self, pdk_name, lib_path=None):
        return SSAForge.get_cts_cmd(pdk_name, lib_path)

    def load_master_catalog(self):
        """Loads PDK master JSON catalog mapping relative paths to absolute repo paths."""
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        master_path = os.path.join(repo_root, "third-party", "pdks", "pdk_master.json")
        if not os.path.exists(master_path):
            return False

        try:
            with open(master_path, 'r') as f:
                self.catalog = json.load(f)
            self.master_catalog_path = master_path
        except Exception as e:
            print(f"[PDKManager] Error loading master catalog: {e}")
            return False

        families = self.catalog.get("families", {})
        parsed_configs = []

        for fam_key, fam_info in families.items():
            fam_disp = fam_info.get("display_name", fam_key)
            variants = fam_info.get("variants", {})
            for var_key, var_info in variants.items():
                var_name = var_info.get("name", var_key)

                tlef = var_info.get("tech_lef", "")
                if tlef and not os.path.isabs(tlef):
                    tlef = os.path.normpath(os.path.join(repo_root, tlef))

                lef = var_info.get("std_cell_lef", "")
                if lef and not os.path.isabs(lef):
                    lef = os.path.normpath(os.path.join(repo_root, lef))

                gds = var_info.get("gds", "")
                if gds and not os.path.isabs(gds):
                    gds = os.path.normpath(os.path.join(repo_root, gds))

                tech = var_info.get("magic_tech", "")
                if tech and not os.path.isabs(tech):
                    tech = os.path.normpath(os.path.join(repo_root, tech))

                corner_groups = var_info.get("corners", {})
                all_corners = {}
                resolved_corner_groups = {}
                default_corner_name = var_info.get("default_corner", "")
                default_lib = ""

                for grp_key, grp_corners in corner_groups.items():
                    resolved_corner_groups[grp_key] = {}
                    for c_name, c_data in grp_corners.items():
                        c_lib = c_data.get("lib", "")
                        if c_lib and not os.path.isabs(c_lib):
                            c_lib = os.path.normpath(os.path.join(repo_root, c_lib))
                        all_corners[c_name] = c_lib
                        resolved_corner_groups[grp_key][c_name] = {
                            "lib": c_lib,
                            "temp": c_data.get("temp", 25),
                            "volt": c_data.get("volt", 1.8)
                        }
                        if c_name == default_corner_name or not default_lib:
                            default_lib = c_lib

                ss_corners = resolved_corner_groups.get("ss", {})
                ff_corners = resolved_corner_groups.get("ff", {})
                tt_corners = resolved_corner_groups.get("tt", {})

                ss_def_key = "ss_100C_1v60" if "ss_100C_1v60" in ss_corners else (list(ss_corners.keys())[0] if ss_corners else default_corner_name)
                ff_def_key = "ff_n40C_1v95" if "ff_n40C_1v95" in ff_corners else (list(ff_corners.keys())[0] if ff_corners else default_corner_name)
                tt_def_key = default_corner_name if default_corner_name in tt_corners else (list(tt_corners.keys())[0] if tt_corners else default_corner_name)

                ss_lib = all_corners.get(ss_def_key, default_lib)
                ff_lib = all_corners.get(ff_def_key, default_lib)
                tt_lib = all_corners.get(tt_def_key, default_lib)

                cfg = {
                    "name": f"{var_key}_{default_corner_name}" if default_corner_name else var_key,
                    "family": fam_key,
                    "family_display": fam_disp,
                    "variant": var_key,
                    "variant_name": var_name,
                    "tlef": tlef,
                    "lef": lef,
                    "gds": gds,
                    "tech": tech,
                    "lib": default_lib,
                    "default_corner": default_corner_name,
                    "corners": all_corners,
                    "corner_groups": resolved_corner_groups,
                    "multi_corner": {
                        "enabled": True,
                        "setup_ss": {"name": ss_def_key, "lib": ss_lib},
                        "nominal_tt": {"name": tt_def_key, "lib": tt_lib},
                        "hold_ff": {"name": ff_def_key, "lib": ff_lib},
                        "power_sweep": True
                    },
                    "rc_corners": {"nom": "default"}
                }
                parsed_configs.append(cfg)

        self.configs = parsed_configs

        # Append any user custom configs
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cached = json.load(f)
                    for c in cached:
                        if c.get("corner") == "Manual" and not any(x['name'] == c['name'] for x in self.configs):
                            self.configs.append(c)
            except Exception:
                pass
        return len(self.configs) > 0

    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    configs = json.load(f)
                    self.configs = [c for c in configs if os.path.exists(c.get('lib', ''))]
            except Exception:
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

    def add_manual_config(self, name, tlef, lef, lib, gds, tech=""):
        entry = {
            "name": name,
            "tlef": tlef,
            "lef": lef,
            "lib": lib,
            "gds": gds,
            "tech": tech,
            "corner": "Manual",
            "corners": {"Manual": lib},
            "corner_groups": {"manual": {"Manual": {"lib": lib, "temp": 25, "volt": 1.8}}}
        }
        self.configs = [c for c in self.configs if c['name'] != name]
        self.configs.insert(0, entry)
        self.save_cache()

    def _discover_pdk_path(self, pdk_path, name_prefix):
        """Scans a standard open_pdks/volare PDK directory for LEF, LIB, and TECH."""
        if not os.path.isdir(pdk_path):
            return None

        tlef_candidates = glob.glob(os.path.join(pdk_path, "libs.ref", "*", "techlef", "*.tlef"))
        tlef_candidates += glob.glob(os.path.join(pdk_path, "*.tlef"))
        tlef_candidates += glob.glob(os.path.join(pdk_path, "*tech*.lef"))
        tlef_candidates += glob.glob(os.path.join(pdk_path, "libs.ref", "*", "techlef", "*tech*.lef"))
        tlef_candidates.sort(key=lambda x: (
            0 if ("nom" in x and "rram" not in x) else
            1 if "tech" in os.path.basename(x).lower() else
            2 if "rram" not in x else 3
        ))
        tlef = [tlef_candidates[0]] if tlef_candidates else []

        lef_candidates = glob.glob(os.path.join(pdk_path, "libs.ref", "sky130_fd_sc_hd", "lef", "*.lef"))
        if not lef_candidates:
            lef_candidates = glob.glob(os.path.join(pdk_path, "libs.ref", "*sc*", "lef", "*.lef"))
        if not lef_candidates:
            lef_candidates = glob.glob(os.path.join(pdk_path, "libs.ref", "*", "lef", "*.lef"))
        if not lef_candidates:
            lef_candidates = glob.glob(os.path.join(pdk_path, "*.lef"))

        lef_candidates = [l for l in lef_candidates if not l.endswith(".tlef") and "tech" not in os.path.basename(l).lower()]
        lef_candidates.sort(key=lambda x: (
            0 if ("sky130_fd_sc_hd.lef" in x or "sc_mcu" in x) and "ef_" not in x and "pr" not in x else
            1 if "fd_sc" in x and "ef_" not in x and "pr" not in x else
            2 if "sc" in x and "pr" not in x else 3
        ))
        lef = [lef_candidates[0]] if lef_candidates else []

        gds = glob.glob(os.path.join(pdk_path, "libs.ref", "*", "gds", "*.gds"))
        if not gds:
            gds = glob.glob(os.path.join(pdk_path, "*.gds"))
        tech = glob.glob(os.path.join(pdk_path, "libs.tech", "magic", "*.tech"))
        if not tech:
            tech = glob.glob(os.path.join(pdk_path, "*.tech"))

        libs = glob.glob(os.path.join(pdk_path, "libs.ref", "*", "lib", "*.lib"))
        if not libs:
            libs = glob.glob(os.path.join(pdk_path, "*.lib"))

        if not libs or not lef:
            return None

        corners = {}
        for l in libs:
            bn = os.path.basename(l).replace('.lib', '')
            if "ccsnoise" in bn: continue
            parts = bn.split("__")
            if len(parts) > 1:
                corners[parts[1]] = l

        default_lib = ""
        for k in ["tt_025C_1v80", "tt_025C_5v00", "tt_100C_1v80", "tt_100C_5v00"]:
            if k in corners:
                default_lib = corners[k]
                break
        if not default_lib and libs:
            default_lib = libs[0]

        return {
            "name": name_prefix,
            "tlef": tlef[0] if tlef else "",
            "lef": lef[0] if lef else "",
            "gds": gds[0] if gds else "",
            "tech": tech[0] if tech else "",
            "lib": default_lib,
            "corners": corners,
            "rc_corners": {"nom": "default"}
        }

    def crawl_volare(self):
        found_any = False
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        pdk_root = os.environ.get("PDK_ROOT", os.path.join(repo_root, "third-party", "pdks"))
        if os.path.isdir(pdk_root):
            for item in os.listdir(pdk_root):
                if item == "volare": continue
                item_path = os.path.join(pdk_root, item)
                if os.path.isdir(item_path):
                    if item.startswith("sky130") or item.startswith("gf180"):
                        cfg = self._discover_pdk_path(item_path, f"Bundled_{item}")
                        if cfg:
                            self.update_config(cfg)
                            found_any = True

            local_volare = os.path.join(pdk_root, "volare")
            for family in ["sky130", "gf180mcu"]:
                fam_dir = os.path.join(local_volare, family, "versions")
                if os.path.isdir(fam_dir) and os.listdir(fam_dir):
                    versions = os.listdir(fam_dir)
                    versions.sort(key=lambda v: os.path.getmtime(os.path.join(fam_dir, v)), reverse=True)
                    latest = versions[0]
                    variant_name = "sky130A" if family == "sky130" else "gf180mcuC"
                    pdk_path = os.path.join(fam_dir, latest, variant_name)
                    cfg = self._discover_pdk_path(pdk_path, f"Local_{family}_{latest[:8]}")
                    if cfg:
                        self.update_config(cfg)
                        found_any = True

        user_volare = os.path.expanduser("~/.volare/volare")
        for family in ["sky130", "gf180mcu"]:
            fam_dir = os.path.join(user_volare, family, "versions")
            if os.path.isdir(fam_dir) and os.listdir(fam_dir):
                versions = os.listdir(fam_dir)
                versions.sort(key=lambda v: os.path.getmtime(os.path.join(fam_dir, v)), reverse=True)
                latest = versions[0]
                variant_name = "sky130A" if family == "sky130" else "gf180mcuC"
                pdk_path = os.path.join(fam_dir, latest, variant_name)
                cfg = self._discover_pdk_path(pdk_path, f"Volare_{family}_{latest[:8]}")
                if cfg:
                    self.update_config(cfg)
                    found_any = True

        if not found_any:
            bundled_sky130 = os.path.join(repo_root, "third-party", "OpenROAD", "test", "sky130hd")
            if os.path.isdir(bundled_sky130):
                cfg = self._discover_pdk_path(bundled_sky130, "Sky130_Bundled_HD")
                if cfg:
                    self.update_config(cfg)
                    found_any = True

        return found_any


class ManualPDKDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Custom PDK Configuration Editor")
        self.resize(750, 480)
        self.layout = QFormLayout(self)

        self.e_name = QLineEdit(config['name'] if config else "Custom_PDK")
        self.layout.addRow("<b>Configuration Name:</b>", self.e_name)

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

        btn_save = QPushButton("Save PDK Configuration")
        btn_save.setStyleSheet("background: #238636; color: white; font-weight: bold; padding: 10px; border-radius: 4px;")
        btn_save.clicked.connect(self.validate_and_accept)
        self.layout.addRow(btn_save)

    def browse(self, line_edit, filter_str):
        f, _ = QFileDialog.getOpenFileName(self, "Select File", "", filter_str)
        if f: line_edit.setText(f)

    def validate_and_accept(self):
        if not all([self.e_tlef.text(), self.e_lef.text(), self.e_lib.text(), self.e_gds.text(), self.e_tech.text()]):
            QMessageBox.warning(self, "Incomplete", "All 5 core files (TLEF, LEF, LIB, GDS, TECH) are required for full backend signoff.")
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
            "corner": "Manual",
            "corners": {"Manual": self.e_lib.text()},
            "corner_groups": {"manual": {"Manual": {"lib": self.e_lib.text(), "temp": 25, "volt": 1.8}}}
        }


class PDKSelector(QDialog):
    """
    Professional EDA PDK & Multi-Corner PVT Configuration Selector.
    Hierarchy: PDK Family -> Library Variant -> Process Corner Group -> PVT Operating Case.
    """
    def __init__(self, pdk_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDK & Timing Sign-Off Configuration")
        self.resize(960, 560)
        self.mgr = pdk_manager
        self.selected_config = None
        self.current_variant_cfg = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Search Bar
        search_lay = QHBoxLayout()
        lbl_search = QLabel("Filter:")
        lbl_search.setStyleSheet("font-weight: bold;")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter libraries, process corners, or operating conditions...")
        self.search.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        self.search.textChanged.connect(self.filter_tree)
        search_lay.addWidget(lbl_search)
        search_lay.addWidget(self.search)
        main_layout.addLayout(search_lay)

        # 2. Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel: Tree
        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(6)

        lbl_tree = QLabel("<b>PDK Library & Corner Hierarchy</b>")
        lbl_tree.setStyleSheet("font-size: 12px;")
        tree_layout.addWidget(lbl_tree)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Library / Corner", "PVT Condition"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        self.tree.itemDoubleClicked.connect(self.accept_selection)
        self.tree.setStyleSheet("""
            QTreeWidget {
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
        """)
        tree_layout.addWidget(self.tree)
        splitter.addWidget(tree_panel)

        # Right Panel: Selected PDK & Sign-Off Configuration
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)

        # Group A: Active PDK Summary & Core Files
        grp_details = QGroupBox("Selected PDK Assets")
        det_layout = QFormLayout(grp_details)
        det_layout.setSpacing(6)

        self.lbl_selected_title = QLabel("No Selection")
        self.lbl_selected_title.setStyleSheet("font-size: 12px; font-weight: bold;")
        det_layout.addRow("Configuration:", self.lbl_selected_title)

        self.lbl_tlef = QLineEdit(); self.lbl_tlef.setReadOnly(True)
        self.lbl_lef = QLineEdit(); self.lbl_lef.setReadOnly(True)
        self.lbl_lib = QLineEdit(); self.lbl_lib.setReadOnly(True)
        self.lbl_gds = QLineEdit(); self.lbl_gds.setReadOnly(True)
        self.lbl_tech = QLineEdit(); self.lbl_tech.setReadOnly(True)
        for w in [self.lbl_tlef, self.lbl_lef, self.lbl_lib, self.lbl_gds, self.lbl_tech]:
            w.setStyleSheet("padding: 3px 6px; font-family: monospace; font-size: 11px;")

        det_layout.addRow("Tech LEF:", self.lbl_tlef)
        det_layout.addRow("Cell LEF:", self.lbl_lef)
        det_layout.addRow("Liberty:", self.lbl_lib)
        det_layout.addRow("GDSII:", self.lbl_gds)
        det_layout.addRow("Magic Tech:", self.lbl_tech)
        right_layout.addWidget(grp_details)

        # Group B: Multi-Corner Multi-Mode (MCMM) Scenario Decision Tree
        grp_mcmm = QGroupBox("Timing Sign-Off & Characterization (MCMM)")
        mcmm_layout = QVBoxLayout(grp_mcmm)
        mcmm_layout.setSpacing(6)

        mcmm_top_bar = QHBoxLayout()
        self.chk_mcmm = QCheckBox("Enable Multi-Corner Sign-Off")
        self.chk_mcmm.setChecked(True)
        self.chk_mcmm.setStyleSheet("font-weight: bold;")
        mcmm_top_bar.addWidget(self.chk_mcmm)
        mcmm_top_bar.addStretch()

        self.btn_preset_all = QPushButton("Run All Standard (SS / TT / FF)")
        self.btn_preset_nom = QPushButton("Single Nominal (TT)")
        mcmm_top_bar.addWidget(self.btn_preset_all)
        mcmm_top_bar.addWidget(self.btn_preset_nom)
        mcmm_layout.addLayout(mcmm_top_bar)

        # Interactive Decision Tree Widget for MCMM Scenarios
        self.tree_mcmm = QTreeWidget()
        self.tree_mcmm.setHeaderLabels(["Scenario / PVT Condition", "Role / Target Mode", "Library Specification"])
        self.tree_mcmm.setStyleSheet("""
            QTreeWidget {
                font-family: monospace;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
        """)
        self.tree_mcmm.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_mcmm.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_mcmm.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree_mcmm.itemChanged.connect(self.on_mcmm_item_changed)
        mcmm_layout.addWidget(self.tree_mcmm)

        # Dynamic OpenSTA TCL Command Preview
        self.txt_mcmm_tcl = QPlainTextEdit()
        self.txt_mcmm_tcl.setReadOnly(True)
        self.txt_mcmm_tcl.setMaximumHeight(75)
        self.txt_mcmm_tcl.setStyleSheet("background-color: #161b22; color: #7ee787; font-family: monospace; font-size: 10px; border: 1px solid #30363d;")
        mcmm_layout.addWidget(QLabel("Live OpenSTA Constraint Preview:"))
        mcmm_layout.addWidget(self.txt_mcmm_tcl)

        self.btn_preset_all.clicked.connect(self.preset_mcmm_all)
        self.btn_preset_nom.clicked.connect(self.preset_mcmm_nominal)
        self.chk_mcmm.toggled.connect(self.on_mcmm_toggled)

        right_layout.addWidget(grp_mcmm)
        right_layout.addStretch()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 5)
        main_layout.addWidget(splitter)

        # 3. Action Toolbar
        btn_bar = QHBoxLayout()
        btn_add = QPushButton("Add Custom PDK...")
        btn_add.clicked.connect(self.trigger_add)

        btn_crawl = QPushButton("Rescan PDKs")
        btn_crawl.clicked.connect(self.trigger_crawl)

        btn_del = QPushButton("Delete Custom")
        btn_del.setStyleSheet("color: #f85149;")
        btn_del.clicked.connect(self.trigger_delete)

        btn_bar.addWidget(btn_add)
        btn_bar.addWidget(btn_crawl)
        btn_bar.addWidget(btn_del)
        btn_bar.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(btn_cancel)

        self.btn_select = QPushButton("Select PDK")
        self.btn_select.setStyleSheet("background-color: #238636; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        self.btn_select.setDefault(True)
        self.btn_select.clicked.connect(self.accept_selection)
        btn_bar.addWidget(self.btn_select)

        main_layout.addLayout(btn_bar)

        self.populate_tree()

    def populate_tree(self):
        """Builds clean, professional tree without emojis."""
        self.tree.clear()

        fam_buckets = {}
        for cfg in self.mgr.configs:
            fam_key = cfg.get("family", "custom")
            if fam_key not in fam_buckets:
                fam_buckets[fam_key] = []
            fam_buckets[fam_key].append(cfg)

        fam_display_map = {
            "sky130": "SkyWater 130nm Commercial PDK (sky130)",
            "gf180mcu": "GlobalFoundries 180nm MCU (gf180mcu)",
            "custom": "Custom ASIC PDKs"
        }

        first_corner_item = None

        for fam_key, configs in fam_buckets.items():
            fam_title = fam_display_map.get(fam_key, f"{fam_key.upper()} PDK")
            fam_node = QTreeWidgetItem(self.tree, [fam_title, ""])
            fam_node.setExpanded(True)
            fam_node.setFont(0, QFont("", 10, QFont.Weight.Bold))

            for cfg in configs:
                var_name = cfg.get("variant_name", cfg.get("name", "Unknown"))
                var_key = cfg.get("variant", cfg.get("name"))
                var_node = QTreeWidgetItem(fam_node, [var_name, f"[{var_key}]"])
                var_node.setData(0, Qt.ItemDataRole.UserRole, cfg)
                var_node.setExpanded(True)

                corner_groups = cfg.get("corner_groups", {})
                if not corner_groups:
                    corners = cfg.get("corners", {})
                    grp_node = QTreeWidgetItem(var_node, ["Standard [TT]", ""])
                    grp_node.setExpanded(True)
                    for c_name, c_lib in corners.items():
                        c_item = QTreeWidgetItem(grp_node, [c_name, "Nominal"])
                        c_item.setData(0, Qt.ItemDataRole.UserRole, (cfg, c_name, c_lib))
                        if not first_corner_item: first_corner_item = c_item
                else:
                    group_meta = [
                        ("tt", "Typical-Typical [TT]", "Nominal Reference"),
                        ("ss", "Slow-Slow [SS]", "Worst-Case Setup"),
                        ("ff", "Fast-Fast [FF]", "Best-Case Hold"),
                        ("manual", "Manual Corner", "")
                    ]
                    for grp_id, grp_title, grp_role in group_meta:
                        if grp_id in corner_groups and corner_groups[grp_id]:
                            grp_node = QTreeWidgetItem(var_node, [grp_title, grp_role])
                            grp_node.setExpanded(grp_id in ["tt", "ss"])

                            for c_name, c_data in corner_groups[grp_id].items():
                                temp = c_data.get("temp", 25)
                                volt = c_data.get("volt", 1.8)
                                is_def = (c_name == cfg.get("default_corner", ""))
                                label = f"{c_name} [Default]" if is_def else c_name
                                pvt_str = f"{temp}°C, {volt}V"
                                c_item = QTreeWidgetItem(grp_node, [label, pvt_str])
                                c_item.setData(0, Qt.ItemDataRole.UserRole, (cfg, c_name, c_data.get("lib", cfg.get("lib", ""))))
                                if is_def and not first_corner_item:
                                    first_corner_item = c_item
                                elif not first_corner_item:
                                    first_corner_item = c_item

        if first_corner_item:
            self.tree.setCurrentItem(first_corner_item)

    def filter_tree(self, text):
        query = text.strip().lower()

        def filter_node(item):
            match = query in item.text(0).lower() or query in item.text(1).lower()
            child_matches = False
            for i in range(item.childCount()):
                child = item.child(i)
                if filter_node(child):
                    child_matches = True
            visible = match or child_matches
            item.setHidden(not visible)
            if visible and query:
                item.setExpanded(True)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            filter_node(self.tree.topLevelItem(i))

    def on_tree_selection_changed(self):
        item = self.tree.currentItem()
        if not item: return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        cfg = None
        selected_corner_name = None
        selected_corner_lib = None

        if isinstance(data, tuple):
            cfg, selected_corner_name, selected_corner_lib = data
        elif isinstance(data, dict):
            cfg = data
            selected_corner_name = cfg.get("default_corner", cfg.get("corner", "default"))
            selected_corner_lib = cfg.get("lib", "")
        else:
            return

        self.current_variant_cfg = cfg
        clean_corner = selected_corner_name.replace(" [Default]", "")
        self.lbl_selected_title.setText(f"{cfg.get('variant_name', cfg.get('name'))}  —  {clean_corner}")
        self.lbl_tlef.setText(cfg.get('tlef', ''))
        self.lbl_lef.setText(cfg.get('lef', ''))
        self.lbl_lib.setText(selected_corner_lib or cfg.get('lib', ''))
        self.lbl_gds.setText(cfg.get('gds', ''))
        self.lbl_tech.setText(cfg.get('tech', ''))

        fam = cfg.get("family", "")
        self.populate_mcmm_tree(cfg, clean_corner)

    def populate_mcmm_tree(self, cfg, clean_corner):
        self.tree_mcmm.blockSignals(True)
        self.tree_mcmm.clear()
        
        all_corners = cfg.get("corners", {})
        if not all_corners:
            all_corners = {clean_corner: cfg.get("lib", "")}

        # Root: Family / Variant
        root_name = f"{cfg.get('family', 'PDK')} — {cfg.get('variant_name', cfg.get('name'))}"
        root_item = QTreeWidgetItem(self.tree_mcmm, [root_name, "Active Stack", cfg.get("tlef", "")])
        root_item.setExpanded(True)
        root_item.setForeground(0, QBrush(QColor("#58a6ff")))

        # Classify available corners
        scenarios = []
        for c_name, c_lib in all_corners.items():
            name_lower = c_name.lower()
            role = "Nominal / Reference"
            mode = "func"
            temp = "25C"
            volt = "1.80V"
            is_checked = True

            if "ss" in name_lower:
                role = "Setup (Worst Late)"
                temp = "100C" if "100" in name_lower else ("125C" if "125" in name_lower else "85C")
                volt = "1.60V"
            elif "ff" in name_lower:
                role = "Hold (Best Early)"
                temp = "-40C" if "n40" in name_lower or "m40" in name_lower else "0C"
                volt = "1.95V"
            elif "tt" in name_lower or clean_corner in c_name:
                role = "Nominal (Reference)"
                temp = "25C"
                volt = "1.80V"
            else:
                role = "PVT Skew"
                is_checked = False

            scenarios.append({
                "name": c_name,
                "role": role,
                "temp": temp,
                "volt": volt,
                "mode": mode,
                "lib": c_lib,
                "checked": is_checked
            })

        for s in scenarios:
            node = QTreeWidgetItem(root_item, [
                f"{s['name']} ({s['temp']}, {s['volt']})",
                s['role'],
                os.path.basename(s['lib']) if s['lib'] else "builtin"
            ])
            node.setFlags(node.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            node.setCheckState(0, Qt.CheckState.Checked if s['checked'] else Qt.CheckState.Unchecked)
            node.setData(0, Qt.ItemDataRole.UserRole, s)
            if "Setup" in s['role']:
                node.setForeground(1, QBrush(QColor("#f85149")))
            elif "Hold" in s['role']:
                node.setForeground(1, QBrush(QColor("#3fb950")))
            else:
                node.setForeground(1, QBrush(QColor("#d29922")))

        self.tree_mcmm.expandAll()
        self.tree_mcmm.blockSignals(False)
        self.update_mcmm_tcl_preview()

    def on_mcmm_toggled(self, checked):
        self.tree_mcmm.setEnabled(checked)
        self.btn_preset_all.setEnabled(checked)
        self.btn_preset_nom.setEnabled(checked)
        self.update_mcmm_tcl_preview()

    def on_mcmm_item_changed(self, item, column):
        self.update_mcmm_tcl_preview()

    def preset_mcmm_all(self):
        self.tree_mcmm.blockSignals(True)
        root = self.tree_mcmm.topLevelItem(0)
        if root:
            for i in range(root.childCount()):
                child = root.child(i)
                child.setCheckState(0, Qt.CheckState.Checked)
        self.tree_mcmm.blockSignals(False)
        self.update_mcmm_tcl_preview()

    def preset_mcmm_nominal(self):
        self.tree_mcmm.blockSignals(True)
        root = self.tree_mcmm.topLevelItem(0)
        if root:
            for i in range(root.childCount()):
                child = root.child(i)
                s = child.data(0, Qt.ItemDataRole.UserRole) or {}
                if "Nominal" in s.get("role", "") or "tt" in s.get("name", "").lower():
                    child.setCheckState(0, Qt.CheckState.Checked)
                else:
                    child.setCheckState(0, Qt.CheckState.Unchecked)
        self.tree_mcmm.blockSignals(False)
        self.update_mcmm_tcl_preview()

    def get_selected_mcmm_corners(self):
        selected = {}
        if not self.chk_mcmm.isChecked():
            return selected
        root = self.tree_mcmm.topLevelItem(0)
        if root:
            for i in range(root.childCount()):
                child = root.child(i)
                if child.checkState(0) == Qt.CheckState.Checked:
                    s = child.data(0, Qt.ItemDataRole.UserRole)
                    if s:
                        selected[s['name']] = s
        return selected

    def update_mcmm_tcl_preview(self):
        corners = self.get_selected_mcmm_corners()
        if not corners:
            self.txt_mcmm_tcl.setPlainText("# Single-Corner Default Timing Mode (MCMM disabled)")
            return
        lines = [
            f"# Multi-Corner Multi-Mode (MCMM) Timing Definition ({len(corners)} corners active)",
            "define_corners " + " ".join(corners.keys())
        ]
        for name, info in corners.items():
            lib_base = os.path.basename(info['lib']) if info.get('lib') else f"{name}.lib"
            lines.append(f'read_liberty -corner {name} "{lib_base}"')
        self.txt_mcmm_tcl.setPlainText("\n".join(lines))

    def trigger_crawl(self):
        if self.mgr.crawl_volare() or self.mgr.load_master_catalog():
            QMessageBox.information(self, "Success", "Refreshed and discovered PDKs successfully.")
            self.populate_tree()
        else:
            QMessageBox.warning(self, "Notice", "No additional PDKs discovered.")

    def trigger_add(self):
        d = ManualPDKDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.mgr.update_config(d.get_data())
            self.populate_tree()

    def trigger_delete(self):
        if not self.current_variant_cfg or self.current_variant_cfg.get("corner") != "Manual":
            QMessageBox.information(self, "Notice", "Only custom user-defined PDKs can be deleted.")
            return
        res = QMessageBox.question(self, "Delete", f"Delete configuration '{self.current_variant_cfg['name']}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            self.mgr.delete_config(self.current_variant_cfg['name'])
            self.populate_tree()

    def accept_selection(self):
        item = self.tree.currentItem()
        if not item and self.tree.topLevelItemCount() > 0:
            item = self.tree.topLevelItem(0)

        data = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        cfg = None
        corner_name = None
        corner_lib = None

        if isinstance(data, tuple):
            cfg, corner_name, corner_lib = data
        elif isinstance(data, dict):
            cfg = data
            corner_name = cfg.get("default_corner", cfg.get("corner", "default"))
            corner_lib = cfg.get("lib", "")
        elif self.current_variant_cfg:
            cfg = self.current_variant_cfg
            corner_name = cfg.get("default_corner", cfg.get("corner", "default"))
            corner_lib = cfg.get("lib", "")
        else:
            return

        corner_name = corner_name.replace(" [Default]", "")
        all_corners = cfg.get("corners", {corner_name: corner_lib})

        # Retrieve explicitly configured scenarios from tree
        active_mcmm = self.get_selected_mcmm_corners()
        mcmm_enabled = self.chk_mcmm.isChecked() and len(active_mcmm) > 0

        target_corners_dict = {}
        for c_k, c_v in active_mcmm.items():
            target_corners_dict[c_k] = c_v.get("lib", all_corners.get(c_k, corner_lib))
        if not target_corners_dict:
            target_corners_dict = all_corners

        # Multi-corner automatic golden mapping
        ss_name = "ss_100C_1v60" if "ss_100C_1v60" in target_corners_dict else corner_name
        tt_name = "tt_025C_1v80" if "tt_025C_1v80" in target_corners_dict else corner_name
        ff_name = "ff_n40C_1v95" if "ff_n40C_1v95" in target_corners_dict else corner_name

        self.selected_config = {
            "name": f"{cfg.get('variant', cfg.get('name'))}_{corner_name}",
            "family": cfg.get("family", "sky130"),
            "variant": cfg.get("variant", cfg.get("name")),
            "variant_name": cfg.get("variant_name", cfg.get("name")),
            "corner": corner_name,
            "tlef": cfg.get("tlef", ""),
            "lef": cfg.get("lef", ""),
            "gds": cfg.get("gds", ""),
            "tech": cfg.get("tech", ""),
            "lib": corner_lib or cfg.get("lib", ""),
            "corners": target_corners_dict,
            "corner_groups": cfg.get("corner_groups", {}),
            "multi_corner": {
                "enabled": mcmm_enabled,
                "setup_ss": {"name": ss_name, "lib": target_corners_dict.get(ss_name, corner_lib)},
                "nominal_tt": {"name": tt_name, "lib": target_corners_dict.get(tt_name, corner_lib)},
                "hold_ff": {"name": ff_name, "lib": target_corners_dict.get(ff_name, corner_lib)},
                "power_sweep": True
            },
            "rc_corners": {"nom": "default"}
        }
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key.Key_Enter, Qt.Key.Key_Return]:
            self.accept_selection()
            event.accept()
        else:
            super().keyPressEvent(event)
