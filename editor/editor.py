import os
import sys
# Ensure the editor directory is on sys.path so editor_engine.so is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.Qsci import QsciScintilla, QsciLexerVerilog, QsciLexerTCL
from config import THEMES, USER_SETTINGS


class ScintillaEditor(QsciScintilla):
    def __init__(self, is_minimap=False, font_family="Consolas", font_size=11, theme_name="Catppuccin Mocha"):
        super().__init__()
        
        # Base setup
        self.setUtf8(True)
        self.setEolMode(QsciScintilla.EolMode.EolUnix)
        
        # Font
        self.font_family = font_family
        self.font_size_pt = 2 if is_minimap else font_size
        font = QFont(font_family, self.font_size_pt)
        font.setFixedPitch(True)
        self.setFont(font)
        self.theme = THEMES.get(theme_name, THEMES["Catppuccin Mocha"])
        self.bg_color = bg_color = QColor(self.theme["bg"])
        self.fg_color = fg_color = QColor(self.theme["fg"])
        caret_color = QColor(self.theme["fg"])
        sel_bg = QColor(self.theme["sel"])
        margin_bg = QColor(self.theme["margin_bg"])
        margin_fg = QColor(self.theme["margin_fg"])
        
        # General styling
        self.setPaper(bg_color)
        self.setColor(fg_color)
        self.setCaretForegroundColor(caret_color)
        self.setSelectionBackgroundColor(sel_bg)
        
        # Line numbers
        self.setMarginsBackgroundColor(margin_bg)
        self.setMarginsForegroundColor(margin_fg)
        self.setMarginsFont(font)
        
        if is_minimap:
            self.setMarginWidth(0, 0)
            self.setReadOnly(True)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setCaretWidth(0)
        else:
            self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
            self.setMarginWidth(0, "0000")
            self.setCaretWidth(2)
            self.setCaretLineVisible(True)
            self.setCaretLineBackgroundColor(sel_bg)
            
            # Folding
            self.setFolding(QsciScintilla.FoldStyle.PlainFoldStyle)
            self.setMarginType(1, QsciScintilla.MarginType.SymbolMargin)
            self.setMarginWidth(1, 12)
            self.setFoldMarginColors(margin_bg, margin_bg)
            
            # Auto-completion & Indentation
            self.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAll)
            self.setAutoCompletionThreshold(2)
            self.setAutoIndent(True)
            self.setIndentationsUseTabs(False)
            self.setTabWidth(4)
            
            # Zoom Shortcuts
            QShortcut(QKeySequence("Ctrl=="), self).activated.connect(self.zoomIn)
            QShortcut(QKeySequence("Ctrl++"), self).activated.connect(self.zoomIn)
            QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(self.zoomOut)

    def set_lexer(self, ext):
        lexer = None
        if ext in ['.v', '.sv', '.vh']:
            lexer = QsciLexerVerilog(self)
        elif ext in ['.tcl', '.sdc']:
            lexer = QsciLexerTCL(self)
            
        if lexer:
            font = QFont(self.font_family, self.font_size_pt)
            font.setFixedPitch(True)
            lexer.setDefaultFont(font)
            lexer.setDefaultPaper(self.bg_color)
            lexer.setDefaultColor(self.fg_color)
            
            # Wipe out any OS-hardcoded default lexer colors
            for i in range(128):
                lexer.setColor(self.fg_color, i)
                lexer.setPaper(self.bg_color, i)
                lexer.setFont(font, i)
            
            # Bold font for keywords
            font_bold = QFont(self.font_family, self.font_size_pt)
            font_bold.setFixedPitch(True)
            font_bold.setBold(True)

            # Customize Verilog colors manually
            if isinstance(lexer, QsciLexerVerilog):
                lexer.setColor(QColor(self.theme["kw"]), QsciLexerVerilog.Keyword)
                lexer.setFont(font_bold, QsciLexerVerilog.Keyword)
                lexer.setColor(QColor(self.theme["kw2"]), QsciLexerVerilog.KeywordSet2)
                lexer.setColor(QColor(self.theme["kw2"]), getattr(QsciLexerVerilog, 'DeclareInputPort', 12))
                lexer.setColor(QColor(self.theme["kw2"]), getattr(QsciLexerVerilog, 'DeclareOutputPort', 13))
                lexer.setColor(QColor(self.theme["kw2"]), getattr(QsciLexerVerilog, 'DeclareInputOutputPort', 14))
                lexer.setColor(QColor(self.theme["str"]), QsciLexerVerilog.String)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerVerilog.Comment)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerVerilog.CommentLine)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerVerilog.CommentBang)
                lexer.setColor(QColor(self.theme["num"]), QsciLexerVerilog.Number)
                lexer.setColor(QColor(self.theme["ident"]), QsciLexerVerilog.Identifier)
            
            # Customize TCL colors manually
            if isinstance(lexer, QsciLexerTCL):
                lexer.setColor(QColor(self.theme["kw"]), QsciLexerTCL.TCLKeyword)
                lexer.setFont(font_bold, QsciLexerTCL.TCLKeyword)
                lexer.setColor(QColor(self.theme["str"]), QsciLexerTCL.QuotedString)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerTCL.Comment)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerTCL.CommentLine)
                lexer.setColor(QColor(self.theme["num"]), QsciLexerTCL.Number)
                lexer.setColor(QColor(self.theme["kw2"]), QsciLexerTCL.Modifier)
                lexer.setColor(QColor(self.theme["ident"]), QsciLexerTCL.Identifier)
                
            self.setLexer(lexer)


