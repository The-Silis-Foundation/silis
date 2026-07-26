import os
import re
import time
import subprocess
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from config import THEMES, USER_SETTINGS


class HeaderFactory:
    """Central factory for the ASCII branding."""
    ASCII_ART = """
███████╗ ██╗ ██╗      ██╗ ███████╗
██╔════╝ ██║ ██║      ██║ ██╔════╝
███████╗ ██║ ██║      ██║ ███████╗
╚════██║ ██║ ██║      ██║ ╚════██║
███████║ ██║ ███████╗ ██║ ███████║
╚══════╝ ╚═╝ ╚══════╝ ╚═╝ ╚══════╝
    """
    TAGLINE = "Silis — Silicon Scaffold"
    COPYRIGHT = "TO BE COPYRIGHTED"
    LICENSE = "TO BE LICENCED UNDER OPEN-SOURCE"

    @staticmethod
    def get_raw_header():
        return f"{HeaderFactory.ASCII_ART}\n{HeaderFactory.TAGLINE}\n{HeaderFactory.COPYRIGHT}\n{HeaderFactory.LICENSE}\n"


class VSCodeTerminalInput(QLineEdit):
    """
    Terminal input bar with:
      - Tab         → cycle through matches / open popup
      - Shift / →   → accept inline ghost-text suggestion (Linux-style)
      - Ghost text   → greyed-out suggestion shown inline as you type
    """
    tabPressed    = pyqtSignal()
    ghostAccepted = pyqtSignal()   # fired when user accepts the ghost suggestion

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ghost = ""           # the suffix not yet accepted
        self._ghost_color = QColor("#666666")

    def set_ghost(self, suffix: str):
        """Set (or clear) the greyed-out inline suggestion suffix."""
        self._ghost = suffix
        self.update()

    def clear_ghost(self):
        self._ghost = ""
        self.update()

    def has_ghost(self):
        return bool(self._ghost)

    def accept_ghost(self):
        """Commit the ghost text into the real input."""
        if self._ghost:
            self.setText(self.text() + self._ghost)
            self.setCursorPosition(len(self.text()))
            self._ghost = ""
            self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Tab:
            if self._ghost:
                self.accept_ghost()
                self.ghostAccepted.emit()
            else:
                self.tabPressed.emit()
            event.accept()
            return
        if self._ghost and key in (Qt.Key.Key_Right, Qt.Key.Key_End):
            if self.cursorPosition() == len(self.text()):
                self.accept_ghost()
                self.ghostAccepted.emit()
                event.accept()
                return
        if key not in (Qt.Key.Key_Control, Qt.Key.Key_Alt,
                       Qt.Key.Key_Meta, Qt.Key.Key_CapsLock):
            self.clear_ghost()
        super().keyPressEvent(event)

    def focusNextPrevChild(self, next):
        return False

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._ghost:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm      = QFontMetrics(self.font())
        typed   = self.text()
        margins  = self.textMargins()
        left_pad = margins.left() + 4
        text_x   = left_pad + fm.horizontalAdvance(typed)
        text_y   = (self.height() + fm.ascent() - fm.descent()) // 2
        painter.setFont(self.font())
        painter.setPen(self._ghost_color)
        painter.drawText(text_x, text_y, self._ghost)
        painter.end()


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

        self.term_log = QTextEdit()
        self.term_log.setReadOnly(True)
        self.term_log.setStyleSheet(
            "QTextEdit {"
            "  background: #1e1e1e;"
            "  color: #cccccc;"
            "  font-family: 'Consolas', 'Courier New', monospace;"
            "  font-size: 12px;"
            "  border: none;"
            "  padding: 4px;"
            "}"
        )
        self.term_log.setPlainText(HeaderFactory.get_raw_header())
        lay.addWidget(self.term_log)

        self._popup = QListWidget(self)
        self._popup.setWindowFlags(Qt.WindowType.Popup)
        self._popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._popup.setStyleSheet(
            "QListWidget {"
            "  background: #252526; color: #cccccc;"
            "  font-family: 'Consolas', monospace; font-size: 12px;"
            "  border: 1px solid #007acc;"
            "  padding: 2px;"
            "}"
            "QListWidget::item:selected { background: #007acc; color: white; }"
            "QListWidget::item:hover    { background: #094771; }"
        )
        self._popup.itemClicked.connect(self._apply_popup_selection)
        self._popup.hide()

        inp_widget = QWidget()
        inp_widget.setStyleSheet("background: #1e1e1e;")
        inp_lay = QHBoxLayout(inp_widget)
        inp_lay.setContentsMargins(4, 2, 4, 2)
        inp_lay.setSpacing(6)

        self.mode_btn = QPushButton("[SHELL]")
        self.mode_btn.setFixedWidth(70)
        self.mode_btn.setStyleSheet(
            "QPushButton { background: #007acc; color: white; border: none;"
            "  font-family: Consolas; font-size: 11px; padding: 3px 6px; border-radius: 3px; }"
            "QPushButton:hover { background: #005f9e; }"
        )
        inp_lay.addWidget(self.mode_btn)

        self._prompt_lbl = QLabel("$")
        self._prompt_lbl.setStyleSheet(
            "color: #4ec9b0; font-family: Consolas; font-size: 12px; padding: 0 4px;"
        )
        inp_lay.addWidget(self._prompt_lbl)

        self.term_input = VSCodeTerminalInput()
        self.term_input.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.term_input.setStyleSheet(
            "QLineEdit {"
            "  background: #1e1e1e; color: #cccccc;"
            "  font-family: 'Consolas', 'Courier New', monospace;"
            "  font-size: 12px; border: none; padding: 2px;"
            "}"
        )
        self.term_input.tabPressed.connect(self._on_tab)
        self.term_input.returnPressed.connect(self._on_enter)
        self.term_input.textEdited.connect(self._on_text_edited)
        self.term_input.ghostAccepted.connect(self._on_ghost_accepted)
        self.term_input.installEventFilter(self)
        inp_lay.addWidget(self.term_input)

        lay.addWidget(inp_widget)
        self._update_prompt()

        current_theme = USER_SETTINGS.get('theme_name', 'Catppuccin Mocha')
        self.update_appearance(USER_SETTINGS.get('font_family', 'Consolas'), USER_SETTINGS.get('font_size', 12), THEMES.get(current_theme, THEMES['Catppuccin Mocha']))

    def update_appearance(self, font_family, font_size, theme):
        self.setStyleSheet(f"background-color: {theme['bg']}; color: {theme['fg']};")
        self.term_log.setStyleSheet(f"QTextEdit {{ background: {theme['bg']}; color: {theme['fg']}; font-family: '{font_family}', monospace; font-size: {font_size}pt; border: none; padding: 4px; }}")
        self.term_input.setStyleSheet(f"QLineEdit {{ background: {theme['bg']}; color: {theme['fg']}; font-family: '{font_family}', monospace; font-size: {font_size}pt; border: none; padding: 2px; }}")
        self._popup.setStyleSheet(f"QListWidget {{ background: {theme['bg']}; color: {theme['fg']}; font-family: '{font_family}', monospace; font-size: {font_size}pt; border: 1px solid {theme['sel']}; padding: 2px; }} QListWidget::item:selected {{ background: {theme['sel']}; color: {theme['fg']}; }} QListWidget::item:hover {{ background: {theme['sel']}; }}")
        self.mode_btn.setStyleSheet(f"QPushButton {{ background: {theme['sel']}; color: {theme['fg']}; border: none; font-family: '{font_family}'; font-size: {font_size-1}pt; padding: 3px 6px; border-radius: 3px; }} QPushButton:hover {{ background: {theme['kw']}; }}")
        self._prompt_lbl.setStyleSheet(f"color: {theme['kw']}; font-family: '{font_family}'; font-size: {font_size}pt; padding: 0 4px;")

    def _update_prompt(self):
        cwd = getattr(self.ide, 'cwd', os.getcwd())
        home = os.path.expanduser("~")
        display = cwd.replace(home, "~") if cwd.startswith(home) else cwd
        self._prompt_lbl.setText(f"{display} $")

    def _strip_ansi(self, text):
        return self.ANSI_ESCAPE.sub('', text)

    def append_output(self, text, color="#cccccc"):
        """Append a line of output to the log (thread-safe via Qt signal routing)."""
        text = self._strip_ansi(str(text))
        cursor = self.term_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.term_log.setTextCursor(cursor)
        self.term_log.setTextColor(QColor(color))
        self.term_log.insertPlainText(text + "\n")
        self.term_log.verticalScrollBar().setValue(
            self.term_log.verticalScrollBar().maximum()
        )

    def _on_enter(self):
        cmd = self.term_input.text().strip()
        self.term_input.clear()
        self._hide_popup()
        if not cmd:
            return
        if not self._history or self._history[-1] != cmd:
            self._history.append(cmd)
        self._hist_idx = -1
        cwd = getattr(self.ide, 'cwd', os.getcwd())
        home = os.path.expanduser("~")
        display = cwd.replace(home, "~") if cwd.startswith(home) else cwd
        self.append_output(f"{display} $ {cmd}", color="#4ec9b0")
        self.ide.handle_terminal_cmd(cmd)

    def _on_tab(self):
        """Called when Tab is pressed and there is NO ghost text."""
        self._handle_tab(from_ghost=False)

    def _handle_tab(self, from_ghost=False):
        import time
        text = self.term_input.text()
        cwd  = getattr(self.ide, 'cwd', os.getcwd())
        now           = time.time()
        is_double_tap = (now - self._last_tab_time) < 0.4
        self._last_tab_time = now
        parts = text.split()
        if text.endswith(" ") or not parts:
            partial    = ""
            prefix_cmd = text
        else:
            partial    = parts[-1]
            prefix_cmd = text[: len(text) - len(partial)]
        if os.path.sep in partial or partial.startswith("~") or partial.startswith("."):
            dir_part  = os.path.dirname(os.path.join(cwd, os.path.expanduser(partial)))
            name_part = os.path.basename(partial)
        else:
            dir_part  = cwd
            name_part = partial
        if is_double_tap:
            self._hide_popup()
            if partial.endswith("/"):
                list_dir = os.path.normpath(os.path.join(cwd, partial))
            else:
                list_dir = dir_part
            self._show_dir_listing(list_dir, name_part if not partial.endswith("/") else "", text)
            return
        if partial.endswith("/"):
            return
        try:
            entries = os.listdir(dir_part)
        except OSError:
            entries = []
        candidates = sorted(e for e in entries if e.lower().startswith(name_part.lower()))
        if not parts or (len(parts) == 1 and not text.endswith(" ")):
            builtins = ["cd", "ls", "pwd", "clear", "echo", "cat", "grep",
                        "mkdir", "rm", "cp", "mv", "python3", "make", "git",
                        "yosys", "iverilog", "vvp", "sta"]
            cmd_cands = sorted(b for b in builtins if b.startswith(name_part))
            candidates = cmd_cands + [c for c in candidates if c not in cmd_cands]
        if not candidates:
            return
        if len(candidates) == 1:
            completed = candidates[0]
            full_path = os.path.join(dir_part, completed)
            if os.path.isdir(full_path):
                completed += "/"
            new_text = prefix_cmd + completed
            if new_text != text:
                self.term_input.setText(new_text)
                self.term_input.setCursorPosition(len(self.term_input.text()))
                self.term_input.clear_ghost()
            self._hide_popup()
        else:
            common = os.path.commonprefix(candidates)
            if common and common != name_part:
                new_text = prefix_cmd + common
                self.term_input.setText(new_text)
                self.term_input.setCursorPosition(len(self.term_input.text()))
                self.term_input.clear_ghost()
            self._hide_popup()

    def _show_dir_listing(self, dir_part, name_part, current_input):
        try:
            all_entries = sorted(os.listdir(dir_part), key=lambda e: e.lower())
        except OSError as exc:
            self.append_output(f"bash: {exc}", color="#f44747")
            return
        if name_part:
            matching = [e for e in all_entries if e.lower().startswith(name_part.lower())]
        else:
            matching = all_entries
        if not matching:
            return
        labels = []
        for e in matching:
            labels.append(e + "/" if os.path.isdir(os.path.join(dir_part, e)) else e)
        col_width  = max(len(l) for l in labels) + 2
        term_width = 80
        num_cols   = max(1, term_width // col_width)
        num_rows   = (len(labels) + num_cols - 1) // num_cols
        plain_lines = []
        for row in range(num_rows):
            line = ""
            for col in range(num_cols):
                idx = row + col * num_rows
                if idx < len(labels):
                    line += labels[idx].ljust(col_width)
            plain_lines.append(line.rstrip())
        for line in plain_lines:
            self.append_output(line, color="#cccccc")
        self.term_log.verticalScrollBar().setValue(self.term_log.verticalScrollBar().maximum())

    def _show_popup(self, candidates):
        self._popup.clear()
        for c in candidates:
            full = os.path.join(getattr(self.ide, 'cwd', os.getcwd()), c)
            icon = "📁 " if os.path.isdir(full) else "📄 "
            self._popup.addItem(icon + c)
        self._popup.setCurrentRow(0)
        pos = self.term_input.mapToGlobal(self.term_input.rect().topLeft())
        item_h = self._popup.sizeHintForRow(0) + 2
        popup_h = min(len(candidates), 8) * item_h + 6
        self._popup.setFixedWidth(max(300, self.term_input.width()))
        self._popup.setFixedHeight(popup_h)
        self._popup.move(pos.x(), pos.y() - popup_h)
        self._popup.show()

    def _hide_popup(self):
        self._popup.hide()
        self._tab_candidates = []

    def _apply_popup_selection(self, item):
        raw = item.text()[2:]
        cwd = getattr(self.ide, 'cwd', os.getcwd())
        full = os.path.join(cwd, raw)
        if os.path.isdir(full):
            raw += "/"
        self.term_input.setText(self._tab_prefix + raw)
        self.term_input.setCursorPosition(len(self.term_input.text()))
        self._hide_popup()
        self.term_input.setFocus()

    def _on_text_edited(self, text):
        self._hide_popup()
        self._hist_idx = -1
        self._update_ghost(text)

    def _on_ghost_accepted(self):
        import time
        self._last_tab_time = time.time()
        self._hide_popup()
        txt = self.term_input.text()
        parts = txt.split()
        token = parts[-1] if parts and not txt.endswith(" ") else ""
        if not token.endswith("/"):
            self._update_ghost(txt)
        else:
            self.term_input.clear_ghost()

    def _update_ghost(self, text: str):
        """Compute the best single inline completion and show it as ghost text."""
        if not text or text.endswith(" "):
            self.term_input.clear_ghost()
            return
        parts = text.split()
        partial = parts[-1] if parts else ""
        if partial.endswith("/"):
            self.term_input.clear_ghost()
            return
        cwd = getattr(self.ide, 'cwd', os.getcwd())
        if os.path.sep in partial or partial.startswith("~") or partial.startswith("."):
            dir_part  = os.path.dirname(os.path.join(cwd, os.path.expanduser(partial)))
            name_part = os.path.basename(partial)
        else:
            dir_part  = cwd
            name_part = partial
        try:
            entries = os.listdir(dir_part)
        except OSError:
            entries = []
        candidates = sorted(e for e in entries if e.startswith(name_part) and e != name_part)
        if not parts or (len(parts) == 1 and not text.endswith(" ")):
            builtins = ["cd", "ls", "pwd", "clear", "echo", "cat", "grep",
                        "mkdir", "rm", "cp", "mv", "python3", "make", "git",
                        "yosys", "iverilog", "vvp", "sta"]
            cmd_cands = sorted(b for b in builtins if b.startswith(partial) and b != partial)
            candidates = cmd_cands + [c for c in candidates if c not in cmd_cands]
        if candidates:
            best      = candidates[0]
            ghost_sfx = best[len(name_part):]
            if os.path.isdir(os.path.join(dir_part, best)):
                ghost_sfx += "/"
            self.term_input.set_ghost(ghost_sfx)
        else:
            self.term_input.clear_ghost()

    def eventFilter(self, obj, event):
        if obj is self.term_input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if self._popup.isVisible():
                if key == Qt.Key.Key_Down:
                    idx = (self._popup.currentRow() + 1) % self._popup.count()
                    self._popup.setCurrentRow(idx)
                    return True
                elif key == Qt.Key.Key_Up:
                    idx = (self._popup.currentRow() - 1) % self._popup.count()
                    self._popup.setCurrentRow(idx)
                    return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    item = self._popup.currentItem()
                    if item:
                        self._apply_popup_selection(item)
                    return True
                elif key == Qt.Key.Key_Escape:
                    self._hide_popup()
                    return True
            if key == Qt.Key.Key_Up:
                if self._history:
                    if self._hist_idx == -1:
                        self._hist_idx = len(self._history) - 1
                    elif self._hist_idx > 0:
                        self._hist_idx -= 1
                    self.term_input.setText(self._history[self._hist_idx])
                    self.term_input.end(False)
                return True
            elif key == Qt.Key.Key_Down:
                if self._hist_idx != -1:
                    if self._hist_idx < len(self._history) - 1:
                        self._hist_idx += 1
                        self.term_input.setText(self._history[self._hist_idx])
                    else:
                        self._hist_idx = -1
                        self.term_input.clear()
                    self.term_input.end(False)
                return True
        return super().eventFilter(obj, event)

    def clear_log(self):
        self.term_log.clear()
