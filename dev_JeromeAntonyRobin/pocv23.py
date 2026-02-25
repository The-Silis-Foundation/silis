#!!!!!!!!!!!!!!!!!!!WORKS FLAWLESSLY, LATEST STABLE VERSION, ONLY GRAPHVIZ ENGINE WORKS!!!!!!!!!!!!!!

import sys
import os
import subprocess
import threading
import queue
import glob
import re
import shutil
import json
from contextlib import suppress

# ================= PYQT6 IMPORTS =================
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QTreeView, 
                             QPlainTextEdit, QTextEdit, QToolBar, QPushButton, 
                             QLabel, QLineEdit, QFileDialog, QMessageBox, 
                             QInputDialog, QGraphicsView, QGraphicsScene, 
                             QGraphicsPixmapItem, QMenu, QFrame, QDockWidget,
                             QSizePolicy, QDialog, QFormLayout, QComboBox)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QThread, QDir, QEvent
from PyQt6.QtGui import (QAction, QFont, QColor, QSyntaxHighlighter, 
                         QTextCharFormat, QPixmap, QPainter, QImage,
                         QFileSystemModel, QKeySequence, QShortcut, QImageReader)

# NEW: SVG Support
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtSvg import QSvgRenderer

# ================= CUSTOM WIDGETS =================

class SilisExplorer(QTreeView):
    """
    Restores keyboard navigation:
    - Enter: Open File / Enter Dir
    - Backspace/Escape: Go Up Dir
    """
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
            event.accept()
        elif key in [Qt.Key.Key_Backspace, Qt.Key.Key_Escape]:
            parent_dir = os.path.dirname(self.fs_model.filePath(self.rootIndex()))
            self.dirChanged.emit(parent_dir)
            event.accept()
        else:
            super().keyPressEvent(event)

