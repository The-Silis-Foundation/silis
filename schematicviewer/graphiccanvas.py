import os
import sys
from PyQt6.QtWidgets import *
from PyQt6.QtSvgWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "build"))
try:
    import schematic_engine
except ImportError:
    schematic_engine = None

from PyQt6 import sip

class SilisSchematic(QWidget):
    module_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.stack = QStackedWidget(self)
        
        # Fast C++ View (New Main Engine)
        if schematic_engine:
            self.fast_view = schematic_engine.SchematicViewerCore()
            import os
            html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "digitaljs.html"))
            self.fast_view.init_url(html_path)
            ptr = self.fast_view.get_ptr()
            self.native_fast_view = sip.wrapinstance(ptr, QWidget)
            self.native_fast_view.installEventFilter(self)
            self.stack.addWidget(self.native_fast_view)
        else:
            self.fast_view = None
            self.native_fast_view = QLabel("Failed to load C++ Schematic Engine. Please recompile.")
            self.native_fast_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stack.addWidget(self.native_fast_view)
            
        self.layout.addWidget(self.stack)

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
        self.stack.setCurrentWidget(self.svg_view)
        self.svg_scene.clear()
        if not (os.path.exists(path) and path.endswith(".svg")): return
        item = QGraphicsSvgItem(path)
        self.svg_scene.addItem(item)
        self.svg_view.fitInView(self.svg_scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def load_json(self, path, module, mode):
        if schematic_engine and self.fast_view:
            self.stack.setCurrentWidget(self.native_fast_view)
            self.fast_view.clear()
            if not (os.path.exists(path) and path.endswith(".json")): return
            self.fast_view.load_json(path, module, mode)
            self.fast_view.fit_in_view()

    def fitInView(self, rect=None, mode=None):
        if self.stack.currentWidget() == self.native_fast_view:
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
        lay.setContentsMargins(0,0,0,0)
        
        tb = QHBoxLayout()
        self.btn_back = QPushButton("< Back")
        self.btn_forward = QPushButton("Forward >")
        self.btn_mode = QPushButton("View: Block")
        self.btn_home = QPushButton("Top Level")
        self.btn_fit = QPushButton("Fit")
        
        self.btn_back.clicked.connect(self.go_back)
        self.btn_forward.clicked.connect(self.go_forward)
        self.btn_mode.clicked.connect(self.toggle_mode)
        self.btn_home.clicked.connect(self.go_home)
        self.btn_fit.clicked.connect(lambda: self.view.fitInView())
        
        tb.addWidget(self.btn_back)
        tb.addWidget(self.btn_forward)
        tb.addWidget(self.btn_mode)
        tb.addWidget(self.btn_home)
        tb.addWidget(self.btn_fit)
        tb.addStretch()
        
        self.view = SilisSchematic()
        self.view.module_clicked.connect(self.on_module_clicked)
        
        lay.addLayout(tb)
        lay.addWidget(self.view)
        self.update_ui_state()

    def update_ui_state(self):
        self.btn_back.setEnabled(self.current_idx > 0)
        self.btn_forward.setEnabled(self.current_idx < len(self.history_stack) - 1)
        if 0 <= self.current_idx < len(self.history_stack):
            mode = self.history_stack[self.current_idx]["mode"]
            self.btn_mode.setText("View: Gate-Level" if mode == "gate" else "View: Block")

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
            self.view.load_json(path, module, mode)

    def toggle_mode(self):
        if 0 <= self.current_idx < len(self.history_stack):
            entry = self.history_stack[self.current_idx]
            new_mode = "gate" if entry["mode"] in ["top", "block"] else "block"
            self.history_stack = self.history_stack[:self.current_idx]
            self.current_idx -= 1
            self.on_module_clicked(entry["module"], force_mode=new_mode)

    def on_module_clicked(self, module_name, force_mode=None):
        if force_mode:
            mode = force_mode
        else:
            if 0 <= self.current_idx < len(self.history_stack):
                curr_mode = self.history_stack[self.current_idx]["mode"]
                if curr_mode == "top":
                    mode = "block"
                elif curr_mode == "block":
                    mode = "gate"
                else:
                    mode = "block"
            else:
                mode = "block"
                
        self.history_stack = self.history_stack[:self.current_idx + 1]
        self.invoke_engine(module_name, mode)
        
    def invoke_engine(self, module_name, mode):
        from schematicviewer.dotschemmaker import YosysStructuralWorker
        import glob
        
        proj_root, base = self.ide.get_context()
        if not proj_root: return
        
        root = self.ide.prep_workspace(base) if base else proj_root
        
        all_src = glob.glob(os.path.join(root, "source", "*.v")) + \
                  glob.glob(os.path.join(root, "source", "*.sv")) + \
                  glob.glob(os.path.join(root, "source", "*.vhd")) + \
                  glob.glob(os.path.join(root, "source", "*.vhdl"))
        src = [f for f in all_src if not any(x in os.path.basename(f).lower() for x in ["tb_", "_tb", "test_"])]
        
        if not src:
            self.ide.log_system("No synthesis sources found.", "ERR")
            return
            
        pdk_lib = None
        if mode == "gate" and hasattr(self.ide, 'active_pdk') and self.ide.active_pdk:
            pdk_lib = self.ide.active_pdk.get("lib")
                
        self.ide.schem_running = True
        self.btn_home.setEnabled(False)
        self.btn_home.setText("Crunching...")
        
        self.worker = YosysStructuralWorker(root, src, module_name, mode, pdk_lib)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.log.connect(self.ide.log_system)
        self.worker.start()

    def on_worker_finished(self, out_path, module, mode):
        self.ide.schem_running = False
        self.btn_home.setEnabled(True)
        self.btn_home.setText("Top Level")
        
        self.history_stack.append({"module": module, "mode": mode, "out_path": out_path})
        self.current_idx = len(self.history_stack) - 1
        self.update_ui_state()
        self.load_from_path(out_path, module, mode)

    def invalidate_cache(self):
        self.history_stack.clear()
        self.current_idx = -1
        self.view.scene.clear()

