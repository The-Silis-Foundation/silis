import os
import sys

# --- Fix for PyQt6 missing symbol error ---
qt_lib_path = "/usr/local/lib/python3.12/dist-packages/PyQt6/Qt6/lib"
current_ld = os.environ.get("LD_LIBRARY_PATH", "")
os.environ["QTWEBENGINEPROCESS_PATH"] = "/usr/lib/qt6/libexec/QtWebEngineProcess"
os.environ["QTWEBENGINE_RESOURCES_PATH"] = "/usr/share/qt6/resources"
os.environ["QTWEBENGINE_LOCALES_PATH"] = "/usr/share/qt6/translations/qtwebengine_locales"
if qt_lib_path not in current_ld:
    os.environ["LD_LIBRARY_PATH"] = f"{qt_lib_path}:{current_ld}" if current_ld else qt_lib_path
    os.execv(sys.executable, [sys.executable] + sys.argv)
# ------------------------------------------

import json
import glob
import subprocess
import time
import queue
import threading
import shutil
import re
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

# Importing extracted modules
from config import THEMES, USER_SETTINGS, save_user_settings
from editor.editor import CommandPalette, FileSearchPalette, VSCodeEditorTabs, ScintillaEditor
from terminal.terminal import VSCodeTerminalWidget
from pdkmanagers.pdk.manager import SSAForge, PDKManager, PDKSelector
from pdkmanagers.volare import VolareManagerWidget
from backendflow.siliconpeeker.peeker import DEFParser, SiliconPeeker
from signalpeeker.code import SignalPeeker
from schematicviewer.graphiccanvas import SchematicTab
from synthesisscripts.synthesisthread import SynthesisTab
from backendflow.flow.backendflow import BackendWidget
from projectwizard.codes import SilisProjectWizard, SilisLauncher

class SilisExplorer(QTreeView):
    fileOpened = pyqtSignal(str)
    dirChanged = pyqtSignal(str)
    gds3dOpened = pyqtSignal(str)

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
        self.explorer.gds3dOpened.connect(self.ide.open_gds3d)
        l_lay.addWidget(QLabel("PROJECT EXPLORER")); l_lay.addWidget(self.explorer)
        self.split.addWidget(self.explorer_container)

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
        USER_SETTINGS["custom_theme"] = THEMES["Custom"]
        USER_SETTINGS["external_editor"] = self.e_ext_edit.text()
        save_user_settings(USER_SETTINGS)

        
        # Update Editor
        if hasattr(self.ide.tab_compile, 'editor'):
            self.ide.tab_compile.editor.update_appearance(font_family, font_size, theme_name)
            
        # Update Terminal
        if hasattr(self.ide.tab_compile, 'terminal'):
            self.ide.tab_compile.terminal.update_appearance(font_family, font_size, THEMES[theme_name])
            
        # Update Silicon Peeker
        if hasattr(self.ide.tab_compile, 'peeker'):
            self.ide.tab_compile.peeker.update_appearance()
            
        self.accept()





class SilisIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silis — Silicon Scaffold v2.1")
        self.resize(1400, 900)
        self.cwd = os.getcwd(); self.current_file = None; self.pdk_path = ""
        self.project_config = None; self.active_pdk = None
        self.pdk_mgr = PDKManager()
        
        launcher = SilisLauncher(self)
        if launcher.exec() == QDialog.DialogCode.Accepted:
            self.cwd = launcher.selected_project_path
            os.chdir(self.cwd)
            self.project_config = launcher.selected_project_config
            pdk_name = self.project_config.get("pdk")
            self.active_pdk = next((cfg for cfg in self.pdk_mgr.configs if cfg['name'] == pdk_name), None)
            if not self.active_pdk:
                QMessageBox.warning(None, "PDK Missing", f"The project's PDK '{pdk_name}' was not found in your cache.")
            proj_name = self.project_config.get("project_name", "Unknown")
            self.setWindowTitle(f"Silis — Silicon Scaffold v2.1 - [{proj_name}]")
        else:
            import sys
            sys.exit(0)
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

        if self.cwd:
            if hasattr(self.tab_compile, 'file_system_model') and hasattr(self.tab_compile, 'tree_view'):
                self.tab_compile.file_system_model.setRootPath(self.cwd)
                self.tab_compile.tree_view.setRootIndex(self.tab_compile.file_system_model.index(self.cwd))
            top_mod = self.project_config.get("top_module") if self.project_config else None
            if top_mod:
                for f_path in self.project_config.get("rtl_files", []):
                    if top_mod in os.path.basename(f_path):
                        target_name = os.path.basename(f_path)
                        found = False
                        for root_dir, _, files in os.walk(self.cwd):
                            if target_name in files:
                                self.open_file_in_editor(os.path.join(root_dir, target_name))
                                found = True
                                break
                        if found: break

    # === UX: SMART SHORTCUTS ===
    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
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
                    ("Go to: 3D Viewer", lambda: (self.switch_world(1), self.backend_widget.viz_tabs.setCurrentIndex(2))),
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
                
                # Position and size perfectly over the file explorer
                explorer_rect = self.tab_compile.explorer_container.geometry()
                global_pos = self.tab_compile.mapToGlobal(explorer_rect.topLeft())
                pal.move(global_pos)
                pal.setFixedSize(explorer_rect.width(), explorer_rect.height())
                
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
                        subprocess.Popen(f"{cmd} {path}", shell=True)
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
                # Give it a moment to write (simple block)
                self.backend_widget.proc.waitForReadyRead(3000) 
                
        import os
        import subprocess
        try:
            pid = os.getpid()
            # Find all child processes using pgrep
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

    # === CORE LOGIC ===

    # === REPLACE IN SilisIDE CLASS ===
    def generate_schematic(self):
        if self.schem_running:
            self.log_system("Schematic generation in progress...", "WARN")
            return
        self.tab_schem.go_home()

    def run_synthesis_flow(self):
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
            self.log_system("[ERR] No Active PDK selected.")
            return
            
        self.pdk_path = self.active_pdk['lib']
        self.run_synthesis_thread(root, base)

    def run_synthesis_thread(self, root, base):
        # Clear the unified log before starting
        self.tab_synth.log_main.clear()
        self.tab_synth.card_status.setText("RUNNING...")
        self.tab_synth.card_status.setStyleSheet("background:#eaeef2; color:#57606a; font-weight:bold; padding:15px; border-radius:6px; border: 1px solid #d0d7de;")

        v_net = f"netlist/{base}_netlist.v"
        
        src_v = []
        if hasattr(self, 'project_config') and self.project_config and self.project_config.get("rtl_files"):
            for f_path in self.project_config.get("rtl_files", []):
                abs_path = os.path.join(self.cwd, f_path) if not os.path.isabs(f_path) else f_path
                src_v.append(abs_path)
        else:
            src_v = glob.glob(os.path.join(root, "source", "*.v")) + \
                    glob.glob(os.path.join(root, "source", "*.sv")) + \
                    glob.glob(os.path.join(root, "source", "*.vhd")) + \
                    glob.glob(os.path.join(root, "source", "*.vhdl"))
                    
        src_v = [s for s in src_v if "tb_" not in os.path.basename(s).lower()]
        
        vhdl_files = [s for s in src_v if s.endswith('.vhd') or s.endswith('.vhdl')]
        vlog_files = [s for s in src_v if not (s.endswith('.vhd') or s.endswith('.vhdl'))]
        
        # Sort VHDL files: packages must be compiled first!
        vhdl_files = sorted(vhdl_files, key=lambda x: 0 if any(k in os.path.basename(x).lower() for k in ['pack', 'pkg', 'type', 'const']) else 1)
        
        read_cmd = "plugin -i ghdl;\n" if vhdl_files else ""
        if vhdl_files:
            work_lib = os.path.basename(root)
            if hasattr(self, 'project_config') and self.project_config:
                work_lib = self.project_config.get("vhdl_work", self.project_config.get("project_name", work_lib))
                # For NeoRV32 specifically, the VHDL library must be 'neorv32'
                if "neorv32" in root.lower() or "neorv32" in work_lib.lower():
                    work_lib = "neorv32"
            read_cmd += f"ghdl --work={work_lib} {' '.join(vhdl_files)} -e {base};\n"
        if vlog_files:
            read_cmd += f"read_verilog {' '.join(vlog_files)};\n"
        
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
        sdc_files = glob.glob(os.path.join(root, "source", "*.sdc"))
        rel_sdc = os.path.relpath(sdc_files[0], root) if sdc_files else f"source/{base}.sdc"
        tcl = f"""
        set_thread_count [exec nproc]
        read_liberty {self.pdk_path}
        read_verilog {v_net}
        link_design {base}
        read_sdc {rel_sdc}
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
        src_v = glob.glob(os.path.join(root, "source", "*.v")) + \
                glob.glob(os.path.join(root, "source", "*.sv")) + \
                glob.glob(os.path.join(root, "source", "*.vhd")) + \
                glob.glob(os.path.join(root, "source", "*.vhdl"))
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
        self.tab_compile.terminal.append_output(f"[{tag}] {msg}")
    def change_directory(self, path):
        if os.path.exists(path):
            os.chdir(path); self.cwd = os.getcwd(); self.tab_compile.explorer.set_cwd(self.cwd)
            self.log_system(f"CD -> {self.cwd}", "SYS")

    def open_file_in_editor(self, path):
        if os.path.exists(path):
            self.tab_compile.editor.open_file(path)
            self.current_file = path; self.lbl_proj.setText(os.path.basename(path))

    def open_gds3d(self, path):
        if os.path.exists(path):
            self.backend_widget.gds3d_port.load_gds(path)
            self.switch_world(1)
            self.backend_widget.viz_tabs.setCurrentIndex(2)
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
            with open(self.current_file, 'w') as f: f.write(self.tab_compile.editor.toPlainText())
            self.log_system(f"Saved {os.path.basename(self.current_file)}")
            self.lbl_proj.setText(os.path.basename(self.current_file))
            if self.current_file.endswith(('.v', '.sv')):
                self.tab_schem.invalidate_cache()

    def get_context(self):
        content = self.tab_compile.editor.toPlainText()
        m = re.search(r'(?:module|entity)\s+(\w+)', content, re.IGNORECASE)
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

            # [NEW] Route terminal command output to the VSCode terminal widget
            if tag == "TERM_OUT":
                self.tab_compile.terminal.append_output(content)

            # [NEW] Route Backend-specific messages to Backend Terminal
            elif tag == "[BACKEND]":
                self.backend_widget.append_output(content)
            elif tag == "[BACKEND_GDS_DONE]":
                QMessageBox.information(self, "GDS Generation Complete", f"GDS layout successfully exported to:\n\n{content}")

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

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    
    # Try loading settings
    font_fam = USER_SETTINGS.get("font_family", "Consolas")
    font_size = USER_SETTINGS.get("font_size", 11)
    
    # Pre-load alias database so IDE doesn't block later
    SSAForge.load_aliases()
    
    window = SilisIDE()
    window.show()
    
    # Launch Wizard if no project loaded
    QTimer.singleShot(100, lambda: SilisLauncher(window).exec() if not window.current_file else None)
    
    sys.exit(app.exec())