class SilisSchematic(QGraphicsView):
    """
    Vector-Based Schematic Viewer (SVG)
    Handles infinite zoom without OOM crashes.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor("#f0f0f0"))
        
        # High Quality Rendering for Vectors
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    def load_schematic(self, path):
        self.scene.clear()
        if path.endswith(".svg"):
            item = QGraphicsSvgItem(path)
            self.scene.addItem(item)
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            # Fallback for PNG if needed
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.scene.addPixmap(pixmap)
                self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0: self.scale(1.25, 1.25)
        else: self.scale(0.8, 0.8)

    def keyPressEvent(self, event):
        key = event.key()
        if key in [Qt.Key.Key_Plus, Qt.Key.Key_Equal]: self.scale(1.2, 1.2)
        elif key == Qt.Key.Key_Minus: self.scale(0.8, 0.8)
        elif key == Qt.Key.Key_Left: self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 20)
        elif key == Qt.Key.Key_Right: self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 20)
        elif key == Qt.Key.Key_Up: self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 20)
        elif key == Qt.Key.Key_Down: self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 20)
        else: super().keyPressEvent(event)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor); self.codeEditor = editor
    def sizeHint(self): return QSize(self.codeEditor.lineNumberAreaWidth(), 0)
    def paintEvent(self, event): self.codeEditor.lineNumberAreaPaintEvent(event)

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
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()): self.updateLineNumberAreaWidth(0)

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
                number = str(blockNumber + 1)
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(0, int(top), self.lineNumberArea.width() - 5, self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)
            block = block.next(); top = bottom; bottom = top + self.blockBoundingRect(block).height(); blockNumber += 1

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
        self.setWindowTitle("Silis QT v2.4 (Vector Engine)")
        self.resize(1400, 900)
        
        # --- STATE ---
        self.cwd = os.getcwd()
        self.current_file = None
        self.pdk_path = ""
        self.schem_engine = "Auto"
        self.term_mode = "SHELL"
        self.queue = queue.Queue()
        
        # --- SUPERKEY ---
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
        main_split.addWidget(top_split); main_split.setStretchFactor(0, 4)
        
        # EXPLORER
        self.explorer = SilisExplorer()
        self.explorer.dirChanged.connect(self.change_directory)
        self.explorer.fileOpened.connect(self.open_file_in_editor)
        self.explorer.doubleClicked.connect(lambda idx: self.on_tree_action(idx))
        exp_layout = QVBoxLayout(); widget_exp = QWidget(); widget_exp.setLayout(exp_layout); exp_layout.setContentsMargins(0,0,0,0)
        self.lbl_explorer = QLabel("Explorer"); self.lbl_explorer.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        exp_layout.addWidget(self.lbl_explorer); exp_layout.addWidget(self.explorer)
        top_split.addWidget(widget_exp)
        
        # EDITOR
        self.editor = CodeEditor()
        ed_layout = QVBoxLayout(); widget_ed = QWidget(); widget_ed.setLayout(ed_layout); ed_layout.setContentsMargins(0,0,0,0)
        self.lbl_code = QLabel("Code"); self.lbl_code.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        ed_layout.addWidget(self.lbl_code); ed_layout.addWidget(self.editor)
        top_split.addWidget(widget_ed); top_split.setStretchFactor(1, 2)
        
        # SCHEMATIC (SVG Enabled)
        self.schematic = SilisSchematic()
        sch_layout = QVBoxLayout(); widget_sch = QWidget(); widget_sch.setLayout(sch_layout); sch_layout.setContentsMargins(0,0,0,0)
        self.lbl_schem = QLabel("Schematic"); self.lbl_schem.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        sch_layout.addWidget(self.lbl_schem); sch_layout.addWidget(self.schematic)
        top_split.addWidget(widget_sch); top_split.setStretchFactor(2, 1)
        
        # DASHBOARD
        bot_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(bot_split); main_split.setStretchFactor(1, 1)
        
        # Terminal
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
        
        # Violations
        viol_layout = QVBoxLayout(); widget_viol = QWidget(); widget_viol.setLayout(viol_layout); viol_layout.setContentsMargins(0,0,0,0)
        self.lbl_viol = QLabel("Violations"); self.lbl_viol.setStyleSheet("background: #ddd; font-weight: bold; padding: 4px;")
        self.viol_log = QTextEdit(); self.viol_log.setReadOnly(True); self.viol_log.setStyleSheet("background: #2d2d2d; color: #ff5555; font-family: Consolas;")
        viol_layout.addWidget(self.lbl_viol); viol_layout.addWidget(self.viol_log)
        bot_split.addWidget(widget_viol); bot_split.setStretchFactor(1, 1)

    def setup_toolbar(self):
        self.tb = QToolBar(); self.addToolBar(self.tb)
        self.tb.addAction("New", self.new_file); self.tb.addAction("Save", self.save_file)
        self.tb.addSeparator()
        self.tb.addAction("F1 Compile", self.run_simulation); self.tb.addAction("F2 Waves", self.open_waves)
        self.tb.addAction("F3 Schem", self.generate_schematic); self.tb.addAction("F4 Synth", self.run_synthesis_flow)
        self.tb.addSeparator()
        self.btn_err = QPushButton("⚠️ Errors"); self.btn_err.setEnabled(False); self.btn_err.setStyleSheet("color:red; font-weight:bold")
        self.btn_err.clicked.connect(self.load_violation_log)
        self.tb.addWidget(self.btn_err)
        empty = QWidget(); empty.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tb.addWidget(empty)
        self.tb.addAction("⚙ Settings", self.open_settings)

    # ================= LOGIC & UTILS =================
    
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
                elif txt == self.key_map["focus_schem"]: self.schematic.setFocus()
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
            if target == "..": target = os.path.dirname(self.cwd)
            elif target == "~": target = os.path.expanduser("~")
            else: target = os.path.join(self.cwd, target)
            self.change_directory(target); return

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
        for d in ["source", "netlist", "reports"]: os.makedirs(os.path.join(root, d), exist_ok=True)
        return root

    # --- SIMULATION ---
    def run_simulation(self):
        if self.current_file: self.save_file()
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        src = glob.glob(os.path.join(root, "source", "*.v"))
        out = f"{base}.out"
        cmd = ["iverilog", "-o", out] + src
        def task():
            try:
                self.queue.put("[SYS] Compiling...")
                res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
                if res.returncode != 0: 
                    self.queue.put(f"[ERROR] Compile:\n{res.stderr}"); return
                self.queue.put("[SYS] Simulating...")
                proc = subprocess.Popen(["vvp", out], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(proc.stdout.readline, ''): self.queue.put(line.strip())
                proc.wait()
                self.queue.put("[SYS] Simulation Finished.")
            except Exception as e: self.queue.put(f"[ERROR] {e}")
        threading.Thread(target=task, daemon=True).start()

    def run_synthesis_flow(self):
        if not self.pdk_path: return QMessageBox.warning(self, "Err", "Set PDK Path!")
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        sdc = os.path.join(root, "netlist", f"{base}.sdc")
        if not os.path.exists(sdc):
            with open(sdc, 'w') as f: f.write(f"# SDC for {base}\n")
            self.open_file_in_editor(sdc)
            self.log_system("Empty SDC created. Edit & Re-run.", "WARN"); return

        v_net = f"netlist/{base}_netlist.v"
        srcs = glob.glob(os.path.join(root, "source", "*.v"))
        srcs = [s for s in srcs if "tb_" not in s]
        ys = f"read_liberty -lib {self.pdk_path}\nread_verilog {' '.join(srcs)}\nsynth -top {base}\ndfflibmap -liberty {self.pdk_path}\nabc -liberty {self.pdk_path}\ntee -o reports/area.rpt stat -liberty {self.pdk_path} -json\nwrite_verilog -noattr {v_net}"
        with open(os.path.join(root, "synth.ys"), 'w') as f: f.write(ys)
        tcl = f"read_liberty {self.pdk_path}\nread_verilog {v_net}\nlink_design {base}\nread_sdc netlist/{base}.sdc\nreport_checks\nreport_power\nexit"
        with open(os.path.join(root, "sta.tcl"), 'w') as f: f.write(tcl)

        def task():
            try:
                self.queue.put("[SYS] Synthesizing...")
                p1 = subprocess.Popen(f"yosys synth.ys | tee reports/synthesis.log", shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(p1.stdout.readline, ''): self.queue.put(line.strip())
                p1.wait()
                self.queue.put("[SYS] Timing Analysis...")
                p2 = subprocess.Popen(f"sta sta.tcl < /dev/null | tee reports/sta.log", shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(p2.stdout.readline, ''): self.queue.put(line.strip())
                p2.wait()
                self.queue.put(("HARVEST", root)); self.queue.put("PARSE")
            except Exception as e: self.queue.put(f"[ERROR] {e}")
        threading.Thread(target=task, daemon=True).start()

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

    def parse_summary(self):
        self.log_system("Flow Complete. Check Reports.", "SUCCESS")

    def open_waves(self):
        vcds = glob.glob(os.path.join(self.cwd, "*.vcd"))
        if vcds: subprocess.Popen(["gtkwave", max(vcds, key=os.path.getctime)], cwd=self.cwd)

    # --- SCHEMATIC GENERATION (VECTOR PIVOT) ---
    def generate_schematic(self):
        if self.current_file: self.save_file()
        _, base = self.get_context()
        if not base: return
        root = self.prep_workspace(base)
        
        # 1. Filter: Exclude TBs
        src_dir = os.path.join(root, "source")
        all_v = glob.glob(os.path.join(src_dir, "*.v"))
        synth_files = [f for f in all_v if not ("tb_" in f or "_tb" in f or "test_" in f)]
        
        if not synth_files:
            self.log_system("No design files found.", "ERROR"); return

        # 2. Generate SVG (Not PNG)
        self.log_system(f"Generating Vector Schematic...", "SYS")
        
        # Generate JSON first (standard intermediate) or DOT directly to SVG
        # We use dot -> SVG for reliability
        cmd = f"yosys -p 'read_verilog {' '.join(synth_files)}; hierarchy -auto-top; proc; show -format dot -prefix {base}'"
        subprocess.run(cmd, shell=True, cwd=root)
        
        dot_path = os.path.join(root, f"{base}.dot")
        if os.path.exists(dot_path):
            # Convert DOT -> SVG
            svg_path = os.path.join(root, f"{base}.svg")
            subprocess.run(f"dot -Tsvg {dot_path} -o {svg_path}", shell=True, cwd=root)
            
            # Load SVG into Viewer
            self.schematic.load_schematic(svg_path)
        else:
            self.log_system("Schematic Failed.", "ERROR")

    # ================= COMMON =================
    def new_file(self): self.current_file=None; self.editor.clear()
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
        self.current_file = path; self.setWindowTitle(f"Silis - {os.path.basename(path)}")

    def open_settings(self):
        d = QDialog(self); l = QFormLayout(d)
        e_pdk = QLineEdit(self.pdk_path)
        btn = QPushButton("Browse"); btn.clicked.connect(lambda: e_pdk.setText(QFileDialog.getOpenFileName()[0]))
        l.addRow("PDK:", e_pdk); l.addRow(btn)
        sk_ed = {}
        for k, v in self.key_map.items():
            sk_ed[k] = QLineEdit(v); l.addRow(k, sk_ed[k])
        def save():
            self.pdk_path = e_pdk.text()
            for k, w in sk_ed.items(): self.key_map[k] = w.text()
            self.update_ui_labels(); d.accept()
        btn_s = QPushButton("Save"); btn_s.clicked.connect(save); l.addRow(btn_s)
        d.exec()

    def update_ui_labels(self):
        self.lbl_explorer.setText(f"Explorer (`+{self.key_map['focus_files']})")
        self.lbl_code.setText(f"Code (`+{self.key_map['focus_editor']})")
        self.lbl_schem.setText(f"Schematic (`+{self.key_map['focus_schem']})")
        self.lbl_term.setText(f"Terminal (`+{self.key_map['focus_terminal']})")
        
    def check_dependencies(self):
        if not shutil.which("sta"): self.log_system("OpenSTA not found!", "ERR")

    def load_violation_log(self): self.harvest_logs(self.cwd)

if __name__ == "__main__":
    # DISABLE ALLOCATION LIMIT (SAFETY OFF)
    QImageReader.setAllocationLimit(0)
    
    app = QApplication(sys.argv)
    w = SilisIDE()
    w.show()
    sys.exit(app.exec())