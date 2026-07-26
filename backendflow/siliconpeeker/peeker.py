import os
import re
import glob
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from config import THEMES, USER_SETTINGS


class DEFParser:
    def __init__(self, def_path, ide=None):
        self.path = def_path
        self.ide = ide
        self.macro_sizes = {}
        if self.ide: self.parse_macro_sizes()
        self.die_rect = QRectF(0,0,0,0)
        self.comps_map = {}   
        self.comp_types = {}  
        self.comp_masters = {} 
        self.module_map = {}  
        self.pins = []       
        self.power_rails = [] 
        self.power_routes = [] 
        self.signal_routes = [] 
        self.dbu = 1000.0    
        self.component_count = 0
        if os.path.exists(def_path):
            self.parse()

    def parse_macro_sizes(self):
        try:
            if not getattr(self.ide, 'project_config', None): return
            pdk_name = self.ide.project_config.get('pdk', '')
            cfg = next((c for c in self.ide.pdk_mgr.configs if c['name'] == pdk_name), None)
            if not cfg: return
            lib_path = cfg.get('lib', '')
            volare_base = lib_path.split("libs.ref")[0]
            import os, glob, re
            search_path = os.path.join(volare_base, "libs.ref", "*", "lef", "*.lef")
            for lef in glob.glob(search_path):
                name = os.path.basename(lef).replace('.lef', '')
                if name in self.ide.project_config.get('macros', []):
                    with open(lef, 'r') as f:
                        content = f.read()
                        m = re.search(r'SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)', content)
                        if m:
                            self.macro_sizes[name] = (float(m.group(1)), float(m.group(2)))
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
                elif line.startswith("END"): 
                    current_section = None
                    if len(current_route_points) >= 2:
                        if current_section == "SPECIALNETS": self.power_routes.append((current_route_width, current_route_points))
                        elif current_section == "NETS": self.signal_routes.append(current_route_points)
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
                    
                    if current_comp_name:
                        if "PLACED" in line or "FIXED" in line or "COVER" in line:
                            coord_match = re.search(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                            if coord_match:
                                x = int(coord_match.group(1))
                                y = int(coord_match.group(2))
                                is_placed = True
                        
                        w, h = std_w, std_h
                        if current_comp_model in self.macro_sizes:
                            w = self.macro_sizes[current_comp_model][0] * self.dbu
                            h = self.macro_sizes[current_comp_model][1] * self.dbu
                            is_macro = True
                            
                        if is_placed or is_macro:
                            self.comps_map[current_comp_name] = QRectF(x, y, w, h)
                            
                            model_lower = current_comp_model.lower()
                            is_tap = "tap" in model_lower or "fill" in model_lower
                            is_clock = "clk" in model_lower and not current_comp_name.startswith("_")
                            
                            if is_tap: self.comp_types[current_comp_name] = "TAP"
                            elif is_clock: self.comp_types[current_comp_name] = "CLOCK"
                            else: self.comp_types[current_comp_name] = "STD"
                            
                            self.comp_masters[current_comp_name] = current_comp_model
                            self.module_map[current_comp_name] = "STD_LOGIC" 
                            self.component_count += 1
                        
                        if ";" in line: current_comp_name = None

                # --- PINS ---
                elif current_section == "PINS":
                    parts = line.split()
                    if line.startswith("-") and len(parts) > 2:
                        current_pin_name = parts[1]
                    
                    if current_pin_name and ("PLACED" in line or "FIXED" in line):
                        coord_match = re.search(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)', line)
                        if coord_match:
                            x = int(coord_match.group(1))
                            y = int(coord_match.group(2))
                            pin_sz = 1 * self.dbu 
                            self.pins.append((QRectF(x, y, pin_sz, pin_sz), current_pin_name))
                            current_pin_name = None 

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
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
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
        self.auto_refresh_timer.start(1000)

    def check_refresh(self):
        if self.current_def_path and os.path.exists(self.current_def_path):
            mtime = os.path.getmtime(self.current_def_path)
            if mtime > self.last_mtime:
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
        if os.path.exists(path):
            self.last_mtime = os.path.getmtime(path)
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
                        
                        is_macro = (rect.width() / self.def_data.dbu > 50)
                        
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
