"""
silis/core/sdk/spatial.py
Agentic EDA Spatial Reasoning & Packing Engine.

Implements high-performance in-memory spatial geometric reasoning:
1. get_empty_cavities(): Maximal open 2D rectilinear rectangular cavity calculation.
2. get_macro_pin_terminals(): Pin terminal inspection, center-of-gravity (COG) & dominant face analysis.
3. get_channel_metrics(): Routing track evaluation, row alignment, and DRC spacing legality.
4. simulate_floorplan_patch(): In-memory pre-flight floorplan patch mutation and verification in < 5ms.
"""

import os
import re
import glob
import time
from typing import Dict, List, Optional, Tuple, Any, Union

from .exceptions import DRCViolationError, OverlappingHaloError
from .floorplan import legalize_coord, snap_to_site_row, Halo, Orientation


class SpatialReasoningEngine:
    """
    In-memory geometric reasoning engine for macro placement, cavity exploration,
    channel track synthesis, and ultra-fast floorplan patch validation.
    """

    def __init__(self, pipeline):
        self.pipe = pipeline
        self.project = pipeline.project
        self._lef_cache: Dict[str, Dict[str, Any]] = {}

    # --------------------------------------------------------------------------
    # 1. Maximal Rectilinear Empty Rectangular Cavities
    # --------------------------------------------------------------------------
    def get_empty_cavities(
        self,
        min_w: float = 40.0,
        min_h: float = 40.0,
        core_box: Optional[Tuple[float, float, float, float]] = None,
        placed_macros: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculates maximal open 2D rectilinear empty rectangular cavities using interval subtraction.
        Takes core area and placed macro boxes (+ halo keepout).
        Returns list of cavity dicts: [{"box": [x1, y1, x2, y2], "width": w, "height": h, "area": a}, ...]
        filtered by min_w and min_h.
        """
        # Resolve core boundary
        if core_box is None:
            # 1. First check staged declarative FPS parameters (spec_floorplan)
            fps_fp = getattr(self.pipe, "_spec_fps", {}).get("floorplan", {})
            if fps_fp and fps_fp.get("die_area"):
                die = fps_fp["die_area"]
                margin = fps_fp.get("core_margin", 20.0)
                if isinstance(margin, (int, float)):
                    ml = mr = mb = mt = float(margin)
                elif isinstance(margin, (list, tuple)) and len(margin) == 4:
                    ml, mb, mr, mt = margin
                else:
                    ml = mr = mb = mt = 20.0
                core_box = (die[0] + ml, die[1] + mb, die[2] - mr, die[3] - mt)

            # 2. Next check project floorplan object
            if core_box is None:
                fp = self.project.get_floorplan() if hasattr(self.project, "get_floorplan") else None
                if fp and (fp.die_width > 0):
                    c = fp.get_core_bbox()
                    if c[2] > c[0] and c[3] > c[1]:
                        core_box = c

            # 3. Fallback to OpenDB
            if core_box is None:
                db_core = getattr(self.pipe.db, "core_area", (0.0, 0.0, 0.0, 0.0))
                if db_core[2] > db_core[0] and db_core[3] > db_core[1]:
                    core_box = db_core
                else:
                    core_box = (0.0, 0.0, 1000.0, 1000.0)

        cx1, cy1, cx2, cy2 = core_box
        free_rects: List[Tuple[float, float, float, float]] = [(cx1, cy1, cx2, cy2)]

        # Resolve placed macro boxes with halo
        macro_keepouts: List[Tuple[float, float, float, float]] = []
        if placed_macros is not None:
            raw_macros = placed_macros
        else:
            # Check staged declarative FPS macros first
            fps_fp = getattr(self.pipe, "_spec_fps", {}).get("floorplan", {})
            raw_macros = fps_fp.get("macros", []) if fps_fp else []

        if raw_macros:
            for m in raw_macros:
                box = m.get("box") or m.get("bbox")
                halo = m.get("halo", 0.0)
                if isinstance(halo, (int, float)):
                    hl = hr = hb = ht = float(halo)
                elif isinstance(halo, (list, tuple)) and len(halo) == 4:
                    hl, hb, hr, ht = halo
                else:
                    hl = hr = hb = ht = 0.0

                if box and len(box) == 4:
                    mx1, my1, mx2, my2 = box
                elif "x" in m and "y" in m and "width" in m and "height" in m:
                    mx1 = float(m["x"])
                    my1 = float(m["y"])
                    mx2 = mx1 + float(m["width"])
                    my2 = my1 + float(m["height"])
                elif "x" in m and "y" in m:
                    # Resolve width/height from master cell if available
                    mx1 = float(m["x"])
                    my1 = float(m["y"])
                    cell = m.get("master") or m.get("cell", "")
                    geom = self._resolve_macro_geometry(cell)
                    w = geom.get("width", 100.0)
                    h = geom.get("height", 100.0)
                    mx2 = mx1 + w
                    my2 = my1 + h
                else:
                    continue
                macro_keepouts.append((mx1 - hl, my1 - hb, mx2 + hr, my2 + ht))
        else:
            # Check floorplan object macros
            fp = self.project.get_floorplan() if hasattr(self.project, "get_floorplan") else None
            fp_macros = fp.get_macros() if fp else []
            if fp_macros:
                for inst in fp_macros:
                    macro_keepouts.append(inst.get_halo_bbox())
            else:
                # Query OpenDB instances
                db_res = self.pipe.db.inspect()
                for inst in db_res.get("instances", []):
                    if inst.get("is_macro"):
                        m_name = inst.get("name")
                        master = inst.get("master")
                        x = float(inst.get("x", 0.0))
                        y = float(inst.get("y", 0.0))
                        # Resolve macro width and height from LEF
                        macro_geom = self._resolve_macro_geometry(master)
                        w = macro_geom.get("width", 0.0)
                        h = macro_geom.get("height", 0.0)
                        macro_keepouts.append((x, y, x + w, y + h))

        # Iteratively subtract each macro keepout from free rectangles
        for kx1, ky1, kx2, ky2 in macro_keepouts:
            new_free: List[Tuple[float, float, float, float]] = []
            for rx1, ry1, rx2, ry2 in free_rects:
                # Intersection check
                ix1 = max(rx1, kx1)
                iy1 = max(ry1, ky1)
                ix2 = min(rx2, kx2)
                iy2 = min(ry2, ky2)
                if ix1 >= ix2 or iy1 >= iy2:
                    # No intersection, keep entire rectangle
                    new_free.append((rx1, ry1, rx2, ry2))
                    continue

                # Intersection exists: generate up to 4 maximal candidate slices
                if kx1 > rx1:
                    new_free.append((rx1, ry1, min(kx1, rx2), ry2))  # Left
                if kx2 < rx2:
                    new_free.append((max(kx2, rx1), ry1, rx2, ry2))  # Right
                if ky1 > ry1:
                    new_free.append((rx1, ry1, rx2, min(ky1, ry2)))  # Bottom
                if ky2 < ry2:
                    new_free.append((rx1, max(ky2, ry1), rx2, ry2))  # Top

            # Prune non-maximal rectangles (rectangles contained inside another)
            pruned: List[Tuple[float, float, float, float]] = []
            for i, r1 in enumerate(new_free):
                contained = False
                for j, r2 in enumerate(new_free):
                    if i != j:
                        if r2[0] <= r1[0] and r2[1] <= r1[1] and r2[2] >= r1[2] and r2[3] >= r1[3]:
                            if (r2[0], r2[1], r2[2], r2[3]) == (r1[0], r1[1], r1[2], r1[3]):
                                if i > j:
                                    contained = True
                                    break
                            else:
                                contained = True
                                break
                if not contained:
                    pruned.append(r1)
            free_rects = pruned

        # Filter by min_w and min_h, calculate area, format results
        cavities = []
        for rx1, ry1, rx2, ry2 in free_rects:
            w = round(rx2 - rx1, 3)
            h = round(ry2 - ry1, 3)
            if w >= min_w and h >= min_h:
                cavities.append({
                    "box": [round(rx1, 3), round(ry1, 3), round(rx2, 3), round(ry2, 3)],
                    "width": w,
                    "height": h,
                    "area": round(w * h, 3),
                })

        # Sort largest cavity first
        cavities.sort(key=lambda c: c["area"], reverse=True)
        return cavities

    # --------------------------------------------------------------------------
    # 2. Macro Pin Terminals & Center-of-Gravity (COG) Inspection
    # --------------------------------------------------------------------------
    def get_macro_pin_terminals(self, inst_name_or_master: str) -> Dict[str, Any]:
        """
        Inspects macro pin terminals via OpenDB / LEF.
        Calculates center-of-gravity (COG) of pin shapes relative to macro bounding box,
        and returns:
        {
            "macro": inst_name_or_master,
            "master": master_name,
            "width": float,
            "height": float,
            "dominant_face": "NORTH" | "SOUTH" | "EAST" | "WEST",
            "pin_count": int,
            "metal_layers": List[str],
            "pin_cog": [cog_x, cog_y],
            "pin_cog_normalized": [norm_x, norm_y]  # [0..1, 0..1]
        }
        """
        # Resolve master name and orientation if an instance name was passed
        master = inst_name_or_master
        orient = "R0"
        db_res = self.pipe.db.inspect()
        for inst in db_res.get("instances", []):
            if inst.get("name") == inst_name_or_master:
                master = inst.get("master", master)
                orient = inst.get("orient", "R0")
                break

        macro_data = self._resolve_macro_geometry(master)
        mw = macro_data.get("width", 0.0)
        mh = macro_data.get("height", 0.0)
        pins = macro_data.get("pins", {})
        layers = sorted(list(macro_data.get("layers", [])))

        total_x = 0.0
        total_y = 0.0
        pin_shape_count = 0

        for p_name, p_info in pins.items():
            for lay, rect in p_info.get("rects", []):
                rx1, ry1, rx2, ry2 = rect
                cx = (rx1 + rx2) / 2.0
                cy = (ry1 + ry2) / 2.0
                total_x += cx
                total_y += cy
                pin_shape_count += 1

        if pin_shape_count > 0:
            cog_x = round(total_x / pin_shape_count, 3)
            cog_y = round(total_y / pin_shape_count, 3)
        else:
            cog_x = round(mw / 2.0, 3)
            cog_y = round(mh / 2.0, 3)

        # Distances to the 4 edges of the un-oriented macro
        # SOUTH: y=0, NORTH: y=mh, WEST: x=0, EAST: x=mw
        d_south = cog_y
        d_north = mh - cog_y if mh > 0 else 0.0
        d_west = cog_x
        d_east = mw - cog_x if mw > 0 else 0.0

        face_dist = {
            "SOUTH": d_south,
            "NORTH": d_north,
            "WEST": d_west,
            "EAST": d_east,
        }
        dominant_face = min(face_dist, key=face_dist.get)

        norm_x = round(cog_x / mw, 4) if mw > 0 else 0.5
        norm_y = round(cog_y / mh, 4) if mh > 0 else 0.5

        return {
            "macro": inst_name_or_master,
            "master": master,
            "width": mw,
            "height": mh,
            "dominant_face": dominant_face,
            "pin_count": len(pins),
            "metal_layers": layers,
            "pin_cog": [cog_x, cog_y],
            "pin_cog_normalized": [norm_x, norm_y],
        }

    # --------------------------------------------------------------------------
    # 3. Channel Metrics & Corridor Legality Analysis
    # --------------------------------------------------------------------------
    def get_channel_metrics(
        self,
        inst_a: Union[str, Dict[str, Any]],
        inst_b: Union[str, Dict[str, Any]],
        min_channel_gap: float = 35.0,
        met2_pitch: float = 0.68,
        met3_pitch: float = 0.68,
        site_row_height: float = 2.72,
    ) -> Dict[str, Any]:
        """
        Calculates distance, routing tracks (met2/met3 pitch = 0.68/0.68 um in Sky130),
        row alignment (y % site_row_height == 0), and legality (gap >= min_channel_gap um).
        Returns:
        {
            "inst_a": str,
            "inst_b": str,
            "dx": float,
            "dy": float,
            "gap": float,
            "tracks_h": int,
            "tracks_v": int,
            "row_aligned": bool,
            "row_residuals": [float, float],
            "legal": bool,
            "deficit": float,
        }
        """
        box_a, y_a, name_a = self._resolve_instance_box_and_y(inst_a)
        box_b, y_b, name_b = self._resolve_instance_box_and_y(inst_b)

        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        # Distance between bounding boxes along X and Y
        # If separated: max(ax1, bx1) - min(ax2, bx2) > 0
        dist_x = max(0.0, max(ax1, bx1) - min(ax2, bx2))
        dist_y = max(0.0, max(ay1, by1) - min(ay2, by2))
        gap = round(max(dist_x, dist_y), 3)

        # Compute available routing tracks in the gap corridor
        # Horizontal tracks (typically met3 or met5, using met3_pitch)
        # Vertical tracks (typically met2 or met4, using met2_pitch)
        tracks_h = int(gap // met3_pitch) if met3_pitch > 0 else 0
        tracks_v = int(gap // met2_pitch) if met2_pitch > 0 else 0

        # Row alignment check
        rem_a = round(y_a % site_row_height, 3)
        rem_b = round(y_b % site_row_height, 3)
        # Tolerant of floating-point rounding (within 0.005 um)
        aligned_a = rem_a <= 0.005 or rem_a >= (site_row_height - 0.005)
        aligned_b = rem_b <= 0.005 or rem_b >= (site_row_height - 0.005)
        row_aligned = aligned_a and aligned_b

        # Legality: gap >= min_channel_gap
        legal = gap >= min_channel_gap
        deficit = round(max(0.0, min_channel_gap - gap), 3)

        return {
            "inst_a": name_a,
            "inst_b": name_b,
            "dx": round(dist_x, 3),
            "dy": round(dist_y, 3),
            "gap": gap,
            "tracks_h": tracks_h,
            "tracks_v": tracks_v,
            "row_aligned": row_aligned,
            "row_residuals": [rem_a, rem_b],
            "legal": legal,
            "deficit": deficit,
        }

    # --------------------------------------------------------------------------
    # 4. In-Memory Floorplan Patch Simulation (< 5ms)
    # --------------------------------------------------------------------------
    def simulate_floorplan_patch(
        self,
        mutations: List[Dict[str, Any]],
        halo_um: float = 5.0,
        min_channel_gap: float = 35.0,
        mfg_grid: float = 0.005,
        site_row_height: float = 2.72,
    ) -> Dict[str, Any]:
        """
        Takes proposed macro location changes:
          [{"inst": str, "loc": [x, y], "orient": str, "halo": optional}]
        Snaps to manufacturing grid (0.005 um) and row height (2.72 um), and runs
        pairwise halo non-overlap and channel checks entirely in memory in < 5ms
        without writing to disk or invoking OpenROAD.

        Returns:
        {
            "legal": bool,
            "elapsed_ms": float,
            "snapped_mutations": List[Dict[str, Any]],
            "violations": List[str],
            "overlaps": List[Tuple[str, str]],
            "channel_deficits": List[Dict[str, Any]],
        }
        """
        t0 = time.perf_counter()

        # Build current instance map from project floorplan or OpenDB
        existing_instances = self._get_current_macro_instances()

        # Apply mutations to the state copy
        snapped_mutations = []
        simulated_macros: Dict[str, Dict[str, Any]] = dict(existing_instances)

        for mut in mutations:
            inst_name = mut["inst"]
            raw_x, raw_y = mut["loc"]
            orient = mut.get("orient", "R0")

            # Snap to manufacturing grid and standard cell site row
            snapped_x = legalize_coord(raw_x, mfg_grid)
            snapped_y = snap_to_site_row(raw_y, site_row_height)

            # Determine macro dimensions
            master = mut.get("master")
            if not master and inst_name in simulated_macros:
                master = simulated_macros[inst_name]["master"]
            if not master:
                master = inst_name  # fallback

            geom = self._resolve_macro_geometry(master)
            w = geom.get("width", 100.0)
            h = geom.get("height", 100.0)

            # Handle orientation swapping width/height for R90, R270, etc.
            if orient in ("R90", "R270", "MX90", "MY90"):
                w, h = h, w

            halo = mut.get("halo", halo_um)
            if isinstance(halo, (int, float)):
                hl = hr = hb = ht = float(halo)
            elif isinstance(halo, (list, tuple)) and len(halo) == 4:
                hl, hb, hr, ht = halo
            else:
                hl = hr = hb = ht = halo_um

            snapped_data = {
                "name": inst_name,
                "master": master,
                "x": snapped_x,
                "y": snapped_y,
                "width": w,
                "height": h,
                "orient": orient,
                "halo": (hl, hb, hr, ht),
                "bbox": [snapped_x, snapped_y, round(snapped_x + w, 3), round(snapped_y + h, 3)],
                "halo_bbox": [
                    round(snapped_x - hl, 3),
                    round(snapped_y - hb, 3),
                    round(snapped_x + w + hr, 3),
                    round(snapped_y + h + ht, 3),
                ],
            }
            simulated_macros[inst_name] = snapped_data
            snapped_mutations.append({
                "inst": inst_name,
                "loc": [snapped_x, snapped_y],
                "orient": orient,
                "bbox": snapped_data["bbox"],
            })

        # Pairwise halo overlap & channel gap validation
        violations: List[str] = []
        overlaps: List[Tuple[str, str]] = []
        channel_deficits: List[Dict[str, Any]] = []

        macro_list = list(simulated_macros.values())
        num_macros = len(macro_list)

        for i in range(num_macros):
            ma = macro_list[i]
            ax1, ay1, ax2, ay2 = ma["halo_bbox"]
            body_ax1, body_ay1, body_ax2, body_ay2 = ma["bbox"]

            for j in range(i + 1, num_macros):
                mb = macro_list[j]
                bx1, by1, bx2, by2 = mb["halo_bbox"]
                body_bx1, body_by1, body_bx2, body_by2 = mb["bbox"]

                # 1. Halo collision check: BBox(A + HaloA) intersect BBox(B + HaloB)
                halo_overlap = not (ax2 <= bx1 or ax1 >= bx2 or ay2 <= by1 or ay1 >= by2)
                if halo_overlap:
                    overlaps.append((ma["name"], mb["name"]))
                    violations.append(
                        f"Overlapping halo between '{ma['name']}' and '{mb['name']}'"
                    )

                # 2. Channel corridor gap check between macro bodies
                dist_x = max(0.0, max(body_ax1, body_bx1) - min(body_ax2, body_bx2))
                dist_y = max(0.0, max(body_ay1, body_by1) - min(body_ay2, body_by2))
                spacing = max(dist_x, dist_y)

                if spacing < min_channel_gap:
                    deficit = round(min_channel_gap - spacing, 3)
                    channel_deficits.append({
                        "inst_a": ma["name"],
                        "inst_b": mb["name"],
                        "gap": round(spacing, 3),
                        "deficit": deficit,
                    })
                    violations.append(
                        f"Channel gap deficit between '{ma['name']}' and '{mb['name']}': "
                        f"gap {spacing:.3f} um < min {min_channel_gap:.3f} um (deficit: {deficit:.3f} um)"
                    )

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        legal = len(violations) == 0

        return {
            "legal": legal,
            "elapsed_ms": elapsed_ms,
            "snapped_mutations": snapped_mutations,
            "violations": violations,
            "overlaps": overlaps,
            "channel_deficits": channel_deficits,
        }

    # --------------------------------------------------------------------------
    # Helper Utilities (LEF Parsing & State Inspection)
    # --------------------------------------------------------------------------
    def _resolve_instance_box_and_y(self, inst_or_dict: Union[str, Dict[str, Any]]) -> Tuple[List[float], float, str]:
        """Extracts [x1, y1, x2, y2], y_origin, and name from an instance name or dict."""
        if isinstance(inst_or_dict, dict):
            name = inst_or_dict.get("name", "unknown")
            x = float(inst_or_dict.get("x", 0.0))
            y = float(inst_or_dict.get("y", 0.0))
            if "box" in inst_or_dict:
                return inst_or_dict["box"], y, name
            w = float(inst_or_dict.get("width", 0.0))
            h = float(inst_or_dict.get("height", 0.0))
            if w == 0.0 or h == 0.0:
                master = inst_or_dict.get("master", name)
                geom = self._resolve_macro_geometry(master)
                w = geom.get("width", w)
                h = geom.get("height", h)
            return [x, y, x + w, y + h], y, name

        inst_name = str(inst_or_dict)
        # Check floorplan object
        fp = self.project.get_floorplan() if hasattr(self.project, "get_floorplan") else None
        if fp and inst_name in fp.macros:
            m = fp.macros[inst_name]
            return list(m.get_bbox()), m.y, m.name

        # Check OpenDB
        db_res = self.pipe.db.inspect()
        for inst in db_res.get("instances", []):
            if inst.get("name") == inst_name:
                x = float(inst.get("x", 0.0))
                y = float(inst.get("y", 0.0))
                master = inst.get("master", "")
                geom = self._resolve_macro_geometry(master)
                w = geom.get("width", 0.0)
                h = geom.get("height", 0.0)
                return [x, y, x + w, y + h], y, inst_name

        return [0.0, 0.0, 0.0, 0.0], 0.0, inst_name

    def _get_current_macro_instances(self) -> Dict[str, Dict[str, Any]]:
        """Collects current macro instances from floorplan or OpenDB."""
        insts = {}
        fp = self.project.get_floorplan() if hasattr(self.project, "get_floorplan") else None
        if fp and fp.macros:
            for name, m in fp.macros.items():
                hl = m.halo.left
                hr = m.halo.right
                hb = m.halo.bottom
                ht = m.halo.top
                insts[name] = {
                    "name": name,
                    "master": m.master,
                    "x": m.x,
                    "y": m.y,
                    "width": m.width,
                    "height": m.height,
                    "orient": m.orientation.value,
                    "halo": (hl, hb, hr, ht),
                    "bbox": list(m.get_bbox()),
                    "halo_bbox": list(m.get_halo_bbox()),
                }
        else:
            db_res = self.pipe.db.inspect()
            for inst in db_res.get("instances", []):
                if inst.get("is_macro"):
                    name = inst.get("name")
                    master = inst.get("master", "")
                    x = float(inst.get("x", 0.0))
                    y = float(inst.get("y", 0.0))
                    orient = inst.get("orient", "R0")
                    geom = self._resolve_macro_geometry(master)
                    w = geom.get("width", 100.0)
                    h = geom.get("height", 100.0)
                    if orient in ("R90", "R270", "MX90", "MY90"):
                        w, h = h, w
                    hl = hr = hb = ht = 5.0
                    insts[name] = {
                        "name": name,
                        "master": master,
                        "x": x,
                        "y": y,
                        "width": w,
                        "height": h,
                        "orient": orient,
                        "halo": (hl, hb, hr, ht),
                        "bbox": [x, y, x + w, y + h],
                        "halo_bbox": [x - hl, y - hb, x + w + hr, y + h + ht],
                    }
        return insts

    def _resolve_macro_geometry(self, master_name: str) -> Dict[str, Any]:
        """Resolves size and pin terminals for a macro master from LEF files."""
        if master_name in self._lef_cache:
            return self._lef_cache[master_name]

        # Search for LEF files across project and PDK
        lef_files = []
        proj_root = getattr(self.project, "root_dir", "")
        if proj_root and os.path.isdir(proj_root):
            for d in [proj_root, os.path.join(proj_root, "source"), os.path.join(proj_root, "rtl"), os.path.join(proj_root, "constr")]:
                if os.path.isdir(d):
                    lef_files.extend(glob.glob(os.path.join(d, "*.lef")))

        pdk_base = os.environ.get("PDK_ROOT", os.path.expanduser("~/.silis/pdks"))
        if os.path.isdir(pdk_base):
            for pattern in ["sky130A/libs.ref/*/lef/*.lef", "sky130B/libs.ref/*/lef/*.lef"]:
                lef_files.extend(glob.glob(os.path.join(pdk_base, pattern)))

        # Also check project pdk_paths if present
        if hasattr(self.project, "pdk_paths") and isinstance(self.project.pdk_paths, dict):
            for pth in self.project.pdk_paths.values():
                if isinstance(pth, str) and pth.endswith(".lef") and os.path.isfile(pth):
                    lef_files.append(pth)

        for lef_path in set(lef_files):
            if not os.path.isfile(lef_path):
                continue
            with open(lef_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if f"MACRO {master_name}" not in content:
                continue

            # Extract macro block
            pattern = re.compile(rf"MACRO\s+{re.escape(master_name)}\b(.*?)\nEND\s+{re.escape(master_name)}\b", re.DOTALL)
            m = pattern.search(content)
            if not m:
                continue

            macro_text = m.group(1)
            # Find size
            size_m = re.search(r"SIZE\s+([\d\.\-]+)\s+BY\s+([\d\.\-]+)", macro_text)
            mw = float(size_m.group(1)) if size_m else 0.0
            mh = float(size_m.group(2)) if size_m else 0.0

            # Find pins
            pins = {}
            layers = set()
            pin_matches = re.finditer(r"PIN\s+(\S+)(.*?)END\s+\1", macro_text, re.DOTALL)
            for pm in pin_matches:
                p_name = pm.group(1)
                p_body = pm.group(2)
                cur_layer = ""
                p_rects = []
                for line in p_body.splitlines():
                    line = line.strip()
                    lm = re.match(r"^LAYER\s+(\S+)", line)
                    if lm:
                        cur_layer = lm.group(1)
                        layers.add(cur_layer)
                        continue
                    rm = re.match(r"^RECT\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)", line)
                    if rm:
                        rect = [float(rm.group(1)), float(rm.group(2)), float(rm.group(3)), float(rm.group(4))]
                        p_rects.append((cur_layer, rect))

                pins[p_name] = {"rects": p_rects}

            res = {
                "master": master_name,
                "width": mw,
                "height": mh,
                "pins": pins,
                "layers": sorted(list(layers)),
            }
            self._lef_cache[master_name] = res
            return res

        # Default fallback if master LEF was not found
        fallback = {
            "master": master_name,
            "width": 100.0,
            "height": 100.0,
            "pins": {},
            "layers": ["met2", "met3", "met4"],
        }
        self._lef_cache[master_name] = fallback
        return fallback
