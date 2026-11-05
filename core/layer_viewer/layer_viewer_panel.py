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
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
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

        # Wire Signals
        self.inspector.inspect_net_requested.connect(self.highlight_net)

    def load_layout_from_opendb(self, def_path: str, pdk_root: str = None):
        """
        Extracts verified geometric layers and instances directly from OpenDB via openroad -python.
        Populates both the C++ layer canvas and the property inspector data graph.
        """
        if not def_path or not os.path.isfile(def_path):
            return

        home_dir = os.path.expanduser("~")
        pdk_base = pdk_root or os.environ.get("PDK_ROOT", os.path.join(home_dir, ".silis", "pdks"))

        proj_dir = os.path.dirname(os.path.abspath(def_path))
        if os.path.basename(proj_dir) == "results":
            proj_dir = os.path.dirname(proj_dir)

        # Dispatch OpenDB script to gather complete geometry + connectivity
        py_script = f"""
# ==============================================================================
# Silis Layer Viewer Panel
#
# Heartfelt compliments, tribute, and attribution to the incredible OpenROAD
# Project community and contributors (The OpenROAD Authors / Precision Innovations).
# Based on OpenROAD's LayoutViewer and DisplayControls paradigm.
# ==============================================================================

import os, sys, json, glob
import openroad as ord
import odb

db = ord.get_db()
pdk_base = "{pdk_base}"
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
    except Exception:
        pass
except Exception:
    pass

io_dir = os.path.join(pdk_base, "sky130A", "libs.ref", "sky130_fd_io", "lef")
for f in ["sky130_ef_io.lef", "sky130_fd_io.lef"]:
    p = os.path.join(io_dir, f)
    if os.path.isfile(p):
        try: odb.read_lef(db, p)
        except Exception: pass

for lef in glob.glob(os.path.join(pdk_base, "**", "sky130_sram_macros", "lef", "*.lef"), recursive=True):
    try: odb.read_lef(db, lef)
    except Exception: pass

proj_dir = "{proj_dir}"
for sdir in [os.path.join(proj_dir, "source"), os.path.join(proj_dir, "rtl"), os.path.join(proj_dir, "constr"), proj_dir]:
    for f in glob.glob(f"{{sdir}}/*.lef"):
        try: odb.read_lef(db, f)
        except Exception: pass

tech = db.getTech()
chip = odb.read_def(tech, "{def_path}")
block = chip.getBlock()
dbu = float(tech.getDbUnitsPerMicron())

die_box = block.getDieArea()
die = [die_box.xMin(), die_box.yMin(), die_box.xMax(), die_box.yMax()]

# Extract Layer SWires
layers_geom = {{"li1": [], "met1": [], "met2": [], "met3": [], "met4": [], "met5": [], "vias": []}}
for net in block.getNets():
    for sw in net.getSWires():
        for box in sw.getWires():
            tlayer = box.getTechLayer()
            if tlayer:
                lname = tlayer.getName()
                if lname in layers_geom:
                    layers_geom[lname].append([box.xMin(), box.yMin(), box.xMax() - box.xMin(), box.yMax() - box.yMin()])
            else:
                layers_geom["vias"].append([box.xMin(), box.yMin(), box.xMax() - box.xMin(), box.yMax() - box.yMin()])

# Extract Placed Components
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

# Extract Net connectivity for flightlines
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
    "inst_x": inst_x, "inst_y": inst_y, "inst_w": inst_w, "inst_h": inst_h,
    "inst_names": inst_names, "inst_masters": inst_masters, "is_macro": is_macro,
    "inst_lookup": inst_lookup,
    "net_lookup": net_lookup
}}

print("___SILIS_LAYER_JSON_START___")
print(json.dumps(out))
print("___SILIS_LAYER_JSON_END___")
"""
        import subprocess
        import json
        cmd = ["openroad", "-exit", "-python", "-c", py_script]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if "___SILIS_LAYER_JSON_START___" in p.stdout:
                j_str = p.stdout.split("___SILIS_LAYER_JSON_START___")[1].split("___SILIS_LAYER_JSON_END___")[0].strip()
                data = json.loads(j_str)
                self._apply_opendb_data(data)
        except Exception as e:
            pass

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