def _find_monaco_vs_path():
    """Detect the monaco-editor min/vs directory from system npm or common fallback paths."""
    import subprocess
    candidates = []
    
    # Try npm root -g
    try:
        npm_root = subprocess.check_output(['npm', 'root', '-g'], stderr=subprocess.DEVNULL).decode().strip()
        candidates.append(os.path.join(npm_root, 'monaco-editor', 'min', 'vs'))
    except Exception:
        pass
    
    # Common fallback locations
    candidates += [
        '/usr/local/lib/node_modules/monaco-editor/min/vs',
        '/usr/lib/node_modules/monaco-editor/min/vs',
        os.path.expanduser('~/.npm/monaco-editor/*/package/min/vs'),
    ]
    
    for path in candidates:
        if os.path.isdir(path):
            return path
    
    return None  # Will fall back to CDN


class MonacoEditorWrapper(QWidget):
    def __init__(self, parent=None, ext='.v', font_family='Consolas', font_size=11, theme_name='Catppuccin Mocha'):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        import editor_engine, json
        from PyQt6.sip import wrapinstance
        self.core = editor_engine.MonacoViewerCore()
        ptr = self.core.get_ptr()
        self.web_view = wrapinstance(ptr, QWidget)
        self._layout.addWidget(self.web_view)

        # Resolve language from extension
        lang = {'.v': 'verilog', '.sv': 'verilog', '.vh': 'verilog',
                '.tcl': 'tcl', '.sdc': 'tcl',
                '.py': 'python',
                '.cpp': 'cpp', '.h': 'cpp', '.c': 'cpp'}.get(ext, 'plaintext')

        # Resolve theme colors from colorconfig — fallback to Catppuccin Mocha
        all_themes = THEMES
        colors = all_themes.get(theme_name) or all_themes.get('Catppuccin Mocha', {})

        # Detect OS dark/light if theme is "Custom" or unknown
        if not colors:
            palette = QApplication.instance().palette()
            bg_lum = palette.color(QPalette.ColorRole.Window).lightness()
            colors = all_themes.get('Catppuccin Mocha' if bg_lum < 128 else 'VS Code Dark+', {})

        # Read template HTML and inject all settings as JS globals before the MONACO_LOCAL line
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'monaco.html'))
        base_url = 'file://' + os.path.dirname(html_path) + '/'
        with open(html_path, 'r') as f:
            html = f.read()

        monaco_path = _find_monaco_vs_path()
        local_var = f"'file://{monaco_path}'" if monaco_path else "''"

        inject = (
            f"var __MONACO_LOCAL__    = {local_var};\n"
            f"var __SILIS_THEME__     = {json.dumps(colors)};\n"
            f"var __SILIS_FONT_FAMILY__ = {json.dumps(font_family)};\n"
            f"var __SILIS_FONT_SIZE__ = {font_size};\n"
            f"var __SILIS_LANG__      = {json.dumps(lang)};\n"
        )

        html = html.replace(
            "var MONACO_LOCAL = window.__MONACO_LOCAL__ || '';",
            inject +
            "var MONACO_LOCAL = __MONACO_LOCAL__;\n"
            "var SILIS_THEME = __SILIS_THEME__;\n"
            "var SILIS_FONT_FAMILY = __SILIS_FONT_FAMILY__;\n"
            "var SILIS_FONT_SIZE = __SILIS_FONT_SIZE__;\n"
            "var SILIS_LANG = __SILIS_LANG__;"
        )

        self.core.load_html(html, base_url)

    def setPlainText(self, text):
        self.core.set_text(text)

    def toPlainText(self):
        return self.core.get_text()

    def set_lexer(self, ext):
        lang = {'.v': 'verilog', '.sv': 'verilog', '.vh': 'verilog',
                '.tcl': 'tcl', '.sdc': 'tcl',
                '.py': 'python',
                '.cpp': 'cpp', '.h': 'cpp', '.c': 'cpp'}.get(ext, 'plaintext')
        self.core.set_language(lang)

    def set_theme(self, theme_name):
        # Re-apply theme by toggling the base — full custom theme was defined at load time
        colors = THEMES.get(theme_name) or THEMES.get('Catppuccin Mocha', {})
        if colors:
            bg = colors.get('bg', '#1e1e1e')
            r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            self.core.set_theme('silis-theme' if lum < 0.5 else 'silis-theme')
        else:
            # OS-based fallback
            palette = QApplication.instance().palette()
            bg_lum = palette.color(QPalette.ColorRole.Window).lightness()
            self.core.set_theme('vs-dark' if bg_lum < 128 else 'vs')

    def set_font(self, font_family, font_size):
        self.core.get_text()  # ensure loaded
        js = f"if(window.setFont) setFont({repr(font_family)}, {font_size});"
        if hasattr(self.core, 'run_js'):
            self.core.run_js(js)

    def run_js(self, script):
        if hasattr(self.core, 'run_js'):
            self.core.run_js(script)

