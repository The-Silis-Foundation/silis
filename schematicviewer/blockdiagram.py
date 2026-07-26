import json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

def clean_cell_name(name, c_type):
    if "/" in name or "\\" in name:
        parts = name.replace("\\", "/").split("/")
        last_part = parts[-1]
        if "$" in last_part:
            last_part = last_part.split("$")[0]
        op = name.split("$")[1] if name.startswith("$") and len(name.split("$")) > 1 else c_type
        return f"{op} ({last_part})"
    if name.startswith("$"):
        parts = [p for p in name.split("$") if p]
        return parts[0] if parts else name
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
        self.clean_name = clean_cell_name(name, type_name)
        
        self.setBrush(QColor("#282c34"))
        self.setPen(QPen(QColor("#61afef") if is_top else QColor("#98c379"), 2))
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setData(0, type_name if type_name != "unknown" else self.clean_name) 
        
        title_text = f"{self.clean_name}\n({type_name})" if self.clean_name != type_name and not is_top else self.clean_name
        self.title = QGraphicsTextItem(title_text, self)
        self.title.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
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

def path_collides_with_blocks(src, sink, mid_x, blocks):
    r1 = QRectF(src, QPointF(mid_x, src.y())).normalized().adjusted(-10, -10, 10, 10)
    r2 = QRectF(QPointF(mid_x, src.y()), QPointF(mid_x, sink.y())).normalized().adjusted(-10, -10, 10, 10)
    r3 = QRectF(QPointF(mid_x, sink.y()), sink).normalized().adjusted(-10, -10, 10, 10)
    
    for b in blocks:
        brect = b.sceneBoundingRect().adjusted(-5, -5, 5, 5)
        if brect.intersects(r1) or brect.intersects(r2) or brect.intersects(r3):
            if not brect.contains(src) and not brect.contains(sink):
                return True
    return False

def parse_and_draw_json(scene, json_path, target_module, mode):
    scene.clear()
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        modules = data.get("modules", {})
        if target_module not in modules:
            return
            
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
            
            # 2. Multi-Row Grid Layout (Stops horizontal explosion and squarifies diagram)
            in_boundary.setPos(0, 0)
            
            num_blocks = len(blocks)
            max_rows = max(2, int(num_blocks ** 0.5))
            col_x = 300
            row_idx = 0
            max_w_in_col = 0
            
            for i, b in enumerate(blocks):
                y_pos = (row_idx - (max_rows // 2)) * 240
                b.setPos(col_x, y_pos)
                max_w_in_col = max(max_w_in_col, b.boundingRect().width())
                
                row_idx += 1
                if row_idx >= max_rows:
                    row_idx = 0
                    col_x += max_w_in_col + 180
                    max_w_in_col = 0
                    
            if row_idx != 0:
                col_x += max_w_in_col + 180
                
            out_boundary.setPos(col_x + 50, 0)
            
            # 3. Routing (Net mapping with collision avoidance)
            all_blocks = [in_boundary, out_boundary] + blocks
            bit_sources = {} 
            bit_sinks = {}   
            
            for p_name, p_data in ports.items():
                dir = p_data.get("direction", "input")
                bits = p_data.get("bits", [])
                for b in bits:
                    if type(b) is int:
                        if dir == "input":
                            bit_sources[b] = in_boundary.ports[p_name].get_anchor()
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
                                if dir == "output":
                                    bit_sources[bit] = anchor
                                else:
                                    if bit not in bit_sinks: bit_sinks[bit] = []
                                    bit_sinks[bit].append(anchor)
            
            # Draw wires & highlight junctions
            net_idx = 0
            for bit, src in bit_sources.items():
                sinks = bit_sinks.get(bit, [])
                net_idx += 1
                
                # Solder dot on source pin
                src_dot = QGraphicsEllipseItem(src.x() - 3, src.y() - 3, 6, 6)
                src_dot.setBrush(QColor("#98c379")) 
                src_dot.setPen(QPen(Qt.PenStyle.NoPen))
                src_dot.setZValue(2)
                scene.addItem(src_dot)
                
                # Highlight junctions if fanout > 1 (Solder Dots)
                if len(sinks) > 1:
                    j_dot = QGraphicsEllipseItem(src.x() - 5, src.y() - 5, 10, 10)
                    j_dot.setBrush(QColor("#e5c07b")) 
                    j_dot.setPen(QPen(QColor("#ffffff"), 1.5))
                    j_dot.setZValue(3)
                    scene.addItem(j_dot)

                for sink in sinks:
                    sink_dot = QGraphicsEllipseItem(sink.x() - 3, sink.y() - 3, 6, 6)
                    sink_dot.setBrush(QColor("#98c379"))
                    sink_dot.setPen(QPen(Qt.PenStyle.NoPen))
                    sink_dot.setZValue(2)
                    scene.addItem(sink_dot)
                    
                    path = QPainterPath(src)
                    mid_x = (src.x() + sink.x()) / 2
                    
                    # If direct path overlaps a block, use an overhead/underground highway
                    if path_collides_with_blocks(src, sink, mid_x, all_blocks):
                        highway_y = -350 - (net_idx % 8) * 15 if (net_idx % 2 == 0) else 350 + (net_idx % 8) * 15
                        path.lineTo(src.x() + 20, src.y())
                        path.lineTo(src.x() + 20, highway_y)
                        path.lineTo(sink.x() - 20, highway_y)
                        path.lineTo(sink.x() - 20, sink.y())
                        path.lineTo(sink)
                    else:
                        path.lineTo(mid_x, src.y())
                        path.lineTo(mid_x, sink.y())
                        path.lineTo(sink)
                    
                    line = QGraphicsPathItem(path)
                    line.setPen(QPen(QColor("#d19a66"), 2))
                    line.setZValue(-1) 
                    scene.addItem(line)
                    
    except Exception as e:
        print(f"Block Diagram Parse Error: {e}")
