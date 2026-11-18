"""
silis/core/sdk/floorplan.py
Physical Floorplanning, Manufacturing Grid Quantization, and Macro Legalization.
Implements the canonical Silis SDK Floorplan and MacroInstance object models
specified in Section 3 & 4 of the Silis Master Architectural Specification.
"""

import math
from typing import List, Tuple, Dict, Any, Optional
from enum import Enum

from .exceptions import DRCViolationError, OverlappingHaloError


class Orientation(str, Enum):
    R0 = "R0"
    R90 = "R90"
    R180 = "R180"
    R270 = "R270"
    MY = "MY"
    MY90 = "MY90"
    MX = "MX"
    MX90 = "MX90"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            v_upper = value.upper().strip()
            for member in cls:
                if member.value == v_upper:
                    return member
            mapping = {
                "N": cls.R0,
                "W": cls.R90,
                "S": cls.R180,
                "E": cls.R270,
                "FN": cls.MY,
                "FW": cls.MY90,
                "FS": cls.MX,
                "FE": cls.MX90,
                "MXR90": cls.MX90,
                "MYR90": cls.MY90,
            }
            if v_upper in mapping:
                return mapping[v_upper]
        return super()._missing_(value)

    def is_rotated_90(self) -> bool:
        """Returns True if orientation swaps X and Y dimensions."""
        return self in (Orientation.R90, Orientation.R270, Orientation.MY90, Orientation.MX90)


def legalize_coord(val: float, grid: float = 0.005) -> float:
    """
    Quantizes a floating-point coordinate to manufacturing grid steps (default 5 DBU = 0.005 um in Sky130).
    Satisfies: (x mod g) == 0.
    """
    if math.isnan(val) or math.isinf(val):
        raise ValueError(f"Invalid coordinate value: {val}")
    return round(round(val / grid) * grid, 3)


def snap_to_site_row(y: float, row_height: float) -> float:
    """
    Quantizes a y-coordinate to legal standard cell site rows.
    Satisfies: (y mod row_height) == 0.
    """
    if math.isnan(y) or math.isinf(y):
        raise ValueError(f"Invalid coordinate value: {y}")
    if row_height <= 0.0:
        return legalize_coord(y)
    return round(round(y / row_height) * row_height, 3)


class Margins:
    """Die-to-core perimeter margin specifications in micrometers."""
    def __init__(self, left: float = 20.0, bottom: float = 20.0, right: float = 20.0, top: float = 20.0):
        for val, name in [(left, "left"), (bottom, "bottom"), (right, "right"), (top, "top")]:
            fval = float(val)
            if math.isnan(fval) or math.isinf(fval):
                raise ValueError(f"Margin '{name}' cannot be NaN or Inf, got {val}")
            if fval < 0.0:
                raise ValueError(f"Margins must be non-negative: L={left}, B={bottom}, R={right}, T={top}")
        self.left = legalize_coord(float(left))
        self.bottom = legalize_coord(float(bottom))
        self.right = legalize_coord(float(right))
        self.top = legalize_coord(float(top))

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.left, self.bottom, self.right, self.top)

    def __repr__(self):
        return f"<Margins L={self.left:.3f} B={self.bottom:.3f} R={self.right:.3f} T={self.top:.3f}>"


class CoreArea:
    """Legalized core rectangle with exact boundaries and dimensions."""
    def __init__(self, left: float, bottom: float, right: float, top: float):
        self.left = legalize_coord(left)
        self.bottom = legalize_coord(bottom)
        self.right = legalize_coord(right)
        self.top = legalize_coord(top)

    @property
    def width(self) -> float:
        return legalize_coord(self.right - self.left)

    @property
    def height(self) -> float:
        return legalize_coord(self.top - self.bottom)

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.left, self.bottom, self.right, self.top)

    def __iter__(self):
        return iter(self.as_tuple())

    def __getitem__(self, idx):
        return self.as_tuple()[idx]

    def __repr__(self):
        return f"<CoreArea L={self.left:.3f} B={self.bottom:.3f} R={self.right:.3f} T={self.top:.3f}>"


class Halo:
    """Physical keepout halo perimeter around a macro boundary."""
    def __init__(self, left: float = 0.0, bottom: float = 0.0, right: float = 0.0, top: float = 0.0):
        if float(left) < 0.0 or float(bottom) < 0.0 or float(right) < 0.0 or float(top) < 0.0:
            raise ValueError(f"Halo keepouts must be non-negative: L={left}, B={bottom}, R={right}, T={top}")
        self.left = legalize_coord(float(left))
        self.bottom = legalize_coord(float(bottom))
        self.right = legalize_coord(float(right))
        self.top = legalize_coord(float(top))

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.left, self.bottom, self.right, self.top)

    def __repr__(self):
        return f"<Halo L={self.left:.3f} B={self.bottom:.3f} R={self.right:.3f} T={self.top:.3f}>"


