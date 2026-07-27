import json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

def clean_instance_name(name):
    if "/" in name or "\\" in name:
        parts = name.replace("\\", "/").split("/")
        return parts[-1]
    return name

class SchematicPort(QGraphicsRectItem):
    def __init__(self, name, direction, is_left, parent=None):
        super().__init__(parent)
        self.name = name
        self.direction = direction
        self.is_left = is_left
        self.setRect(0, 0, 10, 10)
        self.setBrush(QColor("#61afef") if direction == "input" else QColor("#e06c75"))
        self.setPen(QPen(Qt.PenStyle.NoPen))
        
        self.lbl = QGraphicsTextItem(name, self)
        self.lbl.setFont(QFont("Consolas", 8))
        self.lbl.setDefaultTextColor(QColor("#abb2bf"))
        
        if is_left:
            self.lbl.setPos(15, -5)
        else:
            self.lbl.setPos(-self.lbl.boundingRect().width() - 5, -5)

    def get_anchor(self):
        pos = self.scenePos()
        if self.is_left:
            return QPointF(pos.x(), pos.y() + 5)
        else:
            return QPointF(pos.x() + 10, pos.y() + 5)

class SchematicBlock(QGraphicsRectItem):
    def __init__(self, name, type_name, is_top=False):
        super().__init__()
        self.raw_name = name
        self.type_name = type_name
        self.is_top = is_top
        self.short_id = clean_instance_name(name)
        
        self.setBrush(QColor("#282c34"))
        self.setPen(QPen(QColor("#61afef") if is_top else QColor("#98c379"), 2))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setData(0, type_name if type_name != "unknown" else self.short_id) 
        
        if self.short_id != type_name and not is_top:
            title_text = f"ID: {self.short_id}\nType: {type_name}"
        else:
            title_text = self.short_id
            
        self.title = QGraphicsTextItem(title_text, self)
        self.title.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        self.title.setDefaultTextColor(QColor("#e5c07b"))
        self.ports = {} 
        
    def add_port(self, name, direction, is_left):
        p = SchematicPort(name, direction, is_left, self)
        self.ports[name] = p
        
    def layout_ports(self):
        left_ports = [p for p in self.ports.values() if p.is_left]
        right_ports = [p for p in self.ports.values() if not p.is_left]
        max_ports = max(len(left_ports), len(right_ports))
        height = max(60, max_ports * 20 + 40)
        width = max(160, self.title.boundingRect().width() + 40)
        
        self.setRect(0, 0, width, height)
        self.title.setPos((width - self.title.boundingRect().width()) / 2, 5)
        
        ly = 35
        for p in left_ports:
            p.setPos(-5, ly)
            ly += 20
        ry = 35
        for p in right_ports:
            p.setPos(width - 5, ry)
            ry += 20

