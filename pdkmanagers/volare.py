import subprocess
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *

class VolareWorker(QThread):
    finished = pyqtSignal(str, str) # cmd_type, output
    log = pyqtSignal(str)

    def __init__(self, cmd_type, args=[]):
        super().__init__()
        self.cmd_type = cmd_type
        self.args = args

    def run(self):
        cmd = ["volare"] + self.args
        try:
            self.log.emit(f"[VOLARE] Running: {' '.join(cmd)}...")
            
            # Run Subprocess
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            out, _ = proc.communicate()
            
            # === [FIX] Graceful Handling for "Not Found" ===
            if proc.returncode != 0:
                # If checking path/active fails, it just means it's not installed yet.
                # Don't treat it as a crash.
                if self.cmd_type in ["path", "output"]:
                    self.finished.emit(self.cmd_type, "Not Installed / Not Configured")
                    return

                # Real Error for other commands
                self.log.emit(f"[VOLARE] Error (Code {proc.returncode}):\n{out}")
                self.finished.emit("error", out)
            else:
                self.finished.emit(self.cmd_type, out)
                
        except FileNotFoundError:
            self.finished.emit("error", "Volare executable not found. Please install: pip install volare")
        except Exception as e:
            self.finished.emit("error", str(e))


class VolareManagerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # --- 1. PDK Selector ---
        top_frame = QFrame()
        top_frame.setStyleSheet("background: #e1e4e8; padding: 5px; border-radius: 4px;")
        hl = QHBoxLayout(top_frame)
        
        self.combo_pdk = QComboBox()
        self.combo_pdk.addItems(["sky130", "gf180mcu"])
        
        hl.addWidget(QLabel("<b>Target PDK Family:</b>"))
        hl.addWidget(self.combo_pdk)
        hl.addStretch()
        self.layout.addWidget(top_frame)

        # --- 2. Raw Output Display (The Terminal) ---
        self.term = QTextEdit()
        self.term.setReadOnly(True)
        self.term.setStyleSheet("background: #1e1e1e; color: #00ff00; font-family: Consolas; font-size: 10pt;")
        self.term.setPlaceholderText("Volare output will appear here...")
        self.layout.addWidget(self.term)

        # --- 3. Command Grid ---
        btn_grid = QGridLayout()
        
        # Row 1: Information
        btn_ls = QPushButton("List Installed (ls)"); btn_ls.clicked.connect(lambda: self.run_volare("ls"))
        btn_rem = QPushButton("List Remote (ls-remote)"); btn_rem.clicked.connect(lambda: self.run_volare("ls-remote"))
        btn_path = QPushButton("Show Path"); btn_path.clicked.connect(lambda: self.run_volare("path"))
        btn_curr = QPushButton("Show Active"); btn_curr.clicked.connect(lambda: self.run_volare("output"))
        
        # Row 2: Actions
        btn_enable = QPushButton("⚡ Enable Version..."); btn_enable.clicked.connect(self.ask_enable)
        btn_enable.setStyleSheet("background: #2da44e; color: white; font-weight: bold;")
        
        btn_build = QPushButton("⬇ Build/Install..."); btn_build.clicked.connect(self.ask_build)
        btn_build.setStyleSheet("background: #00509d; color: white; font-weight: bold;")
        
        btn_prune = QPushButton("✂ Prune Old"); btn_prune.clicked.connect(self.ask_prune)
        
        btn_grid.addWidget(btn_ls, 0, 0)
        btn_grid.addWidget(btn_rem, 0, 1)
        btn_grid.addWidget(btn_path, 0, 2)
        btn_grid.addWidget(btn_curr, 0, 3)
        
        btn_grid.addWidget(btn_enable, 1, 0, 1, 2) # Span 2 cols
        btn_grid.addWidget(btn_build, 1, 2, 1, 2)
        btn_grid.addWidget(btn_prune, 2, 0, 1, 4)

        self.layout.addLayout(btn_grid)
        
        # --- 4. Manual Command Line ---
        bg_cmd = QHBoxLayout()
        self.cmd_in = QLineEdit()
        self.cmd_in.setPlaceholderText("Manual arguments (e.g. enable <hash>)")
        self.cmd_in.returnPressed.connect(self.run_manual)
        btn_run = QPushButton("Run Manual"); btn_run.clicked.connect(self.run_manual)
        
        bg_cmd.addWidget(QLabel("Manual:"))
        bg_cmd.addWidget(self.cmd_in)
        bg_cmd.addWidget(btn_run)
        self.layout.addLayout(bg_cmd)

    def log(self, text):
        self.term.append(text)
        self.term.verticalScrollBar().setValue(self.term.verticalScrollBar().maximum())

    def run_volare(self, action, extra_args=[]):
        pdk = self.combo_pdk.currentText()
        args = [action, "--pdk", pdk] + extra_args
        
        self.term.append(f"\n> volare {' '.join(args)}")
        
        self.worker = VolareWorker(action, args)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(lambda _, out: self.log(f"\n[DONE]\n{out}"))
        self.worker.start()

    def ask_enable(self):
        text, ok = QInputDialog.getText(self, "Enable Version", "Enter Version Hash (or tag):")
        if ok and text:
            self.run_volare("enable", [text])

    def ask_build(self):
        text, ok = QInputDialog.getText(self, "Build/Install", "Enter Version Hash to Install:")
        if ok and text:
            self.run_volare("build", [text])

    def ask_prune(self):
        if QMessageBox.question(self, "Prune", "Delete all UNUSED versions?") == QMessageBox.StandardButton.Yes:
            self.run_volare("prune")

    def run_manual(self):
        txt = self.cmd_in.text().strip()
        if txt:
            self.run_volare(txt.split()[0], txt.split()[1:])
            self.cmd_in.clear()


