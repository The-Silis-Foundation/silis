"""
gds_snapshot.py
Ultra-fast, production-grade GDSII layout renderer for Silis EDA.
Uses gdstk + Pillow with exact instance transform matrices (rotation, reflection, origin).
Correctly places pad rings along perimeter and standard cells in the core.
"""

import os
import sys
import math
import warnings
import gdstk
from PIL import Image, ImageDraw

SKY130_COLORS = {
    64: (240, 100, 110),  # poly
    67: (0, 230, 255),    # li1
    68: (65, 145, 255),   # met1
    69: (255, 170, 50),   # met2
    70: (50, 220, 100),   # met3
    71: (200, 100, 255),  # met4
    72: (255, 110, 180),  # met5
}

LEGEND_LAYERS = [
    ("LI1", 67),
    ("Met1", 68),
    ("Met2", 69),
    ("Met3", 70),
    ("Met4", 71),
    ("Met5/BondPad", 72)
]


def _parse_def_routed_wires(def_path: str):
    """
    Extracts all detailed routed wire paths from Cadence DEF (NETS and SPECIALNETS)
    grouped by routing layer and thickness.
    """
    routes = []
    if not def_path or not os.path.isfile(def_path):
        return routes

    units = 1000.0
    current_layer = "met1"
    current_width = 0.48
    pts = []
    last_x, last_y = None, None
    in_nets = False

    try:
        with open(def_path, 'r', errors='ignore') as f:
            for line in f:
                line_s = line.strip()
                if line_s.startswith("UNITS DISTANCE MICRONS"):
                    parts = line_s.split()
                    if len(parts) >= 4 and parts[3].isdigit():
                        units = float(parts[3])
                    continue

                if line_s.startswith("NETS ") or line_s.startswith("SPECIALNETS "):
                    in_nets = True
                    continue
                if line_s.startswith("END NETS") or line_s.startswith("END SPECIALNETS"):
                    if len(pts) >= 2:
                        routes.append((current_layer, current_width, pts))
                    in_nets = False
                    pts = []
                    last_x, last_y = None, None
                    continue

                if not in_nets:
                    continue

                if "ROUTED" in line_s or "NEW" in line_s:
                    if len(pts) >= 2:
                        routes.append((current_layer, current_width, pts))
                    pts = []
                    last_x, last_y = None, None
                    parts = line_s.split()
                    for i, token in enumerate(parts):
                        if token in ["ROUTED", "NEW"] and i + 1 < len(parts):
                            current_layer = parts[i + 1].lower()
                            if i + 2 < len(parts) and parts[i + 2].replace('.', '', 1).isdigit():
                                current_width = float(parts[i + 2]) / units
                            else:
                                current_width = 0.48
                            break

                if line_s.startswith("-") or ";" in line_s:
                    if len(pts) >= 2:
                        routes.append((current_layer, current_width, pts))
                    pts = []
                    last_x, last_y = None, None

                if "(" in line_s:
                    raw_groups = line_s.split('(')
                    for group in raw_groups[1:]:
                        if ")" not in group:
                            continue
                        content = group.split(')')[0]
                        tokens = content.split()
                        # Strict 2-point wire coordinate (x, y) - ignore 4-token RECT deltas e.g. RECT ( -620 -150 0 150 )
                        if len(tokens) == 2 or (len(tokens) == 3 and tokens[2].isdigit()):
                            vx, vy = tokens[0], tokens[1]
                            x = last_x if vx == "*" else (float(vx) / units if vx.lstrip('-').replace('.', '', 1).isdigit() else None)
                            y = last_y if vy == "*" else (float(vy) / units if vy.lstrip('-').replace('.', '', 1).isdigit() else None)
                            if x is not None and y is not None:
                                pts.append((x, y))
                                last_x, last_y = x, y

        if len(pts) >= 2:
            routes.append((current_layer, current_width, pts))
    except Exception:
        pass

    return routes


