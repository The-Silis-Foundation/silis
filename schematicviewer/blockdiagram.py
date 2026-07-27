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

def parse_and_draw_json(scene, json_path, target_module, mode, channel_spacing=400):
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
            
        elif mode in ("block", "gate"):
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
            if mode != "gate":
                scene.addItem(in_boundary)
            if mode != "gate":
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
                if mode != "gate":
                    scene.addItem(block)
            
            in_boundary.setPos(0, 0)
            
            num_blocks = len(blocks)
            max_rows = max(2, int(num_blocks ** 0.5))
            col_x = 300
            col_y = 0
            row_idx = 0
            max_w_in_col = 0
            
            for i, b in enumerate(blocks):
                b.setPos(col_x, col_y)
                max_w_in_col = max(max_w_in_col, b.boundingRect().width())
                
                col_y += b.boundingRect().height() + 300
                
                row_idx += 1
                if row_idx >= max_rows:
                    row_idx = 0
                    col_x += max_w_in_col + channel_spacing
                    col_y = 0
                    max_w_in_col = 0
                    
            if row_idx != 0: col_x += max_w_in_col + channel_spacing
            
            in_boundary.setPos(0, 0)
            out_boundary.setPos(col_x + 100, 0)
            
            all_blocks = [in_boundary, out_boundary] + blocks
            
            # --- START RIP-UP AND REROUTE LOOP ---
            MAX_ITERS = 4
            final_segments = []
            final_bit_sources = {}
            
            for iteration in range(MAX_ITERS):
                bit_sources = {} 
                bit_sinks = {}   
                
                # Dynamic pin coordinates extraction (they move when blocks get shoved)
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

                min_y = min([b.sceneBoundingRect().top() for b in all_blocks])
                max_y = max([b.sceneBoundingRect().bottom() for b in all_blocks])
                
                _src_map = {}
                for bit, src in bit_sources.items():
                    src_key = (src.x(), src.y())
                    if src_key not in _src_map: _src_map[src_key] = {'sinks': set(), 'bits': []}
                    _src_map[src_key]['bits'].append(bit)
                    for s in bit_sinks.get(bit, []): _src_map[src_key]['sinks'].add((s.x(), s.y()))
                    
                route_groups = {}
                for src_key, data in _src_map.items():
                    sink_keys = tuple(sorted(list(data['sinks'])))
                    route_groups[(src_key, sink_keys)] = data['bits']
                    
                uid = 0
                uid_is_bus = {}
                segments = []
                
                def is_keepout_collision(x1, y1, x2, y2, ignore_pt=None, halo=20):
                    if len(blocks) > 500: return False
                    sx1, sx2 = min(x1, x2), max(x1, x2)
                    sy1, sy2 = min(y1, y2), max(y1, y2)
                    
                    for b in all_blocks:
                        br = b.sceneBoundingRect()
                        if ignore_pt and br.contains(ignore_pt): continue
                        
                        bx1 = br.left() - halo
                        by1 = br.top() - halo
                        bx2 = br.right() + halo
                        by2 = br.bottom() + halo
                        
                        if not (sx2 < bx1 or sx1 > bx2 or sy2 < by1 or sy1 > by2):
                            return True
                    return False

                for (src_key, sink_keys), bits in route_groups.items():
                    uid += 1
                    uid_is_bus[uid] = len(bits) > 1
                    src = QPointF(src_key[0], src_key[1])
                    sinks = [QPointF(sk[0], sk[1]) for sk in sink_keys]
                    
                    trunk_x = max(src.x() + 15, src.x() + 20 + (uid % 12) * 8)
                    t_r = QRectF(QPointF(src.x(), src.y()), QPointF(trunk_x, src.y())).normalized().adjusted(0, -10, 10, 10)
                    for b in all_blocks:
                        if len(blocks) > 500: break
                        br = b.sceneBoundingRect()
                        if br.intersects(t_r) and not br.contains(src):
                            trunk_x = max(src.x() + 15, br.left() - 20)
                            
                    segments.append({'uid': uid, 'type': 'H', 'x1': src.x(), 'x2': trunk_x, 'y': src.y(), 'is_pin': True})
                    
                    for sink_idx, sink in enumerate(sinks):
                        min_vtx = src.x() + 15
                        max_vtx = sink.x() - 15 
                        
                        direct_success = False
                        if max_vtx > min_vtx:
                            ideal_vtx = (trunk_x + sink.x()) / 2
                            offset = ((uid % 8) - 4) * 16 + (sink_idx * 16)
                            vt_x = max(min_vtx, min(max_vtx, ideal_vtx + offset))
                            
                            c1 = is_keepout_collision(trunk_x, src.y(), vt_x, src.y(), src, 15)
                            c2 = is_keepout_collision(vt_x, src.y(), vt_x, sink.y(), None, 15)
                            c3 = is_keepout_collision(vt_x, sink.y(), sink.x(), sink.y(), sink, 15)
                            
                            if not (c1 or c2 or c3):
                                segments.append({'uid': uid, 'type': 'H', 'x1': trunk_x, 'x2': vt_x, 'y': src.y(), 'is_pin': False})
                                segments.append({'uid': uid, 'type': 'V', 'x': vt_x, 'y1': src.y(), 'y2': sink.y(), 'is_pin': False})
                                segments.append({'uid': uid, 'type': 'H', 'x1': vt_x, 'x2': sink.x(), 'y': sink.y(), 'is_pin': True})
                                direct_success = True

                        if not direct_success:
                            acc_x1 = max(src.x() + 15, trunk_x + 10 + (sink_idx * 16))
                            acc_x2 = sink.x() - 20 - (sink_idx * 16)
                            if acc_x2 >= sink.x() - 15:
                                acc_x2 = sink.x() - 15
                            
                            highway_up = min_y - 60 - (uid % 15) * 20
                            highway_down = max_y + 60 + (uid % 15) * 20
                            
                            chosen_highway = highway_down
                            for _ in range(25):
                                up_safe = not is_keepout_collision(acc_x1, src.y(), acc_x1, highway_up, src, 15) and \
                                          not is_keepout_collision(acc_x2, sink.y(), acc_x2, highway_up, sink, 15)
                                down_safe = not is_keepout_collision(acc_x1, src.y(), acc_x1, highway_down, src, 15) and \
                                            not is_keepout_collision(acc_x2, sink.y(), acc_x2, highway_down, sink, 15)
                                
                                if up_safe:
                                    chosen_highway = highway_up
                                    break
                                elif down_safe:
                                    chosen_highway = highway_down
                                    break
                                else:
                                    acc_x1 += 20
                                    if acc_x2 > 50: acc_x2 -= 10
                                    
                            segments.append({'uid': uid, 'type': 'H', 'x1': trunk_x, 'x2': acc_x1, 'y': src.y(), 'is_pin': False})
                            segments.append({'uid': uid, 'type': 'V', 'x': acc_x1, 'y1': src.y(), 'y2': chosen_highway, 'is_pin': False})
                            segments.append({'uid': uid, 'type': 'H', 'x1': acc_x1, 'x2': acc_x2, 'y': chosen_highway, 'is_pin': False})
                            segments.append({'uid': uid, 'type': 'V', 'x': acc_x2, 'y1': chosen_highway, 'y2': sink.y(), 'is_pin': False})
                            segments.append({'uid': uid, 'type': 'H', 'x1': acc_x2, 'x2': sink.x(), 'y': sink.y(), 'is_pin': True})
                
                # --- COLLISION DETECTION & SHOVE LOGIC ---
                if len(blocks) > 500: continue
                # --- COLLISION DETECTION & SHOVE LOGIC ---
                if len(blocks) > 500: continue
                violation = False
                for b in blocks:
                    br = b.sceneBoundingRect().adjusted(-5, -5, 5, 5)
                    for seg in segments:
                        if seg.get('is_pin', False):
                            continue
                            
                        # Check Horizontal Wires
                        if seg['type'] == 'H':
                            sx1, sx2 = min(seg['x1'], seg['x2']), max(seg['x1'], seg['x2'])
                            if sx1 < br.right() and sx2 > br.left() and br.top() < seg['y'] < br.bottom():
                                violation = True
                        # Check Vertical Wires
                        elif seg['type'] == 'V':
                            sy1, sy2 = min(seg['y1'], seg['y2']), max(seg['y1'], seg['y2'])
                            if sy1 < br.bottom() and sy2 > br.top() and br.left() < seg['x'] < br.right():
                                violation = True
                                
                        if violation:
                            print(f"[ROUTER] Iteration {iteration+1}: Wire hit {b.short_id}. Shoving column +100px.")
                            target_x = b.pos().x()
                            # Cascade push everything below it in the same column
                            for push_b in blocks:
                                if abs(push_b.pos().x() - target_x) < 2.0 and push_b.pos().y() >= b.pos().y():
                                    push_b.setPos(target_x, push_b.pos().y() + 100)
                            break
                    if violation:
                        break

            # --- POST-PROCESSING: Space out parallel overlapping channel lines ---
            if len(blocks) <= 500:
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
                                    old_x = v2['x']
                                    safe_x = old_x
                                    for step in range(1, 40):
                                        test_shift = (step // 2 + 1) * 16 if step % 2 != 0 else -(step // 2) * 16
                                        tx = old_x + test_shift
                                        if not is_keepout_collision(tx, y2_min, tx, y2_max, None, 15):
                                            if abs(tx - v1['x']) >= 6:
                                                safe_x = tx
                                                break
                                                
                                    v2['x'] = safe_x
                                    for h in segments:
                                        if h['type'] == 'H' and h['uid'] == v2['uid']:
                                            if h['x1'] == old_x: h['x1'] = v2['x']
                                            elif h['x2'] == old_x: h['x2'] = v2['x']

                h_segs_all = [s for s in segments if s['type'] == 'H' and not s.get('is_pin', False)]
                for _ in range(3):
                    for i in range(len(h_segs_all)):
                        for j in range(i+1, len(h_segs_all)):
                            h1, h2 = h_segs_all[i], h_segs_all[j]
                            if h1['uid'] == h2['uid']: continue 
                            
                            x1_min, x1_max = min(h1['x1'], h1['x2']), max(h1['x1'], h1['x2'])
                            x2_min, x2_max = min(h2['x1'], h2['x2']), max(h2['x1'], h2['x2'])
                            
                            if abs(h1['y'] - h2['y']) < 6:
                                if max(x1_min, x2_min) < min(x1_max, x2_max):
                                    old_y = h2['y']
                                    safe_y = old_y
                                    for step in range(1, 40):
                                        test_shift = (step // 2 + 1) * 20 if step % 2 != 0 else -(step // 2) * 20
                                        ty = old_y + test_shift
                                        if not is_keepout_collision(x2_min, ty, x2_max, ty, None, 15):
                                            if abs(ty - h1['y']) >= 6:
                                                safe_y = ty
                                                break
                                                
                                    h2['y'] = safe_y
                                    for v in segments:
                                        if v['type'] == 'V' and v['uid'] == h2['uid']:
                                            if v['y1'] == old_y: v['y1'] = h2['y']
                                            elif v['y2'] == old_y: v['y2'] = h2['y']

            # --- STEP 3: Intersection & Junction Node Math ---
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
            if len(blocks) > 500:
                import ctypes, os
                class CSegment(ctypes.Structure):
                    _fields_ = [("uid", ctypes.c_int), ("is_h", ctypes.c_int), 
                                ("x1", ctypes.c_int), ("x2", ctypes.c_int), 
                                ("y1", ctypes.c_int), ("y2", ctypes.c_int),
                                ("x_min", ctypes.c_int), ("x_max", ctypes.c_int),
                                ("y_min", ctypes.c_int), ("y_max", ctypes.c_int)]
                class CRect(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_int), ("top", ctypes.c_int), 
                                ("right", ctypes.c_int), ("bottom", ctypes.c_int)]
                try:
                    fast_router = ctypes.CDLL(os.path.join(os.path.dirname(__file__), "fast_router.so"))
                    fast_router.space_out_channels_v.restype = ctypes.c_int
                    fast_router.space_out_channels_h.restype = ctypes.c_int
                    c_segs = (CSegment * len(segments))()
                    for idx, s in enumerate(segments):
                        c_segs[idx].uid = s['uid']
                        c_segs[idx].is_h = 1 if s['type'] == 'H' else 0
                        c_segs[idx].x1 = int(s.get('x1', s.get('x', 0)))
                        c_segs[idx].x2 = int(s.get('x2', s.get('x', 0)))
                        c_segs[idx].y1 = int(s.get('y1', s.get('y', 0)))
                        c_segs[idx].y2 = int(s.get('y2', s.get('y', 0)))
                        c_segs[idx].x_min = min(c_segs[idx].x1, c_segs[idx].x2)
                        c_segs[idx].x_max = max(c_segs[idx].x1, c_segs[idx].x2)
                        c_segs[idx].y_min = min(c_segs[idx].y1, c_segs[idx].y2)
                        c_segs[idx].y_max = max(c_segs[idx].y1, c_segs[idx].y2)
                    c_rects = (CRect * len(all_blocks))()
                    for idx, b in enumerate(all_blocks):
                        br = b.sceneBoundingRect()
                        c_rects[idx].left = int(br.left())
                        c_rects[idx].top = int(br.top())
                        c_rects[idx].right = int(br.right())
                        c_rects[idx].bottom = int(br.bottom())
                    fail_v = fast_router.space_out_channels_v(c_segs, len(segments), c_rects, len(all_blocks))
                    fail_h = fast_router.space_out_channels_h(c_segs, len(segments), c_rects, len(all_blocks))
                    if fail_v or fail_h:
                        print(f"[ROUTER] Collision detected! Re-routing with spacing {channel_spacing + 400}...")
                        return parse_and_draw_json(scene, json_path, target_module, mode, channel_spacing + 400)
                    for idx, s in enumerate(segments):
                        if s['type'] == 'H': s['y'] = c_segs[idx].y1
                        else: s['x'] = c_segs[idx].x1
                except Exception as e:
                    print(f"Failed to run C router: {e}")

            if len(blocks) <= 500:
                for h in h_segs:
                    for v in v_segs:
                        ix, iy = v['x'], h['y']
                        if h['x_min'] <= ix <= h['x_max'] and v['y_min'] <= iy <= v['y_max']:
                            if h['uid'] == v['uid']:
                                # Same UID = Junction (if it's not a pure corner)
                                if not (ix == h['x1'] or ix == h['x2']) or not (iy == v['y1'] or iy == v['y2']):
                                    junctions.add((ix, iy))
                            else:
                                # Different UID = Crossing (only if strictly inside)
                                if h['x_min'] < ix < h['x_max'] and v['y_min'] < iy < v['y_max']:
                                    v_idx = id(v)
                                    if v_idx not in v_crossings: v_crossings[v_idx] = []
                                    v_crossings[v_idx].append(iy)
                            
            # --- STEP 4: Render Graphics ---

            if mode == "gate":
                import xml.sax.saxutils as saxutils
                import os
                try:
                    with open(os.path.expanduser("~/.silis_ui_settings.json")) as f:
                        COLORS = json.load(f)
                except:
                    COLORS = {}
                c_bg = COLORS.get("block", {}).get("background", "#282c34")
                c_stroke = COLORS.get("nodes", {}).get("stroke", "#3e4451")
                c_text_pri = COLORS.get("text", {}).get("primary", "#e6ebf2")
                c_text_sec = COLORS.get("text", {}).get("secondary", "#abb2bf")
                c_port_in = COLORS.get("port", {}).get("input", "#61afef")
                c_port_out = COLORS.get("port", {}).get("output", "#e06c75")
                c_wire = COLORS.get("routing", {}).get("wire", "#d19a66")
                c_bus = COLORS.get("routing", {}).get("bus", "#e5c07b")
                c_dot = COLORS.get("routing", {}).get("pin_dot", "#98c379")
                c_junc = COLORS.get("routing", {}).get("junction", "#c678dd")
                
                svg_w = int(col_x + max_w_in_col + 500)
                svg_h = int(max_y + 1000)
                svg_out = [f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
                           f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}" style="background-color: {c_bg}">']
                
                for seg in segments:
                    is_bus = uid_is_bus.get(seg['uid'], False)
                    color = c_bus if is_bus else c_wire
                    width = 3.5 if is_bus else 2.0
                    if seg['type'] == 'H':
                        svg_out.append(f'<line x1="{seg["x1"]}" y1="{seg["y"]}" x2="{seg["x2"]}" y2="{seg["y"]}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
                    else:
                        svg_out.append(f'<line x1="{seg["x"]}" y1="{seg["y1"]}" x2="{seg["x"]}" y2="{seg["y2"]}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
                        
                for src_key, data in _src_map.items():
                    svg_out.append(f'<circle cx="{src_key[0]}" cy="{src_key[1]}" r="3" fill="{c_dot}"/>')
                    svg_out.append(f'<text x="{src_key[0]+5}" y="{src_key[1]-10}" fill="{c_text_sec}" font-family="Consolas" font-size="10">[{len(data["bits"])}]</text>')
                    for s in data['sinks']:
                        svg_out.append(f'<circle cx="{s[0]}" cy="{s[1]}" r="3" fill="{c_dot}"/>')
                        
                for jx, jy in junctions:
                    svg_out.append(f'<rect x="{jx-3}" y="{jy-3}" width="6" height="6" fill="{c_junc}"/>')
                    
                for b in all_blocks:
                    bx, by = b.pos().x(), b.pos().y()
                    bw, bh = b.boundingRect().width(), b.boundingRect().height()
                    
                    svg_out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{c_bg}" stroke="{c_stroke}" stroke-width="2"/>')
                    svg_out.append(f'<text x="{bx+bw/2}" y="{by+20}" fill="{c_text_pri}" font-family="Consolas" font-size="12" font-weight="bold" text-anchor="middle">{saxutils.escape(b.short_id)}</text>')
                    
                    for p_name, p in b.ports.items():
                        px, py = p.pos().x(), p.pos().y()
                        p_col = c_port_in if p.direction == "input" else c_port_out
                        svg_out.append(f'<rect x="{bx+px}" y="{by+py}" width="10" height="10" fill="{p_col}"/>')
                        
                        lbl_x = bx + px + (15 if p.is_left else -5)
                        anchor = "start" if p.is_left else "end"
                        svg_out.append(f'<text x="{lbl_x}" y="{by+py+8}" fill="{c_text_sec}" font-family="Consolas" font-size="10" text-anchor="{anchor}">{saxutils.escape(p.name)}</text>')
                
                svg_out.append('</svg>')
                svg_path = json_path.replace(".json", "_fast.svg")
                with open(svg_path, 'w') as f:
                    f.write("\n".join(svg_out))
                    
                from PyQt6.QtSvgWidgets import QGraphicsSvgItem
                svg_item = QGraphicsSvgItem(svg_path)
                scene.addItem(svg_item)
                return
            # Render pin dots and labels based on the FINAL bit_sources
            _src_map_f = {}
            for bit, src in bit_sources.items():
                src_key = (src.x(), src.y())
                if src_key not in _src_map_f: _src_map_f[src_key] = {'sinks': set(), 'bits': []}
                _src_map_f[src_key]['bits'].append(bit)
                for s in bit_sinks.get(bit, []): _src_map_f[src_key]['sinks'].add((s.x(), s.y()))
                
            route_groups_final = {}
            for src_key, data in _src_map_f.items():
                sink_keys = tuple(sorted(list(data['sinks'])))
                route_groups_final[(src_key, sink_keys)] = data['bits']

            for (src_key, sink_keys), bits in route_groups_final.items():
                src = QPointF(src_key[0], src_key[1])
                sinks = [QPointF(sk[0], sk[1]) for sk in sink_keys]
                
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
                
                for sink in sinks:
                    sink_dot = QGraphicsEllipseItem(sink.x() - 3, sink.y() - 3, 6, 6)
                    sink_dot.setBrush(QColor("#98c379")) 
                    sink_dot.setPen(QPen(Qt.PenStyle.NoPen))
                    sink_dot.setZValue(5)
                    scene.addItem(sink_dot)

            for seg in segments:
                is_bus = uid_is_bus.get(seg['uid'], False)
                base_color = "#e5c07b" if is_bus else "#d19a66"
                thickness = 3.5 if is_bus else 2.0
                
                if seg['type'] == 'H':
                    path = QPainterPath(QPointF(seg['x1'], seg['y']))
                    path.lineTo(seg['x2'], seg['y'])
                    line = QGraphicsPathItem(path)
                    line.setPen(QPen(QColor(base_color), thickness))
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
                        gap_line.setPen(QPen(QColor("#e06c75"), thickness + 0.5))
                        gap_line.setZValue(5)
                        scene.addItem(gap_line)
                        
                    path.lineTo(seg['x'], end_y)
                    line = QGraphicsPathItem(path)
                    line.setPen(QPen(QColor(base_color), thickness))
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