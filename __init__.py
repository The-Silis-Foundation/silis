"""
Silis project package root.
All sub-modules expose their public classes here for convenient importing.
"""

from config import THEMES, USER_SETTINGS, load_user_settings, save_user_settings
from editor.editor import ScintillaEditor, VSCodeEditor, VSCodeEditorTabs, CommandPalette
from pdkmanagers.pdk.manager import SSAForge, PDKManager, ManualPDKDialog, PDKSelector
from backendflow.siliconpeeker.peeker import DEFParser, SiliconPeeker

__all__ = [
    "THEMES", "USER_SETTINGS", "load_user_settings", "save_user_settings",
    "ScintillaEditor", "VSCodeEditor", "VSCodeEditorTabs", "CommandPalette",
    "SSAForge", "PDKManager", "ManualPDKDialog", "PDKSelector",
    "DEFParser", "SiliconPeeker",
]
