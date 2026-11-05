import os
import json
import shutil

SILIS_HOME = os.path.expanduser("~/.silis")
SILIS_CONFIG_DIR = os.path.join(SILIS_HOME, "config")
SILIS_PDK_DIR = os.path.join(SILIS_HOME, "pdks")
SILIS_MACRO_DIR = os.path.join(SILIS_HOME, "macrocache")
SILIS_REPORTS_DIR = os.path.join(SILIS_HOME, "reports")
USER_SETTINGS_FILE = os.path.join(SILIS_CONFIG_DIR, "settings.json")
EDITOR_CONFIG_FILE = os.path.join(SILIS_HOME, "editorconfig.json")
COLOR_CONFIG_FILE = os.path.join(SILIS_HOME, "colorconfig.json")

def setup_environment():
    """
    Scaffolds the central ~/.silis user directory on first launch.
    Deep-copies bundled PDKs and seed macros from third-party/pdks to ~/.silis/
    ensuring 100% self-contained AppImage portability without fragile symlinks.
    """
    os.makedirs(SILIS_CONFIG_DIR, exist_ok=True)
    os.makedirs(SILIS_PDK_DIR, exist_ok=True)
    os.makedirs(os.path.join(SILIS_MACRO_DIR, "sky130"), exist_ok=True)
    os.makedirs(os.path.join(SILIS_MACRO_DIR, "gf180mcu"), exist_ok=True)
    os.makedirs(SILIS_REPORTS_DIR, exist_ok=True)

    init_stamp = os.path.join(SILIS_HOME, ".initialized")
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    bundled_pdks = os.path.join(repo_root, "silis", "third-party", "pdks")
    if not os.path.isdir(bundled_pdks):
        bundled_pdks = os.path.join(repo_root, "third-party", "pdks")

    # Migrate legacy dotfiles if present
    legacy_settings = os.path.expanduser("~/.silis_ui_settings.json")
    if os.path.isfile(legacy_settings) and not os.path.isfile(USER_SETTINGS_FILE):
        try:
            shutil.copy2(legacy_settings, USER_SETTINGS_FILE)
        except Exception:
            pass

    # Deep-copy bundled PDKs on first launch
    if not os.path.isfile(init_stamp) and os.path.isdir(bundled_pdks):
        try:
            for item in os.listdir(bundled_pdks):
                src = os.path.join(bundled_pdks, item)
                dst = os.path.join(SILIS_PDK_DIR, item)
                if os.path.isdir(src) and not os.path.exists(dst):
                    shutil.copytree(src, dst)
                elif os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
            with open(init_stamp, "w") as f:
                f.write(json.dumps({"version": "2.1.0", "status": "initialized"}, indent=2))
        except Exception as e:
            print(f"[SILIS] Notice: First-launch PDK initialization: {e}")

    # Set standard process environment variables
    os.environ["PDK_ROOT"] = SILIS_PDK_DIR
    os.environ["SILIS_MACRO_CACHE"] = SILIS_MACRO_DIR

setup_environment()

def load_user_settings():
    if os.path.exists(USER_SETTINGS_FILE):
        try:
            with open(USER_SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "font_family": "Consolas",
        "font_size": 11,
        "theme_name": "Catppuccin Mocha",
        "custom_theme": {},
        "editor_backend": "monaco",
        "radix_preference": "hex"
    }

def save_user_settings(settings):
    try:
        os.makedirs(os.path.dirname(USER_SETTINGS_FILE), exist_ok=True)
        with open(USER_SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception:
        pass

USER_SETTINGS = load_user_settings()

def load_editor_config():
    """Loads editor-specific properties like font size, family, backend, line numbers."""
    if os.path.exists(EDITOR_CONFIG_FILE):
        try:
            with open(EDITOR_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    # Fallback to defaults or existing user settings
    return {
        "font_family": USER_SETTINGS.get("font_family", "Consolas"),
        "font_size": USER_SETTINGS.get("font_size", 11),
        "editor_backend": USER_SETTINGS.get("editor_backend", "monaco"),
        "line_numbers": True
    }

def save_editor_config(cfg):
    """Persists font and editor configurations to ~/.silis/editorconfig.json."""
    try:
        os.makedirs(os.path.dirname(EDITOR_CONFIG_FILE), exist_ok=True)
        with open(EDITOR_CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        print(f"[CONFIG] Error saving editorconfig.json: {e}")

EDITOR_CONFIG = load_editor_config()
# Ensure USER_SETTINGS stays synchronized
USER_SETTINGS["font_size"] = EDITOR_CONFIG.get("font_size", USER_SETTINGS.get("font_size", 11))
USER_SETTINGS["font_family"] = EDITOR_CONFIG.get("font_family", USER_SETTINGS.get("font_family", "Consolas"))
USER_SETTINGS["editor_backend"] = EDITOR_CONFIG.get("editor_backend", USER_SETTINGS.get("editor_backend", "monaco"))

def load_themes():
    # 1. Base built-in themes
    theme_file = os.path.join(os.path.dirname(__file__), "editor", "colorconfig.json")
    themes = {}
    if os.path.exists(theme_file):
        try:
            with open(theme_file, 'r') as f:
                themes = json.load(f)
        except Exception:
            pass

    # 2. User custom color overrides from ~/.silis/colorconfig.json
    if os.path.exists(COLOR_CONFIG_FILE):
        try:
            with open(COLOR_CONFIG_FILE, 'r') as f:
                user_themes = json.load(f)
                themes.update(user_themes)
        except Exception:
            pass

    return themes

def save_custom_palette(palette_name, palette_dict):
    """Saves a custom theme / palette into ~/.silis/colorconfig.json."""
    current_palettes = {}
    if os.path.exists(COLOR_CONFIG_FILE):
        try:
            with open(COLOR_CONFIG_FILE, 'r') as f:
                current_palettes = json.load(f)
        except Exception:
            pass
    current_palettes[palette_name] = palette_dict
    try:
        os.makedirs(os.path.dirname(COLOR_CONFIG_FILE), exist_ok=True)
        with open(COLOR_CONFIG_FILE, 'w') as f:
            json.dump(current_palettes, f, indent=4)
        THEMES[palette_name] = palette_dict
        return True
    except Exception as e:
        print(f"[CONFIG] Error saving colorconfig.json: {e}")
        return False

THEMES = load_themes()

THEMES["Custom"] = THEMES["Catppuccin Mocha"].copy()
if "custom_theme" in USER_SETTINGS and USER_SETTINGS["custom_theme"]:
    THEMES["Custom"].update(USER_SETTINGS["custom_theme"])
