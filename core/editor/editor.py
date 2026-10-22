import os
import sys

try:
    import qt_setup
except ImportError:
    pass

# Ensure the editor directory is on sys.path so editor_engine.so is importable
_ed_dir = os.path.dirname(os.path.abspath(__file__))
if _ed_dir not in sys.path:
    sys.path.append(_ed_dir)

from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
try:
    from PyQt6.Qsci import (
        QsciScintilla, QsciLexerVerilog, QsciLexerTCL,
        QsciLexerVHDL, QsciLexerPython, QsciLexerCPP
    )
    QSCI_AVAILABLE = True
except ImportError:
    QSCI_AVAILABLE = False
    class QsciScintilla(QPlainTextEdit):
        class EolMode:
            EolUnix = 1
        class MarginType:
            NumberMargin = 0
            SymbolMargin = 1
        class FoldStyle:
            PlainFoldStyle = 0
        class AutoCompletionSource:
            AcsAll = 0
        def setUtf8(self, *a): pass
        def setEolMode(self, *a): pass
        def setPaper(self, *a): pass
        def setColor(self, *a): pass
        def setCaretForegroundColor(self, *a): pass
        def setSelectionBackgroundColor(self, *a): pass
        def setMarginsBackgroundColor(self, *a): pass
        def setMarginsForegroundColor(self, *a): pass
        def setMarginsFont(self, *a): pass
        def setMarginWidth(self, *a): pass
        def setMarginType(self, *a): pass
        def setCaretWidth(self, *a): pass
        def setCaretLineVisible(self, *a): pass
        def setCaretLineBackgroundColor(self, *a): pass
        def setFolding(self, *a): pass
        def setFoldMarginColors(self, *a): pass
        def setAutoCompletionSource(self, *a): pass
        def setAutoCompletionThreshold(self, *a): pass
        def setAutoIndent(self, *a): pass
        def setIndentationsUseTabs(self, *a): pass
        def setTabWidth(self, *a): pass
        def zoomIn(self, *a): pass
        def zoomOut(self, *a): pass
        def setLexer(self, *a): pass
        def setText(self, text): self.setPlainText(text)
        def text(self): return self.toPlainText()
    class QsciLexerVerilog: pass
    class QsciLexerTCL: pass
    class QsciLexerVHDL: pass
    class QsciLexerPython: pass
    class QsciLexerCPP: pass

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
        if not QSCI_AVAILABLE:
            return
        lexer = None
        if ext in ['.v', '.sv', '.vh']:
            lexer = QsciLexerVerilog(self)
        elif ext in ['.tcl', '.sdc']:
            lexer = QsciLexerTCL(self)
        elif ext in ['.vhd', '.vhdl']:
            lexer = QsciLexerVHDL(self)
        elif ext in ['.py']:
            lexer = QsciLexerPython(self)
        elif ext in ['.c', '.cpp', '.cc', '.h', '.hpp']:
            lexer = QsciLexerCPP(self)
            
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

            # Customize VHDL colors manually
            if isinstance(lexer, QsciLexerVHDL):
                lexer.setColor(QColor(self.theme["kw"]), QsciLexerVHDL.Keyword)
                lexer.setFont(font_bold, QsciLexerVHDL.Keyword)
                lexer.setColor(QColor(self.theme["kw2"]), QsciLexerVHDL.StandardOperator)
                lexer.setColor(QColor(self.theme["str"]), QsciLexerVHDL.String)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerVHDL.Comment)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerVHDL.CommentLine)
                lexer.setColor(QColor(self.theme["num"]), QsciLexerVHDL.Number)
                lexer.setColor(QColor(self.theme["ident"]), QsciLexerVHDL.Identifier)

            # Customize Python colors manually
            if isinstance(lexer, QsciLexerPython):
                lexer.setColor(QColor(self.theme["kw"]), QsciLexerPython.Keyword)
                lexer.setFont(font_bold, QsciLexerPython.Keyword)
                lexer.setColor(QColor(self.theme["kw2"]), QsciLexerPython.HighlightedIdentifier)
                lexer.setColor(QColor(self.theme["str"]), QsciLexerPython.DoubleQuotedString)
                lexer.setColor(QColor(self.theme["str"]), QsciLexerPython.SingleQuotedString)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerPython.Comment)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerPython.CommentBlock)
                lexer.setColor(QColor(self.theme["num"]), QsciLexerPython.Number)
                lexer.setColor(QColor(self.theme["ident"]), QsciLexerPython.Identifier)

            # Customize C/C++ colors manually
            if isinstance(lexer, QsciLexerCPP):
                lexer.setColor(QColor(self.theme["kw"]), QsciLexerCPP.Keyword)
                lexer.setFont(font_bold, QsciLexerCPP.Keyword)
                lexer.setColor(QColor(self.theme["kw2"]), QsciLexerCPP.KeywordSet2)
                lexer.setColor(QColor(self.theme["str"]), QsciLexerCPP.DoubleQuotedString)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerCPP.Comment)
                lexer.setColor(QColor(self.theme["comment"]), QsciLexerCPP.CommentLine)
                lexer.setColor(QColor(self.theme["num"]), QsciLexerCPP.Number)
                lexer.setColor(QColor(self.theme["ident"]), QsciLexerCPP.Identifier)

            self.setLexer(lexer)


