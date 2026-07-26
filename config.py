import os
import json

USER_SETTINGS_FILE = os.path.expanduser("~/.silis_ui_settings.json")

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
        "custom_theme": {}
    }

def save_user_settings(settings):
    try:
        with open(USER_SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception:
        pass

USER_SETTINGS = load_user_settings()

def load_themes():
    theme_file = os.path.join(os.path.dirname(__file__), "editor", "colorconfig.json")
    if os.path.exists(theme_file):
        try:
            with open(theme_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

THEMES = load_themes()

THEMES["Custom"] = THEMES["Catppuccin Mocha"].copy()
if "custom_theme" in USER_SETTINGS and USER_SETTINGS["custom_theme"]:
    THEMES["Custom"].update(USER_SETTINGS["custom_theme"])
