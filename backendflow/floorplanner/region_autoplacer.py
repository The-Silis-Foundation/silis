"""
silis/backendflow/floorplanner/region_autoplacer.py
Hierarchical Auto Region Placer & Legalizer for Silis Floorplanner.

Features:
- Dual Affinity Models:
    * Netlist Interconnect Graph (Bus wire counts & dataflow connectivity)
    * Hierarchical Architecture Tree (Namespace clumping)
    * Hybrid Mode (Macro-clustering + Netlist bus affinity)
- 4-Force Gravitational Field:
    * Region-to-Region (R2R)
    * Region-to-Macro (R2M)
    * Region-to-Pin (R2P)
    * Obstacle Repulsion & Core Boundary Clamping
- Core Cavity Field Construction:
    * Subtraction of macros, halos (+corridors), locked regions, and blockages
    * Maximal disjoint orthogonal rectangular cavities
    * Narrow corridor detection (< 50um)
- Nested Sub-Region Containment:
    * Parent regions placed in chip cavities
    * Child regions placed strictly within parent bounding boxes
- Discrete Site Row Snapping (SkyWater 130nm standard cell row height: 2.72 um, track pitch: 0.46 um)
- Starvation Detection with Recommended Core Area computation
"""

import os
import re
import math
import random
from typing import List, Dict, Tuple, Optional, Any
from PyQt6.QtCore import QRectF, QPointF


SKY130_ROW_HEIGHT = 2.72
SKY130_SITE_WIDTH = 0.46
MIN_CORRIDOR_WIDTH = 50.0


