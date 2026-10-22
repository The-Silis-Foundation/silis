"""
signalpeeker/code.py
VCD waveform viewer — VCDParser, WaveformCanvas, SignalPeeker
"""
import os
import glob
import subprocess
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *


class VCDParser:
    def __init__(self, path):
        self.signals = {}
        self.names = {}
        self.widths = {}
        self.id_map = {}
        self.end_time = 0
        self.timescale = "1ns"
        if os.path.exists(path): self.parse(path)

    def parse(self, path):
        curr_t = 0
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if line.startswith("$var"):
                        parts = line.split()
                        if len(parts) >= 5:
                            width = int(parts[2])
                            sid = parts[3]
                            name = parts[4]
                            self.names[sid] = name
                            self.widths[sid] = width
                            self.signals[sid] = []
                            self.id_map[name] = sid
                    elif line.startswith("$timescale"):
                        if len(line.split()) > 1: self.timescale = line.split()[1]
                    elif line.startswith("$enddefinitions"):
                        break
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if line.startswith("#"):
                        try:
                            curr_t = int(line[1:])
                            self.end_time = max(self.end_time, curr_t)
                        except: pass
                    elif line.startswith("$dumpvars") or line.startswith("$end"):
                        continue
                    else:
                        if line.startswith('b'):
                            parts = line.split()
                            if len(parts) < 2: continue
                            val_bin = parts[0][1:]
                            sid = parts[1]
                            if sid in self.signals:
                                try:
                                    val_hex = hex(int(val_bin, 2))[2:].upper()
                                    if len(val_hex) > 1 and len(val_hex) % 2 != 0: val_hex = "0" + val_hex
                                except:
                                    val_hex = "X" if 'x' in val_bin else "Z"
                                sig = self.signals[sid]
                                if not sig or sig[-1][1] != val_hex:
                                    sig.append((curr_t, val_hex))
                        else:
                            if len(line) < 2: continue
                            val = line[0]
                            sid = line[1:].strip()
                            if sid in self.signals:
                                sig = self.signals[sid]
                                if not sig or sig[-1][1] != val:
                                    sig.append((curr_t, val))
        except Exception as e: print(f"VCD Parse Error (Non-Fatal): {e}")


