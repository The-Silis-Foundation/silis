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
from pathlib import Path
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

# Importing extracted modules from core
from config import (
    THEMES, USER_SETTINGS, save_user_settings,
    EDITOR_CONFIG, save_editor_config, save_custom_palette, COLOR_CONFIG_FILE, EDITOR_CONFIG_FILE
)
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

# Re-export Python SDK layer & SiliconCompiler
try:
    from sdk import (
        Project,
        Pipeline,
        Floorplan,
        MacroInstance,
        Margins,
        Orientation,
        Halo,
        legalize_coord,
        PowerNetwork,
        PowerDomain,
        IsolationRule,
        LevelShifterRule,
        TimingGraph,
        TimingPin,
        Layout,
        LayoutNet,
        SignoffReport,
        SynthesisReport,
        DRCReport,
        DFTSignoffReport,
        GLSSignoffReport,
        LVSSignoffReport,
        TapeoutManifestReport,
        create_project,
        load_project,
        get_utilization,
        enquire_utilization,
        get_required_area,
        suggest_box,
        auto_place_regions,
        view_layout,
        view_gds3d,
        view_waveforms,
        view_schematic,
        open_gui,
        open_floorplanner,
        open_ioplacer,
        view_magic,
        view_gtkwave,
        view_openroad_gui,
        sc,
        from_sc,
        to_sc,
        _SC_AVAILABLE,
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

        # Right: Top Area (Monaco Code + sv-pathfinder Schematic) & Bottom Area (Terminal + Waveform)
        self.right_split = QSplitter(Qt.Orientation.Vertical)
        self.split.addWidget(self.right_split)
        
        # Top Container: Splitter between Monaco Editor and Schematic Canvas
        self.top_work_split = QSplitter(Qt.Orientation.Horizontal)
        
        # Code Container
        self.code_container = QWidget()
        c_lay = QVBoxLayout(self.code_container); c_lay.setContentsMargins(0,0,0,0)
        self.editor = VSCodeEditorTabs()
        c_lay.addWidget(self.editor)
        self.top_work_split.addWidget(self.code_container)

        # Schematic Container (Initially hidden until compile/schematic requested)
        from schematicviewer.graphiccanvas import SchematicTab
        self.schem_container = QWidget()
        s_lay = QVBoxLayout(self.schem_container); s_lay.setContentsMargins(0,0,0,0)
        self.schem_view = SchematicTab(self.ide)
        s_lay.addWidget(self.schem_view)
        self.top_work_split.addWidget(self.schem_container)
        self.schem_container.hide() # Hidden initially
        
        self.top_work_split.setStretchFactor(0, 1)
        self.top_work_split.setStretchFactor(1, 1)
        self.right_split.addWidget(self.top_work_split)
        
        # Bottom Container: Tabbed Terminal, Log & Waveform Viewer
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setDocumentMode(True)
        
        # Tab 1: VS Code-style Terminal
        self.terminal = VSCodeTerminalWidget(self.ide)
        self.bottom_tabs.addTab(self.terminal, "Terminal")

        # Tab 2: Build / Flow Log
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("font-family:Consolas, 'Courier New', monospace; font-size:11px; background-color:#1e1e1e; color:#d4d4d4; border:none; padding:6px;")
        self.bottom_tabs.addTab(self.log_view, "Log")
        
        # Tab 3: ROHD Waveform Viewer
        from signalpeeker.code import SignalPeeker
        self.wave_view = SignalPeeker(self.ide)
        self.bottom_tabs.addTab(self.wave_view, "Waveform")
        
        # Custom Bottom Tab Corner Widget: Maximize/Restore Toggle Button (⛶)
        self.btn_fullscreen_wave = QPushButton("⛶")
        self.btn_fullscreen_wave.setFixedSize(26, 22)
        self.btn_fullscreen_wave.setToolTip("Maximize / Restore Bottom Panel")
        self.btn_fullscreen_wave.clicked.connect(self._toggle_maximize_bottom_panel)
        self.bottom_tabs.setCornerWidget(self.btn_fullscreen_wave, Qt.Corner.TopRightCorner)
        self._bottom_panel_maximized = False
        self._saved_right_split_sizes = None
        
        self.right_split.addWidget(self.bottom_tabs)
        
        self.split.setStretchFactor(0, 1); self.split.setStretchFactor(1, 4)
        self.split.setSizes([1200, 8800])
        self.right_split.setStretchFactor(0, 8); self.right_split.setStretchFactor(1, 2)
        self.right_split.setSizes([8000, 2000])

    def show_schematic(self, show=True):
        if show:
            self.schem_container.show()
            self.top_work_split.setSizes([5000, 5000])
        else:
            self.schem_container.hide()

    def _toggle_maximize_bottom_panel(self):
        if not self._bottom_panel_maximized:
            # Save current sizes and maximize bottom panel in-place
            self._saved_right_split_sizes = self.right_split.sizes()
            self.top_work_split.hide()
            self.right_split.setSizes([0, 10000])
            self._bottom_panel_maximized = True
            self.btn_fullscreen_wave.setText("❐")
            self.btn_fullscreen_wave.setToolTip("Restore Bottom Panel")
        else:
            # Restore previous split sizes
            self.top_work_split.show()
            if self._saved_right_split_sizes and sum(self._saved_right_split_sizes) > 0:
                self.right_split.setSizes(self._saved_right_split_sizes)
            else:
                self.right_split.setSizes([6000, 4000])
            self._bottom_panel_maximized = False
            self.btn_fullscreen_wave.setText("⛶")
            self.btn_fullscreen_wave.setToolTip("Maximize Bottom Panel")

class CustomPaletteDialog(QDialog):
    """Interactive Custom Color Palette Designer dialog saving to ~/.silis/colorconfig.json."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Color Palette Designer")
        self.resize(460, 480)
        self.layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_edit = QLineEdit("Custom")
        form.addRow("Palette Name:", self.name_edit)

        base_palette = THEMES.get("Catppuccin Mocha", {})
        self.color_edits = {}
        fields = [
            ("bg", "Background"),
            ("fg", "Foreground (Text)"),
            ("sel", "Selection"),
            ("kw", "Keyword 1 (module, endmodule)"),
            ("kw2", "Keyword 2 (input, output)"),
            ("str", "Strings"),
            ("comment", "Comments"),
            ("num", "Numbers"),
            ("ident", "Identifiers")
        ]
        for key, label in fields:
            curr_val = base_palette.get(key, "#ffffff")
            le = QLineEdit(curr_val)
            lbl = QLabel()
            lbl.setFixedSize(22, 22)
            if QColor(curr_val).isValid():
                lbl.setStyleSheet(f"background-color: {curr_val}; border: 1px solid #555; border-radius: 3px;")
            btn = QPushButton("Pick")
            btn.clicked.connect(lambda ch, _e=le, _l=lbl: self._pick(_e, _l))
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(le)
            h.addWidget(lbl)
            h.addWidget(btn)
            form.addRow(f"{label}:", w)
            self.color_edits[key] = le

        self.layout.addLayout(form)
        bb = QHBoxLayout()
        btn_save = QPushButton("Save Palette")
        btn_save.clicked.connect(self._save_palette)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        bb.addStretch()
        bb.addWidget(btn_cancel)
        bb.addWidget(btn_save)
        self.layout.addLayout(bb)

    def _pick(self, edit_widget, label_widget):
        init_col = QColor(edit_widget.text()) if QColor(edit_widget.text()).isValid() else QColor("#ffffff")
        col = QColorDialog.getColor(init_col, self, "Select Color")
        if col.isValid():
            hex_col = col.name()
            edit_widget.setText(hex_col)
            label_widget.setStyleSheet(f"background-color: {hex_col}; border: 1px solid #555; border-radius: 3px;")

    def _save_palette(self):
        pname = self.name_edit.text().strip() or "Custom"
        pal = {}
        for k, le in self.color_edits.items():
            pal[k] = le.text().strip()
        pal["margin_bg"] = pal.get("bg", "#181825")
        pal["margin_fg"] = pal.get("fg", "#cdd6f4")
        save_custom_palette(pname, pal)
        QMessageBox.information(self, "Palette Saved", f"Custom palette '{pname}' committed to ~/.silis/colorconfig.json")
        self.accept()


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

        # Radix Display Preference (Hexadecimal vs Binary)
        self.cb_radix = QComboBox()
        self.cb_radix.addItem("Hexadecimal (e.g. 0xE)", "hex")
        self.cb_radix.addItem("Binary (e.g. 4'b1110)", "bin")
        curr_radix = USER_SETTINGS.get("radix_preference", "hex").lower()
        self.cb_radix.setCurrentIndex(0 if curr_radix == "hex" else 1)
        form_app.addRow("Value Radix (Editor / Schematic):", self.cb_radix)
        
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
        USER_SETTINGS["radix_preference"] = self.cb_radix.currentData() or "hex"
        USER_SETTINGS["custom_theme"] = THEMES["Custom"]
        USER_SETTINGS["external_editor"] = self.e_ext_edit.text()
        USER_SETTINGS["lod_enabled"] = self.chk_lod.isChecked()
        USER_SETTINGS["lod_std_cells"] = self.spin_lod_std.value()
        USER_SETTINGS["lod_nets"] = self.spin_lod_nets.value()
        save_user_settings(USER_SETTINGS)

        # Synchronize and save to ~/.silis/editorconfig.json
        EDITOR_CONFIG["font_family"] = font_family
        EDITOR_CONFIG["font_size"] = font_size
        EDITOR_CONFIG["editor_backend"] = editor_backend
        save_editor_config(EDITOR_CONFIG)

        
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
        pname = pdk_config.get('name', 'None') if pdk_config else 'None'
        if hasattr(self, 'backend_widget') and self.backend_widget:
            self.backend_widget.active_pdk = pdk_config
        if hasattr(self, 'btn_pdk_status') and self.btn_pdk_status:
            self.btn_pdk_status.setText(f"⚙ PDK: {pname}")
        if hasattr(self, 'tab_synth') and hasattr(self.tab_synth, 'lbl_pdk'):
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

    def _on_check_updates(self):
        try:
            from core.updater.delta_updater import check_for_updates_interactive
            check_for_updates_interactive(parent=self)
        except Exception as e:
            QMessageBox.warning(self, "Update Check Error", f"Unable to check for updates: {e}")

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
        
        # World 1: Frontend Pure IDE Workspace (CompileTab with Code, Wave, Schematic, Terminal & Log)
        self.tab_compile = CompileTab(self)
        self.tab_waves = self.tab_compile.wave_view
        self.tab_schem = self.tab_compile.schem_view
        self.tab_synth = SynthesisTab(self) # Headless/shared report generator & metrics model
        self.stack.addWidget(self.tab_compile)
        
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
        
        # ASCII Spinning Roller for Simulation Status Bar
        self.sim_spinner_timer = QTimer(self)
        self.sim_spinner_frames = ["-", "\\", "|", "/"]
        self.sim_spinner_idx = 0
        self.sim_spinner_label = "UVM RUNNING"
        self.sim_spinner_timer.timeout.connect(self._step_sim_spinner)
        
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

                # 2. Shallow check in rtl/, source/ or top-level project root
                if not target_file:
                    for ext in [".v", ".sv", ".vhd", ".vhdl"]:
                        for subdir in ["rtl", "source"]:
                            cand_src = os.path.join(self.cwd, subdir, f"{top_mod}{ext}")
                            if os.path.isfile(cand_src):
                                target_file = cand_src
                                break
                        if target_file:
                            break
                        cand_root = os.path.join(self.cwd, f"{top_mod}{ext}")
                        if os.path.isfile(cand_root):
                            target_file = cand_root
                            break

                # 3. Shallow search in rtl/ or source/ directory if top module specific file not matched
                if not target_file:
                    for subdir in ["rtl", "source"]:
                        src_dir = os.path.join(self.cwd, subdir)
                        if os.path.isdir(src_dir):
                            try:
                                for entry in os.listdir(src_dir):
                                    if top_mod in entry and os.path.isfile(os.path.join(src_dir, entry)):
                                        target_file = os.path.join(src_dir, entry)
                                        break
                            except Exception:
                                pass
                        if target_file:
                            break

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
                ("Go to: Terminal", lambda: (self.switch_world(0), hasattr(self, 'tab_compile') and self.tab_compile.bottom_tabs.setCurrentIndex(0))),
                ("Go to: Log", lambda: (self.switch_world(0), hasattr(self, 'tab_compile') and self.tab_compile.bottom_tabs.setCurrentIndex(1))),
                ("Go to: Waveform Tab", lambda: (self.switch_world(0), hasattr(self, 'tab_compile') and self.tab_compile.bottom_tabs.setCurrentIndex(2))),
                ("Go to: Schematic View", lambda: (self.switch_world(0), self.generate_schematic())),
                ("Go to: Synthesis PAT Report", lambda: (self.switch_world(0), hasattr(self, 'tab_synth') and self.tab_synth.open_markdown_report())),
                ("Go to: 3D Layout Viewer", lambda: (self.switch_world(1), self.backend_widget.viz_tabs.setCurrentIndex(1))),
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
                self.run_simulation()
                return True
            
            elif key == Qt.Key.Key_F2:
                if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'bottom_tabs'):
                    self.tab_compile.bottom_tabs.setCurrentIndex(2) # Switch to Waveform
                self.tab_waves.auto_load() 
                return True
            
            elif key == Qt.Key.Key_F3:
                self.generate_schematic()
                return True
            
            elif key == Qt.Key.Key_F4:
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
                self.switch_world(0)
                self.tab_compile.explorer.setFocus()
            elif txt == self.key_map["focus_editor"]: 
                self.switch_world(0)
                current_ed = self.tab_compile.editor.current_editor()
                if current_ed:
                    if hasattr(current_ed, 'run_js'): current_ed.run_js("editor.focus()")
                    if hasattr(current_ed, 'editor') and hasattr(current_ed.editor, 'web_view'): current_ed.editor.web_view.setFocus()
                else:
                    self.tab_compile.editor.setFocus()
            elif txt == self.key_map["focus_terminal"]: 
                self.switch_world(0)
                if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'bottom_tabs'):
                    self.tab_compile.bottom_tabs.setCurrentIndex(0)
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
        if not (hasattr(self, 'sim_spinner_timer') and self.sim_spinner_timer.isActive()):
            self.statusBar().clearMessage()
        if hasattr(self, 'sk_overlays'):
            for lbl in self.sk_overlays:
                lbl.deleteLater()
            self.sk_overlays = []

    def _step_sim_spinner(self):
        frame = self.sim_spinner_frames[self.sim_spinner_idx % len(self.sim_spinner_frames)]
        self.sim_spinner_idx += 1
        self.statusBar().showMessage(f"[{self.sim_spinner_label}] {frame} Executing simulation suite...")

    def start_sim_spinner(self, label="UVM RUNNING"):
        self.sim_spinner_label = label
        self.sim_spinner_idx = 0
        if hasattr(self, 'sim_spinner_timer'):
            self.sim_spinner_timer.start(100)
            self._step_sim_spinner()

    def stop_sim_spinner(self, final_msg="[OK] Simulation completed."):
        if hasattr(self, 'sim_spinner_timer'):
            self.sim_spinner_timer.stop()
        self.statusBar().showMessage(final_msg, 5000)

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
            
        if self.stack.currentIndex() == 0 and hasattr(self, 'tab_compile'):
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
        # Open schematic container in CompileTab
        if hasattr(self, 'tab_compile'):
            self.tab_compile.show_schematic(True)
            if hasattr(self.tab_compile.schem_view, 'ensure_engine'):
                self.tab_compile.schem_view.ensure_engine()
            base = None
            if hasattr(self, 'project_config') and self.project_config:
                base = self.project_config.get("top_module")
            if not base:
                _, base = self.get_context()
            if base:
                self.show_module_schematic(base)

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
        # Switch bottom drawer to Log tab (Tab index 1)
        if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'bottom_tabs'):
            self.tab_compile.bottom_tabs.setCurrentIndex(1)
        if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'log_view'):
            self.tab_compile.log_view.clear()

        # Clear the unified log before starting
        if hasattr(self, 'tab_synth') and hasattr(self.tab_synth, 'log_main'):
            self.tab_synth.log_main.clear()
        if hasattr(self, 'tab_synth') and hasattr(self.tab_synth, 'card_status'):
            self.tab_synth.card_status.setText("RUNNING...")
            self.tab_synth.card_status.setStyleSheet("background:#eaeef2; color:#57606a; font-weight:bold; padding:15px; border-radius:6px; border: 1px solid #d0d7de;")

        v_net = os.path.join(root, "netlist", f"{base}_netlist.v")
        
        src_v = []
        if hasattr(self, 'project_config') and self.project_config and self.project_config.get("rtl_files"):
            for f_path in self.project_config.get("rtl_files", []):
                abs_path = os.path.join(self.cwd, f_path) if not os.path.isabs(f_path) else f_path
                if not os.path.exists(abs_path):
                    # Smart healing: check relative to root, root/rtl, or root/source
                    for cand_dir in ["rtl", "source", ""]:
                        cand = os.path.join(root, cand_dir, os.path.basename(f_path)) if cand_dir else os.path.join(root, os.path.basename(f_path))
                        if os.path.exists(cand):
                            abs_path = cand
                            break
                src_v.append(abs_path)
        else:
            search_dirs = [d for d in [os.path.join(root, "rtl"), os.path.join(root, "source")] if os.path.isdir(d)]
            if not search_dirs:
                search_dirs = [root]
            for sdir in search_dirs:
                for pat in ("*.v", "*.sv", "*.vhd", "*.vhdl"):
                    for f in glob.glob(os.path.join(sdir, pat)):
                        bname = os.path.basename(f).lower()
                        if sdir == os.path.join(root, "rtl") or not any(x in bname for x in ["tb_", "_tb", "test_"]):
                            if f not in src_v:
                                src_v.append(f)
                    
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
        macro_lib_paths = []  # keep raw paths for deferred corner-aware emission
        macros = self.project_config.get('macros', []) if hasattr(self, 'project_config') and self.project_config else []
        if macros:
            volare_base = self.pdk_path.split("libs.ref")[0]
            lib_search = os.path.join(volare_base, "libs.ref", "*", "lib", "*.lib")
            for lib in glob.glob(lib_search):
                name = os.path.basename(lib).replace('.lib', '')
                if any(m in name for m in macros):
                    macro_lib_cmds_yosys += f"read_liberty -lib {lib}\n        "
                    macro_lib_paths.append(lib)  # defer — will be corner-qualified below

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
            # --- USER CONFIRMATION DIALOG (Yosys Script + DFT Controls) ---
            dlg = QDialog(self)
            dlg.setWindowTitle("Confirm Synthesis Script & Flow Configuration")
            dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
            dlg.resize(750, 480)
            
            theme_name = USER_SETTINGS.get("theme_name", "Catppuccin Mocha")
            theme = THEMES.get(theme_name, THEMES["Catppuccin Mocha"])
            dlg.setStyleSheet(f"QDialog {{ background-color: {theme['bg']}; color: {theme['fg']}; }} QLabel {{ color: {theme['fg']}; }}")
            
            dlg_layout = QVBoxLayout(dlg)
            dlg_layout.addWidget(QLabel("<b>Yosys Synthesis Commands:</b> (Uncomment 'flatten' to extract complete hierarchy)"))
            
            editor = ScintillaEditor(is_minimap=False, font_family=USER_SETTINGS.get("font_family", "Consolas"), font_size=USER_SETTINGS.get("font_size", 11), theme_name=theme_name)
            editor.set_lexer(".tcl")
            editor.setText(ys.strip())
            dlg_layout.addWidget(editor)

            # DFT Scan Insertion Configuration (Group Box)
            grp_dft = QGroupBox("Design For Test (DFT) & Scan Insertion Options")
            grp_dft.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #444; border-radius: 4px; margin-top: 8px; padding-top: 10px; }")
            dft_l = QHBoxLayout(grp_dft)
            dft_l.setContentsMargins(8, 4, 8, 4); dft_l.setSpacing(10)

            chk_dft_en = QCheckBox("Enable Scan Insertion")
            chk_dft_en.setStyleSheet("color: #2da44e; font-weight: bold;")
            init_dft = getattr(self, 'enable_dft', False) or (hasattr(self, 'tab_synth') and getattr(self.tab_synth, 'chk_dft', None) and self.tab_synth.chk_dft.isChecked())
            chk_dft_en.setChecked(bool(init_dft))

            in_sin = QLineEdit("scan_in"); in_sin.setPlaceholderText("Scan In"); in_sin.setFixedWidth(75)
            in_sout = QLineEdit("scan_out"); in_sout.setPlaceholderText("Scan Out"); in_sout.setFixedWidth(75)
            in_sen = QLineEdit("scan_en"); in_sen.setPlaceholderText("Scan En"); in_sen.setFixedWidth(75)
            in_sclk = QLineEdit("clk"); in_sclk.setPlaceholderText("Scan Clk"); in_sclk.setFixedWidth(60)
            chk_dft_clamp = QCheckBox("Clamp Macros")
            chk_dft_clamp.setChecked(True)

            dft_l.addWidget(chk_dft_en)
            dft_l.addWidget(QLabel("In:")); dft_l.addWidget(in_sin)
            dft_l.addWidget(QLabel("Out:")); dft_l.addWidget(in_sout)
            dft_l.addWidget(QLabel("En:")); dft_l.addWidget(in_sen)
            dft_l.addWidget(QLabel("Clk:")); dft_l.addWidget(in_sclk)
            dft_l.addWidget(chk_dft_clamp)
            dft_l.addStretch()
            dlg_layout.addWidget(grp_dft)
            
            bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            bbox.accepted.connect(dlg.accept)
            bbox.rejected.connect(dlg.reject)
            dlg_layout.addWidget(bbox)
            
            QShortcut(QKeySequence("Ctrl+Return"), dlg).activated.connect(dlg.accept)
            
            if not dlg.exec():
                if hasattr(self, 'tab_synth') and hasattr(self.tab_synth, 'card_status'):
                    self.tab_synth.card_status.setText("CANCELLED")
                return
                
            ys = editor.text()
            # Cache user DFT choices
            self._dft_config = {
                "enabled": chk_dft_en.isChecked(),
                "scan_in": in_sin.text().strip() or "scan_in",
                "scan_out": in_sout.text().strip() or "scan_out",
                "scan_en": in_sen.text().strip() or "scan_en",
                "scan_clk": in_sclk.text().strip() or "clk",
                "clamp": chk_dft_clamp.isChecked()
            }
        else:
            self._dft_config = getattr(self, '_dft_config', {"enabled": False, "scan_in": "scan_in", "scan_out": "scan_out", "scan_en": "scan_en", "scan_clk": "clk", "clamp": True})

        with open(os.path.join(root, "synth.ys"), 'w') as f: f.write(ys)
        
        # --- 2. STA SCRIPT (Full Multi-Corner Multi-Mode MCMM Signoff) ---
        # Redirects output (>) to timing.rpt and power.rpt
        sdc_files = glob.glob(os.path.join(root, "constr", "*.sdc")) + glob.glob(os.path.join(root, "source", "*.sdc"))
        abs_sdc = sdc_files[0] if sdc_files else (os.path.join(root, "constr", f"{base}.sdc") if os.path.isdir(os.path.join(root, "constr")) else os.path.join(root, "source", f"{base}.sdc"))
        
        # Discover and configure multi-corner scenarios
        mcmm_corners = {}
        if self.active_pdk and isinstance(self.active_pdk.get('corners'), dict):
            pdk_corners = self.active_pdk['corners']
            ss_k = next((k for k in ['ss_100C_1v60', 'ss_n40C_1v35', 'ss_100C_1v40'] if k in pdk_corners), None)
            tt_k = next((k for k in ['tt_025C_1v80', 'tt_100C_1v80'] if k in pdk_corners), None)
            ff_k = next((k for k in ['ff_n40C_1v95', 'ff_100C_1v95', 'ff_n40C_1v65'] if k in pdk_corners), None)
            if ss_k: mcmm_corners['ss'] = pdk_corners[ss_k]
            if tt_k: mcmm_corners['tt'] = pdk_corners[tt_k]
            if ff_k: mcmm_corners['ff'] = pdk_corners[ff_k]

        if mcmm_corners and len(mcmm_corners) > 1:
            # --- MCMM: define corners + per-corner liberty (standard cells) ---
            sta_mcmm_defs = f"define_corners {' '.join(mcmm_corners.keys())}\n"
            for c_name, c_lib in mcmm_corners.items():
                sta_mcmm_defs += f'read_liberty -corner {c_name} "{c_lib}"\n'

            # Macro libs: emit only once per unique lib path (dedup), then qualify per corner.
            # Dedup is critical — the SRAM typically has only a TT lib, reading it 3× causes
            # STA-1140 "library already exists" warnings and may shadow corner resolution.
            seen_libs: set = set()
            for lib in macro_lib_paths:
                if lib in seen_libs:
                    continue
                seen_libs.add(lib)
                for c_name in mcmm_corners:
                    macro_lib_cmds_sta += f'read_liberty -corner {c_name} "{lib}"\n'

            # Standalone OpenSTA MCMM API (NOT OpenROAD -scene API):
            #   read_sdc is called once — constraints apply to all corners.
            #   report_checks / report_power use -corner <name>.
            rpt_corner = "tt" if "tt" in mcmm_corners else list(mcmm_corners.keys())[0]
            sdc_cmd    = f'read_sdc "{abs_sdc}"'
            pwr_cmd    = f"report_power -corner {rpt_corner}"
            checks_cmd = (
                f"report_checks -path_delay max -fields {{slew cap input_pins nets fanout}} "
                f"-format full_clock_expanded -group_count 100 "
                f"-corner {rpt_corner} "
                f'> {os.path.join(root, "reports", "timing.rpt")}'
            )
        else:
            sta_mcmm_defs = f'read_liberty "{self.pdk_path}"\n'
            # Single-corner: macro libs need no corner qualifier; dedup just in case
            seen_libs_sc: set = set()
            for lib in macro_lib_paths:
                if lib not in seen_libs_sc:
                    seen_libs_sc.add(lib)
                    macro_lib_cmds_sta += f'read_liberty "{lib}"\n'
            sdc_cmd    = f'read_sdc "{abs_sdc}"'
            pwr_cmd    = "report_power"
            checks_cmd = (
                f"report_checks -path_delay max -fields {{slew cap input_pins nets fanout}} "
                f"-format full_clock_expanded -group_count 100 "
                f'> {os.path.join(root, "reports", "timing.rpt")}'
            )

        tcl = f"""sta::set_thread_count [exec nproc]
{sta_mcmm_defs}
{macro_lib_cmds_sta}read_verilog {v_net}
link_design {base}
{sdc_cmd}
{checks_cmd}
{pwr_cmd} > {os.path.join(root, 'reports', 'power.rpt')}
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

                # --- STEP 2: OPENSTA (standalone) ---
                try:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    # Candidate locations in priority order:
                    #   1. Vendored third-party OpenSTA build (symlinked in third-party/bin/sta)
                    #   2. Core synthengine build
                    #   3. System PATH
                    sta_candidates = [
                        os.path.join(REPO_ROOT, "third-party", "bin", "sta"),
                        os.path.join(REPO_ROOT, "third-party", "OpenSTA", "build", "sta"),
                        os.path.join(REPO_ROOT, "core", "synthengine", "build", "OpenSTA_build", "sta"),
                        os.path.join(base_dir, "core", "synthengine", "build", "OpenSTA_build", "sta"),
                        shutil.which("sta"),
                        "sta",
                    ]
                    sta_bin = None
                    for c in sta_candidates:
                        if c and os.path.isfile(c) and os.access(c, os.X_OK):
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
                dft_cfg = getattr(self, '_dft_config', {})
                dft_active = dft_cfg.get('enabled', False) or getattr(self, 'enable_dft', False)
                if dft_active:
                    try:
                        from dft.dft_engine import DFTEngine
                        pdk_name = self.active_pdk.get("name", "sky130") if self.active_pdk else "sky130"
                        
                        s_in = dft_cfg.get("scan_in", "scan_in")
                        s_out = dft_cfg.get("scan_out", "scan_out")
                        s_en = dft_cfg.get("scan_en", "scan_en")
                        s_clk = dft_cfg.get("scan_clk", "clk")
                        clamp = dft_cfg.get("clamp", True)
                        
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

    def run_verilator_lint(self):
        """Runs fast static linting across project RTL using bundled Verilator."""
        proj_root, base = self.get_context()
        root = self.get_proj_root(base)
        rtl_dir = os.path.join(root, "rtl") if os.path.isdir(os.path.join(root, "rtl")) else os.path.join(root, "source")
        
        rtl_sources = glob.glob(os.path.join(rtl_dir, "*.v")) + glob.glob(os.path.join(rtl_dir, "*.sv"))
        if not rtl_sources:
            self.log_system("No RTL files found to lint.", "WARN")
            return

        verilator_bin = os.path.abspath(os.path.join(REPO_ROOT, "third-party", "bin", "verilator"))
        if not os.path.isfile(verilator_bin):
            verilator_bin = shutil.which("verilator")
        if not verilator_bin:
            self.log_system("Verilator binary not available.", "ERR")
            return

        # Switch to terminal view
        if hasattr(self.tab_compile, 'bottom_tabs'):
            self.tab_compile.bottom_tabs.setCurrentIndex(0)

        cmd = [verilator_bin, "--lint-only", "-sv", "-Wall", "-Wno-fatal", f"-I{rtl_dir}"] + rtl_sources

        def lint_task():
            self.queue.put(("[SYS]", f"[LINT] Running Verilator RTL Lint on {len(rtl_sources)} files..."))
            res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
            output = res.stderr or res.stdout or ""
            if not output.strip():
                self.queue.put(("[SYS]", "[LINT] [OK] RTL Lint Clean: No warnings or errors found."))
            else:
                for line in output.splitlines():
                    self.queue.put(("[SYS]", f"[LINT] {line}"))
                self.queue.put(("[SYS]", "[LINT] Lint completed with diagnostics."))

        threading.Thread(target=lint_task, daemon=True).start()

    def run_simulation(self):
        if self.current_file: self.save_file()
        
        # Always autoselect and prioritize project top module if defined,
        # regardless of what file/submodule is active in editor or explorer
        base = None
        if hasattr(self, 'project_config') and self.project_config:
            base = self.project_config.get("top_module")
        if not base:
            _, base = self.get_context()
        if not base:
            self.log_system("[ERR] Cannot determine top module for simulation.")
            return

        # 1. Automatically generate and display schematic on top-right
        self.generate_schematic()

        root = self.prep_workspace(base)
        src_v = []
        # Check rtl/, tb/ and legacy source/, recursively including nested subdirectories
        for sdir in [os.path.join(root, "rtl"), os.path.join(root, "tb"), os.path.join(root, "source")]:
            if os.path.isdir(sdir):
                for subroot, _, files in os.walk(sdir):
                    if any(ignored in subroot for ignored in ['/.', '/build', '__pycache__', '/.git']):
                        continue
                    for f in files:
                        if f.lower().endswith(('.v', '.sv')):
                            f_path = os.path.join(subroot, f)
                            if f_path not in src_v:
                                src_v.append(f_path)
        if not src_v:
            src_v = glob.glob(os.path.join(root, "*.v")) + glob.glob(os.path.join(root, "*.sv"))
        if not src_v:
            self.log_system("No source files found in rtl/, tb/, or source/!", "ERR")
            return

        # Scan for actual Verilog/SystemVerilog declared `module <name>` across all files
        # to ensure --top-module matches an actual instantiated module (not a UVM class or interface)
        module_declarations = {}  # module_name -> file_path
        included_files = set()    # files that are `included inside other source files
        for f in src_v:
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                    f_content = fp.read()
                # Find included files to prevent MODDUP
                for inc_m in re.finditer(r'`include\s+["<]([^">]+)[">]', f_content):
                    inc_bname = os.path.basename(inc_m.group(1))
                    included_files.add(inc_bname)
                # Find all declared modules
                for mod_m in re.finditer(r'\bmodule\s+([a-zA-Z0-9_]+)', f_content):
                    mname = mod_m.group(1)
                    module_declarations[mname] = f
            except Exception:
                pass

        # Deduplicate sources: if a file is explicitly `included in another file (e.g. `include "testfpssoc_if.sv"),
        # exclude it from the direct compile list to prevent Verilator MODDUP warnings
        if included_files:
            src_v = [f for f in src_v if os.path.basename(f) not in included_files]

        # Robust simulation top selection among actual declared modules
        sim_top = None
        # 1. Exact match for tb_<base> or <base>_tb
        for mname in module_declarations:
            ml = mname.lower()
            if ml in [f"tb_{base.lower()}", f"{base.lower()}_tb"]:
                sim_top = mname
                break

        # 2. Match module containing "tb" and "top" (e.g. tb_top)
        if not sim_top:
            for mname in module_declarations:
                ml = mname.lower()
                if "tb" in ml and "top" in ml:
                    sim_top = mname
                    break

        # 3. Match any module containing "tb" or "top"
        if not sim_top:
            for mname in module_declarations:
                ml = mname.lower()
                if ml.startswith("tb_") or ml.endswith("_tb") or ml == "tb" or ml == "tb_top":
                    sim_top = mname
                    break

        # 4. Fallback to base module
        if not sim_top:
            sim_top = base if base in module_declarations else None

        # Sort sources so packages, headers, and dependencies come before modules and testbenches
        def _sort_key(p):
            b = os.path.basename(p).lower()
            if "pkg" in b or "package" in b:
                return (0, b)
            if "if" in b or "interface" in b:
                return (1, b)
            if "tb" in b or "test" in b:
                return (3, b)
            return (2, b)
        src_v = sorted(src_v, key=_sort_key)

        # Detect UVM usage across sources to auto-inject uvm_pkg.sv and uvm_dpi.cc at compile start
        uvm_pkg_path = os.path.abspath(os.path.join(REPO_ROOT, "third-party", "uvm-verilator", "src", "uvm_pkg.sv"))
        uvm_dpi_path = os.path.abspath(os.path.join(REPO_ROOT, "third-party", "uvm-verilator", "src", "dpi", "uvm_dpi.cc"))
        is_uvm_design = False
        if os.path.isfile(uvm_pkg_path):
            for fpath in src_v:
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fscan:
                        content_scan = fscan.read()
                        if "uvm_pkg" in content_scan or "uvm_macros" in content_scan:
                            is_uvm_design = True
                            break
                except Exception:
                    pass
        if is_uvm_design:
            if uvm_pkg_path not in src_v:
                src_v.insert(0, uvm_pkg_path)
            if os.path.isfile(uvm_dpi_path) and uvm_dpi_path not in src_v:
                src_v.append(uvm_dpi_path)

        # Switch bottom drawer to Terminal initially so compilation progress is visible
        if hasattr(self.tab_compile, 'bottom_tabs'):
            self.tab_compile.bottom_tabs.setCurrentIndex(0)

        # Locate Verilator binary from third-party or system path
        verilator_bin = os.path.abspath(os.path.join(REPO_ROOT, "third-party", "bin", "verilator"))
        if not os.path.isfile(verilator_bin):
            verilator_bin = shutil.which("verilator")

        uvm_dir = os.path.abspath(os.path.join(REPO_ROOT, "third-party", "uvm-verilator", "src"))
        out_bin = os.path.join(root, f"{base}.out")

        # Determine if Verilator is available
        use_verilator = bool(verilator_bin and os.path.isfile(verilator_bin))
        
        # Processor Allocation Dialog (ask user if not remembered in session)
        avail_cpus = os.cpu_count() or 4
        if not hasattr(self, '_allocated_sim_cpus') or not self._allocated_sim_cpus:
            cores, ok = QInputDialog.getInt(
                self,
                "Simulation Processor Allocation",
                f"Allocate parallel CPU threads for Verilator simulation/build (1 - {avail_cpus}):",
                value=avail_cpus,
                min=1,
                max=avail_cpus,
                step=1
            )
            self._allocated_sim_cpus = cores if ok else min(avail_cpus, 4)

        cpu_threads = self._allocated_sim_cpus
        coverage_dat = os.path.join(root, "coverage.dat")
        
        # Build include path arguments, dynamically finding all subdirectories under rtl/ and tb/
        inc_dirs = [".", "rtl", "tb", "constr", "source"]
        for search_base in [os.path.join(root, "rtl"), os.path.join(root, "tb")]:
            if os.path.isdir(search_base):
                for subroot, dirs, _ in os.walk(search_base):
                    rel = os.path.relpath(subroot, root)
                    if rel not in inc_dirs:
                        inc_dirs.append(rel)
        v_inc_args = [f"-I{d}" for d in inc_dirs]

        if use_verilator:
            # Build Verilator simulation command with full SystemVerilog IEEE 1800, multithreading, coverage, & UVM include paths
            if os.path.isdir(uvm_dir):
                v_inc_args.extend([f"-I{uvm_dir}", f"-I{os.path.join(uvm_dir, 'macros')}"])
                if is_uvm_design:
                    v_inc_args.extend(["-CFLAGS", f"-I{os.path.join(uvm_dir, 'dpi')}"])
            cmd = [
                verilator_bin, "--binary", "--timing", "-sv",
                "--timescale", "1ns/1ps",
                "--vpi",
                "--trace", "--trace-structs",
                "--coverage",
                f"-j", str(cpu_threads),
                f"--build-jobs", str(cpu_threads),
                "-Wno-fatal",
                "-Wno-TIMESCALEMOD",
                "-Wno-MODDUP",
                "-Wno-WIDTHEXPAND",
                "-Wno-WIDTHTRUNC"
            ]
            if sim_top:
                cmd.extend(["--top-module", sim_top])
            cmd.extend(["-o", out_bin] + v_inc_args + src_v)
        else:
            cmd = ["iverilog", "-g2012"] + v_inc_args + ["-o", out_bin] + src_v

        # Determine simulation methodology display label
        methodology = "Procedural SystemVerilog"
        if hasattr(self, "tab_compile") and hasattr(self.tab_compile, "explorer_panel"):
            methodology = getattr(self.tab_compile.explorer_panel, "current_tb_methodology", "Procedural SystemVerilog")
        spinner_label = "UVM RUNNING" if "uvm" in methodology.lower() or (sim_top and "uvm" in sim_top.lower()) else "SIM RUNNING"
        self.start_sim_spinner(spinner_label)

        def task():
            try:
                sim_tool_name = "Verilator" if use_verilator else "iverilog"
                self.queue.put(("[SYS]", f"Compiling RTL & Testbenches with {sim_tool_name} ({len(src_v)} files, {cpu_threads} threads)..."))
                sub_env = os.environ.copy()
                v_root = os.path.abspath(os.path.join(REPO_ROOT, "third-party", "share", "verilator"))
                if os.path.isdir(v_root):
                    sub_env["VERILATOR_ROOT"] = v_root
                comp = subprocess.run(cmd, cwd=root, capture_output=True, text=True, env=sub_env)
                if comp.returncode != 0:
                    err_msg = comp.stderr.strip() or comp.stdout.strip()
                    self.queue.put(("[SYS]", f"[ERR] {sim_tool_name} compilation failed:\n{err_msg}"))
                    self.queue.put(("STOP_SIM_SPINNER", "[ERR] Simulation build failed."))
                    return

                # Run simulation executable
                if use_verilator:
                    sim_exec = os.path.join(root, "obj_dir", f"V{base}") if os.path.isfile(os.path.join(root, "obj_dir", f"V{base}")) else out_bin
                    self.queue.put(("[SYS]", f"Simulating with Verilator native binary ({os.path.basename(sim_exec)})..."))
                    proc = subprocess.Popen([sim_exec], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                else:
                    self.queue.put(("[SYS]", "Simulating with vvp..."))
                    proc = subprocess.Popen(["vvp", out_bin], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                
                assertion_markers = []
                assert_regex = re.compile(
                    r'(?P<file>[a-zA-Z0-9_./\\-]+\.(?:v|sv|vhd|vhdl)):(?P<line>\d+):(?:\d+:)?\s*(?:@(?P<time_vhdl>\d+(?:\.\d+)?\s*(?:ps|ns|us|ms|s)))?.*?(?P<msg>(?:assertion\s+(?:error|failure)|error|fatal|fail).*)$',
                    re.IGNORECASE
                )
                time_regex = re.compile(r'Time:\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?', re.IGNORECASE)
                curr_err = None
                
                sim_logs = []
                for line in iter(proc.stdout.readline, ''):
                    line_str = line.strip()
                    sim_logs.append(line_str)
                    self.queue.put(("[SYS]", line_str))
                    # Check for Verilog / SystemVerilog / VHDL assertion and fatal logs
                    m = assert_regex.search(line_str)
                    if m:
                        tv = m.group("time_vhdl")
                        t_ps = None
                        if tv:
                            tv_m = re.match(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)', tv)
                            if tv_m:
                                v_num = float(tv_m.group(1))
                                u_str = tv_m.group(2).lower()
                                mult = {'ps': 1.0, 'ns': 1000.0, 'us': 1000000.0, 'ms': 1000000000.0}.get(u_str, 1.0)
                                t_ps = int(v_num * mult)
                        curr_err = {
                            "file": m.group("file"),
                            "line": int(m.group("line")),
                            "msg": m.group("msg"),
                            "severity": "fatal" if "fatal" in line_str.lower() else "error",
                            "time_ps": t_ps
                        }
                        assertion_markers.append(curr_err)
                    elif curr_err and curr_err.get("time_ps") is None:
                        tm = time_regex.search(line_str)
                        if tm:
                            val = float(tm.group(1))
                            unit = (tm.group(2) or 'ps').lower()
                            mult = {'ps': 1.0, 'ns': 1000.0, 'us': 1000000.0, 'ms': 1000000000.0}.get(unit, 1.0)
                            curr_err["time_ps"] = int(val * mult)
                proc.wait()

                # Process Hardware Coverage with verilator_coverage if coverage.dat was generated
                coverage_data = {}
                coverage_metrics = {}
                cov_tool = os.path.abspath(os.path.join(REPO_ROOT, "third-party", "bin", "verilator_coverage"))
                if not os.path.isfile(cov_tool):
                    cov_tool = shutil.which("verilator_coverage")
                if os.path.isfile(coverage_dat) and cov_tool:
                    try:
                        cov_res = subprocess.run([cov_tool, "--report", "summary", coverage_dat], cwd=root, capture_output=True, text=True)
                        cov_out = cov_res.stdout or ""
                        try:
                            from verification.verificationprt import VerificationReport
                            coverage_metrics = VerificationReport.parse_verilator_coverage(cov_out)
                        except Exception:
                            coverage_metrics = {}
                        # Parse summary table from verilator_coverage
                        for cline in cov_out.splitlines():
                            cline_s = cline.strip()
                            if "Total coverage" in cline_s or "Total" in cline_s:
                                m_pct = re.search(r'(\d+(?:\.\d+)?)%', cline_s)
                                if m_pct: coverage_data["overall_pct"] = float(m_pct.group(1))
                            elif "Line" in cline_s:
                                m_pct = re.search(r'(\d+(?:\.\d+)?)%', cline_s)
                                if m_pct: coverage_data["line_pct"] = float(m_pct.group(1))
                            elif "Toggle" in cline_s:
                                m_pct = re.search(r'(\d+(?:\.\d+)?)%', cline_s)
                                if m_pct: coverage_data["toggle_pct"] = float(m_pct.group(1))
                        self.queue.put(("[SYS]", f"[COVERAGE] Verilator Coverage: Line {coverage_data.get('line_pct', 'N/A')}%, Toggle {coverage_data.get('toggle_pct', 'N/A')}%"))
                    except Exception as e_cov:
                        print(f"[SILIS] Coverage extraction error: {e_cov}")

                # Find generated FST or VCD waveform
                wave_candidates = (
                    glob.glob(os.path.join(root, "*.fst")) +
                    glob.glob(os.path.join(root, "tb", "*.fst")) +
                    glob.glob(os.path.join(root, "*.vcd")) +
                    glob.glob(os.path.join(root, "tb", "*.vcd")) +
                    glob.glob(os.path.join(root, "source", "*.vcd"))
                )
                if wave_candidates:
                    latest_wave = max(wave_candidates, key=os.path.getmtime)
                    self.queue.put(("LOAD_WAVES", latest_wave))
                    self.queue.put(("[SYS]", f"[OK] Waveform successfully loaded: {os.path.basename(latest_wave)}"))
                    if assertion_markers:
                        # Determine max timestamp to calculate precise relative X positions on ruler
                        max_time_ps = 1
                        try:
                            if latest_wave.endswith(".vcd"):
                                with open(latest_wave, 'r', errors='ignore') as vf:
                                    for vline in vf:
                                        if vline.startswith('#'):
                                             try:
                                                 vt = int(vline[1:].strip())
                                                 if vt > max_time_ps: max_time_ps = vt
                                             except: pass
                        except Exception:
                            max_time_ps = 100000

                        for mark in assertion_markers:
                            tp = mark.get("time_ps")
                            if tp is not None and max_time_ps > 0:
                                # Scale marker left offset accounting for 25% hierarchy pane on left and right margin
                                rel_pct = min(1.0, max(0.0, tp / max_time_ps))
                                mark["rel_x"] = 0.25 + 0.70 * rel_pct
                            else:
                                mark["rel_x"] = 0.50

                        self.queue.put(("ASSERTION_MARKERS", assertion_markers))
                        self.queue.put(("[SYS]", f"[ASSERT] Detected {len(assertion_markers)} simulation assertion events."))

                # Generate Verification Markdown Report using VerificationReport
                try:
                    from verification.verificationprt import VerificationReport
                    proj_name = getattr(self, "project_config", {}).get("project_name", os.path.basename(root)) if hasattr(self, "project_config") and self.project_config else os.path.basename(root)
                    test_name = sim_top or base or "verification_test"
                    methodology = "Procedural SystemVerilog"
                    if hasattr(self, "tab_compile") and hasattr(self.tab_compile, "explorer_panel"):
                        methodology = getattr(self.tab_compile.explorer_panel, "current_tb_methodology", "Procedural SystemVerilog")
                    rep_path = os.path.join(root, "reports", "verification_report.md")
                    VerificationReport.generate(
                        project_name=proj_name,
                        top_module=base,
                        test_name=test_name,
                        methodology=methodology,
                        sim_logs=sim_logs,
                        assertion_markers=assertion_markers,
                        coverage_metrics=coverage_metrics,
                        out_path=rep_path
                    )
                    if rep_path and os.path.exists(rep_path):
                        self.queue.put(("[SYS]", f"[REPORT] Verification Report generated: {os.path.basename(rep_path)}"))
                        self.queue.put(("OPEN_REPORT", rep_path))
                except Exception as ex_rep:
                    self.queue.put(("[SYS]", f"[REPORT] Verification Report notice: {ex_rep}"))
                else:
                    if not wave_candidates:
                        self.queue.put(("[SYS]", "[WARN] Simulation finished, but no waveform was generated. Ensure testbench calls $dumpfile and $dumpvars."))
                self.queue.put(("STOP_SIM_SPINNER", "[OK] Simulation finished."))
            except Exception as e:
                self.queue.put(("[SYS]", f"[ERR] Simulation Error: {e}"))
                self.queue.put(("STOP_SIM_SPINNER", "[ERR] Simulation encountered an error."))

        threading.Thread(target=task, daemon=True).start()

    def run_verilator_lint(self):
        """Runs fast static linting across project RTL using bundled Verilator."""
        proj_root, base = self.get_context()
        root = self.get_proj_root(base)
        rtl_dir = os.path.join(root, "rtl") if os.path.isdir(os.path.join(root, "rtl")) else os.path.join(root, "source")
        
        rtl_sources = glob.glob(os.path.join(rtl_dir, "*.v")) + glob.glob(os.path.join(rtl_dir, "*.sv"))
        if not rtl_sources:
            self.log_system("No RTL files found to lint.", "WARN")
            return

        verilator_bin = os.path.abspath(os.path.join(REPO_ROOT, "third-party", "bin", "verilator"))
        if not os.path.isfile(verilator_bin):
            verilator_bin = shutil.which("verilator")
        if not verilator_bin:
            self.log_system("Verilator binary not available.", "ERR")
            return

        # Switch to terminal view
        if hasattr(self.tab_compile, 'bottom_tabs'):
            self.tab_compile.bottom_tabs.setCurrentIndex(0)

        cmd = [verilator_bin, "--lint-only", "-sv", "-Wall", "-Wno-fatal", f"-I{rtl_dir}"] + rtl_sources

        def lint_task():
            self.queue.put(("[SYS]", f"[LINT] Running Verilator RTL Lint on {len(rtl_sources)} files..."))
            res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
            output = res.stderr or res.stdout or ""
            if not output.strip():
                self.queue.put(("[SYS]", "[LINT] [OK] RTL Lint Clean: No warnings or errors found."))
            else:
                for line in output.splitlines():
                    self.queue.put(("[SYS]", f"[LINT] {line}"))
                self.queue.put(("[SYS]", "[LINT] Lint completed with diagnostics."))

        threading.Thread(target=lint_task, daemon=True).start()

    # --- HELPERS (Copied & Cleaned) ---
    def setup_toolbar(self):
        # 1. Top Menubar
        menubar = self.menuBar()

        # --- Menu 1: File ---
        menu_file = menubar.addMenu("File")
        
        act_new_file = QAction("New File", self)
        act_new_file.setShortcut("Ctrl+N")
        act_new_file.triggered.connect(self.new_file)
        menu_file.addAction(act_new_file)

        act_open_file = QAction("Open File...", self)
        act_open_file.setShortcut("Ctrl+O")
        act_open_file.triggered.connect(self.browse_open_file)
        menu_file.addAction(act_open_file)

        menu_file.addSeparator()

        act_imp_rtl = QAction("Import RTL Source...", self)
        act_imp_rtl.triggered.connect(self.import_rtl_files)
        menu_file.addAction(act_imp_rtl)

        act_imp_sim = QAction("Import Simulation Source...", self)
        act_imp_sim.triggered.connect(self.import_sim_files)
        menu_file.addAction(act_imp_sim)

        act_imp_constr = QAction("Import Constraint Source...", self)
        act_imp_constr.triggered.connect(self.import_constr_files)
        menu_file.addAction(act_imp_constr)

        # Submenu: Import Others
        menu_imp_others = menu_file.addMenu("Import Others")

        act_imp_macro = QAction("Import Macro IP...", self)
        act_imp_macro.triggered.connect(self.import_macro_ip)
        menu_imp_others.addAction(act_imp_macro)

        act_imp_power = QAction("Import UPF / CPF (Power Intent)...", self)
        act_imp_power.triggered.connect(self.import_power_intent_file)
        menu_imp_others.addAction(act_imp_power)

        act_imp_io = QAction("Import I/O Pin Config...", self)
        act_imp_io.triggered.connect(self.import_io_config_file)
        menu_imp_others.addAction(act_imp_io)

        menu_file.addSeparator()

        act_new_proj = QAction("New Project...", self)
        act_new_proj.setShortcut("Ctrl+Shift+N")
        act_new_proj.triggered.connect(self.new_project)
        menu_file.addAction(act_new_proj)

        act_open_proj = QAction("Open Project...", self)
        act_open_proj.setShortcut("Ctrl+Shift+O")
        act_open_proj.triggered.connect(lambda: self.open_project())
        menu_file.addAction(act_open_proj)

        act_save_state = QAction("Save Project State", self)
        act_save_state.setShortcut("Ctrl+S")
        act_save_state.triggered.connect(self.save_project_state)
        menu_file.addAction(act_save_state)

        act_save_state_as = QAction("Save Project State As...", self)
        act_save_state_as.triggered.connect(self.save_project_state_as)
        menu_file.addAction(act_save_state_as)

        self.menu_recent = menu_file.addMenu("Recent Projects")
        self.menu_recent.aboutToShow.connect(self._populate_recent_menu)

        # --- Menu 2: View ---
        menu_view = menubar.addMenu("View")

        # Submenu: Viewer Mode (Instance-Wise vs Layer-Wise)
        menu_viewer_mode = menu_view.addMenu("Viewer Mode")
        act_vm_instance = QAction("Instance-Wise View", self)
        act_vm_instance.setCheckable(True)
        act_vm_instance.setChecked(True)
        act_vm_instance.triggered.connect(lambda: self.set_viewer_mode("instance"))
        menu_viewer_mode.addAction(act_vm_instance)

        act_vm_layer = QAction("Layer-Wise View", self)
        act_vm_layer.setCheckable(True)
        act_vm_layer.setChecked(False)
        act_vm_layer.triggered.connect(lambda: self.set_viewer_mode("layer"))
        menu_viewer_mode.addAction(act_vm_layer)

        ag_vm = QActionGroup(self)
        ag_vm.addAction(act_vm_instance)
        ag_vm.addAction(act_vm_layer)
        ag_vm.setExclusive(True)
        self.act_vm_instance = act_vm_instance
        self.act_vm_layer = act_vm_layer

        menu_view.addSeparator()

        menu_heatmaps = menu_view.addMenu("Heatmaps")
        hm_rudy = QAction("RUDY Congestion", self)
        hm_rudy.triggered.connect(lambda: self.activate_heatmap("rudy"))
        menu_heatmaps.addAction(hm_rudy)

        hm_ir = QAction("Static IR Drop (::psm)", self)
        hm_ir.triggered.connect(lambda: self.activate_heatmap("ir_drop"))
        menu_heatmaps.addAction(hm_ir)

        hm_route = QAction("Routing Congestion", self)
        hm_route.triggered.connect(lambda: self.activate_heatmap("route_congestion"))
        menu_heatmaps.addAction(hm_route)

        hm_pin = QAction("Pin Density", self)
        hm_pin.triggered.connect(lambda: self.activate_heatmap("pin_density"))
        menu_heatmaps.addAction(hm_pin)

        hm_place = QAction("Placement Density", self)
        hm_place.triggered.connect(lambda: self.activate_heatmap("placement_density"))
        menu_heatmaps.addAction(hm_place)

        hm_pwr = QAction("Power Density", self)
        hm_pwr.triggered.connect(lambda: self.activate_heatmap("power_density"))
        menu_heatmaps.addAction(hm_pwr)

        menu_heatmaps.addSeparator()
        hm_clear = QAction("Clear Heatmap Overlay", self)
        hm_clear.triggered.connect(lambda: self.activate_heatmap(None))
        menu_heatmaps.addAction(hm_clear)

        act_ruler = QAction("Ruler (M)", self)
        act_ruler.setShortcut("M")
        act_ruler.triggered.connect(self.toggle_ruler)
        menu_view.addAction(act_ruler)

        # --- Menu 3: Tools ---
        menu_tools = menubar.addMenu("Tools")

        act_lint = QAction("Lint RTL (Verilator)", self)
        act_lint.setShortcut("Ctrl+L")
        act_lint.triggered.connect(self.run_verilator_lint)
        menu_tools.addAction(act_lint)

        act_openram = QAction("OpenRAM SRAM Compilation", self)
        act_openram.triggered.connect(self.open_openram_studio)
        menu_tools.addAction(act_openram)

        act_pdk = QAction("PDK Config", self)
        act_pdk.triggered.connect(self.open_pdk_selector)
        menu_tools.addAction(act_pdk)

        # --- Menu 4: Settings ---
        menu_settings = menubar.addMenu("Settings")

        menu_editor_sel = menu_settings.addMenu("Editor Backend")
        act_ed_monaco = QAction("Monaco (WebEngine, VS Code)", self)
        act_ed_monaco.setCheckable(True)
        act_ed_monaco.setChecked(USER_SETTINGS.get("editor_backend", "monaco").lower() == "monaco")
        act_ed_monaco.triggered.connect(lambda: self.set_editor_backend("monaco"))
        menu_editor_sel.addAction(act_ed_monaco)

        act_ed_qsci = QAction("QScintilla (Native C++)", self)
        act_ed_qsci.setCheckable(True)
        act_ed_qsci.setChecked(USER_SETTINGS.get("editor_backend", "monaco").lower() == "qscintilla")
        act_ed_qsci.triggered.connect(lambda: self.set_editor_backend("qscintilla"))
        menu_editor_sel.addAction(act_ed_qsci)

        self.act_group_ed = QActionGroup(self)
        self.act_group_ed.addAction(act_ed_monaco)
        self.act_group_ed.addAction(act_ed_qsci)
        self.act_group_ed.setExclusive(True)

        menu_font = menu_settings.addMenu("Font")
        act_font_inc = QAction("Increase Font Size (Ctrl+=)", self)
        act_font_inc.setShortcuts([QKeySequence("Ctrl+="), QKeySequence("Ctrl++")])
        act_font_inc.triggered.connect(lambda: self.zoom_font(1))
        menu_font.addAction(act_font_inc)

        act_font_dec = QAction("Decrease Font Size (Ctrl+-)", self)
        act_font_dec.setShortcut("Ctrl+-")
        act_font_dec.triggered.connect(lambda: self.zoom_font(-1))
        menu_font.addAction(act_font_dec)

        menu_font_families = menu_font.addMenu("Font Family")
        for fam in ["Consolas", "Courier New", "Fira Code", "JetBrains Mono", "Source Code Pro", "Monospace"]:
            act_fam = QAction(fam, self)
            act_fam.triggered.connect(lambda checked, f=fam: self.set_font_family(f))
            menu_font_families.addAction(act_fam)

        menu_colors = menu_settings.addMenu("Colors")
        menu_presets = menu_colors.addMenu("Presets")
        for tname in THEMES.keys():
            act_thm = QAction(tname, self)
            act_thm.triggered.connect(lambda checked, tn=tname: self.set_theme(tn))
            menu_presets.addAction(act_thm)

        act_cust_pal = QAction("Design Custom Palette...", self)
        act_cust_pal.triggered.connect(self.open_custom_palette_dialog)
        menu_colors.addAction(act_cust_pal)

        act_toggle_ln = QAction("Toggle Line Numbers", self)
        act_toggle_ln.setCheckable(True)
        act_toggle_ln.setChecked(EDITOR_CONFIG.get("line_numbers", True))
        act_toggle_ln.triggered.connect(self.toggle_line_numbers)
        menu_settings.addAction(act_toggle_ln)

        act_help_shortcuts = QAction("Shortcuts & Help", self)
        act_help_shortcuts.setShortcut("F1")
        act_help_shortcuts.triggered.connect(self.show_shortcuts_dialog)
        menu_settings.addAction(act_help_shortcuts)

        act_check_updates = QAction("Check for Updates...", self)
        act_check_updates.triggered.connect(lambda: self._on_check_updates())
        menu_settings.addAction(act_check_updates)

        act_pref = QAction("Preferences...", self)
        act_pref.triggered.connect(self.open_settings)
        menu_settings.addAction(act_pref)

        # 2. Main Tool Bar
        tb = QToolBar("Main Tool Bar")
        self.addToolBar(tb)
        tb.setMovable(False)

        # Quick action icons
        act_run = QAction("Compile & Sim", self)
        act_run.setToolTip("Compile RTL, simulate testbench, and open waveforms")
        act_run.triggered.connect(self.run_simulation)
        tb.addAction(act_run)

        act_synth = QAction("Synthesis", self)
        act_synth.setShortcut("F2")
        act_synth.setToolTip("Run Yosys Synthesis & Timing Flow")
        act_synth.triggered.connect(self.run_synthesis_flow)
        tb.addAction(act_synth)

        tb.addSeparator()
        self.btn_pdk_status = QPushButton("PDK: Sky130A")
        self.btn_pdk_status.setToolTip("Open PDK Manager & MCMM Selector")
        self.btn_pdk_status.setStyleSheet("QPushButton { font-weight: bold; padding: 3px 8px; border: 1px solid #444; border-radius: 3px; } QPushButton:hover { border-color: #58a6ff; }")
        self.btn_pdk_status.clicked.connect(self.open_pdk_selector)
        tb.addWidget(self.btn_pdk_status)

        tb.addSeparator()
        self.btn_front = QPushButton("Frontend")
        self.btn_front.setCheckable(True)
        self.btn_front.setChecked(True)
        self.btn_front.clicked.connect(lambda: self.switch_world(0))
        self.btn_back = QPushButton("Backend")
        self.btn_back.setCheckable(True)
        self.btn_back.clicked.connect(lambda: self.switch_world(1))
        tb.addWidget(self.btn_front)
        tb.addWidget(self.btn_back)

        tb.addSeparator()
        self.lbl_proj = QLabel(" Untitled ")
        tb.addWidget(self.lbl_proj)


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
            target_file = None
            for ext in [".v", ".sv", ".vhd", ".vhdl"]:
                for sdir in ["rtl", "source", ""]:
                    cand = os.path.join(self.cwd, sdir, f"{top_mod}{ext}") if sdir else os.path.join(self.cwd, f"{top_mod}{ext}")
                    if os.path.isfile(cand):
                        target_file = cand
                        break
                if target_file:
                    break

            if target_file:
                self.open_file_in_editor(target_file)
            else:
                for sdir in ["rtl", "source"]:
                    src_dir = os.path.join(self.cwd, sdir)
                    if os.path.isdir(src_dir):
                        v_files = [os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.endswith(('.v', '.sv', '.vhd', '.vhdl'))]
                        if v_files:
                            self.open_file_in_editor(v_files[0])
                            break

            self.log_system(f"Loaded Project: {proj_name} at {self.cwd}")
            if hasattr(self.tab_compile, 'explorer_panel'):
                self.tab_compile.explorer_panel.scan_workspace()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")

    def open_openram_studio(self):
        from pdkmanagers.macro.openram_studio import OpenRAMStudioDialog
        dlg = OpenRAMStudioDialog(self, self.project_config)
        dlg.exec()

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

        # Switch to log tab in bottom drawer
        if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'bottom_tabs'):
            self.tab_compile.bottom_tabs.setCurrentIndex(1)

        self.log_system(f"Ingested & Lowered Top Module: {result.get('top_module', '')}")

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()
    def log_system(self, msg, tag="SYS"):
        # ROUTE SYSTEM MESSAGES TO STATUS BAR, LOG VIEW & SYNTH LOG
        formatted = f"[{tag}] {msg}"
        self.statusBar().showMessage(formatted, 5000)
        if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'log_view'):
            self.tab_compile.log_view.append(formatted)
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
        if hasattr(self, 'tab_compile'):
            self.tab_compile.show_schematic(True)
            if hasattr(self.tab_compile.schem_view, 'load_from_path'):
                # SchematicTab: trigger structural Yosys engine to synthesize and display
                self.tab_compile.schem_view.invoke_engine(module_name, "block")
            elif hasattr(self.tab_compile.schem_view, 'load_json'):
                self.tab_compile.schem_view.ensure_engine()
                self.tab_compile.schem_view.load_json("", module_name, "block")

    def add_waveform_signal(self, signal_name):
        if not signal_name: return
        # Switch bottom drawer to Waveforms (Tab index 2)
        if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'bottom_tabs'):
            self.tab_compile.bottom_tabs.setCurrentIndex(2)
            
        if hasattr(self, 'tab_waves') and hasattr(self.tab_waves, 'add_signal_by_name'):
            self.tab_waves.add_signal_by_name(signal_name)
        elif hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'wave_view') and hasattr(self.tab_compile.wave_view, 'add_signal_by_name'):
            self.tab_compile.wave_view.add_signal_by_name(signal_name)
        self.log_system(f"Added '{signal_name}' to Waveform Viewer", "SYS")

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

    def browse_open_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Open File", self.cwd,
            "HDL & Sources (*.v *.sv *.vhd *.vhdl *.tcl *.sdc *.py *.c *.cpp *.h *.md *.json);;All Files (*)"
        )
        if f and os.path.isfile(f):
            self.open_file_in_editor(f)

    def import_rtl_files(self):
        proj_root = self.get_proj_root(self.get_context()[1] or "design")
        rtl_dir = os.path.join(proj_root, "rtl")
        os.makedirs(rtl_dir, exist_ok=True)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import RTL Source Files", self.cwd,
            "Verilog / SystemVerilog / VHDL (*.v *.sv *.vh *.svh *.vhd *.vhdl);;All Files (*)"
        )
        if not files:
            return
        imported = []
        for src in files:
            dest = os.path.join(rtl_dir, os.path.basename(src))
            shutil.copy2(src, dest)
            imported.append(dest)
        if self.project_config is None:
            self.project_config = {}
        curr_rtl = self.project_config.get("rtl_files", [])
        for f in imported:
            rel = os.path.relpath(f, proj_root)
            if rel not in curr_rtl:
                curr_rtl.append(rel)
        self.project_config["rtl_files"] = curr_rtl
        self.save_project_state()
        self.log_system(f"Imported {len(imported)} RTL file(s) into rtl/")
        if imported:
            self.open_file_in_editor(imported[0])
        if hasattr(self.tab_compile, 'explorer_panel'):
            self.tab_compile.explorer_panel.scan_workspace()

    def import_sim_files(self):
        proj_root = self.get_proj_root(self.get_context()[1] or "design")
        tb_dir = os.path.join(proj_root, "tb")
        os.makedirs(tb_dir, exist_ok=True)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Simulation Source Files", self.cwd,
            "Testbenches & Sim Sources (*.v *.sv *.vh *.svh *.cpp *.cc *.h);;All Files (*)"
        )
        if not files:
            return
        imported = []
        for src in files:
            dest = os.path.join(tb_dir, os.path.basename(src))
            shutil.copy2(src, dest)
            imported.append(dest)
        self.log_system(f"Imported {len(imported)} simulation file(s) into tb/")
        if imported:
            self.open_file_in_editor(imported[0])
        if hasattr(self.tab_compile, 'explorer_panel'):
            self.tab_compile.explorer_panel.scan_workspace()

    def import_constr_files(self):
        proj_root = self.get_proj_root(self.get_context()[1] or "design")
        constr_dir = os.path.join(proj_root, "constr")
        os.makedirs(constr_dir, exist_ok=True)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Constraint Files", self.cwd,
            "Constraints & Scripts (*.sdc *.tcl);;All Files (*)"
        )
        if not files:
            return
        imported = []
        for src in files:
            dest = os.path.join(constr_dir, os.path.basename(src))
            shutil.copy2(src, dest)
            imported.append(dest)
        if self.project_config is None:
            self.project_config = {}
        curr_sdc = self.project_config.get("sdc_files", [])
        for f in imported:
            rel = os.path.relpath(f, proj_root)
            if rel not in curr_sdc:
                curr_sdc.append(rel)
        self.project_config["sdc_files"] = curr_sdc
        self.save_project_state()
        self.log_system(f"Imported {len(imported)} constraint file(s) into constr/")
        if imported:
            self.open_file_in_editor(imported[0])

    def import_macro_ip(self):
        """
        Opens MacroPickerWidget to select a macro, generates/writes its Verilog stub
        into rtl/, registers the macro in .silisproj, and opens the stub in the editor.
        """
        try:
            from pdkmanagers.macro.ipcatalog import MacroPickerWidget
        except ImportError:
            try:
                from core.pdkmanagers.macro.ipcatalog import MacroPickerWidget
            except ImportError as e:
                self.log_system(f"Cannot load MacroPickerWidget: {e}", "ERR")
                return

        dlg = MacroPickerWidget(self.active_pdk, self.pdk_mgr, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        macro_name, stub_content, auto_stub = dlg.get_selected_macro()
        if not macro_name:
            return

        proj_root = self.get_proj_root(self.get_context()[1] or "design")
        rtl_dir = os.path.join(proj_root, "rtl")
        os.makedirs(rtl_dir, exist_ok=True)

        stub_path = None
        if stub_content and stub_content.strip():
            stub_file = os.path.join(rtl_dir, f"{macro_name}_stub.v")
            try:
                with open(stub_file, "w", encoding="utf-8") as f:
                    f.write(stub_content)
                stub_path = stub_file
                self.log_system(f"Generated macro black-box stub: {os.path.relpath(stub_file, proj_root)}")
            except Exception as e:
                self.log_system(f"Error saving macro stub: {e}", "ERR")

        if self.project_config is None:
            self.project_config = {}

        # Add macro name to macros list
        macros_list = self.project_config.get("macros", [])
        if macro_name not in macros_list:
            macros_list.append(macro_name)
        self.project_config["macros"] = macros_list

        # Add stub file to rtl_files list if generated
        if stub_path:
            curr_rtl = self.project_config.get("rtl_files", [])
            rel_stub = os.path.relpath(stub_path, proj_root)
            if rel_stub not in curr_rtl:
                curr_rtl.append(rel_stub)
            self.project_config["rtl_files"] = curr_rtl

        self.save_project_state()
        self.log_system(f"Imported macro '{macro_name}' into project.")

        if hasattr(self.tab_compile, 'explorer_panel'):
            self.tab_compile.explorer_panel.scan_workspace()

        if stub_path and os.path.isfile(stub_path):
            self.open_file_in_editor(stub_path)

    def import_power_intent_file(self):
        """
        Imports UPF/CPF/TCL power intent file into power/ in project root,
        records it in .silisproj as upf_file, and opens it in editor.
        """
        proj_root = self.get_proj_root(self.get_context()[1] or "design")
        pwr_dir = os.path.join(proj_root, "power")
        os.makedirs(pwr_dir, exist_ok=True)

        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Power Intent Files (UPF / CPF)", self.cwd,
            "Power Intent Files (*.upf *.cpf *.tcl *.sdc);;All Files (*)"
        )
        if not files:
            return

        imported = []
        for src in files:
            dest = os.path.join(pwr_dir, os.path.basename(src))
            shutil.copy2(src, dest)
            imported.append(dest)

        if self.project_config is None:
            self.project_config = {}

        if imported:
            rel = os.path.relpath(imported[0], proj_root)
            self.project_config["upf_file"] = rel

        self.save_project_state()
        self.log_system(f"Imported {len(imported)} power intent file(s) into power/")

        if hasattr(self.tab_compile, 'explorer_panel'):
            self.tab_compile.explorer_panel.scan_workspace()

        if imported:
            self.open_file_in_editor(imported[0])

    def import_io_config_file(self):
        """
        Imports I/O pin order/config file into io/ in project root,
        records it in .silisproj as pin_order_file, and opens it in editor.
        """
        proj_root = self.get_proj_root(self.get_context()[1] or "design")
        io_dir = os.path.join(proj_root, "io")
        os.makedirs(io_dir, exist_ok=True)

        files, _ = QFileDialog.getOpenFileNames(
            self, "Import I/O Pin Configuration", self.cwd,
            "Pin Configuration Files (*.cfg *.tcl *.json *.txt);;All Files (*)"
        )
        if not files:
            return

        imported = []
        for src in files:
            dest = os.path.join(io_dir, os.path.basename(src))
            # If target exists, create a backup
            if os.path.isfile(dest):
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                bak = f"{dest}.bak.{ts}"
                try:
                    shutil.copy2(dest, bak)
                except Exception:
                    pass
            shutil.copy2(src, dest)
            imported.append(dest)

        if self.project_config is None:
            self.project_config = {}

        if imported:
            rel = os.path.relpath(imported[0], proj_root)
            self.project_config["pin_order_file"] = rel

        self.save_project_state()
        self.log_system(f"Imported {len(imported)} I/O configuration file(s) into io/")

        if hasattr(self.tab_compile, 'explorer_panel'):
            self.tab_compile.explorer_panel.scan_workspace()

        if imported:
            self.open_file_in_editor(imported[0])

    def save_project_state(self, path=None):
        if self.current_file:
            self.save_file()
        proj_root = self.get_proj_root(self.get_context()[1] or "design")
        target_path = path or os.path.join(proj_root, "silis.silisproj")
        if not self.project_config:
            self.project_config = {
                "project_name": os.path.basename(proj_root),
                "top_module": self.get_context()[1] or "design",
                "pdk": self.active_pdk.get("name", "sky130") if self.active_pdk else "sky130"
            }
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(self.project_config, f, indent=2)
            self.log_system(f"Project state saved: {os.path.basename(target_path)}")
        except Exception as e:
            self.log_system(f"Error saving project state: {e}", "ERR")

    def save_project_state_as(self):
        f, _ = QFileDialog.getSaveFileName(
            self, "Save Project State As", self.cwd,
            "Silis Project (*.silisproj);;JSON (*.json);;All Files (*)"
        )
        if f:
            if not f.endswith((".silisproj", ".json")):
                f += ".silisproj"
            self.save_project_state(path=f)


    def set_viewer_mode(self, mode: str):
        """Switches between Instance-Wise (FastSiliconPeeker) and Layer-Wise (OpenROAD layout engine)."""
        self.switch_world(1)
        if hasattr(self, 'backend_widget') and self.backend_widget:
            if hasattr(self.backend_widget, 'set_viewer_mode'):
                self.backend_widget.set_viewer_mode(mode)
            if hasattr(self, 'act_vm_instance') and hasattr(self, 'act_vm_layer'):
                self.act_vm_instance.setChecked(mode == "instance")
                self.act_vm_layer.setChecked(mode == "layer")
        self.log_system(f"Viewer Mode switched to: {mode.title()}-Wise View")

    def activate_heatmap(self, heatmap_type):
        """Switches to layout peeker and requests the given heatmap overlay."""
        self.switch_world(1)
        if hasattr(self, 'backend_widget') and self.backend_widget:
            self.backend_widget.viz_tabs.setCurrentIndex(0)
            if hasattr(self.backend_widget, 'fast_peeker') and hasattr(self.backend_widget.fast_peeker, 'set_heatmap_mode'):
                self.backend_widget.fast_peeker.set_heatmap_mode(heatmap_type)
            else:
                tag = heatmap_type or "Disabled"
                self.log_system(f"Heatmap requested: {tag} (Overlay engine connecting...)")

    def toggle_ruler(self):
        """Activates interactive ruler mode in FastSiliconPeeker."""
        self.switch_world(1)
        if hasattr(self, 'backend_widget') and self.backend_widget:
            self.backend_widget.viz_tabs.setCurrentIndex(0)
            if hasattr(self.backend_widget, 'fast_peeker') and hasattr(self.backend_widget.fast_peeker, 'toggle_ruler'):
                active = self.backend_widget.fast_peeker.toggle_ruler()
                if active:
                    self.log_system("Ruler Active: Left-click and drag or click two points in layout to measure distance.")
                else:
                    self.log_system("Ruler Deactivated.")
            else:
                self.log_system("Ruler tool active: Click two points in layout to measure distance.")

    def zoom_font(self, delta):
        curr_size = EDITOR_CONFIG.get("font_size", USER_SETTINGS.get("font_size", 11))
        new_size = max(6, min(36, curr_size + delta))
        EDITOR_CONFIG["font_size"] = new_size
        USER_SETTINGS["font_size"] = new_size
        save_editor_config(EDITOR_CONFIG)
        save_user_settings(USER_SETTINGS)
        fam = EDITOR_CONFIG.get("font_family", "Consolas")
        thm = USER_SETTINGS.get("theme_name", "Catppuccin Mocha")
        backend = EDITOR_CONFIG.get("editor_backend", "monaco")
        if hasattr(self.tab_compile, 'editor'):
            self.tab_compile.editor.update_appearance(fam, new_size, thm, editor_backend=backend)
        if hasattr(self.tab_compile, 'terminal'):
            self.tab_compile.terminal.update_appearance(fam, new_size, THEMES.get(thm, {}))
        self.log_system(f"Editor font size adjusted to {new_size}pt")

    def set_font_family(self, family):
        EDITOR_CONFIG["font_family"] = family
        USER_SETTINGS["font_family"] = family
        save_editor_config(EDITOR_CONFIG)
        save_user_settings(USER_SETTINGS)
        size = EDITOR_CONFIG.get("font_size", 11)
        thm = USER_SETTINGS.get("theme_name", "Catppuccin Mocha")
        backend = EDITOR_CONFIG.get("editor_backend", "monaco")
        if hasattr(self.tab_compile, 'editor'):
            self.tab_compile.editor.update_appearance(family, size, thm, editor_backend=backend)
        if hasattr(self.tab_compile, 'terminal'):
            self.tab_compile.terminal.update_appearance(family, size, THEMES.get(thm, {}))
        self.log_system(f"Editor font family set to {family}")

    def set_editor_backend(self, backend):
        backend = backend.lower()
        EDITOR_CONFIG["editor_backend"] = backend
        USER_SETTINGS["editor_backend"] = backend
        save_editor_config(EDITOR_CONFIG)
        save_user_settings(USER_SETTINGS)
        fam = EDITOR_CONFIG.get("font_family", "Consolas")
        size = EDITOR_CONFIG.get("font_size", 11)
        thm = USER_SETTINGS.get("theme_name", "Catppuccin Mocha")
        if hasattr(self.tab_compile, 'editor'):
            self.tab_compile.editor.update_appearance(fam, size, thm, editor_backend=backend)
        self.log_system(f"Switched editor backend to {backend.upper()}")

    def set_theme(self, theme_name):
        USER_SETTINGS["theme_name"] = theme_name
        save_user_settings(USER_SETTINGS)
        fam = EDITOR_CONFIG.get("font_family", "Consolas")
        size = EDITOR_CONFIG.get("font_size", 11)
        backend = EDITOR_CONFIG.get("editor_backend", "monaco")
        if hasattr(self.tab_compile, 'editor'):
            self.tab_compile.editor.update_appearance(fam, size, theme_name, editor_backend=backend)
        if hasattr(self.tab_compile, 'terminal'):
            self.tab_compile.terminal.update_appearance(fam, size, THEMES.get(theme_name, {}))
        self.log_system(f"Color theme changed to {theme_name}")

    def open_custom_palette_dialog(self):
        dlg = CustomPaletteDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.set_theme("Custom")

    def toggle_line_numbers(self, checked):
        EDITOR_CONFIG["line_numbers"] = bool(checked)
        save_editor_config(EDITOR_CONFIG)
        self.log_system(f"Line numbers set to {'ON' if checked else 'OFF'}")

    def show_shortcuts_dialog(self):
        info = (
            "<h3>Silis IDE — Keyboard Shortcuts & Reference</h3>"
            "<table>"
            "<tr><td><b>Ctrl+N</b></td><td>New File</td></tr>"
            "<tr><td><b>Ctrl+O</b></td><td>Open File</td></tr>"
            "<tr><td><b>Ctrl+S</b></td><td>Save File & Project State</td></tr>"
            "<tr><td><b>Ctrl+Shift+N</b></td><td>New Project Wizard</td></tr>"
            "<tr><td><b>Ctrl+Shift+O</b></td><td>Open Project (.silisproj)</td></tr>"
            "<tr><td><b>Ctrl+L</b></td><td>Verilator Strict RTL Lint</td></tr>"
            "<tr><td><b>Ctrl+= / Ctrl++</b></td><td>Increase Editor Font Size</td></tr>"
            "<tr><td><b>Ctrl+-</b></td><td>Decrease Editor Font Size</td></tr>"
            "<tr><td><b>F1</b></td><td>Compile RTL & Simulate Testbench</td></tr>"
            "<tr><td><b>F2</b></td><td>Run Synthesis & PAT Flow</td></tr>"
            "<tr><td><b>M</b></td><td>Measure Distance (Interactive Layout Ruler)</td></tr>"
            "<tr><td><b>Ctrl+I</b></td><td>Find Instance in Netlist/Layout</td></tr>"
            "</table>"
            "<p><b>Configuration Files:</b><br/>"
            "• Editor Configuration: <code>~/.silis/editorconfig.json</code><br/>"
            "• Custom Palettes: <code>~/.silis/colorconfig.json</code><br/>"
            "• User Settings: <code>~/.silis/usersettings.json</code><br/>"
            "• Project State: <code>[project_root]/silis.silisproj</code></p>"
        )
        QMessageBox.information(self, "Shortcuts & Configuration Reference", info)

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
            if hasattr(self.tab_compile, 'editor') and hasattr(self.tab_compile.editor, 'mark_dirty'):
                self.tab_compile.editor.mark_dirty(self.current_file, False)
                if hasattr(self.tab_compile.editor, 'run_linter'):
                    self.tab_compile.editor.run_linter(self.current_file)
            if self.current_file.endswith(('.v', '.sv')):
                if hasattr(self.tab_schem, 'invalidate_cache'):
                    self.tab_schem.invalidate_cache()
                elif hasattr(self.tab_compile, 'schem_view') and hasattr(self.tab_compile.schem_view, 'fast_view') and self.tab_compile.schem_view.fast_view:
                    self.tab_compile.schem_view.fast_view.clear()

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
        if os.path.basename(cwd) in ["rtl", "tb", "constr", "source", "netlist", "reports", "results"]:
            return os.path.dirname(cwd)
            
        # 3. Default: the current directory is the project root
        return cwd

    def prep_workspace(self, base):
        root = self.get_proj_root(base)
        # Create standard layout: rtl, tb, constr, netlist, reports, results
        has_rtl_dir = os.path.isdir(os.path.join(root, "rtl"))
        rtl_dir = os.path.join(root, "rtl") if has_rtl_dir or not os.path.isdir(os.path.join(root, "source")) else os.path.join(root, "source")
        tb_dir = os.path.join(root, "tb") if os.path.isdir(os.path.join(root, "tb")) or not os.path.isdir(os.path.join(root, "source")) else os.path.join(root, "source")
        for d in ["rtl", "tb", "constr", "netlist", "reports", "results"]:
            os.makedirs(os.path.join(root, d), exist_ok=True)
        files = [f"{base}.v", f"tb_{base}.v", f"{base}_tb.v", f"test_{base}.v", f"{base}.sv"]
        search_dirs = list(set([os.path.abspath(self.cwd), root]))
        for fname in files:
            target_sub = tb_dir if any(x in fname.lower() for x in ["tb_", "_tb", "test_"]) else rtl_dir
            if os.path.exists(os.path.join(target_sub, fname)): continue
            found = None
            for s_dir in search_dirs:
                possible = os.path.join(s_dir, fname)
                if os.path.exists(possible): found = possible; break
            if found:
                try: 
                    shutil.move(found, os.path.join(target_sub, fname))
                    self.log_system(f"Moved {fname} -> {os.path.basename(target_sub)}/")
                except: pass
        return root

    def open_waves(self):
        if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'bottom_tabs'):
            self.tab_compile.bottom_tabs.setCurrentIndex(2)
        self.tab_waves.auto_load()

    def harvest_logs(self, root):
        p = os.path.join(root, "reports/synthesis.log")
        if os.path.exists(p):
            with open(p) as f:
                content = f.read()
                if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'log_view'):
                    self.tab_compile.log_view.setPlainText(content)
                if hasattr(self, 'tab_synth') and hasattr(self.tab_synth, 'log_main'):
                    self.tab_synth.log_main.setPlainText(content)
    
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
                if hasattr(self.tab_compile, 'bottom_tabs'):
                    self.tab_compile.bottom_tabs.setCurrentIndex(2) # Switch bottom tab to Waveform

            elif tag == "ASSERTION_MARKERS":
                if hasattr(self.tab_waves, 'set_assertion_markers'):
                    self.tab_waves.set_assertion_markers(content)

            elif tag == "OPEN_REPORT":
                if os.path.exists(content):
                    self.open_file_in_editor(content)

            elif tag == "UPDATE_DASHBOARD":
                self.tab_synth.update_dashboard()

            elif tag == "START_SIM_SPINNER":
                self.start_sim_spinner(content or "UVM RUNNING")

            elif tag == "STOP_SIM_SPINNER":
                self.stop_sim_spinner(content or "[OK] Simulation finished.")
                
            elif tag in ["[YOSYS]", "[STA]", "[DFT]", "SYNTH_LOG", "STA_LOG"]:
                if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'log_view'):
                    self.tab_compile.log_view.append(content)
                    sb_comp = self.tab_compile.log_view.verticalScrollBar()
                    sb_comp.setValue(sb_comp.maximum())
                if hasattr(self, 'tab_synth') and hasattr(self.tab_synth, 'log_main'):
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
        if hasattr(self, 'tab_compile') and hasattr(self.tab_compile, 'bottom_tabs'):
            self.tab_compile.bottom_tabs.setCurrentIndex(1)
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
    
    # 0. First-boot onboarding & SDK host bridge registration
    try:
        from core.setup_wizard import run_first_boot_if_needed
        run_first_boot_if_needed(app=app)
    except Exception as _e_init:
        print(f"[Silis Init] Note on first-boot check: {_e_init}")

    try:
        from core.sdk_installer import check_and_auto_bootstrap
        check_and_auto_bootstrap()
    except Exception as _e_sdk:
        print(f"[Silis Init] Note on SDK bridge check: {_e_sdk}")

    # Try loading settings
    font_fam = USER_SETTINGS.get("font_family", "Consolas")
    font_size = USER_SETTINGS.get("font_size", 11)
    
    # Check if a project file or initial tab was requested for GUI launch
    proj_to_open = None
    target_tab = None
    launch_backend_standalone = False
    argv_copy = list(sys.argv[1:])
    idx = 0
    while idx < len(argv_copy):
        arg = argv_copy[idx]
        if arg in ["--bend", "--backend"]:
            launch_backend_standalone = True
            argv_copy.pop(idx)
        elif arg in ["--tab", "-t"] and idx + 1 < len(argv_copy):
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
    
    # If standalone backend mode requested via --bend / --backend
    if launch_backend_standalone:
        window.switch_world(1)
        if hasattr(window, 'backend_widget') and window.backend_widget:
            window.backend_widget.viz_tabs.setCurrentIndex(0)
    # If initial tab was requested, or auto-detect current project stage
    elif target_tab:
        if target_tab in ["synth", "synthesis", "4"]:
            window.switch_world(0)
            if hasattr(window, 'tab_compile') and hasattr(window.tab_compile, 'bottom_tabs'):
                window.tab_compile.bottom_tabs.setCurrentIndex(1)
        elif target_tab in ["schem", "schematic", "3"]:
            window.switch_world(0)
            window.generate_schematic()
        elif target_tab in ["waves", "waveform", "2"]:
            window.switch_world(0)
            if hasattr(window, 'tab_compile') and hasattr(window.tab_compile, 'bottom_tabs'):
                window.tab_compile.bottom_tabs.setCurrentIndex(2)
        elif target_tab in ["compile", "editor", "1"]:
            window.switch_world(0)
            if hasattr(window, 'tab_compile') and hasattr(window.tab_compile, 'bottom_tabs'):
                window.tab_compile.bottom_tabs.setCurrentIndex(0)
        elif target_tab in ["layout", "backend", "floorplan", "place", "route"]:
            window.switch_world(1)
            window.backend_widget.viz_tabs.setCurrentIndex(0)
    elif proj_to_open and window.project_config:
        # Smart auto-detection: if DEF exists, open Layout view; else if netlist exists, open Synthesis log view
        top = window.project_config.get("top_module", "design")
        root = os.path.dirname(os.path.abspath(proj_to_open)) if proj_to_open.endswith(".json") else os.path.abspath(proj_to_open)
        if os.path.exists(os.path.join(root, "results", "temp.def")) or os.path.exists(os.path.join(root, "results", "design.def")):
            window.switch_world(1)
        elif os.path.exists(os.path.join(root, "netlist", f"{top}_netlist.v")) or os.path.exists(os.path.join(root, "netlist", "design.v")):
            window.switch_world(0)
            if hasattr(window, 'tab_compile') and hasattr(window.tab_compile, 'bottom_tabs'):
                window.tab_compile.bottom_tabs.setCurrentIndex(1) # LOG TAB

    window.show()
    window.raise_()
    window.activateWindow()
    
    sys.exit(app.exec())
