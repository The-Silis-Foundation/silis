"""
silis/core/sdk/floorplan.py
Physical Floorplanning, Manufacturing Grid Quantization, and Macro Legalization.
Implements the canonical Silis SDK Floorplan and MacroInstance object models
specified in Section 3 & 4 of the Silis Master Architectural Specification.
"""

import math
from typing import List, Tuple, Dict, Any, Optional
from enum import Enum

from .exceptions import DRCViolationError


class Orientation(str, Enum):
    R0 = "R0"
    R90 = "R90"
    R180 = "R180"
    R270 = "R270"
    MY = "MY"
    MY90 = "MY90"
    MX = "MX"
    MX90 = "MX90"


class Margins:
    """Die-to-core perimeter margin specifications in micrometers."""
    def __init__(self, left: float = 20.0, bottom: float = 20.0, right: float = 20.0, top: float = 20.0):
        self.left = float(left)
        self.bottom = float(bottom)
        self.right = float(right)
        self.top = float(top)

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.left, self.bottom, self.right, self.top)

    def __repr__(self):
        return f"<Margins L={self.left:.3f} B={self.bottom:.3f} R={self.right:.3f} T={self.top:.3f}>"


def legalize_coord(val: float, grid: float = 0.005) -> float:
    """
    Quantizes a floating-point coordinate to manufacturing grid steps (default 5 DBU = 0.005 um in Sky130).
    Satisfies: (x mod g) == 0.
    """
    return round(round(val / grid) * grid, 3)


def snap_to_site_row(y: float, row_height: float) -> float:
    """
    Quantizes a y-coordinate to legal standard cell site rows.
    Satisfies: (y mod row_height) == 0.
    """
    if row_height <= 0.0:
        return legalize_coord(y)
    return round(round(y / row_height) * row_height, 3)


class Halo:
    """Physical keepout halo perimeter around a macro boundary."""
    def __init__(self, left: float = 0.0, bottom: float = 0.0, right: float = 0.0, top: float = 0.0):
        self.left = legalize_coord(left)
        self.bottom = legalize_coord(bottom)
        self.right = legalize_coord(right)
        self.top = legalize_coord(top)

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
        self.name = name
        self.master = master
        self.x = legalize_coord(x)
        self.y = legalize_coord(y)
        self.width = legalize_coord(width)
        self.height = legalize_coord(height)
        self.orientation = orientation if isinstance(orientation, Orientation) else Orientation(orientation)
        self.halo = halo or Halo(0.0, 0.0, 0.0, 0.0)
        self.parent_floorplan = parent_floorplan

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
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def get_halo_bbox(self) -> Tuple[float, float, float, float]:
        """Returns physical bounding box including keepout halo margins (x1, y1, x2, y2)."""
        return (
            self.x - self.halo.left,
            self.y - self.halo.bottom,
            self.x + self.width + self.halo.right,
            self.y + self.height + self.halo.top,
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
        return 0.0

    def _resolve_mfg_grid(self) -> float:
        """Dynamically queries manufacturing grid resolution from OpenDB or project PDK."""
        if self.project and hasattr(self.project, "db") and getattr(self.project.db, "mfg_grid", 0.0) > 0:
            return self.project.db.mfg_grid
        return 0.005

    def set_die_dimensions(self, width: float, height: float, margins: Optional[Margins] = None) -> None:
        """Sets die bounds with defensive dimension assertions."""
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

    def get_core_dimensions(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.get_core_bbox()
        return (legalize_coord(x2 - x1), legalize_coord(y2 - y1))

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

    def verify_legal_placement(self) -> bool:
        """
        Executes pre-flight DRC checks:
        1. Macro-to-macro keepout collision verification.
        2. Core containment assertion.
        """
        insts = list(self.macros.values())
        cx1, cy1, cx2, cy2 = self.get_core_bbox()

        # Check core containment
        for inst in insts:
            mx1, my1, mx2, my2 = inst.get_bbox()
            if mx1 < cx1 or my1 < cy1 or mx2 > cx2 or my2 > cy2:
                raise DRCViolationError(
                    1,
                    f"Macro {inst.name} ({inst.master}) at [{mx1}, {my1}, {mx2}, {my2}] exceeds core boundary [{cx1}, {cy1}, {cx2}, {cy2}]"
                )

        # Check collision invariant
        for i in range(len(insts)):
            for j in range(i + 1, len(insts)):
                if insts[i].overlaps(insts[j]):
                    raise DRCViolationError(
                        1,
                        f"Macro collision detected between '{insts[i].name}' and '{insts[j].name}'"
                    )

        return True

    def _notify_physical_mutation(self):
        """Notifies parent project and OpenDB bridge of layout changes."""
        if self.project and hasattr(self.project, "_on_layout_mutated"):
            self.project._on_layout_mutated()

    def __repr__(self):
        cw, ch = self.get_core_dimensions()
        return f"<Floorplan Die=({self.die_width:.1f}x{self.die_height:.1f}) Core=({cw:.1f}x{ch:.1f}) Macros={len(self.macros)}>"
