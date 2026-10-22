"""
silis/sdk/__init__.py
Silis Python SDK Root.
Exposes Project, Pipeline, SignoffReport, SynthesisReport, DRCReport,
view_layout, view_gds3d, view_waveforms, view_schematic, open_gui,
and SiliconCompiler integration (silis.sc, from_sc, to_sc).
"""

import sys as _sys
import os as _os

# ============================================================
# SCINT Phase 0: Auto-inject vendored SiliconCompiler
# ============================================================
_SDK_DIR = _os.path.dirname(_os.path.abspath(__file__))
# Check both repo root and parent of core/ for third-party/siliconcompiler
_CANDIDATE_ROOTS = [
    _os.path.dirname(_os.path.dirname(_SDK_DIR)),
    _os.path.dirname(_SDK_DIR),
]
for _root in _CANDIDATE_ROOTS:
    _sc_cand = _os.path.normpath(_os.path.join(_root, "third-party", "siliconcompiler"))
    if _os.path.isdir(_sc_cand) and _sc_cand not in _sys.path:
        _sys.path.insert(0, _sc_cand)
        break


try:
    import siliconcompiler as sc
    _SC_AVAILABLE = True
except ImportError:
    sc = None
    _SC_AVAILABLE = False

del _sys, _os, _SDK_DIR, _CANDIDATE_ROOTS

from .project import Project
from .pipeline import Pipeline
from .report import (
    SignoffReport,
    SynthesisReport,
    DRCReport,
    DFTSignoffReport,
    GLSSignoffReport,
    LVSSignoffReport,
    TapeoutManifestReport,
)
from .viewers import (
    view_layout,
    view_gds3d,
    view_waveforms,
    view_schematic,
    open_gui,
    open_floorplanner,
    open_ioplacer,
    view_magic,
    view_gtkwave,
    view_openroad_gui,
)

load_project = Project.load
create_project = Project.create

def get_utilization(module_or_region, area=None, project=None, refresh=False):
    """Computes module/region cell utilization using the specified Project or Pipeline."""
    if project is None:
        raise ValueError("A Project or Pipeline must be provided: get_utilization(..., project=proj)")
    return project.get_utilization(module_or_region, area=area, refresh=refresh)

enquire_utilization = get_utilization

def get_required_area(module, target_density=0.40, project=None, refresh=False):
    """Computes required physical area for target density using the specified Project or Pipeline."""
    if project is None:
        raise ValueError("A Project or Pipeline must be provided: get_required_area(..., project=proj)")
    return project.get_required_area(module=module, target_density=target_density, refresh=refresh)

def suggest_box(module, origin=(0.0, 0.0), target_density=0.40, aspect_ratio=1.0, project=None, refresh=False):
    """Calculates suggested [x1, y1, x2, y2] bounding box using the specified Project or Pipeline."""
    if project is None:
        raise ValueError("A Project or Pipeline must be provided: suggest_box(..., project=proj)")
    return project.suggest_box(module=module, origin=origin, target_density=target_density, aspect_ratio=aspect_ratio, refresh=refresh)

def auto_place_regions(pipeline_or_project, **kwargs):
    """Headless auto region placer for SDK."""
    if hasattr(pipeline_or_project, "auto_place_regions"):
        return pipeline_or_project.auto_place_regions(**kwargs)
    raise AttributeError("Object does not support auto_place_regions")

__all__ = [
    "Project",
    "Pipeline",
    "SignoffReport",
    "SynthesisReport",
    "DRCReport",
    "DFTSignoffReport",
    "GLSSignoffReport",
    "LVSSignoffReport",
    "TapeoutManifestReport",
    "load_project",
    "create_project",
    "get_utilization",
    "enquire_utilization",
    "get_required_area",
    "suggest_box",
    "auto_place_regions",
    "view_layout",
    "view_gds3d",
    "view_waveforms",
    "view_schematic",
    "open_gui",
    "view_magic",
    "view_gtkwave",
    "view_openroad_gui",
    # SiliconCompiler Integration (SCINT)
    "sc",
    "from_sc",
    "to_sc",
    "_SC_AVAILABLE",
]

# Bridge exports
from .sc_bridge import from_sc, to_sc