def parse_and_draw_json(scene, json_path, target_module, mode):
    scene.clear()
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        modules = data.get("modules", {})
        if target_module not in modules: return
        mod = modules[target_module]
        
        if mode == "top":
            block = SchematicBlock(target_module, target_module, is_top=True)
            for port_name, port_data in mod.get("ports", {}).items():
                dir = port_data.get("direction", "input")
                block.add_port(port_name, dir, is_left=(dir=="input"))
            block.layout_ports()
            scene.addItem(block)
            
        elif mode == "block":
            cells = mod.get("cells", {})
            ports = mod.get("ports", {})
            
            in_boundary = SchematicBlock("INPUTS", "BOUNDARY", is_top=True)
            out_boundary = SchematicBlock("OUTPUTS", "BOUNDARY", is_top=True)
            
            for port_name, port_data in ports.items():
                dir = port_data.get("direction", "input")
                if dir == "input":
                    in_boundary.add_port(port_name, "output", is_left=False) 
                else:
                    out_boundary.add_port(port_name, "input", is_left=True) 
                    
            in_boundary.layout_ports()
            out_boundary.layout_ports()
            scene.addItem(in_boundary)
            scene.addItem(out_boundary)
            
            blocks = []
            for cell_name, cell_data in cells.items():
                c_type = cell_data.get("type", "unknown")
                block = SchematicBlock(cell_name, c_type)
                directions = cell_data.get("port_directions", {})
                for p_name, p_dir in directions.items():
                    block.add_port(p_name, p_dir, is_left=(p_dir=="input"))
                block.layout_ports()
                blocks.append(block)
                scene.addItem(block)
            
            in_boundary.setPos(0, 0)
            
            num_blocks = len(blocks)
            max_rows = max(2, int(num_blocks ** 0.5))
            col_x = 300
            row_idx = 0
            max_w_in_col = 0
            
            for i, b in enumerate(blocks):
                y_pos = (row_idx - (max_rows // 2)) * 260
                b.setPos(col_x, y_pos)
                max_w_in_col = max(max_w_in_col, b.boundingRect().width())
                
                row_idx += 1
                if row_idx >= max_rows:
                    row_idx = 0
                    col_x += max_w_in_col + 200
                    max_w_in_col = 0
                    
            if row_idx != 0: col_x += max_w_in_col + 200
            out_boundary.setPos(col_x + 100, 0)
            
            all_blocks = [in_boundary, out_boundary] + blocks
            bit_sources = {} 
            bit_sinks = {}   
            
            for p_name, p_data in ports.items():
                dir = p_data.get("direction", "input")
                bits = p_data.get("bits", [])
                for b in bits:
                    if type(b) is int:
                        if dir == "input": bit_sources[b] = in_boundary.ports[p_name].get_anchor()
                        else:
                            if b not in bit_sinks: bit_sinks[b] = []
                            bit_sinks[b].append(out_boundary.ports[p_name].get_anchor())
                            
            for b in blocks:
                c_data = cells[b.raw_name]
                conns = c_data.get("connections", {})
                dirs = c_data.get("port_directions", {})
                for p_name, bits in conns.items():
                    dir = dirs.get(p_name, "input")
                    if p_name in b.ports:
                        anchor = b.ports[p_name].get_anchor()
                        for bit in bits:
                            if type(bit) is int:
                                if dir == "output": bit_sources[bit] = anchor
                                else:
                                    if bit not in bit_sinks: bit_sinks[bit] = []
                                    bit_sinks[bit].append(anchor)
                        # Precompute safe highway boundaries for collision avoidance
            min_y = min([b.sceneBoundingRect().top() for b in all_blocks])
            max_y = max([b.sceneBoundingRect().bottom() for b in all_blocks])
            
            # --- STEP 1: Bus Bundling ---
            route_groups = {} # key: (src, tuple(sinks)), value: list of bits
            for bit, src in bit_sources.items():
                sinks = tuple(bit_sinks.get(bit, []))
                src_key = (src.x(), src.y())
                sink_keys = tuple(sorted([(s.x(), s.y()) for s in sinks]))
                route_key = (src_key, sink_keys)
                if route_key not in route_groups:
                    route_groups[route_key] = []
                route_groups[route_key].append(bit)
                
            # --- STEP 2: UID Assignment & Segment Generation ---
            uid = 0
            segments = []
            
            for (src_key, sink_keys), bits in route_groups.items():
                uid += 1
                src = QPointF(src_key[0], src_key[1])
                sinks = [QPointF(sk[0], sk[1]) for sk in sink_keys]
                
                # Draw Pin Dots and Bus Labels
                src_dot = QGraphicsEllipseItem(src.x() - 3, src.y() - 3, 6, 6)
                src_dot.setBrush(QColor("#98c379")) 
                src_dot.setPen(QPen(Qt.PenStyle.NoPen))
                src_dot.setZValue(5)
                scene.addItem(src_dot)
                
                lbl = QGraphicsTextItem(f"[{len(bits)}]")
                lbl.setFont(QFont("Consolas", 7))
                lbl.setDefaultTextColor(QColor("#abb2bf"))
                lbl.setPos(src.x() + 5, src.y() - 15)
                lbl.setZValue(5)
                scene.addItem(lbl)
                
                trunk_x = src.x() + 20 + (uid % 12) * 8
                t_r = QRectF(QPointF(src.x(), src.y()), QPointF(trunk_x, src.y())).normalized().adjusted(0, -10, 10, 10)
                for b in all_blocks:
                    br = b.sceneBoundingRect()
                    if br.intersects(t_r) and not br.contains(src):
                        trunk_x = min(trunk_x, br.left() - 20)
                        
                segments.append({'uid': uid, 'type': 'H', 'x1': src.x(), 'x2': trunk_x, 'y': src.y()})
                
                for sink_idx, sink in enumerate(sinks):
                    sink_dot = QGraphicsEllipseItem(sink.x() - 3, sink.y() - 3, 6, 6)
                    sink_dot.setBrush(QColor("#98c379")) 
                    sink_dot.setPen(QPen(Qt.PenStyle.NoPen))
                    sink_dot.setZValue(5)
                    scene.addItem(sink_dot)
                    
                    vt_x = ((trunk_x + sink.x()) / 2) + ((uid % 8) - 4) * 12 + (sink_idx * 6)
                    
                    def collides(r_x1, r_y1, r_x2, r_y2):
                        r = QRectF(QPointF(r_x1, r_y1), QPointF(r_x2, r_y2)).normalized().adjusted(-15, -15, 15, 15)
                        for b in all_blocks:
                            if b.sceneBoundingRect().intersects(r) and not b.sceneBoundingRect().contains(src) and not b.sceneBoundingRect().contains(sink):
                                return True
                        return False
                        
                    if not collides(trunk_x, src.y(), vt_x, src.y()) and not collides(vt_x, src.y(), vt_x, sink.y()) and not collides(vt_x, sink.y(), sink.x(), sink.y()):
                        segments.append({'uid': uid, 'type': 'H', 'x1': trunk_x, 'x2': vt_x, 'y': src.y()})
                        segments.append({'uid': uid, 'type': 'V', 'x': vt_x, 'y1': src.y(), 'y2': sink.y()})
                        segments.append({'uid': uid, 'type': 'H', 'x1': vt_x, 'x2': sink.x(), 'y': sink.y()})
                    else:
                        acc_x1 = trunk_x + 10 + (sink_idx * 5)
                        acc_x2 = sink.x() - 20 - (sink_idx * 5)
                        
                        highway_up = min_y - 60 - (uid % 15)*20
                        highway_down = max_y + 60 + (uid % 15)*20
                        
                        def collides_v(x, y1, y2, ignore_pt):
                            r = QRectF(QPointF(x, y1), QPointF(x, y2)).normalized().adjusted(-20, -20, 20, 20)
                            for b in all_blocks:
                                br = b.sceneBoundingRect()
                                if br.intersects(r) and not br.contains(ignore_pt): return True
                            return False
                            
                        chosen_highway = highway_down
                        for _ in range(25):
                            up_safe = not collides_v(acc_x1, src.y(), highway_up, src) and not collides_v(acc_x2, sink.y(), highway_up, sink)
                            down_safe = not collides_v(acc_x1, src.y(), highway_down, src) and not collides_v(acc_x2, sink.y(), highway_down, sink)
                            
                            if up_safe:
                                chosen_highway = highway_up
                                break
                            elif down_safe:
                                chosen_highway = highway_down
                                break
                            else:
                                acc_x1 += 30
                                acc_x2 -= 30
                                
                        segments.append({'uid': uid, 'type': 'H', 'x1': trunk_x, 'x2': acc_x1, 'y': src.y()})
                        segments.append({'uid': uid, 'type': 'V', 'x': acc_x1, 'y1': src.y(), 'y2': chosen_highway})
                        segments.append({'uid': uid, 'type': 'H', 'x1': acc_x1, 'x2': acc_x2, 'y': chosen_highway})
                        segments.append({'uid': uid, 'type': 'V', 'x': acc_x2, 'y1': chosen_highway, 'y2': sink.y()})
                        segments.append({'uid': uid, 'type': 'H', 'x1': acc_x2, 'x2': sink.x(), 'y': sink.y()})
                        
            # --- POST-PROCESSING: Space out parallel overlapping lines (Different UIDs) ---
            v_segs_all = [s for s in segments if s['type'] == 'V']
            for _ in range(3):
                for i in range(len(v_segs_all)):
                    for j in range(i+1, len(v_segs_all)):
                        v1, v2 = v_segs_all[i], v_segs_all[j]
                        if v1['uid'] == v2['uid']: continue 
                        
                        y1_min, y1_max = min(v1['y1'], v1['y2']), max(v1['y1'], v1['y2'])
                        y2_min, y2_max = min(v2['y1'], v2['y2']), max(v2['y1'], v2['y2'])
                        
                        if abs(v1['x'] - v2['x']) < 6:
                            if max(y1_min, y2_min) < min(y1_max, y2_max):
                                shift = 16
                                old_x = v2['x']
                                v2['x'] += shift
                                for h in segments:
                                    if h['type'] == 'H' and h['uid'] == v2['uid']:
                                        if h['x1'] == old_x: h['x1'] = v2['x']
                                        elif h['x2'] == old_x: h['x2'] = v2['x']

            h_segs_all = [s for s in segments if s['type'] == 'H']
            for _ in range(3):
                for i in range(len(h_segs_all)):
                    for j in range(i+1, len(h_segs_all)):
                        h1, h2 = h_segs_all[i], h_segs_all[j]
                        if h1['uid'] == h2['uid']: continue 
                        
                        x1_min, x1_max = min(h1['x1'], h1['x2']), max(h1['x1'], h1['x2'])
                        x2_min, x2_max = min(h2['x1'], h2['x2']), max(h2['x1'], h2['x2'])
                        
                        if abs(h1['y'] - h2['y']) < 6:
                            if max(x1_min, x2_min) < min(x1_max, x2_max):
                                shift = 20
                                old_y = h2['y']
                                h2['y'] += shift
                                for v in segments:
                                    if v['type'] == 'V' and v['uid'] == h2['uid']:
                                        if v['y1'] == old_y: v['y1'] = h2['y']
                                        elif v['y2'] == old_y: v['y2'] = h2['y']

            # --- STEP 3: Intersection Math (Junctions vs Crossings) ---
            for seg in segments:
                if seg['type'] == 'H':
                    seg['x_min'] = min(seg['x1'], seg['x2'])
                    seg['x_max'] = max(seg['x1'], seg['x2'])
                else:
                    seg['y_min'] = min(seg['y1'], seg['y2'])
                    seg['y_max'] = max(seg['y1'], seg['y2'])
                    
            h_segs = [s for s in segments if s['type'] == 'H']
            v_segs = [s for s in segments if s['type'] == 'V']
            
            junctions = set()
            v_crossings = {}
            
            for h in h_segs:
                for v in v_segs:
                    if h['x_min'] <= v['x'] <= h['x_max'] and v['y_min'] <= h['y'] <= v['y_max']:
                        ix, iy = v['x'], h['y']
                        if h['uid'] == v['uid']:
                            # Same UID = Junction! (Ignore corners)
                            if not (ix == h['x1'] or ix == h['x2']) or not (iy == v['y1'] or iy == v['y2']):
                                junctions.add((ix, iy))
                        else:
                            # Different UID = Crossing!
                            v_idx = id(v)
                            if v_idx not in v_crossings: v_crossings[v_idx] = []
                            v_crossings[v_idx].append(iy)
                            
            # --- STEP 4: Drawing ---
            for seg in segments:
                if seg['type'] == 'H':
                    path = QPainterPath(QPointF(seg['x1'], seg['y']))
                    path.lineTo(seg['x2'], seg['y'])
                    line = QGraphicsPathItem(path)
                    line.setPen(QPen(QColor("#d19a66"), 2))
                    line.setZValue(-1)
                    scene.addItem(line)
                else:
                    cross_ys = v_crossings.get(id(seg), [])
                    start_y, end_y = seg['y1'], seg['y2']
                    direction = 1 if end_y > start_y else -1
                    cross_ys.sort(key=lambda y: y * direction)
                    
                    path = QPainterPath(QPointF(seg['x'], start_y))
                    for cy in cross_ys:
                        if abs(cy - start_y) < 5 or abs(cy - end_y) < 5: continue
                        hop_start = cy - (4 * direction)
                        hop_end = cy + (4 * direction)
                        
                        path.lineTo(seg['x'], hop_start)
                        path.moveTo(seg['x'], hop_end)
                        
                        gap_path = QPainterPath(QPointF(seg['x'], hop_start))
                        gap_path.lineTo(seg['x'], hop_end)
                        gap_line = QGraphicsPathItem(gap_path)
                        gap_line.setPen(QPen(QColor("#e06c75"), 2.5))
                        gap_line.setZValue(5)
                        scene.addItem(gap_line)
                        
                    path.lineTo(seg['x'], end_y)
                    line = QGraphicsPathItem(path)
                    line.setPen(QPen(QColor("#d19a66"), 2))
                    line.setZValue(-1)
                    scene.addItem(line)
                    
            for jx, jy in junctions:
                j_rect = QGraphicsRectItem(jx - 3, jy - 3, 6, 6)
                j_rect.setBrush(QColor("#c678dd"))
                j_rect.setPen(QPen(Qt.PenStyle.NoPen))
                j_rect.setZValue(10)
                scene.addItem(j_rect)
                    
    except Exception as e:
        print(f"Block Diagram Parse Error: {e}")
