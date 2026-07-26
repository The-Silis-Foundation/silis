import os
from PyQt6.QtWidgets import *
from PyQt6.QtSvgWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from schematicviewer.blockdiagram import parse_and_draw_json, SchematicBlock

class SilisSchematic(QGraphicsView):
    module_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def load_svg(self, path):
        self.scene.clear()
        if not (os.path.exists(path) and path.endswith(".svg")): return
        item = QGraphicsSvgItem(path)
        self.scene.addItem(item)
        self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def load_json(self, path, module, mode):
        self.scene.clear()
        if not (os.path.exists(path) and path.endswith(".json")): return
        parse_and_draw_json(self.scene, path, module, mode)
        self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, SchematicBlock):
            module = item.data(0)
            if module and module != "BOUNDARY":
                self.module_clicked.emit(module)
                return
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 0.85
        self.scale(factor, factor)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_0 or event.key() == Qt.Key.Key_F:
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            super().keyPressEvent(event)

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
        self.btn_fit.clicked.connect(lambda: self.view.fitInView(self.view.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio))
        
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
        _, base = self.ide.get_context()
        if base:
            self.on_module_clicked(base, force_mode="top")
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
        elif path.endswith(".json"):
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
        
        all_src = glob.glob(os.path.join(root, "source", "*.v")) + glob.glob(os.path.join(root, "source", "*.sv"))
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

