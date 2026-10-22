"""
Silis Core Package
Houses all ASIC EDA submodules, engines, managers, and viewers.
"""

import sys
import os

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
CLI_DIR = os.path.join(CORE_DIR, "cli")

for _d in [CORE_DIR, CLI_DIR]:
    if _d not in sys.path:
        sys.path.insert(0, _d)


from .config import THEMES, USER_SETTINGS, load_user_settings, save_user_settings

__all__ = [
    "THEMES",
    "USER_SETTINGS",
    "load_user_settings",
    "save_user_settings",
]
