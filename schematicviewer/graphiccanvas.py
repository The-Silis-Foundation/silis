import os
import subprocess
import shutil
from PyQt6.QtWidgets import *
from PyQt6.QtSvgWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

class SilisSchematic(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # High Quality Rendering Attributes
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # Navigation
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # Clean UI
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def load_schematic(self, path):
        self.scene.clear()
        if os.path.exists(path) and path.endswith(".svg"):
            # Render SVG
            item = QGraphicsSvgItem(path)
            self.scene.addItem(item)
            # Auto-Fit to screen on load
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        # Smooth Zoom
        factor = 1.15 if event.angleDelta().y() > 0 else 0.85
        self.scale(factor, factor)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_0 or key == Qt.Key.Key_F:
            # 'F' or '0' to Reset View
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            super().keyPressEvent(event)
            
    def contextMenuEvent(self, event):
        # Right Click Menu
        menu = QMenu(self)
        reset_act = QAction("Fit to View", self)
        reset_act.triggered.connect(lambda: self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio))
        menu.addAction(reset_act)
        menu.exec(event.globalPos())

class SchematicTab(QWidget):
    def __init__(self, ide):
        super().__init__()
        self.ide = ide; lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        tb = QHBoxLayout()
        self.btn_gen = QPushButton("Generate Logic View"); self.btn_gen.clicked.connect(self.ide.generate_schematic)
        btn_fit = QPushButton("Fit"); btn_fit.clicked.connect(lambda: self.view.fitInView(self.view.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio))
        tb.addWidget(self.btn_gen); tb.addWidget(btn_fit); tb.addStretch()
        self.view = SilisSchematic(); lay.addLayout(tb); lay.addWidget(self.view)


class SchematicWorker(QThread):
    finished = pyqtSignal(str); log = pyqtSignal(str, str)
    
    def __init__(self, root, base, engine, src_files):
        super().__init__()
        self.root = root
        self.base = base
        self.src_files = src_files

    def run(self):
        # 1. Check for Graphviz (The Painter)
        if not shutil.which("dot"):
            self.log.emit("Graphviz ('dot') not found!", "ERR")
            self.log.emit("Run: sudo apt install graphviz", "TIP")
            return

        # Prepare paths
        read_cmd = "".join([f"read_verilog {s}; " for s in self.src_files])
        dot_base = os.path.join(self.root, self.base) # Yosys adds .dot automatically
        dot_file = dot_base + ".dot"
        svg_file = dot_base + ".svg"
        
        if os.path.exists(dot_file): os.remove(dot_file)

        # === STRATEGY 1: High-Level RTL (Best for reading) ===
        # 'proc' converts processes to logic. 'memory' handles arrays.
        # We explicitly use -prefix to control the output filename.
        cmd_rtl = f"yosys -p '{read_cmd} hierarchy -check -top {self.base}; proc; opt; show -colors 2 -width -stretch -format dot -prefix {dot_base}'"
        
        # === STRATEGY 2: Structural (Fallback if logic is too complex) ===
        # No optimization, just raw connectivity.
        cmd_raw = f"yosys -p '{read_cmd} hierarchy -auto-top; proc; show -colors 2 -width -stretch -format dot -prefix {dot_base}'"

        try:
            self.log.emit("Generating logic graph...", "SYS")
            
            # Try elegant RTL view first
            res = subprocess.run(cmd_rtl, shell=True, cwd=self.root, capture_output=True, text=True)
            
            # If RTL view failed (or produced empty dot), try raw view
            if not os.path.exists(dot_file):
                self.log.emit("Complex render failed. Trying structural view...", "WARN")
                subprocess.run(cmd_raw, shell=True, cwd=self.root, capture_output=True, text=True)

            # 3. Convert DOT to SVG (The Visualizer)
            if os.path.exists(dot_file):
                self.log.emit("Rendering SVG...", "SYS")
                # -Grankdir=LR makes it flow Left-to-Right (Standard Schematic style)
                subprocess.run(f"dot -Tsvg {dot_file} -o {svg_file} -Grankdir=LR", shell=True, cwd=self.root)
                
                if os.path.exists(svg_file):
                    self.finished.emit(svg_file)
                    self.log.emit("Schematic Ready.", "SYS")
                else:
                    self.log.emit("Graphviz failed to convert DOT to SVG.", "ERR")
            else:
                self.log.emit("Yosys failed to generate graph. Check syntax.", "ERR")
                self.log.emit(f"Yosys Stderr: {res.stderr[:200]}...", "DBG")

        except Exception as e:
            self.log.emit(f"Schematic Engine Crash: {e}", "ERR")





if __name__ == "__main__":
    QImageReader.setAllocationLimit(0)
    app = QApplication(sys.argv)
    w = SilisIDE()
    w.show()
    sys.exit(app.exec())