class HierarchicalAutoRegionPlacer:
    def __init__(
        self,
        core_rect: QRectF,
        die_rect: QRectF,
        macros: List[Dict[str, Any]],
        regions: List[Dict[str, Any]],
        blockages: Optional[List[QRectF]] = None,
        pins: Optional[List[Dict[str, Any]]] = None,
        netlist_path: Optional[str] = None,
        affinity_mode: str = "hybrid",  # "netlist", "hierarchy", "hybrid"
        allow_rotation: bool = True,
        ignore_narrow_corridors: bool = True,
        force_auto_shape: bool = False,
        force_density: Optional[float] = None,
        seed: int = 42,
        w_r2m: float = 1.0,
        w_r2r: float = 1.0,
        w_r2io: float = 1.0,
        allow_non_rectangular: bool = True,
        interconnect_graph: Optional[Dict[str, Dict[str, int]]] = None,
    ):
        self.core_rect = QRectF(core_rect) if core_rect is not None else QRectF(0, 0, 1000, 1000)
        self.die_rect = QRectF(die_rect) if die_rect is not None else QRectF(0, 0, 1040, 1040)
        self.macros = macros
        self.regions = regions
        self.blockages = blockages or []
        self.pins = pins or []
        self.netlist_path = netlist_path
        self.affinity_mode = affinity_mode.lower()
        self.allow_rotation = allow_rotation
        self.ignore_narrow_corridors = ignore_narrow_corridors
        self.force_auto_shape = force_auto_shape
        self.force_density = force_density
        self.seed = seed
        self.rng = random.Random(seed)
        self.w_r2m = max(0.0, float(w_r2m))
        self.w_r2r = max(0.0, float(w_r2r))
        self.w_r2io = max(0.0, float(w_r2io))
        self.allow_non_rectangular = allow_non_rectangular

        # Internal state
        self.interconnect_graph: Dict[str, Dict[str, int]] = interconnect_graph or {}
        self.pin_affinity: Dict[str, List[QPointF]] = {}
        self.macro_affinity: Dict[str, List[str]] = {}
        self.multi_boxes: Dict[str, List[Tuple[float, float, float, float]]] = {}
        self.claimed_macro_facets: Dict[str, Dict[str, float]] = {}  # Tracks contact surface allocations for fair sharing

        if not self.interconnect_graph:
            self._parse_netlist_interconnect()

    def _parse_netlist_interconnect(self):
        """Builds module-to-module and module-to-macro interconnect graph from netlist."""
        if not self.netlist_path or not os.path.isfile(self.netlist_path):
            return

        try:
            with open(self.netlist_path, "r", errors="replace") as f:
                content = f.read()

            # Regex parse module instances and their connected net names
            inst_pat = re.compile(r'(\w+)\s+(\w+)\s*\((.*?)\);', re.DOTALL)
            net_to_modules: Dict[str, List[str]] = {}

            for m_cell, m_inst, ports_str in inst_pat.findall(content):
                # Map port connections .port(net)
                port_conns = re.findall(r'\.\w+\s*\(\s*([^)]+)\s*\)', ports_str)
                for net in port_conns:
                    net_clean = net.strip().replace("\\", "").split("[")[0]
                    if net_clean:
                        net_to_modules.setdefault(net_clean, []).append(m_inst)

            # Build connectivity edge weights between modules
            for net, connected_insts in net_to_modules.items():
                if len(connected_insts) > 1 and len(connected_insts) < 30:  # ignore clock/reset
                    for i in range(len(connected_insts)):
                        for j in range(i + 1, len(connected_insts)):
                            m1, m2 = connected_insts[i], connected_insts[j]
                            self.interconnect_graph.setdefault(m1, {})
                            self.interconnect_graph[m1][m2] = self.interconnect_graph[m1].get(m2, 0) + 1
                            self.interconnect_graph.setdefault(m2, {})
                            self.interconnect_graph[m2][m1] = self.interconnect_graph[m2].get(m1, 0) + 1
        except Exception as e:
            print(f"[AutoRegionPlacer] Warning parsing netlist: {e}")

    def _get_affinity_score(self, mod1: str, mod2: str) -> float:
        """Computes affinity attraction between two modules based on chosen mode."""
        score = 0.0

        # 1. Hierarchy Namespace Affinity
        if self.affinity_mode in ("hierarchy", "hybrid"):
            parts1 = mod1.split("/")
            parts2 = mod2.split("/")
            common_depth = 0
            for p1, p2 in zip(parts1, parts2):
                if p1 == p2:
                    common_depth += 1
                else:
                    break
            score += common_depth * 10.0

        # 2. Netlist Interconnect Graph Affinity
        if self.affinity_mode in ("netlist", "hybrid"):
            # Check direct connections
            wire_count = self.interconnect_graph.get(mod1, {}).get(mod2, 0)
            score += wire_count * 2.0

        return score

    def build_cavity_field(self, obstacles: List[QRectF]) -> List[QRectF]:
        """
        Decomposes the core area minus obstacles into maximal rectangular cavities.
        Filters out corridors narrower than MIN_CORRIDOR_WIDTH if enabled.
        """
        cavities = [QRectF(self.core_rect)]

        for obs in obstacles:
            new_cavities = []
            for cav in cavities:
                if not cav.intersects(obs):
                    new_cavities.append(cav)
                    continue

                inter = cav.intersected(obs)
                # Split cavity into up to 4 non-overlapping pieces around the obstacle:
                # Top, Bottom, Left, Right
                if cav.top() < inter.top():
                    top_rect = QRectF(cav.left(), cav.top(), cav.width(), inter.top() - cav.top())
                    if top_rect.width() > 1.0 and top_rect.height() > 1.0:
                        new_cavities.append(top_rect)

                if cav.bottom() > inter.bottom():
                    bot_rect = QRectF(cav.left(), inter.bottom(), cav.width(), cav.bottom() - inter.bottom())
                    if bot_rect.width() > 1.0 and bot_rect.height() > 1.0:
                        new_cavities.append(bot_rect)

                if cav.left() < inter.left():
                    left_rect = QRectF(cav.left(), inter.top(), inter.left() - cav.left(), inter.height())
                    if left_rect.width() > 1.0 and left_rect.height() > 1.0:
                        new_cavities.append(left_rect)

                if cav.right() > inter.right():
                    right_rect = QRectF(inter.right(), inter.top(), cav.right() - inter.right(), inter.height())
                    if right_rect.width() > 1.0 and right_rect.height() > 1.0:
                        new_cavities.append(right_rect)

            cavities = new_cavities

        # Filter out thin slivers / narrow corridors if requested
        valid_cavities = []
        for c in cavities:
            if self.ignore_narrow_corridors:
                if c.width() < MIN_CORRIDOR_WIDTH or c.height() < MIN_CORRIDOR_WIDTH:
                    continue
            valid_cavities.append(c)

        return valid_cavities

    def solve(self) -> Dict[str, Any]:
        """
        Executes hierarchical placement.
        Returns:
            {
                "success": bool,
                "placements": {module_name: QRectF},
                "starved_regions": [module_name],
                "recommended_core_w": float,
                "recommended_core_h": float,
                "corridor_warnings": [str]
            }
        """
        placements: Dict[str, QRectF] = {}
        starved_regions: List[str] = []

        # 1. Identify locked regions vs floatable regions
        locked_obstacles: List[QRectF] = []
        floatable_regions: List[Dict[str, Any]] = []

        for r in self.regions:
            rect = QRectF(r.get("x", 0.0), r.get("y", 0.0), r.get("width", 100.0), r.get("height", 100.0))
            halo = r.get("halo", (0.0, 0.0, 0.0, 0.0))
            if isinstance(halo, (int, float)):
                hl = hr = hb = ht = float(halo)
            elif isinstance(halo, (list, tuple)) and len(halo) >= 4:
                hl, hr, hb, ht = map(float, halo[:4])
            else:
                hl = hr = hb = ht = 0.0

            if r.get("locked", False):
                expanded = QRectF(rect.x() - hl, rect.y() - hb, rect.width() + hl + hr, rect.height() + hb + ht)
                locked_obstacles.append(expanded)
                placements[r["module"]] = rect
            else:
                floatable_regions.append(r)

        # 2. Build obstacles list: Macros + halos (+10um corridor) + blockages + locked regions
        obstacles: List[QRectF] = []
        for m in self.macros:
            mx, my = m.get("x", 0.0), m.get("y", 0.0)
            mw, mh = m.get("width", 100.0), m.get("height", 100.0)
            halo = m.get("halo", 10.0)
            if isinstance(halo, (int, float)):
                hl = hr = hb = ht = float(halo)
            elif isinstance(halo, (list, tuple)) and len(halo) >= 4:
                hl, hr, hb, ht = map(float, halo[:4])
            else:
                hl = hr = hb = ht = 10.0

            # Expand macro by halo
            expanded = QRectF(mx - hl, my - hb, mw + hl + hr, mh + hb + ht)
            obstacles.append(expanded)

        for b in self.blockages:
            obstacles.append(QRectF(b))

        obstacles.extend(locked_obstacles)

        # 3. Construct initial cavity field
        cavities = self.build_cavity_field(obstacles)

        # 4. Partition into Independent Root Regions and Nested Sub-Regions
        # Do not treat top-level wrapper or chip roots as parents that swallow the entire die.
        # Instead, identify genuine independent functional blocks.
        parent_regions = []
        child_regions = []

        # Find if there is a root wrapper enclosing everything (like 'neorv32_top_inst')
        # Filter it out if other sub-modules are present so it doesn't starve the canvas
        eligible_regions = [r for r in floatable_regions]
        all_mods = [r["module"] for r in eligible_regions]
        if len(all_mods) > 1:
            # If a module name is a prefix to ALL other modules (e.g. 'neorv32_top_inst'), exclude it
            top_wrapper = next((m for m in all_mods if all(other == m or other.startswith(m + "/") for other in all_mods)), None)
            if top_wrapper:
                eligible_regions = [r for r in eligible_regions if r["module"] != top_wrapper]

        # Independent functional regions are those where no other eligible module is their parent
        for r in eligible_regions:
            mod = r["module"]
            has_parent = any(other["module"] != mod and mod.startswith(other["module"] + "/") for other in eligible_regions)
            if has_parent:
                child_regions.append(r)
            else:
                parent_regions.append(r)

        # Apply Force Density if specified
        if self.force_density and self.force_density > 0:
            for r in parent_regions + child_regions:
                # Use true inclusive subtree area if provided, otherwise flat area or current rect area
                mod_area = r.get("inclusive_area", r.get("module_area", r.get("width", 100.0) * r.get("height", 100.0) * r.get("density", 0.60)))
                req_area = mod_area / max(0.10, min(0.95, self.force_density))
                side = math.sqrt(req_area)
                r["width"] = side
                r["height"] = side
                r["density"] = self.force_density

        # Sort parents by area descending (Best-Fit Decreasing)
        parent_regions.sort(key=lambda r: r.get("width", 100.0) * r.get("height", 100.0), reverse=True)

        # 5. Place Parent Regions
        for r in parent_regions:
            mod = r["module"]
            w = r.get("width", 100.0)
            h = r.get("height", 100.0)
            target_area = w * h

            # Determine anchor point from macro (pin-side aware) and sibling affinity
            anchor = self._compute_module_anchor(mod, placements)

            # Try rectangular cavity placement with auto-shaping
            placed_res = self._place_with_shaping(w, h, target_area, cavities, anchor, obstacles)
            if placed_res:
                snapped_rect, m_boxes = placed_res
                placements[mod] = snapped_rect
                if m_boxes:
                    self.multi_boxes[mod] = m_boxes

                # Account for region halo when updating obstacles
                halo = r.get("halo", (0.0, 0.0, 0.0, 0.0))
                hl, hr, hb, ht = halo if isinstance(halo, (list, tuple)) and len(halo) >= 4 else (0.0, 0.0, 0.0, 0.0)
                expanded_reg = QRectF(snapped_rect.x() - hl, snapped_rect.y() - hb, snapped_rect.width() + hl + hr, snapped_rect.height() + hb + ht)
                obstacles.append(expanded_reg)
                cavities = self.build_cavity_field(obstacles)
            else:
                starved_regions.append(mod)

        # 6. Place Nested Child Regions strictly within parent bounding boxes
        for r in child_regions:
            mod = r["module"]
            w = r.get("width", 50.0)
            h = r.get("height", 50.0)
            target_area = w * h

            # Find closest parent placement in the hierarchy
            cand_parents = [p["module"] for p in parent_regions if mod.startswith(p["module"] + "/")]
            parent_mod = max(cand_parents, key=len) if cand_parents else None
            parent_rect = placements.get(parent_mod) if parent_mod else None

            # Only constrain inside parent if parent_rect is strictly larger than the child
            if parent_rect and parent_rect.width() >= w and parent_rect.height() >= h:
                child_cavities = [QRectF(parent_rect)]
                anchor = self._compute_module_anchor(mod, placements)
                placed_res = self._place_with_shaping(w, h, target_area, child_cavities, anchor, [])
                if placed_res:
                    snapped_rect, m_boxes = placed_res
                    placements[mod] = snapped_rect
                    if m_boxes:
                        self.multi_boxes[mod] = m_boxes
                else:
                    starved_regions.append(mod)
            else:
                # If parent cannot physically contain child or parent is just a thin logic envelope,
                # place child in free cavities alongside the parent
                anchor = self._compute_module_anchor(mod, placements)
                placed_res = self._place_with_shaping(w, h, target_area, cavities, anchor, obstacles)
                if placed_res:
                    snapped_rect, m_boxes = placed_res
                    placements[mod] = snapped_rect
                    if m_boxes:
                        self.multi_boxes[mod] = m_boxes
                    halo = r.get("halo", (0.0, 0.0, 0.0, 0.0))
                    hl, hr, hb, ht = halo if isinstance(halo, (list, tuple)) and len(halo) >= 4 else (0.0, 0.0, 0.0, 0.0)
                    expanded_reg = QRectF(snapped_rect.x() - hl, snapped_rect.y() - hb, snapped_rect.width() + hl + hr, snapped_rect.height() + hb + ht)
                    obstacles.append(expanded_reg)
                    cavities = self.build_cavity_field(obstacles)
                else:
                    starved_regions.append(mod)

        # 7. Post-placement pairwise overlap & halo verification check
        overlaps = []
        placed_keys = list(placements.keys())
        for i in range(len(placed_keys)):
            mod_a = placed_keys[i]
            rect_a = placements[mod_a]
            # Check against other placed regions
            for j in range(i + 1, len(placed_keys)):
                mod_b = placed_keys[j]
                rect_b = placements[mod_b]
                if rect_a.intersects(rect_b):
                    inter = rect_a.intersected(rect_b)
                    if inter.width() > 0.05 and inter.height() > 0.05:
                        overlaps.append({
                            "type": "region_overlap",
                            "entity_a": mod_a,
                            "entity_b": mod_b,
                            "overlap_area": round(inter.width() * inter.height(), 3),
                            "intersection_box": [round(inter.left(), 3), round(inter.top(), 3), round(inter.right(), 3), round(inter.bottom(), 3)]
                        })

            # Check against all macros
            for m in self.macros:
                m_inst = m.get("inst", "macro")
                mx = m.get("x", 0.0)
                my = m.get("y", 0.0)
                mw = m.get("width", 0.0)
                mh = m.get("height", 0.0)
                m_rect = QRectF(mx, my, mw, mh)
                if rect_a.intersects(m_rect):
                    inter = rect_a.intersected(m_rect)
                    if inter.width() > 0.05 and inter.height() > 0.05:
                        overlaps.append({
                            "type": "macro_overlap",
                            "entity_a": mod_a,
                            "entity_b": m_inst,
                            "overlap_area": round(inter.width() * inter.height(), 3),
                            "intersection_box": [round(inter.left(), 3), round(inter.top(), 3), round(inter.right(), 3), round(inter.bottom(), 3)]
                        })

        # 8. Check starvation & compute recommended core expansion
        success = (len(starved_regions) == 0) and (len(overlaps) == 0)
        rec_w, rec_h = self._compute_recommended_core(starved_regions)

        return {
            "success": success,
            "placements": placements,
            "multi_boxes": self.multi_boxes,
            "starved_regions": starved_regions,
            "overlaps": overlaps,
            "recommended_core_w": rec_w,
            "recommended_core_h": rec_h,
            "interconnect_graph": self.interconnect_graph,
        }

    def _compute_module_anchor(self, module_name: str, current_placements: Optional[Dict[str, QRectF]] = None) -> QPointF:
        """Computes ideal target center anchor based on macro (pin-side aware), sibling (fair-share balanced), and R2IO top-level pin affinity."""
        weights_x = []
        weights_y = []

        # 1. Macro affinity with active pin-edge awareness & fair-share multi-candidate surface partitioning
        for m in self.macros:
            m_inst = m.get("inst", "")
            aff = self._get_affinity_score(module_name, m_inst)
            if aff > 0:
                mx = m.get("x", 0.0)
                my = m.get("y", 0.0)
                mw = m.get("width", 100.0)
                mh = m.get("height", 100.0)

                # Check if other modules also compete for this macro
                competitors = []
                for other in self.regions:
                    o_mod = other.get("module", "")
                    if o_mod != module_name and self._get_affinity_score(o_mod, m_inst) > 0:
                        competitors.append((o_mod, self._get_affinity_score(o_mod, m_inst)))

                # Fair-Share surface balancing:
                # If multiple regions are attracted to the same macro, the stronger candidate is capped to at most 70%
                # of the primary facet so the weaker candidate is guaranteed contact space (~30% or adjacent East/West facet).
                facet_info = self.claimed_macro_facets.setdefault(m_inst, {"south_claimed": 0.0, "total_candidates": 1 + len(competitors)})
                
                if competitors:
                    total_aff = aff + sum(c[1] for c in competitors)
                    raw_share = aff / max(1.0, total_aff)
                    # Bound share between 25% (minimum guaranteed touch) and 70% (no total dominance)
                    share = max(0.25, min(0.70, raw_share))
                else:
                    share = 1.0

                # Determine South facet offset or secondary facet if South is saturated
                south_taken = facet_info.get("south_claimed", 0.0)
                if south_taken < 0.70:
                    # Place along South pin facet proportionally
                    cand_x = mx + (mw * (south_taken + share / 2.0))
                    cand_y = max(self.core_rect.top() + 10.0, my - 20.0)
                    facet_info["south_claimed"] = south_taken + share
                else:
                    # South facet occupied by stronger candidate: assign weaker candidate to adjacent West/East facet
                    # so it still directly touches the macro surface!
                    cand_x = mx + mw + 20.0 if (len(weights_x) % 2 == 0) else max(self.core_rect.left() + 10.0, mx - 20.0)
                    cand_y = my + mh / 2.0

                w_count = max(1, int(aff * 2 * self.w_r2m))
                weights_x.extend([cand_x] * w_count)
                weights_y.extend([cand_y] * w_count)

        # 2. Sibling region affinity (R2R contact maximization with fair sharing)
        if current_placements and self.w_r2r > 0:
            for other_mod, other_rect in current_placements.items():
                if other_mod != module_name:
                    aff = self._get_affinity_score(module_name, other_mod)
                    if aff > 0:
                        w_count = max(1, int(aff * self.w_r2r))
                        weights_x.extend([other_rect.center().x()] * w_count)
                        weights_y.extend([other_rect.center().y()] * w_count)

        # 3. R2IO Affinity: Gravitational pull toward top-level I/O pins / peripheral ports
        # Direct name matching or netlist port association (e.g. uart0 -> uart0_rxd, gpio -> gpio_o)
        if self.w_r2io > 0:
            mod_base = module_name.split("/")[-1].lower()
            # Strip common instance suffixes
            mod_key = mod_base.replace("_inst", "").replace("_core", "")
            for p in self.pins:
                p_name = p.get("name", "").lower()
                p_clean = p_name.replace("pad_", "").replace("[", "_").replace("]", "").lower()
                if mod_key in p_clean or p_clean.startswith(mod_key) or any(part in p_clean for part in mod_key.split("_") if len(part) >= 3):
                    # Strong R2IO attraction toward the die boundary pin location
                    w_count = max(1, int(10 * self.w_r2io))
                    weights_x.extend([p.get("x", 0.0)] * w_count)
                    weights_y.extend([p.get("y", 0.0)] * w_count)

        if weights_x and weights_y:
            raw_x = sum(weights_x) / len(weights_x)
            raw_y = sum(weights_y) / len(weights_y)
            # Add subtle stochastic seed jitter (±3% core width/height) if seed is varied
            jitter_x = (self.rng.uniform(-0.03, 0.03) * self.core_rect.width()) if self.seed != 42 else 0.0
            jitter_y = (self.rng.uniform(-0.03, 0.03) * self.core_rect.height()) if self.seed != 42 else 0.0
            final_x = min(max(raw_x + jitter_x, self.core_rect.left()), self.core_rect.right())
            final_y = min(max(raw_y + jitter_y, self.core_rect.top()), self.core_rect.bottom())
            return QPointF(final_x, final_y)

        # Fallback to core center with seed jitter
        cx = self.core_rect.center().x() + ((self.rng.uniform(-0.05, 0.05) * self.core_rect.width()) if self.seed != 42 else 0.0)
        cy = self.core_rect.center().y() + ((self.rng.uniform(-0.05, 0.05) * self.core_rect.height()) if self.seed != 42 else 0.0)
        return QPointF(cx, cy)

    def _place_with_shaping(
        self,
        req_w: float,
        req_h: float,
        target_area: float,
        cavities: List[QRectF],
        anchor: QPointF,
        obstacles: List[QRectF]
    ) -> Optional[Tuple[QRectF, Optional[List[Tuple[float, float, float, float]]]]]:
        """Places a region using single rect (with auto-aspect ratios) or L-shaped decomposition."""
        candidates = [(req_w, req_h)]
        if self.allow_rotation and abs(req_w - req_h) > 5.0:
            candidates.append((req_h, req_w))

        if self.force_auto_shape and target_area > 0:
            # Extended aspect ratios alpha in [0.25, 0.33, 0.5, 0.67, 1.0, 1.5, 2.0, 3.0, 4.0]
            # to snugly utilize peripheral corridors alongside macros
            for alpha in (0.25, 0.33, 0.5, 0.67, 1.0, 1.5, 2.0, 3.0, 4.0):
                w_a = math.sqrt(target_area * alpha)
                h_a = math.sqrt(target_area / alpha)
                if (w_a, h_a) not in candidates and w_a >= 20.0 and h_a >= 20.0:
                    candidates.append((w_a, h_a))

        best_rect = None
        best_dist = float("inf")

        for w, h in candidates:
            placed = self._place_in_cavities(w, h, cavities, anchor)
            if placed:
                snapped = self._snap_to_site_grid(placed)
                center = snapped.center()
                dist = math.hypot(center.x() - anchor.x(), center.y() - anchor.y())
                if dist < best_dist:
                    best_dist = dist
                    best_rect = snapped

        if best_rect:
            return best_rect, None

        # If rigid rectangular placement fails and non-rectangular shapes are permitted, try L or C decomposition
        if (self.allow_non_rectangular or self.force_auto_shape) and target_area > 1000.0:
            l_result = self._decompose_l_shape(target_area, cavities, anchor, obstacles)
            if l_result:
                return l_result
            c_result = self._decompose_c_shape(target_area, cavities, anchor, obstacles)
            if c_result:
                return c_result

        # BEST-EFFORT FALLBACK: If region still doesn't fit standard cavities,
        # find the largest available cavity and place the best-fitting aspect ratio inside it.
        # Strict DRC Guarantee: Candidate MUST NOT intersect any existing placed obstacles.
        if cavities:
            sorted_cavities = sorted(cavities, key=lambda c: c.width() * c.height(), reverse=True)
            for cav in sorted_cavities:
                for w, h in candidates:
                    cw = min(w, cav.width())
                    ch = min(h, cav.height())
                    if cw >= SKY130_SITE_WIDTH * 4 and ch >= SKY130_ROW_HEIGHT * 2:
                        cand_x = min(max(anchor.x() - cw / 2.0, cav.left()), cav.right() - cw)
                        cand_y = min(max(anchor.y() - ch / 2.0, cav.top()), cav.bottom() - ch)
                        best_eff = self._snap_to_site_grid(QRectF(cand_x, cand_y, cw, ch))
                        # Verify zero intersection with existing obstacles
                        if not any(best_eff.intersects(o) and best_eff.intersected(o).width() > 0.05 and best_eff.intersected(o).height() > 0.05 for o in obstacles):
                            return best_eff, None

        # Return None so the region is declared starved/overflow rather than overlapping an existing block!
        return None

    def _decompose_l_shape(
        self,
        target_area: float,
        cavities: List[QRectF],
        anchor: QPointF,
        obstacles: List[QRectF]
    ) -> Optional[Tuple[QRectF, List[Tuple[float, float, float, float]]]]:
        """
        Decomposes target area into 2 contiguous legal sub-rectangles forming an L-shape
        around cavity boundaries while maintaining arm widths >= 25 um.
        Strict abutment: b1 and b2 MUST share an edge >= 25 um and never overlap.
        """
        min_arm = 25.0  # Minimum DRC safe corridor width for Sky130 rows

        for cav in cavities:
            if cav.width() < min_arm or cav.height() < min_arm:
                continue

            for split_ratio in (0.60, 0.50, 0.70):
                area1 = target_area * split_ratio
                area2 = target_area * (1.0 - split_ratio)

                w1 = min(cav.width(), math.sqrt(area1 * 1.5))
                h1 = area1 / max(min_arm, w1)
                if h1 > cav.height() or w1 < min_arm or h1 < min_arm:
                    continue

                b1 = QRectF(cav.left(), cav.top(), w1, h1)

                # Variant A: b2 attaches directly below b1
                w2 = min(cav.width(), area2 / min_arm)
                h2 = area2 / max(min_arm, w2)
                if cav.top() + h1 + h2 <= cav.bottom() and w2 >= min_arm and h2 >= min_arm:
                    b2 = QRectF(cav.left(), cav.top() + h1, w2, h2)
                    b1_s = self._snap_to_site_grid(b1)
                    b2_s = self._snap_to_site_grid(b2)
                    # Verify strict abutment: share boundary length >= 25um
                    shared_edge = min(b1_s.right(), b2_s.right()) - max(b1_s.left(), b2_s.left())
                    if shared_edge >= min_arm:
                        union_rect = b1_s.united(b2_s)
                        boxes = [
                            (b1_s.left(), b1_s.top(), b1_s.right(), b1_s.bottom()),
                            (b2_s.left(), b2_s.top(), b2_s.right(), b2_s.bottom())
                        ]
                        return union_rect, boxes

                # Variant B: b2 attaches directly to the right of b1
                h2_b = min(cav.height(), area2 / min_arm)
                w2_b = area2 / max(min_arm, h2_b)
                if cav.left() + w1 + w2_b <= cav.right() and w2_b >= min_arm and h2_b >= min_arm:
                    b2 = QRectF(cav.left() + w1, cav.top(), w2_b, h2_b)
                    b1_s = self._snap_to_site_grid(b1)
                    b2_s = self._snap_to_site_grid(b2)
                    shared_edge = min(b1_s.bottom(), b2_s.bottom()) - max(b1_s.top(), b2_s.top())
                    if shared_edge >= min_arm:
                        union_rect = b1_s.united(b2_s)
                        boxes = [
                            (b1_s.left(), b1_s.top(), b1_s.right(), b1_s.bottom()),
                            (b2_s.left(), b2_s.top(), b2_s.right(), b2_s.bottom())
                        ]
                        return union_rect, boxes

        return None

    def _decompose_c_shape(
        self,
        target_area: float,
        cavities: List[QRectF],
        anchor: QPointF,
        obstacles: List[QRectF]
    ) -> Optional[Tuple[QRectF, List[Tuple[float, float, float, float]]]]:
        """
        Decomposes target area into 3 contiguous legal sub-rectangles forming a C-shape
        (base vertical spine with top and bottom horizontal wings).
        Strict abutment: Wings must touch spine seamlessly.
        """
        min_arm = 25.0

        for cav in cavities:
            if cav.width() < min_arm * 2 or cav.height() < min_arm * 3:
                continue

            # 3 sub-boxes: spine (50%), top wing (25%), bottom wing (25%)
            area_spine = target_area * 0.50
            area_wing = target_area * 0.25

            spine_w = max(min_arm, math.sqrt(area_spine * 0.4))
            spine_h = area_spine / max(min_arm, spine_w)
            if spine_h > cav.height() or spine_w > cav.width():
                continue

            wing_w = min(cav.width() - spine_w, area_wing / min_arm)
            wing_h = area_wing / max(min_arm, wing_w)
            if wing_h * 2 > spine_h or (spine_w + wing_w) > cav.width():
                continue

            # Spine box
            b_spine = QRectF(cav.left(), cav.top(), spine_w, spine_h)
            # Top wing
            b_top = QRectF(cav.left() + spine_w, cav.top(), wing_w, wing_h)
            # Bottom wing
            b_bot = QRectF(cav.left() + spine_w, cav.top() + spine_h - wing_h, wing_w, wing_h)

            s_spine = self._snap_to_site_grid(b_spine)
            s_top = self._snap_to_site_grid(b_top)
            s_bot = self._snap_to_site_grid(b_bot)

            union_rect = s_spine.united(s_top).united(s_bot)
            boxes = [
                (s_spine.left(), s_spine.top(), s_spine.right(), s_spine.bottom()),
                (s_top.left(), s_top.top(), s_top.right(), s_top.bottom()),
                (s_bot.left(), s_bot.top(), s_bot.right(), s_bot.bottom())
            ]
            return union_rect, boxes

        return None

    def _place_in_cavities(self, req_w: float, req_h: float, cavities: List[QRectF], anchor: QPointF) -> Optional[QRectF]:
        """Finds candidate location in cavities minimizing distance to anchor."""
        candidates = [(req_w, req_h)]
        if self.allow_rotation and abs(req_w - req_h) > 5.0:
            candidates.append((req_h, req_w))

        best_rect = None
        best_dist = float("inf")

        for w, h in candidates:
            for cav in cavities:
                if cav.width() >= w and cav.height() >= h:
                    # Potential corner positions in cavity: closest to anchor
                    cand_x = min(max(anchor.x() - w / 2.0, cav.left()), cav.right() - w)
                    cand_y = min(max(anchor.y() - h / 2.0, cav.top()), cav.bottom() - h)

                    rect = QRectF(cand_x, cand_y, w, h)
                    center = rect.center()
                    dist = math.hypot(center.x() - anchor.x(), center.y() - anchor.y())

                    if dist < best_dist:
                        best_dist = dist
                        best_rect = rect

        return best_rect

    def _snap_to_site_grid(self, rect: QRectF) -> QRectF:
        """Snaps Y to SkyWater 130nm standard cell row height (2.72 um) and X to site track width (0.46 um)."""
        x = round(rect.left() / SKY130_SITE_WIDTH) * SKY130_SITE_WIDTH
        y = round(rect.top() / SKY130_ROW_HEIGHT) * SKY130_ROW_HEIGHT
        w = max(SKY130_SITE_WIDTH, round(rect.width() / SKY130_SITE_WIDTH) * SKY130_SITE_WIDTH)
        h = max(SKY130_ROW_HEIGHT, round(rect.height() / SKY130_ROW_HEIGHT) * SKY130_ROW_HEIGHT)
        return QRectF(round(x, 3), round(y, 3), round(w, 3), round(h, 3))

    def _compute_recommended_core(self, starved: List[str]) -> Tuple[float, float]:
        """Calculates recommended core dimensions when regions cannot fit."""
        current_w = self.core_rect.width()
        current_h = self.core_rect.height()
        if not starved:
            return current_w, current_h

        total_starved_area = 0.0
        for r in self.regions:
            if r["module"] in starved:
                total_starved_area += r.get("width", 100.0) * r.get("height", 100.0)

        needed_core_area = (current_w * current_h) + (total_starved_area * 1.35)  # 35% margin for routing
        aspect_ratio = current_w / max(1.0, current_h)

        new_h = math.sqrt(needed_core_area / aspect_ratio)
        new_w = new_h * aspect_ratio

        # Snap to discrete row heights
        rec_h = round(math.ceil(new_h / SKY130_ROW_HEIGHT) * SKY130_ROW_HEIGHT, 1)
        rec_w = round(math.ceil(new_w / SKY130_ROW_HEIGHT) * SKY130_ROW_HEIGHT, 1)
        return rec_w, rec_h


