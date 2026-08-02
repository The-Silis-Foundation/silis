import os
import sys
import subprocess
import time
import hashlib
import gdstk
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6 import sip

sys.path.append("/home/jerome/silis/third-party/GDS3D/build")
try:
    import gds3d_engine
except ImportError:
    gds3d_engine = None

class LODPolygonItem(QGraphicsPolygonItem):
    # 0.5 = Aggressive (Fastest)
    # 0.1 = Standard
    LOD_THRESHOLD = 0.5 

    def __init__(self, polygon, parent=None):
        super().__init__(polygon, parent)
        # 1. Cache the bounding rect (Massive speedup for 100k items)
        self._rect = polygon.boundingRect()
        # 2. Disable selection/collision checks if you don't need them
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self):
        return self._rect

    def shape(self):
        # 3. Cheat: Return a box instead of a complex polygon shape
        # This makes "itemAt" queries 100x faster
        path = QPainterPath()
        path.addRect(self._rect)
        return path

    def paint(self, painter, option, widget):
        # 4. The LOD Check
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod < self.LOD_THRESHOLD:
            return # Skip drawing completely
            
        super().paint(painter, option, widget)
        

class GDSViewerWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Optimization Flags for Speed
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False) 
        self.setOptimizationFlags(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing | 
                                  QGraphicsView.OptimizationFlag.DontSavePainterState)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor("#000000")) 
        
        self.layer_colors = {}
        self.layer_groups = {} 
        self.loaded_file = None

    def get_color(self, layer, datatype):
        key = (layer, datatype)
        if key not in self.layer_colors:
            import hashlib
            hash_bytes = hashlib.md5(f"{layer}-{datatype}".encode()).digest()
            self.layer_colors[key] = QColor(hash_bytes[0], hash_bytes[1], hash_bytes[2], 180)
        return self.layer_colors[key]

    def load_gds(self, gds_path):
        if not os.path.exists(gds_path): return
        
        self.scene.clear()
        self.layer_groups.clear()
        self.loaded_file = gds_path
        
        try:
            library = gdstk.read_gds(gds_path)
            top_cells = library.top_level()
            if not top_cells: return
            self.render_cell(top_cells[0])
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        except Exception as e:
            print(f"GDS Load Error: {e}")

    def render_cell(self, cell):
        flat_cell = cell.flatten()
        layer_buckets = {}
        
        # Bucketing for fast layer toggling
        for polygon in flat_cell.polygons:
            key = (polygon.layer, polygon.datatype)
            if key not in layer_buckets: layer_buckets[key] = []
            
            points = [QPointF(pt[0], -pt[1]) for pt in polygon.points]
            if not points: continue
            
            # Use our custom LOD Item
            item = LODPolygonItem(QPolygonF(points))
            
            col = self.get_color(*key)
            item.setBrush(QBrush(col))
            
            # [FIXED] Correct syntax for NoPen in PyQt6
            item.setPen(QPen(Qt.PenStyle.NoPen))
            
            layer_buckets[key].append(item)
            
        # Group items by layer for the sidebar toggle
        for key, items in layer_buckets.items():
            group = self.scene.createItemGroup(items)
            self.layer_groups[key] = group

    def set_layer_visible(self, layer, datatype, visible):
        key = (layer, datatype)
        if key in self.layer_groups:
            self.layer_groups[key].setVisible(visible)

    def get_layers(self):
        return sorted(list(self.layer_groups.keys()))

    def wheelEvent(self, event):
        zoom_in = 1.25
        old_pos = self.mapToScene(event.position().toPoint())
        if event.angleDelta().y() > 0: self.scale(zoom_in, zoom_in)
        else: self.scale(1/zoom_in, 1/zoom_in)
        new_pos = self.mapToScene(event.position().toPoint())
        self.translate(new_pos.x() - old_pos.x(), new_pos.y() - old_pos.y())


class GDS3DPort(QWidget):
    def __init__(self, parent_ide=None):
        super().__init__(parent_ide)
        self.ide = parent_ide
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.header = QWidget()
        self.header.setStyleSheet("background: #1e1e1e; border-bottom: 2px solid #fd8c73;")
        self.header.setFixedHeight(45)
        h_lay = QHBoxLayout(self.header)
        h_lay.setContentsMargins(10, 5, 10, 5)
        
        self.btn_load = QPushButton("Load GDS in 3D")
        self.btn_load.setStyleSheet("background: #2da44e; color: white; font-weight: bold; padding: 5px 15px; border-radius: 4px;")
        self.btn_load.clicked.connect(self.prompt_load)
        
        h_lay.addWidget(QLabel("<b style='color:#c9d1d9'>Hardware Accelerated GDS3D (Native)</b>"))
        h_lay.addStretch()
        h_lay.addWidget(self.btn_load)
        self.layout.addWidget(self.header)
        
        self.canvas = QWidget()
        self.canvas.setStyleSheet("background: #2d2d2d;")
        self.canvas_layout = QVBoxLayout(self.canvas)
        self.canvas_layout.setContentsMargins(0,0,0,0)
        self.layout.addWidget(self.canvas, stretch=1)
        
        self.core = None
        self.native_widget = None
        
        if gds3d_engine:
            self.core = gds3d_engine.GDS3DViewerCore()
            ptr = self.core.get_ptr()
            self.native_widget = sip.wrapinstance(ptr, QWidget)
            self.canvas_layout.addWidget(self.native_widget)
        else:
            self.canvas_layout.addWidget(QLabel("GDS3D Engine failed to load! Compile it first."))

    def prompt_load(self):
        try:
            proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
            results_dir = os.path.join(proj_root, "results")
        except AttributeError:
            results_dir = os.getcwd() 
            
        gds_path, _ = QFileDialog.getOpenFileName(self, "Select GDS File for 3D Viewer", results_dir, "GDSII Files (*.gds);;All Files (*)")
        if not gds_path: return
        self.load_gds(gds_path)

    def load_gds(self, path):
        if not os.path.exists(path) or not self.core: return
        process_file = os.path.expanduser("~/silis/third-party/GDS3D/techfiles/sky130.txt")
        if not os.path.exists(process_file):
            print("Warning: Missing sky130.txt process file for GDS3D!")
            return
        
        self.core.load_gds(path, process_file, "")