class VSCodeEditor(QWidget):
    def __init__(self, parent=None, ext=".v", font_family="Consolas", font_size=11, theme_name="Catppuccin Mocha"):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        try:
            import editor_engine
            self.editor = MonacoEditorWrapper(self, ext=ext, font_family=font_family, font_size=font_size, theme_name=theme_name)
            self.editor.set_lexer(ext)
        except Exception as e:
            import traceback
            print(f"Warning: Monaco editor failed ({e}). Falling back to ScintillaEditor.")
            traceback.print_exc()
            self.editor = ScintillaEditor(is_minimap=False, font_family=font_family, font_size=font_size, theme_name=theme_name)
            self.editor.set_lexer(ext)
            
        self.layout.addWidget(self.editor)
        
    def setPlainText(self, text):
        if hasattr(self.editor, 'setText'):
            self.editor.setText(text) # Scintilla
        else:
            self.editor.setPlainText(text) # Monaco
        
    def toPlainText(self):
        if hasattr(self.editor, 'text'):
            return self.editor.text() # Scintilla
        else:
            return self.editor.toPlainText() # Monaco

    def run_js(self, script):
        if hasattr(self.editor, 'run_js'):
            self.editor.run_js(script)


class VSCodeEditorTabs(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.font_family = USER_SETTINGS.get("font_family", "Consolas")
        self.font_size = USER_SETTINGS.get("font_size", 11)
        self.theme_name = USER_SETTINGS.get("theme_name", "Catppuccin Mocha")
        self.setTabsClosable(True)
        self.setDocumentMode(True)
        self.update_stylesheet()
        self.tabCloseRequested.connect(self.close_tab)
        self.files = {}  # path -> VSCodeEditor

    def open_file(self, path):
        if path in self.files:
            self.setCurrentWidget(self.files[path])
            return
        ext = os.path.splitext(path)[1]
        editor = VSCodeEditor(ext=ext, font_family=self.font_family, font_size=self.font_size, theme_name=self.theme_name)
        with open(path, 'r') as f:
            editor.setPlainText(f.read())
        self.files[path] = editor
        idx = self.addTab(editor, os.path.basename(path))
        self.setTabToolTip(idx, path)
        self.setCurrentIndex(idx)

    def update_appearance(self, font_family, font_size, theme_name):
        self.font_family = font_family
        self.font_size = font_size
        self.theme_name = theme_name
        self.update_stylesheet()
        open_paths = list(self.files.keys())
        current_idx = self.currentIndex()
        for i in range(self.count()-1, -1, -1):
            self.close_tab(i)
        for path in open_paths:
            self.open_file(path)
        if current_idx >= 0 and current_idx < self.count():
            self.setCurrentIndex(current_idx)

    def update_stylesheet(self):
        theme = THEMES.get(self.theme_name, THEMES["Catppuccin Mocha"])
        self.setStyleSheet(f"""
            QTabWidget::pane {{ border: 0; }}
            QTabBar::tab {{
                background: {theme.get('margin_bg', '#2D2D2D')};
                color: {theme.get('margin_fg', '#969696')};
                padding: 8px 16px;
                border: none;
                border-right: 1px solid {theme.get('bg', '#1E1E1E')};
            }}
            QTabBar::tab:selected {{
                background: {theme.get('bg', '#1E1E1E')};
                color: {theme.get('fg', '#FFFFFF')};
                border-top: 1px solid {theme.get('kw', '#007ACC')};
            }}
        """)

    def close_tab(self, index):
        widget = self.widget(index)
        for path, ed in list(self.files.items()):
            if ed == widget:
                del self.files[path]
                break
        self.removeTab(index)
        widget.deleteLater()

    def current_editor(self):
        return self.currentWidget()

    def current_file_path(self):
        widget = self.currentWidget()
        for path, ed in list(self.files.items()):
            if ed == widget: return path
        return None

    def setPlainText(self, text):
        ed = self.current_editor()
        if ed: ed.setPlainText(text)

    def toPlainText(self):
        ed = self.current_editor()
        return ed.toPlainText() if ed else ""


class CommandPalette(QDialog):
    def __init__(self, parent, commands):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setStyleSheet("""
            QDialog { background: #252526; border: 1px solid #454545; border-radius: 6px; }
            QLineEdit { background: #3C3C3C; color: #CCCCCC; padding: 6px; border: 1px solid #007ACC; font-size: 14px; }
            QListWidget { background: #252526; color: #CCCCCC; border: none; font-size: 13px; }
            QListWidget::item:selected { background: #094771; }
        """)
        self.setFixedSize(600, 400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command...")
        layout.addWidget(self.input)
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.commands = commands
        self.populate_list(self.commands)
        self.input.textChanged.connect(self.filter_list)
        self.list.itemActivated.connect(self.accept)
        self.input.returnPressed.connect(self.on_return)
        
        self.input.installEventFilter(self)

    def showEvent(self, event):
        super().showEvent(event)
        self.input.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up:
                row = self.list.currentRow()
                if row > 0: self.list.setCurrentRow(row - 1)
                return True
            elif key == Qt.Key.Key_Down:
                row = self.list.currentRow()
                if row < self.list.count() - 1: self.list.setCurrentRow(row + 1)
                return True
        return super().eventFilter(obj, event)

    def populate_list(self, items):
        self.list.clear()
        for name, _ in items:
            self.list.addItem(name)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def filter_list(self, text):
        filtered = [cmd for cmd in self.commands if text.lower() in cmd[0].lower()]
        self.populate_list(filtered)

    def on_return(self):
        if self.list.count() > 0:
            self.accept()

    def get_selected(self):
        if self.list.currentItem():
            name = self.list.currentItem().text()
            for cmd_name, func in self.commands:
                if cmd_name == name: return func
        return None

class FileSearchPalette(QDialog):
    def __init__(self, parent, root_dir):
        super().__init__(parent)
        self.root_dir = root_dir
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setStyleSheet("""
            QDialog { background: #252526; border: 1px solid #454545; border-radius: 6px; }
            QLineEdit { background: #3C3C3C; color: #CCCCCC; padding: 6px; border: 1px solid #007ACC; font-size: 14px; }
            QListWidget { background: #252526; color: #CCCCCC; border: none; font-size: 13px; }
            QListWidget::item:selected { background: #094771; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Search files by name (e.g. main.v)...")
        layout.addWidget(self.input)
        self.list = QListWidget()
        layout.addWidget(self.list)
        
        self.all_files = []
        import os
        ignore_dirs = {'build', '.git', 'node_modules', '__pycache__', '.pytest_cache'}
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, self.root_dir)
                self.all_files.append((f, rel, full))
                
        self.input.textChanged.connect(self.filter_list)
        self.list.itemActivated.connect(self.accept)
        self.input.returnPressed.connect(self.on_return)
        
        self.input.installEventFilter(self)
        self.filter_list("")

    def showEvent(self, event):
        super().showEvent(event)
        self.input.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up:
                row = self.list.currentRow()
                if row > 0: self.list.setCurrentRow(row - 1)
                return True
            elif key == Qt.Key.Key_Down:
                row = self.list.currentRow()
                if row < self.list.count() - 1: self.list.setCurrentRow(row + 1)
                return True
        return super().eventFilter(obj, event)
        
    def filter_list(self, text):
        self.list.clear()
        text = text.lower()
        
        results = []
        for name, rel, full in self.all_files:
            if not text:
                results.append((0, name, rel, full))
            elif text in name.lower():
                # Prefer exact or starts with
                if name.lower().startswith(text): results.append((1, name, rel, full))
                else: results.append((2, name, rel, full))
            elif text in rel.lower():
                results.append((3, name, rel, full))
                
        results.sort(key=lambda x: (x[0], x[1]))
        for r in results[:100]:
            item = QListWidgetItem(f"{r[1]}  —  {os.path.dirname(r[2])}")
            item.setData(Qt.ItemDataRole.UserRole, r[3])
            self.list.addItem(item)
            
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
            
    def on_return(self):
        if self.list.count() > 0:
            self.accept()
            
    def get_selected(self):
        if self.list.currentItem():
            return self.list.currentItem().data(Qt.ItemDataRole.UserRole)
        return None
