"""
silis/core/sdk/layout.py
In-Memory Real-Time Physical Layout & Change Engine.
Provides direct manipulation of OpenDB instances, nets, terminals, and bounding boxes
without requiring intermediate DEF file emission or disk roundtrips.
"""

import os
from typing import Dict, Any, List, Optional, Tuple
from .opendb_bridge import OpenDBBridge, OpenDBInstance, OpenDBPin


class LayoutNet:
    """Represents an interconnected net in the layout with direct terminal inspection."""
    def __init__(self, name: str, is_special: bool = False, terminals: Optional[List[str]] = None):
        self.name = name
        self.is_special = is_special
        self.terminals = terminals or []

    def __repr__(self):
        return f"<LayoutNet {self.name} Terms={len(self.terminals)} Special={self.is_special}>"


class Layout:
    """
    Authoritative In-Memory Physical Design Layout Engine.
    Exposes real-time instance coordinate mutation, boundary inspection,
    and net connectivity graphs.
    """
    def __init__(self, project=None):
        self.project = project
        self.bridge = OpenDBBridge(project)
        self._instances_cache: Optional[Dict[str, OpenDBInstance]] = None
        self._nets_cache: Optional[Dict[str, LayoutNet]] = None

    def _ensure_loaded(self):
        if self._instances_cache is None:
            data = self.bridge.inspect(force_refresh=True)
            self._instances_cache = {}
            for item in data.get("instances", []):
                if isinstance(item, dict):
                    inst_obj = OpenDBInstance(
                        name=item["name"],
                        master=item["master"],
                        x=item["x"],
                        y=item["y"],
                        orientation=item.get("orient", item.get("orientation", "R0")),
                        is_macro=item.get("is_macro", False),
                    )
                else:
                    inst_obj = item
                self._instances_cache[inst_obj.name] = inst_obj
            self._nets_cache = {}

    def get_instances(self) -> List[OpenDBInstance]:
        """Returns all physical standard cell and macro instances in the active design."""
        self._ensure_loaded()
        return list(self._instances_cache.values())

    def find_instance(self, name: str) -> Optional[OpenDBInstance]:
        """Finds an instance by hierarchical name."""
        self._ensure_loaded()
        return self._instances_cache.get(name)

    def set_instance_location(self, name: str, x: float, y: float, orientation: str = "R0") -> bool:
        """
        Mutates the instance location directly in the in-memory layout representation
        with 0.005 um manufacturing grid quantization.
        """
        inst = self.find_instance(name)
        if not inst:
            return False

        inst.x = round(round(x / 0.005) * 0.005, 3)
        inst.y = round(round(y / 0.005) * 0.005, 3)
        inst.orientation = orientation
        return True

    @property
    def die_area(self) -> List[float]:
        """Returns die boundary [x1, y1, x2, y2] in microns."""
        return self.get_die_area()

    @property
    def core_area(self) -> List[float]:
        """Returns core boundary [x1, y1, x2, y2] in microns."""
        return self.get_core_area()

    @property
    def utilization(self) -> float:
        """Returns standard cell core area utilization percentage."""
        return self.get_utilization()

    def get_die_area(self) -> List[float]:
        """Returns die boundary [x1, y1, x2, y2] in microns."""
        self._ensure_loaded()
        return self.bridge.die_area

    def get_core_area(self) -> List[float]:
        """Returns core boundary [x1, y1, x2, y2] in microns."""
        self._ensure_loaded()
        return self.bridge.core_area

    def get_utilization(self) -> float:
        """Returns standard cell core area utilization percentage."""
        self._ensure_loaded()
        return self.bridge.utilization

    def get_pins(self) -> List[OpenDBPin]:
        """Returns top-level I/O boundary pins."""
        self._ensure_loaded()
        return self.bridge.get_pins()

    def view(self, show: bool = True, detach: Optional[bool] = None, layer_view: bool = False, **kwargs) -> Any:
        """
        Interactive visualization of the physical layout directly from SDK.
        
        Args:
            show: Whether to display the window.
            detach: Launch as detached background GUI process (default True for non-blocking SDK).
            layer_view: If True, uses the C++ OpenROAD Native Layer Viewer with layer controls
                        and cell/macro internal shapes. If False, uses FastSiliconPeeker.
            **kwargs: Extra viewer arguments (e.g., layer_visibility, heatmap, show_rulers).
        """
        proj = self.project
        def_path = ""
        if proj:
            cand = getattr(proj, "get_def", lambda: None)()
            if cand and os.path.isfile(cand):
                def_path = cand
            elif hasattr(proj, "results_dir"):
                cand2 = os.path.join(proj.results_dir, "temp.def")
                if os.path.isfile(cand2):
                    def_path = cand2

        if not def_path:
            raise FileNotFoundError("No DEF or layout file found to visualize.")

        from .viewers import view_layout, view_layers
        if layer_view:
            return view_layers(def_path, show=show, detach=detach, **kwargs)
        else:
            return view_layout(def_path, show=show, detach=detach, **kwargs)

    def view_layers(self, show: bool = True, detach: Optional[bool] = None, **kwargs) -> Any:
        """Convenience method to launch the C++ OpenROAD Layer Viewer directly."""
        return self.view(show=show, detach=detach, layer_view=True, **kwargs)

    def __repr__(self):
        die = self.get_die_area()
        return f"<Layout Instances={len(self.get_instances())} Die=[{die[0]:.1f}, {die[1]:.1f}, {die[2]:.1f}, {die[3]:.1f}]>"