def _find_monaco_vs_path():
    """Detect the monaco-editor min/vs directory."""
    # 1. First priority: Bundled in editor/vs or third-party/monaco (AppImage ready & 100% offline)
    editor_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(editor_dir, ".."))
    fast_candidates = [
        os.path.join(editor_dir, "vs"),
        os.path.join(repo_root, "third-party", "monaco", "min", "vs"),
        os.path.join(repo_root, "third-party", "monaco", "node_modules", "monaco-editor", "min", "vs"),
    ]

    appdir = os.environ.get("APPDIR")
    if appdir:
        fast_candidates.extend([
            os.path.join(appdir, "editor", "vs"),
            os.path.join(appdir, "third-party", "monaco", "min", "vs"),
        ])

    for path in fast_candidates:
        if os.path.isdir(path):
            return path

    # 2. Common fallback filesystem locations before spawning slow subprocesses
    common_paths = [
        '/usr/local/lib/node_modules/monaco-editor/min/vs',
        '/usr/lib/node_modules/monaco-editor/min/vs',
    ]
    for path in common_paths:
        if os.path.isdir(path):
            return path

    # 3. Last-resort fallback: query npm (only if not found locally)
    try:
        import subprocess
        npm_root = subprocess.check_output(['npm', 'root', '-g'], stderr=subprocess.DEVNULL, timeout=0.5).decode().strip()
        cand = os.path.join(npm_root, 'monaco-editor', 'min', 'vs')
        if os.path.isdir(cand):
            return cand
    except Exception:
        pass

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
    def __init__(self, parent=None, ext=".v", font_family="Consolas", font_size=11, theme_name="Catppuccin Mocha", editor_backend=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        backend = (editor_backend or USER_SETTINGS.get("editor_backend", "qscintilla")).lower()
        if backend == "monaco":
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
        else:
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
        self.editor_backend = USER_SETTINGS.get("editor_backend", "qscintilla")
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
        editor = VSCodeEditor(
            ext=ext, font_family=self.font_family, font_size=self.font_size,
            theme_name=self.theme_name, editor_backend=self.editor_backend
        )
        with open(path, 'r') as f:
            editor.setPlainText(f.read())
        self.files[path] = editor
        idx = self.addTab(editor, os.path.basename(path))
        self.setTabToolTip(idx, path)
        self.setCurrentIndex(idx)

    def update_appearance(self, font_family, font_size, theme_name, editor_backend=None):
        self.font_family = font_family
        self.font_size = font_size
        self.theme_name = theme_name
        if editor_backend:
            self.editor_backend = editor_backend
        else:
            self.editor_backend = USER_SETTINGS.get("editor_backend", "qscintilla")
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
