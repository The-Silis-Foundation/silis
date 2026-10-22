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

            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
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
                                for match in re.finditer(r'MACRO\s+([\w\d_]+)[\s\S]*?SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)', content):
                                    self.comp_sizes[match.group(1)] = (float(match.group(2)), float(match.group(3)))
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
                            is_tap = "tap" in model_lower or "fill" in model_lower
                            is_clock = "clk" in model_lower and not current_comp_name.startswith("_")
                            
                            if (current_comp_model in self.comp_sizes) or is_macro_by_size:
                                self.comp_types[current_comp_name] = "MACRO"
                            elif is_tap: self.comp_types[current_comp_name] = "TAP"
                            elif is_clock: self.comp_types[current_comp_name] = "CLOCK"
                            else: self.comp_types[current_comp_name] = "STD"
                            
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
                            w_match = re.search(r'ROUTED\s+\S+\s+(\d+)', line)
                            if w_match: current_route_width = int(w_match.group(1))

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
    def __init__(self, parent=None):
        super().__init__(parent)
        # [FIX] REMOVED OpenGL to stop MESA/libEGL errors and Black Screen
        # self.setViewport(QOpenGLWidget()) 
        
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

        self.last_mtime = mtime
        self._last_size = size

        # Show non-blocking spinner in status bar if IDE available
        if self.ide and hasattr(self.ide, 'statusBar'):
            self.ide.statusBar().showMessage("Loading DEF layout in background...")

        if hasattr(self, '_load_worker') and self._load_worker and self._load_worker.isRunning():
            self._load_worker.terminate()
            self._load_worker.wait()

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
        
    def set_heatmap(self, mode):
        if not self.core or not self.def_data or not self.def_data.die_rect: return
        import random
        data = [0.0] * 400
        
        dr = self.def_data.die_rect
        if dr.width() <= 0 or dr.height() <= 0: return
        
        if mode == 1: # Congestion
            for pts in self.def_data.signal_routes:
                for p in pts:
                    cx = int(20 * (p.x() - dr.x()) / dr.width())
                    cy = int(20 * (p.y() - dr.y()) / dr.height())
                    if 0 <= cx < 20 and 0 <= cy < 20:
                        data[cy * 20 + cx] = min(1.0, data[cy * 20 + cx] + 0.05)
        elif mode == 2: # Cell Density
            for name, rect in self.def_data.comps_map.items():
                cx = int(20 * (rect.x() - dr.x()) / dr.width())
                cy = int(20 * (rect.y() - dr.y()) / dr.height())
                if 0 <= cx < 20 and 0 <= cy < 20:
                    data[cy * 20 + cx] = min(1.0, data[cy * 20 + cx] + 0.02)
        elif mode in [3, 4]:
            for i in range(400): data[i] = random.random() * 0.8
            
        self.core.set_heatmap(mode, data)

    def redraw(self):
        if not self.core or not self.def_data: return
        self.core.clear()
        
        d = self.def_data.die_rect
        self.core.set_core(d.x(), d.y(), d.width(), d.height())
        
        std_x, std_y, std_w, std_h = [], [], [], []
        mac_x, mac_y, mac_w, mac_h, mac_names = [], [], [], [], []
        pin_x, pin_y, pin_w, pin_h, pin_names = [], [], [], [], []
        pwr_x, pwr_y, pwr_w, pwr_h = [], [], [], []
        reg_x, reg_y, reg_w, reg_h, reg_names = [], [], [], [], []
        blk_x, blk_y, blk_w, blk_h = [], [], [], []
        tap_x, tap_y, tap_w, tap_h = [], [], [], []
        
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
                
        if self.show_pins and hasattr(self.def_data, 'pins'):
            for rect, name in self.def_data.pins:
                pin_x.append(rect.x()); pin_y.append(rect.y()); pin_w.append(rect.width()); pin_h.append(rect.height())
                pin_names.append(name)
                
        if hasattr(self.def_data, 'regions'):
            for rect, name in self.def_data.regions:
                reg_x.append(rect.x()); reg_y.append(rect.y()); reg_w.append(rect.width()); reg_h.append(rect.height())
                reg_names.append(name)
                
        if hasattr(self.def_data, 'blockages'):
            for rect in self.def_data.blockages:
                blk_x.append(rect.x()); blk_y.append(rect.y()); blk_w.append(rect.width()); blk_h.append(rect.height())
                
        if self.show_power and hasattr(self.def_data, 'power_routes'):
            for width, points in self.def_data.power_routes:
                for i in range(len(points)-1):
                    p1 = points[i]; p2 = points[i+1]
                    px = min(p1.x(), p2.x()) - width/2
                    py = min(p1.y(), p2.y()) - width/2
                    pw = abs(p2.x() - p1.x()) + width
                    ph = abs(p2.y() - p1.y()) + width
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
        if blk_x: self.core.load_blockages(blk_x, blk_y, blk_w, blk_h)
        
        if self.first_load:
            self.core.fit_in_view()
            self.first_load = False

        if hasattr(self, 'completer') and self.def_data and self.def_data.comps_map:
            names = sorted(list(self.def_data.comps_map.keys()))
            self.completer.setModel(QStringListModel(names))