def render_gds_snapshot(gds_path: str, out_png_path: str, canvas_width: int = 1200, pdk_name: str = "SkyWater 130nm", def_path: str = None) -> str:
    """
    Renders an accurate, high-speed PNG snapshot of a layout respecting reference orientations,
    macro structural functional blocks, and full DEF/GDS routing interconnect layers.
    """
    if not os.path.isfile(gds_path):
        raise FileNotFoundError(f"GDSII file not found: {gds_path}")

    # Silence C++ stderr record warnings (e.g. NODE/NODETYPE unsupported) and Python RuntimeWarning
    devnull_fd = None
    saved_stderr_fd = None
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        saved_stderr_fd = os.dup(2)
        os.dup2(devnull_fd, 2)
    except Exception:
        pass

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lib = gdstk.read_gds(gds_path)
    finally:
        if saved_stderr_fd is not None:
            try:
                os.dup2(saved_stderr_fd, 2)
                os.close(saved_stderr_fd)
            except Exception:
                pass
        if devnull_fd is not None:
            try:
                os.close(devnull_fd)
            except Exception:
                pass
    top_cells = lib.top_level()
    if not top_cells:
        raise ValueError(f"No top-level cells found in GDS: {gds_path}")

    top_cell = top_cells[0]
    bbox = top_cell.bounding_box()
    if not bbox:
        raise ValueError(f"Empty bounding box in top cell {top_cell.name}")

    (min_x, min_y), (max_x, max_y) = bbox
    width_um = max(1.0, max_x - min_x)
    height_um = max(1.0, max_y - min_y)

    margin = 40
    canvas_w = max(400, canvas_width)
    canvas_h = int(canvas_w * (height_um / width_um))
    canvas_h = max(200, min(2400, canvas_h))

    # Dark-mode EDA substrate
    img = Image.new("RGB", (canvas_w, canvas_h + 90), (20, 22, 32))
    draw = ImageDraw.Draw(img)

    # Coordinate transform scale factors
    sx = (canvas_w - 2 * margin) / width_um
    sy = (canvas_h - 2 * margin) / height_um
    ox = margin
    oy = canvas_h - margin

    # Coordinate Grid
    grid_step = max(50, int((canvas_w - 2 * margin) / 10))
    for gx in range(margin, canvas_w - margin, grid_step):
        draw.line([(gx, margin), (gx, canvas_h - margin)], fill=(35, 40, 55), width=1)
    for gy in range(margin, canvas_h - margin, grid_step):
        draw.line([(margin, gy), (canvas_w - margin, gy)], fill=(35, 40, 55), width=1)

    # Outer chip boundary outline
    draw.rectangle([margin - 2, margin - 2, canvas_w - margin + 2, canvas_h - margin + 2], outline=(255, 255, 255), width=2)

    # 1. Top-level routing metals and rings
    for poly in top_cell.polygons:
        lyr = poly.layer
        if lyr in SKY130_COLORS:
            color = SKY130_COLORS[lyr]
            pts = [(int((p[0] - min_x) * sx + ox), int(oy - (p[1] - min_y) * sy)) for p in poly.points]
            if len(pts) >= 3:
                draw.polygon(pts, fill=color)

    # 2. Subcell instances with proper transform matrix (rotation, x_reflection, origin)
    for ref in top_cell.references:
        c_name = ref.cell.name
        c_box = ref.cell.bounding_box()
        if not c_box:
            continue

        local_corners = [
            (c_box[0][0], c_box[0][1]),
            (c_box[1][0], c_box[0][1]),
            (c_box[1][0], c_box[1][1]),
            (c_box[0][0], c_box[1][1]),
        ]

        rot = ref.rotation
        x_refl = ref.x_reflection
        ox_ref, oy_ref = ref.origin

        world_pts = []
        for lx, ly in local_corners:
            if x_refl:
                ly = -ly
            wx = lx * math.cos(rot) - ly * math.sin(rot) + ox_ref
            wy = lx * math.sin(rot) + ly * math.cos(rot) + oy_ref
            px = int((wx - min_x) * sx + ox)
            py = int(oy - (wy - min_y) * sy)
            world_pts.append((px, py))

        is_macro = ("sram" in c_name.lower() or "macro" in c_name.lower() or len(ref.cell.polygons) > 500)

        is_filler = ("fill" in c_name.lower() or "slice" in c_name.lower())
        is_pad_or_corner = ("gpiov2" in c_name.lower() or "power" in c_name.lower() or "ground" in c_name.lower() or "corner" in c_name.lower()) and not is_filler

        if is_pad_or_corner:
            # Full pad boundary along outer perimeter
            draw.polygon(world_pts, fill=(28, 32, 48), outline=(255, 110, 180))
            # Bonding pad terminal only on actual pads (not on corner cells or tiny slices)
            if "corner" not in c_name.lower():
                center_x = (world_pts[0][0] + world_pts[2][0]) // 2
                center_y = (world_pts[0][1] + world_pts[2][1]) // 2
                bw = max(3, int(15 * sx))
                draw.rectangle([center_x - bw, center_y - bw, center_x + bw, center_y + bw], fill=(255, 110, 180), outline=(255, 255, 255))
        elif is_filler:
            # Subtle dark fill for abutment bus slices so they don't spawn white/pink placeholder boxes
            draw.polygon(world_pts, fill=(24, 26, 36), outline=(40, 46, 64))
        elif is_macro:
            # Macro dark background boundary with cyan border
            draw.polygon(world_pts, fill=(12, 16, 26), outline=(0, 230, 255), width=2)
            cos_r = math.cos(rot)
            sin_r = math.sin(rot)

            # 1. Render all hierarchical sub-blocks (memory banks, bitcell arrays, decoders, sense amps)
            macro_block_palette = [
                (30, 144, 255),   # Dodger blue (bitcell arrays)
                (50, 205, 50),    # Lime green (decoders)
                (255, 165, 0),    # Orange (sense amps)
                (186, 85, 211),   # Medium orchid (control logic)
                (255, 99, 71),    # Tomato (buffers)
                (0, 206, 209),    # Dark turquoise (I/O & precharge)
            ]
            color_map = {}
            c_idx = 0
            for sub in ref.cell.references:
                s_name = sub.cell.name
                s_box = sub.cell.bounding_box()
                if not s_box:
                    continue
                sub_ox, sub_oy = sub.origin
                sub_rot = sub.rotation
                sub_refl = sub.x_reflection
                sub_cos = math.cos(sub_rot)
                sub_sin = math.sin(sub_rot)

                sub_corners = [
                    (s_box[0][0], s_box[0][1]),
                    (s_box[1][0], s_box[0][1]),
                    (s_box[1][0], s_box[1][1]),
                    (s_box[0][0], s_box[1][1]),
                ]
                sub_world = []
                for slx, sly in sub_corners:
                    if sub_refl: sly = -sly
                    mx = slx * sub_cos - sly * sub_sin + sub_ox
                    my = slx * sub_sin + sly * sub_cos + sub_oy
                    if x_refl: my = -my
                    wx = mx * cos_r - my * sin_r + ox_ref
                    wy = mx * sin_r + my * cos_r + oy_ref
                    sub_world.append((int((wx - min_x) * sx + ox), int(oy - (wy - min_y) * sy)))

                prefix = s_name.split("_")[-2] if "_" in s_name else s_name
                if prefix not in color_map:
                    color_map[prefix] = macro_block_palette[c_idx % len(macro_block_palette)]
                    c_idx += 1
                draw.polygon(sub_world, outline=color_map[prefix])

            # 2. Render direct routing metal layers (Met1, Met2, Met3, Met4) on the macro
            VALID_DATATYPES = {0, 5, 20}
            for poly in ref.cell.polygons:
                if poly.datatype in VALID_DATATYPES and poly.layer in SKY130_COLORS:
                    color = SKY130_COLORS[poly.layer]
                    pts = []
                    for p in poly.points:
                        lx, ly = p[0], p[1]
                        if x_refl: ly = -ly
                        wx = lx * cos_r - ly * sin_r + ox_ref
                        wy = lx * sin_r + ly * cos_r + oy_ref
                        pts.append((int((wx - min_x) * sx + ox), int(oy - (wy - min_y) * sy)))
                    if len(pts) >= 3:
                        draw.polygon(pts, fill=color)
        else:
            # Core standard cells
            draw.polygon(world_pts, fill=(35, 42, 60), outline=(55, 75, 115))

    # 3. Render all actual routed wires from DEF if available or adjacent
    if not def_path:
        # Search adjacent def file
        gds_dir = os.path.dirname(os.path.abspath(gds_path))
        candidates = [
            os.path.join(gds_dir, f"{top_cell.name}.def"),
            os.path.join(gds_dir, "temp.def"),
            os.path.join(os.path.dirname(gds_dir), "results", "temp.def"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                def_path = c
                break

    if def_path and os.path.isfile(def_path):
        LAYER_TO_GDS = {
            "poly": 64,
            "li1": 67,
            "met1": 68,
            "met2": 69,
            "met3": 70,
            "met4": 71,
            "met5": 72,
        }
        routes = _parse_def_routed_wires(def_path)
        for lyr_name, width_um, pt_list in routes:
            gds_lyr = LAYER_TO_GDS.get(lyr_name, 68)
            color = SKY130_COLORS.get(gds_lyr, (65, 145, 255))
            line_w = max(1, int(width_um * sx))
            pts_canvas = []
            for wx, wy in pt_list:
                px = int((wx - min_x) * sx + ox)
                py = int(oy - (wy - min_y) * sy)
                pts_canvas.append((px, py))
            if len(pts_canvas) >= 2:
                draw.line(pts_canvas, fill=color, width=line_w)

    # Bottom Metadata and Layer Legend
    draw.line([(margin, canvas_h + 10), (canvas_w - margin, canvas_h + 10)], fill=(60, 65, 85), width=2)
    meta_text = (
        f"Cell: {top_cell.name}  |  PDK: {pdk_name}  |  "
        f"Die: {width_um:.1f}um x {height_um:.1f}um  |  "
        f"Instances: {len(top_cell.references)}"
    )
    draw.text((margin, canvas_h + 20), meta_text, fill=(240, 245, 255))

    lx = margin
    ly = canvas_h + 50
    for name, lyr in LEGEND_LAYERS:
        if lyr in SKY130_COLORS:
            draw.rectangle([lx, ly, lx + 16, ly + 16], fill=SKY130_COLORS[lyr], outline=(255, 255, 255))
            draw.text((lx + 24, ly + 2), f"{name} (L{lyr})", fill=(200, 205, 220))
            lx += 140

    os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
    img.save(out_png_path, "PNG")
    return os.path.abspath(out_png_path)
