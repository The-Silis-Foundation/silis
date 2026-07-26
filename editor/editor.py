import os
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


class VSCodeEditor(QWidget):
    def __init__(self, parent=None, ext=".v", font_family="Consolas", font_size=11, theme_name="Catppuccin Mocha"):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.editor = ScintillaEditor(is_minimap=False, font_family=font_family, font_size=font_size, theme_name=theme_name)
        self.editor.set_lexer(ext)
        self.layout.addWidget(self.editor)
        
    def setPlainText(self, text):
        self.editor.setText(text)
        
    def toPlainText(self):
        return self.editor.text()


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