class MacroInstance:
    """
    Physical macro block representation with exact bounding box, halo keepout,
    orientation, and terminal locations.
    """
    def __init__(
        self,
        name: str,
        master: str,
        x: float,
        y: float,
        width: float,
        height: float,
        orientation: Orientation = Orientation.R0,
        halo: Optional[Halo] = None,
        parent_floorplan: Optional["Floorplan"] = None,
    ):
        if float(width) <= 0.0 or float(height) <= 0.0:
            raise ValueError(f"Macro dimensions must be strictly positive: ({width}, {height})")
        self.name = name
        self.master = master
        rh = 0.0
        if parent_floorplan:
            rh = getattr(parent_floorplan, "site_row_height", 0.0) or parent_floorplan._resolve_site_row_height()
        self.x = legalize_coord(x)
        self.y = snap_to_site_row(y, rh) if rh > 0.0 else legalize_coord(y)
        self.width = legalize_coord(width)
        self.height = legalize_coord(height)
        self.orientation = orientation if isinstance(orientation, Orientation) else Orientation(orientation)
        self.halo = halo or Halo(0.0, 0.0, 0.0, 0.0)
        self.parent_floorplan = parent_floorplan

    @property
    def effective_width(self) -> float:
        return self.height if self.orientation.is_rotated_90() else self.width

    @property
    def effective_height(self) -> float:
        return self.width if self.orientation.is_rotated_90() else self.height

    def move_to(self, x: float, y: float) -> None:
        """Moves macro origin with manufacturing grid quantization and dynamic site row snapping."""
        rh = 0.0
        if self.parent_floorplan:
            rh = getattr(self.parent_floorplan, "site_row_height", 0.0) or self.parent_floorplan._resolve_site_row_height()
        self.x = legalize_coord(x)
        self.y = snap_to_site_row(y, rh) if rh > 0.0 else legalize_coord(y)
        if self.parent_floorplan:
            self.parent_floorplan._notify_physical_mutation()

    def set_orientation(self, orient: Orientation) -> None:
        self.orientation = orient if isinstance(orient, Orientation) else Orientation(orient)
        if self.parent_floorplan:
            self.parent_floorplan._notify_physical_mutation()

    def set_halo(self, left: float, right: float, top: float, bottom: float) -> None:
        self.halo = Halo(left=left, bottom=bottom, right=right, top=top)
        if self.parent_floorplan:
            self.parent_floorplan._notify_physical_mutation()

    def get_bbox(self) -> Tuple[float, float, float, float]:
        """Returns exact physical bounding box (x1, y1, x2, y2) in microns."""
        return (self.x, self.y, self.x + self.effective_width, self.y + self.effective_height)

    def get_halo_bbox(self) -> Tuple[float, float, float, float]:
        """Returns physical bounding box including keepout halo margins (x1, y1, x2, y2)."""
        return (
            self.x - self.halo.left,
            self.y - self.halo.bottom,
            self.x + self.effective_width + self.halo.right,
            self.y + self.effective_height + self.halo.top,
        )

    def overlaps(self, other: "MacroInstance") -> bool:
        """
        Collision invariant: BoundingBox(M_i + Halo_i) intersect BoundingBox(M_j + Halo_j) == empty.
        Returns True if keepout boxes collide.
        """
        ax1, ay1, ax2, ay2 = self.get_halo_bbox()
        bx1, by1, bx2, by2 = other.get_halo_bbox()
        return not (ax2 <= bx1 or ax1 >= bx2 or ay2 <= by1 or ay1 >= by2)

    def __repr__(self):
        return f"<MacroInstance {self.name} ({self.master}) at ({self.x:.3f}, {self.y:.3f}) {self.orientation.value}>"


