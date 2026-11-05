import os
import re
import glob
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from config import THEMES, USER_SETTINGS
from PyQt6 import sip
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fast_viewer", "build"))
try:
    import fast_layout_viewer
except ImportError:
    fast_layout_viewer = None


class DEFParser:
    def __init__(self, def_path, ide=None):
        self.path = def_path
        self.ide = ide
        self.comp_sizes = {}
        self.comp_classes = {}
        self.parse_macro_sizes()
        self.die_rect = QRectF(0,0,0,0)
        self.comps_map = {}   
        self.comp_types = {}  
        self.comp_masters = {} 
        self.comp_orients = {}
        self.module_map = {}  
        self.pins = []       
        self.power_rails = [] 
        self.power_routes = [] 
        self.signal_routes = [] 
        self.regions = []
        self.blockages = []
        self.dbu = 1000.0    
        self.std_coords_flat = [] # [x, y, w, h, ...] for zero-overhead C++ ingest
        self.tap_coords = []
        self.macro_items = [] # (x, y, w, h, name)
        self.component_count = 0
        if os.path.exists(def_path):
            self.parse()

    def parse_macro_sizes(self):
        try:
            import os, glob, re, json
            search_dirs = []
            proj_d = None
            if self.ide and getattr(self.ide, 'current_project_dir', None):
                proj_d = self.ide.current_project_dir
            elif self.path:
                cand = os.path.dirname(os.path.dirname(os.path.abspath(self.path)))
                if cand not in ["/", "/tmp", "/var", "/home", "/usr", "/etc"] and os.path.isdir(cand):
                    proj_d = cand
                else:
                    cand2 = os.path.dirname(os.path.abspath(self.path))
                    if cand2 not in ["/", "/tmp", "/var", "/home", "/usr", "/etc"] and os.path.isdir(cand2):
                        proj_d = cand2

            if proj_d and os.path.isdir(proj_d):
                search_dirs.append(proj_d)
                src = os.path.join(proj_d, "source")
                if os.path.isdir(src): search_dirs.append(src)
                
                # Preload sizes from reports if available
                rep_dir = os.path.join(proj_d, "reports")
                if os.path.isdir(rep_dir):
                    for fp_sf in glob.glob(os.path.join(rep_dir, "*_floorplan_save.json")):
                        try:
                            with open(fp_sf, 'r') as f:
                                fp_data = json.load(f)
                            for m in fp_data.get("macros", []):
                                if "name" in m and "w" in m and "h" in m:
                                    self.comp_sizes[m["name"]] = (float(m["w"]), float(m["h"]))
                        except:
                            pass

            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            bundled_pdk = os.path.join(repo_root, "third-party", "pdks")
            if os.path.isdir(bundled_pdk):
                search_dirs.append(bundled_pdk)

            if getattr(self.ide, 'active_pdk', None):
                lib_path = self.ide.active_pdk.get('lib', '')
                if "libs.ref" in lib_path:
                    search_dirs.append(lib_path.split("libs.ref")[0])

            env_pdk = os.environ.get("PDK_ROOT")
            if env_pdk and os.path.isdir(env_pdk):
                search_dirs.append(env_pdk)

            for d in search_dirs:
                if not os.path.exists(d): continue
                for root, _, files in os.walk(d):
                    rel = os.path.relpath(root, d)
                    if rel.count(os.sep) > 3:
                        continue
                    for file in files:
                        if file.endswith(".lef"):
                            lef = os.path.join(root, file)
                            try:
                                with open(lef, 'r') as f:
                                    content = f.read()
                                name = os.path.basename(lef).replace('.lef', '')
                                m = re.search(r'SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)', content)
                                if m:
                                    self.comp_sizes[name] = (float(m.group(1)), float(m.group(2)))
                                for match in re.finditer(r'MACRO\s+([\w\d_]+)([\s\S]*?)END\s+\1', content):
                                    m_name = match.group(1)
                                    m_body = match.group(2)
                                    sz_m = re.search(r'SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)', m_body)
                                    if sz_m:
                                        self.comp_sizes[m_name] = (float(sz_m.group(1)), float(sz_m.group(2)))
                                    cls_m = re.search(r'CLASS\s+([^;\s]+)', m_body)
                                    if cls_m:
                                        self.comp_classes[m_name] = cls_m.group(1).upper()
                            except:
                                pass
        except:
            pass

    def parse(self):
        if not os.path.exists(self.path): return

        with open(self.path, 'r') as f:
            lines = f.readlines()

        current_section = None
        std_w, std_h = 5.0, 2.72 
        
        current_comp_name = None
        current_comp_model = None
        current_pin_name = None
        
        # Route State
        current_route_width = 0
        current_route_points = [] 
        parsing_route = False
        
        # Routing Context
        last_x = None
        last_y = None

        for line in lines:
            try:
                line = line.strip()
                if not line or line.startswith('#'): continue

                # --- GLOBAL ---
                if line.startswith("UNITS DISTANCE MICRONS"):
                    parts = line.split()
                    if len(parts) >= 4:
                        self.dbu = float(parts[3])
                        std_w = 5 * self.dbu 
                        std_h = 2.72 * self.dbu 

                elif line.startswith("DIEAREA"):
                    nums = re.findall(r'(-?\d+)', line)
                    if len(nums) >= 4:
                        x1, y1, x2, y2 = map(int, nums[:4])
                        self.die_rect = QRectF(x1, y1, x2-x1, y2-y1)

                # --- SECTIONS ---
                elif line.startswith("COMPONENTS"): 
                    current_section = "COMPONENTS"
                    parsing_route = False
                elif line.startswith("PINS"): 
                    current_section = "PINS"
                    parsing_route = False
                elif line.startswith("SPECIALNETS"): 
                    current_section = "SPECIALNETS"
                elif line.startswith("NETS") and "SPECIAL" not in line: 
                    current_section = "NETS"
                elif line.startswith("REGIONS"):
                    current_section = "REGIONS"
                elif line.startswith("BLOCKAGES"):
                    current_section = "BLOCKAGES"
                elif line.startswith("END"): 
                    if len(current_route_points) >= 2:
                        if current_section == "SPECIALNETS": self.power_routes.append((current_route_width, current_route_points))
                        elif current_section == "NETS": self.signal_routes.append(current_route_points)
                    current_section = None
                    current_route_points = []
                    parsing_route = False

                # --- COMPONENTS ---
                elif current_section == "COMPONENTS":
                    parts = line.split()
                    if line.startswith("-"):
                        if len(parts) >= 3:
                            current_comp_name = parts[1]
                            current_comp_model = parts[2]
                            is_placed = False
                            is_macro = False
                            x, y = 0, 0
                    
                        if "PLACED" in line or "FIXED" in line or "COVER" in line:
                            coord_match = re.search(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*([A-Za-z0-9_]+)?', line)
                            if coord_match:
                                x = int(coord_match.group(1))
                                y = int(coord_match.group(2))
                                orient = coord_match.group(3) if coord_match.group(3) else "N"
                                is_placed = True
                        
                        w, h = std_w, std_h
                        if current_comp_model in self.comp_sizes:
                            w = self.comp_sizes[current_comp_model][0] * self.dbu
                            h = self.comp_sizes[current_comp_model][1] * self.dbu
                            
                        is_macro_by_size = (w / self.dbu > 20 or h / self.dbu > 20)
                            
                        if is_placed:
                            bb_x, bb_y = x, y
                            bb_w, bb_h = w, h
                            if is_macro_by_size:
                                if orient in ["W", "E", "FW", "FE", "R90", "R270", "MYR90", "MXR90", "MX90", "MY90"]:
                                    bb_w, bb_h = h, w
                                
                            self.comps_map[current_comp_name] = QRectF(bb_x, bb_y, bb_w, bb_h)
                            
                            model_lower = current_comp_model.lower()
                            is_tap = "tap" in model_lower or "fill" in model_lower or "decap" in model_lower
                            is_clock = "clk" in model_lower and not current_comp_name.startswith("_")

                            # Check LEF class and model traits
                            lef_class = self.comp_classes.get(current_comp_model, "")
                            is_lef_macro = any(k in lef_class for k in ["PAD", "RING", "BLOCK", "COVER"])
                            is_pad_model = ("_io" in model_lower or "pad" in model_lower or "corner" in model_lower or "slice" in model_lower)

                            if is_lef_macro or is_pad_model or (is_macro_by_size and not is_tap and lef_class != "CORE"):
                                self.comp_types[current_comp_name] = "MACRO"
                                self.macro_items.append((bb_x, bb_y, bb_w, bb_h, current_comp_name))
                            elif is_tap:
                                self.comp_types[current_comp_name] = "TAP"
                                self.tap_coords.extend([bb_x, bb_y, bb_w, bb_h])
                            elif is_clock:
                                self.comp_types[current_comp_name] = "CLOCK"
                                self.std_coords_flat.extend([bb_x, bb_y, bb_w, bb_h])
                            else:
                                self.comp_types[current_comp_name] = "STD"
                                self.std_coords_flat.extend([bb_x, bb_y, bb_w, bb_h])
                            
                            self.comp_masters[current_comp_name] = current_comp_model
                            self.comp_orients[current_comp_name] = orient
                            self.module_map[current_comp_name] = "STD_LOGIC" 
                            self.component_count += 1
                        
                        if ";" in line: current_comp_name = None

                # --- PINS ---
                elif current_section == "PINS":
                    parts = line.split()
                    if line.startswith("-") and len(parts) > 1:
                        current_pin_name = parts[1]
                        current_pin_port_rect = None

                    # Check for LAYER port dimensions: + LAYER <name> ( x1 y1 ) ( x2 y2 )
                    if "LAYER" in line:
                        layer_box = re.search(r'LAYER\s+\S+\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                        if layer_box:
                            lx1, ly1, lx2, ly2 = map(int, layer_box.groups())
                            current_pin_port_rect = (lx1, ly1, lx2 - lx1, ly2 - ly1)

                    if current_pin_name and ("PLACED" in line or "FIXED" in line):
                        coord_match = re.search(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                        if coord_match:
                            x = int(coord_match.group(1))
                            y = int(coord_match.group(2))
                            if current_pin_port_rect:
                                ox, oy, pw, ph = current_pin_port_rect
                                px = x + ox
                                py = y + oy
                                self.pins.append((QRectF(px, py, pw, ph), current_pin_name))
                            else:
                                pin_sz = 1.0 * self.dbu
                                self.pins.append((QRectF(x - pin_sz/2, y - pin_sz/2, pin_sz, pin_sz), current_pin_name))
                            current_pin_name = None
                            current_pin_port_rect = None 

                # --- REGIONS ---
                elif current_section == "REGIONS":
                    if line.startswith("-"):
                        parts = line.split()
                        if len(parts) >= 2:
                            r_name = parts[1]
                            coord_match = re.findall(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                            for c_i in range(0, len(coord_match) - 1, 2):
                                x1, y1 = int(coord_match[c_i][0]), int(coord_match[c_i][1])
                                x2, y2 = int(coord_match[c_i+1][0]), int(coord_match[c_i+1][1])
                                self.regions.append((QRectF(x1, y1, x2-x1, y2-y1), r_name))

                # --- BLOCKAGES ---
                elif current_section == "BLOCKAGES":
                    if "RECT" in line:
                        coord_match = re.search(r'RECT\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                        if coord_match:
                            x1, y1 = int(coord_match.group(1)), int(coord_match.group(2))
                            x2, y2 = int(coord_match.group(3)), int(coord_match.group(4))
                            self.blockages.append(QRectF(x1, y1, x2-x1, y2-y1))

                # --- ROUTING (FINAL RECT FIX) ---
                elif current_section in ["NETS", "SPECIALNETS"]:
                    
                    if "ROUTED" in line or "NEW" in line:
                        parsing_route = True
                        if len(current_route_points) >= 2:
                            if current_section == "SPECIALNETS": self.power_routes.append((current_route_width, current_route_points))
                            else: self.signal_routes.append(current_route_points)
                        
                        current_route_points = []
                        last_x = None 
                        last_y = None 

                        if current_section == "SPECIALNETS":
                            w_match = re.search(r'(?:ROUTED|NEW)\s+\S+\s+(\d+)', line)
                            if w_match:
                                current_route_width = int(w_match.group(1))

                    if "RECT" in line or "LAYER" in line:
                        continue 

                    if parsing_route:
                        if line.startswith("-") or ";" in line:
                            parsing_route = False
                            if len(current_route_points) >= 2:
                                if current_section == "SPECIALNETS": self.power_routes.append((current_route_width, current_route_points))
                                else: self.signal_routes.append(current_route_points)
                            current_route_points = []
                            last_x = None
                            last_y = None

                        if "(" in line:
                            raw_groups = line.split('(')
                            
                            for group in raw_groups[1:]: 
                                if ")" not in group: continue
                                content = group.split(')')[0]
                                
                                tokens = content.split()
                                if len(tokens) >= 2:
                                    val_x_str = tokens[0]
                                    val_y_str = tokens[1]
                                    
                                    x = None
                                    if val_x_str == "*": x = last_x
                                    elif val_x_str.lstrip('-').isdigit(): x = int(val_x_str)
                                    
                                    y = None
                                    if val_y_str == "*": y = last_y
                                    elif val_y_str.lstrip('-').isdigit(): y = int(val_y_str)
                                    
                                    if x is not None and y is not None:
                                        current_route_points.append(QPointF(x, y))
                                        last_x, last_y = x, y

            except Exception as inner_e:
                continue
        
        # EOF Flush
        if len(current_route_points) >= 2:
             if current_section == "SPECIALNETS":
                 self.power_routes.append((current_route_width, current_route_points))
             elif current_section == "NETS":
                 self.signal_routes.append(current_route_points)
        
        print(f"DEBUG: Parsed {self.component_count} comps, {len(self.power_routes)} pwr_segs, {len(self.signal_routes)} sig_nets.")


class SiliconPeeker(QGraphicsView):
    """
    [DEPRECATED] Legacy software-rendered CPU SiliconPeeker.
    Use FastSiliconPeeker which utilizes hardware-accelerated FastLayoutViewer C++.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        import warnings
        warnings.warn("SiliconPeeker is deprecated and sluggish. Use FastSiliconPeeker instead.", DeprecationWarning, stacklevel=2)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.theme = THEMES.get(USER_SETTINGS.get("theme_name", "Catppuccin Mocha"), THEMES["Catppuccin Mocha"])
        self.setBackgroundBrush(QBrush(QColor(self.theme.get("margin_bg", "#1E1E1E"))))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Optimization
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setOptimizationFlags(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing)
        
        # Flip Y (CAD Coordinates)
        self.scale(1, -1) 
        
        # Initial Default Scene Rect (Will be overridden by set_die_area)
        self.setSceneRect(0, 0, 1000, 1000)
        
        self.def_data = None
        self.first_load = True
        
        self.show_insts = True
        self.show_macros = True
        self.show_pins = True
        self.show_nets = True 
        self.show_power = True
        self.show_heatmap = False

        self.current_def_path = None
        self.last_mtime = 0
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self.check_refresh)
        # Note: Do not start timer until widget is visible (see showEvent/hideEvent)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'auto_refresh_timer') and not self.auto_refresh_timer.isActive():
            self.check_refresh()
            self.auto_refresh_timer.start(2000)

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, 'auto_refresh_timer') and self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()

    def check_refresh(self):
        if self.current_def_path and os.path.exists(self.current_def_path):
            mtime = os.path.getmtime(self.current_def_path)
            size = os.path.getsize(self.current_def_path)
            if mtime > self.last_mtime and size > 0:
                if getattr(self, '_last_size', -1) != size:
                    self._last_size = size
                    return
                self.last_mtime = mtime
                # Silently reload without resetting camera
                self.def_data = DEFParser(self.current_def_path, getattr(self, 'ide', None))
                self.redraw()

    def update_appearance(self):
        self.theme = THEMES.get(USER_SETTINGS.get("theme_name", "Catppuccin Mocha"), THEMES["Catppuccin Mocha"])
        self.setBackgroundBrush(QBrush(QColor(self.theme.get("margin_bg", "#1E1E1E"))))
        self.redraw()

    def set_die_area(self, x1, y1, x2, y2):
        """
        Called by BackendWidget to pre-set the view before DEF is loaded.
        Centers the chip in a scene that is 1.5x larger than the chip itself.
        """
        self.scene.clear()
        
        width = x2 - x1
        height = y2 - y1
        
        scene_w = width * 1.5
        scene_h = height * 1.5
        
        self.setSceneRect(0, 0, scene_w, scene_h)
        
        offset_x = (scene_w - width) / 2
        offset_y = (scene_h - height) / 2
        
        rect = QRectF(offset_x, offset_y, width, height)
        item = QGraphicsRectItem(rect)
        item.setPen(QPen(QColor("#000000"), 2))
        item.setBrush(QBrush(QColor("#eeeeee")))
        self.scene.addItem(item)
        
        t = self.scene.addText(f"Die Area: {width:.1f} x {height:.1f}")
        t.setPos(offset_x + width/2, offset_y + height/2)
        t.setTransform(QTransform().scale(1, -1))
        
        self.centerOn(offset_x + width/2, offset_y + height/2)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def drawForeground(self, painter, rect):
        # [FIX] CRITICAL GUARD CLAUSE
        if self.viewport().width() <= 0 or self.viewport().height() <= 0:
            return
            
        if not self.def_data: return
        
        try:
            painter.save()
            painter.resetTransform()
            
            view_transform = self.transform()
            zoom_level = view_transform.m11() 
            
            if self.def_data and self.def_data.dbu > 0:
                pixels_per_micron = zoom_level * self.def_data.dbu
            else:
                pixels_per_micron = zoom_level * 1000
            
            if pixels_per_micron > 0.1:
                target_px = 150
                target_microns = target_px / pixels_per_micron
                
                if target_microns >= 100: d_val = 100
                elif target_microns >= 10: d_val = 10
                elif target_microns >= 1: d_val = 1
                else: d_val = 0.1
                
                bar_w = d_val * pixels_per_micron
                vx, vy = self.viewport().width(), self.viewport().height()
                
                painter.setPen(QPen(Qt.GlobalColor.red, 2))
                painter.drawLine(int(vx - bar_w - 20), int(vy - 30), int(vx - 20), int(vy - 30))
                painter.drawText(int(vx - bar_w - 20), int(vy - 40), f"{d_val} µm")

            painter.restore()
        except Exception:
            pass

    def wheelEvent(self, event):
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor
        oldPos = self.mapToScene(event.position().toPoint())
        
        if event.angleDelta().y() > 0:
            self.scale(zoomInFactor, zoomInFactor)
        else:
            self.scale(zoomOutFactor, zoomOutFactor)
            
        newPos = self.mapToScene(event.position().toPoint())
        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())
        event.accept()
        self.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.viewport().update()

    def fit_with_slack(self):
        rect = self.scene.itemsBoundingRect()
        if rect.isNull(): return
        margin = max(rect.width(), rect.height()) * 0.1
        self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.AspectRatioMode.KeepAspectRatio)

    def load_def_file(self, path):
        self.current_def_path = path
        if not os.path.exists(path):
            return
        mtime = os.path.getmtime(path)
        size = os.path.getsize(path)
        if self.def_data is not None and getattr(self, 'last_mtime', 0) == mtime and getattr(self, '_last_size', 0) == size:
            return
        self.last_mtime = mtime
        self._last_size = size
        self.def_data = DEFParser(path, getattr(self, 'ide', None))
        self.redraw()
        if self.first_load:
            self.fit_with_slack()
            self.first_load = False

    def redraw(self):
        try:
            current_transform = self.transform()
            self.scene.clear()
            if not self.def_data: return

            d = self.def_data.die_rect
            
            self.setSceneRect(d.adjusted(-d.width()*0.25, -d.height()*0.25, d.width()*0.25, d.height()*0.25))
            
            die = QGraphicsRectItem(d)
            die.setPen(QPen(QColor(self.theme.get("sel", "#4A5568")), 0))
            die.setBrush(QBrush(QColor(self.theme.get("bg", "#2D323A")))) 
            die.setZValue(-100)
            self.scene.addItem(die)

            if self.def_data.component_count == 0 and d.width() > 0:
                t = self.scene.addText(f"Parsed {self.def_data.component_count} components")
                t.setPos(d.center().x(), d.center().y())
                t.setTransform(QTransform().scale(100, -100))
                t.setDefaultTextColor(QColor("red"))

            if self.show_heatmap:
                self.draw_organic_heatmap(d)
            else:
                # POWER
                if self.show_power:
                    for r in self.def_data.power_rails:
                        item = QGraphicsRectItem(r)
                        item.setPen(QPen(Qt.PenStyle.NoPen))
                        item.setBrush(QBrush(QColor(self.theme.get("num", "#ffaa00")))) 
                        item.setZValue(-5)
                        self.scene.addItem(item)
                    
                    if self.def_data.power_routes:
                        path = QPainterPath()
                        for width, points in self.def_data.power_routes:
                            if not points: continue
                            path.moveTo(points[0])
                            for p in points[1:]: path.lineTo(p)
                        
                        pen = QPen(QColor(self.theme.get("num", "#ffaa00")), 0)
                        item = QGraphicsPathItem(path)
                        item.setPen(pen)
                        item.setZValue(-5)
                        self.scene.addItem(item)

                # NETS (Signal)
                if self.show_nets:
                    path = QPainterPath()
                    for points in self.def_data.signal_routes:
                        if not points: continue
                        path.moveTo(points[0])
                        for p in points[1:]: path.lineTo(p)
                    
                    pen = QPen(QColor(self.theme.get("ident", "#4169E1")), 0)
                    item = QGraphicsPathItem(path)
                    item.setPen(pen)
                    item.setZValue(-5) 
                    self.scene.addItem(item)

                # CELLS
                if self.show_insts:
                    for name, rect in self.def_data.comps_map.items():
                        ctype = self.def_data.comp_types.get(name, "STD")
                        item = QGraphicsRectItem(rect)
                        
                        is_macro = (ctype == "MACRO") or (rect.width() / self.def_data.dbu > 20) or (rect.height() / self.def_data.dbu > 20)
                        
                        if is_macro and not self.show_macros: continue
                        if not is_macro and not self.show_insts: continue

                        if ctype == "TAP":
                            item.setPen(QPen(Qt.PenStyle.NoPen)) 
                            item.setBrush(QBrush(QColor("#000000"))) 
                            item.setZValue(-4) 
                        elif ctype == "CLOCK":
                            item.setPen(QPen(QColor("#800000"), 0)) 
                            item.setBrush(QBrush(QColor("#D00000"))) 
                            item.setZValue(15)
                        elif is_macro:
                            item.setPen(QPen(Qt.GlobalColor.black, 0))
                            item.setBrush(QBrush(QColor("#4CAF50")))
                            item.setZValue(12)
                            self.scene.addItem(item)
                            
                            master = self.def_data.comp_masters.get(name, "")
                            t = self.scene.addText(f"{name}\n({master})")
                            t.setDefaultTextColor(QColor("black"))
                            
                            br = t.boundingRect()
                            scale_x = (rect.width() * 0.9) / br.width()
                            scale_y = (rect.height() * 0.9) / br.height()
                            scale = min(scale_x, scale_y)
                            t.setTransform(QTransform().scale(scale, -scale))
                            
                            t.setPos(rect.center().x() - (br.width()*scale)/2, rect.center().y() + (br.height()*scale)/2)
                            t.setZValue(13)
                            continue
                        else:
                            item.setPen(QPen(QColor("#00509d"), 0)) 
                            item.setBrush(QBrush(QColor("#4cc9f0"))) 
                            item.setZValue(10)
                        
                        self.scene.addItem(item)

            # PINS
            if self.show_pins:
                for rect, name in self.def_data.pins:
                    cx, cy = rect.center().x(), rect.center().y()
                    sz = max(5 * self.def_data.dbu, d.width() / 150)
                    poly = QPolygonF([QPointF(cx, cy + sz), QPointF(cx - sz/2, cy), QPointF(cx + sz/2, cy)])
                    item = QGraphicsPolygonItem(poly)
                    item.setPen(QPen(QColor("#000000"), 0)) 
                    item.setBrush(QBrush(QColor("#ff0000")))
                    item.setZValue(30)
                    self.scene.addItem(item)
                    
                    text = self.scene.addText(name)
                    text.setPos(cx, cy)
                    sf = d.width() / 1200.0 if d.width() > 0 else 1.0
                    text.setTransform(QTransform().scale(sf, -sf)) 
                    text.setDefaultTextColor(QColor("black"))
                    text.setZValue(31)

            self.setTransform(current_transform)
            
        except Exception as e:
            print(f"Redraw Exception: {e}")

    def draw_organic_heatmap(self, die_rect):
        expansion = 8 * self.def_data.dbu 
        color = QColor(255, 0, 0, 8) 
        brush = QBrush(color)
        
        count = 0
        for rect in self.def_data.comps_map.values():
            count += 1
            if count > 40000: break
            
            big_rect = rect.adjusted(-expansion, -expansion, expansion, expansion)
            final_rect = big_rect.intersected(die_rect)
            
            if not final_rect.isEmpty():
                item = QGraphicsRectItem(final_rect)
                item.setPen(QPen(Qt.PenStyle.NoPen))
                item.setBrush(brush)
                item.setZValue(20)
                self.scene.addItem(item)


class DefLoadWorker(QThread):
    def_loaded = pyqtSignal(object)

    def __init__(self, def_path, ide=None, parent=None):
        super().__init__(parent)
        self.def_path = def_path
        self.ide = ide

    def run(self):
        try:
            # First attempt high-fidelity OpenDB direct extraction
            try:
                from sdk.opendb_bridge import OpenDBBridge
            except ImportError:
                from silis.core.sdk.opendb_bridge import OpenDBBridge
            raw_odb = OpenDBBridge.extract_layout_geometry(self.def_path)
            if raw_odb and raw_odb.get("die"):
                # Wrap OpenDB extraction into DEFParser-compatible interface
                class OpenDBDefData:
                    def __init__(self, data, path):
                        self.path = path
                        self.dbu = data.get("dbu", 1000.0)
                        die = data.get("die", [0, 0, 0, 0])
                        self.die_rect = QRectF(die[0], die[1], die[2] - die[0], die[3] - die[1])
                        core = data.get("core", die)
                        self.core_rect = QRectF(core[0], core[1], core[2] - core[0], core[3] - core[1]) if core else self.die_rect
                        std = data.get("std_cells", {})
                        self.std_x = std.get("x", [])
                        self.std_y = std.get("y", [])
                        self.std_w = std.get("w", [])
                        self.std_h = std.get("h", [])
                        self.std_names = std.get("names", [])
                        self.is_filler = std.get("is_filler", [])
                        
                        mac = data.get("macros", {})
                        self.mac_x = mac.get("x", [])
                        self.mac_y = mac.get("y", [])
                        self.mac_w = mac.get("w", [])
                        self.mac_h = mac.get("h", [])
                        self.mac_names = mac.get("names", [])
                        
                        pin = data.get("pins", {})
                        self.pin_x = pin.get("x", [])
                        self.pin_y = pin.get("y", [])
                        self.pin_w = pin.get("w", [])
                        self.pin_h = pin.get("h", [])
                        self.pin_names = pin.get("names", [])
                        
                        pwr = data.get("power", {})
                        self.pwr_x = pwr.get("x", [])
                        self.pwr_y = pwr.get("y", [])
                        self.pwr_w = pwr.get("w", [])
                        self.pwr_h = pwr.get("h", [])
                        
                        self.comps_map = {}
                        self.comp_masters = {}
                        self.comp_types = {}
                        for i in range(len(self.mac_names)):
                            mname = self.mac_names[i]
                            self.comps_map[mname] = QRectF(self.mac_x[i], self.mac_y[i], self.mac_w[i], self.mac_h[i])
                            self.comp_types[mname] = "MACRO"

                        # Index std cells for instant inspector lookup and search
                        if self.std_names:
                            for i in range(len(self.std_names)):
                                sname = self.std_names[i]
                                self.comps_map[sname] = QRectF(self.std_x[i], self.std_y[i], self.std_w[i], self.std_h[i])
                                self.comp_types[sname] = "STD"
                        
                        self.pins = []
                        for i in range(len(self.pin_names)):
                            pname = self.pin_names[i]
                            self.pins.append((QRectF(self.pin_x[i], self.pin_y[i], self.pin_w[i], self.pin_h[i]), pname))
                            
                        self.is_opendb = True
                        reg = data.get("regions", {})
                        self.regions = []
                        rx = reg.get("x", [])
                        ry = reg.get("y", [])
                        rw = reg.get("w", [])
                        rh = reg.get("h", [])
                        rnames = reg.get("names", [])
                        for i in range(len(rx)):
                            self.regions.append((QRectF(rx[i], ry[i], rw[i], rh[i]), rnames[i] if i < len(rnames) else "Region"))

                        blk = data.get("blockages", {})
                        self.blockages = []
                        bx = blk.get("x", [])
                        by = blk.get("y", [])
                        bw = blk.get("w", [])
                        bh = blk.get("h", [])
                        for i in range(len(bx)):
                            self.blockages.append(QRectF(bx[i], by[i], bw[i], bh[i]))

                        self.power_routes = []
                        self.signal_routes = []

                parsed = OpenDBDefData(raw_odb, self.def_path)
                self.def_loaded.emit(parsed)
                return
        except Exception:
            pass

        try:
            parsed = DEFParser(self.def_path, self.ide)
            self.def_loaded.emit(parsed)
        except Exception as e:
            self.def_loaded.emit(None)


class FastSiliconPeeker(QWidget):
    def __init__(self, ide=None, parent=None):
        super().__init__(parent)
        self.ide = ide
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.def_data = None
        self.current_def_path = None
        self.last_mtime = 0
        self.first_load = True
        
        self.show_insts = True
        self.show_macros = True
        self.show_tapcells = True
        self.show_pins = True
        self.show_nets = True
        self.show_power = True

        if fast_layout_viewer:
            self.core = fast_layout_viewer.FastLayoutViewerCore()
            std_lod = USER_SETTINGS.get("lod_std_cells", 0.002) if USER_SETTINGS.get("lod_enabled", False) else 0.0
            net_lod = USER_SETTINGS.get("lod_nets", 0.005) if USER_SETTINGS.get("lod_enabled", False) else 0.0
            self.core.set_lod(std_lod, net_lod)
            ptr = self.core.get_ptr()
            self.native_widget = sip.wrapinstance(ptr, QWidget)
            self.layout.addWidget(self.native_widget)
        else:
            self.layout.addWidget(QLabel("FastLayoutViewer C++ extension not found!"))
            self.core = None

        # --- Tiny Floating Search Overlay (Leaves 100% Canvas Space Free) ---
        self.search_overlay = QWidget(self)
        self.search_overlay.setStyleSheet("background: transparent;")
        so_layout = QHBoxLayout(self.search_overlay)
        so_layout.setContentsMargins(0, 0, 0, 0)
        so_layout.setSpacing(4)

        self.btn_search_toggle = QPushButton("🔍", self.search_overlay)
        self.btn_search_toggle.setFixedSize(26, 26)
        self.btn_search_toggle.setToolTip("Search instance / macro (Ctrl+F)")
        self.btn_search_toggle.setStyleSheet("""
            QPushButton {
                background: rgba(30, 30, 30, 0.85);
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(50, 50, 50, 0.95);
                border: 1px solid #777;
            }
        """)
        self.btn_search_toggle.clicked.connect(self.toggle_search_input)

        self.search_input_container = QWidget(self.search_overlay)
        sic_layout = QHBoxLayout(self.search_input_container)
        sic_layout.setContentsMargins(4, 2, 4, 2)
        sic_layout.setSpacing(4)
        self.search_input_container.setStyleSheet("""
            QWidget {
                background: rgba(24, 24, 24, 0.92);
                border: 1px solid #4a5568;
                border-radius: 4px;
            }
        """)

        self.search_input = QLineEdit(self.search_input_container)
        self.search_input.setPlaceholderText("Find instance...")
        self.search_input.setFixedWidth(160)
        self.search_input.setFixedHeight(22)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: #f7fafc;
                border: none;
                font-family: monospace;
                font-size: 11px;
            }
        """)

        self.completer = QCompleter([])
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer.setMaxVisibleItems(15)
        self.search_input.setCompleter(self.completer)
        self.search_input.returnPressed.connect(self.on_search_instance)
        self.completer.activated.connect(self.on_search_instance)

        self.btn_clear_search = QPushButton("✕", self.search_input_container)
        self.btn_clear_search.setFixedSize(16, 16)
        self.btn_clear_search.setToolTip("Close Search")
        self.btn_clear_search.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #a0aec0;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #fc8181;
            }
        """)
        self.btn_clear_search.clicked.connect(self.clear_and_collapse_search)

        sic_layout.addWidget(self.search_input)
        sic_layout.addWidget(self.btn_clear_search)
        self.search_input_container.setVisible(False)

        so_layout.addWidget(self.btn_search_toggle)
        so_layout.addWidget(self.search_input_container)
        self.reposition_search_overlay()

        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self.check_refresh)
        # Note: Do not start timer unconditionally to prevent background polling.
        # Timer starts in showEvent and stops in hideEvent.

    def toggle_ruler(self):
        if not self.core:
            return False
        curr = self.core.is_ruler_active() if hasattr(self.core, 'is_ruler_active') else False
        new_state = not curr
        if hasattr(self.core, 'set_ruler_active'):
            self.core.set_ruler_active(new_state)
        return new_state

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'auto_refresh_timer') and not self.auto_refresh_timer.isActive():
            self.check_refresh()
            self.auto_refresh_timer.start(2000)

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, 'auto_refresh_timer') and self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_search_overlay()

    def reposition_search_overlay(self):
        if hasattr(self, 'search_overlay'):
            self.search_overlay.adjustSize()
            w = self.search_overlay.width()
            self.search_overlay.move(max(10, self.width() - w - 14), 10)
            self.search_overlay.raise_()

    def toggle_search_input(self):
        is_vis = self.search_input_container.isVisible()
        self.search_input_container.setVisible(not is_vis)
        self.reposition_search_overlay()
        if not is_vis:
            self.search_input.setFocus()
            self.search_input.selectAll()

    def clear_and_collapse_search(self):
        self.clear_search()
        self.search_input_container.setVisible(False)
        self.reposition_search_overlay()

    def on_search_instance(self, text=None):
        if not text or not isinstance(text, str):
            text = self.search_input.text().strip()
        if not text or not self.def_data or not self.core:
            return
            
        matched = None
        if text in self.def_data.comps_map:
            matched = text
        else:
            for k in self.def_data.comps_map.keys():
                if text.lower() in k.lower():
                    matched = k
                    break
                    
        if matched:
            rect = self.def_data.comps_map[matched]
            cx = rect.center().x()
            cy = rect.center().y()
            w = rect.width()
            h = rect.height()
            
            target_zoom = min(25.0, max(0.8, (self.width() * 0.35) / max(w, 8.0 * self.def_data.dbu)))
            self.core.pan_to(cx, cy, target_zoom)
            self.core.highlight_box(rect.x(), rect.y(), w, h, matched)
        else:
            if hasattr(self, 'search_input'):
                self.search_input.setPlaceholderText("Not found...")

    def clear_search(self):
        self.search_input.clear()
        if self.core:
            self.core.clear_highlight()

    def check_refresh(self):
        if self.current_def_path and os.path.exists(self.current_def_path):
            mtime = os.path.getmtime(self.current_def_path)
            size = os.path.getsize(self.current_def_path)
            if mtime > self.last_mtime and size > 0:
                if getattr(self, '_last_size', -1) != size:
                    self._last_size = size
                    return
                self.load_def_file(self.current_def_path)

    def load_def_file(self, path):
        self.current_def_path = path
        if not os.path.exists(path):
            return
        mtime = os.path.getmtime(path)
        size = os.path.getsize(path)
        # Fast exit if file hasn't changed at all (instant world/tab switch)
        if self.def_data is not None and getattr(self, 'last_mtime', 0) == mtime and getattr(self, '_last_size', 0) == size:
            return

        if hasattr(self, '_load_worker') and self._load_worker and self._load_worker.isRunning():
            return

        self.last_mtime = mtime
        self._last_size = size

        # Show non-blocking spinner in status bar if IDE available
        if self.ide and hasattr(self.ide, 'statusBar'):
            self.ide.statusBar().showMessage("Loading DEF layout in background...")

        self._load_worker = DefLoadWorker(path, getattr(self, 'ide', None), self)
        self._load_worker.def_loaded.connect(self._on_def_loaded)
        self._load_worker.start()

    def _on_def_loaded(self, parsed_def):
        if parsed_def:
            self.def_data = parsed_def
            self.redraw()
        if self.ide and hasattr(self.ide, 'statusBar'):
            self.ide.statusBar().showMessage("DEF Layout Ready", 3000)

    def set_die_area(self, x1, y1, x2, y2):
        if self.core:
            self.core.set_core(x1, y1, x2 - x1, y2 - y1)
            
    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_0: self.set_heatmap(0)
        elif k == Qt.Key.Key_1: self.set_heatmap(1)
        elif k == Qt.Key.Key_2: self.set_heatmap(2)
        elif k == Qt.Key.Key_3: self.set_heatmap(3)
        elif k == Qt.Key.Key_4: self.set_heatmap(4)
        else: super().keyPressEvent(event)
        
    def set_heatmap_mode(self, mode_name):
        """
        Activates high-resolution EDA heatmaps (160x160 resolution).
        Supported mode_name:
            - 'rudy': Relative Uniform Density of Wires (RUDY global congestion)
            - 'route_congestion': Detailed routing segment density
            - 'placement_density': Standard cell area occupancy
            - 'pin_density': Pin count distribution across core
            - 'ir_drop': Static IR drop voltage gradients across power mesh
            - 'power_density': Dynamic/static power switching dissipation
            - None / 'clear' / '0': Turn off heatmap
        """
        if not mode_name or mode_name in ["clear", "0", "disabled", "none"]:
            self.set_heatmap(0)
            return

        mode_map = {
            "rudy": 1,
            "route_congestion": 2,
            "placement_density": 3,
            "pin_density": 4,
            "ir_drop": 5,
            "power_density": 6
        }
        mode_idx = mode_map.get(str(mode_name).lower(), 1)
        self.set_heatmap(mode_idx)

    def get_core_or_active_rect(self):
        """
        Calculates the active placement / standard cell core region.
        In floorplans where I/O pads or wide margins surround the chip,
        this bounds standard cells, macros, and routes to avoid diluting
        heatmap resolution across empty peripheral margins.
        """
        if not self.def_data:
            return QRectF()

        # If OpenDB or DEF provides an explicit non-empty core rectangle, use it directly
        cr = getattr(self.def_data, "core_rect", None)
        if cr and cr.width() > 0 and cr.height() > 0:
            return cr

        comps = getattr(self.def_data, "comps_map", {})
        if not comps and getattr(self.def_data, "std_x", None):
            # Fallback for raw coordinate arrays from OpenDB
            xs = list(self.def_data.std_x)
            ys = list(self.def_data.std_y)
            rights = [self.def_data.std_x[i] + self.def_data.std_w[i] for i in range(len(self.def_data.std_x))]
            bottoms = [self.def_data.std_y[i] + self.def_data.std_h[i] for i in range(len(self.def_data.std_y))]
        elif comps:
            xs = [r.x() for r in comps.values()]
            ys = [r.y() for r in comps.values()]
            rights = [r.x() + r.width() for r in comps.values()]
            bottoms = [r.y() + r.height() for r in comps.values()]
        else:
            xs, ys, rights, bottoms = [], [], [], []

        if xs:

            # Also incorporate signal routing bounding boxes
            for pts in getattr(self.def_data, "signal_routes", []):
                for p in pts:
                    xs.append(p.x())
                    rights.append(p.x())
                    ys.append(p.y())
                    bottoms.append(p.y())

            min_x = min(xs)
            max_x = max(rights)
            min_y = min(ys)
            max_y = max(bottoms)

            # Add a small 2-cell buffer (approx 20um) around the active area
            pad = 20.0 * getattr(self.def_data, "dbu", 1000.0)
            active_rect = QRectF(min_x - pad, min_y - pad, (max_x - min_x) + 2 * pad, (max_y - min_y) + 2 * pad)
            
            # Constrain within die_rect if die_rect is valid
            dr = getattr(self.def_data, "die_rect", None)
            if dr and dr.width() > 0 and dr.height() > 0:
                active_rect = active_rect.intersected(dr)
            
            if active_rect.width() > 0 and active_rect.height() > 0:
                return active_rect

        # Fallback to die_rect if no components or empty
        return getattr(self.def_data, "die_rect", QRectF())

    def set_heatmap(self, mode):
        if not self.core:
            return
        if mode == 0:
            self.core.set_heatmap(0, [], 0, 0)
            return

        if not self.def_data or not self.def_data.die_rect:
            return

        # Calculate active placement / core bounding box instead of bloating over I/O pads
        active_rect = self.get_core_or_active_rect()
        dr = active_rect if (active_rect.width() > 0 and active_rect.height() > 0) else self.def_data.die_rect
        if dr.width() <= 0 or dr.height() <= 0:
            return

        # Set bounds in native viewer for coordinate mapping and hover inspection
        if hasattr(self.core, "set_heatmap_bounds"):
            self.core.set_heatmap_bounds(dr.x(), dr.y(), dr.width(), dr.height())

        gw = 160
        gh = 160
        grid_size = gw * gh
        data = [0.0] * grid_size

        dw = float(dr.width())
        dh = float(dr.height())
        dx0 = float(dr.x())
        dy0 = float(dr.y())
        tile_w = dw / gw
        tile_h = dh / gh
        tile_area = max(1.0, tile_w * tile_h)

        if mode == 1:
            # RUDY Wire Congestion (OpenROAD standard model)
            # Accumulates true HPWL wire area / bounding box area without premature saturation
            wire_width = 0.14 * getattr(self.def_data, "dbu", 1000.0) # nominal M1/M2 wire width
            for pts in getattr(self.def_data, "signal_routes", []):
                if not pts or len(pts) < 2:
                    continue
                xs = [p.x() for p in pts]
                ys = [p.y() for p in pts]
                min_x = min(xs); max_x = max(xs)
                min_y = min(ys); max_y = max(ys)
                
                net_dx = max(1.0, max_x - min_x)
                net_dy = max(1.0, max_y - min_y)
                net_area = net_dx * net_dy
                hpwl = net_dx + net_dy
                wire_area = hpwl * wire_width
                net_congestion = wire_area / net_area

                gx0 = max(0, min(gw - 1, int((min_x - dx0) / tile_w)))
                gx1 = max(0, min(gw - 1, int((max_x - dx0) / tile_w)))
                gy0 = max(0, min(gh - 1, int((min_y - dy0) / tile_h)))
                gy1 = max(0, min(gh - 1, int((max_y - dy0) / tile_h)))

                for gy in range(gy0, gy1 + 1):
                    ty0 = dy0 + gy * tile_h
                    ty1 = ty0 + tile_h
                    iy0 = max(min_y, ty0); iy1 = min(max_y, ty1)
                    if iy1 <= iy0: continue

                    row_offset = gy * gw
                    for gx in range(gx0, gx1 + 1):
                        tx0 = dx0 + gx * tile_w
                        tx1 = tx0 + tile_w
                        ix0 = max(min_x, tx0); ix1 = min(max_x, tx1)
                        if ix1 <= ix0: continue

                        intersect_area = (ix1 - ix0) * (iy1 - iy0)
                        rudy_val = net_congestion * (intersect_area / tile_area)
                        data[row_offset + gx] += rudy_val

        elif mode == 2:
            # Routing Congestion: Raw routed segment length density per bin
            for pts in getattr(self.def_data, "signal_routes", []):
                for p in pts:
                    cx = int((p.x() - dx0) / tile_w)
                    cy = int((p.y() - dy0) / tile_h)
                    if 0 <= cx < gw and 0 <= cy < gh:
                        data[cy * gw + cx] += 1.0

        elif mode == 3:
            # Placement Density (OpenROAD standard model)
            # Fast vectorized accumulation for OpenDB extraction and DEF parser
            std_x = getattr(self.def_data, "std_x", None)
            std_y = getattr(self.def_data, "std_y", None)
            std_w = getattr(self.def_data, "std_w", None)
            std_h = getattr(self.def_data, "std_h", None)

            if std_x is not None and len(std_x) > 0:
                import numpy as np
                sx = np.array(std_x, dtype=np.float32)
                sy = np.array(std_y, dtype=np.float32)
                sw = np.array(std_w, dtype=np.float32)
                sh = np.array(std_h, dtype=np.float32)

                # Filter out filler/tap cells if flagged by OpenDB
                is_fill = getattr(self.def_data, "is_filler", None)
                if is_fill is not None and len(is_fill) == len(sx):
                    mask = ~np.array(is_fill, dtype=bool)
                    sx = sx[mask]; sy = sy[mask]; sw = sw[mask]; sh = sh[mask]

                # Center point binning with true cell area weighting
                cx = np.clip(((sx + sw * 0.5 - dx0) / tile_w).astype(np.int32), 0, gw - 1)
                cy = np.clip(((sy + sh * 0.5 - dy0) / tile_h).astype(np.int32), 0, gh - 1)
                cell_density = (sw * sh) / tile_area

                grid, _, _ = np.histogram2d(cy, cx, bins=[gh, gw], range=[[0, gh], [0, gw]], weights=cell_density)

                # Include macro items in density calculation
                mac_x = getattr(self.def_data, "mac_x", [])
                mac_y = getattr(self.def_data, "mac_y", [])
                mac_w = getattr(self.def_data, "mac_w", [])
                mac_h = getattr(self.def_data, "mac_h", [])
                for i in range(len(mac_x)):
                    rx0 = mac_x[i]; rx1 = rx0 + mac_w[i]
                    ry0 = mac_y[i]; ry1 = ry0 + mac_h[i]
                    gx0 = max(0, min(gw - 1, int((rx0 - dx0) / tile_w)))
                    gx1 = max(0, min(gw - 1, int((rx1 - dx0) / tile_w)))
                    gy0 = max(0, min(gh - 1, int((ry0 - dy0) / tile_h)))
                    gy1 = max(0, min(gh - 1, int((ry1 - dy0) / tile_h)))
                    for gy in range(gy0, gy1 + 1):
                        ty0 = dy0 + gy * tile_h; ty1 = ty0 + tile_h
                        iy0 = max(ry0, ty0); iy1 = min(ry1, ty1)
                        if iy1 <= iy0: continue
                        for gx in range(gx0, gx1 + 1):
                            tx0 = dx0 + gx * tile_w; tx1 = tx0 + tile_w
                            ix0 = max(rx0, tx0); ix1 = min(rx1, tx1)
                            if ix1 <= ix0: continue
                            grid[gy, gx] += ((ix1 - ix0) * (iy1 - iy0)) / tile_area

                data = grid.flatten().tolist()
            else:
                for name, rect in getattr(self.def_data, "comps_map", {}).items():
                    # Exclude filler and tapcells from placement heatmap if known
                    m_name = getattr(self.def_data, "comp_masters", {}).get(name, "")
                    if "fill" in m_name.lower() or "tap" in m_name.lower():
                        continue

                    rx0 = rect.x(); rx1 = rx0 + rect.width()
                    ry0 = rect.y(); ry1 = ry0 + rect.height()

                    gx0 = max(0, min(gw - 1, int((rx0 - dx0) / tile_w)))
                    gx1 = max(0, min(gw - 1, int((rx1 - dx0) / tile_w)))
                    gy0 = max(0, min(gh - 1, int((ry0 - dy0) / tile_h)))
                    gy1 = max(0, min(gh - 1, int((ry1 - dy0) / tile_h)))

                    for gy in range(gy0, gy1 + 1):
                        ty0 = dy0 + gy * tile_h
                        ty1 = ty0 + tile_h
                        iy0 = max(ry0, ty0); iy1 = min(ry1, ty1)
                        if iy1 <= iy0: continue

                        row_offset = gy * gw
                        for gx in range(gx0, gx1 + 1):
                            tx0 = dx0 + gx * tile_w
                            tx1 = tx0 + tile_w
                            ix0 = max(rx0, tx0); ix1 = min(rx1, tx1)
                            if ix1 <= ix0: continue

                            inter_area = (ix1 - ix0) * (iy1 - iy0)
                            data[row_offset + gx] += (inter_area / tile_area)

        elif mode == 4:
            # Pin Density (OpenROAD PinDensityDataSource model)
            # Accumulate true raw pin counts per tile bin
            for pin in getattr(self.def_data, "pins", []):
                rect = pin[0] if isinstance(pin, (tuple, list)) else pin
                center = rect.center() if hasattr(rect, "center") else None
                if center:
                    cx = int((center.x() - dx0) / tile_w)
                    cy = int((center.y() - dy0) / tile_h)
                    if 0 <= cx < gw and 0 <= cy < gh:
                        data[cy * gw + cx] += 1.0

        elif mode == 5:
            # Static IR Drop (::psm): True OpenROAD PSM report ingestion or high-fidelity PDN mesh model
            psm_loaded = False
            search_dirs = []
            if getattr(self, 'current_def_path', None):
                search_dirs.append(os.path.dirname(os.path.abspath(self.current_def_path)))
            if hasattr(self, 'ide') and self.ide:
                if hasattr(self.ide, 'cwd') and self.ide.cwd:
                    search_dirs.append(os.path.abspath(self.ide.cwd))
                if hasattr(self.ide, 'get_proj_root'):
                    try:
                        ctx = self.ide.get_context() if hasattr(self.ide, 'get_context') else ("design", "design")
                        search_dirs.append(os.path.abspath(self.ide.get_proj_root(ctx[0] or "design")))
                    except Exception:
                        pass

            # Check potential voltage report candidates
            rpt_candidates = []
            for d in search_dirs:
                if not os.path.exists(d): continue
                rpt_candidates.extend([
                    os.path.join(d, "vdd_voltage.rpt"),
                    os.path.join(d, "results", "vdd_voltage.rpt"),
                    os.path.join(d, "reports", "vdd_voltage.rpt"),
                    os.path.join(d, "reports", "power", "vdd_voltage.rpt"),
                ])
                # Also glob any *voltage*.rpt or *irdrop*.rpt
                try:
                    for root, _, files in os.walk(d):
                        for f in files:
                            fl = f.lower()
                            if fl.endswith(".rpt") and ("voltage" in fl or "irdrop" in fl):
                                rpt_candidates.append(os.path.join(root, f))
                        if len(rpt_candidates) > 20: break
                except Exception:
                    pass

            for rpt_path in rpt_candidates:
                if os.path.exists(rpt_path) and os.path.isfile(rpt_path):
                    try:
                        # PSM CSV format: Instance,Terminal,Layer,X location,Y location,Voltage
                        v_coords = []
                        max_v = -1e9
                        with open(rpt_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                line = line.strip()
                                if not line or line.startswith("Instance") or line.startswith("#"):
                                    continue
                                parts = [p.strip() for p in line.split(",")]
                                if len(parts) >= 6:
                                    try:
                                        # OpenROAD outputs X and Y in microns, convert to DBU if necessary
                                        x_val = float(parts[3])
                                        y_val = float(parts[4])
                                        volt = float(parts[5])
                                        v_coords.append((x_val, y_val, volt))
                                        if volt > max_v: max_v = volt
                                    except ValueError:
                                        continue

                        if v_coords and max_v > 0.0:
                            # Detect units: if coordinates match DBU directly or microns
                            # Compare coordinate range to die_rect
                            is_microns = (max(c[0] for c in v_coords[:100]) < (dx1 / 10.0))
                            unit_scale = 1000.0 if is_microns else 1.0

                            for vx, vy, volt in v_coords:
                                px = vx * unit_scale
                                py = vy * unit_scale
                                gx = int((px - dx0) / tile_w)
                                gy = int((py - dy0) / tile_h)
                                if 0 <= gx < gw and 0 <= gy < gh:
                                    v_drop = max(0.0, max_v - volt)
                                    idx = gy * gw + gx
                                    if v_drop > data[idx]:
                                        data[idx] = v_drop
                            psm_loaded = True
                            break
                    except Exception:
                        pass

            if not psm_loaded:
                # OpenROAD PSM-aligned 2D Conductance Poisson Solver:
                # Solves \nabla \cdot (G \nabla V) = I on the 2D PDN grid.
                # VDD sources (pads/rings) are Dirichlet boundary conditions (V_drop = 0.0V).
                # Current sinks I[gy, gx] draw current based on cell types/activities.
                import numpy as np

                I_grid = np.zeros((gh, gw), dtype=np.float32)
                comps = getattr(self.def_data, "comps_map", {})
                masters = getattr(self.def_data, "comp_masters", {})
                for name, rect in comps.items():
                    cx = int((rect.x() - dx0) / tile_w)
                    cy = int((rect.y() - dy0) / tile_h)
                    if 0 <= cx < gw and 0 <= cy < gh:
                        m_name = masters.get(name, "").lower()
                        is_macro = getattr(rect, "is_macro", False) or ("fakeram" in m_name or "sram" in m_name)
                        if is_macro:
                            weight = 20.0
                        elif "clk" in m_name or "buf" in m_name or "inv" in m_name:
                            weight = 5.0
                        elif "df" in m_name or "ff" in m_name:
                            weight = 2.5
                        elif "tap" in m_name or "fill" in m_name or "decap" in m_name:
                            weight = 0.02
                        else:
                            weight = 1.0
                        I_grid[cy, cx] += weight

                # Conductance map: M1 standard cell rails run horizontally, vertical straps run on M4
                Gx = np.full((gh, gw), 1.0, dtype=np.float32)
                Gy = np.full((gh, gw), 0.35, dtype=np.float32)

                pwr_routes = getattr(self.def_data, "power_routes", [])
                for seg in pwr_routes:
                    points = seg[1] if (isinstance(seg, (tuple, list)) and len(seg) == 2 and isinstance(seg[1], list)) else seg
                    if isinstance(points, (tuple, list)) and len(points) >= 2:
                        p1, p2 = points[0], points[1]
                        x1 = p1.x() if hasattr(p1, 'x') else (p1[0] if isinstance(p1, (tuple, list)) else 0)
                        y1 = p1.y() if hasattr(p1, 'y') else (p1[1] if isinstance(p1, (tuple, list)) else 0)
                        x2 = p2.x() if hasattr(p2, 'x') else (p2[0] if isinstance(p2, (tuple, list)) else 0)
                        y2 = p2.y() if hasattr(p2, 'y') else (p2[1] if isinstance(p2, (tuple, list)) else 0)
                        if abs(x1 - x2) < 50:
                            col = int((x1 - dx0) / tile_w)
                            if 0 <= col < gw:
                                Gy[:, max(0, col - 1):min(gw, col + 2)] += 4.0
                        elif abs(y1 - y2) < 50:
                            row = int((y1 - dy0) / tile_h)
                            if 0 <= row < gh:
                                Gx[max(0, row - 1):min(gh, row + 2), :] += 4.0

                # Identify VDD voltage sources (power pads / core power pins / boundary ring)
                is_source = np.zeros((gh, gw), dtype=bool)
                vdd_pads = [
                    name for name in comps
                    if any(k in name.lower() or k in masters.get(name, '').lower() for k in ['pad_vdd', 'vccd', 'vdd_core', 'p_core'])
                ]
                if vdd_pads:
                    for name in vdd_pads:
                        rect = comps[name]
                        cx = int((rect.x() - dx0) / tile_w)
                        cy = int((rect.y() - dy0) / tile_h)
                        for ddy in range(-2, 3):
                            for ddx in range(-2, 3):
                                if 0 <= cx + ddx < gw and 0 <= cy + ddy < gh:
                                    is_source[cy + ddy, cx + ddx] = True
                else:
                    # Power ring around die periphery
                    is_source[0, :] = True
                    is_source[-1, :] = True
                    is_source[:, 0] = True
                    is_source[:, -1] = True

                # Vectorized Red-Black SOR Poisson Solver (50 iterations)
                V = np.zeros((gh, gw), dtype=np.float32)
                y_idx, x_idx = np.indices((gh, gw))
                red = ((y_idx + x_idx) % 2 == 0) & (~is_source)
                black = ((y_idx + x_idx) % 2 == 1) & (~is_source)

                denom = np.roll(Gx, 1, axis=1) + Gx + np.roll(Gy, 1, axis=0) + Gy
                denom[denom == 0] = 1.0

                omega = 1.65
                for _ in range(50):
                    # Red update
                    v_nbr = (np.roll(V, 1, axis=1) * np.roll(Gx, 1, axis=1) +
                             np.roll(V, -1, axis=1) * Gx +
                             np.roll(V, 1, axis=0) * np.roll(Gy, 1, axis=0) +
                             np.roll(V, -1, axis=0) * Gy)
                    V_new = (v_nbr + I_grid) / denom
                    V[red] = (1.0 - omega) * V[red] + omega * V_new[red]

                    # Black update
                    v_nbr = (np.roll(V, 1, axis=1) * np.roll(Gx, 1, axis=1) +
                             np.roll(V, -1, axis=1) * Gx +
                             np.roll(V, 1, axis=0) * np.roll(Gy, 1, axis=0) +
                             np.roll(V, -1, axis=0) * Gy)
                    V_new = (v_nbr + I_grid) / denom
                    V[black] = (1.0 - omega) * V[black] + omega * V_new[black]

                    V[is_source] = 0.0

                # Flatten solution array for fast viewer
                data = V.flatten().tolist()

        elif mode == 6:
            # Power Density: Dynamic activity estimation based on cell concentration + clock buffers
            for name, rect in getattr(self.def_data, "comps_map", {}).items():
                cx = int((rect.x() - dx0) / tile_w)
                cy = int((rect.y() - dy0) / tile_h)
                if 0 <= cx < gw and 0 <= cy < gh:
                    pwr_weight = 1.0
                    m_name = getattr(self.def_data, "comp_masters", {}).get(name, "")
                    if "clk" in m_name.lower() or "buf" in m_name.lower() or "inv" in m_name.lower():
                        pwr_weight = 4.0
                    data[cy * gw + cx] += pwr_weight

        # Pass 2: OpenROAD correctMapScale normalization
        # Note: Mode 3 (Placement Density) is an absolute physical ratio (Area(Cells) / Area(Tile)).
        # It must NOT be scaled by 1/max_val, as that would distort true utilization (e.g. 45% showing as 100% hot-spot).
        if mode == 3:
            # Physical placement density: clean saturation clamp at 1.0 (or >1.0 to highlight DRC overlaps)
            data = [min(1.0, max(0.0, v)) for v in data]
        else:
            # Unbounded models (RUDY wire counts, Pin counts, Activity weights) normalize against peak
            max_val = max(data) if data else 0.0
            if max_val > 0.0:
                scale = 1.0 / max_val
                data = [v * scale for v in data]

        self.core.set_heatmap(mode, data, gw, gh)

    def redraw(self):
        if not self.core or not self.def_data: return
        self.core.clear()
        
        d = self.def_data.die_rect
        self.core.set_core(d.x(), d.y(), d.width(), d.height())
        
        mac_x, mac_y, mac_w, mac_h, mac_names = [], [], [], [], []
        pin_x, pin_y, pin_w, pin_h, pin_names = [], [], [], [], []
        pwr_x, pwr_y, pwr_w, pwr_h = [], [], [], []
        reg_x, reg_y, reg_w, reg_h, reg_names = [], [], [], [], []
        vi_x, vi_y, vi_w, vi_h, vi_volts, vi_names = [], [], [], [], [], []
        blk_x, blk_y, blk_w, blk_h = [], [], [], []
        tap_x, tap_y, tap_w, tap_h = [], [], [], []
        std_x, std_y, std_w, std_h = [], [], [], []

        has_fast_flat = hasattr(self.def_data, "std_coords_flat") and self.def_data.std_coords_flat is not None and hasattr(self.core, "load_cells_flat")
        # Fast path: OpenDB native extraction
        if getattr(self.def_data, "is_opendb", False):
            if self.show_insts and getattr(self.def_data, "std_x", None):
                self.core.load_std_cells(self.def_data.std_x, self.def_data.std_y, self.def_data.std_w, self.def_data.std_h)
            if self.show_macros and getattr(self.def_data, "mac_x", None):
                mac_x = self.def_data.mac_x
                mac_y = self.def_data.mac_y
                mac_w = self.def_data.mac_w
                mac_h = self.def_data.mac_h
                mac_names = self.def_data.mac_names
            if self.show_pins and getattr(self.def_data, "pin_x", None):
                pin_x = self.def_data.pin_x
                pin_y = self.def_data.pin_y
                pin_w = self.def_data.pin_w
                pin_h = self.def_data.pin_h
                pin_names = self.def_data.pin_names
            if self.show_power and getattr(self.def_data, "pwr_x", None):
                pwr_x = self.def_data.pwr_x
                pwr_y = self.def_data.pwr_y
                pwr_w = self.def_data.pwr_w
                pwr_h = self.def_data.pwr_h
        # Fast path: use pre-accumulated flat coordinates when available
        elif has_fast_flat:
            if self.show_insts and self.def_data.std_coords_flat:
                import numpy as np
                flat_arr = np.array(self.def_data.std_coords_flat, dtype=np.float32)
                self.core.load_cells_flat(flat_arr)
            
            if self.show_tapcells and self.def_data.tap_coords and hasattr(self.core, "load_cells_flat"):
                import numpy as np
                flat_tap = np.array(self.def_data.tap_coords, dtype=np.float32)
                # Tap cells can be ingested via flat buffer or tap loader
                tap_x = self.def_data.tap_coords[0::4]
                tap_y = self.def_data.tap_coords[1::4]
                tap_w = self.def_data.tap_coords[2::4]
                tap_h = self.def_data.tap_coords[3::4]
                if hasattr(self.core, 'load_tap_cells'):
                    self.core.load_tap_cells(tap_x, tap_y, tap_w, tap_h)

            if self.show_macros and hasattr(self.def_data, "macro_items"):
                for mx, my, mw, mh, mn in self.def_data.macro_items:
                    mac_x.append(mx); mac_y.append(my); mac_w.append(mw); mac_h.append(mh); mac_names.append(mn)
        else:
            std_x, std_y, std_w, std_h = [], [], [], []
            for name, rect in self.def_data.comps_map.items():
                ctype = self.def_data.comp_types.get(name, "STD")
                is_macro = (ctype == "MACRO") or (rect.width() / self.def_data.dbu > 20) or (rect.height() / self.def_data.dbu > 20)
                is_tap = (ctype == "TAP")
                
                if is_macro:
                    if self.show_macros:
                        mac_x.append(rect.x()); mac_y.append(rect.y()); mac_w.append(rect.width()); mac_h.append(rect.height())
                        mac_names.append(name)
                elif is_tap:
                    if self.show_tapcells:
                        tap_x.append(rect.x()); tap_y.append(rect.y()); tap_w.append(rect.width()); tap_h.append(rect.height())
                else:
                    if self.show_insts:
                        std_x.append(rect.x()); std_y.append(rect.y()); std_w.append(rect.width()); std_h.append(rect.height())
            if std_x: self.core.load_std_cells(std_x, std_y, std_w, std_h)
                
        if self.show_pins and hasattr(self.def_data, 'pins'):
            for rect, name in self.def_data.pins:
                pin_x.append(rect.x()); pin_y.append(rect.y()); pin_w.append(rect.width()); pin_h.append(rect.height())
                pin_names.append(name)
                
        if hasattr(self.def_data, 'regions'):
            for rect, name in self.def_data.regions:
                reg_x.append(rect.x()); reg_y.append(rect.y()); reg_w.append(rect.width()); reg_h.append(rect.height())
                reg_names.append(name)

        # Ingest Voltage Islands from UPF intent or DEF regions
        proj_root = getattr(self.parent_ide, "cwd", None) if hasattr(self, "parent_ide") and self.parent_ide else None
        if not proj_root and self.current_def_path:
            cand = os.path.dirname(os.path.abspath(self.current_def_path))
            if os.path.basename(cand) == "results":
                cand = os.path.dirname(cand)
            proj_root = cand

        pds = []
        if proj_root:
            import glob
            upf_candidates = [
                os.path.join(proj_root, "power", "design.upf"),
                os.path.join(proj_root, "design.upf"),
            ]
            upf_candidates.extend(glob.glob(os.path.join(proj_root, "power", "*.upf")))
            upf_candidates.extend(glob.glob(os.path.join(proj_root, "*.upf")))
            for upf_f in upf_candidates:
                if os.path.isfile(upf_f) and os.path.getsize(upf_f) > 0:
                    try:
                        from backendflow.power.upf_engine import parse_upf
                        pds = parse_upf(upf_f)
                        if pds:
                            break
                    except Exception:
                        pass

        # If UPF domains found, map their area (either explicit or envelope of their module regions in DEF)
        if pds:
            dbu = getattr(self.def_data, 'dbu', 1000.0)
            # Build map of region bounds from DEF regions
            region_dict = {}
            if hasattr(self.def_data, 'regions'):
                for rect, rname in self.def_data.regions:
                    region_dict[rname] = rect

            for pd in pds:
                if pd.is_top:
                    continue
                if pd.area and len(pd.area) == 4:
                    ix1, iy1, ix2, iy2 = pd.area
                    vi_x.append(ix1 * dbu)
                    vi_y.append(iy1 * dbu)
                    vi_w.append((ix2 - ix1) * dbu)
                    vi_h.append((iy2 - iy1) * dbu)
                    vi_volts.append(pd.voltage)
                    vi_names.append(pd.name)
                elif pd.elements and region_dict:
                    # Compute union envelope of element regions
                    matched_rects = []
                    for elem in pd.elements:
                        for rname, rect in region_dict.items():
                            if elem in rname or rname in elem or (f"region_{elem}" == rname):
                                matched_rects.append(rect)
                    if matched_rects:
                        ux1 = min(r.left() for r in matched_rects)
                        uy1 = min(r.top() for r in matched_rects)
                        ux2 = max(r.right() for r in matched_rects)
                        uy2 = max(r.bottom() for r in matched_rects)
                        vi_x.append(ux1)
                        vi_y.append(uy1)
                        vi_w.append(ux2 - ux1)
                        vi_h.append(uy2 - uy1)
                        vi_volts.append(pd.voltage)
                        vi_names.append(pd.name)
                
        if hasattr(self.def_data, 'blockages'):
            for rect in self.def_data.blockages:
                blk_x.append(rect.x()); blk_y.append(rect.y()); blk_w.append(rect.width()); blk_h.append(rect.height())
                
        if self.show_power and hasattr(self.def_data, 'power_routes'):
            for width, points in self.def_data.power_routes:
                if width <= 0 or len(points) < 2:
                    continue
                for i in range(len(points)-1):
                    p1 = points[i]; p2 = points[i+1]
                    dx = abs(p2.x() - p1.x())
                    dy = abs(p2.y() - p1.y())
                    # Skip diagonal synthetic segments spanning across unrelated coordinates
                    if dx > 0 and dy > 0:
                        continue
                    px = min(p1.x(), p2.x()) - width/2
                    py = min(p1.y(), p2.y()) - width/2
                    pw = dx + width
                    ph = dy + width
                    pwr_x.append(px); pwr_y.append(py); pwr_w.append(pw); pwr_h.append(ph)
                    
        sig_x1, sig_y1, sig_x2, sig_y2 = [], [], [], []
        if self.show_nets and hasattr(self.def_data, 'signal_routes'):
            for points in self.def_data.signal_routes:
                for i in range(len(points)-1):
                    p1 = points[i]; p2 = points[i+1]
                    sig_x1.append(p1.x()); sig_y1.append(p1.y())
                    sig_x2.append(p2.x()); sig_y2.append(p2.y())
                
        if std_x: self.core.load_std_cells(std_x, std_y, std_w, std_h)
        if mac_x: self.core.load_macros(mac_x, mac_y, mac_w, mac_h, mac_names)
        if tap_x and hasattr(self.core, 'load_tap_cells'): self.core.load_tap_cells(tap_x, tap_y, tap_w, tap_h)
        if pin_x: self.core.load_pins(pin_x, pin_y, pin_w, pin_h, pin_names)
        if pwr_x: self.core.load_power(pwr_x, pwr_y, pwr_w, pwr_h)
        if sig_x1: self.core.load_signals(sig_x1, sig_y1, sig_x2, sig_y2)
        if reg_x: self.core.load_regions(reg_x, reg_y, reg_w, reg_h, reg_names)
        if vi_x and hasattr(self.core, 'load_voltage_islands'):
            self.core.load_voltage_islands(vi_x, vi_y, vi_w, vi_h, vi_volts, vi_names)
        if blk_x: self.core.load_blockages(blk_x, blk_y, blk_w, blk_h)
        
        if self.first_load:
            self.core.fit_in_view()
            self.first_load = False

        if hasattr(self, 'completer') and self.def_data and self.def_data.comps_map:
            names = sorted(list(self.def_data.comps_map.keys()))
            self.completer.setModel(QStringListModel(names))
