"""
silis/core/backendflow/gdsviewer/gds3d.py
Native Qt6 + OpenGL 3.3 Core Instanced 3D IC Layout Viewer.
"""

import os
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QSplitter, QListWidget, QListWidgetItem,
    QSlider, QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6 import sip

_GDSVIEWER_DIR = os.path.dirname(os.path.abspath(__file__))
if _GDSVIEWER_DIR not in sys.path:
    sys.path.insert(0, _GDSVIEWER_DIR)

try:
    import silis_gds3d_viewer
except ImportError:
    silis_gds3d_viewer = None

# Standard Sky130 / ASIC physical stack: (z_min, z_max, r, g, b, a)
_LAYER_STACK = {
    "diff":  (0.0,  0.3,  0.25, 0.72, 0.42, 0.90),
    "poly":  (0.3,  0.65, 0.85, 0.25, 0.25, 0.95),
    "licon": (0.60, 0.70, 0.75, 0.75, 0.75, 0.95),
    "li1":   (0.70, 0.82, 0.90, 0.55, 0.20, 0.92),
    "mcon":  (0.82, 1.15, 0.80, 0.80, 0.80, 0.95),
    "met1":  (1.15, 1.51, 0.24, 0.54, 0.95, 0.90),
    "via":   (2.3,  2.8,  0.85, 0.85, 0.85, 0.95),
    "met2":  (2.8,  3.4,  0.92, 0.36, 0.66, 0.90),
    "via2":  (3.4,  4.0,  0.85, 0.85, 0.85, 0.95),
    "met3":  (4.0,  4.8,  0.22, 0.80, 0.75, 0.90),
    "via3":  (4.8,  5.5,  0.85, 0.85, 0.85, 0.95),
    "met4":  (5.5,  6.5,  0.94, 0.78, 0.24, 0.90),
    "via4":  (6.5,  7.4,  0.85, 0.85, 0.85, 0.95),
    "met5":  (7.4,  9.0,  0.66, 0.44, 0.94, 0.90),
    "vias":  (2.3,  7.4,  0.85, 0.85, 0.85, 0.90),
}

_SKY130_GDS_MAP = {
    (65, 20): "diff",
    (66, 20): "poly",
    (66, 44): "licon",
    (67, 20): "li1",
    (67, 44): "mcon",
    (68, 20): "met1",
    (68, 44): "via",
    (69, 20): "met2",
    (69, 44): "via2",
    (70, 20): "met3",
    (70, 44): "via3",
    (71, 20): "met4",
    (71, 44): "via4",
    (72, 20): "met5",
}


