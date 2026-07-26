import os
import subprocess
import time
import hashlib
import gdstk
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

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
        
        # --- 1. THE ESCAPE HATCH (Header Bar) ---
        self.header = QWidget()
        self.header.setStyleSheet("background: #1e1e1e; border-bottom: 2px solid #fd8c73;")
        self.header.setFixedHeight(45)
        h_lay = QHBoxLayout(self.header)
        h_lay.setContentsMargins(10, 5, 10, 5)
        
        self.btn_close_3d = QPushButton("Close 3D Viewer")
        self.btn_close_3d.setStyleSheet("background: #cf222e; color: white; font-weight: bold; padding: 5px 15px; border-radius: 4px;")
        self.btn_close_3d.clicked.connect(self.kill_viewer)
        self.btn_close_3d.hide() # Hidden until viewer is running
        
        h_lay.addWidget(QLabel("<b style='color:#c9d1d9'>Hardware Accelerated GDS3D</b>"))
        h_lay.addStretch()
        h_lay.addWidget(self.btn_close_3d)
        self.layout.addWidget(self.header)
        
        # --- 2. THE TRACKING CANVAS ---
        self.canvas = QWidget()
        self.canvas.setStyleSheet("background: #2d2d2d;") # Dark background while loading
        self.canvas_layout = QVBoxLayout(self.canvas)
        self.layout.addWidget(self.canvas, stretch=1)
        
        # UI: Launch Button (Lives inside the Canvas)
        self.btn_launch = QPushButton("🚀 Launch 3D GDS Viewer")
        self.btn_launch.setFixedSize(250, 50)
        self.btn_launch.setStyleSheet("font-size: 14px; font-weight: bold; background: #2da44e; color: white; border-radius: 6px;")
        self.btn_launch.clicked.connect(self.launch_viewer)
        
        self.info_label = QLabel("Click to bind the Chameleon Overlay.\nUse Left/Right Click to Rotate & Pan in 3D.")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #8b949e;")
        
        self.canvas_layout.addStretch()
        self.canvas_layout.addWidget(self.btn_launch, alignment=Qt.AlignmentFlag.AlignCenter)
        self.canvas_layout.addWidget(self.info_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.canvas_layout.addStretch()
        
        # State Tracking
        self.gds3d_proc = None
        self.wid = None
        self.last_geom = (0, 0, 0, 0)
        self.is_mapped = False
        self.track_timer = QTimer(self)
        self.track_timer.timeout.connect(self.sync_overlay)

    def launch_viewer(self):
        # The Highlander Protocol
        subprocess.call(["killall", "-9", "gds3d"], stderr=subprocess.DEVNULL)
        if self.gds3d_proc and self.gds3d_proc.poll() is None:
            self.gds3d_proc.kill()

        try:
            proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
            results_dir = os.path.join(proj_root, "results")
        except AttributeError:
            results_dir = os.getcwd() 
            
        gds_path, _ = QFileDialog.getOpenFileName(self, "Select GDS File for 3D Viewer", results_dir, "GDSII Files (*.gds);;All Files (*)")
        
        if not gds_path:
            return # User canceled
        process_file = os.path.expanduser("~/GDS3D/techfiles/sky130.txt")
        
        if not os.path.exists(gds_path) or not os.path.exists(process_file):
            self.info_label.setText("❌ Missing GDS or Tech file!")
            self.info_label.setStyleSheet("color: #ff7b72;")
            return

        self.btn_launch.setEnabled(False)
        self.btn_launch.setText("Binding to OS...")

        try:
            self.gds3d_proc = subprocess.Popen(["gds3d", "-p", process_file, "-i", gds_path]) 
            self.bind_chameleon_overlay()
        except FileNotFoundError:
            self.info_label.setText("❌ 'gds3d' executable not found!")
            self.info_label.setStyleSheet("color: #ff7b72;")
            self.btn_launch.setEnabled(True)
            self.btn_launch.setText("🚀 Launch 3D GDS Viewer")

    def bind_chameleon_overlay(self):
        max_attempts = 30 
        self.wid = None
        
        for _ in range(max_attempts):
            try:
                out = subprocess.check_output(['xdotool', 'search', '--onlyvisible', '--name', 'GDS3D']).decode('utf-8').strip()
                wids = out.splitlines()
                if wids:
                    self.wid = wids[-1] 
                    break
            except subprocess.CalledProcessError:
                pass
            time.sleep(0.1) 
            
        if not self.wid:
            self.info_label.setText("❌ Timeout: GDS3D Window never appeared.")
            self.btn_launch.setEnabled(True)
            self.btn_launch.setText("🚀 Launch 3D GDS Viewer")
            return

        try:
            # Decapitate borders and force on top
            subprocess.call(['xprop', '-id', self.wid, '-f', '_MOTIF_WM_HINTS', '32c', '-set', '_MOTIF_WM_HINTS', '2, 0, 0, 0, 0'])
            subprocess.call(['wmctrl', '-i', '-r', hex(int(self.wid)), '-b', 'add,above'])

            # Hide Launch UI, Show Escape Hatch
            self.btn_launch.hide()
            self.info_label.hide()
            self.btn_close_3d.show()
                
            self.is_mapped = True
            self.track_timer.start(16) 
            
        except Exception as e:
            self.info_label.setText(f"❌ Overlay Binding Failed:\n{e}")
            self.btn_launch.setEnabled(True)
            self.btn_launch.setText("🚀 Launch 3D GDS Viewer")

    def sync_overlay(self):
        if not self.wid: return

        currently_visible = self.isVisible() and not self.window().isMinimized()

        if currently_visible and not self.is_mapped:
            subprocess.Popen(['xdotool', 'windowmap', self.wid])
            self.is_mapped = True
        elif not currently_visible and self.is_mapped:
            subprocess.Popen(['xdotool', 'windowunmap', self.wid])
            self.is_mapped = False

        if not currently_visible:
            return 

        # --- THE FIX: Track the CANVAS, not the whole widget ---
        global_pos = self.canvas.mapToGlobal(QPoint(0, 0))
        x, y = global_pos.x(), global_pos.y()
        w, h = self.canvas.width(), self.canvas.height()

        if (x, y, w, h) != self.last_geom:
            subprocess.Popen(['xdotool', 'windowsize', self.wid, str(w), str(h)])
            subprocess.Popen(['xdotool', 'windowmove', self.wid, str(x), str(y)])
            self.last_geom = (x, y, w, h)

    def kill_viewer(self):
        """ The Escape Hatch Logic """
        # Murder the process
        if self.gds3d_proc:
            self.gds3d_proc.kill()
        subprocess.call(["killall", "-9", "gds3d"], stderr=subprocess.DEVNULL)
        
        # Stop tracking
        self.track_timer.stop()
        self.is_mapped = False
        self.wid = None
        self.last_geom = (0, 0, 0, 0)
        
        # Restore UI
        self.btn_close_3d.hide()
        self.btn_launch.show()
        self.btn_launch.setText("🚀 Launch 3D GDS Viewer")
        self.btn_launch.setEnabled(True)
        self.info_label.show()
        self.info_label.setText("Viewer closed. Ready to launch again.")
        self.info_label.setStyleSheet("color: #8b949e;")

    def closeEvent(self, event):
        self.kill_viewer()
        super().closeEvent(event)


