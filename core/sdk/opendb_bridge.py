"""
silis/core/sdk/opendb_bridge.py
Zero-TCL OpenDB / OpenROAD programmatic inspection and query engine.
Wraps the embedded OpenROAD python/OpenDB environment to query die boundaries,
cells, macros, placed instances, routing layers, pins, and exact utilization.
"""

import os
import sys
import json
import subprocess
from typing import Dict, List, Optional, Tuple, Any


class OpenDBInstance:
    """Represents a placed component instance inside OpenDB."""
    def __init__(self, name: str, master: str, x: float, y: float, orientation: str = "R0", is_macro: bool = False):
        self.name = name
        self.master = master
        self.x = x
        self.y = y
        self.orientation = orientation
        self.is_macro = is_macro

    def __repr__(self):
        return f"<OpenDBInstance {self.name} master={self.master} loc=({self.x:.3f}, {self.y:.3f}) macro={self.is_macro}>"


class OpenDBPin:
    """Represents a top-level block boundary pin / I/O terminal."""
    def __init__(self, name: str, direction: str, layer: str, x: float, y: float):
        self.name = name
        self.direction = direction
        self.layer = layer
        self.x = x
        self.y = y

    def __repr__(self):
        return f"<OpenDBPin {self.name} dir={self.direction} layer={self.layer} loc=({self.x:.3f}, {self.y:.3f})>"


