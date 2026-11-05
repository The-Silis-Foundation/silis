import os
import sys
from PyQt6.QtWidgets import *
from PyQt6.QtSvgWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

try:
    import qt_setup
except ImportError:
    pass

_sch_dir = os.path.dirname(os.path.abspath(__file__))
if _sch_dir not in sys.path:
    sys.path.append(_sch_dir)
if os.path.join(_sch_dir, "build") not in sys.path:
    sys.path.append(os.path.join(_sch_dir, "build"))

try:
    import schematic_engine
except ImportError:
    schematic_engine = None

from PyQt6 import sip
from PyQt6.QtWebEngineWidgets import QWebEngineView
import json

class SilisSchematic(QWidget):
    module_clicked = pyqtSignal(str)
    schematic_action = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.stack = QStackedWidget(self)
        self.fast_view = None
        self.native_fast_view = None
        self.layout.addWidget(self.stack)

    def ensure_engine(self):
        if self.fast_view is not None:
            return self.fast_view
        if schematic_engine:
            self.fast_view = schematic_engine.SchematicViewerCore()
            import os
            html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "digitaljs.html"))
            self.fast_view.init_url(html_path)
            ptr = self.fast_view.get_ptr()
            self.native_fast_view = sip.wrapinstance(ptr, QWebEngineView)
            self.native_fast_view.installEventFilter(self)
            self.native_fast_view.titleChanged.connect(self._on_title_changed)
            self.stack.addWidget(self.native_fast_view)
        else:
            self.fast_view = None
            self.native_fast_view = QLabel("Failed to load C++ Schematic Engine. Please recompile.")
            self.native_fast_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stack.addWidget(self.native_fast_view)
        return self.fast_view

    def _on_title_changed(self, title):
        prefix = "SILIS_SCHEM_MSG:"
        if not title or not title.startswith(prefix):
            return
        payload = title[len(prefix):]
        # Strip trailing seq tag if present (#<seq>)
        hash_idx = payload.rfind('#')
        if hash_idx != -1:
            payload = payload[:hash_idx]
        try:
            data = json.loads(payload)
            self.schematic_action.emit(data)
        except Exception as e:
            print(f"[Schematic Bridge] Error decoding bridge message: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        self.ensure_engine()

    def eventFilter(self, obj, event):
        if obj == self.native_fast_view and event.type() == QEvent.Type.MouseButtonDblClick:
            x, y = event.position().x(), event.position().y()
            if hasattr(self.fast_view, 'hit_test'):
                module = self.fast_view.hit_test(x, y)
                if module and module != "BOUNDARY":
                    self.module_clicked.emit(module)
                    return True
        return super().eventFilter(obj, event)

    def load_svg(self, path):
        self.ensure_engine()
        self.stack.setCurrentWidget(self.svg_view)
        self.svg_scene.clear()
        if not (os.path.exists(path) and path.endswith(".svg")): return
        item = QGraphicsSvgItem(path)
        self.svg_scene.addItem(item)
        self.svg_view.fitInView(self.svg_scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def load_json(self, path, module, mode):
        self.ensure_engine()
        if schematic_engine and self.fast_view:
            self.stack.setCurrentWidget(self.native_fast_view)
            self.fast_view.clear()
            if not (os.path.exists(path) and path.endswith(".json")): return
            self.fast_view.load_json(path, module, mode)
            self.fast_view.fit_in_view()

    def set_wire_values(self, updates):
        if not updates: return
        self.ensure_engine()
        if hasattr(self, 'native_fast_view') and hasattr(self.native_fast_view, 'page'):
            import json
            js = f"if (typeof setSchematicWireValues === 'function') {{ setSchematicWireValues({json.dumps(updates)}); }}"
            self.native_fast_view.page().runJavaScript(js)

    def clear_wire_values(self):
        self.ensure_engine()
        if hasattr(self, 'native_fast_view') and hasattr(self.native_fast_view, 'page'):
            self.native_fast_view.page().runJavaScript("if (typeof clearSchematicWireValues === 'function') { clearSchematicWireValues(); }")

    def highlight_net_or_cell(self, target_name):
        if not target_name: return
        self.ensure_engine()
        if hasattr(self, 'native_fast_view') and hasattr(self.native_fast_view, 'page'):
            import json
            js = f"if (typeof highlightNetOrCell === 'function') {{ highlightNetOrCell({json.dumps(target_name)}); }}"
            self.native_fast_view.page().runJavaScript(js)

    def fitInView(self, rect=None, mode=None):
        if self.native_fast_view and self.stack.currentWidget() == self.native_fast_view:
            if hasattr(self.fast_view, 'fit_in_view'):
                self.fast_view.fit_in_view()


class SchematicTab(QWidget):
    def __init__(self, ide):
        super().__init__()
        self.ide = ide
        self.worker = None
        self.history_stack = []
        self.current_idx = -1
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        
        self.view = SilisSchematic()
        self.view.module_clicked.connect(self.on_module_clicked)
        self.view.schematic_action.connect(self.on_schematic_action)
        
        lay.addWidget(self.view)
        self.update_ui_state()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'view') and hasattr(self.view, 'ensure_engine'):
            self.view.ensure_engine()

    def update_ui_state(self):
        can_back = self.current_idx > 0
        can_forward = self.current_idx < len(self.history_stack) - 1
        js = f"if (typeof updateNavButtons === 'function') updateNavButtons({str(can_back).lower()}, {str(can_forward).lower()});"
        if hasattr(self.view, 'native_fast_view') and hasattr(self.view.native_fast_view, 'page'):
            self.view.native_fast_view.page().runJavaScript(js)

    def on_instance_selected(self, index):
        pass

    def go_home(self):
        self.history_stack.clear()
        self.current_idx = -1
        import json
        _, base = self.ide.get_context()
        if base:
            top_mod = base
            proj_root = self.ide.get_proj_root(base)
            proj_file = os.path.join(proj_root, "silis.silisproj") if proj_root else None
            if proj_file and os.path.exists(proj_file):
                try:
                    with open(proj_file, 'r') as f:
                        top_mod = json.load(f).get("top_module", base)
                        if not top_mod: top_mod = base
                except: pass
            self.on_module_clicked(top_mod, force_mode="top")
        else:
            self.ide.log_system("No Top Module found", "ERR")

    def go_back(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.load_from_history()

    def go_forward(self):
        if self.current_idx < len(self.history_stack) - 1:
            self.current_idx += 1
            self.load_from_history()
            
    def load_from_history(self):
        entry = self.history_stack[self.current_idx]
        self.update_ui_state()
        self.load_from_path(entry["out_path"], entry["module"], entry["mode"])

    def load_from_path(self, path, module, mode):
        if not os.path.exists(path):
            self.invoke_engine(module, mode)
            return
        if path.endswith(".svg"):
            self.view.load_svg(path)
        elif path.endswith(".json"):   # covers both .json and .hier.json
            import json
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                
                # Apply current theme to WebEngine
                if hasattr(self.view, 'fast_view') and self.view.fast_view is not None:
                    try:
                        from config import USER_SETTINGS
                        theme_name = USER_SETTINGS.get("theme_name", "Catppuccin Mocha")
                    except ImportError:
                        theme_name = "Catppuccin Mocha"
                        
                    color_cfg = os.path.join(os.path.dirname(os.path.dirname(__file__)), "editor", "colorconfig.json")
                    if os.path.exists(color_cfg):
                        with open(color_cfg, 'r') as cf:
                            all_themes = json.load(cf)
                            colors = all_themes.get(theme_name)
                            if not colors:
                                colors = all_themes.get("Catppuccin Mocha", {})
                        if colors:
                            if hasattr(self.view.fast_view, 'set_theme'):
                                self.view.fast_view.set_theme(json.dumps(colors))
                            
            except Exception as e:
                print("Error parsing json for UI:", e)
                
            self.view.load_json(path, module, mode)

    def toggle_mode(self):
        if 0 <= self.current_idx < len(self.history_stack):
            entry = self.history_stack[self.current_idx]
            new_mode = "gate" if entry["mode"] in ["top", "block"] else "block"
            self.history_stack = self.history_stack[:self.current_idx]
            self.current_idx -= 1
            self.on_module_clicked(entry["module"], force_mode=new_mode)

    def on_module_clicked(self, module_name, force_mode=None):
        # Always maintain block schematic view
        mode = "block"
        self.history_stack = self.history_stack[:self.current_idx + 1]
        self.invoke_engine(module_name, mode)
        
    def invoke_engine(self, module_name, mode):
        from schematicviewer.dotschemmaker import YosysStructuralWorker
        import glob
        
        proj_root, base = self.ide.get_context()
        if not proj_root: return
        
        root = self.ide.prep_workspace(base) if base else proj_root
        
        all_src = []
        if hasattr(self.ide, 'project_config') and self.ide.project_config and self.ide.project_config.get("rtl_files"):
            for f_path in self.ide.project_config.get("rtl_files", []):
                abs_path = os.path.join(self.ide.cwd, f_path) if not os.path.isabs(f_path) else f_path
                all_src.append(abs_path)
        else:
            search_dirs = [d for d in [os.path.join(root, "rtl"), os.path.join(root, "source")] if os.path.isdir(d)]
            if not search_dirs:
                search_dirs = [root]
            for sdir in search_dirs:
                for pat in ("*.v", "*.sv", "*.vhd", "*.vhdl"):
                    for f in glob.glob(os.path.join(sdir, pat)):
                        if f not in all_src:
                            all_src.append(f)
        
        src = [f for f in all_src if not any(x in os.path.basename(f).lower() for x in ["tb_", "_tb", "test_"])]
        
        if not src:
            self.ide.log_system("No synthesis sources found.", "ERR")
            return
            
        pdk_lib = None
        if mode == "gate" and hasattr(self.ide, 'active_pdk') and self.ide.active_pdk:
            pdk_lib = self.ide.active_pdk.get("lib")
                
        self.ide.schem_running = True
        if hasattr(self, 'btn_home'):
            self.btn_home.setEnabled(False)
            self.btn_home.setText("Crunching...")
        
        self.worker = YosysStructuralWorker(root, src, module_name, mode, pdk_lib)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.log.connect(self.ide.log_system)
        self.worker.start()

    def on_worker_finished(self, out_path, module, mode):
        self.ide.schem_running = False
        if hasattr(self, 'btn_home'):
            self.btn_home.setEnabled(True)
            self.btn_home.setText("Top Level")
        
        self.history_stack.append({"module": module, "mode": mode, "out_path": out_path})
        self.current_idx = len(self.history_stack) - 1
        self.update_ui_state()
        self.load_from_path(out_path, module, mode)

        # Notify DesignExplorerPanel to build real-time hierarchy
        if hasattr(self.ide, 'tab_compile') and hasattr(self.ide.tab_compile, 'explorer_panel'):
            self.ide.tab_compile.explorer_panel.load_design_json(out_path, top_module=module)

    def invalidate_cache(self):
        self.history_stack.clear()
        self.current_idx = -1
        if hasattr(self.view, 'fast_view') and self.view.fast_view:
            self.view.fast_view.clear()

    def highlight_net_or_cell(self, target_name):
        if hasattr(self, 'view') and hasattr(self.view, 'highlight_net_or_cell'):
            self.view.highlight_net_or_cell(target_name)

    def on_schematic_action(self, msg):
        """
        Handles user interactions forwarded from sv-pathfinder / DigitalJS webview.
        Supports:
          - stepInto: navigates hierarchy into the child subcircuit module
          - goToParent: navigates back to parent module in hierarchy
          - gotoSource / gotoDefinition: opens Monaco editor jumped to the source line/col
          - setPreset: switches between RTL and Gate-Level view
          - addToWaveform: adds the clicked signal/instance to the waveform viewer
          - copyName / copyValue: copies to clipboard
          - refresh: reloads current schematic
        """
        if not isinstance(msg, dict):
            return
        mtype = msg.get("type")
        if mtype == "contextAction":
            action = msg.get("action")
            leaf = msg.get("leafName")
            celltype = msg.get("celltype")
            source_positions = msg.get("sourcePositions", [])

            if action == "stepInto":
                target = celltype or leaf
                if target:
                    self.on_module_clicked(target, force_mode="block")

            elif action == "gotoDefinition":
                # Always navigate to definition of module/celltype
                target = celltype or leaf
                self._handle_goto_definition(target)

            elif action == "gotoSource":
                # Navigate to instance location in source
                self._handle_goto_source(target_name=celltype or leaf, positions=source_positions)

            elif action == "copyName":
                if leaf:
                    QGuiApplication.clipboard().setText(leaf)
                    self.ide.log_system(f"Copied '{leaf}' to clipboard", "SYS")

            elif action == "copyValue":
                val = msg.get("value")
                if val is not None:
                    QGuiApplication.clipboard().setText(str(val))
                    self.ide.log_system(f"Copied value '{val}' to clipboard", "SYS")

            elif action == "addToWaveform":
                target_sig = leaf or celltype
                if target_sig and hasattr(self.ide, 'add_waveform_signal'):
                    self.ide.add_waveform_signal(target_sig)

        elif mtype == "goToParent":
            self.go_back()

        elif mtype == "schemNavBack" or msg.get("command") == "schemNavBack":
            self.go_back()

        elif mtype == "schemNavForward" or msg.get("command") == "schemNavForward":
            self.go_forward()

        elif mtype == "setPreset":
            # Always maintain block schematic view
            target_mode = "block"
            if 0 <= self.current_idx < len(self.history_stack):
                curr = self.history_stack[self.current_idx]
                if curr.get("mode") != target_mode:
                    self.history_stack = self.history_stack[:self.current_idx]
                    self.current_idx -= 1
                    self.on_module_clicked(curr["module"], force_mode=target_mode)

        elif mtype == "refresh":
            if 0 <= self.current_idx < len(self.history_stack):
                curr = self.history_stack[self.current_idx]
                self.invoke_engine(curr["module"], curr["mode"])

    def _handle_goto_definition(self, target_name):
        import re
        import glob

        if not target_name:
            return

        proj_root, base = self.ide.get_context()
        root = self.ide.prep_workspace(base) if base else proj_root
        if not root or not os.path.exists(root):
            return

        src_candidates = (
            glob.glob(os.path.join(root, "rtl", "*.v")) +
            glob.glob(os.path.join(root, "rtl", "*.sv")) +
            glob.glob(os.path.join(root, "rtl", "*.vhd")) +
            glob.glob(os.path.join(root, "rtl", "*.vhdl")) +
            glob.glob(os.path.join(root, "tb", "*.v")) +
            glob.glob(os.path.join(root, "tb", "*.sv")) +
            glob.glob(os.path.join(root, "source", "*.v")) +
            glob.glob(os.path.join(root, "source", "*.sv")) +
            glob.glob(os.path.join(root, "source", "*.vhd")) +
            glob.glob(os.path.join(root, "source", "*.vhdl")) +
            glob.glob(os.path.join(root, "*.v")) +
            glob.glob(os.path.join(root, "*.sv"))
        )

        mod_pattern = re.compile(rf'\b(?:module|entity)\s+{re.escape(target_name)}\b')
        for path in src_candidates:
            try:
                with open(path, 'r', errors='ignore') as f:
                    for lno, line in enumerate(f, 1):
                        if mod_pattern.search(line):
                            self.ide.open_file_in_editor(path, lno, 1)
                            return
            except Exception:
                pass

    def _handle_goto_source(self, target_name, positions):
        import re
        import glob

        # 1. First attempt: check precise sourcePositions emitted from Yosys/DigitalJS
        if positions and isinstance(positions, list):
            first_pos = positions[0]
            file_name = first_pos.get("name")
            from_pos = first_pos.get("from", {})
            line = from_pos.get("line")
            col = from_pos.get("column", 1)

            if file_name:
                abs_file = file_name
                if not os.path.isabs(abs_file):
                    proj_root, base = self.ide.get_context()
                    root = self.ide.prep_workspace(base) if base else proj_root
                    abs_file = os.path.join(root, file_name)
                if os.path.exists(abs_file):
                    self.ide.open_file_in_editor(abs_file, line, col)
                    return

        # 2. Fallback attempt: search project source files for target module / instance declaration
        if not target_name:
            return

        proj_root, base = self.ide.get_context()
        root = self.ide.prep_workspace(base) if base else proj_root
        if not root or not os.path.exists(root):
            return

        src_candidates = (
            glob.glob(os.path.join(root, "rtl", "*.v")) +
            glob.glob(os.path.join(root, "rtl", "*.sv")) +
            glob.glob(os.path.join(root, "rtl", "*.vhd")) +
            glob.glob(os.path.join(root, "rtl", "*.vhdl")) +
            glob.glob(os.path.join(root, "tb", "*.v")) +
            glob.glob(os.path.join(root, "tb", "*.sv")) +
            glob.glob(os.path.join(root, "source", "*.v")) +
            glob.glob(os.path.join(root, "source", "*.sv")) +
            glob.glob(os.path.join(root, "source", "*.vhd")) +
            glob.glob(os.path.join(root, "source", "*.vhdl")) +
            glob.glob(os.path.join(root, "*.v")) +
            glob.glob(os.path.join(root, "*.sv"))
        )

        mod_pattern = re.compile(rf'\b(?:module|entity)\s+{re.escape(target_name)}\b')
        inst_pattern = re.compile(rf'\b{re.escape(target_name)}\b')

        # Check for instance name first for gotoSource
        for path in src_candidates:
            try:
                with open(path, 'r', errors='ignore') as f:
                    for lno, line in enumerate(f, 1):
                        if inst_pattern.search(line):
                            self.ide.open_file_in_editor(path, lno, 1)
                            return
            except Exception:
                pass

        # Then fallback to module definition
        for path in src_candidates:
            try:
                with open(path, 'r', errors='ignore') as f:
                    for lno, line in enumerate(f, 1):
                        if mod_pattern.search(line):
                            self.ide.open_file_in_editor(path, lno, 1)
                            return
            except Exception:
                pass


