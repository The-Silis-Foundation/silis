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

    def __init__(self, def_path: str, odb_path: str, pdk_base: str, proj_dir: str, pdk_name: str = "", parent=None):
        super().__init__(parent)
        self.def_path = def_path
        self.odb_path = odb_path
        self.pdk_base = pdk_base
        self.proj_dir = proj_dir
        self.pdk_name = pdk_name

    def run(self):
        from silis.core.pdkmanagers.pdk.manager import SSAForge
        pdk_paths = SSAForge.get_pdk_paths(self.pdk_name, self.pdk_base)
        tlef_path = pdk_paths.get("tech_lef", "")
        sc_lef_path = pdk_paths.get("std_cell_lef", "")
        extra_lefs = list(pdk_paths.get("extra_lefs", []))
        io_site = SSAForge.get(self.pdk_name, "io_site") or "IO_SITE"
        io_csite = SSAForge.get(self.pdk_name, "io_corner_site") or "IO_CSITE"

        # Automatically discover SkyWater 130 IO and Corner pad LEFs if SkyWater PDK
        if "sky130" in (self.pdk_name or "").lower() or "sky130" in (tlef_path or "").lower():
            pdk_r = pdk_paths.get("pdk_root", self.pdk_base)
            for cand_lef in [
                os.path.join(pdk_r, "libs.ref", "sky130_fd_io", "lef", "sky130_ef_io.lef"),
                os.path.join(pdk_r, "libs.ref", "sky130_fd_io", "lef", "sky130_fd_io.lef"),
                os.path.join(pdk_r, "libs.tech", "openlane", "custom_cells", "lef", "sky130_ef_io_core.lef"),
                os.path.join(pdk_r, "libs.tech", "openlane", "custom_cells", "lef", "sky130_fd_io_core.lef"),
            ]:
                if os.path.isfile(cand_lef) and cand_lef not in extra_lefs:
                    extra_lefs.append(cand_lef)

        import json
        extra_lefs_json = json.dumps(extra_lefs)

        py_script = f"""
import os, sys, json, glob
import openroad as ord
import odb

def_path = "{self.def_path}"
odb_path = "{self.odb_path}"
tlef_path = "{tlef_path}"
sc_lef_path = "{sc_lef_path}"
extra_lefs = {extra_lefs_json}
io_site = "{io_site}"
io_csite = "{io_csite}"

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
    if os.path.isfile(tlef_path):
        try: odb.read_lef(db, tlef_path)
        except Exception: pass
    if os.path.isfile(sc_lef_path):
        try:
            lib = odb.read_lef(db, sc_lef_path)
            try:
                s1 = odb.dbSite.create(lib, io_site)
                s1.setWidth(1000); s1.setHeight(200000)
                s2 = odb.dbSite.create(lib, io_csite)
                s2.setWidth(200000); s2.setHeight(204000)
            except Exception: pass
        except Exception: pass

    for lef in extra_lefs:
        if os.path.isfile(lef):
            try: odb.read_lef(db, lef)
            except Exception: pass

    proj_dir = "{self.proj_dir}"
    for sdir in [os.path.join(proj_dir, "source"), os.path.join(proj_dir, "rtl"), os.path.join(proj_dir, "constr"), proj_dir]:
        for f in glob.glob(f"{{sdir}}/*.lef"):
            if os.path.isfile(f):
                try: odb.read_lef(db, f)
                except Exception: pass

    chip = odb.read_def(db.getTech(), def_path)

block = design.getBlock()
dbu = float(design.getDb().getTech().getDbUnitsPerMicron())

die_box = block.getDieArea()
die = [die_box.xMin(), die_box.yMin(), die_box.xMax(), die_box.yMax()]

layers_geom = {{"vias": []}}
for tlayer in design.getDb().getTech().getLayers():
    layers_geom[tlayer.getName()] = []

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
            if tlayer:
                lname = tlayer.getName()
                bx = box.xMin()
                by = box.yMin()
                bw = box.xMax() - box.xMin()
                bh = box.yMax() - box.yMin()
                if lname not in layers_geom:
                    layers_geom[lname] = []
                layers_geom[lname].append([bx, by, bw, bh])
                if is_pwr:
                    rail_x.append(bx)
                    rail_y.append(by)
                    rail_w.append(bw)
                    rail_h.append(bh)
                    rail_nets.append(nname)
                    rail_layers.append(lname)
            else:
                # Decompose Multi-Cut / Technology / Block Via Stacks into constituent layers
                bv = box.getBlockVia()
                tv = box.getTechVia()
                via = bv if bv else tv
                if via:
                    vx_mid = (box.xMin() + box.xMax()) / 2.0
                    vy_mid = (box.yMin() + box.yMax()) / 2.0
                    for v_box in via.getBoxes():
                        v_tech_layer = v_box.getTechLayer()
                        v_lname = v_tech_layer.getName() if v_tech_layer else "vias"
                        vx1 = vx_mid + v_box.xMin()
                        vy1 = vy_mid + v_box.yMin()
                        vw = v_box.xMax() - v_box.xMin()
                        vh = v_box.yMax() - v_box.yMin()
                        if v_lname not in layers_geom:
                            layers_geom[v_lname] = []
                        layers_geom[v_lname].append([vx1, vy1, vw, vh])
                        if is_pwr:
                            rail_x.append(vx1)
                            rail_y.append(vy1)
                            rail_w.append(vw)
                            rail_h.append(vh)
                            rail_nets.append(nname)
                            rail_layers.append(v_lname)

# 2. Extract Block Boundary Terminals (I/O Pins)
for bt in block.getBTerms():
    for bp in bt.getBPins():
        for b_box in bp.getBoxes():
            tlayer = b_box.getTechLayer()
            lname = tlayer.getName() if tlayer else "Metal2"
            bx = b_box.xMin()
            by = b_box.yMin()
            bw = b_box.xMax() - bx
            bh = b_box.yMax() - by
            if lname not in layers_geom:
                layers_geom[lname] = []
            layers_geom[lname].append([bx, by, bw, bh])

# 2. Instance Internals: Macros, IO Pads, and Full Standard Cell Internal Pins
master_pin_cache = {{}}
for _l in db.getLibs():
    for _m in _l.getMasters():
        _pins = []
        for _mterm in _m.getMTerms():
            for _mpin in _mterm.getMPins():
                for _gbox in _mpin.getGeometry():
                    _layer_obj = _gbox.getTechLayer()
                    _lname = _layer_obj.getName() if _layer_obj else "li1"
                    _pins.append((_lname, _gbox.xMin(), _gbox.yMin(), _gbox.xMax(), _gbox.yMax()))
        master_pin_cache[_m.getName()] = _pins

# High-speed vectorized affine coordinate projection (N, FS, FN, S)
for inst in block.getInsts():
    m = inst.getMaster()
    mname = m.getName()
    if mname not in master_pin_cache:
        continue
    pins = master_pin_cache[mname]
    if not pins:
        continue
    ox, oy = inst.getOrigin()
    orient = inst.getOrient()

    if orient == "R0":
        for lname, px1, py1, px2, py2 in pins:
            if lname not in layers_geom:
                layers_geom[lname] = []
            layers_geom[lname].append([ox + px1, oy + py1, px2 - px1, py2 - py1])
    elif orient == "FS":
        mh = m.getHeight()
        for lname, px1, py1, px2, py2 in pins:
            if lname not in layers_geom:
                layers_geom[lname] = []
            layers_geom[lname].append([ox + px1, oy + (mh - py2), px2 - px1, py2 - py1])
    else:
        xform = inst.getTransform()
        for lname, px1, py1, px2, py2 in pins:
            tx, ty, tw, th = transform_rect(xform, px1, py1, px2, py2)
            if lname not in layers_geom:
                layers_geom[lname] = []
            layers_geom[lname].append([tx, ty, tw, th])

# Macro-level obstructions
for inst in block.getInsts():
    m = inst.getMaster()
    if not (m.isBlock() or m.isPad()):
        continue
    xform = inst.getTransform()
    for obs in m.getObstructions():
        tlayer = obs.getTechLayer()
        lname = tlayer.getName() if tlayer else "vias"
        tx, ty, tw, th = transform_rect(xform, obs.xMin(), obs.yMin(), obs.xMax(), obs.yMax())
        if lname not in layers_geom:
            layers_geom[lname] = []
        layers_geom[lname].append([tx, ty, tw, th])

# 3. Extract Placed Components
inst_x, inst_y, inst_w, inst_h = [], [], [], []
inst_names, inst_masters, is_macro = [], [], []
inst_categories = []
inst_lookup = {{}}

for inst in block.getInsts():
    m = inst.getMaster()
    macro_flag = bool(m.isBlock() or m.isPad())
    mname = m.getName()
    mname_lower = mname.lower()
    mtype = str(m.getType())
    
    # Classify power category cells (tap, welltap, decap, power_switch, level_shifter)
    is_power = bool(
        "tap" in mname_lower or
        "filltie" in mname_lower or
        "power_switch" in mname_lower or
        "pwron" in mname_lower or
        "decap" in mname_lower or
        "isowell" in mname_lower or
        "lsbuf" in mname_lower or
        "isobuf" in mname_lower or
        mtype in ["CORE_WELLTAP", "CORE_SPACER", "ENDCAP"]
    )

    cat = 2 if is_power else (1 if macro_flag else 0)

    bbox = inst.getBBox()
    bx = bbox.xMin(); by = bbox.yMin()
    bw = bbox.xMax() - bx; bh = bbox.yMax() - by
    iname = inst.getName()
    inst_x.append(bx); inst_y.append(by); inst_w.append(bw); inst_h.append(bh)
    inst_names.append(iname); inst_masters.append(mname); is_macro.append(macro_flag)
    inst_categories.append(cat)

    terms = []
    for it in inst.getITerms():
        net = it.getNet()
        terms.append({{"pin": it.getMTerm().getName(), "net": net.getName() if net else "UNCONNECTED"}})
    inst_lookup[iname] = {{
        "master": mname,
        "type": mtype,
        "category": "POWER" if is_power else ("MACRO" if macro_flag else "STDCELL"),
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
    "inst_categories": inst_categories,
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

        proj_pdk = ""
        try:
            from silis.core.sdk.project import Project, find_project_file
            p_file = find_project_file(proj_dir)
            if p_file:
                p_obj = Project.load(p_file)
                proj_pdk = p_obj.config.get("pdk", "")
        except Exception:
            pass

        self._load_worker = LayerLoadWorker(def_path, odb_path, pdk_base, proj_dir, pdk_name=proj_pdk, parent=self)
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
        icats = data.get("inst_categories", [])
        self.core.load_instances(ix, iy, iw, ih, inames, imasters, imacro, icats)

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