class GDS3DPort(QWidget):
    """Native Qt6 OpenGL 3.3 Core Instanced 3D IC Layout Viewer."""

    def __init__(self, parent_ide=None):
        super().__init__(parent_ide)
        self.ide = parent_ide
        self.core = None
        self.native_widget = None

        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(4)

        # Native Qt6 control bar
        bar = QWidget(self)
        h_lay = QHBoxLayout(bar)
        h_lay.setContentsMargins(8, 4, 8, 4)
        h_lay.setSpacing(6)

        h_lay.addWidget(QLabel("Silis 3D Silicon Viewer (OpenGL 3.3 Core)"))
        h_lay.addStretch()

        for preset, label in [("iso", "Iso"), ("top", "Top"), ("front", "Front")]:
            btn = QPushButton(label, bar)
            btn.clicked.connect(lambda _=False, p=preset: self._set_preset(p))
            h_lay.addWidget(btn)

        btn_fit = QPushButton("Fit", bar)
        btn_fit.clicked.connect(self._fit_view)
        h_lay.addWidget(btn_fit)

        h_lay.addWidget(QLabel("Z-Scale:"))
        self.sld_z = QSlider(Qt.Orientation.Horizontal, bar)
        self.sld_z.setRange(1, 15)
        self.sld_z.setValue(1)
        self.sld_z.setFixedWidth(90)
        self.sld_z.valueChanged.connect(self._on_z_scale)
        h_lay.addWidget(self.sld_z)

        h_lay.addWidget(QLabel("Z-Clip:"))
        self.sld_clip = QSlider(Qt.Orientation.Horizontal, bar)
        self.sld_clip.setRange(1, 100)
        self.sld_clip.setValue(100)
        self.sld_clip.setFixedWidth(90)
        self.sld_clip.valueChanged.connect(self._on_clip_z)
        h_lay.addWidget(self.sld_clip)

        self.btn_load = QPushButton("Load GDS / DEF", bar)
        self.btn_load.clicked.connect(self.prompt_load)
        h_lay.addWidget(self.btn_load)

        self.btn_close = QPushButton("Close", bar)
        self.btn_close.clicked.connect(self.close_viewer)
        h_lay.addWidget(self.btn_close)

        root_lay.addWidget(bar)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.layer_list = QListWidget(splitter)
        self.layer_list.setMaximumWidth(180)
        self.layer_list.itemChanged.connect(self._on_layer_toggled)

        self.canvas = QWidget(splitter)
        self.canvas_layout = QVBoxLayout(self.canvas)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)

        splitter.addWidget(self.layer_list)
        splitter.addWidget(self.canvas)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root_lay.addWidget(splitter, stretch=1)

    def ensure_engine(self):
        if self.core is not None:
            return self.core
        if silis_gds3d_viewer:
            self.core = silis_gds3d_viewer.SilisNative3DViewer()
            ptr = self.core.get_ptr()
            self.native_widget = sip.wrapinstance(ptr, QWidget)
            self.canvas_layout.addWidget(self.native_widget)
        else:
            lbl = QLabel("silis_gds3d_viewer native module not compiled.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.canvas_layout.addWidget(lbl)
        return self.core

    def showEvent(self, event):
        super().showEvent(event)
        self.ensure_engine()

    def _set_preset(self, preset: str):
        if self.core:
            self.core.set_camera_preset(preset)

    def _fit_view(self):
        if self.core:
            self.core.fit_in_view()

    def _on_z_scale(self, val: int):
        if self.core:
            self.core.set_z_scale(float(val))

    def _on_clip_z(self, val: int):
        if self.core:
            self.core.set_clip_z(15.0 * (val / 100.0))

    def _on_layer_toggled(self, item: QListWidgetItem):
        if self.core:
            self.core.set_layer_visible(item.text(), item.checkState() == Qt.CheckState.Checked)

    def close_viewer(self):
        parent = self.parent()
        while parent:
            if isinstance(parent, QTabWidget):
                parent.setCurrentIndex(0)
                break
            parent = parent.parent()

    def prompt_load(self):
        try:
            proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
            results_dir = os.path.join(proj_root, "results")
        except AttributeError:
            results_dir = os.getcwd()

        path, _ = QFileDialog.getOpenFileName(
            self, "Select GDS or DEF File for 3D Viewer", results_dir,
            "Layout Files (*.gds *.def *.odb);;All Files (*)"
        )
        if path:
            self.load_gds(path)

    def _populate_layers(self, layers_dict, bounds):
        self.core.clear()
        self.layer_list.blockSignals(True)
        self.layer_list.clear()

        for lname, boxes in layers_dict.items():
            if not boxes:
                continue
            z_min, z_max, r, g, b, a = _LAYER_STACK.get(lname, (1.0, 2.0, 0.6, 0.7, 0.8, 0.9))
            xs = [float(bx[0]) for bx in boxes]
            ys = [float(bx[1]) for bx in boxes]
            ws = [float(bx[2]) for bx in boxes]
            hs = [float(bx[3]) for bx in boxes]
            self.core.set_layer_data(lname, xs, ys, ws, hs, z_min, z_max, r, g, b, a)

            it = QListWidgetItem(lname)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            self.layer_list.addItem(it)

        self.layer_list.blockSignals(False)
        self.core.set_bounds(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))

    def load_gds(self, path: str):
        self.ensure_engine()
        if not os.path.isfile(path) or not self.core:
            return

        if path.lower().endswith(".def"):
            self._load_def(path)
            return

        if path.lower().endswith(".gds"):
            try:
                import gdstk
                lib = gdstk.read_gds(path)
                tops = lib.top_level()
                if not tops:
                    return
                top = tops[0]
                layers_dict = {}
                min_x, min_y = 1e12, 1e12
                max_x, max_y = -1e12, -1e12
                die_bounds = None
                for poly in top.get_polygons(depth=0):
                    if (poly.layer, poly.datatype) in ((235, 4), (235, 0)):
                        bb = poly.bounding_box()
                        if bb is not None:
                            x1, y1 = float(bb[0][0]), float(bb[0][1])
                            x2, y2 = float(bb[1][0]), float(bb[1][1])
                            if die_bounds is None:
                                die_bounds = (x1, y1, x2, y2)
                            else:
                                die_bounds = (
                                    min(die_bounds[0], x1), min(die_bounds[1], y1),
                                    max(die_bounds[2], x2), max(die_bounds[3], y2)
                                )
                for poly in top.get_polygons(depth=None):
                    key = (poly.layer, poly.datatype)
                    if key in ((235, 4), (235, 0)):
                        continue
                    lname = _SKY130_GDS_MAP.get(key)
                    if not lname:
                        continue
                    bb = poly.bounding_box()
                    if bb is None:
                        continue
                    x1, y1 = float(bb[0][0]), float(bb[0][1])
                    x2, y2 = float(bb[1][0]), float(bb[1][1])
                    if x2 <= x1 or y2 <= y1:
                        continue
                    layers_dict.setdefault(lname, []).append((x1, y1, x2 - x1, y2 - y1))
                    min_x = min(min_x, x1); min_y = min(min_y, y1)
                    max_x = max(max_x, x2); max_y = max(max_y, y2)
                if layers_dict:
                    self._populate_layers(layers_dict, die_bounds or (min_x, min_y, max_x, max_y))
                return
            except Exception as e:
                print(f"[GDS3D] gdstk load note: {e}")

    def _load_def(self, def_path: str):
        """Extracts 3D multi-layer physical geometry from a DEF file via OpenDB."""
        import glob
        import json
        import subprocess

        abs_def = os.path.abspath(def_path)
        proj_dir = os.path.dirname(abs_def)
        if os.path.basename(proj_dir) == "results":
            proj_dir = os.path.dirname(proj_dir)

        home_dir = os.path.expanduser("~")
        pdk_base = os.environ.get("PDK_ROOT", os.path.join(home_dir, ".silis", "pdks"))

        py_script = f"""
import os, sys, json, glob
import openroad as ord
import odb

db = ord.get_db()
pdk_base = {json.dumps(pdk_base)}
pdk_var = "sky130B" if os.path.isdir(os.path.join(pdk_base, "sky130B")) else "sky130A"
tlef = os.path.join(pdk_base, pdk_var, "libs.ref", "sky130_fd_sc_hd", "techlef", "sky130_fd_sc_hd__nom.tlef")
sc_lef = os.path.join(pdk_base, pdk_var, "libs.ref", "sky130_fd_sc_hd", "lef", "sky130_fd_sc_hd.lef")

try:
    if os.path.isfile(tlef):
        odb.read_lef(db, tlef)
    if os.path.isfile(sc_lef):
        lib = odb.read_lef(db, sc_lef)
        try:
            s1 = odb.dbSite_create(lib, "IO_SITE"); s1.setWidth(1000); s1.setHeight(200000)
            s2 = odb.dbSite_create(lib, "IO_CSITE"); s2.setWidth(200000); s2.setHeight(204000)
        except Exception:
            pass
except Exception:
    pass

extra_lefs = [
    os.path.join(pdk_base, pdk_var, "libs.ref", "sky130_fd_io", "lef", "sky130_fd_io.lef"),
    os.path.join(pdk_base, pdk_var, "libs.ref", "sky130_fd_io", "lef", "sky130_ef_io.lef"),
    os.path.join(pdk_base, pdk_var, "libs.ref", "sky130_power_switch", "lef", "power_switch.lef"),
    os.path.join(pdk_base, pdk_var, "libs.ref", "sky130_fd_sc_hd", "lef", "sky130_power_switch.lef"),
] + glob.glob(os.path.join(pdk_base, "**", "sky130_sram_macros", "lef", "*.lef"), recursive=True)

proj_dir = {json.dumps(proj_dir)}
for sdir in [os.path.join(proj_dir, "source"), os.path.join(proj_dir, "rtl"), os.path.join(proj_dir, "constr"), proj_dir]:
    extra_lefs.extend(glob.glob(os.path.join(sdir, "*.lef")))

for f in extra_lefs:
    if os.path.isfile(f):
        try:
            odb.read_lef(db, f)
        except Exception:
            pass

tech = db.getTech()
chip = odb.read_def(tech, {json.dumps(abs_def)})
block = chip.getBlock() if chip else None
if not block:
    sys.exit(0)

dbu = float(tech.getDbUnitsPerMicron())
die_box = block.getDieArea()
bounds = [die_box.xMin() / dbu, die_box.yMin() / dbu, die_box.xMax() / dbu, die_box.yMax() / dbu]

_LAYER_ALIAS = {{
    "li1": "li1", "met1": "met1", "mcon": "mcon", "via": "via", "via1": "via",
    "met2": "met2", "via2": "via2", "met3": "met3", "via3": "via3",
    "met4": "met4", "via4": "via4", "met5": "met5",
}}
layers = {{k: [] for k in ("diff", "poly", "licon", "li1", "mcon", "met1", "via", "met2", "via2", "met3", "via3", "met4", "via4", "met5")}}

def add_box(lname, x1, y1, x2, y2):
    if x2 <= x1 or y2 <= y1 or not lname:
        return
    if lname not in layers:
        layers[lname] = []
    layers[lname].append([round(x1 / dbu, 3), round(y1 / dbu, 3), round((x2 - x1) / dbu, 3), round((y2 - y1) / dbu, 3)])

# 1. Instances: stdcells -> diff, special/power cells -> poly, macros & pads -> diff + met3 bezel
for inst in block.getInsts():
    m = inst.getMaster()
    if not m:
        continue
    mname = m.getName().lower()
    if "decap" in mname or "fill" in mname:
        continue
    bb = inst.getBBox()
    x1, y1, x2, y2 = bb.xMin(), bb.yMin(), bb.xMax(), bb.yMax()
    if m.isBlock() or m.isPad():
        add_box("diff", x1, y1, x2, y2)
        add_box("poly", x1, y1, x2, y2)
        add_box("met1", x1, y1, x2, y2)
    elif ("tap" in mname or "power_switch" in mname or "lsbuf" in mname or "isowell" in mname or "diode" in mname):
        add_box("poly", x1, y1, x2, y2)
    else:
        add_box("diff", x1, y1, x2, y2)

# 2. Special nets (PDN straps/rings) + pins
for bt in block.getBTerms():
    for bp in bt.getBPins():
        for b in bp.getBoxes():
            tl = b.getTechLayer()
            ln = _LAYER_ALIAS.get(tl.getName().lower() if tl else "", "met3")
            add_box(ln, b.xMin(), b.yMin(), b.xMax(), b.yMax())

dec = odb.dbWireDecoder()
for net in block.getNets():
    for sw in net.getSWires():
        for box in sw.getWires():
            tl = box.getTechLayer()
            if tl:
                ln = _LAYER_ALIAS.get(tl.getName().lower(), "")
                if ln:
                    add_box(ln, box.xMin(), box.yMin(), box.xMax(), box.yMax())
            else:
                via = box.getBlockVia() or box.getTechVia()
                if via:
                    cx = 0.5 * (box.xMin() + box.xMax())
                    cy = 0.5 * (box.yMin() + box.yMax())
                    for vb in via.getBoxes():
                        vtl = vb.getTechLayer()
                        ln = _LAYER_ALIAS.get(vtl.getName().lower() if vtl else "", "via")
                        add_box(ln, cx + vb.xMin(), cy + vb.yMin(), cx + vb.xMax(), cy + vb.yMax())

    w = net.getWire()
    if not w:
        continue
    dec.begin(w)
    pts = []
    cur_layer = None
    prev_pt = None
    while True:
        op = dec.next()
        if op == odb.dbWireDecoder.END_DECODE:
            break
        elif op in (odb.dbWireDecoder.PATH, odb.dbWireDecoder.SHORT, odb.dbWireDecoder.VWIRE):
            cur_layer = dec.getLayer()
            prev_pt = None
        elif op == odb.dbWireDecoder.JUNCTION:
            jid = dec.getJunctionValue()
            if 0 <= jid < len(pts):
                prev_pt = pts[jid]
        elif op in (odb.dbWireDecoder.POINT, odb.dbWireDecoder.POINT_EXT):
            pt = dec.getPoint() if op == odb.dbWireDecoder.POINT else dec.getPoint_ext()
            x, y = pt[0], pt[1]
            ext = pt[2] if (op == odb.dbWireDecoder.POINT_EXT and len(pt) > 2) else 0
            pts.append((x, y))
            if prev_pt is not None and cur_layer is not None:
                ln = _LAYER_ALIAS.get(cur_layer.getName().lower(), "")
                if ln:
                    hw = max(int(cur_layer.getWidth() // 2), int(0.07 * dbu))
                    px, py = prev_pt
                    x1, x2 = (px, x) if px <= x else (x, px)
                    y1, y2 = (py, y) if py <= y else (y, py)
                    add_box(ln, x1 - hw - abs(ext), y1 - hw - abs(ext), x2 + hw + abs(ext), y2 + hw + abs(ext))
            prev_pt = (x, y)
        elif op in (odb.dbWireDecoder.TECH_VIA, odb.dbWireDecoder.VIA):
            via = dec.getTechVia() if op == odb.dbWireDecoder.TECH_VIA else dec.getVia()
            if via and prev_pt is not None:
                px, py = prev_pt
                for vb in via.getBoxes():
                    vtl = vb.getTechLayer()
                    ln = _LAYER_ALIAS.get(vtl.getName().lower() if vtl else "", "via")
                    add_box(ln, px + vb.xMin(), py + vb.yMin(), px + vb.xMax(), py + vb.yMax())
        elif op == odb.dbWireDecoder.RECT:
            # TritonRoute patch metal rectangles are non-essential for 3D topology;
            # OpenDB Python SWIG binds getRect with raw C++ 'int &' refs.
            pass

layers = {{k: v for k, v in layers.items() if v}}
print("___SILIS_GDS3D_JSON_START___")
print(json.dumps({{"bounds": bounds, "layers": layers}}))
print("___SILIS_GDS3D_JSON_END___")
"""
        try:
            proc = subprocess.run(["openroad", "-exit", "-python", "-c", py_script], capture_output=True, text=True, timeout=90)
            if "___SILIS_GDS3D_JSON_START___" in proc.stdout:
                raw = proc.stdout.split("___SILIS_GDS3D_JSON_START___")[1].split("___SILIS_GDS3D_JSON_END___")[0].strip()
                payload = json.loads(raw)
                layers_dict = payload.get("layers", {})
                bounds = payload.get("bounds")
                if layers_dict and bounds:
                    self._populate_layers(layers_dict, tuple(bounds))
                return
            print(f"[GDS3D] OpenDB DEF load note: {(proc.stderr or proc.stdout).strip()[:300]}")
        except Exception as e:
            print(f"[GDS3D] DEF load exception: {e}")
