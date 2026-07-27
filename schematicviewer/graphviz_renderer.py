import json
import os
import subprocess
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsTextItem, QGraphicsRectItem
from PyQt6.QtGui import QPainterPath, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QPointF

def generate_graphviz_dot(yosys_json_path, dot_out_path, module_name):
    """ Converts Yosys structural JSON into a themed Graphviz DOT file. """
    with open(yosys_json_path, 'r') as f:
        data = json.load(f)
        
    try:
        with open(os.path.expanduser("~/.silis_ui_settings.json")) as f:
            COLORS = json.load(f)
    except:
        COLORS = {}
        
    c_bg = COLORS.get("block", {}).get("background", "#282c34")
    c_stroke = COLORS.get("nodes", {}).get("stroke", "#3e4451")
    c_text_pri = COLORS.get("text", {}).get("primary", "#e6ebf2")
    c_wire = COLORS.get("routing", {}).get("wire", "#d19a66")

    mod = data.get("modules", {}).get(module_name)
    if not mod: return
    
    cells = mod.get("cells", {})
    
    with open(dot_out_path, 'w') as f:
        f.write(f'digraph "{module_name}" {{\n')
        f.write(f'  bgcolor="{c_bg}";\n')
        f.write(f'  splines=ortho;\n')
        f.write(f'  nodesep=0.5;\n')
        f.write(f'  node [shape=box, style=filled, fillcolor="{c_bg}", color="{c_stroke}", fontcolor="{c_text_pri}", fontname="Consolas"];\n')
        f.write(f'  edge [color="{c_wire}", penwidth=2.0];\n')
        
        # Add nodes
        for c, c_data in cells.items():
            f.write(f'  "{c}";\n')
            
        # Add edges (basic netlist extraction for Graphviz)
        net_map = {} # bit -> [sources, sinks]
        for c, c_data in cells.items():
            for p_name, bits in c_data.get("connections", {}).items():
                dir = c_data.get("port_directions", {}).get(p_name, "input")
                for b in bits:
                    if type(b) is int:
                        if b not in net_map: net_map[b] = {'src': [], 'snk': []}
                        if dir == "output": net_map[b]['src'].append(c)
                        else: net_map[b]['snk'].append(c)
                        
        for bit, data in net_map.items():
            for src in data['src']:
                for snk in data['snk']:
                    f.write(f'  "{src}" -> "{snk}";\n')
                    
        f.write('}\n')


def render_graphviz_json(scene: QGraphicsScene, json_path: str):
    """ Parses Graphviz -Tjson and renders to a single QGraphicsPathItem """
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    try:
        with open(os.path.expanduser("~/.silis_ui_settings.json")) as f:
            COLORS = json.load(f)
    except:
        COLORS = {}
        
    c_bg = QColor(COLORS.get("block", {}).get("background", "#282c34"))
    c_stroke = QColor(COLORS.get("nodes", {}).get("stroke", "#3e4451"))
    c_text_pri = QColor(COLORS.get("text", {}).get("primary", "#e6ebf2"))
    c_wire = QColor(COLORS.get("routing", {}).get("wire", "#d19a66"))

    wire_path = QPainterPath()
    box_path = QPainterPath()
    
    def process_draw_ops(ops, path_obj):
        for op in ops:
            if op['op'] == 'b':  # cubic b-spline
                pts = op['points']
                # Graphviz Y is inverted relative to PyQt!
                path_obj.moveTo(pts[0][0], -pts[0][1])
                i = 1
                while i + 2 < len(pts):
                    path_obj.cubicTo(pts[i][0], -pts[i][1], pts[i+1][0], -pts[i+1][1], pts[i+2][0], -pts[i+2][1])
                    i += 3
            elif op['op'] in ('P', 'p'):  # polygon / polyline
                pts = op['points']
                path_obj.moveTo(pts[0][0], -pts[0][1])
                for pt in pts[1:]:
                    path_obj.lineTo(pt[0], -pt[1])
                if op['op'] == 'P': path_obj.closeSubpath()
            elif op['op'] in ('e', 'E'):  # ellipse
                r = op['rect']
                path_obj.addEllipse(r[0]-r[2], -r[1]-r[3], r[2]*2, r[3]*2)
                
    # Parse Objects (Nodes)
    for obj in data.get("objects", []):
        process_draw_ops(obj.get("_draw_", []), box_path)
        
        # Draw Labels
        for op in obj.get("_ldraw_", []):
            if op['op'] == 'T':
                pt = op['pt']
                text = op['text']
                t_item = QGraphicsTextItem(text)
                t_item.setDefaultTextColor(c_text_pri)
                t_item.setFont(QFont("Consolas", 10))
                # Adjust position (Graphviz uses bottom-left or center, we need to center)
                t_item.setPos(pt[0] - t_item.boundingRect().width()/2, -pt[1] - t_item.boundingRect().height())
                scene.addItem(t_item)

    # Parse Edges
    for edge in data.get("edges", []):
        process_draw_ops(edge.get("_draw_", []), wire_path)
        process_draw_ops(edge.get("_hdraw_", []), wire_path) # Arrowheads
        
    # Add mega-paths to scene
    box_item = QGraphicsPathItem(box_path)
    box_item.setPen(QPen(c_stroke, 2))
    box_item.setBrush(c_bg)
    scene.addItem(box_item)
    
    wire_item = QGraphicsPathItem(wire_path)
    wire_item.setPen(QPen(c_wire, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    scene.addItem(wire_item)

