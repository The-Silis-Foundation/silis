"""
silis/core/layer_viewer/layer_viewer_panel.py
Full Native OpenROAD Layer Viewer and Property Inspector Container.
Combines the C++ SilisNativeLayerViewer canvas with the native Qt6 DesignPropertyInspector
and OpenDB high-fidelity data extraction.
"""

# ==============================================================================
# Silis Layer Viewer Panel
#
# Heartfelt compliments, tribute, and attribution to the incredible OpenROAD
# Project community and contributors (The OpenROAD Authors / Precision Innovations).
# Based on OpenROAD's LayoutViewer and DisplayControls paradigm.
# ==============================================================================

import os
import glob
import json
import subprocess
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6 import sip

try:
    import silis_layer_viewer
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import silis_layer_viewer

try:
    from layer_viewer.inspector_widget import DesignPropertyInspector
except ImportError:
    from silis.core.layer_viewer.inspector_widget import DesignPropertyInspector


class LayerLoadWorker(QThread):
    """Asynchronous background worker executing OpenDB geometric extraction."""
    data_loaded = pyqtSignal(dict)

    def __init__(self, def_path: str, odb_path: str, pdk_base: str, proj_dir: str, parent=None):
        super().__init__(parent)
        self.def_path = def_path
        self.odb_path = odb_path
        self.pdk_base = pdk_base
        self.proj_dir = proj_dir

    def run(self):
        py_script = f"""
import os, sys, json, glob
import openroad as ord
import odb

def_path = "{self.def_path}"
odb_path = "{self.odb_path}"

tech = ord.Tech()
design = ord.Design(tech)

loaded = False
if os.path.isfile(odb_path) and os.path.getsize(odb_path) > 0:
    try:
        design.readDb(odb_path)
        loaded = True
    except Exception:
        loaded = False

if not loaded:
    db = design.getDb()
    pdk_base = "{self.pdk_base}"
    tlef = os.path.join(pdk_base, "sky130A", "libs.ref", "sky130_fd_sc_hd", "techlef", "sky130_fd_sc_hd__nom.tlef")
    sc_lef = os.path.join(pdk_base, "sky130A", "libs.ref", "sky130_fd_sc_hd", "lef", "sky130_fd_sc_hd.lef")
    try:
        odb.read_lef(db, tlef)
        lib = odb.read_lef(db, sc_lef)
        try:
            s1 = odb.dbSite_create(lib, "IO_SITE")
            s1.setWidth(1000); s1.setHeight(200000)
            s2 = odb.dbSite_create(lib, "IO_CSITE")
            s2.setWidth(200000); s2.setHeight(204000)
        except Exception: pass
    except Exception: pass

    io_dir = os.path.join(pdk_base, "sky130A", "libs.ref", "sky130_fd_io", "lef")
    for f in ["sky130_ef_io.lef", "sky130_fd_io.lef"]:
        p = os.path.join(io_dir, f)
        if os.path.isfile(p):
            try: odb.read_lef(db, p)
            except Exception: pass

    for lef in glob.glob(os.path.join(pdk_base, "**", "sky130_sram_macros", "lef", "*.lef"), recursive=True):
        try: odb.read_lef(db, lef)
        except Exception: pass

    proj_dir = "{self.proj_dir}"
    for sdir in [os.path.join(proj_dir, "source"), os.path.join(proj_dir, "rtl"), os.path.join(proj_dir, "constr"), proj_dir]:
        for f in glob.glob(f"{{sdir}}/*.lef"):
            try: odb.read_lef(db, f)
            except Exception: pass

    chip = odb.read_def(db.getTech(), def_path)

block = design.getBlock()
dbu = float(design.getDb().getTech().getDbUnitsPerMicron())

die_box = block.getDieArea()
die = [die_box.xMin(), die_box.yMin(), die_box.xMax(), die_box.yMax()]

layers_geom = {{"li1": [], "met1": [], "met2": [], "met3": [], "met4": [], "met5": [], "vias": []}}

def transform_rect(xform, x1, y1, x2, y2):
    p1 = odb.Point(x1, y1)
    p2 = odb.Point(x2, y1)
    p3 = odb.Point(x2, y2)
    p4 = odb.Point(x1, y2)
    xform.apply(p1)
    xform.apply(p2)
    xform.apply(p3)
    xform.apply(p4)
    min_x = min(p1.x(), p2.x(), p3.x(), p4.x())
    max_x = max(p1.x(), p2.x(), p3.x(), p4.x())
    min_y = min(p1.y(), p2.y(), p3.y(), p4.y())
    max_y = max(p1.y(), p2.y(), p3.y(), p4.y())
    return min_x, min_y, max_x - min_x, max_y - min_y

# 1. SWires & Power Rails
rail_x, rail_y, rail_w, rail_h = [], [], [], []
rail_nets, rail_layers = [], []

for net in block.getNets():
    nname = net.getName()
    st = str(net.getSigType())
    is_pwr = (st in ("POWER", "GROUND") or nname in ("VDD", "VSS", "vccd", "vssd"))
    for sw in net.getSWires():
        for box in sw.getWires():
            tlayer = box.getTechLayer()
            lname = tlayer.getName() if tlayer else "vias"
            bx = box.xMin()
            by = box.yMin()
            bw = box.xMax() - box.xMin()
            bh = box.yMax() - box.yMin()
            if lname in layers_geom:
                layers_geom[lname].append([bx, by, bw, bh])
            if is_pwr:
                rail_x.append(bx)
                rail_y.append(by)
                rail_w.append(bw)
                rail_h.append(bh)
                rail_nets.append(nname)
                rail_layers.append(lname)

# 2. Instance Internals: Macros, Pads, and Standard Cells (Obstructions & Port Pins)
master_cache = {{}}
for inst in block.getInsts():
    m = inst.getMaster()
    mname = m.getName()
    if mname not in master_cache:
        shapes = []
        for obs in m.getObstructions():
            tlayer = obs.getTechLayer()
            lname = tlayer.getName() if tlayer else "vias"
            if lname in layers_geom:
                shapes.append((lname, obs.xMin(), obs.yMin(), obs.xMax(), obs.yMax()))
        for mterm in m.getMTerms():
            for mpin in mterm.getMPins():
                for gbox in mpin.getGeometry():
                    tlayer = gbox.getTechLayer()
                    lname = tlayer.getName() if tlayer else "vias"
                    if lname in layers_geom:
                        shapes.append((lname, gbox.xMin(), gbox.yMin(), gbox.xMax(), gbox.yMax()))
        master_cache[mname] = shapes

    xform = inst.getTransform()
    for lname, ox1, oy1, ox2, oy2 in master_cache[mname]:
        tx, ty, tw, th = transform_rect(xform, ox1, oy1, ox2, oy2)
        layers_geom[lname].append([tx, ty, tw, th])

# 3. Extract Placed Components
inst_x, inst_y, inst_w, inst_h = [], [], [], []
inst_names, inst_masters, is_macro = [], [], []
inst_lookup = {{}}

for inst in block.getInsts():
    m = inst.getMaster()
    macro_flag = bool(m.isBlock() or m.isPad())
    bbox = inst.getBBox()
    bx = bbox.xMin(); by = bbox.yMin()
    bw = bbox.xMax() - bx; bh = bbox.yMax() - by
    iname = inst.getName()
    inst_x.append(bx); inst_y.append(by); inst_w.append(bw); inst_h.append(bh)
    inst_names.append(iname); inst_masters.append(m.getName()); is_macro.append(macro_flag)

    terms = []
    for it in inst.getITerms():
        net = it.getNet()
        terms.append({{"pin": it.getMTerm().getName(), "net": net.getName() if net else "UNCONNECTED"}})
    inst_lookup[iname] = {{
        "master": m.getName(),
        "type": m.getType(),
        "x": bx, "y": by, "w": bw, "h": bh,
        "orient": inst.getOrient(),
        "terms": terms
    }}

# 4. Extract Net connectivity for flightlines
net_lookup = {{}}
for net in block.getNets():
    nname = net.getName()
    terms = []
    driver_pt = None
    sink_pts = []
    for it in net.getITerms():
        inst = it.getInst()
        bbox = inst.getBBox()
        cx = (bbox.xMin() + bbox.xMax()) / 2.0
        cy = (bbox.yMin() + bbox.yMax()) / 2.0
        io_type = it.getMTerm().getIoType()
        if io_type == "OUTPUT":
            driver_pt = [cx, cy]
        else:
            sink_pts.append([cx, cy])
        terms.append(f"{{inst.getName()}}/{{it.getMTerm().getName()}}")

    for bt in net.getBTerms():
        for bp in bt.getBPins():
            for b_box in bp.getBoxes():
                cx = (b_box.xMin() + b_box.xMax()) / 2.0
                cy = (b_box.yMin() + b_box.yMax()) / 2.0
                if bt.getIoType() == "INPUT":
                    driver_pt = [cx, cy]
                else:
                    sink_pts.append([cx, cy])
                break

    net_lookup[nname] = {{
        "type": net.getSigType(),
        "driver": terms[0] if terms else None,
        "terms": terms,
        "driver_pt": driver_pt,
        "sink_pts": sink_pts,
        "is_routed": bool(net.getWire() is not None)
    }}

out = {{
    "dbu": dbu,
    "die": die,
    "layers": layers_geom,
    "rail_x": rail_x, "rail_y": rail_y, "rail_w": rail_w, "rail_h": rail_h,
    "rail_nets": rail_nets, "rail_layers": rail_layers,
    "inst_x": inst_x, "inst_y": inst_y, "inst_w": inst_w, "inst_h": inst_h,
    "inst_names": inst_names, "inst_masters": inst_masters, "is_macro": is_macro,
    "inst_lookup": inst_lookup,
    "net_lookup": net_lookup
}}

print("___SILIS_LAYER_JSON_START___")
print(json.dumps(out))
print("___SILIS_LAYER_JSON_END___")
"""
        cmd = ["openroad", "-exit", "-python", "-c", py_script]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if "___SILIS_LAYER_JSON_START___" in p.stdout:
                j_str = p.stdout.split("___SILIS_LAYER_JSON_START___")[1].split("___SILIS_LAYER_JSON_END___")[0].strip()
                data = json.loads(j_str)
                self.data_loaded.emit(data)
        except Exception:
            pass


