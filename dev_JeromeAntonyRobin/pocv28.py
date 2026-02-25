import sys
import os
import subprocess
import threading
import queue
import glob
import re
import shutil
import json
import xml.etree.ElementTree as ET
from contextlib import suppress

# ================= PYQT6 IMPORTS =================
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QTreeView, 
                             QPlainTextEdit, QTextEdit, QToolBar, QPushButton, 
                             QLabel, QLineEdit, QFileDialog, QMessageBox, 
                             QInputDialog, QGraphicsView, QGraphicsScene, 
                             QGraphicsPixmapItem, QMenu, QFrame, QDockWidget,
                             QSizePolicy, QDialog, QFormLayout, QComboBox, QProgressBar)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QThread, QDir, QEvent, QUrl
from PyQt6.QtGui import (QAction, QFont, QColor, QSyntaxHighlighter, 
                         QTextCharFormat, QPixmap, QPainter, QImage,
                         QFileSystemModel, QKeySequence, QShortcut, QImageReader)

# --- CHROMIUM ENGINE CHECK ---
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    print("CRITICAL: PyQt6-WebEngine not found. Run 'pip install PyQt6-WebEngine'")

# ================= WORKER THREAD (PREVENTS FREEZING) =================

class SchematicWorker(QThread):
    """
    Runs Yosys and NetlistSVG in the background so the GUI doesn't hang.
    """
    finished = pyqtSignal(str) # Emits path to generated SVG
    log = pyqtSignal(str, str) # Emits (message, tag) for terminal

    def __init__(self, root, base, engine, src_files):
        super().__init__()
        self.root = root
        self.base = base
        self.engine = engine
        self.src_files = src_files

    def run(self):
        # 1. PREPARE COMMANDS
        # Detect if we need -sv flag for SystemVerilog
        read_cmd = ""
        for s in self.src_files:
            if s.endswith(".sv"): 
                read_cmd += f"read_verilog -sv {s}; "
            else: 
                read_cmd += f"read_verilog {s}; "

        # 2. ATTEMPT VECTOR ENGINE (NetlistSVG)
        use_netlist = (self.engine == "NetlistSVG") or (self.engine == "Auto" and shutil.which("netlistsvg"))
        
        if use_netlist:
            self.log.emit("Generating Vector Schematic (Background)...", "SYS")
            
            # Generate JSON
            cmd_json = f"yosys -p '{read_cmd} hierarchy -auto-top; proc; opt; write_json {self.base}.json'"
            subprocess.run(cmd_json, shell=True, cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            json_path = os.path.join(self.root, f"{self.base}.json")
            if os.path.exists(json_path):
                # High Memory Limit for RISC-V cores
                env = os.environ.copy()
                env["NODE_OPTIONS"] = "--max-old-space-size=4096"
                
                try:
                    # 30s Timeout to prevent infinite hangs on massive loops
                    res = subprocess.run(f"netlistsvg {self.base}.json -o {self.base}.svg", 
                                       shell=True, cwd=self.root, env=env, timeout=30,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    svg_path = os.path.join(self.root, f"{self.base}.svg")
                    if res.returncode == 0 and os.path.exists(svg_path):
                        self.patch_xml(svg_path)
                        self.finished.emit(svg_path)
                        return
                except subprocess.TimeoutExpired:
                    self.log.emit("Vector Engine Timed Out (Too Complex). Switching to Graphviz.", "WARN")
                except Exception as e:
                    self.log.emit(f"Vector Gen Failed: {e}", "WARN")

        # 3. FALLBACK: GRAPHVIZ (Industrial Mode)
        self.log.emit("Generating Industrial Schematic (Graphviz)...", "SYS")
        cmd_dot = f"yosys -p '{read_cmd} hierarchy -auto-top; proc; show -format dot -prefix {self.base}'"
        subprocess.run(cmd_dot, shell=True, cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        dot_path = os.path.join(self.root, f"{self.base}.dot")
        svg_path = os.path.join(self.root, f"{self.base}.svg")
        
        if os.path.exists(dot_path):
            subprocess.run(f"dot -Tsvg {dot_path} -o {self.base}.svg", shell=True, cwd=self.root)
            self.patch_xml(svg_path)
            self.finished.emit(svg_path)
        else:
            self.log.emit("Schematic Generation Failed completely.", "ERROR")

    def patch_xml(self, path):
        # Fix colors for Dark/Light mode compatibility using XML parsing
        if not os.path.exists(path): return
        try:
            ET.register_namespace('', "http://www.w3.org/2000/svg")
            ET.register_namespace('xlink', "http://www.w3.org/1999/xlink")
            tree = ET.parse(path)
            root = tree.getroot()
            
            def local_tag(elem): 
                return elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            for elem in root.iter():
                tag = local_tag(elem)
                # Force Black Lines / Text for visibility on White Background
                if tag in ['path', 'line', 'polyline']:
                    elem.attrib['stroke'] = 'black'
                    elem.attrib['stroke-width'] = '2'
                    elem.attrib['fill'] = 'none'
                    if 'style' in elem.attrib: del elem.attrib['style']
                elif tag == 'text':
                    elem.attrib['fill'] = 'black'
                    elem.attrib['stroke'] = 'none'
                    if 'style' in elem.attrib: del elem.attrib['style']
                elif tag in ['rect', 'circle', 'polygon', 'ellipse']:
                    elem.attrib['stroke'] = 'black'
                    elem.attrib['stroke-width'] = '2'
                    if 'style' in elem.attrib: del elem.attrib['style']
            tree.write(path)
        except Exception as e:
            self.log.emit(f"XML Patch Warning: {e}", "WARN")

# ================= CUSTOM WIDGETS =================

class SilisExplorer(QTreeView):
    fileOpened = pyqtSignal(str)
    dirChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(QDir.currentPath())
        self.setModel(self.fs_model)
        self.setRootIndex(self.fs_model.index(QDir.currentPath()))
        for i in range(1, 4): self.setColumnHidden(i, True)
        self.setHeaderHidden(True)
        self.setAnimated(False)
        self.setIndentation(15)
        self.setDragEnabled(False)

    def set_cwd(self, path):
        self.setRootIndex(self.fs_model.index(path))

    def keyPressEvent(self, event):
        idx = self.currentIndex()
        path = self.fs_model.filePath(idx)
        key = event.key()
        if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            if self.fs_model.isDir(idx): self.dirChanged.emit(path) 
            else: self.fileOpened.emit(path) 
        elif key in [Qt.Key.Key_Backspace, Qt.Key.Key_Escape]:
            self.dirChanged.emit(os.path.dirname(self.fs_model.filePath(self.rootIndex())))
        elif key == Qt.Key.Key_Delete: 
            self.ask_delete(path)
        else: 
            super().keyPressEvent(event)

    def ask_delete(self, path):
        if not path or not os.path.exists(path): return
        reply = QMessageBox.question(self, "Delete", f"Delete '{os.path.basename(path)}'?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try: 
                if os.path.isdir(path): shutil.rmtree(path)
                else: os.remove(path)
            except Exception as e: 
                QMessageBox.critical(self, "Error", f"{e}")

class SilisSchematic(QWidget):
    """
    Uses QWebEngineView (Chromium) to render massive SVGs without crashing.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        if HAS_WEBENGINE:
            self.browser = QWebEngineView()
            self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
            self.layout.addWidget(self.browser)
            
            # Loading Overlay
            self.loader_lbl = QLabel("Processing Hardware...", self.browser)
            self.loader_lbl.setStyleSheet("background: rgba(0,0,0,180); color: #00FF00; font-weight:bold; padding: 15px; border-radius: 5px;")
            self.loader_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.loader_lbl.hide()
        else:
            self.browser = None
            self.layout.addWidget(QLabel("CRITICAL: Install PyQt6-WebEngine"))

    def show_loader(self, show=True):
        if not self.browser: return
        if show:
            self.loader_lbl.resize(200, 50)
            self.loader_lbl.move(self.width()//2 - 100, self.height()//2 - 25)
            self.loader_lbl.show()
            self.loader_lbl.raise_()
        else: 
            self.loader_lbl.hide()

    def load_schematic(self, path):
        if not self.browser or not os.path.exists(path): return
        # Load local SVG into Chromium
        self.browser.setUrl(QUrl.fromLocalFile(os.path.abspath(path)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'loader_lbl'):
            self.loader_lbl.move(self.width()//2 - 100, self.height()//2 - 25)

class LineNumberArea(QWidget):
    def __init__(self, editor): 
        super().__init__(editor)
        self.codeEditor = editor
    def sizeHint(self): 
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)
    def paintEvent(self, event): 
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self.setFont(QFont("Consolas", 11))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance('9') * digits

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()): 
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(0, int(top), self.lineNumberArea.width() - 5, self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, str(blockNumber + 1))
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(Qt.GlobalColor.yellow).lighter(160))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

# ================= MAIN APPLICATION =================

class SilisIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silis QT v3.6 (Chromium + Threaded + Restore)")
        self.resize(1400, 900)
        
        self.cwd = os.getcwd()
        self.current_file = None
        self.pdk_path = ""
        self.schem_engine = "Auto"
        self.term_mode = "SHELL"
        self.queue = queue.Queue()
        
        self.sk_active = False
        self.sk_timer = QTimer()
        self.sk_timer.setSingleShot(True)
        self.sk_timer.timeout.connect(self.reset_sk)
        self.key_map = {"focus_editor":"c", "focus_terminal":"x", "focus_files":"v", "focus_schem":"z", "term_toggle":"s"}
        
        self.setup_ui()
        self.setup_toolbar()
        
        QApplication.instance().installEventFilter(self)
        
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(50)
        
        self.update_ui_labels()
        self.log_system(f"Silis Ready. CWD: {self.cwd}", "SYS")
        self.check_dependencies()

    def setup_ui(self):
        main_split = QSplitter(Qt.Orientation.Vertical)
        self.setCentralWidget(main_split)
        top_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(top_split)
        main_split.setStretchFactor(0, 4)
        
        # 1. EXPLORER
        self.explorer = SilisExplorer()
        self.explorer.dirChanged.connect(self.change_directory)
        self.explorer.fileOpened.connect(self.open_file_in_editor)
        self.explorer.doubleClicked.connect(lambda idx: self.on_tree_action(idx))
        exp_layout = QVBoxLayout(); widget_exp = QWidget(); widget_exp.setLayout(exp_layout); exp_layout.setContentsMargins(0,0,0,0)
        self.lbl_explorer = QLabel("Explorer"); self.lbl_explorer.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        exp_layout.addWidget(self.lbl_explorer); exp_layout.addWidget(self.explorer)
        top_split.addWidget(widget_exp)
        
        # 2. EDITOR
        self.editor = CodeEditor()
        ed_layout = QVBoxLayout(); widget_ed = QWidget(); widget_ed.setLayout(ed_layout); ed_layout.setContentsMargins(0,0,0,0)
        self.lbl_code = QLabel("Code"); self.lbl_code.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        ed_layout.addWidget(self.lbl_code); ed_layout.addWidget(self.editor)
        top_split.addWidget(widget_ed); top_split.setStretchFactor(1, 2)
        
        # 3. SCHEMATIC
        self.schematic = SilisSchematic()
        sch_layout = QVBoxLayout(); widget_sch = QWidget(); widget_sch.setLayout(sch_layout); sch_layout.setContentsMargins(0,0,0,0)
        self.lbl_schem = QLabel("Schematic"); self.lbl_schem.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        sch_layout.addWidget(self.lbl_schem); sch_layout.addWidget(self.schematic)
        top_split.addWidget(widget_sch); top_split.setStretchFactor(2, 1)
        
        bot_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(bot_split)
        main_split.setStretchFactor(1, 1)
        
        # 4. TERMINAL
        term_layout = QVBoxLayout(); widget_term = QWidget(); widget_term.setLayout(term_layout); term_layout.setContentsMargins(0,0,0,0)
        self.lbl_term = QLabel("Terminal"); self.lbl_term.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        self.term_log = QTextEdit(); self.term_log.setReadOnly(True); self.term_log.setStyleSheet("background: #1e1e1e; color: #e0e0e0; font-family: Consolas;")
        inp_layout = QHBoxLayout()
        self.mode_btn = QPushButton("[SHELL]"); self.mode_btn.setStyleSheet("background: #0d6efd; color: white; font-weight: bold;")
        self.mode_btn.clicked.connect(self.toggle_term_mode)
        self.term_input = QLineEdit(); self.term_input.setStyleSheet("background: #333; color: white; font-family: Consolas;")
        self.term_input.returnPressed.connect(self.handle_terminal_input)
        inp_layout.addWidget(self.mode_btn); inp_layout.addWidget(self.term_input)
        term_layout.addWidget(self.lbl_term); term_layout.addWidget(self.term_log); term_layout.addLayout(inp_layout)
        bot_split.addWidget(widget_term); bot_split.setStretchFactor(0, 2)
        
        # 5. VIOLATIONS
        viol_layout = QVBoxLayout(); widget_viol = QWidget(); widget_viol.setLayout(viol_layout); viol_layout.setContentsMargins(0,0,0,0)
        self.lbl_viol = QLabel("Violations"); self.lbl_viol.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        self.viol_log = QTextEdit(); self.viol_log.setReadOnly(True); self.viol_log.setStyleSheet("background: #2d2d2d; color: #ff5555; font-family: Consolas;")
        viol_layout.addWidget(self.lbl_viol); viol_layout.addWidget(self.viol_log)
        bot_split.addWidget(widget_viol); bot_split.setStretchFactor(1, 1)

    def setup_toolbar(self):
        self.tb = QToolBar(); self.addToolBar(self.tb)
        act_new = QAction("New", self); act_new.setShortcut("Ctrl+N"); act_new.triggered.connect(self.new_file); self.tb.addAction(act_new)
        act_save = QAction("Save", self); act_save.setShortcut("Ctrl+S"); act_save.triggered.connect(self.save_file); self.tb.addAction(act_save)
        self.tb.addSeparator()
        self.tb.addAction("F1 Compile", self.run_simulation)
        self.tb.addAction("F2 Waves", self.open_waves)
        self.tb.addAction("F3 Schem", self.generate_schematic)
        self.tb.addAction("F4 Synth", self.run_synthesis_flow)
        self.tb.addSeparator()
        self.btn_err = QPushButton("⚠️ Errors"); self.btn_err.setEnabled(False); self.btn_err.setStyleSheet("color:red; font-weight:bold")
        self.btn_err.clicked.connect(self.load_violation_log)
        self.tb.addWidget(self.btn_err)
        empty = QWidget(); empty.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding); self.tb.addWidget(empty)
        self.tb.addAction("⚙ Settings", self.open_settings)

    # ================= LOGIC =================
    
    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_QuoteLeft:
                self.sk_active = True; self.tb.setStyleSheet("background-color: #00FFFF;")
                self.sk_timer.start(1000); return True
            if self.sk_active:
                txt = event.text().lower()
                if txt == self.key_map["focus_editor"]: self.editor.setFocus()
                elif txt == self.key_map["focus_terminal"]: self.term_input.setFocus()
                elif txt == self.key_map["focus_files"]: self.explorer.setFocus()
                elif txt == self.key_map["focus_schem"]: 
                    if self.schematic.browser: self.schematic.browser.setFocus()
                elif txt == self.key_map["term_toggle"]: self.toggle_term_mode()
                self.reset_sk(); return True
        return super().eventFilter(source, event)

    def reset_sk(self):
        self.sk_active = False; self.tb.setStyleSheet("")

    def change_directory(self, path):
        if os.path.exists(path):
            os.chdir(path); self.cwd = os.getcwd(); self.explorer.set_cwd(self.cwd)
            self.log_system(f"CD -> {self.cwd}", "SYS")

    def on_tree_action(self, index):
        path = self.explorer.fs_model.filePath(index)
        if self.explorer.fs_model.isDir(index): self.change_directory(path)
        else: self.open_file_in_editor(path)

    def handle_terminal_input(self):
        cmd = self.term_input.text().strip(); self.term_input.clear()
        if not cmd: return
        self.log_system(f"$ {cmd}", "INPUT")
        if cmd.startswith("cd "): 
            target = cmd[3:].strip()
            self.change_directory(target if target else os.path.expanduser("~"))
            return
        
        def run():
            try:
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=self.cwd, bufsize=1)
                for line in iter(proc.stdout.readline, ''): self.queue.put(line.strip())
                proc.wait()
            except Exception as e: self.queue.put(f"[EXC] {e}")
        threading.Thread(target=run, daemon=True).start()

    def toggle_term_mode(self):
        self.term_mode = "SIM" if self.term_mode == "SHELL" else "SHELL"
        self.mode_btn.setText(f"[{self.term_mode}]")

    def log_system(self, msg, tag="SYS"):
        color = "#00FFFF"
        if "ERR" in tag or "FAIL" in msg: color = "#FF5555"
        elif "WARN" in tag: color = "#F1FA8C"
        elif "SUCCESS" in tag: color = "#50FA7B"
        elif "INPUT" in tag: color = "#FFFFFF"
        self.term_log.append(f'<span style="color:{color};">[{tag}] {msg}</span>')
        self.term_log.verticalScrollBar().setValue(self.term_log.verticalScrollBar().maximum())

    def process_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            if isinstance(msg, tuple):
                if msg[0] == "HARVEST": self.harvest_logs(msg[1])
            elif msg == "PARSE": self.parse_summary()
            else: self.log_system(str(msg).strip(), "SYS")

    def get_context(self):
        content = self.editor.toPlainText()
        m = re.search(r'module\s+(\w+)', content)
        if not m: return None, None
        return m.group(1), m.group(1).replace("tb_", "").replace("_tb", "")

    def get_proj_root(self, base):
        pname = f"{base}_project"
        cwd = os.path.abspath(self.cwd)
        if os.path.basename(cwd) == pname: return cwd
        if os.path.basename(cwd) in ["source", "netlist"]: return os.path.dirname(cwd)
        return os.path.join(cwd, pname)

    def prep_workspace(self, base):
        root = self.get_proj_root(base)
        src_dir = os.path.join(root, "source")
        for d in ["source", "netlist", "reports"]: os.makedirs(os.path.join(root, d), exist_ok=True)
        
        # Surgical File Move
        files = [f"{base}.v", f"tb_{base}.v", f"{base}_tb.v", f"test_{base}.v", f"{base}.sv"]
        dirs = list(set([os.path.abspath(self.cwd), root]))
        
        for f in files:
            if os.path.exists(os.path.join(src_dir, f)): continue
            found_src = None
            for d in dirs:
                if os.path.exists(os.path.join(d, f)): found_src = os.path.join(d, f); break
            
            if found_src:
                dst = os.path.join(src_dir, f)
                try:
                    shutil.move(found_src, dst)
                    if self.current_file and os.path.abspath(self.current_file) == found_src: 
                        self.current_file = dst
                        self.setWindowTitle(f"Silis - {f} (Moved)")
                        self.log_system(f"Moved active {f} -> source/", "SYS")
                    else:
                        self.log_system(f"Moved {f} -> source/", "SYS")
                except: pass
        return root

    def run_simulation(self):
        if self.current_file: self.save_file()
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        
        src = glob.glob(os.path.join(root, "source", "*.v")) + glob.glob(os.path.join(root, "source", "*.sv"))
        if not src: self.log_system("No sources!", "ERROR"); return
        
        out = f"{base}.out"
        cmd = ["iverilog", "-g2012", "-o", out] + src
        
        def task():
            try:
                self.queue.put("[SYS] Compiling...")
                res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
                if res.returncode != 0: 
                    self.queue.put(f"[ERROR] Compile:\n{res.stderr}"); return
                self.queue.put("[SYS] Simulating...")
                subprocess.run(["vvp", out], cwd=root, stdout=subprocess.PIPE)
                self.queue.put("[SYS] Done.")
            except Exception as e: self.queue.put(f"[ERROR] {e}")
        threading.Thread(target=task, daemon=True).start()

    def run_synthesis_flow(self):
        if not self.pdk_path: return QMessageBox.warning(self, "Err", "Set PDK Path!")
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        
        srcs = [s for s in glob.glob(os.path.join(root, "source", "*.v")) + glob.glob(os.path.join(root, "source", "*.sv")) if "tb_" not in s]
        
        read_cmd = ""
        for s in srcs:
            if s.endswith(".sv"): read_cmd += f"read_verilog -sv {s}\n"
            else: read_cmd += f"read_verilog {s}\n"

        ys = f"read_liberty -lib {self.pdk_path}\n{read_cmd}\nsynth -top {base}\ndfflibmap -liberty {self.pdk_path}\nabc -liberty {self.pdk_path}\nwrite_verilog -noattr netlist/{base}_netlist.v"
        
        with open(os.path.join(root, "synth.ys"), 'w') as f: f.write(ys)
        
        def task():
            try:
                self.queue.put("[SYS] Synthesizing...")
                subprocess.run(f"yosys synth.ys", shell=True, cwd=root, stdout=subprocess.DEVNULL)
                self.queue.put("[SYS] Flow Complete.")
            except: pass
        threading.Thread(target=task, daemon=True).start()

    # --- SCHEMATIC GENERATION (THREADED & CHROMIUM) ---
    def generate_schematic(self):
        if self.current_file: self.save_file()
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        
        srcs = [s for s in glob.glob(os.path.join(root, "source", "*.v")) + glob.glob(os.path.join(root, "source", "*.sv")) if "tb_" not in s]
        if not srcs: self.log_system("No design files.", "ERROR"); return

        # Show Loading UI
        self.schematic.show_loader(True)
        self.log_system("Starting Schematic Gen (Threaded)...", "SYS")
        
        # Start Worker
        self.worker = SchematicWorker(root, base, self.schem_engine, srcs)
        self.worker.log.connect(self.log_system)
        self.worker.finished.connect(self.on_schematic_ready)
        self.worker.start()

    def on_schematic_ready(self, path):
        self.schematic.show_loader(False)
        self.schematic.load_schematic(path)
        self.log_system(f"Schematic Loaded: {os.path.basename(path)}", "SUCCESS")

    # ================= COMMON =================
    def new_file(self): 
        self.current_file=None
        self.editor.clear()

    def save_file(self):
        if not self.current_file: 
            f, _ = QFileDialog.getSaveFileName(self, "Save", self.cwd)
            if f: self.current_file = f
        if self.current_file: 
            with open(self.current_file, 'w') as f: f.write(self.editor.toPlainText())
            self.log_system(f"Saved {os.path.basename(self.current_file)}", "SUCCESS")

    def open_file_in_editor(self, path):
        if not os.path.exists(path): return
        with open(path) as f: self.editor.setPlainText(f.read())
        self.current_file = path
        self.setWindowTitle(f"Silis - {os.path.basename(path)}")

    def open_settings(self):
        d = QDialog(self)
        l = QFormLayout(d)
        e_pdk = QLineEdit(self.pdk_path)
        l.addRow("PDK:", e_pdk)
        combo = QComboBox()
        combo.addItems(["Auto", "Graphviz", "NetlistSVG"])
        combo.setCurrentText(self.schem_engine)
        l.addRow("Engine:", combo)
        
        def save(): 
            self.pdk_path = e_pdk.text()
            self.schem_engine = combo.currentText()
            d.accept()
        
        btn = QPushButton("Save")
        btn.clicked.connect(save)
        l.addRow(btn)
        d.exec()

    def harvest_logs(self, root):
        self.viol_log.clear()
        found = False
        for log in ["reports/synthesis.log", "reports/sta.log"]:
            p = os.path.join(root, log)
            if os.path.exists(p):
                self.viol_log.append(f"--- {log} ---")
                with open(p) as f:
                    for l in f:
                        if any(x in l for x in ["Error", "Warning"]):
                            self.viol_log.append(l.strip()); found = True
        self.btn_err.setEnabled(found)
        if found: self.log_system("Violations Found!", "WARN")

    def open_waves(self):
        vcds = glob.glob(os.path.join(self.cwd, "*.vcd"))
        if vcds: subprocess.Popen(["gtkwave", max(vcds, key=os.path.getctime)], cwd=self.cwd)

    def check_dependencies(self):
        if not shutil.which("sta"): self.log_system("OpenSTA not found!", "ERR")

    def load_violation_log(self): 
        self.harvest_logs(self.cwd)

    def update_ui_labels(self):
        self.lbl_explorer.setText(f"Explorer (`+{self.key_map['focus_files']})")
        self.lbl_code.setText(f"Code (`+{self.key_map['focus_editor']})")
        self.lbl_schem.setText(f"Schematic (`+{self.key_map['focus_schem']})")
        self.lbl_term.setText(f"Terminal (`+{self.key_map['focus_terminal']})")

if __name__ == "__main__":
    QImageReader.setAllocationLimit(0)
    app = QApplication(sys.argv)
    w = SilisIDE()
    w.show()
    sys.exit(app.exec())