class OpenDBBridge:
    """
    Programmatic OpenROAD OpenDB Inspector.
    Dispatches python queries into OpenROAD's native runtime or parses .def via odb library.
    """
    def __init__(self, pipeline_or_project):
        self.pipe = pipeline_or_project
        self._cached_data = None

    def _resolve_paths(self):
        proj = getattr(self.pipe, "project", self.pipe)
        results_dir = getattr(proj, "results_dir", "")
        def_path = os.path.join(results_dir, "temp.def")
        if not os.path.isfile(def_path):
            cand = getattr(proj, "get_def", lambda: None)()
            if cand and os.path.isfile(cand):
                def_path = cand
        return proj, def_path

    def inspect(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Runs OpenROAD python script to query all design properties into clean JSON."""
        if self._cached_data and not force_refresh:
            return self._cached_data

        proj, def_path = self._resolve_paths()
        if not def_path or not os.path.isfile(def_path):
            return {
                "die_area": [0.0, 0.0, 0.0, 0.0],
                "core_area": [0.0, 0.0, 0.0, 0.0],
                "utilization": 0.0,
                "instances": [],
                "pins": [],
                "nets_count": 0,
            }

        # Query OpenROAD via self-contained python script
        py_script = f"""
import sys, json
import openroad as ord
import odb

db = ord.get_db()

# Read LEFs
tlef = "{getattr(proj, 'pdk_paths', {}).get('tlef', '')}"
if not tlef:
    tlef = "/home/eatheswar/.silis/pdks/sky130A/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef"
sc_lef = "/home/eatheswar/.silis/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef"

try:
    odb.read_lef(db, tlef)
    lib = odb.read_lef(db, sc_lef)
    # create default fake IO sites so custom pad rows don't abort reader
    try:
        s1 = odb.dbSite_create(lib, "IO_SITE")
        s1.setWidth(1000); s1.setHeight(200000)
        s2 = odb.dbSite_create(lib, "IO_CSITE")
        s2.setWidth(200000); s2.setHeight(204000)
    except Exception:
        pass
except Exception as e:
    pass

# Additional LEFs in source/
import glob, os
for f in glob.glob("{proj.root_dir}/source/*.lef"):
    try: odb.read_lef(db, f)
    except: pass
for f in ["/home/eatheswar/.silis/pdks/sky130A/libs.ref/sky130_fd_io/lef/sky130_ef_io.lef", "/home/eatheswar/.silis/pdks/sky130A/libs.ref/sky130_fd_io/lef/sky130_fd_io.lef"]:
    if os.path.isfile(f):
        try: odb.read_lef(db, f)
        except: pass

tech = db.getTech()
chip = odb.read_def(tech, "{def_path}")
block = chip.getBlock()
dbu = float(tech.getDbUnitsPerMicron())

die_box = block.getDieArea()
die = [die_box.xMin()/dbu, die_box.yMin()/dbu, die_box.xMax()/dbu, die_box.yMax()/dbu]

core_box = block.getCoreArea()
core = [core_box.xMin()/dbu, core_box.yMin()/dbu, core_box.xMax()/dbu, core_box.yMax()/dbu]

insts = []
total_std_area = 0.0
for inst in block.getInsts():
    master = inst.getMaster()
    m_name = master.getName()
    is_macro = master.isBlock() or master.isPad()
    mw = master.getWidth() / dbu
    mh = master.getHeight() / dbu
    if not is_macro:
        total_std_area += (mw * mh)
    origin = inst.getOrigin()
    insts.append({{
        "name": inst.getName(),
        "master": m_name,
        "x": origin[0] / dbu,
        "y": origin[1] / dbu,
        "orient": inst.getOrient(),
        "is_macro": is_macro
    }})

core_area = (core[2] - core[0]) * (core[3] - core[1])
util = (total_std_area / core_area) if core_area > 0 else 0.0

pins = []
for bt in block.getBTerms():
    b_name = bt.getName()
    b_dir = bt.getIoType()
    b_layer = ""
    bx, by = 0.0, 0.0
    for bp in bt.getBPins():
        for b_box in bp.getBoxes():
            bx = b_box.xMin() / dbu
            by = b_box.yMin() / dbu
            b_layer = b_box.getTechLayer().getName()
            break
        if b_layer: break
    pins.append({{"name": b_name, "dir": b_dir, "layer": b_layer, "x": bx, "y": by}})

res = {{
    "die_area": die,
    "core_area": core,
    "utilization": util,
    "instances": insts,
    "pins": pins,
    "nets_count": len(block.getNets())
}}

print("___SILIS_OPENDB_JSON_START___")
print(json.dumps(res))
print("___SILIS_OPENDB_JSON_END___")
"""
        cmd = ["openroad", "-exit", "-python", "-c", py_script]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if "___SILIS_OPENDB_JSON_START___" in p.stdout:
                j_str = p.stdout.split("___SILIS_OPENDB_JSON_START___")[1].split("___SILIS_OPENDB_JSON_END___")[0].strip()
                self._cached_data = json.loads(j_str)
                return self._cached_data
        except Exception:
            pass

        return {
            "die_area": [0.0, 0.0, 0.0, 0.0],
            "core_area": [0.0, 0.0, 0.0, 0.0],
            "utilization": 0.0,
            "instances": [],
            "pins": [],
            "nets_count": 0,
        }

    @property
    def die_area(self) -> Tuple[float, float, float, float]:
        """Returns die bounds in micrometers (x1, y1, x2, y2)."""
        d = self.inspect().get("die_area", [0.0, 0.0, 0.0, 0.0])
        return tuple(d)

    @property
    def core_area(self) -> Tuple[float, float, float, float]:
        """Returns core boundary in micrometers (x1, y1, x2, y2)."""
        c = self.inspect().get("core_area", [0.0, 0.0, 0.0, 0.0])
        return tuple(c)

    @property
    def utilization(self) -> float:
        """Returns calculated standard-cell core utilization [0.0 .. 1.0]."""
        return float(self.inspect().get("utilization", 0.0))

    def get_instances(self, macro_only: bool = False) -> List[OpenDBInstance]:
        """Returns placed instances from OpenDB."""
        data = self.inspect().get("instances", [])
        res = []
        for i in data:
            if macro_only and not i.get("is_macro", False):
                continue
            res.append(OpenDBInstance(
                name=i["name"],
                master=i["master"],
                x=i["x"],
                y=i["y"],
                orientation=i.get("orient", "R0"),
                is_macro=i.get("is_macro", False)
            ))
        return res

    def get_pins(self) -> List[OpenDBPin]:
        """Returns top-level design boundary pins / I/O terminals."""
        data = self.inspect().get("pins", [])
        return [
            OpenDBPin(name=p["name"], direction=p["dir"], layer=p["layer"], x=p["x"], y=p["y"])
            for p in data
        ]
