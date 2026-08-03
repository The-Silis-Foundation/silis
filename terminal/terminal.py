import os
import re
import time
import subprocess
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from config import THEMES, USER_SETTINGS





class VSCodeTerminalWidget(QWidget):
    """
    A proper VS Code-style terminal panel with:
      - Tab autocomplete for paths and commands (cd, ls, etc.)
      - Up/Down arrow command history (like a real shell)
      - Coloured prompt showing current directory
      - Async subprocess output streamed to the log
      - ANSI escape-code stripping so output is clean
    """
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def __init__(self, ide_parent):
        super().__init__()
        self.ide = ide_parent
        self._history = []
        self._hist_idx = -1
        self._tab_candidates = []
        self._tab_idx = 0
        self._tab_prefix = ""
        self._last_tab_time = 0.0
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)



        import sys
        terminal_dir = os.path.dirname(os.path.abspath(__file__))
        if terminal_dir not in sys.path:
            sys.path.insert(0, terminal_dir)
        import terminal_engine
        from PyQt6.sip import wrapinstance
        
        self.core = terminal_engine.TerminalWidgetCore()
        ptr = self.core.get_ptr()
        self.term_widget = wrapinstance(ptr, QWidget)
        
        self.term_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.term_widget.setMinimumHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(50)
        
        lay.addWidget(self.term_widget)
        
        # We start the shell and pass the current directory
        cwd = getattr(self.ide, 'cwd', os.getcwd())
        self.core.start_shell("", cwd)

        current_theme = USER_SETTINGS.get('theme_name', 'Catppuccin Mocha')
        self.update_appearance(USER_SETTINGS.get('font_family', 'Consolas'), USER_SETTINGS.get('font_size', 12), THEMES.get(current_theme, THEMES['Catppuccin Mocha']))

    def update_appearance(self, font_family, font_size, theme):
        import json
        self.setStyleSheet(f"background-color: {theme.get('bg', '#1e1e1e')}; color: {theme.get('fg', '#cccccc')};")
        self.core.apply_theme(json.dumps(theme))
        self.core.set_font(font_family, font_size)

    def _strip_ansi(self, text):
        return self.ANSI_ESCAPE.sub('', text)

    def append_output(self, text, color="#cccccc"):
        """Forward output to the native terminal widget"""
        self.core.send_text(str(text) + "\n")
        
    def clear_log(self):
        self.core.send_text("\x1b[2J\x1b[H")


