"""
Silis project package root.
All sub-modules expose their public classes here for convenient importing.
"""

import sys
import os

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR = os.path.join(_REPO_ROOT, "core")
_CLI_DIR = os.path.join(_CORE_DIR, "cli")

for _d in [_REPO_ROOT, _CORE_DIR, _CLI_DIR]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

__path__.append(_CORE_DIR)

from config import THEMES, USER_SETTINGS, load_user_settings, save_user_settings
from editor.editor import ScintillaEditor, VSCodeEditor, VSCodeEditorTabs, CommandPalette
from pdkmanagers.pdk.manager import SSAForge, PDKManager, ManualPDKDialog, PDKSelector
from backendflow.siliconpeeker.peeker import DEFParser, SiliconPeeker
from sdk import (
    Project,
    Pipeline,
    SignoffReport,
    SynthesisReport,
    DRCReport,
    create_project,
    load_project,
    view_layout,
    view_gds3d,
    view_waveforms,
    view_schematic,
    open_gui,
    _SC_AVAILABLE,
    sc,
    from_sc,
    to_sc,
)

load = load_project

# Re-export SilisIDE class from silis.py module
def _get_silis_ide():
    import importlib.util
    silis_py_path = os.path.join(_REPO_ROOT, "silis.py")
    spec = importlib.util.spec_from_file_location("_silis_app", silis_py_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "SilisIDE")

try:
    from silis import SilisIDE
except (ImportError, AttributeError):
    try:
        SilisIDE = _get_silis_ide()
    except Exception:
        SilisIDE = None


import sdk
import backendflow
import pdkmanagers
import schematicviewer
import synthesisscripts
import editor
import terminal
import signalpeeker

__all__ = [
    "THEMES", "USER_SETTINGS", "load_user_settings", "save_user_settings",
    "ScintillaEditor", "VSCodeEditor", "VSCodeEditorTabs", "CommandPalette",
    "SSAForge", "PDKManager", "ManualPDKDialog", "PDKSelector",
    "DEFParser", "SiliconPeeker",
    "Project", "Pipeline", "SignoffReport", "SynthesisReport", "DRCReport",
    "view_layout", "view_gds3d", "view_waveforms", "view_schematic", "open_gui",
    "sdk", "backendflow", "pdkmanagers", "schematicviewer", "synthesisscripts",
    "editor", "terminal", "signalpeeker",
]