class WaveformCanvas(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.data = None
        self.zoom = 1.0
        self.offset_x = 0
        self.cursor_time = 0
        self.sidebar_width = 180
        self.selected_row = 0
        self.visible_ids = []
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_data(self, parser):
        self.data = parser
        if self.data:
            self.visible_ids = list(self.data.signals.keys())
            total_h = (len(self.visible_ids) * 40) + 60
            self.setMinimumHeight(total_h)
            self.resize(self.width(), total_h)
        self.update()

    def format_time(self, t):
        return f"{t} {self.data.timescale}" if self.data else f"{t}"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1e1e1e"))
        painter.fillRect(0, 0, self.sidebar_width, self.height(), QColor("#252526"))
        if not self.data:
            painter.setPen(QColor("#666"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Waveform Loaded")
            return
        row_h = 40
        highlight_y = (self.selected_row * row_h) + 30
        painter.fillRect(0, highlight_y, self.width(), row_h, QColor(255, 255, 255, 15))
        painter.setPen(QPen(QColor("#333333"), 1, Qt.PenStyle.DotLine))
        for x in range(self.sidebar_width, self.width(), 100):
            painter.drawLine(x, 0, x, self.height())
        y = 40
        font_main = QFont("Consolas", 10); painter.setFont(font_main)
        for i, sid in enumerate(self.visible_ids):
            name = self.data.names[sid]
            width = self.data.widths[sid]
            trans = self.data.signals[sid]
            if i == self.selected_row: painter.setPen(QColor("#ffffff"))
            else: painter.setPen(QColor("#aaaaaa"))
            label = f"{name} [{width}]" if width > 1 else name
            elided = self.fontMetrics().elidedText(label, Qt.TextElideMode.ElideMiddle, self.sidebar_width - 10)
            painter.drawText(10, y + 5, elided)
            prev_x = self.sidebar_width - self.offset_x
            prev_val = 'x'
            if trans and trans[0][0] == 0: prev_val = trans[0][1]
            elif trans: prev_val = 'x'
            draw_trans = trans + [(self.data.end_time, prev_val)]
            for t, val in draw_trans:
                x_pos = self.sidebar_width + (t * self.zoom) - self.offset_x
                if x_pos < self.sidebar_width:
                    prev_x = max(self.sidebar_width, x_pos); prev_val = val; continue
                if prev_x > self.width(): break
                if width == 1:
                    if prev_val == '1': c = QColor("#4EC9B0"); h_curr = y - 10
                    elif prev_val == '0': c = QColor("#2c5d52"); h_curr = y + 10
                    elif prev_val in ['z', 'Z']: c = QColor("#dcdcaa"); h_curr = y
                    else: c = QColor("#f44747"); h_curr = y
                    painter.setPen(QPen(c, 2))
                    painter.drawLine(int(prev_x), int(h_curr), int(x_pos), int(h_curr))
                    if val != prev_val:
                        h_next = y - 10 if val == '1' else (y + 10 if val == '0' else y)
                        painter.setPen(QColor("#555"))
                        painter.drawLine(int(x_pos), int(h_curr), int(x_pos), int(h_next))
                else:
                    is_valid = not ('X' in str(prev_val) or 'Z' in str(prev_val))
                    c_bus = QColor("#4EC9B0") if is_valid else QColor("#f44747")
                    path = QPainterPath()
                    path.moveTo(prev_x, y)
                    path.lineTo(prev_x + 4, y - 8)
                    path.lineTo(x_pos - 4, y - 8)
                    path.lineTo(x_pos, y)
                    path.lineTo(x_pos - 4, y + 8)
                    path.lineTo(prev_x + 4, y + 8)
                    path.closeSubpath()
                    painter.setPen(QPen(c_bus, 1))
                    painter.setBrush(QColor(c_bus.red(), c_bus.green(), c_bus.blue(), 40))
                    painter.drawPath(path)
                    if (x_pos - prev_x) > 25:
                        painter.setPen(QColor("#fff")); painter.setFont(QFont("Arial", 8))
                        painter.drawText(QRectF(prev_x, y - 8, x_pos - prev_x, 16), Qt.AlignmentFlag.AlignCenter, str(prev_val))
                        painter.setFont(font_main)
                prev_x = x_pos; prev_val = val
            y += row_h
        cx = self.sidebar_width + (self.cursor_time * self.zoom) - self.offset_x
        if cx > self.sidebar_width:
            painter.setPen(QPen(QColor("#FFD700"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(cx), 0, int(cx), self.height())
            painter.drawText(int(cx)+5, 20, self.format_time(self.cursor_time))
        painter.setPen(QPen(QColor("#444"), 2))
        painter.drawLine(self.sidebar_width, 0, self.sidebar_width, self.height())

    def mouseMoveEvent(self, e):
        if e.pos().x() > self.sidebar_width:
            rel_x = e.pos().x() - self.sidebar_width + self.offset_x
            self.cursor_time = int(max(0, rel_x / self.zoom))
            self.update()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0: self.zoom *= 1.1
        else: self.zoom *= 0.9
        self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Up: self.zoom *= 1.2
        elif key == Qt.Key.Key_Down: self.zoom *= 0.8
        elif key == Qt.Key.Key_W:
            self.selected_row = max(0, self.selected_row - 1)
            self.ensure_row_visible()
        elif key == Qt.Key.Key_S:
            self.selected_row = min(len(self.visible_ids) - 1, self.selected_row + 1)
            self.ensure_row_visible()
        elif key in [Qt.Key.Key_D, Qt.Key.Key_Right]: self.jump_edge(forward=True)
        elif key in [Qt.Key.Key_A, Qt.Key.Key_Left]: self.jump_edge(forward=False)
        elif key == Qt.Key.Key_F: self.controller.fit_view()
        self.update()

    def ensure_row_visible(self):
        row_y = (self.selected_row * 40) + 40
        if self.parentWidget(): self.parentWidget().parentWidget().ensureVisible(0, row_y, 0, 50)

    def jump_edge(self, forward=True):
        if not self.data or not self.visible_ids: return
        sid = self.visible_ids[self.selected_row]
        trans = self.data.signals[sid]
        target = self.cursor_time; found = False
        if forward:
            for t, v in trans:
                if t > self.cursor_time: target = t; found = True; break
            if not found: target = self.data.end_time
        else:
            for t, v in reversed(trans):
                if t < self.cursor_time: target = t; found = True; break
            if not found: target = 0
        self.cursor_time = target
        screen_x = self.sidebar_width + (self.cursor_time * self.zoom) - self.offset_x
        if screen_x > self.width(): self.offset_x += (screen_x - self.width()) + 100
        if screen_x < self.sidebar_width: self.offset_x = max(0, (self.cursor_time * self.zoom) - 100)
        self.update()


class SignalPeeker(QWidget):
    def __init__(self, ide):
        super().__init__()
        self.ide = ide
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        tb_widget = QWidget()
        tb_widget.setStyleSheet("background: #252526; border-bottom: 1px solid #333;")
        tb = QHBoxLayout(tb_widget); tb.setContentsMargins(5,5,5,5)
        btn_style = "QPushButton { background: #333; color: white; border: 1px solid #555; padding: 4px 10px; border-radius: 3px; } QPushButton:hover { background: #444; }"
        self.btn_load = QPushButton("📂 Load VCD"); self.btn_load.setStyleSheet(btn_style); self.btn_load.clicked.connect(self.manual_load)
        self.btn_gtk = QPushButton("🌊 GTKWave"); self.btn_gtk.setStyleSheet(btn_style); self.btn_gtk.clicked.connect(self.launch_gtkwave)
        self.btn_fit = QPushButton("↔ Fit (F)"); self.btn_fit.setStyleSheet(btn_style); self.btn_fit.clicked.connect(self.fit_view)
        self.lbl_info = QLabel("No Waveform Loaded"); self.lbl_info.setStyleSheet("color: #888; font-family: Consolas; margin-left: 10px;")
        tb.addWidget(self.btn_load); tb.addWidget(self.btn_gtk); tb.addWidget(self.btn_fit); tb.addWidget(self.lbl_info); tb.addStretch()
        lay.addWidget(tb_widget)

        self.cvs = WaveformCanvas(self)
        self.scroll = QScrollArea(); self.scroll.setWidget(self.cvs); self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; }"); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        lay.addWidget(self.scroll)
        self.current_vcd_path = None

    def paintEvent(self, event):
        if self.width() <= 0 or self.height() <= 0:
            return
        super().paintEvent(event)
        painter = QPainter(self)
        wm_text = "POWERED BY SIGNALPEEKER"
        painter.setPen(QColor("#00FFFF"))
        painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
        painter.setOpacity(0.5)
        painter.drawText(self.rect().adjusted(-5, -5, -25, -5),
                        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, wm_text)

    def manual_load(self):
        t, _ = QFileDialog.getOpenFileName(self, "Open VCD", self.ide.cwd, "*.vcd")
        if t: self.load_file(t)

    def auto_load(self):
        candidates = glob.glob(os.path.join(self.ide.cwd, "*.vcd"))
        parent_dir = os.path.dirname(self.ide.cwd)
        candidates += glob.glob(os.path.join(parent_dir, "*.vcd"))
        if candidates: self.load_file(max(candidates, key=os.path.getctime))
        else: self.lbl_info.setText("No .vcd files found.")

    def load_file(self, path):
        self.current_vcd_path = path; self.ide.log_system(f"Loading Waves: {os.path.basename(path)}")
        self.lbl_info.setText(f"Active: {os.path.basename(path)}")
        parser = VCDParser(path); self.cvs.set_data(parser); self.fit_view(); self.cvs.setFocus()

    def fit_view(self):
        if self.cvs.data and self.cvs.data.end_time > 0:
            available_w = self.scroll.width() - self.cvs.sidebar_width - 20
            self.cvs.zoom = max(0.0001, available_w / self.cvs.data.end_time)
            self.cvs.offset_x = 0; self.cvs.update()

    def launch_gtkwave(self):
        if self.current_vcd_path: subprocess.Popen(["gtkwave", self.current_vcd_path])
        else: QMessageBox.information(self, "Info", "Load a VCD file first.")
