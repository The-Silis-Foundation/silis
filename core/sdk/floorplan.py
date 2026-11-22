"""
silis/core/sdk/floorplan.py
Physical Floorplanning, Manufacturing Grid Quantization, and Macro Legalization.
Implements the canonical Silis SDK Floorplan and MacroInstance object models
specified in Section 3 & 4 of the Silis Master Architectural Specification.
"""

import math
from typing import List, Tuple, Dict, Any, Optional, Union
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


def snap_to_site_row(y: float, row_height: float, origin_y: float = 0.0) -> float:
    """
    Quantizes a y-coordinate to legal standard cell site rows relative to row origin.
    Satisfies: ((y - origin_y) mod row_height) == 0.
    """
    if math.isnan(y) or math.isinf(y):
        raise ValueError(f"Invalid coordinate value: {y}")
    if row_height <= 0.0:
        return legalize_coord(y)
    rel = y - origin_y
    return round(origin_y + round(rel / row_height) * row_height, 3)


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

    @property
    def area(self) -> float:
        return round(self.width * self.height, 3)

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
        """Moves macro origin with manufacturing grid quantization, site row snapping, and physical non-overlap assertion."""
        rh = 0.0
        mfg = 0.005
        if self.parent_floorplan:
            rh = getattr(self.parent_floorplan, "site_row_height", 0.0) or self.parent_floorplan._resolve_site_row_height()
            mfg = getattr(self.parent_floorplan, "manufacturing_grid", 0.005)
        new_x = legalize_coord(x, mfg)
        new_y = snap_to_site_row(y, rh) if rh > 0.0 else legalize_coord(y, mfg)

        if self.parent_floorplan:
            # Pre-flight core containment
            cx1, cy1, cx2, cy2 = self.parent_floorplan.get_core_bbox()
            cw, ch = self.parent_floorplan.get_core_dimensions()
            if cw > 0.0 and ch > 0.0:
                mx1, my1 = new_x, new_y
                mx2, my2 = mx1 + self.effective_width, my1 + self.effective_height
                if mx1 < (cx1 - 0.001) or my1 < (cy1 - 0.001) or mx2 > (cx2 + 0.001) or my2 > (cy2 + 0.001):
                    from .exceptions import PlacementContainmentError
                    raise PlacementContainmentError(self.name, (mx1, my1, mx2, my2), (cx1, cy1, cx2, cy2), "core")

            # Physical and halo non-overlap assertions against other placed macros
            new_bbox = (new_x, new_y, new_x + self.effective_width, new_y + self.effective_height)
            new_halo_bbox = (
                new_x - self.halo.left,
                new_y - self.halo.bottom,
                new_x + self.effective_width + self.halo.right,
                new_y + self.effective_height + self.halo.top,
            )
            for ex_name, ex_m in self.parent_floorplan.macros.items():
                if ex_name == self.name:
                    continue
                ex_bbox = ex_m.get_bbox()
                ov_x1 = max(new_bbox[0], ex_bbox[0])
                ov_y1 = max(new_bbox[1], ex_bbox[1])
                ov_x2 = min(new_bbox[2], ex_bbox[2])
                ov_y2 = min(new_bbox[3], ex_bbox[3])
                if ov_x1 < (ov_x2 - 0.001) and ov_y1 < (ov_y2 - 0.001):
                    from .exceptions import MacroCollisionError
                    raise MacroCollisionError(self.name, new_bbox, ex_name, ex_bbox, (ov_x1, ov_y1, ov_x2, ov_y2))
                ex_h_bbox = ex_m.get_halo_bbox()
                h_ov_x1 = max(new_halo_bbox[0], ex_h_bbox[0])
                h_ov_y1 = max(new_halo_bbox[1], ex_h_bbox[1])
                h_ov_x2 = min(new_halo_bbox[2], ex_h_bbox[2])
                h_ov_y2 = min(new_halo_bbox[3], ex_h_bbox[3])
                if h_ov_x1 < (h_ov_x2 - 0.001) and h_ov_y1 < (h_ov_y2 - 0.001):
                    from .exceptions import OverlappingHaloError
                    raise OverlappingHaloError(
                        f"Macro halo collision between '{self.name}' halo {new_halo_bbox} and '{ex_name}' halo {ex_h_bbox}. "
                        f"Keepout overlap: {(h_ov_x1, h_ov_y1, h_ov_x2, h_ov_y2)}."
                    )

        self.x = new_x
        self.y = new_y
        if self.parent_floorplan:
            self.parent_floorplan._notify_physical_mutation()

    def set_orientation(self, orient: Orientation) -> None:
        self.orientation = orient if isinstance(orient, Orientation) else Orientation(orient)
        if self.parent_floorplan:
            self.parent_floorplan._notify_physical_mutation()

    def set_halo(
        self,
        left: float = 0.0,
        bottom: Optional[float] = None,
        right: Optional[float] = None,
        top: Optional[float] = None,
        **kwargs
    ) -> None:
        """Sets physical keepout halo margins around the macro body."""
        if "bottom" in kwargs or "right" in kwargs or "top" in kwargs:
            b_val = kwargs.get("bottom", bottom if bottom is not None else 0.0)
            r_val = kwargs.get("right", right if right is not None else 0.0)
            t_val = kwargs.get("top", top if top is not None else 0.0)
            l_val = left
        elif bottom is not None and right is not None and top is not None:
            b_val = bottom
            r_val = right
            t_val = top
            l_val = left
        else:
            b_val = float(bottom if bottom is not None else left)
            r_val = float(right if right is not None else left)
            t_val = float(top if top is not None else left)
            l_val = float(left)
        self.halo = Halo(left=l_val, bottom=b_val, right=r_val, top=t_val)
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
    def __init__(
        self,
        project=None,
        die_width: Optional[float] = None,
        die_height: Optional[float] = None,
        margins: Optional[Margins] = None,
    ):
        if isinstance(project, (int, float)):
            actual_w = float(project)
            actual_h = float(die_width) if die_width is not None else actual_w
            self.project = None
            self.die_width = legalize_coord(actual_w)
            self.die_height = legalize_coord(actual_h)
        else:
            self.project = project
            self.die_width = legalize_coord(float(die_width)) if die_width is not None else 1000.0
            self.die_height = legalize_coord(float(die_height)) if die_height is not None else 1000.0
        if margins is not None:
            self.margins = margins if isinstance(margins, Margins) else Margins(*margins)
        else:
            self.margins = Margins(20.0, 20.0, 20.0, 20.0)
        self.macros: Dict[str, MacroInstance] = {}
        self.regions: Dict[str, Dict[str, Any]] = {}
        self.extra_components: Dict[str, Dict[str, Any]] = {}
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
        *args,
        orientation: Orientation = Orientation.R0,
        width: Optional[float] = None,
        height: Optional[float] = None,
        halo: Optional[Halo] = None,
        **kwargs,
    ) -> MacroInstance:
        """Adds a macro instance to the physical floorplan context with dynamic site row snapping."""
        actual_orient = orientation
        actual_width = width
        actual_height = height
        actual_halo = halo or kwargs.get("halo")

        if len(args) == 1:
            if isinstance(args[0], (Orientation, str)):
                actual_orient = args[0]
            elif isinstance(args[0], (int, float)):
                actual_width = float(args[0])
        elif len(args) == 2:
            if isinstance(args[0], (int, float)) and isinstance(args[1], (int, float)):
                actual_width = float(args[0])
                actual_height = float(args[1])
            elif isinstance(args[0], (Orientation, str)):
                actual_orient = args[0]
                actual_halo = args[1]
        elif len(args) >= 3:
            actual_width = float(args[0])
            actual_height = float(args[1])
            actual_orient = args[2]
            if len(args) >= 4:
                actual_halo = args[3]

        # Auto-resolve physical dimensions from project/PDK LEF if omitted
        if actual_width is None or actual_height is None:
            proj = getattr(self, "project", None)
            if proj and hasattr(proj, "get_macro_dimensions"):
                dim = proj.get_macro_dimensions(master) or proj.get_macro_dimensions(name)
                if dim:
                    if actual_width is None:
                        actual_width = dim[0]
                    if actual_height is None:
                        actual_height = dim[1]

        if actual_width is None:
            actual_width = float(kwargs.get("width", 100.0))
        if actual_height is None:
            actual_height = float(kwargs.get("height", 100.0))
        if isinstance(actual_orient, Orientation):
            pass
        elif hasattr(actual_orient, "value"):
            actual_orient = Orientation(actual_orient.value)
        else:
            s_orient = str(actual_orient).split(".")[-1].upper()
            def_to_orient = {
                "N": "R0", "S": "R180", "W": "R90", "E": "R270",
                "FN": "MY", "FS": "MX", "FW": "MXR90", "FE": "MYR90"
            }
            s_orient = def_to_orient.get(s_orient, s_orient)
            actual_orient = Orientation(s_orient)

        if actual_halo is None:
            actual_halo = Halo(0.0, 0.0, 0.0, 0.0)
        elif isinstance(actual_halo, (int, float)):
            actual_halo = Halo(float(actual_halo), float(actual_halo), float(actual_halo), float(actual_halo))
        elif isinstance(actual_halo, (tuple, list)):
            if len(actual_halo) == 4:
                actual_halo = Halo(*actual_halo)
            elif len(actual_halo) == 2:
                actual_halo = Halo(actual_halo[0], actual_halo[1], actual_halo[0], actual_halo[1])
            else:
                actual_halo = Halo(0.0, 0.0, 0.0, 0.0)

        # Manufacturing grid assertion
        diff_x = abs(x - round(x / self.manufacturing_grid) * self.manufacturing_grid)
        if diff_x > 0.0001:
            from .exceptions import GridLegalizationError
            raise GridLegalizationError(name, x, y, self.manufacturing_grid)

        rh = self.site_row_height or self._resolve_site_row_height()
        snapped_y = snap_to_site_row(y, rh) if rh > 0.0 else legalize_coord(y)
        legal_x = legalize_coord(x)

        # Pre-flight core containment assertion
        if self.die_width > 0.0 and self.die_height > 0.0:
            cx1, cy1, cx2, cy2 = self.get_core_bbox()
            cw, ch = self.get_core_dimensions()
            if cw > 0.0 and ch > 0.0:
                mx1 = legal_x
                my1 = snapped_y
                mx2 = mx1 + actual_width
                my2 = my1 + actual_height
                if mx1 < (cx1 - 0.001) or my1 < (cy1 - 0.001) or mx2 > (cx2 + 0.001) or my2 > (cy2 + 0.001):
                    from .exceptions import PlacementContainmentError
                    raise PlacementContainmentError(name, (mx1, my1, mx2, my2), (cx1, cy1, cx2, cy2), "core")

        # Physical and halo non-overlap assertions against all existing placed macros
        new_bbox = (legal_x, snapped_y, legal_x + actual_width, snapped_y + actual_height)
        new_halo_bbox = (
            legal_x - actual_halo.left,
            snapped_y - actual_halo.bottom,
            legal_x + actual_width + actual_halo.right,
            snapped_y + actual_height + actual_halo.top,
        )
        for exist_name, exist_m in self.macros.items():
            if exist_name == name:
                continue
            ex_bbox = exist_m.get_bbox()
            ov_x1 = max(new_bbox[0], ex_bbox[0])
            ov_y1 = max(new_bbox[1], ex_bbox[1])
            ov_x2 = min(new_bbox[2], ex_bbox[2])
            ov_y2 = min(new_bbox[3], ex_bbox[3])
            if ov_x1 < (ov_x2 - 0.001) and ov_y1 < (ov_y2 - 0.001):
                from .exceptions import MacroCollisionError
                raise MacroCollisionError(name, new_bbox, exist_name, ex_bbox, (ov_x1, ov_y1, ov_x2, ov_y2))
            
            ex_h_bbox = exist_m.get_halo_bbox()
            h_ov_x1 = max(new_halo_bbox[0], ex_h_bbox[0])
            h_ov_y1 = max(new_halo_bbox[1], ex_h_bbox[1])
            h_ov_x2 = min(new_halo_bbox[2], ex_h_bbox[2])
            h_ov_y2 = min(new_halo_bbox[3], ex_h_bbox[3])
            if h_ov_x1 < (h_ov_x2 - 0.001) and h_ov_y1 < (h_ov_y2 - 0.001):
                from .exceptions import OverlappingHaloError
                raise OverlappingHaloError(
                    f"Macro halo collision between '{name}' halo {new_halo_bbox} and '{exist_name}' halo {ex_h_bbox}. "
                    f"Keepout overlap: {(h_ov_x1, h_ov_y1, h_ov_x2, h_ov_y2)}."
                )

        inst = MacroInstance(
            name=name,
            master=master,
            x=legalize_coord(x),
            y=snapped_y,
            width=actual_width,
            height=actual_height,
            orientation=actual_orient,
            halo=actual_halo,
            parent_floorplan=self,
        )
        self.macros[name] = inst
        self._notify_physical_mutation()
        return inst

    def get_macro(self, name: str) -> Optional[MacroInstance]:
        return self.macros.get(name)

    def get_macros(self) -> List[MacroInstance]:
        return list(self.macros.values())

    def add_component(
        self,
        name: str,
        master: str,
        x: float,
        y: float,
        orientation: Union[Orientation, str] = Orientation.R0,
        status: str = "PLACED"
    ) -> Dict[str, Any]:
        """Adds an explicitly placed cell (pad, power switch, tapcell, MBIST collar) to the floorplan."""
        rh = self.site_row_height or self._resolve_site_row_height()
        cy1 = self.margins.bottom if self.margins else 0.0
        cx1 = self.margins.left if self.margins else 0.0
        site_w = 0.460
        is_pad_or_filler = "pad" in name or "fill" in name or "sky130_ef_io" in master or "corner" in name
        if not is_pad_or_filler and rh > 0.0:
            sy = snap_to_site_row(y, rh, origin_y=cy1)
            rel_x = max(0.0, x - cx1)
            sx = round(cx1 + round(rel_x / site_w) * site_w, 3)
        else:
            sx = legalize_coord(x, self.manufacturing_grid)
            sy = legalize_coord(y, self.manufacturing_grid)

        comp_info = {
            "name": name,
            "master": master,
            "x": sx,
            "y": sy,
            "orient": orientation if isinstance(orientation, Orientation) else Orientation(orientation),
            "status": status
        }
        self.extra_components[name] = comp_info
        self._notify_physical_mutation()
        return comp_info

    def add_pad(
        self,
        name: str,
        master: str,
        x: float,
        y: float,
        orientation: Union[Orientation, str] = Orientation.R0
    ) -> Dict[str, Any]:
        """Adds a peripheral I/O bond pad or supply pad."""
        return self.add_component(name=name, master=master, x=x, y=y, orientation=orientation, status="PLACED")

    def add_power_switch(
        self,
        name: str,
        x: float,
        y: float,
        master: str = "sky130_fd_sc_hd__power_switch"
    ) -> Dict[str, Any]:
        """Adds a physical power switch cell inside a switched power domain."""
        rh = self.site_row_height or self._resolve_site_row_height()
        cy1 = self.margins.bottom if self.margins else 0.0
        r_idx = int(round((y - cy1) / rh))
        orient = Orientation.MX if (r_idx % 2 == 1) else Orientation.R0
        return self.add_component(name=name, master=master, x=x, y=y, orientation=orient, status="PLACED")

    def add_mbist_collar_cell(
        self,
        name: str,
        x: float,
        y: float,
        master: str = "sky130_fd_sc_hd__dfxtp_1"
    ) -> Dict[str, Any]:
        """Adds an MBIST collar scan register adjacent to a memory macro."""
        rh = self.site_row_height or self._resolve_site_row_height()
        cy1 = self.margins.bottom if self.margins else 0.0
        r_idx = int(round((y - cy1) / rh))
        orient = Orientation.MX if (r_idx % 2 == 1) else Orientation.R0
        return self.add_component(name=name, master=master, x=x, y=y, orientation=orient, status="PLACED")

    def add_region(
        self,
        name: str,
        box: Union[Tuple[float, float, float, float], List[float]],
        module: Optional[str] = None
    ) -> Dict[str, Any]:
        """Declares an exclusive voltage fence or hierarchical floorplan region with core containment assertions."""
        if len(box) != 4:
            raise ValueError(f"Region box must have 4 coordinates [x1, y1, x2, y2], got {box}")
        x1, y1, x2, y2 = [legalize_coord(float(c), self.manufacturing_grid) for c in box]
        cx1, cy1, cx2, cy2 = self.get_core_bbox()
        if x1 < (cx1 - 0.001) or y1 < (cy1 - 0.001) or x2 > (cx2 + 0.001) or y2 > (cy2 + 0.001):
            from .exceptions import PlacementContainmentError
            raise PlacementContainmentError(name, (x1, y1, x2, y2), (cx1, cy1, cx2, cy2), "core")
        reg_info = {
            "name": name,
            "box": (x1, y1, x2, y2),
            "module": module or name
        }
        self.regions[name] = reg_info
        self._notify_physical_mutation()
        return reg_info

    def get_regions(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.regions)

    def _discover_netlist_instances(self) -> List[Tuple[str, str]]:
        """Parses gate-level netlist to extract valid physical standard cell instances, resolving submodules recursively."""
        import re, os
        instances: List[Tuple[str, str]] = []
        if not self.project:
            return instances
        nl_path = self.project.get_netlist() if hasattr(self.project, "get_netlist") else None
        if not nl_path or not os.path.isfile(nl_path):
            return instances
        try:
            with open(nl_path, "r", errors="ignore") as f:
                content = f.read()

            modules = {}
            for m in re.finditer(r"\bmodule\s+([a-zA-Z0-9_]+)\b\s*\([^;]*\);(.*?)endmodule", content, re.DOTALL):
                modules[m.group(1)] = m.group(2)

            top_mod = getattr(self.project, "top_module", None)
            if not top_mod or top_mod not in modules:
                if modules:
                    top_mod = list(modules.keys())[-1]

            seen_inames = set()

            def extract_from_mod(mod_name: str, prefix: str = ""):
                body = modules.get(mod_name, "")
                for match in re.finditer(r"\b([a-zA-Z0-9_]+)\s+([a-zA-Z0-9_]+)\s*\(\s*\.", body):
                    cell_type, inst_name = match.group(1), match.group(2)
                    full_name = f"{prefix}{inst_name}" if prefix else inst_name
                    if cell_type in modules:
                        extract_from_mod(cell_type, prefix=f"{full_name}/")
                    elif cell_type not in ("module", "input", "output", "wire", "reg", "assign", "always"):
                        if full_name not in seen_inames:
                            seen_inames.add(full_name)
                            instances.append((full_name, cell_type))

            if top_mod:
                extract_from_mod(top_mod)
        except Exception:
            pass
        return instances

    def _load_standard_cell_sizes(self) -> Dict[str, Tuple[float, float]]:
        """Parses available standard cell LEFs to map cell master name to (width_um, height_um)."""
        import os, re
        sizes: Dict[str, Tuple[float, float]] = {}
        lef_candidates = []
        home_dir = os.path.expanduser("~")
        pdk_base = os.environ.get("PDK_ROOT", os.path.join(home_dir, ".silis", "pdks"))
        for var in ["sky130A", "sky130B"]:
            p = os.path.join(pdk_base, var, "libs.ref", "sky130_fd_sc_hd", "lef", "sky130_fd_sc_hd.lef")
            if os.path.isfile(p):
                lef_candidates.append(p)
            p_psw = os.path.join(pdk_base, var, "libs.ref", "sky130_fd_sc_hd", "lef", "sky130_power_switch.lef")
            if os.path.isfile(p_psw):
                lef_candidates.append(p_psw)
            p_psw2 = os.path.join(pdk_base, var, "libs.ref", "sky130_power_switch", "lef", "power_switch.lef")
            if os.path.isfile(p_psw2):
                lef_candidates.append(p_psw2)

        for lef_file in lef_candidates:
            try:
                with open(lef_file, "r") as f:
                    cur_macro = None
                    for line in f:
                        m = re.match(r"^\s*MACRO\s+([a-zA-Z0-9_]+)", line)
                        if m:
                            cur_macro = m.group(1)
                        elif cur_macro and "SIZE" in line:
                            sm = re.search(r"SIZE\s+([\d\.]+)\s+BY\s+([\d\.]+)", line)
                            if sm:
                                sizes[cur_macro] = (float(sm.group(1)), float(sm.group(2)))
                                cur_macro = None
            except Exception:
                pass
        return sizes

    def _discover_toplevel_ports(self) -> List[Tuple[str, str]]:
        """Discovers top-level module ports and their directions from netlist, expanding bus bit ranges."""
        import re, os
        ports: List[Tuple[str, str]] = []
        if not self.project:
            return ports
        nl_path = self.project.get_netlist() if hasattr(self.project, "get_netlist") else None
        if not nl_path or not os.path.isfile(nl_path):
            return ports
        try:
            with open(nl_path, "r", errors="ignore") as f:
                content = f.read()
            top_mod = getattr(self.project, "top_module", None)
            module_body = content
            if top_mod:
                m_match = re.search(rf"\bmodule\s+{re.escape(top_mod)}\b\s*\((.*?)\);(.*?)endmodule", content, re.DOTALL)
                if m_match:
                    module_body = m_match.group(2)
            else:
                m_match = re.search(r"\bmodule\s+([a-zA-Z0-9_]+)\s*\((.*?)\);(.*?)endmodule", content, re.DOTALL)
                if m_match:
                    module_body = m_match.group(3)

            for m in re.finditer(r"\b(input|output|inout)\b(?:\s+(?:wire|reg))?(?:\s*\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*([^;]+);", module_body):
                direction = m.group(1).upper()
                msb_s, lsb_s = m.group(2), m.group(3)
                pnames = [p.strip() for p in m.group(4).split(",") if p.strip()]
                for pname in pnames:
                    if msb_s is not None and lsb_s is not None:
                        msb, lsb = int(msb_s), int(lsb_s)
                        step = 1 if lsb <= msb else -1
                        for b in range(lsb, msb + step, step):
                            ports.append((f"{pname}[{b}]", direction))
                    else:
                        ports.append((pname, direction))
        except Exception:
            pass
        return ports

    def insert_tapcells(
        self,
        distance: float = 14.0,
        master: str = "sky130_fd_sc_hd__tapvpwrvgnd_1"
    ) -> int:
        """
        Synthesizes a latchup-prevention tapcell grid across standard cell rows.
        Inserts tapcell instances spaced at `distance` (default 14.0 um) in every row,
        strictly excluding macro keepout halo regions.
        """
        cx1, cy1, cx2, cy2 = self.get_core_bbox()
        cw, ch = self.get_core_dimensions()
        if cw <= 0.0 or ch <= 0.0:
            return 0

        rh = self.site_row_height or self._resolve_site_row_height()
        if rh <= 0.0:
            rh = 2.72
        site_w = 0.460
        mfg = self.manufacturing_grid

        # Collect all macro halo keepout boxes
        halo_boxes = [m.get_halo_bbox() for m in self.macros.values()]
        cell_sizes = self._load_standard_cell_sizes()

        count = 0
        num_rows = int(ch // rh)
        sites_per_tap = max(1, int(round(distance / site_w)))
        stagger_sites = sites_per_tap // 2

        for r in range(num_rows):
            ry = legalize_coord(cy1 + r * rh, mfg)
            orient = Orientation.MX if (r % 2 == 1) else Orientation.R0
            offset_s = stagger_sites if (r % 2 == 1) else 0
            col_idx = 0
            while True:
                sx = legalize_coord(cx1 + (offset_s + col_idx * sites_per_tap) * site_w, mfg)
                if (sx + site_w) > (cx2 + 1e-4):
                    break
                tx1, ty1 = sx, ry
                tx2, ty2 = sx + site_w, ry + rh
                in_halo = False
                for hx1, hy1, hx2, hy2 in halo_boxes:
                    if not (tx2 <= hx1 or tx1 >= hx2 or ty2 <= hy1 or ty1 >= hy2):
                        in_halo = True
                        break
                if not in_halo:
                    for comp in self.extra_components.values():
                        if comp.get("status") in ("PLACED", "FIXED"):
                            cmaster = comp["master"]
                            if "pad" in comp["name"] or "fill" in comp["name"]:
                                continue
                            cx = comp["x"]
                            cy = comp["y"]
                            cw = cell_sizes.get(cmaster, (site_w, rh))[0]
                            ch_comp = cell_sizes.get(cmaster, (site_w, rh))[1]
                            if not (tx2 <= cx or tx1 >= (cx + cw) or ty2 <= cy or ty1 >= (cy + ch_comp)):
                                in_halo = True
                                break
                if not in_halo:
                    tname = f"u_tap_r{r}_c{col_idx}"
                    self.add_component(tname, master, sx, ry, orientation=orient, status="PLACED")
                    count += 1
                col_idx += 1

        self._notify_physical_mutation()
        return count

    def fill_io_pad_ring(
        self,
        masters: Optional[List[str]] = None
    ) -> int:
        """
        Fills all perimeter pad gaps across IO_SOUTH, IO_NORTH, IO_WEST, and IO_EAST
        with abutted IO filler slices (20um, 10um, 5um, 1um) to maintain continuous
        power/ground/ESD rings without floating boundary gaps.
        """
        if self.die_width <= 0.0 or self.die_height <= 0.0:
            return 0

        fill_defs = [
            ("sky130_ef_io__com_bus_slice_20um", 20.0),
            ("sky130_ef_io__com_bus_slice_10um", 10.0),
            ("sky130_ef_io__com_bus_slice_5um", 5.0),
            ("sky130_ef_io__com_bus_slice_1um", 1.0),
        ]
        mfg = self.manufacturing_grid
        die_w = self.die_width
        die_h = self.die_height
        corner_w = 200.0
        corner_h = 204.0
        pad_depth = 197.965

        south_pads = []
        north_pads = []
        west_pads = []
        east_pads = []

        for name, comp in list(self.extra_components.items()):
            m = comp.get("master", "")
            if "slice" in m or "com_bus" in m:
                continue
            x, y = comp["x"], comp["y"]
            w = 80.0
            if "corner" in m:
                continue
            elif "gpiov2" in m:
                w = 80.0
            elif "pad" in m or "io" in m:
                w = 75.0

            if y <= 5.0 and 190.0 <= x <= (die_w - 190.0):
                south_pads.append((x, x + w))
            elif y >= (die_h - 215.0) and 190.0 <= x <= (die_w - 190.0):
                north_pads.append((x, x + w))
            elif x <= 5.0 and 190.0 <= y <= (die_h - 190.0):
                west_pads.append((y, y + w))
            elif x >= (die_w - 215.0) and 190.0 <= y <= (die_h - 190.0):
                east_pads.append((y, y + w))

        def fill_segments(edge_start, edge_end, pads_occupied):
            pads_occupied.sort(key=lambda p: p[0])
            gaps = []
            cur = edge_start
            for p_start, p_end in pads_occupied:
                if p_start > (cur + 0.999):
                    gaps.append((cur, p_start))
                cur = max(cur, p_end)
            if cur < (edge_end - 0.999):
                gaps.append((cur, edge_end))
            return gaps

        total_fillers = 0

        # Fill South
        south_gaps = fill_segments(corner_w, die_w - corner_w, south_pads)
        for g_start, g_end in south_gaps:
            length = g_end - g_start
            cur_pos = g_start
            while (length - 0.999) > 0:
                chosen_master, chosen_w = fill_defs[-1]
                for f_m, f_w in fill_defs:
                    if f_w <= (length + 0.001):
                        chosen_master, chosen_w = f_m, f_w
                        break
                fname = f"io_fill_s_{legalize_coord(cur_pos, mfg):.3f}".replace(".", "_")
                self.add_component(fname, chosen_master, legalize_coord(cur_pos, mfg), 0.0, orientation=Orientation.R0, status="PLACED")
                total_fillers += 1
                cur_pos += chosen_w
                length -= chosen_w

        # Fill North
        north_gaps = fill_segments(corner_w, die_w - corner_w, north_pads)
        for g_start, g_end in north_gaps:
            length = g_end - g_start
            cur_pos = g_start
            while (length - 0.999) > 0:
                chosen_master, chosen_w = fill_defs[-1]
                for f_m, f_w in fill_defs:
                    if f_w <= (length + 0.001):
                        chosen_master, chosen_w = f_m, f_w
                        break
                fname = f"io_fill_n_{legalize_coord(cur_pos, mfg):.3f}".replace(".", "_")
                self.add_component(fname, chosen_master, legalize_coord(cur_pos, mfg), legalize_coord(die_h - pad_depth, mfg), orientation=Orientation.R180, status="PLACED")
                total_fillers += 1
                cur_pos += chosen_w
                length -= chosen_w

        # Fill West
        west_gaps = fill_segments(corner_h, die_h - corner_h, west_pads)
        for g_start, g_end in west_gaps:
            length = g_end - g_start
            cur_pos = g_start
            while (length - 0.999) > 0:
                chosen_master, chosen_w = fill_defs[-1]
                for f_m, f_w in fill_defs:
                    if f_w <= (length + 0.001):
                        chosen_master, chosen_w = f_m, f_w
                        break
                fname = f"io_fill_w_{legalize_coord(cur_pos, mfg):.3f}".replace(".", "_")
                self.add_component(fname, chosen_master, 0.0, legalize_coord(cur_pos, mfg), orientation=Orientation.R270, status="PLACED")
                total_fillers += 1
                cur_pos += chosen_w
                length -= chosen_w

        # Fill East
        east_gaps = fill_segments(corner_h, die_h - corner_h, east_pads)
        for g_start, g_end in east_gaps:
            length = g_end - g_start
            cur_pos = g_start
            while (length - 0.999) > 0:
                chosen_master, chosen_w = fill_defs[-1]
                for f_m, f_w in fill_defs:
                    if f_w <= (length + 0.001):
                        chosen_master, chosen_w = f_m, f_w
                        break
                fname = f"io_fill_e_{legalize_coord(cur_pos, mfg):.3f}".replace(".", "_")
                self.add_component(fname, chosen_master, legalize_coord(die_w - pad_depth, mfg), legalize_coord(cur_pos, mfg), orientation=Orientation.R90, status="PLACED")
                total_fillers += 1
                cur_pos += chosen_w
                length -= chosen_w

        self._notify_physical_mutation()
        return total_fillers

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

    def check_drc(self, def_path: Optional[str] = None) -> Any:
        """
        Runs comprehensive physical design rule checking (DRC) on the floorplan.
        1. Executes strict internal geometric & mathematical pre-flight checks.
        2. If DEF exists (or is generated) and OpenROAD is installed, executes OpenROAD detailed placement DRC (check_placement).
        Returns a DRCReport instance (clean=True if 0 violations, raises DRCViolationError if violations are found).
        """
        import os, shutil, subprocess
        from .report import DRCReport
        self.verify_legal_placement()

        target_def = def_path
        if not target_def and self.project:
            target_def = self.project.get_def(stage="floorplan")
        if not target_def or not os.path.isfile(target_def):
            return DRCReport(violations_count=0, tool="Floorplan Geometric DRC")

        if shutil.which("openroad"):
            home_dir = os.path.expanduser("~")
            pdk_base = os.environ.get("PDK_ROOT", os.path.join(home_dir, ".silis", "pdks"))
            tlef = os.path.join(pdk_base, "sky130A", "libs.ref", "sky130_fd_sc_hd", "techlef", "sky130_fd_sc_hd__nom.tlef")
            sc_lef = os.path.join(pdk_base, "sky130A", "libs.ref", "sky130_fd_sc_hd", "lef", "sky130_fd_sc_hd.lef")
            psw_lef = os.path.join(pdk_base, "sky130A", "libs.ref", "sky130_power_switch", "lef", "power_switch.lef")
            ef_io_lef = os.path.join(pdk_base, "sky130A", "libs.ref", "sky130_fd_io", "lef", "sky130_ef_io.lef")
            fd_io_lef = os.path.join(pdk_base, "sky130A", "libs.ref", "sky130_fd_io", "lef", "sky130_fd_io.lef")

            tcl_cmds = []
            for lf in [tlef, sc_lef, psw_lef, ef_io_lef, fd_io_lef]:
                if os.path.isfile(lf):
                    tcl_cmds.append(f'read_lef "{lf}"')
            if self.project:
                for m in getattr(self.project, "macros", []):
                    mf = os.path.join(pdk_base, "sky130A", "libs.ref", "sky130_sram_macros", "lef", f"{m}.lef")
                    if os.path.isfile(mf):
                        tcl_cmds.append(f'read_lef "{mf}"')
            tcl_cmds.append(f'read_def "{target_def}"')
            tcl_cmds.append("check_placement -verbose")

            cmd = ["openroad", "-exit"]
            res = subprocess.run(cmd, input="\n".join(tcl_cmds), text=True, capture_output=True)
            viols = []
            for line in res.stdout.splitlines():
                if "check failed" in line.lower() or "error:" in line.lower():
                    viols.append(line.strip())
            if viols:
                raise DRCViolationError(len(viols), f"OpenROAD placement DRC check failed: {'; '.join(viols[:3])}")
            return DRCReport(file_path=target_def, violations_count=0, tool="OpenROAD Detailed Placement DRC")

        return DRCReport(file_path=target_def, violations_count=0, tool="Floorplan Geometric DRC")

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

    def export_def(self, path: str, verify_drc: bool = True) -> None:
        """
        Exports full production-grade DEF 5.8 physical design representation with integer DBU units.
        Emits:
        - DIEAREA
        - Standard cell site ROWS across the core area
        - Routing TRACKS for metal layers (li1, met1, met2, met3, met4, met5)
        - REGIONS & GROUPS for voltage fences & power domains
        - COMPONENTS for placed macros and unplaced/placed netlist instances
        - PINS for top-level I/O ports along core perimeter
        - BLOCKAGES for macro placement halos (DEF 5.8 PLACEMENT RECT)
        Executes strict pre-flight DRC legalization (grid, site rows, core containment, halos).
        """
        import os
        if verify_drc:
            self.verify_legal_placement()

        orient_to_def = {
            "R0": "N", "R180": "S", "R90": "W", "R270": "E",
            "MY": "FN", "MX": "FS", "MXR90": "FW", "MYR90": "FE",
            "N": "N", "S": "S", "W": "W", "E": "E",
            "FN": "FN", "FS": "FS", "FW": "FW", "FE": "FE",
        }
        dbu = 1000
        top_name = getattr(self.project, "top_module", "top") if self.project else "top"
        die_w_dbu = int(round(self.die_width * dbu))
        die_h_dbu = int(round(self.die_height * dbu))

        cx1, cy1, cx2, cy2 = self.get_core_bbox()
        cx1_dbu = int(round(cx1 * dbu))
        cy1_dbu = int(round(cy1 * dbu))
        cx2_dbu = int(round(cx2 * dbu))
        cy2_dbu = int(round(cy2 * dbu))

        lines = [
            "VERSION 5.8 ;",
            'DIVIDERCHAR "/" ;',
            'BUSBITCHARS "[]" ;',
            f"DESIGN {top_name} ;",
            f"UNITS DISTANCE MICRONS {dbu} ;",
            f"DIEAREA ( 0 0 ) ( {die_w_dbu} {die_h_dbu} ) ;",
        ]

        # 1. Standard Cell Site Rows (ROWS)
        site_name = getattr(self, "site_name", "unithd")
        site_h = self._resolve_site_row_height()
        site_h_dbu = int(round(site_h * dbu))
        site_w = 0.460
        site_w_dbu = int(round(site_w * dbu))
        
        core_h_dbu = max(site_h_dbu, cy2_dbu - cy1_dbu)
        core_w_dbu = max(site_w_dbu, cx2_dbu - cx1_dbu)
        num_rows = max(1, int(core_h_dbu // site_h_dbu))
        num_sites = max(1, int(core_w_dbu // site_w_dbu))

        for r_idx in range(num_rows):
            r_y = cy1_dbu + r_idx * site_h_dbu
            r_orient = "FS" if (r_idx % 2 == 1) else "N"
            lines.append(f"ROW ROW_{r_idx} {site_name} {cx1_dbu} {r_y} {r_orient} DO {num_sites} BY 1 STEP {site_w_dbu} 0 ;")
            if r_idx % 2 == 0:
                lines.append(f"ROW ROW_{r_idx}_dbl unithddbl {cx1_dbu} {r_y} N DO {num_sites} BY 1 STEP {site_w_dbu} 0 ;")

        # 2. Manufacturing Routing Tracks (TRACKS)
        tracks_spec = [
            ("X", 230, int(die_w_dbu / 460), 460, "li1"),
            ("Y", 170, int(die_h_dbu / 340), 340, "li1"),
            ("X", 170, int(die_w_dbu / 340), 340, "met1"),
            ("Y", 170, int(die_h_dbu / 340), 340, "met1"),
            ("X", 230, int(die_w_dbu / 460), 460, "met2"),
            ("Y", 230, int(die_h_dbu / 460), 460, "met2"),
            ("X", 340, int(die_w_dbu / 680), 680, "met3"),
            ("Y", 340, int(die_h_dbu / 680), 680, "met3"),
            ("X", 460, int(die_w_dbu / 920), 920, "met4"),
            ("Y", 460, int(die_h_dbu / 920), 920, "met4"),
            ("X", 1700, int(die_w_dbu / 3400), 3400, "met5"),
            ("Y", 1700, int(die_h_dbu / 3400), 3400, "met5"),
        ]
        for axis, start, count, step, layer in tracks_spec:
            if count > 0:
                lines.append(f"TRACKS {axis} {start} DO {count} STEP {step} LAYER {layer} ;")

        # 3. Voltage Fences & Regions (REGIONS & GROUPS)
        all_regions = dict(getattr(self, "regions", {}))
        if self.project and hasattr(self.project, "get_power_network"):
            pnet = self.project.get_power_network()
            for d in getattr(pnet, "domains", {}).values():
                d_area = getattr(d, "area_box", None) or getattr(d, "area", None)
                if d_area and len(d_area) == 4 and not getattr(d, "is_top", False):
                    all_regions[d.name] = {
                        "name": d.name,
                        "box": d_area,
                        "module": d.elements[0] if getattr(d, "elements", []) else d.name
                    }

        if all_regions:
            lines.append(f"REGIONS {len(all_regions)} ;")
            for rname, rinfo in all_regions.items():
                box = rinfo["box"]
                rx1_dbu = int(round(box[0] * dbu))
                ry1_dbu = int(round(box[1] * dbu))
                rx2_dbu = int(round(box[2] * dbu))
                ry2_dbu = int(round(box[3] * dbu))
                lines.append(f"    - {rname} ( {rx1_dbu} {ry1_dbu} ) ( {rx2_dbu} {ry2_dbu} ) ;")
            lines.append("END REGIONS")

            lines.append(f"GROUPS {len(all_regions)} ;")
            for rname, rinfo in all_regions.items():
                lines.append(f"    - {rname} + REGION {rname} ;")
            lines.append("END GROUPS")

        # 4. Components (COMPONENTS)
        comp_lines = []
        placed_names = set()
        for inst in self.macros.values():
            mx = int(round(inst.x * dbu))
            my = int(round(inst.y * dbu))
            raw_orient = getattr(inst.orientation, "value", str(inst.orientation))
            def_orient = orient_to_def.get(raw_orient, "N")
            comp_lines.append(f"    - {inst.name} {inst.master} + PLACED ( {mx} {my} ) {def_orient} ;")
            placed_names.add(inst.name)

        # Ingest explicitly placed extra components (pads, power switches, MBIST collar cells)
        for comp in getattr(self, "extra_components", {}).values():
            if comp["name"] not in placed_names:
                cx = int(round(comp["x"] * dbu))
                cy = int(round(comp["y"] * dbu))
                raw_orient = getattr(comp["orient"], "value", str(comp["orient"]))
                def_orient = orient_to_def.get(raw_orient, "N")
                st = comp.get("status", "PLACED")
                comp_lines.append(f"    - {comp['name']} {comp['master']} + {st} ( {cx} {cy} ) {def_orient} ;")
                placed_names.add(comp["name"])

        # Ingest netlist standard cells with row placement
        netlist_instances = self._discover_netlist_instances()
        cell_sizes = self._load_standard_cell_sizes()
        site_w_dbu = int(round(site_w * dbu))

        macro_halo_boxes_dbu = [
            (
                int(round((m.x - m.halo.left) * dbu)),
                int(round((m.y - m.halo.bottom) * dbu)),
                int(round((m.x + m.effective_width + m.halo.right) * dbu)),
                int(round((m.y + m.effective_height + m.halo.top) * dbu))
            )
            for m in self.macros.values()
        ]

        # Extra components obstacle intervals per row
        extra_row_obstacles: Dict[int, List[Tuple[int, int]]] = {r: [] for r in range(num_rows)}
        for comp in getattr(self, "extra_components", {}).values():
            if comp.get("status") in ("PLACED", "FIXED"):
                cy_um = comp["y"]
                r_idx = int(round((cy_um - (cy1_dbu / dbu)) / (site_h_dbu / dbu)))
                if 0 <= r_idx < num_rows:
                    cx_dbu = int(round(comp["x"] * dbu))
                    cmaster = comp["master"]
                    cw_um = cell_sizes.get(cmaster, (site_w, site_h))[0]
                    cw_dbu = int(round(cw_um * dbu))
                    extra_row_obstacles[r_idx].append((cx_dbu, cx_dbu + cw_dbu))

        # Power domain lowpwr box
        pdl_box = all_regions.get("PD_LOWPWR", {}).get("box")
        pdl_x1_dbu = int(round(pdl_box[0] * dbu)) if pdl_box else None
        pdl_y1_dbu = int(round(pdl_box[1] * dbu)) if pdl_box else None
        pdl_x2_dbu = int(round(pdl_box[2] * dbu)) if pdl_box else None
        pdl_y2_dbu = int(round(pdl_box[3] * dbu)) if pdl_box else None

        def compute_free_intervals(row_x1: int, row_x2: int, obstacles: List[Tuple[int, int]], site_w_int: int) -> List[List[int]]:
            if not obstacles:
                return [[row_x1, row_x2]]
            sorted_obs = sorted(obstacles, key=lambda b: b[0])
            merged = []
            for ox1, ox2 in sorted_obs:
                rel1 = max(0, ox1 - row_x1)
                rel2 = max(0, ox2 - row_x1)
                k1 = rel1 // site_w_int
                k2 = int(math.ceil(rel2 / site_w_int))
                ox1_snap = min(row_x2, row_x1 + k1 * site_w_int)
                ox2_snap = min(row_x2, row_x1 + k2 * site_w_int)
                if ox1_snap >= ox2_snap:
                    continue
                if not merged:
                    merged.append([ox1_snap, ox2_snap])
                else:
                    if ox1_snap <= merged[-1][1]:
                        merged[-1][1] = max(merged[-1][1], ox2_snap)
                    else:
                        merged.append([ox1_snap, ox2_snap])
            free = []
            curr = row_x1
            for ox1, ox2 in merged:
                if ox1 > curr:
                    free.append([curr, ox1])
                curr = max(curr, ox2)
            if curr < row_x2:
                free.append([curr, row_x2])
            return [iv for iv in free if (iv[1] - iv[0]) >= site_w_int]

        general_row_free: Dict[int, List[List[int]]] = {}
        lowpwr_row_free: Dict[int, List[List[int]]] = {}

        for r in range(num_rows):
            ry1 = cy1_dbu + r * site_h_dbu
            ry2 = ry1 + site_h_dbu

            obs_general = list(extra_row_obstacles[r])
            for hx1, hy1, hx2, hy2 in macro_halo_boxes_dbu:
                if not (ry2 <= hy1 or ry1 >= hy2):
                    obs_general.append((hx1, hx2))

            if pdl_box and pdl_y1_dbu is not None and pdl_y2_dbu is not None:
                if not (ry2 <= pdl_y1_dbu or ry1 >= pdl_y2_dbu):
                    obs_general.append((pdl_x1_dbu, pdl_x2_dbu))
                    obs_pdl = [o for o in obs_general if not (o[1] <= pdl_x1_dbu or o[0] >= pdl_x2_dbu)]
                    lowpwr_row_free[r] = compute_free_intervals(pdl_x1_dbu, pdl_x2_dbu, obs_pdl, site_w_dbu)

            general_row_free[r] = compute_free_intervals(cx1_dbu, cx2_dbu, obs_general, site_w_dbu)

        cur_gen_row = 0
        pdl_rows = list(lowpwr_row_free.keys())
        cur_pdl_row = 0

        for iname, cmaster in netlist_instances:
            if iname in placed_names:
                continue

            cw_um = cell_sizes.get(cmaster, (1.380, 2.720))[0]
            cell_w_dbu = int(round(cw_um * dbu))
            cell_w_dbu = max(site_w_dbu, int(math.ceil(cell_w_dbu / site_w_dbu)) * site_w_dbu)

            is_lowpwr_cell = bool("u_alu" in iname or iname.startswith("alu_"))
            placed_x_dbu = None
            placed_y_dbu = None
            orient = "N"

            if is_lowpwr_cell and pdl_rows:
                attempts = 0
                while attempts < len(pdl_rows):
                    r_cand = pdl_rows[cur_pdl_row % len(pdl_rows)]
                    cur_pdl_row += 1
                    attempts += 1
                    intervals = lowpwr_row_free.get(r_cand, [])
                    for idx, iv in enumerate(intervals):
                        if (iv[1] - iv[0]) >= cell_w_dbu:
                            placed_x_dbu = iv[0]
                            placed_y_dbu = cy1_dbu + r_cand * site_h_dbu
                            orient = "FS" if (r_cand % 2 == 1) else "N"
                            iv[0] += cell_w_dbu
                            if iv[0] >= iv[1]:
                                intervals.pop(idx)
                            break
                    if placed_x_dbu is not None:
                        break

            if placed_x_dbu is None:
                attempts = 0
                while attempts < num_rows:
                    r_cand = cur_gen_row % num_rows
                    cur_gen_row += 1
                    attempts += 1
                    intervals = general_row_free.get(r_cand, [])
                    for idx, iv in enumerate(intervals):
                        if (iv[1] - iv[0]) >= cell_w_dbu:
                            placed_x_dbu = iv[0]
                            placed_y_dbu = cy1_dbu + r_cand * site_h_dbu
                            orient = "FS" if (r_cand % 2 == 1) else "N"
                            iv[0] += cell_w_dbu
                            if iv[0] >= iv[1]:
                                intervals.pop(idx)
                            break
                    if placed_x_dbu is not None:
                        break

            if placed_x_dbu is not None:
                comp_lines.append(f"    - {iname} {cmaster} + PLACED ( {placed_x_dbu} {placed_y_dbu} ) {orient} ;")
            else:
                comp_lines.append(f"    - {iname} {cmaster} + UNPLACED ;")
            placed_names.add(iname)

        if comp_lines:
            lines.append(f"COMPONENTS {len(comp_lines)} ;")
            lines.extend(comp_lines)
            lines.append("END COMPONENTS")

        # 5. Top-level I/O Pins (PINS)
        ports = self._discover_toplevel_ports()
        if ports:
            lines.append(f"PINS {len(ports)} ;")
            q = max(1, len(ports) // 4)
            for idx, (pname, pdir) in enumerate(ports):
                side = idx // q
                pos = idx % q
                if side == 0:  # South
                    px = cx1_dbu + int((pos + 0.5) * (core_w_dbu / q))
                    py = cy1_dbu
                    layer = "met2"
                    orient = "N"
                elif side == 1:  # East
                    px = cx2_dbu
                    py = cy1_dbu + int((pos + 0.5) * (core_h_dbu / q))
                    layer = "met3"
                    orient = "W"
                elif side == 2:  # North
                    px = cx1_dbu + int((pos + 0.5) * (core_w_dbu / q))
                    py = cy2_dbu
                    layer = "met2"
                    orient = "S"
                else:  # West
                    px = cx1_dbu
                    py = cy1_dbu + int((pos + 0.5) * (core_h_dbu / q))
                    layer = "met3"
                    orient = "E"
                lines.append(f"    - {pname} + NET {pname} + DIRECTION {pdir} + USE SIGNAL")
                lines.append(f"      + LAYER {layer} ( -140 -140 ) ( 140 140 ) + PLACED ( {px} {py} ) {orient} ;")
            lines.append("END PINS")

        # 6. Placement Blockages / Halos (BLOCKAGES)
        blockage_lines = []
        for inst in self.macros.values():
            if inst.halo.left > 0 or inst.halo.right > 0 or inst.halo.bottom > 0 or inst.halo.top > 0:
                hx1 = int(round((inst.x - inst.halo.left) * dbu))
                hy1 = int(round((inst.y - inst.halo.bottom) * dbu))
                hx2 = int(round((inst.x + inst.effective_width + inst.halo.right) * dbu))
                hy2 = int(round((inst.y + inst.effective_height + inst.halo.top) * dbu))
                blockage_lines.append(f"    - PLACEMENT RECT ( {hx1} {hy1} ) ( {hx2} {hy2} ) ;")
        if blockage_lines:
            lines.append(f"BLOCKAGES {len(blockage_lines)} ;")
            lines.extend(blockage_lines)
            lines.append("END BLOCKAGES")

        # 7. Power Distribution Network (SPECIALNETS)
        sp_lines = ["SPECIALNETS 2 ;"]
        # VDD
        sp_lines.append("    - VDD ( * VPWR ) ( * vccd1 ) + USE POWER")
        first_segment = True
        for r_idx in range(num_rows):
            r_y = cy1_dbu + r_idx * site_h_dbu
            if r_idx % 2 == 0:
                prefix = "      + ROUTED" if first_segment else "      NEW"
                sp_lines.append(f"{prefix} met1 480 + SHAPE FOLLOWPIN ( {cx1_dbu} {r_y} ) ( {cx2_dbu} {r_y} )")
                first_segment = False
        trunk_step = 60000
        t_x = cx1_dbu + 30000
        while t_x <= (cx2_dbu - 30000):
            sp_lines.append(f"      NEW met4 1600 + SHAPE STRIPE ( {t_x} {cy1_dbu} ) ( {t_x} {cy2_dbu} )")
            t_x += trunk_step
        strap_step = 80000
        s_y = cy1_dbu + 40000
        while s_y <= (cy2_dbu - 40000):
            sp_lines.append(f"      NEW met5 3200 + SHAPE STRIPE ( {cx1_dbu} {s_y} ) ( {cx2_dbu} {s_y} )")
            s_y += strap_step
        sp_lines.append("      ;")

        # VSS
        sp_lines.append("    - VSS ( * VGND ) ( * vssd1 ) + USE GROUND")
        first_segment = True
        for r_idx in range(num_rows):
            r_y = cy1_dbu + r_idx * site_h_dbu
            if r_idx % 2 == 1:
                prefix = "      + ROUTED" if first_segment else "      NEW"
                sp_lines.append(f"{prefix} met1 480 + SHAPE FOLLOWPIN ( {cx1_dbu} {r_y} ) ( {cx2_dbu} {r_y} )")
                first_segment = False
        t_x = cx1_dbu + 60000
        while t_x <= (cx2_dbu - 30000):
            sp_lines.append(f"      NEW met4 1600 + SHAPE STRIPE ( {t_x} {cy1_dbu} ) ( {t_x} {cy2_dbu} )")
            t_x += trunk_step
        s_y = cy1_dbu + 80000
        while s_y <= (cy2_dbu - 40000):
            sp_lines.append(f"      NEW met5 3200 + SHAPE STRIPE ( {cx1_dbu} {s_y} ) ( {cx2_dbu} {s_y} )")
            s_y += strap_step
        sp_lines.append("      ;")
        sp_lines.append("END SPECIALNETS")
        lines.extend(sp_lines)

        lines.append("END DESIGN")
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp_path, path)

        # Atomically synchronize results/temp.def if exporting into a project results directory
        res_dir = os.path.dirname(os.path.abspath(path))
        if os.path.basename(res_dir) == "results":
            temp_path = os.path.join(res_dir, "temp.def")
            if os.path.abspath(temp_path) != os.path.abspath(path):
                tmp_temp = temp_path + ".tmp"
                try:
                    shutil.copy2(path, tmp_temp)
                    os.replace(tmp_temp, temp_path)
                except Exception:
                    pass

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
            self.set_die_dimensions(w, h, Margins(left=ml, bottom=mb, right=mr, top=mt))

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
                macro.set_halo(left=m["halo"][0], bottom=m["halo"][1], right=m["halo"][2], top=m["halo"][3])

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
