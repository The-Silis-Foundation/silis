import sys

with open("blockdiagram.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.strip() == 'def parse_and_draw_json(scene, json_path, target_module, mode):':
        new_lines.append(line)
        continue
        
    if 'elif mode == "block":' in line:
        new_lines.append(line.replace('elif mode == "block":', 'elif mode in ("block", "gate"):'))
        continue
        
    if 'scene.addItem(in_boundary)' in line:
        new_lines.append(line.replace('scene.addItem(in_boundary)', 'if mode != "gate":\n                scene.addItem(in_boundary)'))
        continue
    if 'scene.addItem(out_boundary)' in line:
        new_lines.append(line.replace('scene.addItem(out_boundary)', 'if mode != "gate":\n                scene.addItem(out_boundary)'))
        continue
    
    if 'scene.addItem(block)' in line and 'blocks.append(block)' in lines[i-1]:
        new_lines.append(line.replace('scene.addItem(block)', 'if mode != "gate":\n                    scene.addItem(block)'))
        continue
        
    if 'def is_keepout_collision(x1, y1, x2, y2, ignore_pt=None, halo=20):' in line:
        new_lines.append(line)
        new_lines.append('                    if len(blocks) > 500: return False\n')
        continue
        
    if '# --- COLLISION DETECTION & SHOVE LOGIC ---' in line:
        new_lines.append(line)
        new_lines.append('                if len(blocks) > 500: continue\n')
        continue
        
    if 'if HAS_C_ROUTER and cached_rects:' in line:
        new_lines.append(line.replace('if HAS_C_ROUTER and cached_rects:', 'if HAS_C_ROUTER and cached_rects and len(segments) < 5000:'))
        continue
        
    if 'v_segs = [s for s in segments if s[\'type\'] == \'V\']' in line and '# --- STEP 3: Intersection & Junction Node Math ---' in lines[i-3]:
        new_lines.append('            if len(blocks) > 500: pass\n            else:\n                ' + line.lstrip())
        continue
        
    if '# --- STEP 4: Render Graphics ---' in line:
        new_lines.append(line)
        # INSERT SVG LOGIC HERE
        svg_logic = """
            if mode == "gate":
                import xml.sax.saxutils as saxutils
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
                        
                for src_key, data in _src_map_f.items():
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
                    f.write("\\n".join(svg_out))
                    
                from PyQt6.QtSvgWidgets import QGraphicsSvgItem
                svg_item = QGraphicsSvgItem(svg_path)
                scene.addItem(svg_item)
                return
"""
        new_lines.append(svg_logic)
        continue
        
    new_lines.append(line)

with open("blockdiagram.py", "w") as f:
    f.writelines(new_lines)