class LayerViewerPanel(QWidget):
    """
    Composite Layer Viewer Widget hosting:
      1. High-Performance C++ OpenGL/QPainter Canvas (SilisNativeLayerViewer)
      2. Object Selection & Flightlines
      3. Right-hand Collapsible Property Inspector (DesignPropertyInspector)
    """
    def __init__(self, ide=None, parent=None):
        super().__init__(parent)
        self.ide = ide

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(self.splitter)

        # C++ Native Layer Viewer Core
        self.core = silis_layer_viewer.SilisNativeLayerViewer()
        ptr = self.core.get_ptr()
        self.canvas_widget = sip.wrapinstance(ptr, QWidget)
        self.splitter.addWidget(self.canvas_widget)

        # Native Property Inspector
        self.inspector = DesignPropertyInspector(self)
        self.splitter.addWidget(self.inspector)

        # 75% Canvas, 25% Inspector initial distribution
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)

        # Internal design graph cache for instant inspection
        self.inst_lookup = {}
        self.net_lookup = {}
        self.dbu = 1000.0

        # Optimization & Cache state
        self._last_loaded_path = None
        self._last_loaded_mtime = 0
        self._last_loaded_size = 0
        self._load_worker = None

        # Wire Signals
        self.canvas_widget.instance_clicked.connect(self.on_instance_selected)
        if hasattr(self.canvas_widget, 'power_rail_clicked'):
            self.canvas_widget.power_rail_clicked.connect(self.on_power_rail_selected)
        self.inspector.inspect_net_requested.connect(self.highlight_net)

    def load_layout_from_opendb(self, def_path: str, pdk_root: str = None):
        """
        Extracts verified geometric layers and instances directly from OpenDB via an asynchronous QThread worker.
        Guarded with mtime & file-size cache checks to eliminate zero-change re-renders.
        """
        if not def_path or not os.path.isfile(def_path):
            return

        mtime = os.path.getmtime(def_path)
        size = os.path.getsize(def_path)

        # Fast exit if file hasn't changed at all (zero-latency tab switch)
        if (self._last_loaded_path == def_path and 
            self._last_loaded_mtime == mtime and 
            self._last_loaded_size == size and 
            bool(self.inst_lookup)):
            return

        # Avoid redundant concurrent workers
        if self._load_worker and self._load_worker.isRunning():
            return

        self._last_loaded_path = def_path
        self._last_loaded_mtime = mtime
        self._last_loaded_size = size

        home_dir = os.path.expanduser("~")
        pdk_base = pdk_root or os.environ.get("PDK_ROOT", os.path.join(home_dir, ".silis", "pdks"))

        proj_dir = os.path.dirname(os.path.abspath(def_path))
        if os.path.basename(proj_dir) == "results":
            proj_dir = os.path.dirname(proj_dir)

        odb_path = os.path.join(proj_dir, "results", "temp.odb")
        if not os.path.isfile(odb_path):
            cand_odb = os.path.join(os.path.dirname(os.path.abspath(def_path)), "temp.odb")
            if os.path.isfile(cand_odb):
                odb_path = cand_odb

        # Show non-blocking status message in IDE status bar
        if self.ide and hasattr(self.ide, 'statusBar'):
            self.ide.statusBar().showMessage("Extracting OpenROAD layer geometry in background...")

        self._load_worker = LayerLoadWorker(def_path, odb_path, pdk_base, proj_dir, self)
        self._load_worker.data_loaded.connect(self._on_worker_data_loaded)
        self._load_worker.start()

    def _on_worker_data_loaded(self, data: dict):
        if data:
            self._apply_opendb_data(data)
        if self.ide and hasattr(self.ide, 'statusBar'):
            self.ide.statusBar().showMessage("Layer Geometry Ready", 3000)

    def _apply_opendb_data(self, data: dict):
        self.core.clear()
        self.inspector.clear_inspector()

        self.dbu = data.get("dbu", 1000.0)
        self.inspector.set_dbu(self.dbu)
        self.core.set_dbu(self.dbu)

        die = data.get("die", [0, 0, 100000, 100000])
        self.core.set_core(die[0], die[1], die[2] - die[0], die[3] - die[1])

        # Load Layers into C++ canvas
        layers = data.get("layers", {})
        for lname, boxes in layers.items():
            if not boxes:
                continue
            x = [b[0] for b in boxes]
            y = [b[1] for b in boxes]
            w = [b[2] for b in boxes]
            h = [b[3] for b in boxes]
            self.core.load_layer_shapes(lname, x, y, w, h)

        # Load Power Rails into C++ canvas for direct rail click-selection
        rx = data.get("rail_x", [])
        ry = data.get("rail_y", [])
        rw = data.get("rail_w", [])
        rh = data.get("rail_h", [])
        rn = data.get("rail_nets", [])
        rl = data.get("rail_layers", [])
        if rx and hasattr(self.core, 'load_power_rails'):
            self.core.load_power_rails(rx, ry, rw, rh, rn, rl)

        # Load Placed Instances
        ix = data.get("inst_x", [])
        iy = data.get("inst_y", [])
        iw = data.get("inst_w", [])
        ih = data.get("inst_h", [])
        inames = data.get("inst_names", [])
        imasters = data.get("inst_masters", [])
        imacro = data.get("is_macro", [])
        self.core.load_instances(ix, iy, iw, ih, inames, imasters, imacro)

        self.inst_lookup = data.get("inst_lookup", {})
        self.net_lookup = data.get("net_lookup", {})

        # Fit in view
        self.core.fit_in_view()

    def set_layer_visibility(self, layer_map: dict):
        """Passes layer toggles from the sidebar to the C++ canvas."""
        for lname, vis in layer_map.items():
            self.core.set_layer_visible(lname, vis)

    def on_instance_selected(self, name: str, master: str, x: float, y: float, w: float, h: float):
        """Triggered when an instance is clicked in the C++ layout canvas."""
        inst_info = self.inst_lookup.get(name, {})
        iterms = inst_info.get("terms", [])
        orient = inst_info.get("orient", "R0")
        self.inspector.inspect_instance(name, master, x, y, w, h, orient=orient, iterms=iterms)

    def on_power_rail_selected(self, net_name: str, layer_name: str, x: float, y: float, w: float, h: float):
        """Triggered when a power rail strap/trunk is clicked in the C++ layout canvas."""
        net_info = self.net_lookup.get(net_name, {})
        self.inspector.inspect_net(
            net_name=net_name,
            sig_type=net_info.get("type", "POWER"),
            driver=f"PDN Strap ({layer_name})",
            sinks=net_info.get("terms", []),
            is_routed=True
        )

    def highlight_net(self, net_name: str):
        """Computes and renders flightline rubberbands for the inspected net."""
        net_info = self.net_lookup.get(net_name)
        if not net_info:
            return

        drv = net_info.get("driver_pt")
        sinks = net_info.get("sink_pts", [])
        if not drv or not sinks:
            self.core.clear_flightlines()
            return

        x1_list, y1_list, x2_list, y2_list = [], [], [], []
        for s in sinks:
            x1_list.append(drv[0])
            y1_list.append(drv[1])
            x2_list.append(s[0])
            y2_list.append(s[1])

        self.core.set_flightlines(x1_list, y1_list, x2_list, y2_list)
        self.inspector.inspect_net(
            net_name=net_name,
            sig_type=net_info.get("type", "SIGNAL"),
            driver=net_info.get("driver"),
            sinks=net_info.get("terms", []),
            is_routed=net_info.get("is_routed", False)
        )