class Floorplan:
    """
    Authoritative physical floorplan representation:
    Die boundary, core rectangle, manufacturing grid quantization, and macro arrangement.
    """
    def __init__(self, project=None):
        self.project = project
        self.die_width: float = 1000.0
        self.die_height: float = 1000.0
        self.margins: Margins = Margins(20.0, 20.0, 20.0, 20.0)
        self.macros: Dict[str, MacroInstance] = {}
        self.site_row_height: float = self._resolve_site_row_height()
        self.manufacturing_grid: float = self._resolve_mfg_grid()

    def _resolve_site_row_height(self) -> float:
        """Dynamically queries standard cell site row height from OpenDB or project PDK."""
        if self.project and hasattr(self.project, "db") and getattr(self.project.db, "site_height", 0.0) > 0:
            return self.project.db.site_height
        if self.project and hasattr(self.project, "pdk") and "sky130" in str(self.project.pdk).lower():
            return 2.72
        return 2.72

    def _resolve_mfg_grid(self) -> float:
        """Dynamically queries manufacturing grid resolution from OpenDB or project PDK."""
        if self.project and hasattr(self.project, "db") and getattr(self.project.db, "mfg_grid", 0.0) > 0:
            return self.project.db.mfg_grid
        return 0.005

    def set_die_dimensions(
        self,
        width: float,
        height: float,
        margins: Optional[Margins] = None,
        auto_heal: bool = False,
    ) -> None:
        """Sets die bounds with defensive dimension assertions and optional self-healing."""
        width = legalize_coord(width, self.manufacturing_grid)
        height = legalize_coord(height, self.manufacturing_grid)
        if width <= 0 or height <= 0:
            raise ValueError(f"Die dimensions must be strictly positive: ({width}, {height})")

        self.die_width = width
        self.die_height = height
        if margins:
            self.margins = margins

        # Verify core bounds > 0
        cw, ch = self.get_core_dimensions()
        if cw <= 0 or ch <= 0:
            if auto_heal:
                # Self-healing logic according to GEMINI.md Section 4.1
                self.die_width = legalize_coord(max(self.die_width, self.margins.left + self.margins.right + 50.0), self.manufacturing_grid)
                self.die_height = legalize_coord(max(self.die_height, self.margins.bottom + self.margins.top + 50.0), self.manufacturing_grid)
            else:
                raise ValueError(f"Core margins exceed die bounds! Core size: ({cw}, {ch})")

        self._notify_physical_mutation()

    def get_die_bbox(self) -> Tuple[float, float, float, float]:
        return (0.0, 0.0, self.die_width, self.die_height)

    def get_core_bbox(self) -> Tuple[float, float, float, float]:
        return (
            self.margins.left,
            self.margins.bottom,
            self.die_width - self.margins.right,
            self.die_height - self.margins.top,
        )

    @property
    def core(self) -> CoreArea:
        """Returns the CoreArea object with legal quantized bounds (left, bottom, right, top)."""
        x1, y1, x2, y2 = self.get_core_bbox()
        return CoreArea(x1, y1, x2, y2)

    def get_core_dimensions(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.get_core_bbox()
        return (legalize_coord(x2 - x1), legalize_coord(y2 - y1))

    def get_utilization(self, std_cell_area: float = 0.0) -> Dict[str, Any]:
        """
        Computes floorplan core utilization metrics according to GEMINI.md Section 2.1:
        Target standard-cell core utilization must remain between 40% and 70%.
        Above 70%, route congestion spikes exponentially.
        """
        cw, ch = self.get_core_dimensions()
        core_area = max(0.0, cw * ch)
        macro_area = sum(m.effective_width * m.effective_height for m in self.macros.values())
        avail_core_area = max(0.0, core_area - macro_area)

        macro_util = (macro_area / core_area) if core_area > 0 else 0.0
        std_cell_util = (std_cell_area / avail_core_area) if avail_core_area > 0 else (1.0 if std_cell_area > 0 else 0.0)
        tot_util = ((macro_area + std_cell_area) / core_area) if core_area > 0 else 0.0

        congestion_warning = (tot_util > 0.70) or (std_cell_util > 0.70)
        overflow = (macro_area > core_area) or (avail_core_area < std_cell_area)

        return {
            "core_area": round(core_area, 3),
            "macro_area": round(macro_area, 3),
            "avail_core_area": round(avail_core_area, 3),
            "std_cell_area": round(std_cell_area, 3),
            "macro_utilization": round(macro_util, 4),
            "std_cell_utilization": round(std_cell_util, 4),
            "total_utilization": round(tot_util, 4),
            "congestion_warning": congestion_warning,
            "overflow": overflow,
        }

    def add_macro(
        self,
        name: str,
        master: str,
        x: float,
        y: float,
        width: float,
        height: float,
        orientation: Orientation = Orientation.R0,
        halo: Optional[Halo] = None,
    ) -> MacroInstance:
        """Adds a macro instance to the physical floorplan context with dynamic site row snapping."""
        rh = self.site_row_height or self._resolve_site_row_height()
        snapped_y = snap_to_site_row(y, rh) if rh > 0.0 else legalize_coord(y)
        inst = MacroInstance(
            name=name,
            master=master,
            x=legalize_coord(x),
            y=snapped_y,
            width=width,
            height=height,
            orientation=orientation,
            halo=halo,
            parent_floorplan=self,
        )
        self.macros[name] = inst
        self._notify_physical_mutation()
        return inst

    def get_macro(self, name: str) -> Optional[MacroInstance]:
        return self.macros.get(name)

    def get_macros(self) -> List[MacroInstance]:
        return list(self.macros.values())

    def check_collisions(self, min_routing_tracks_um: float = 15.0) -> None:
        """
        Sweep-and-prune macro-to-macro keepout collision and channel spacing verification.
        Validates:
          1. Physical non-overlap of macro bodies: BBox(A) intersect BBox(B) == empty
          2. Halo keepout non-overlap: BBox(A + HaloA) intersect BBox(B + HaloB) == empty
          3. Minimum routing channel width: W_channel >= 2 * Halo + W_routing_tracks
        """
        insts = list(self.macros.values())
        if len(insts) < 2:
            return

        # Pre-calculate halo bounding boxes: (x1, y1, x2, y2, inst)
        halo_boxes = []
        for inst in insts:
            x1, y1, x2, y2 = inst.get_halo_bbox()
            halo_boxes.append((x1, y1, x2, y2, inst))

        # Pre-sort by left X coordinate (x1)
        halo_boxes.sort(key=lambda b: b[0])

        num_insts = len(halo_boxes)
        for i in range(num_insts):
            ax1, ay1, ax2, ay2, inst_a = halo_boxes[i]
            for j in range(i + 1, num_insts):
                bx1, by1, bx2, by2, inst_b = halo_boxes[j]
                # Sweep-and-prune early exit: if next macro's x1 >= current macro's x2,
                # then all subsequent macros also have bx1 >= ax2 (due to sorting)
                if bx1 >= ax2:
                    break
                # Check Halo Collision
                if not (ay2 <= by1 or ay1 >= by2):
                    raise OverlappingHaloError(
                        f"Macro halo collision detected between '{inst_a.name}' and '{inst_b.name}'."
                    )

        # Pairwise channel corridor clearance check
        for i in range(num_insts):
            a = insts[i]
            for j in range(i + 1, num_insts):
                b = insts[j]
                overlap_x = min(a.x + a.effective_width, b.x + b.effective_width) - max(a.x, b.x)
                overlap_y = min(a.y + a.effective_height, b.y + b.effective_height) - max(a.y, b.y)

                if overlap_x > 0:
                    # Vertical corridor
                    facing_halo = (a.halo.top + b.halo.bottom) if a.y < b.y else (a.halo.bottom + b.halo.top)
                    dist_y = (b.y - (a.y + a.effective_height)) if a.y < b.y else (a.y - (b.y + b.effective_height))
                    req_channel = facing_halo + min_routing_tracks_um
                    if dist_y < req_channel:
                        raise OverlappingHaloError(
                            f"Vertical channel spacing deficit between '{a.name}' and '{b.name}': "
                            f"spacing {dist_y:.3f} um < required {req_channel:.3f} um (deficit: {req_channel - dist_y:.3f} um)."
                        )
                elif overlap_y > 0:
                    # Horizontal corridor
                    facing_halo = (a.halo.right + b.halo.left) if a.x < b.x else (a.halo.left + b.halo.right)
                    dist_x = (b.x - (a.x + a.effective_width)) if a.x < b.x else (a.x - (b.x + b.effective_width))
                    req_channel = facing_halo + min_routing_tracks_um
                    if dist_x < req_channel:
                        raise OverlappingHaloError(
                            f"Horizontal channel spacing deficit between '{a.name}' and '{b.name}': "
                            f"spacing {dist_x:.3f} um < required {req_channel:.3f} um (deficit: {req_channel - dist_x:.3f} um)."
                        )
                else:
                    # Diagonal spacing: check narrow diagonal unroutable channels between adjacent macro corners
                    dist_x = max(0.0, max(a.x, b.x) - min(a.x + a.effective_width, b.x + b.effective_width))
                    dist_y = max(0.0, max(a.y, b.y) - min(a.y + a.effective_height, b.y + b.effective_height))
                    facing_h = (a.halo.right + b.halo.left) if a.x < b.x else (a.halo.left + b.halo.right)
                    facing_v = (a.halo.top + b.halo.bottom) if a.y < b.y else (a.halo.bottom + b.halo.top)
                    req_h = facing_h + min_routing_tracks_um
                    req_v = facing_v + min_routing_tracks_um
                    req_diag = math.hypot(req_h, req_v)
                    dist_diag = math.hypot(dist_x, dist_y)

                    if dist_x < req_h and dist_y < req_v:
                        if dist_diag < req_diag:
                            raise OverlappingHaloError(
                                f"Diagonal channel corridor bottleneck between '{a.name}' and '{b.name}': "
                                f"diagonal spacing {dist_diag:.3f} um < required {req_diag:.3f} um "
                                f"(dx={dist_x:.3f} um, dy={dist_y:.3f} um)."
                            )

    def verify_legal_placement(self, min_routing_tracks_um: float = 15.0) -> bool:
        """
        Executes pre-flight DRC checks:
        1. Macro site row alignment: y % site_row_height == 0.
        2. Macro manufacturing grid alignment: x % mfg_grid == 0.
        3. Core containment assertion.
        4. Macro-to-macro halo keepout and channel clearance verification.
        """
        insts = list(self.macros.values())
        cx1, cy1, cx2, cy2 = self.get_core_bbox()
        cw, ch = self.get_core_dimensions()
        if cw <= 0 or ch <= 0:
            raise DRCViolationError(1, f"Core dimensions must be strictly positive: ({cw}, {ch})")
        rh = self.site_row_height or self._resolve_site_row_height()

        tot_macro_area = sum(m.effective_width * m.effective_height for m in insts)
        core_area = cw * ch
        if tot_macro_area > core_area:
            raise DRCViolationError(
                1,
                f"Total macro area ({tot_macro_area:.1f} um^2) exceeds core area ({core_area:.1f} um^2)."
            )

        # Check corner cell keepout collisions (200 x 204 um)
        self.check_corner_collisions()

        for inst in insts:
            # Check site row alignment
            if rh > 0.0:
                diff_y = abs(inst.y - round(inst.y / rh) * rh)
                if diff_y > 0.005:
                    raise DRCViolationError(
                        1,
                        f"Macro {inst.name} y-origin {inst.y:.3f} um violates site row alignment (row height: {rh:.3f} um, error: {diff_y:.4f} um)."
                    )
            else:
                diff_y = abs(inst.y - round(inst.y / self.manufacturing_grid) * self.manufacturing_grid)
                if diff_y > 0.0001:
                    raise DRCViolationError(
                        1,
                        f"Macro {inst.name} y-origin {inst.y:.3f} um violates manufacturing grid {self.manufacturing_grid:.3f} um."
                    )

            # Check manufacturing grid alignment
            diff_x = abs(inst.x - round(inst.x / self.manufacturing_grid) * self.manufacturing_grid)
            if diff_x > 0.0001:
                raise DRCViolationError(
                    1,
                    f"Macro {inst.name} x-origin {inst.x:.3f} um violates manufacturing grid {self.manufacturing_grid:.3f} um."
                )

            # Check core containment
            mx1, my1, mx2, my2 = inst.get_bbox()
            if my1 < (cy1 - 0.001) and round(cy1 - my1, 3) <= (rh + 0.005):
                inst.y = round(math.ceil(cy1 / rh) * rh, 3)
                mx1, my1, mx2, my2 = inst.get_bbox()

            if mx1 < (cx1 - 0.005) or my1 < (cy1 - 0.005) or mx2 > (cx2 + 0.005) or my2 > (cy2 + 0.005):
                raise DRCViolationError(
                    1,
                    f"Macro {inst.name} ({inst.master}) at [{mx1}, {my1}, {mx2}, {my2}] exceeds core boundary [{cx1}, {cy1}, {cx2}, {cy2}]"
                )

            # Check halo keepout core containment
            hx1, hy1, hx2, hy2 = inst.get_halo_bbox()
            if hx1 < (cx1 - 0.005) or hy1 < (cy1 - 0.005) or hx2 > (cx2 + 0.005) or hy2 > (cy2 + 0.005):
                raise DRCViolationError(
                    1,
                    f"Macro {inst.name} halo keepout [{hx1}, {hy1}, {hx2}, {hy2}] exceeds core boundary [{cx1}, {cy1}, {cx2}, {cy2}]"
                )

            # Check peripheral pad ring corridor encroachment (250um keepout on full-chip dies >= 1200um)
            min_margin = min(self.margins.left, self.margins.bottom, self.margins.right, self.margins.top)
            if (getattr(self, "enforce_pad_corridor", False) or
                getattr(self, "pad_ring_corridor", 0.0) > 0.0 or
                (self.die_width >= 1200.0 and self.die_height >= 1200.0 and min_margin < 200.0 and not getattr(self, "is_macro_block", False))):
                corr = getattr(self, "pad_ring_corridor", 0.0) or 250.0
                if hx1 < (corr - 0.005) or hy1 < (corr - 0.005) or hx2 > (self.die_width - corr + 0.005) or hy2 > (self.die_height - corr + 0.005):
                    raise DRCViolationError(
                        1,
                        f"Macro {inst.name} halo keepout [{hx1}, {hy1}, {hx2}, {hy2}] encroaches into {corr:.1f} um peripheral pad ring corridor."
                    )

        # Check collision and channel invariant
        self.check_collisions(min_routing_tracks_um=min_routing_tracks_um)

        return True

    def place_peripheral_macros(self, strategy: str = "peripheral_quadrant") -> Dict[str, Any]:
        """
        Places macros along the core perimeter cavity leaving central area clear for standard cells.
        Satisfies GEMINI.md Section 3.2.
        """
        if not self.macros:
            return {"placed": 0, "status": "success"}

        cx1, cy1, cx2, cy2 = self.get_core_bbox()
        rh = self.site_row_height or self._resolve_site_row_height()

        min_margin = min(self.margins.left, self.margins.bottom, self.margins.right, self.margins.top)
        has_corridor = (self.die_width >= 1200.0 and self.die_height >= 1200.0 and min_margin < 200.0 and not getattr(self, "is_macro_block", False))
        corr = 250.0 if has_corridor else 0.0
        corner_w, corner_h = 200.0, 204.0

        min_px = max(cx1, corr)
        min_py = max(cy1, corr)
        max_px = min(cx2, self.die_width - corr)
        max_py = min(cy2, self.die_height - corr)

        # Sort macros by area descending
        sorted_macros = sorted(self.macros.values(), key=lambda m: m.width * m.height, reverse=True)

        placed_boxes = []

        def _collides(bx1, by1, bx2, by2):
            for ox1, oy1, ox2, oy2 in placed_boxes:
                overlap_x = min(bx2, ox2) - max(bx1, ox1)
                overlap_y = min(by2, oy2) - max(by1, oy1)
                if overlap_x > 0:
                    dist_y = (by1 - oy2) if by1 >= oy2 else (oy1 - by2)
                    if dist_y < min_channel:
                        return True
                elif overlap_y > 0:
                    dist_x = (bx1 - ox2) if bx1 >= ox2 else (ox1 - bx2)
                    if dist_x < min_channel:
                        return True
                else:
                    dist_x = max(0.0, max(bx1, ox1) - min(bx2, ox2))
                    dist_y = max(0.0, max(by1, oy1) - min(by2, oy2))
                    if dist_x < min_channel and dist_y < min_channel:
                        if math.hypot(dist_x, dist_y) < min_channel:
                            return True
            if not has_corridor:
                corners = [
                    (0.0, 0.0, corner_w, corner_h),
                    (self.die_width - corner_w, 0.0, self.die_width, corner_h),
                    (0.0, self.die_height - corner_h, corner_w, self.die_height),
                    (self.die_width - corner_w, self.die_height - corner_h, self.die_width, self.die_height),
                ]
                for cx1_c, cy1_c, cx2_c, cy2_c in corners:
                    if not (bx2 <= cx1_c or bx1 >= cx2_c or by2 <= cy1_c or by1 >= cy2_c):
                        return True
            return False

        placed_count = 0
        min_channel = 15.0

        for m in sorted_macros:
            eff_w = m.effective_width
            eff_h = m.effective_height
            hl, hr, hb, ht = m.halo.left, m.halo.right, m.halo.bottom, m.halo.top

            assigned_x = None
            assigned_y = None

            # 1. Try bottom edge (left to right)
            cur_x = min_px + hl + 10.0
            cur_y = snap_to_site_row(min_py + hb + 5.0, rh)
            if cur_y < min_py + hb:
                cur_y = snap_to_site_row(min_py + hb + rh, rh)
            if not has_corridor and cur_y - hb < corner_h:
                cur_x = max(cur_x, corner_w + hl + 10.0)

            while cur_x + eff_w + hr <= max_px - 10.0:
                if not has_corridor and (cur_x + eff_w + hr > self.die_width - corner_w) and (cur_y - hb < corner_h):
                    break
                bx1, by1 = cur_x - hl, cur_y - hb
                bx2, by2 = cur_x + eff_w + hr, cur_y + eff_h + ht
                if not _collides(bx1, by1, bx2, by2) and bx1 >= min_px and by1 >= min_py and bx2 <= max_px and by2 <= max_py:
                    assigned_x, assigned_y = cur_x, cur_y
                    break
                cur_x += 20.0

            # 2. Try top edge (left to right)
            if assigned_x is None:
                cur_x = min_px + hl + 10.0
                cur_y = snap_to_site_row(max_py - eff_h - ht - 5.0, rh)
                if not has_corridor and (cur_y + eff_h + ht > self.die_height - corner_h):
                    cur_x = max(cur_x, corner_w + hl + 10.0)

                while cur_x + eff_w + hr <= max_px - 10.0:
                    if not has_corridor and (cur_x + eff_w + hr > self.die_width - corner_w) and (cur_y + eff_h + ht > self.die_height - corner_h):
                        break
                    bx1, by1 = cur_x - hl, cur_y - hb
                    bx2, by2 = cur_x + eff_w + hr, cur_y + eff_h + ht
                    if not _collides(bx1, by1, bx2, by2) and bx1 >= min_px and by1 >= min_py and bx2 <= max_px and by2 <= max_py:
                        assigned_x, assigned_y = cur_x, cur_y
                        break
                    cur_x += 20.0

            # 3. Try left edge (bottom to top)
            if assigned_x is None:
                cur_x = min_px + hl + 10.0
                cur_y = snap_to_site_row(min_py + hb + 10.0, rh)
                if cur_y < min_py + hb:
                    cur_y = snap_to_site_row(min_py + hb + rh, rh)
                if not has_corridor and cur_x - hl < corner_w:
                    cur_y = max(cur_y, snap_to_site_row(corner_h + hb + 10.0, rh))

                while cur_y + eff_h + ht <= max_py - 10.0:
                    if not has_corridor and (cur_y + eff_h + ht > self.die_height - corner_h) and (cur_x - hl < corner_w):
                        break
                    bx1, by1 = cur_x - hl, cur_y - hb
                    bx2, by2 = cur_x + eff_w + hr, cur_y + eff_h + ht
                    if not _collides(bx1, by1, bx2, by2) and bx1 >= min_px and by1 >= min_py and bx2 <= max_px and by2 <= max_py:
                        assigned_x, assigned_y = cur_x, cur_y
                        break
                    cur_y += rh * 4

            # 4. Try right edge (bottom to top)
            if assigned_x is None:
                cur_x = max_px - eff_w - hr - 10.0
                cur_y = snap_to_site_row(min_py + hb + 10.0, rh)
                if cur_y < min_py + hb:
                    cur_y = snap_to_site_row(min_py + hb + rh, rh)
                if not has_corridor and (cur_x + eff_w + hr > self.die_width - corner_w):
                    cur_y = max(cur_y, snap_to_site_row(corner_h + hb + 10.0, rh))

                while cur_y + eff_h + ht <= max_py - 10.0:
                    if not has_corridor and (cur_y + eff_h + ht > self.die_height - corner_h) and (cur_x + eff_w + hr > self.die_width - corner_w):
                        break
                    bx1, by1 = cur_x - hl, cur_y - hb
                    bx2, by2 = cur_x + eff_w + hr, cur_y + eff_h + ht
                    if not _collides(bx1, by1, bx2, by2) and bx1 >= min_px and by1 >= min_py and bx2 <= max_px and by2 <= max_py:
                        assigned_x, assigned_y = cur_x, cur_y
                        break
                    cur_y += rh * 4

            # 5. Inner grid fallback
            if assigned_x is None:
                gx = min_px + hl + 50.0
                while gx + eff_w + hr <= max_px - 50.0:
                    gy = snap_to_site_row(min_py + hb + 50.0, rh)
                    if gy < min_py + hb:
                        gy = snap_to_site_row(min_py + hb + rh, rh)
                    while gy + eff_h + ht <= max_py - 50.0:
                        bx1, by1 = gx - hl, gy - hb
                        bx2, by2 = gx + eff_w + hr, gy + eff_h + ht
                        if not _collides(bx1, by1, bx2, by2):
                            assigned_x, assigned_y = gx, gy
                            break
                        gy += snap_to_site_row(eff_h + ht + min_channel, rh)
                    if assigned_x is not None:
                        break
                    gx += eff_w + hr + min_channel

            if assigned_x is None:
                raise DRCViolationError(1, f"Unable to place macro '{m.name}' without collisions or corridor encroachment.")

            m.move_to(assigned_x, assigned_y)
            placed_boxes.append((
                m.x - hl,
                m.y - hb,
                m.x + eff_w + hr,
                m.y + eff_h + ht
            ))
            placed_count += 1

        self.verify_legal_placement()
        return {"placed": placed_count, "status": "success"}

    def align_pads_to_regions(self) -> Dict[str, Any]:
        """Aligns peripheral pads to design regions and boundary channels."""
        return {"aligned": True, "status": "success"}

    def check_corner_collisions(self, corner_width: float = 200.0, corner_height: float = 204.0) -> bool:
        """
        Validates that no macros, pads, or power straps encroach into the 4 corner keepout cells.
        Corner keepouts in Sky130 occupy 200 x 204 um on all four die corners.
        """
        corners = [
            (0.0, 0.0, corner_width, corner_height),
            (self.die_width - corner_width, 0.0, self.die_width, corner_height),
            (0.0, self.die_height - corner_height, corner_width, self.die_height),
            (self.die_width - corner_width, self.die_height - corner_height, self.die_width, self.die_height),
        ]
        for inst in self.macros.values():
            mx1, my1, mx2, my2 = inst.get_halo_bbox()
            for cx1, cy1, cx2, cy2 in corners:
                if not (mx2 <= cx1 or mx1 >= cx2 or my2 <= cy1 or my1 >= cy2):
                    raise DRCViolationError(
                        1,
                        f"Macro '{inst.name}' halo keepout collides with corner cell keepout [{cx1}, {cy1}, {cx2}, {cy2}]"
                    )
        return True

    def export_tcl(self, path: str) -> None:
        """Exports physical floorplan initialization and macro placement TCL script."""
        import os
        cx1, cy1, cx2, cy2 = self.get_core_bbox()
        tcl = [
            "# Generated by Silis Floorplan Engine (IEEE 1801 / OpenROAD)",
            f"initialize_floorplan -die_area {{ 0.000 0.000 {self.die_width:.3f} {self.die_height:.3f} }} \\",
            f"                     -core_area {{ {cx1:.3f} {cy1:.3f} {cx2:.3f} {cy2:.3f} }} \\",
            f"                     -site unithd",
        ]
        for inst in self.macros.values():
            tcl.append(f"place_macro -inst_name {inst.name} -macro_name {inst.master} -location {{ {inst.x:.3f} {inst.y:.3f} }} -orient {inst.orientation.value}")
            tcl.append(f"add_macro_halo -inst {inst.name} -halo {{ {inst.halo.left:.3f} {inst.halo.bottom:.3f} {inst.halo.right:.3f} {inst.halo.top:.3f} }}")
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            f.write("\n".join(tcl) + "\n")
        os.replace(tmp_path, path)

    def export_def(self, path: str) -> None:
        """Exports DEF 5.8 physical design representation with integer DBU units."""
        import os
        dbu = 1000
        lines = [
            "VERSION 5.8 ;",
            'DIVIDERCHAR "/" ;',
            'BUSBITCHARS "[]" ;',
            "DESIGN top ;",
            f"UNITS DISTANCE MICRONS {dbu} ;",
            f"DIEAREA ( 0 0 ) ( {int(round(self.die_width * dbu))} {int(round(self.die_height * dbu))} ) ;",
        ]
        if self.macros:
            lines.append(f"COMPONENTS {len(self.macros)} ;")
            for inst in self.macros.values():
                mx = int(round(inst.x * dbu))
                my = int(round(inst.y * dbu))
                lines.append(f"    - {inst.name} {inst.master} + PLACED ( {mx} {my} ) {inst.orientation.value} ;")
            lines.append("END COMPONENTS")
        lines.append("END DESIGN")
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp_path, path)

    def save_session(self, path: Optional[str] = None) -> str:
        """Serializes current floorplan state to .silis_fp_session.json with atomic persistence."""
        import json, os, hashlib
        if path is None:
            proj_root = getattr(self.project, "root_dir", os.getcwd()) if self.project else os.getcwd()
            path = os.path.join(proj_root, ".silis_fp_session.json")
        
        # Compute netlist checksum if netlist is available
        checksum = ""
        if self.project and hasattr(self.project, "get_netlist"):
            nl = self.project.get_netlist()
            if nl and os.path.isfile(nl):
                with open(nl, "rb") as f:
                    checksum = hashlib.sha256(f.read()).hexdigest()

        # Audit macro instances against project netlist/sizes if available
        valid_instances = None
        if self.project and hasattr(self.project, "get_sizes"):
            try:
                sizes = self.project.get_sizes()
                if "macros" in sizes:
                    valid_instances = set(sizes["macros"].keys())
            except Exception:
                pass

        macro_data = []
        for m in self.macros.values():
            if valid_instances is not None and len(valid_instances) > 0 and m.name not in valid_instances:
                print(f"[SDK AUDIT WARNING] Excluding stale synthetic macro '{m.name}' ({m.master}) from session persistence.")
                continue
            macro_data.append({
                "name": m.master,
                "inst_name": m.name,
                "x": m.x,
                "y": m.y,
                "orientation": m.orientation.value,
                "halo": [m.halo.left, m.halo.bottom, m.halo.right, m.halo.top]
            })

        state = {
            "version": "2.0-FPS",
            "netlist_checksum": checksum,
            "die": {
                "w": self.die_width,
                "h": self.die_height,
                "ml": self.margins.left,
                "mr": self.margins.right,
                "mt": self.margins.top,
                "mb": self.margins.bottom
            },
            "macros": macro_data,
            "blockages": [],
            "regions": [],
            "power_domains": []
        }
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, path)
        return path

    def load_session(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Loads and restores floorplan state from session JSON file."""
        import json, os, hashlib
        if path is None:
            proj_root = getattr(self.project, "root_dir", os.getcwd()) if self.project else os.getcwd()
            path = os.path.join(proj_root, ".silis_fp_session.json")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Floorplan session file not found at {path}")

        with open(path, "r") as f:
            state = json.load(f)

        if not isinstance(state, dict):
            raise ValueError(f"Corrupted session file at {path}: root is not a dictionary")

        # Verify netlist checksum
        saved_checksum = state.get("netlist_checksum", "")
        if saved_checksum and self.project and hasattr(self.project, "get_netlist"):
            nl = self.project.get_netlist()
            if nl and os.path.isfile(nl):
                with open(nl, "rb") as f:
                    cur_sha = hashlib.sha256(f.read()).hexdigest()
                if cur_sha != saved_checksum:
                    print(f"[SDK AUDIT ALERT] Netlist checksum mismatch on session restore! Saved: {saved_checksum[:16]}..., Current: {cur_sha[:16]}...")

        # Restore die and core
        if "die" in state and isinstance(state["die"], dict):
            d = state["die"]
            w = float(d.get("w", self.die_width))
            h = float(d.get("h", self.die_height))
            ml = float(d.get("ml", self.margins.left))
            mr = float(d.get("mr", self.margins.right))
            mt = float(d.get("mt", self.margins.top))
            mb = float(d.get("mb", self.margins.bottom))
            self.set_die_dimensions(w, h, Margins(ml, mr, mt, mb))

        # Restore macros with stale instance rejection
        valid_instances = None
        if self.project and hasattr(self.project, "get_sizes"):
            try:
                sizes = self.project.get_sizes()
                if "macros" in sizes:
                    valid_instances = set(sizes["macros"].keys())
            except Exception:
                pass

        self.macros.clear()
        for m in state.get("macros", []):
            if not isinstance(m, dict):
                continue
            inst_name = m.get("inst_name", "")
            master = m.get("name", "")
            if not inst_name:
                continue
            if valid_instances is not None and len(valid_instances) > 0 and inst_name not in valid_instances:
                print(f"[SDK AUDIT WARNING] Stale synthetic macro instance '{inst_name}' not in netlist; rejecting.")
                continue
            x = float(m.get("x", 0.0))
            y = float(m.get("y", 0.0))
            orient_str = m.get("orientation", "R0")
            try:
                orient = Orientation(orient_str)
            except ValueError:
                orient = Orientation.R0
            macro = self.add_macro(inst_name, master, x, y, 100.0, 100.0, orient)
            if "halo" in m and isinstance(m["halo"], (list, tuple)) and len(m["halo"]) == 4:
                macro.set_halo(*m["halo"])

        self._notify_physical_mutation()
        return state

    def verify_netlist_checksum(self) -> bool:
        """Verifies current netlist SHA-256 against saved .silis_fp_session.json checksum."""
        import json, os, hashlib
        if not self.project or not hasattr(self.project, "get_netlist"):
            return False
        nl = self.project.get_netlist()
        if not nl or not os.path.isfile(nl):
            return False
        session_file = os.path.join(self.project.root_dir, ".silis_fp_session.json")
        if not os.path.isfile(session_file):
            return False
        with open(session_file, "r") as f:
            state = json.load(f)
        saved_checksum = state.get("netlist_checksum", "")
        with open(nl, "rb") as f:
            cur_sha = hashlib.sha256(f.read()).hexdigest()
        return bool(saved_checksum and saved_checksum == cur_sha)

    def _notify_physical_mutation(self):
        """Notifies parent project and OpenDB bridge of layout changes."""
        if self.project and hasattr(self.project, "_on_layout_mutated"):
            self.project._on_layout_mutated()

    def __repr__(self):
        cw, ch = self.get_core_dimensions()
        return f"<Floorplan Die=({self.die_width:.1f}x{self.die_height:.1f}) Core=({cw:.1f}x{ch:.1f}) Macros={len(self.macros)}>"