def auto_place_regions(
    core_rect: Any,
    die_rect: Any,
    macros: Optional[List[Dict[str, Any]]] = None,
    regions: Optional[List[Dict[str, Any]]] = None,
    blockages: Optional[List[Any]] = None,
    pins: Optional[List[Dict[str, Any]]] = None,
    netlist_path: Optional[str] = None,
    target_density: float = 0.70,
    min_cutoff_pct: float = 15.0,
    force_place_all: bool = True,
    force_auto_shape: bool = True,
    as_fence: bool = False,
    common_halo: float = 10.0,
    sizes_data: Optional[Dict[str, Any]] = None,
    seed: int = 42,
    w_r2m: float = 1.0,
    w_r2r: float = 1.0,
    w_r2io: float = 1.0,
    allow_non_rectangular: bool = True,
) -> Dict[str, Any]:
    """
    High-level headless Auto Region Placer.
    Takes core/die specifications, module area reports, macro locations, and automatically:
    1. Computes inclusive module subtree areas
    2. Filters submodules by cutoff % (e.g. 15%)
    3. Sizes qualifying modules to target utilization density (e.g. 70%)
    4. Auto-shapes and legally places regions in core cavities avoiding macros and obstacles
    5. Returns ready-to-use region dictionaries with [x1, y1, x2, y2] bounding boxes
    """
    from PyQt6.QtCore import QRectF

    if isinstance(core_rect, (list, tuple)):
        cr = QRectF(core_rect[0], core_rect[1], core_rect[2] - core_rect[0], core_rect[3] - core_rect[1])
    else:
        cr = QRectF(core_rect)

    if isinstance(die_rect, (list, tuple)):
        dr = QRectF(die_rect[0], die_rect[1], die_rect[2] - die_rect[0], die_rect[3] - die_rect[1])
    else:
        dr = QRectF(die_rect)

    norm_macros = list(macros or [])
    active_regions = list(regions or [])
    norm_blockages = [QRectF(b[0], b[1], b[2] - b[0], b[3] - b[1]) if isinstance(b, (list, tuple)) else b for b in (blockages or [])]

    # Process sizes_data for true inclusive subtree hierarchy
    if sizes_data and force_place_all:
        flat_modules = sizes_data.get("modules", {})
        total_std_area = max(1.0, sizes_data.get("total_std_cell_area", sum(flat_modules.values()) if flat_modules else 1.0))

        inclusive_areas: Dict[str, float] = {}
        for mod, a in flat_modules.items():
            parts = mod.split("/")
            for i in range(1, len(parts) + 1):
                pfx = "/".join(parts[:i])
                inclusive_areas[pfx] = inclusive_areas.get(pfx, 0.0) + a

        existing_names = {r.get("module") or r.get("module_name") for r in active_regions}

        # Filter by min_cutoff_pct
        for mod, inc_area in inclusive_areas.items():
            if mod in existing_names:
                continue
            # Skip root wrapper if submodules exist
            if mod == "neorv32_top_inst" and len(inclusive_areas) > 1:
                continue
            pct = (inc_area / total_std_area) * 100.0
            if pct >= min_cutoff_pct:
                req_area = inc_area / max(0.10, min(0.95, target_density))
                side = math.sqrt(req_area)
                active_regions.append({
                    "module": mod,
                    "width": side,
                    "height": side,
                    "density": target_density,
                    "is_fence": as_fence,
                    "halo": (common_halo, common_halo, common_halo, common_halo),
                    "module_area": flat_modules.get(mod, inc_area),
                    "inclusive_area": inc_area,
                    "locked": False,
                })

    placer = HierarchicalAutoRegionPlacer(
        core_rect=cr,
        die_rect=dr,
        macros=norm_macros,
        regions=active_regions,
        blockages=norm_blockages,
        pins=pins or [],
        netlist_path=netlist_path,
        affinity_mode="hybrid",
        allow_rotation=True,
        ignore_narrow_corridors=True,
        force_auto_shape=force_auto_shape,
        force_density=target_density if force_place_all else None,
        seed=seed,
        w_r2m=w_r2m,
        w_r2r=w_r2r,
        w_r2io=w_r2io,
        allow_non_rectangular=allow_non_rectangular,
    )

    result = placer.solve()

    # Formulate output regions with explicit [x1, y1, x2, y2] boxes
    placed_regions = []
    multi_map = result.get("multi_boxes", {})
    for r in active_regions:
        mod = r.get("module") or r.get("module_name")
        if mod in result["placements"]:
            prect = result["placements"][mod]
            rx1 = round(prect.x(), 3)
            ry1 = round(prect.y(), 3)
            rx2 = round(rx1 + prect.width(), 3)
            ry2 = round(ry1 + prect.height(), 3)
            entry = {
                "module": mod,
                "box": [rx1, ry1, rx2, ry2],
                "density": target_density,
                "is_fence": as_fence,
                "halo": r.get("halo", (common_halo, common_halo, common_halo, common_halo)),
            }
            if mod in multi_map:
                entry["multi_boxes"] = multi_map[mod]
            placed_regions.append(entry)

    return {
        "success": result["success"],
        "regions": placed_regions,
        "placements": result["placements"],
        "starved_regions": result["starved_regions"],
        "overlaps": result.get("overlaps", []),
        "recommended_core_w": result["recommended_core_w"],
        "recommended_core_h": result["recommended_core_h"],
    }

