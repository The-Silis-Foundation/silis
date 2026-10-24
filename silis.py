#!/usr/bin/env python3
import os
import sys

# Bootstrap repository root and core package paths
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR = os.path.join(_REPO_ROOT, "core")
_CLI_DIR = os.path.join(_CORE_DIR, "cli")

for _p in [_REPO_ROOT, _CORE_DIR, _CLI_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


import qt_setup
REPO_ROOT = qt_setup.REPO_ROOT

import json
import glob
import subprocess
import shlex
import time
import queue
import threading
import shutil
import re
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

# Importing extracted modules from core
from config import THEMES, USER_SETTINGS, save_user_settings
from editor.editor import CommandPalette, FileSearchPalette, VSCodeEditorTabs, ScintillaEditor
from terminal.terminal import VSCodeTerminalWidget
from pdkmanagers.pdk.manager import SSAForge, PDKManager, PDKSelector
from pdkmanagers.volare import VolareManagerWidget
from backendflow.siliconpeeker.peeker import DEFParser, FastSiliconPeeker
from signalpeeker.code import SignalPeeker
from schematicviewer.graphiccanvas import SchematicTab
from synthesisscripts.synthesisthread import SynthesisTab
from backendflow.flow.backendflow import BackendWidget
from projectwizard.codes import SilisProjectWizard, SilisLauncher

# Re-export Python SDK layer
try:
    from sdk import (
        Project,
        Pipeline,
        SignoffReport,
        SynthesisReport,
        DRCReport,
        create_project,
        load_project,
        view_layout,
        view_gds3d,
        view_waveforms,
        view_schematic,
        open_gui,
    )
except Exception:
    pass

# Direct alias for clean SDK usage: silis.load()
load = load_project

class SilisExplorer(QTreeView):
    fileOpened = pyqtSignal(str)
    dirChanged = pyqtSignal(str)
    gds3dOpened = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ide = parent
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

    def contextMenuEvent(self, event):
        idx = self.indexAt(event.pos())
        if not idx.isValid(): return
        path = self.fs_model.filePath(idx)
        menu = QMenu(self)
        if path.endswith(".gds") or path.endswith(".GDS"):
            action = menu.addAction("Open in 3D Viewer")
            action.triggered.connect(lambda: self.gds3dOpened.emit(path))
        menu.exec(event.globalPos())

    def on_double_click(self, index):
        path = self.fs_model.filePath(index)
        if self.fs_model.isDir(index):
            self.dirChanged.emit(path)
        else:
            self.fileOpened.emit(path)

    def set_cwd(self, path):
        self.setRootIndex(self.fs_model.index(path))

    def _get_project_root(self):
        if self.ide:
            proj = getattr(self.ide, 'project_path', None)
            if proj and os.path.exists(proj):
                return os.path.realpath(proj)
            cwd = getattr(self.ide, 'cwd', None)
            if cwd and os.path.exists(cwd):
                return os.path.realpath(cwd)
        return os.path.realpath(os.getcwd())

    def keyPressEvent(self, event):
        idx = self.currentIndex()
        path = self.fs_model.filePath(idx)
        key = event.key()

        if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            if self.fs_model.isDir(idx): self.dirChanged.emit(path) 
            else: self.fileOpened.emit(path) 
            event.accept()
        elif key in [Qt.Key.Key_Backspace, Qt.Key.Key_Escape]:
            # UX: Go up one directory (prevent navigating above project_path)
            current_dir = os.path.realpath(self.fs_model.filePath(self.rootIndex()))
            proj_root = self._get_project_root()
            if current_dir != proj_root and os.path.commonpath([current_dir, proj_root]) == proj_root:
                parent_dir = os.path.dirname(current_dir)
                if os.path.commonpath([parent_dir, proj_root]) == proj_root:
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
        real_path = os.path.realpath(path)
        proj_root = self._get_project_root()
        # Security SEC-06: Do not delete files outside project root or the project root itself
        if real_path == proj_root or os.path.commonpath([real_path, proj_root]) != proj_root:
            QMessageBox.warning(self, "Delete Forbidden", "Cannot delete files or directories outside the active project root.")
            return

        name = os.path.basename(path)
        reply = QMessageBox.question(self, "Delete", f"Are you sure you want to delete '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isdir(path): shutil.rmtree(path)
                else: os.remove(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete: {e}")

class CompileTab(QWidget):
    def __init__(self, ide_parent):
        super().__init__()
        self.ide = ide_parent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.split = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.split)

        # Explorer (Files | Hierarchy | Modules)
        from design_explorer import DesignExplorerPanel
        self.explorer = SilisExplorer(self.ide)
        self.explorer_panel = DesignExplorerPanel(self.ide, file_explorer=self.explorer)
        self.explorer.dirChanged.connect(self.ide.change_directory)
        self.explorer.fileOpened.connect(self.ide.open_file_in_editor)
        self.explorer.gds3dOpened.connect(self.ide.open_gds3d)
        
        self.explorer_panel.goToSource.connect(self.ide.open_file_in_editor)
        self.explorer_panel.openSchematic.connect(self.ide.show_module_schematic)
        self.explorer_panel.showInWaveform.connect(self.ide.add_waveform_signal)
        
        self.split.addWidget(self.explorer_panel)

        # Right: Code + Terminal
        self.right_split = QSplitter(Qt.Orientation.Vertical)
        self.split.addWidget(self.right_split)
        
        # Code
        self.code_container = QWidget()
        c_lay = QVBoxLayout(self.code_container); c_lay.setContentsMargins(0,0,0,0)
        self.editor = VSCodeEditorTabs()
        c_lay.addWidget(self.editor)
        self.right_split.addWidget(self.code_container)
        
        # ── VS Code-style terminal ──────────────────────────────────────────
        self.terminal = VSCodeTerminalWidget(self.ide)
        self.right_split.addWidget(self.terminal)
        
        self.split.setStretchFactor(0, 1); self.split.setStretchFactor(1, 4)
        self.split.setSizes([1000, 9000])  # Make explorer pane take less space
        self.right_split.setStretchFactor(0, 8); self.right_split.setStretchFactor(1, 1)
        self.right_split.setSizes([8000, 2000])

class SettingsDialog(QDialog):
    def _pick_color(self, line_edit, lbl):
        c = QColorDialog.getColor(QColor(line_edit.text() if line_edit.text() else "#FFFFFF"), self)
        if c.isValid():
            line_edit.setText(c.name())
            lbl.setStyleSheet(f"background-color: {c.name()}; border: 1px solid #555; border-radius: 2px;")

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
            
        # External Editor
        self.e_ext_edit = QLineEdit(USER_SETTINGS.get("external_editor", ""))
        form.addRow("External Editor Command:", self.e_ext_edit)
        
        # LOD Settings
        form.addRow(QLabel("<b>Level of Detail (LOD) Thresholds:</b>"))
        
        self.chk_lod = QCheckBox("Enable LOD (Disable to always show all)")
        self.chk_lod.setChecked(USER_SETTINGS.get("lod_enabled", False))
        form.addRow("", self.chk_lod)
        
        self.spin_lod_std = QDoubleSpinBox()
        self.spin_lod_std.setRange(0.0, 1.0)
        self.spin_lod_std.setSingleStep(0.0001)
        self.spin_lod_std.setDecimals(6)
        self.spin_lod_std.setValue(USER_SETTINGS.get("lod_std_cells", 0.002))
        form.addRow("Standard/Tap Cells Zoom Threshold:", self.spin_lod_std)
        
        self.spin_lod_nets = QDoubleSpinBox()
        self.spin_lod_nets.setRange(0.0, 1.0)
        self.spin_lod_nets.setSingleStep(0.0001)
        self.spin_lod_nets.setDecimals(6)
        self.spin_lod_nets.setValue(USER_SETTINGS.get("lod_nets", 0.005))
        form.addRow("Nets/Signals Zoom Threshold:", self.spin_lod_nets)
            
            
        self.tabs.addTab(t_gen, "General Settings")
        
        # --- TAB 1.5: Appearance ---
        t_app = QWidget(); form_app = QFormLayout(t_app)
        
        self.cb_font = QFontComboBox()
        self.cb_font.setCurrentFont(QFont(self.ide.tab_compile.editor.font_family))
        form_app.addRow("Editor Font:", self.cb_font)
        
        self.spin_size = QSpinBox()
        self.spin_size.setRange(6, 36)
        self.spin_size.setValue(self.ide.tab_compile.editor.font_size)
        form_app.addRow("Font Size:", self.spin_size)
        

        self.cb_theme = QComboBox()
        self.cb_theme.addItems(list(THEMES.keys()))
        self.cb_theme.setCurrentText(self.ide.tab_compile.editor.theme_name)
        form_app.addRow("Color Theme:", self.cb_theme)
        
        # Editor Engine Backend (QScintilla vs Monaco)
        self.cb_editor_backend = QComboBox()
        self.cb_editor_backend.addItem("QScintilla (Fast, Native)", "qscintilla")
        self.cb_editor_backend.addItem("Monaco (WebEngine, VS Code)", "monaco")
        curr_backend = USER_SETTINGS.get("editor_backend", "monaco").lower()
        idx_backend = 0 if curr_backend == "qscintilla" else 1
        self.cb_editor_backend.setCurrentIndex(idx_backend)
        form_app.addRow("Editor Engine:", self.cb_editor_backend)
        
        self.custom_colors = {}
        for key in ["bg", "fg", "sel", "kw", "kw2", "str", "comment", "num", "ident"]:
            c_val = THEMES["Custom"].get(key, "")
            e = QLineEdit(c_val)
            self.custom_colors[key] = e
            
            lbl = QLabel()
            lbl.setFixedSize(20, 20)
            if QColor(c_val).isValid():
                lbl.setStyleSheet(f"background-color: {c_val}; border: 1px solid #555; border-radius: 2px;")
                
            btn = QPushButton("Pick Color")
            btn.clicked.connect(lambda checked, _e=e, _l=lbl: self._pick_color(_e, _l))
            
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0)
            l.addWidget(e)
            l.addWidget(lbl)
            l.addWidget(btn)
            
            desc = {
                "bg": "Background",
                "fg": "Foreground (Text)",
                "sel": "Selection (sel)",
                "kw": "Keyword 1 (kw - module, endmodule)",
                "kw2": "Keyword 2 (kw2 - input, output)",
                "str": "Strings (str - \"text\")",
                "comment": "Comments (comment - // text)",
                "num": "Numbers (num - 1, 2, 3)",
                "ident": "Identifiers (ident - wire_name)"
            }
            form_app.addRow(f"{desc.get(key, key)}:", w)
        
        self.tabs.addTab(t_app, "Appearance")
        
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
            

        # Apply Appearance
        font_family = self.cb_font.currentFont().family()
        font_size = self.spin_size.value()
        theme_name = self.cb_theme.currentText()
        
        for k, e in self.custom_colors.items():
            THEMES["Custom"][k] = e.text()
            
        USER_SETTINGS["font_family"] = font_family
        USER_SETTINGS["font_size"] = font_size
        USER_SETTINGS["theme_name"] = theme_name
        editor_backend = self.cb_editor_backend.currentData() or "qscintilla"
        USER_SETTINGS["editor_backend"] = editor_backend
        USER_SETTINGS["custom_theme"] = THEMES["Custom"]
        USER_SETTINGS["external_editor"] = self.e_ext_edit.text()
        USER_SETTINGS["lod_enabled"] = self.chk_lod.isChecked()
        USER_SETTINGS["lod_std_cells"] = self.spin_lod_std.value()
        USER_SETTINGS["lod_nets"] = self.spin_lod_nets.value()
        save_user_settings(USER_SETTINGS)

        
        # Update Editor
        if hasattr(self.ide.tab_compile, 'editor'):
            self.ide.tab_compile.editor.update_appearance(font_family, font_size, theme_name, editor_backend=editor_backend)
            
        # Update Terminal
        if hasattr(self.ide.tab_compile, 'terminal'):
            self.ide.tab_compile.terminal.update_appearance(font_family, font_size, THEMES[theme_name])
            
        # Update Silicon Peeker
        if hasattr(self.ide.tab_compile, 'peeker'):
            if hasattr(self.ide.tab_compile.peeker, 'core') and self.ide.tab_compile.peeker.core:
                std_lod = USER_SETTINGS["lod_std_cells"] if USER_SETTINGS["lod_enabled"] else 0.0
                net_lod = USER_SETTINGS["lod_nets"] if USER_SETTINGS["lod_enabled"] else 0.0
                self.ide.tab_compile.peeker.core.set_lod(std_lod, net_lod)
            self.ide.tab_compile.peeker.update_appearance()
            if hasattr(self.ide.tab_compile.peeker, 'native_widget'):
                self.ide.tab_compile.peeker.native_widget.update()
            
        self.accept()





class SilisIDE(QMainWindow):
    def set_active_pdk(self, pdk_config):
        self.active_pdk = pdk_config
        if hasattr(self, 'backend_widget') and self.backend_widget:
            self.backend_widget.active_pdk = pdk_config
        if hasattr(self, 'tab_synth') and hasattr(self.tab_synth, 'lbl_pdk'):
            pname = pdk_config.get('name', 'None') if pdk_config else 'None'
            self.tab_synth.lbl_pdk.setText(f"<b>Active PDK:</b> {pname}")

    def resolve_and_set_pdk(self, pdk_name=None):
        if not pdk_name and hasattr(self, 'project_config') and self.project_config:
            pdk_name = self.project_config.get("pdk", "sky130")
        if not pdk_name:
            pdk_name = "sky130"

        target = None
        for cfg in self.pdk_mgr.configs:
            if cfg['name'] == pdk_name or pdk_name.lower() in cfg['name'].lower():
                target = cfg
                break

        if not target:
            self.pdk_mgr.crawl_volare()
            for cfg in self.pdk_mgr.configs:
                if cfg['name'] == pdk_name or pdk_name.lower() in cfg['name'].lower():
                    target = cfg
                    break

        if not target and self.pdk_mgr.configs:
            target = self.pdk_mgr.configs[0]

        if target:
            self.set_active_pdk(target)
            return target
        return None

    def __init__(self, project_file=None, headless=False):
        super().__init__()
        self.setWindowTitle("Silis — Silicon Scaffold v2.1")
        self.resize(1400, 900)
        self.cwd = os.getcwd(); self.current_file = None; self.pdk_path = ""
        self.project_path = self.cwd
        self.project_config = None; self.active_pdk = None
        self.headless = headless
        self.pdk_mgr = PDKManager()


        if project_file:
            proj_path = os.path.abspath(project_file)
            if os.path.isdir(proj_path):
                cand = os.path.join(proj_path, "silis.silisproj")
                if os.path.isfile(cand):
                    proj_path = cand
            self.cwd = os.path.dirname(proj_path)
            self.project_path = self.cwd
            os.chdir(self.cwd)
            import json
            with open(proj_path, 'r') as f:
                self.project_config = json.load(f)
            import project_registry
            project_registry.register_project(proj_path)
            pdk_name = self.project_config.get("pdk", "sky130")
            self.resolve_and_set_pdk(pdk_name)
            proj_name = self.project_config.get("project_name", "Unknown")
            self.setWindowTitle(f"Silis — Silicon Scaffold v2.1 - [{proj_name}]")
        else:
            cand_cwd = os.path.join(os.getcwd(), "silis.silisproj")
            if os.path.isfile(cand_cwd):
                self.cwd = os.getcwd()
                self.project_path = self.cwd
                import json
                with open(cand_cwd, 'r') as f:
                    self.project_config = json.load(f)
                import project_registry
                project_registry.register_project(self.cwd)
                pdk_name = self.project_config.get("pdk", "sky130")
                self.resolve_and_set_pdk(pdk_name)
                proj_name = self.project_config.get("project_name", "Unknown")
                self.setWindowTitle(f"Silis — Silicon Scaffold v2.1 - [{proj_name}]")
            elif not headless:
                launcher = SilisLauncher(None)
                launcher.raise_()
                launcher.activateWindow()
                if launcher.exec() == QDialog.DialogCode.Accepted:
                    self.cwd = launcher.selected_project_path
                    self.project_path = self.cwd
                    os.chdir(self.cwd)
                    self.project_config = launcher.selected_project_config
                    import project_registry
                    project_registry.register_project(self.cwd)
                    pdk_name = self.project_config.get("pdk", "sky130")
                    self.resolve_and_set_pdk(pdk_name)
                    proj_name = self.project_config.get("project_name", "Unknown")
                    self.setWindowTitle(f"Silis — Silicon Scaffold v2.1 - [{proj_name}]")
                else:
                    self.project_config = None
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
        self.synth_running = False
        self.synth_error = None
        self.sk_timer = QTimer(); self.sk_timer.setSingleShot(True); self.sk_timer.timeout.connect(self.reset_sk)

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
        self.frontend_tabs.currentChanged.connect(self._on_frontend_tab_changed)
        self.stack.addWidget(self.frontend_tabs)
        
        # World 2: Backend Layout
        self.backend_widget = BackendWidget(self)
        self.stack.addWidget(self.backend_widget)
        self.setup_toolbar()
        
        # Global Input Filter
        QApplication.instance().installEventFilter(self)
        
        # Shortcut: Ctrl+I to Find Instance
        shortcut_find_inst = QShortcut(QKeySequence("Ctrl+I"), self)
        shortcut_find_inst.activated.connect(self._trigger_find_instance)
        
        # Background Timer
        self.queue_timer = QTimer(); self.queue_timer.timeout.connect(self.process_queue); self.queue_timer.start(50)
        
        self.log_system(f"Silis Initialized. CWD: {self.cwd}")
        self.check_dependencies()

        # Propagate active PDK
        if self.project_config:
            self.resolve_and_set_pdk()
        elif self.active_pdk:
            self.set_active_pdk(self.active_pdk)

        if self.cwd:
            if hasattr(self.tab_compile, 'file_system_model') and hasattr(self.tab_compile, 'tree_view'):
                self.tab_compile.file_system_model.setRootPath(self.cwd)
                self.tab_compile.tree_view.setRootIndex(self.tab_compile.file_system_model.index(self.cwd))
            top_mod = self.project_config.get("top_module") if self.project_config else None
            if top_mod:
                target_file = None
                rtl_files = self.project_config.get("rtl_files", []) if self.project_config else []
                # 1. Direct match from rtl_files list
                for f_path in rtl_files:
                    abs_candidate = f_path if os.path.isabs(f_path) else os.path.join(self.cwd, f_path)
                    if top_mod in os.path.basename(f_path) and os.path.isfile(abs_candidate):
                        target_file = abs_candidate
                        break

                # 2. Shallow check in source/ or top-level project root
                if not target_file:
                    for ext in [".v", ".sv", ".vhd", ".vhdl"]:
                        cand_src = os.path.join(self.cwd, "source", f"{top_mod}{ext}")
                        if os.path.isfile(cand_src):
                            target_file = cand_src
                            break
                        cand_root = os.path.join(self.cwd, f"{top_mod}{ext}")
                        if os.path.isfile(cand_root):
                            target_file = cand_root
                            break

                # 3. Shallow search in source/ directory if top module specific file not matched
                if not target_file:
                    src_dir = os.path.join(self.cwd, "source")
                    if os.path.isdir(src_dir):
                        try:
                            for entry in os.listdir(src_dir):
                                if top_mod in entry and os.path.isfile(os.path.join(src_dir, entry)):
                                    target_file = os.path.join(src_dir, entry)
                                    break
                        except Exception:
                            pass

                if target_file and os.path.isfile(target_file):
                    self.open_file_in_editor(target_file)

            if hasattr(self.tab_compile, 'explorer_panel'):
                self.tab_compile.explorer_panel.scan_workspace()

        # Auto-coordinate with CLI deliverables on disk (GUI mode only)
        if not self.headless:
            QTimer.singleShot(200, self._coordinate_cli_state)

    def _on_frontend_tab_changed(self, index):
        """
        Coordinates the shared WebEngineView when switching between frontend tabs.
        Compile tab uses Monaco (if backend=monaco), Schematic tab uses DigitalJS,
        and Waveform tab can use Intel ROHD.
        """
        try:
            # If leaving Waveform tab and ROHD was open, keep state clean
            # If entering Schematic tab, ensure DigitalJS is initialized
            if index == 1: # WAVEFORM
                if hasattr(self, 'tab_waves') and hasattr(self.tab_waves, 'ensure_viewer'):
                    self.tab_waves.ensure_viewer()
            elif index == 2: # SCHEMATIC
                if hasattr(self, 'tab_schem') and hasattr(self.tab_schem, 'ensure_engine'):
                    self.tab_schem.ensure_engine()
        except Exception as e:
            print(f"[SILIS] Tab switch warning: {e}")

    def _coordinate_cli_state(self):
        if self.headless:
            return
        try:
            if hasattr(self, 'tab_synth') and self.tab_synth:
                self.tab_synth.update_dashboard()
            if hasattr(self, 'backend_widget') and self.backend_widget:
                self.backend_widget.force_refresh_view()
            if hasattr(self, 'tab_waves') and self.tab_waves:
                self.tab_waves.auto_load()
        except Exception as e:
            pass

    # === UX: SMART SHORTCUTS ===
    def eventFilter(self, source, event):
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(source, event)

        key = event.key()
        modifiers = event.modifiers()
        
        # --- COMMAND PALETTE ---
        if key == Qt.Key.Key_P and (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.ShiftModifier):
            focused = QApplication.focusWidget()
            if focused and (self.tab_compile.editor.isAncestorOf(focused) or focused is self.tab_compile.editor):
                current_ed = self.tab_compile.editor.current_editor()
                if current_ed and hasattr(current_ed, 'run_js'):
                    current_ed.run_js("editor.trigger('keyboard', 'editor.action.quickCommand')")
                return True
                
            commands = [
                ("View: Toggle Fullscreen", lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen()),
                ("View: Open Settings", self.open_settings),
                ("Go to: Compile Tab", lambda: self.frontend_tabs.setCurrentIndex(0)),
                ("Go to: Waveform Tab", lambda: self.frontend_tabs.setCurrentIndex(1)),
                ("Go to: Schematic Tab", lambda: self.frontend_tabs.setCurrentIndex(2)),
                ("Go to: Synthesis Dashboard", lambda: self.frontend_tabs.setCurrentIndex(3)),
                ("Go to: 3D Viewer", lambda: (self.switch_world(1), self.backend_widget.viz_tabs.setCurrentIndex(1))),
                ("Backend: Reset Flow", self.backend_widget.reset_backend),
            ]
            pal = CommandPalette(self, commands)
            pal.move(self.geometry().center() - pal.rect().center())
            if pal.exec():
                func = pal.get_selected()
                if func: func()
            return True
            
        # --- FILE SEARCH (Ctrl+P) ---
        if key == Qt.Key.Key_P and (modifiers & Qt.KeyboardModifier.ControlModifier) and not (modifiers & Qt.KeyboardModifier.ShiftModifier):
            from editor.editor import FileSearchPalette
            pal = FileSearchPalette(self, self.cwd)
            pal.setFixedSize(600, 400)
            pal.move(self.geometry().center() - pal.rect().center())
            
            if pal.exec():
                selected_file = pal.get_selected()
                if selected_file:
                    self.open_file_in_editor(selected_file)
            return True
        
        # --- FULLSCREEN TOGGLE ---
        if key == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return True
        
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

            elif key == Qt.Key.Key_F5:
                self.switch_world(1)
                self.backend_widget.viz_tabs.setCurrentIndex(2)
                return True

        # --- SUPER KEY LOGIC (` + Key) ---
        if key == Qt.Key.Key_QuoteLeft: # Backtick `
            if getattr(self, '_ignore_next_sk', False):
                self._ignore_next_sk = False
                return False
            if self.sk_active:
                self.reset_sk()
                focused = QApplication.focusWidget()
                if focused:
                    self._ignore_next_sk = True
                    if self.tab_compile.terminal.isAncestorOf(focused) or focused is self.tab_compile.terminal:
                        self.tab_compile.terminal.core.send_text("`")
                    elif self.tab_compile.editor.isAncestorOf(focused) or focused is self.tab_compile.editor:
                        current_ed = self.tab_compile.editor.current_editor()
                        if current_ed and hasattr(current_ed, 'run_js'):
                            current_ed.run_js("editor.trigger('keyboard', 'type', {text: '`'})")
                    elif hasattr(focused, 'insert'):
                        focused.insert("`")
                    elif hasattr(focused, 'insertPlainText'):
                        focused.insertPlainText("`")
                return True
            else:
                self.sk_active = True
                self.statusBar().showMessage("SUPER KEY ACTIVE")
                self.show_sk_overlays()
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
                current_ed = self.tab_compile.editor.current_editor()
                if current_ed:
                    if hasattr(current_ed, 'run_js'): current_ed.run_js("editor.focus()")
                    if hasattr(current_ed, 'editor') and hasattr(current_ed.editor, 'web_view'): current_ed.editor.web_view.setFocus()
                else:
                    self.tab_compile.editor.setFocus()
            elif txt == self.key_map["focus_terminal"]: 
                self.switch_world(0); self.frontend_tabs.setCurrentIndex(0)
                self.tab_compile.terminal.setFocus()
            elif txt == self.key_map["term_toggle"]:
                pass # term toggle removed
            elif txt == 'e':
                cmd = USER_SETTINGS.get("external_editor", "")
                path = self.tab_compile.editor.current_file_path()
                if cmd and path:
                    import subprocess
                    import shlex
                    try:
                        cmd_args = shlex.split(cmd) + [path]
                        subprocess.Popen(cmd_args, shell=False)
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to launch editor: {e}")
                else:
                    QMessageBox.warning(self, "Error", "No external editor configured or no active file.")

            
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
                # Wait for OpenROAD to finish writing the checkpoint database
                import time
                t0 = time.time()
                while getattr(self.backend_widget, 'cmd_active', False) and (time.time() - t0 < 10.0):
                    QApplication.processEvents()
                    self.backend_widget.proc.waitForReadyRead(200)

            # Attempt graceful exit of OpenROAD backend
            if self.backend_widget.proc and self.backend_widget.proc.state() == QProcess.ProcessState.Running:
                self.backend_widget.send_command_internal("exit")
                self.backend_widget.proc.waitForFinished(2000)

        import os
        import subprocess
        try:
            pid = os.getpid()
            # Clean up any remaining child processes
            out = subprocess.check_output(['pgrep', '-P', str(pid)]).decode('utf-8').strip()
            for child_pid in out.split():
                if child_pid:
                    try:
                        os.kill(int(child_pid), 9)
                    except: pass
        except: pass
            
        event.accept()

    def reset_sk(self):
        self.sk_active = False
        self.statusBar().clearMessage()
        if hasattr(self, 'sk_overlays'):
            for lbl in self.sk_overlays:
                lbl.deleteLater()
            self.sk_overlays = []

    def show_sk_overlays(self):
        self.sk_overlays = []
        def create_overlay(parent, text):
            lbl = QLabel(text, parent)
            lbl.setStyleSheet("background: rgba(0, 122, 204, 0.9); color: white; font-weight: bold; font-size: 24px; padding: 10px; border-radius: 5px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.resize(100, 50)
            lbl.move(parent.width()//2 - 50, parent.height()//2 - 25)
            lbl.show()
            self.sk_overlays.append(lbl)
            
        if self.stack.currentIndex() == 0 and self.frontend_tabs.currentIndex() == 0:
            create_overlay(self.tab_compile.explorer, f"[{self.key_map.get('focus_explorer', 'x').upper()}]")
            create_overlay(self.tab_compile.editor, f"[{self.key_map.get('focus_editor', 'c').upper()}]")
            create_overlay(self.tab_compile.terminal, f"[{self.key_map.get('focus_terminal', 'v').upper()}]")

    def switch_world(self, index):
        self.stack.setCurrentIndex(index)
        self.btn_front.setChecked(index == 0)
        self.btn_back.setChecked(index == 1)
        if index == 1 and hasattr(self, 'backend_widget') and self.backend_widget:
            self.backend_widget.force_refresh_view()
        elif index == 0 and hasattr(self, 'tab_synth') and self.tab_synth:
            self.tab_synth.update_dashboard()

    # === CORE LOGIC ===

    # === REPLACE IN SilisIDE CLASS ===
    def generate_schematic(self):
        if self.schem_running:
            self.log_system("Schematic generation in progress...", "WARN")
            return
        self.tab_schem.go_home()

    def run_synthesis_flow(self, bypass_prompt=False):
        base = None
        if hasattr(self, 'project_config') and self.project_config:
            base = self.project_config.get("top_module")
        if not base:
            _, base = self.get_context()
        
        if not base: 
            self.log_system("[ERR] Cannot determine top module for synthesis.")
            return
            
        root = self.prep_workspace(base)
        if not self.active_pdk:
            self.resolve_and_set_pdk()
        if not self.active_pdk:
            self.log_system("[ERR] No Active PDK selected.")
            return
            
        self.pdk_path = self.active_pdk['lib']
        self.run_synthesis_thread(root, base, bypass_prompt=bypass_prompt)

    def run_synthesis_thread(self, root, base, bypass_prompt=False):
        # Clear the unified log before starting
        self.tab_synth.log_main.clear()
        self.tab_synth.card_status.setText("RUNNING...")
        self.tab_synth.card_status.setStyleSheet("background:#eaeef2; color:#57606a; font-weight:bold; padding:15px; border-radius:6px; border: 1px solid #d0d7de;")

        v_net = os.path.join(root, "netlist", f"{base}_netlist.v")
        
        src_v = []
        if hasattr(self, 'project_config') and self.project_config and self.project_config.get("rtl_files"):
            for f_path in self.project_config.get("rtl_files", []):
                abs_path = os.path.join(self.cwd, f_path) if not os.path.isabs(f_path) else f_path
                if not os.path.exists(abs_path):
                    # Smart healing: check relative to root or root/source
                    cand = os.path.join(root, "source", os.path.basename(f_path))
                    if os.path.exists(cand):
                        abs_path = cand
                    else:
                        cand2 = os.path.join(root, os.path.basename(f_path))
                        if os.path.exists(cand2):
                            abs_path = cand2
                src_v.append(abs_path)
        else:
            src_v = glob.glob(os.path.join(root, "source", "*.v")) + \
                    glob.glob(os.path.join(root, "source", "*.sv")) + \
                    glob.glob(os.path.join(root, "source", "*.vhd")) + \
                    glob.glob(os.path.join(root, "source", "*.vhdl"))
                    
        vhdl_files = [s for s in src_v if s.endswith('.vhd') or s.endswith('.vhdl')]
        vlog_files = [s for s in src_v if not (s.endswith('.vhd') or s.endswith('.vhdl'))]

        # Prioritize packages and core types before entities
        def vhdl_sort_key(p):
            fn = os.path.basename(p).lower()
            if any(k in fn for k in ['package', 'pkg', 'types', 'const']):
                return 0
            if 'sys' in fn or 'prim' in fn:
                return 1
            if fn.endswith('_top.vhd') or fn.endswith('_wrapper.vhd'):
                return 3
            return 2
        vhdl_files = sorted(vhdl_files, key=vhdl_sort_key)
        
        plugin_path = os.path.abspath(os.path.join(REPO_ROOT, "third-party", "plugins", "ghdl.so"))
        plugin_cmd = f"plugin -i {plugin_path};\n" if os.path.exists(plugin_path) else "plugin -i ghdl;\n"
        read_cmd = plugin_cmd if vhdl_files else ""
        if vhdl_files:
            work_lib = os.path.basename(root)
            if hasattr(self, 'project_config') and self.project_config:
                work_lib = self.project_config.get("vhdl_work", self.project_config.get("project_name", work_lib))
            # If the design or any VHDL file is from neorv32, library must be 'neorv32'
            if any("neorv32" in str(x).lower() for x in [root, base, work_lib] + vhdl_files):
                work_lib = "neorv32"
            
            vhdl_std = "08"
            if hasattr(self, 'project_config') and self.project_config:
                vhdl_std = self.project_config.get("vhdl_std", "08")
                
            is_vhdl_top = False
            for vf in vhdl_files:
                try:
                    with open(vf, "r", errors="ignore") as vfh:
                        c = vfh.read().lower()
                        if f"entity {base.lower()} " in c or f"entity {base.lower()}\n" in c or f"entity {base.lower()};" in c:
                            is_vhdl_top = True
                            break
                except Exception:
                    pass

            e_flag = f" -e {base}" if is_vhdl_top else ""
            read_cmd += f"ghdl --std={vhdl_std} --work={work_lib} {' '.join(vhdl_files)}{e_flag};\n"
        if vlog_files:
            has_sv = any(f.endswith('.sv') for f in vlog_files)
            sv_flag = "-sv " if has_sv else ""
            read_cmd += f"read_verilog {sv_flag}{' '.join(vlog_files)};\n"
        macro_lib_cmds_yosys = ""
        macro_lib_cmds_sta = ""
        macros = self.project_config.get('macros', []) if hasattr(self, 'project_config') and self.project_config else []
        if macros:
            volare_base = self.pdk_path.split("libs.ref")[0]
            lib_search = os.path.join(volare_base, "libs.ref", "*", "lib", "*.lib")
            for lib in glob.glob(lib_search):
                name = os.path.basename(lib).replace('.lib', '')
                if any(m in name for m in macros):
                    macro_lib_cmds_yosys += f"read_liberty -lib {lib}\n        "
                    macro_lib_cmds_sta += f"read_liberty {lib}\n        "

        # --- 1. YOSYS SCRIPT (With Explicit File Dumps) ---
        # Note the 'tee -o reports/area.rpt' to save area stats to a file
        flatten_cmd = "flatten\n        " if getattr(self, "synth_flatten", False) else "#flatten\n        "
        ys = f"""
        read_liberty -lib {self.pdk_path}
        {macro_lib_cmds_yosys}{read_cmd}
        synth -top {base}
        dfflibmap -liberty {self.pdk_path}
        abc -liberty {self.pdk_path}
        {flatten_cmd}tee -o {os.path.join(root, 'reports', 'area.rpt')} stat -liberty {self.pdk_path} -json
        write_verilog -noattr {v_net}
        """
        
        if not bypass_prompt:
            # --- USER CONFIRMATION DIALOG ---
            dlg = QDialog(self)
            dlg.setWindowTitle("Confirm Yosys Synthesis Script")
            dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
            dlg.resize(700, 350)
            
            theme_name = USER_SETTINGS.get("theme_name", "Catppuccin Mocha")
            theme = THEMES.get(theme_name, THEMES["Catppuccin Mocha"])
            dlg.setStyleSheet(f"QDialog {{ background-color: {theme['bg']}; color: {theme['fg']}; }} QLabel {{ color: {theme['fg']}; }}")
            
            dlg_layout = QVBoxLayout(dlg)
            dlg_layout.addWidget(QLabel("Edit the Yosys commands below. (Uncomment 'flatten' to extract complete clock tree hierarchy)"))
            
            editor = ScintillaEditor(is_minimap=False, font_family=USER_SETTINGS.get("font_family", "Consolas"), font_size=USER_SETTINGS.get("font_size", 11), theme_name=theme_name)
            editor.set_lexer(".tcl")
            editor.setText(ys.strip())
            dlg_layout.addWidget(editor)
            
            bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            bbox.accepted.connect(dlg.accept)
            bbox.rejected.connect(dlg.reject)
            dlg_layout.addWidget(bbox)
            
            QShortcut(QKeySequence("Ctrl+Return"), dlg).activated.connect(dlg.accept)
            
            if not dlg.exec():
                self.tab_synth.card_status.setText("CANCELLED")
                return
                
            ys = editor.text()

        with open(os.path.join(root, "synth.ys"), 'w') as f: f.write(ys)
        
        # --- 2. STA SCRIPT (With Explicit File Dumps) ---
        # Redirects output (>) to timing.rpt and power.rpt
        sdc_files = glob.glob(os.path.join(root, "source", "*.sdc"))
        abs_sdc = sdc_files[0] if sdc_files else os.path.join(root, "source", f"{base}.sdc")
        tcl = f"""sta::set_thread_count [exec nproc]
        read_liberty {self.pdk_path}
        {macro_lib_cmds_sta}read_verilog {v_net}
        link_design {base}
        read_sdc {abs_sdc}
        report_checks -path_delay max -fields {{slew cap input_pins nets fanout}} -format full_clock_expanded -group_count 100 > {os.path.join(root, 'reports', 'timing.rpt')}
        report_power > {os.path.join(root, 'reports', 'power.rpt')}
        exit
        """
        with open(os.path.join(root, "sta.tcl"), 'w') as f: f.write(tcl)

        def task():
            self.synth_running = True
            self.synth_error = None
            try:
                self.queue.put(("[SYS]", "Starting Synthesis Flow..."))
                
                # --- STEP 1: YOSYS ---
                try:
                    # We pipe output to a file AND the GUI queue
                    plugins_dir = os.path.abspath(os.path.join(REPO_ROOT, "third-party", "plugins"))
                    ghdl_prefix = os.path.join(plugins_dir, "ghdl")
                    synth_env = os.environ.copy()
                    synth_env["GHDL_PREFIX"] = ghdl_prefix
                    curr_ld = synth_env.get("LD_LIBRARY_PATH", "")
                    synth_env["LD_LIBRARY_PATH"] = f"{plugins_dir}:{curr_ld}" if curr_ld else plugins_dir
                    log_path = os.path.join(root, "reports", "synthesis.log")
                    with open(log_path, "w") as log_file:
                        p1 = subprocess.Popen(f"yosys synth.ys", shell=True, cwd=root, env=synth_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                        
                        for line in iter(p1.stdout.readline, ''):
                            line = line.strip()
                            if line:
                                self.queue.put(("[YOSYS]", line)) 
                                log_file.write(line + "\n")
                        p1.wait()
                        if p1.returncode != 0: raise Exception("Yosys Failed")
                except Exception as e:
                    self.synth_error = f"Yosys Crash: {e}"
                    self.queue.put(("[SYS]", f"[ERR] Yosys Crash: {e}")); return

                # --- STEP 2: OPENSTA ---
                try:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    # Check candidate OpenSTA binary locations:
                    # 1. Vendored third-party build
                    # 2. Core synthengine build
                    # 3. System PATH (e.g. /usr/local/bin/sta or /usr/bin/sta)
                    sta_candidates = [
                        os.path.join(REPO_ROOT, "third-party", "OpenSTA", "build", "sta"),
                        os.path.join(REPO_ROOT, "core", "synthengine", "build", "OpenSTA_build", "sta"),
                        os.path.join(base_dir, "core", "synthengine", "build", "OpenSTA_build", "sta"),
                        shutil.which("sta"),
                        "sta",
                    ]
                    sta_bin = None
                    for c in sta_candidates:
                        if c and (os.path.isabs(c) and os.path.isfile(c) and os.access(c, os.X_OK)):
                            sta_bin = c
                            break
                    if not sta_bin:
                        sta_bin = shutil.which("sta") or "sta"

                    p2 = subprocess.Popen(f'"{sta_bin}" sta.tcl', shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                    for line in iter(p2.stdout.readline, ''):
                        line = line.strip()
                        if line:
                            self.queue.put(("[STA]", line)) 
                    p2.wait()
                    if p2.returncode != 0: raise Exception("OpenSTA Failed")
                except Exception as e:
                    self.synth_error = f"STA Crash: {e}"
                    self.queue.put(("[SYS]", f"[ERR] STA Crash: {e}")); return

                self.queue.put(("[SYS]", "Synthesis & Timing Complete."))

                # --- STEP 3: DFT SCAN INSERTION (If Enabled) ---
                dft_active = getattr(self, 'enable_dft', False) or (
                    hasattr(self, 'tab_synth')
                    and getattr(self.tab_synth, 'chk_dft', None)
                    and self.tab_synth.chk_dft.isChecked()
                )
                if dft_active:
                    try:
                        try:
                            from dft.dft_engine import DFTEngine
                        except (ImportError, ModuleNotFoundError):
                            from dft.dft_engine import DFTEngine
                        pdk_name = self.active_pdk.get("name", "sky130") if self.active_pdk else "sky130"
                        
                        s_in = self.tab_synth.in_scan_in.text().strip() if hasattr(self.tab_synth, 'in_scan_in') else "scan_in"
                        s_out = self.tab_synth.in_scan_out.text().strip() if hasattr(self.tab_synth, 'in_scan_out') else "scan_out"
                        s_en = self.tab_synth.in_scan_en.text().strip() if hasattr(self.tab_synth, 'in_scan_en') else "scan_en"
                        s_clk = self.tab_synth.in_scan_clk.text().strip() if hasattr(self.tab_synth, 'in_scan_clk') else "clk"
                        clamp = self.tab_synth.chk_clamp.isChecked() if hasattr(self.tab_synth, 'chk_clamp') else True
                        
                        dft_eng = DFTEngine(
                            netlist_path=v_net,
                            top_module=base,
                            pdk=pdk_name,
                            scan_in_port=s_in or "scan_in",
                            scan_out_port=s_out or "scan_out",
                            scan_en_port=s_en or "scan_en",
                            scan_clk_port=s_clk or "clk",
                            clamp_macros=clamp,
                        )
                        scandef_file = os.path.join(root, "results", "design.scandef")
                        scan_net_file = os.path.join(root, "netlist", f"{base}_scan.v")
                        dft_eng.stitch_scan_chain(scan_net_file, scandef_file)
                        self.queue.put(("[DFT]", f"Generated SCANDEF: {scandef_file} ({len(dft_eng.scan_cells)} scan cells)"))
                    except Exception as e:
                        self.queue.put(("[DFT]", f"[WARN] DFT Scan Insertion Warning: {e}"))

                self.queue.put(("UPDATE_DASHBOARD", None)) # Trigger UI update
            except Exception as e:
                self.synth_error = str(e)
                self.queue.put(("[SYS]", f"[ERR] Synthesis Flow Error: {e}"))
            finally:
                self.synth_running = False
        
        self.synth_running = True
        self.synth_error = None
        threading.Thread(target=task, daemon=True).start()

    def run_simulation(self):
        if self.current_file: self.save_file()
        _, base = self.get_context()
        if not base:
            if hasattr(self, 'project_config') and self.project_config:
                base = self.project_config.get("top_module")
        if not base:
            self.log_system("[ERR] Cannot determine top module for simulation.")
            return

        root = self.prep_workspace(base)
        src_v = glob.glob(os.path.join(root, "source", "*.v")) + \
                glob.glob(os.path.join(root, "source", "*.sv"))
        if not src_v:
            self.log_system("No source files found in source/!", "ERR")
            return

        out_bin = os.path.join(root, f"{base}.out")
        cmd = ["iverilog", "-g2012", "-o", out_bin] + src_v

        def task():
            try:
                self.queue.put(("[SYS]", f"Compiling RTL & Testbenches ({len(src_v)} files)..."))
                comp = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
                if comp.returncode != 0:
                    err_msg = comp.stderr.strip() or comp.stdout.strip()
                    self.queue.put(("[SYS]", f"[ERR] iverilog compilation failed:\n{err_msg}"))
                    return

                self.queue.put(("[SYS]", "Simulating with vvp..."))
                proc = subprocess.Popen(["vvp", out_bin], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(proc.stdout.readline, ''):
                    self.queue.put(("[SYS]", line.strip()))
                proc.wait()

                # Find generated VCD
                vcd_candidates = glob.glob(os.path.join(root, "*.vcd")) + glob.glob(os.path.join(root, "source", "*.vcd"))
                if vcd_candidates:
                    latest_vcd = max(vcd_candidates, key=os.path.getmtime)
                    self.queue.put(("LOAD_WAVES", latest_vcd))
                    self.queue.put(("[SYS]", f"[OK] Waveform successfully loaded: {os.path.basename(latest_vcd)}"))
                else:
                    self.queue.put(("[SYS]", "[WARN] Simulation finished, but no .vcd was generated. Ensure testbench calls $dumpfile and $dumpvars."))
            except Exception as e:
                self.queue.put(("[SYS]", f"[ERR] Simulation Error: {e}"))

        threading.Thread(target=task, daemon=True).start()

    # --- HELPERS (Copied & Cleaned) ---
    def setup_toolbar(self):
        tb = QToolBar(); self.addToolBar(tb); tb.setMovable(False)
        act_new = QAction("New", self); act_new.setShortcut("Ctrl+N"); act_new.triggered.connect(self.new_file); tb.addAction(act_new)
        act_save = QAction("Save", self); act_save.setShortcut("Ctrl+S"); act_save.triggered.connect(self.save_file); tb.addAction(act_save)
        
        act_new_proj = QAction("New Project...", self)
        act_new_proj.setShortcut("Ctrl+Shift+N")
        act_new_proj.triggered.connect(self.new_project)
        tb.addAction(act_new_proj)

        act_open = QAction("Open Project", self)
        act_open.setShortcut("Ctrl+Shift+O")
        act_open.triggered.connect(lambda: self.open_project())
        tb.addAction(act_open)

        self.btn_recent_menu = QToolButton(self)
        self.btn_recent_menu.setText("Recent Projects")
        self.btn_recent_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_recent = QMenu(self)
        self.btn_recent_menu.setMenu(self.menu_recent)
        self.menu_recent.aboutToShow.connect(self._populate_recent_menu)
        tb.addWidget(self.btn_recent_menu)

        tb.addSeparator()
        self.btn_front = QPushButton("Frontend"); self.btn_front.setCheckable(True); self.btn_front.setChecked(True)
        self.btn_front.clicked.connect(lambda: self.switch_world(0))
        self.btn_back = QPushButton("Backend"); self.btn_back.setCheckable(True)
        self.btn_back.clicked.connect(lambda: self.switch_world(1))
        tb.addWidget(self.btn_front); tb.addWidget(self.btn_back)
        tb.addSeparator()
        self.lbl_proj = QLabel(" Untitled "); tb.addWidget(self.lbl_proj)
        tb.addSeparator()
        act_set = QAction("Settings", self); act_set.triggered.connect(self.open_settings); tb.addAction(act_set)

    def _populate_recent_menu(self):
        self.menu_recent.clear()
        import project_registry
        projects = project_registry.get_registered_projects()
        if not projects:
            act = self.menu_recent.addAction("No Recent Projects")
            act.setEnabled(False)
            return

        for p in projects:
            title = f"{p['name']} ({p['top']} | {p['pdk']})"
            act = self.menu_recent.addAction(title)
            act.setToolTip(p['path'])
            target_path = p['path']
            act.triggered.connect(lambda checked, path=target_path: self.open_project(path))

    def new_project(self):
        from projectwizard.codes import SilisProjectWizard
        wizard = SilisProjectWizard(self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            self.open_project(wizard.project_path)

    def open_project(self, project_path=None):
        import project_registry
        if not project_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open Silis Project", os.path.expanduser("~"), "Silis Project (*.silisproj);;All Files (*)"
            )
            if not file_path:
                return
            project_path = file_path

        if os.path.isdir(project_path):
            proj_file = os.path.join(project_path, "silis.silisproj")
        else:
            proj_file = project_path

        if not os.path.isfile(proj_file):
            QMessageBox.warning(self, "Error", f"Project file not found:\n{proj_file}")
            return

        try:
            with open(proj_file, 'r') as f:
                self.project_config = json.load(f)

            self.cwd = os.path.dirname(os.path.abspath(proj_file))
            self.project_path = self.cwd
            os.chdir(self.cwd)
            project_registry.register_project(self.cwd)

            pdk_name = self.project_config.get("pdk", "sky130")
            self.active_pdk = next((cfg for cfg in self.pdk_mgr.configs if cfg['name'] == pdk_name), None)
            if not self.active_pdk:
                self.pdk_mgr.crawl_volare()
                self.active_pdk = next((cfg for cfg in self.pdk_mgr.configs if pdk_name in cfg['name'].lower()), None)
            if hasattr(self, 'backend_widget') and self.backend_widget:
                self.backend_widget.active_pdk = self.active_pdk
                if hasattr(self.backend_widget, 'reset_backend'):
                    self.backend_widget.reset_backend()

            # Clear synthesis dashboard logs and error lists
            if hasattr(self, 'tab_synth') and self.tab_synth:
                if hasattr(self.tab_synth, 'log_main'):
                    self.tab_synth.log_main.clear()
                if hasattr(self.tab_synth, 'list_err'):
                    self.tab_synth.list_err.clear()
                if hasattr(self.tab_synth, 'card_status'):
                    self.tab_synth.card_status.setText("READY")
                    self.tab_synth.card_status.setStyleSheet("font-size:14px; font-weight:bold; padding:10px; border-radius:6px; border: 1px solid gray;")
                if hasattr(self.tab_synth, 'val_wns'):
                    self.tab_synth.val_wns.setText("--")
                if hasattr(self.tab_synth, 'val_area'):
                    self.tab_synth.val_area.setText("--")
                if hasattr(self.tab_synth, 'val_gates'):
                    self.tab_synth.val_gates.setText("--")
                if hasattr(self.tab_synth, 'preview'):
                    self.tab_synth.preview.clear()

            self.tab_compile.explorer.set_cwd(self.cwd)
            proj_name = self.project_config.get("project_name", os.path.basename(self.cwd))
            self.setWindowTitle(f"Silis — Silicon Scaffold v2.1 - [{proj_name}]")
            self.lbl_proj.setText(f" {proj_name} ")

            # Close / clean editor tabs before loading new primary source file
            if hasattr(self.tab_compile, 'editor') and self.tab_compile.editor:
                for i in range(self.tab_compile.editor.count() - 1, -1, -1):
                    self.tab_compile.editor.close_tab(i)
                self.current_file = None

            top_mod = self.project_config.get("top_module", "")
            top_v = os.path.join(self.cwd, "source", f"{top_mod}.v")
            top_vhd = os.path.join(self.cwd, "source", f"{top_mod}.vhd")
            if os.path.isfile(top_v):
                self.open_file_in_editor(top_v)
            elif os.path.isfile(top_vhd):
                self.open_file_in_editor(top_vhd)
            else:
                src_dir = os.path.join(self.cwd, "source")
                if os.path.isdir(src_dir):
                    v_files = [os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.endswith(('.v', '.sv', '.vhd', '.vhdl'))]
                    if v_files:
                        self.open_file_in_editor(v_files[0])

            self.log_system(f"Loaded Project: {proj_name} at {self.cwd}")
            if hasattr(self.tab_compile, 'explorer_panel'):
                self.tab_compile.explorer_panel.scan_workspace()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")

    def open_intake_wizard(self):
        from intake.intake_dialog import IntakeWizardDialog
        dlg = IntakeWizardDialog(self, self.project_config)
        dlg.intake_completed.connect(self._apply_intake_result)
        dlg.exec()

    def _apply_intake_result(self, result: dict):
        if not self.project_config:
            self.project_config = {}

        self.project_config["top_module"] = result.get("top_module", "")
        self.project_config["rtl_files"] = result.get("rtl_files", [])
        self.project_config["vhdl_work"] = result.get("vhdl_work", "work")
        self.project_config["vhdl_std"] = result.get("vhdl_std", "08")

        # Save project config to silis.silisproj if cwd is set
        if hasattr(self, 'cwd') and os.path.isdir(self.cwd):
            proj_file = os.path.join(self.cwd, "silis.silisproj")
            try:
                with open(proj_file, "w") as f:
                    json.dump(self.project_config, f, indent=2)
            except Exception as e:
                print(f"[INTAKE] Note saving project config: {e}")

        # Open the generated Verilog file in the editor
        rtl_files = result.get("rtl_files", [])
        if rtl_files and os.path.isfile(rtl_files[0]):
            self.open_file_in_editor(rtl_files[0])

        # Switch to synthesis tab
        if hasattr(self, 'frontend_tabs'):
            self.frontend_tabs.setCurrentIndex(3)

        self.log_system(f"Ingested & Lowered Top Module: {result.get('top_module', '')}")

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()
    def log_system(self, msg, tag="SYS"):
        # ROUTE SYSTEM MESSAGES TO STATUS BAR & SYNTH LOG
        formatted = f"[{tag}] {msg}"
        self.statusBar().showMessage(formatted, 5000)
        if hasattr(self, 'tab_synth') and hasattr(self.tab_synth, 'log_main'):
            self.tab_synth.log_main.append(formatted)
        # Also push it to the terminal via a cat command as requested
        try:
            root = self.get_proj_root(self.get_context()[1] or "design")
            log_dir = os.path.join(root, "reports")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "sys.log")
            with open(log_path, "a") as f:
                f.write(f"[{tag}] {msg}\n")
        except Exception:
            pass
    def change_directory(self, path):
        if os.path.exists(path):
            os.chdir(path); self.cwd = os.getcwd(); self.tab_compile.explorer.set_cwd(self.cwd)
            self.log_system(f"CD -> {self.cwd}", "SYS")

    def open_file_in_editor(self, path, line=None, col=None):
        if os.path.exists(path):
            self.tab_compile.editor.open_file(path, line, col)
            self.current_file = path; self.lbl_proj.setText(os.path.basename(path))

    def _trigger_find_instance(self):
        if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'explorer_panel'):
            self.tab_compile.explorer_panel.open_find_instance_dialog()

    def show_module_schematic(self, module_name):
        if hasattr(self, 'tab_schematic'):
            self.switch_frontend_tab(1)
            self.tab_schematic.on_module_clicked(module_name)

    def add_waveform_signal(self, signal_name):
        if hasattr(self, 'tab_sim') and hasattr(self.tab_sim, 'wave_view'):
            self.switch_frontend_tab(2)
            # Try to reveal or add signal if wave server supports it
            js = f"window.postMessage({{ type: 'addSignal', name: '{signal_name}' }}, '*');"
            if hasattr(self.tab_sim.wave_view, 'page'):
                self.tab_sim.wave_view.page().runJavaScript(js)

    def open_gds3d(self, path):
        if os.path.exists(path):
            self.backend_widget.gds3d_port.load_gds(path)
            self.switch_world(1)
            self.backend_widget.viz_tabs.setCurrentIndex(1)
            self.current_file = path; self.lbl_proj.setText(os.path.basename(path))

    def handle_terminal_input(self):
        """Legacy shim — real input now comes from VSCodeTerminalWidget via handle_terminal_cmd."""
        pass

    def handle_terminal_cmd(self, cmd):
        """Called by VSCodeTerminalWidget after the user presses Enter."""
        terminal = self.tab_compile.terminal

        # ── built-in: cd ──────────────────────────────────────────────────
        if cmd.strip() == "cd":
            self.change_directory(os.path.expanduser("~"))
            terminal._update_prompt()
            return
        if cmd.startswith("cd "):
            target = cmd[3:].strip()
            if target == "..":    target = os.path.dirname(self.cwd)
            elif target == "~":   target = os.path.expanduser("~")
            else:                 target = os.path.join(self.cwd, os.path.expanduser(target))
            if os.path.isdir(target):
                self.change_directory(target)
                terminal._update_prompt()
            else:
                terminal.append_output(f"cd: {target}: No such file or directory", color="#f44747")
            return

        # ── built-in: clear ───────────────────────────────────────────────
        if cmd.strip() in ("clear", "cls"):
            terminal.clear_log()
            return

        # ── shell command — run async, stream output ───────────────────────
        def _run():
            try:
                proc = subprocess.Popen(
                    cmd, shell=True,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=self.cwd, bufsize=1
                )
                for line in iter(proc.stdout.readline, ''):
                    self.queue.put(("TERM_OUT", line.rstrip()))
                proc.wait()
                if proc.returncode != 0:
                    self.queue.put(("TERM_OUT", f"[exit {proc.returncode}]"))
            except Exception as e:
                self.queue.put(("TERM_OUT", f"[ERR] {e}"))
        threading.Thread(target=_run, daemon=True).start()


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
            content = self.tab_compile.editor.toPlainText()
            # Safety Guard: Never overwrite non-empty disk files with empty content from an unready editor widget
            if not content and os.path.exists(self.current_file) and os.path.getsize(self.current_file) > 0:
                self.log_system(f"Warning: Editor content was empty; preserved existing {os.path.basename(self.current_file)}", "WARN")
                return
            with open(self.current_file, 'w') as f: f.write(content)
            self.log_system(f"Saved {os.path.basename(self.current_file)}")
            self.lbl_proj.setText(os.path.basename(self.current_file))
            if self.current_file.endswith(('.v', '.sv')):
                self.tab_schem.invalidate_cache()

    def get_context(self):
        if hasattr(self, 'project_config') and self.project_config and self.project_config.get("top_module"):
            top = self.project_config["top_module"]
            return top, top.replace("tb_", "").replace("_tb", "")
        content = self.tab_compile.editor.toPlainText()
        if not content and self.current_file and os.path.exists(self.current_file):
            try:
                with open(self.current_file, 'r') as f:
                    content = f.read()
            except Exception:
                pass
        m = re.search(r'(?:module|entity)\s+(\w+)', content, re.IGNORECASE)
        if not m: return None, None
        return m.group(1), m.group(1).replace("tb_", "").replace("_tb", "")

    def get_proj_root(self, base):
        cwd = os.path.abspath(self.cwd)
        
        # 1. Search upwards for a .silisproj file
        curr = cwd
        while curr and curr != '/' and curr != os.path.dirname(curr):
            try:
                if any(f.endswith('.silisproj') for f in os.listdir(curr) if os.path.isfile(os.path.join(curr, f))):
                    return curr
            except Exception:
                pass
            curr = os.path.dirname(curr)
            
        # 2. If we are in a known subfolder, the parent is the root
        if os.path.basename(cwd) in ["source", "netlist", "reports", "results"]:
            return os.path.dirname(cwd)
            
        # 3. Default: the current directory is the project root
        return cwd

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
        had_items = False
        while not self.queue.empty():
            had_items = True
            item = self.queue.get()
            
            if isinstance(item, tuple): tag, content = item
            else: tag, content = "SYS", str(item)

            # [NEW] Route terminal command output to the VSCode terminal widget
            if tag == "TERM_OUT":
                self.tab_compile.terminal.append_output(content)

            # [NEW] Route Backend-specific messages to Backend Terminal
            elif tag == "[BACKEND]":
                if hasattr(self, 'backend_widget') and self.backend_widget:
                    if hasattr(self.backend_widget, 'append_output'):
                        self.backend_widget.append_output(content)
                    elif hasattr(self.backend_widget, 'term_log'):
                        self.backend_widget.term_log.append(str(content))
            elif tag == "[BACKEND_GDS_DONE]":
                if not getattr(self, "headless", False):
                    QMessageBox.information(self, "GDS Generation Complete", f"GDS layout successfully exported to:\n\n{content}")
                else:
                    print(f"[BACKEND_GDS_DONE] GDS layout successfully exported to: {content}")

            # Existing Routing...
            elif tag == "LOAD_WAVES":
                self.tab_waves.load_file(content)
                self.frontend_tabs.setCurrentIndex(1)

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

        # Dynamic poll backoff: throttle when idle, accelerate when active
        if hasattr(self, 'queue_timer'):
            if had_items and self.queue_timer.interval() != 40:
                self.queue_timer.setInterval(40)
            elif not had_items and self.queue_timer.interval() != 200:
                self.queue_timer.setInterval(200)

    def load_violation_log(self): 
        self.frontend_tabs.setCurrentIndex(3)
        self.harvest_logs(self.get_proj_root(self.get_context()[1] or "design"))
        
    def check_dependencies(self):
        if not shutil.which("sta"): self.log_system("OpenSTA not found!", "ERR")
    
    def update_ui_labels(self): pass

if __name__ == "__main__":
    import sys
    from core.cli.main import handle_cli
    if handle_cli(sys.argv[1:]):
        sys.exit(0)

    # Enable OpenGL context sharing & pre-import WebEngine before QApplication
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    try:
        import PyQt6.QtWebEngineWidgets
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    # Try loading settings
    font_fam = USER_SETTINGS.get("font_family", "Consolas")
    font_size = USER_SETTINGS.get("font_size", 11)
    
    # Check if a project file or initial tab was requested for GUI launch
    proj_to_open = None
    target_tab = None
    argv_copy = list(sys.argv[1:])
    idx = 0
    while idx < len(argv_copy):
        arg = argv_copy[idx]
        if arg in ["--tab", "-t"] and idx + 1 < len(argv_copy):
            target_tab = argv_copy[idx + 1].lower()
            argv_copy.pop(idx)
            argv_copy.pop(idx)
        elif not arg.startswith("-") and (arg.endswith(".json") or os.path.isdir(arg)):
            proj_to_open = arg
            argv_copy.pop(idx)
        else:
            idx += 1

    # Pre-load alias database so IDE doesn't block later
    SSAForge.load_aliases()
    
    window = SilisIDE(project_file=proj_to_open)
    
    # If initial tab was requested, or auto-detect current project stage
    if target_tab:
        if target_tab in ["synth", "synthesis", "4"]:
            window.switch_world(0)
            window.frontend_tabs.setCurrentIndex(3)
        elif target_tab in ["schem", "schematic", "3"]:
            window.switch_world(0)
            window.frontend_tabs.setCurrentIndex(2)
        elif target_tab in ["waves", "waveform", "2"]:
            window.switch_world(0)
            window.frontend_tabs.setCurrentIndex(1)
        elif target_tab in ["compile", "editor", "1"]:
            window.switch_world(0)
            window.frontend_tabs.setCurrentIndex(0)
        elif target_tab in ["layout", "backend", "floorplan", "place", "route"]:
            window.switch_world(1)
            window.backend_widget.viz_tabs.setCurrentIndex(0)
    elif proj_to_open and window.project_config:
        # Smart auto-detection: if DEF exists, open Layout view; else if netlist exists, open Synthesis view
        top = window.project_config.get("top_module", "design")
        root = os.path.dirname(os.path.abspath(proj_to_open)) if proj_to_open.endswith(".json") else os.path.abspath(proj_to_open)
        if os.path.exists(os.path.join(root, "results", "temp.def")) or os.path.exists(os.path.join(root, "results", "design.def")):
            window.switch_world(1)
        elif os.path.exists(os.path.join(root, "netlist", f"{top}_netlist.v")) or os.path.exists(os.path.join(root, "netlist", "design.v")):
            window.switch_world(0)
            window.frontend_tabs.setCurrentIndex(3) # SYNTHESIS TAB

    window.show()
    window.raise_()
    window.activateWindow()
    
    sys.exit(app.exec())
