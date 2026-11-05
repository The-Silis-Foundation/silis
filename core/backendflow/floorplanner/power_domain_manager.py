"""
silis/core/backendflow/floorplanner/power_domain_manager.py
Power Architecture & Low-Power Island Management for Silis FP Studio.
Handles:
- Power Domain Registry (Always-On, Internally Switched, Dedicated External Pad)
- Boundary Clamp Exceptions Tree-Table with single-keystroke (0/1) editing
- Level Shifter auto-selection (_lh vs _hl) and drive strength sizing
- IEEE-1801 UPF file generation
- PMU hierarchy traversal and control signal mapping
"""

import os
import re
from typing import Dict, List, Optional, Any
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QCheckBox,
    QMessageBox, QGroupBox, QFormLayout, QTreeWidget, QTreeWidgetItem,
    QDoubleSpinBox, QWidget
)


class PowerDomain:
    """Represents a physical or logical power domain."""
    @property
    def is_top(self) -> bool:
        return self.name == "PD_TOP" or self.domain_type.lower() == "always-on"

    def __init__(
        self,
        name: str,
        voltage: float = 1.8,
        domain_type: str = "Always-On",  # "Always-On", "Internally Gated", "Dedicated External Pad"
        parent_domain: Optional[str] = "PD_TOP",
        pmu_instance: Optional[str] = None,
        elements: Optional[List[str]] = None,
        switch_topology: str = "Checkerboard Columns",  # "Checkerboard Columns" or "Perimeter Ring"
        switch_pitch: float = 20.0,
        enable_srpg: bool = False,
        iso_en: Optional[str] = None,
        sleep_en: Optional[str] = None,
        sleep_ack: Optional[str] = None,
        tapcell_type: str = "sky130_fd_sc_hd__tapvpwrvgnd_1",
        site_type: str = "unithd",
        row_height: float = 2.72,
        enable_physical_switch: bool = False
    ):
        self.name = name
        self.voltage = voltage
        self.domain_type = domain_type
        self.parent_domain = parent_domain
        self.pmu_instance = pmu_instance
        self.elements = elements or []
        self.switch_topology = switch_topology
        self.switch_pitch = switch_pitch
        self.enable_srpg = enable_srpg
        self.iso_en = iso_en or f"{name.lower()}_iso_en"
        self.sleep_en = sleep_en or f"{name.lower()}_sleep"
        self.sleep_ack = sleep_ack
        self.tapcell_type = tapcell_type
        self.site_type = site_type
        self.row_height = row_height
        self.enable_physical_switch = enable_physical_switch
        self.clamps: Dict[str, int] = {}  # net_name -> clamp value (0 or 1)
        self.area: Optional[Any] = None  # QRectF physical cavity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "voltage": self.voltage,
            "domain_type": self.domain_type,
            "parent_domain": self.parent_domain,
            "pmu_instance": self.pmu_instance,
            "elements": self.elements,
            "switch_topology": self.switch_topology,
            "switch_pitch": self.switch_pitch,
            "enable_srpg": self.enable_srpg,
            "iso_en": self.iso_en,
            "sleep_en": self.sleep_en,
            "sleep_ack": self.sleep_ack,
            "tapcell_type": self.tapcell_type,
            "site_type": self.site_type,
            "row_height": self.row_height,
            "enable_physical_switch": self.enable_physical_switch,
            "clamps": self.clamps
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PowerDomain":
        pd = cls(
            name=data.get("name", "PD_TOP"),
            voltage=data.get("voltage", 1.8),
            domain_type=data.get("domain_type", "Always-On"),
            parent_domain=data.get("parent_domain", "PD_TOP"),
            pmu_instance=data.get("pmu_instance", None),
            elements=data.get("elements", []),
            switch_topology=data.get("switch_topology", "Checkerboard Columns"),
            switch_pitch=data.get("switch_pitch", 20.0),
            enable_srpg=data.get("enable_srpg", False),
            iso_en=data.get("iso_en"),
            sleep_en=data.get("sleep_en"),
            sleep_ack=data.get("sleep_ack"),
            tapcell_type=data.get("tapcell_type", "sky130_fd_sc_hd__tapvpwrvgnd_1"),
            site_type=data.get("site_type", "unithd"),
            row_height=data.get("row_height", 2.72),
            enable_physical_switch=data.get("enable_physical_switch", False)
        )
        pd.clamps = data.get("clamps", {})
        return pd


class BoundaryClampTableDialog(QDialog):
    """
    Rapid-fire keyboard-driven Boundary Clamp Exceptions Table.
    Single-keystrokes: '0' sets 0 and advances; '1' sets 1 and advances; Space toggles.
    TreeWidget allows folding/unfolding multi-bit buses.
    """
    def __init__(self, domain_or_manager, crossing_nets=None, netlist_path=None, parent=None):
        if parent is None and isinstance(netlist_path, QWidget):
            parent = netlist_path
            netlist_path = None
        super().__init__(parent)
        if hasattr(domain_or_manager, 'domains'):
            self.manager = domain_or_manager
            # Default to first non-top domain or top domain
            gated = [d for d in self.manager.domains.values() if not d.is_top]
            self.domain = gated[0] if gated else self.manager.domains.get("PD_TOP")
        else:
            self.domain = domain_or_manager
            self.manager = None
        self.crossing_nets = crossing_nets or [
            {"name": "data_in[0]", "dest": "PD_TOP"},
            {"name": "data_in[1]", "dest": "PD_TOP"},
            {"name": "data_in[2]", "dest": "PD_TOP"},
            {"name": "data_in[3]", "dest": "PD_TOP"},
            {"name": "rst_n", "dest": "PD_TOP"},
            {"name": "valid", "dest": "PD_TOP"}
        ]
        self.setWindowTitle(f"Boundary Clamp Exceptions: {domain.name} -> Core")
        self.resize(750, 480)

        layout = QVBoxLayout(self)

        lbl_desc = QLabel(
            f"Review inter-domain boundary signals leaving '{domain.name}'.\n"
            "Rapid Keys: Press '0' for Clamp-0, '1' for Clamp-1 (auto-advances to next row). Space toggles."
        )
        layout.addWidget(lbl_desc)

        # Search filter
        h_filter = QHBoxLayout()
        h_filter.addWidget(QLabel("Filter:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter nets...")
        self.txt_filter.textChanged.connect(self._apply_filter)
        h_filter.addWidget(self.txt_filter)
        layout.addLayout(h_filter)

        # Tree Widget for foldable buses
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Net / Bus Name", "Destination", "Bit Width", "Clamp (0/1)", "Inferred Cell"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.installEventFilter(self)
        layout.addWidget(self.tree)

        # Populate tree
        self._populate_tree()

        # Action Buttons
        h_actions = QHBoxLayout()
        btn_infer = QPushButton("Auto-Infer Defaults")
        btn_infer.clicked.connect(self._auto_infer_all)
        btn_collapse = QPushButton("Collapse All")
        btn_collapse.clicked.connect(self.tree.collapseAll)
        btn_expand = QPushButton("Expand All")
        btn_expand.clicked.connect(self.tree.expandAll)
        h_actions.addWidget(btn_infer)
        h_actions.addWidget(btn_collapse)
        h_actions.addWidget(btn_expand)
        h_actions.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_apply = QPushButton("Commit & Apply")
        btn_apply.setDefault(True)
        btn_apply.clicked.connect(self._save_and_accept)
        h_actions.addWidget(btn_cancel)
        h_actions.addWidget(btn_apply)
        layout.addLayout(h_actions)

    def _auto_infer_value(self, name: str) -> int:
        """Active-low patterns get Clamp-1; others get Clamp-0."""
        lname = name.lower()
        if re.search(r'(_n|_b|rst|reset|csn|cs_b)$', lname) or 'rst_n' in lname or 'reset_n' in lname:
            return 1
        return 0

    def _populate_tree(self):
        self.tree.clear()
        # Group buses
        bus_groups: Dict[str, List[Dict[str, Any]]] = {}
        single_nets: List[Dict[str, Any]] = []

        for item in self.crossing_nets:
            net_name = item.get("name", "")
            bus_match = re.match(r'^(.*)\[(\d+)\]$', net_name)
            if bus_match:
                prefix = bus_match.group(1)
                if prefix not in bus_groups:
                    bus_groups[prefix] = []
                bus_groups[prefix].append(item)
            else:
                single_nets.append(item)

        # Insert single nets
        for item in single_nets:
            name = item.get("name", "")
            clamp_val = self.domain.clamps.get(name, self._auto_infer_value(name))
            cell_name = "sky130_fd_sc_hd__lpflow_inputiso1p" if clamp_val == 1 else "sky130_fd_sc_hd__lpflow_inputiso0p"
            node = QTreeWidgetItem(self.tree, [name, item.get("dest", "PD_TOP"), "1", str(clamp_val), cell_name])
            node.setData(0, Qt.ItemDataRole.UserRole, {"is_bus": False, "net_name": name})

        # Insert buses
        for prefix, bits in bus_groups.items():
            first_val = self.domain.clamps.get(bits[0]["name"], self._auto_infer_value(prefix))
            cell_name = "sky130_fd_sc_hd__lpflow_inputiso1p" if first_val == 1 else "sky130_fd_sc_hd__lpflow_inputiso0p"
            bus_node = QTreeWidgetItem(self.tree, [f"{prefix}[{len(bits)-1}:0]", bits[0].get("dest", "PD_TOP"), str(len(bits)), str(first_val), cell_name])
            bus_node.setData(0, Qt.ItemDataRole.UserRole, {"is_bus": True, "prefix": prefix, "bits": bits})

            for b in bits:
                bname = b["name"]
                bval = self.domain.clamps.get(bname, first_val)
                bcell = "sky130_fd_sc_hd__lpflow_inputiso1p" if bval == 1 else "sky130_fd_sc_hd__lpflow_inputiso0p"
                child = QTreeWidgetItem(bus_node, [bname, b.get("dest", "PD_TOP"), "1", str(bval), bcell])
                child.setData(0, Qt.ItemDataRole.UserRole, {"is_bus": False, "net_name": bname})

    def eventFilter(self, obj, event):
        if obj == self.tree and event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_0, Qt.Key.Key_1):
                new_val = 0 if key == Qt.Key.Key_0 else 1
                curr = self.tree.currentItem()
                if curr:
                    self._set_item_clamp(curr, new_val)
                    # Advance to next item
                    next_item = self.tree.itemBelow(curr)
                    if next_item:
                        self.tree.setCurrentItem(next_item)
                return True
            elif key == Qt.Key.Key_Space:
                curr = self.tree.currentItem()
                if curr:
                    cur_val = 0 if curr.text(3) == "0" else 1
                    self._set_item_clamp(curr, 1 - cur_val)
                return True
        return super().eventFilter(obj, event)

    def _set_item_clamp(self, item: QTreeWidgetItem, val: int):
        item.setText(3, str(val))
        cell_name = "sky130_fd_sc_hd__lpflow_inputiso1p" if val == 1 else "sky130_fd_sc_hd__lpflow_inputiso0p"
        item.setText(4, cell_name)

        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if data.get("is_bus"):
            # Update all children bits
            for i in range(item.childCount()):
                ch = item.child(i)
                ch.setText(3, str(val))
                ch.setText(4, cell_name)

    def _apply_filter(self, text: str):
        pattern = text.lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            match = pattern in item.text(0).lower()
            item.setHidden(not match and pattern != "")

    def _auto_infer_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            val = self._auto_infer_value(item.text(0))
            self._set_item_clamp(item, val)

    def _save_and_accept(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("is_bus"):
                for c in range(item.childCount()):
                    ch = item.child(c)
                    cdata = ch.data(0, Qt.ItemDataRole.UserRole) or {}
                    self.domain.clamps[cdata.get("net_name", ch.text(0))] = int(ch.text(3))
            else:
                self.domain.clamps[data.get("net_name", item.text(0))] = int(item.text(3))
        self.accept()


class PowerDomainManager(QObject):
    """
    Central Manager for Multi-Voltage Domains in Silis FP Studio.
    Provides UPF export, OpenROAD PDN followpin scripts, and level-shifter selection.
    """
    domains_changed = pyqtSignal()

    def __init__(self, proj_root: str = "", top_module: str = "", parent=None):
        super().__init__(parent)
        self.proj_root = proj_root
        self.top_module = top_module
        self.domains: Dict[str, PowerDomain] = {}
        # Search for UPF file in project root or power subdirectory
        self.upf_path = ""
        if proj_root:
            candidates = [
                os.path.join(proj_root, "design.upf"),
                os.path.join(proj_root, "power", "design.upf"),
                os.path.join(proj_root, f"{top_module}.upf")
            ]
            for cand in candidates:
                if os.path.isfile(cand):
                    self.upf_path = cand
                    break
        if not self.upf_path:
            self.upf_path = os.path.join(proj_root, "power", "design.upf") if proj_root else "design.upf"
        # Always register Top Always-On domain
        self.domains["PD_TOP"] = PowerDomain(name="PD_TOP", voltage=1.8, domain_type="Always-On")

    def load_or_create_upf(self):
        """
        Parses UPF file (design.upf) if it exists and populates self.domains.
        Extracts create_power_domain, elements, create_power_switch, isolation, and voltages.
        """
        if not self.upf_path or not os.path.isfile(self.upf_path):
            return

        try:
            with open(self.upf_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Normalize line continuations with backslashes
            content_norm = re.sub(r"\\\s*\n", " ", content)

            # 1. Parse create_power_domain statements
            # Pattern: create_power_domain <name> [-include_scope] [-elements {<elements>}]
            pd_matches = re.finditer(
                r"create_power_domain\s+([A-Za-z0-9_]+)(?:\s+-include_scope)?(?:\s+-elements\s*\{([^}]*)\})?",
                content_norm
            )
            found_domains = {}
            for m in pd_matches:
                dom_name = m.group(1).strip()
                elems_str = m.group(2)
                elems = [e.strip() for e in elems_str.split()] if elems_str else []
                is_top = (dom_name == "PD_TOP" or "-include_scope" in m.group(0))
                dtype = "Always-On" if is_top else "Dedicated External Pad"
                pd = PowerDomain(name=dom_name, voltage=1.8, domain_type=dtype, elements=elems)
                found_domains[dom_name] = pd

            # 2. Parse power switches to discover sleep control and output supply nets
            switch_matches = re.finditer(
                r"create_power_switch\s+([A-Za-z0-9_]+)\s+-domain\s+([A-Za-z0-9_]+)(?:.*?-control_port\s*\{sleep\s+([^}]+)\})?(?:.*?-ack_port\s*\{[^\s]+\s+([^}]+)\})?",
                content_norm,
                re.DOTALL
            )
            for sm in switch_matches:
                dom_name = sm.group(2).strip()
                sleep_pin = sm.group(3).strip() if sm.group(3) else None
                ack_pin = sm.group(4).strip() if sm.group(4) else None
                if dom_name in found_domains:
                    if sleep_pin:
                        found_domains[dom_name].sleep_en = sleep_pin
                    if ack_pin:
                        found_domains[dom_name].sleep_ack = ack_pin
                    found_domains[dom_name].domain_type = "Internally Gated"
                    # If sleep_pin has hierarchy (e.g. u_pmu/crypto_sleep), infer pmu_instance
                    if sleep_pin and "/" in sleep_pin:
                        pmu_inst = sleep_pin.split("/")[0]
                        found_domains[dom_name].pmu_instance = pmu_inst

            # 3. Parse isolation control signals
            iso_matches = re.finditer(
                r"set_isolation_control\s+([A-Za-z0-9_]+)\s+-domain\s+([A-Za-z0-9_]+).*?-isolation_signal\s+([^\s\\]+)",
                content_norm,
                re.DOTALL
            )
            for im in iso_matches:
                dom_name = im.group(2).strip()
                iso_sig = im.group(3).strip()
                if dom_name in found_domains:
                    found_domains[dom_name].iso_en = iso_sig
                    if "/" in iso_sig and not found_domains[dom_name].pmu_instance:
                        found_domains[dom_name].pmu_instance = iso_sig.split("/")[0]

            # 4. Parse set_domain_supply_net or add_power_state to detect voltages
            # e.g., set_domain_supply_net PD_COMPUTE ... -voltage 0.95
            supply_matches = re.finditer(
                r"set_domain_supply_net\s+([A-Za-z0-9_]+).*?-voltage\s+([0-9.]+)",
                content_norm
            )
            for sm in supply_matches:
                dom_name = sm.group(1).strip()
                try:
                    volts = float(sm.group(2).strip())
                    if dom_name in found_domains:
                        found_domains[dom_name].voltage = volts
                except ValueError:
                    pass

            # e.g., add_power_state PD_TOP.primary_power_net -state ON {1.8}
            state_matches = re.finditer(
                r"add_power_state\s+([A-Za-z0-9_]+)\.[A-Za-z0-9_]+\s+-state\s+ON\s*\{([0-9.]+)\}",
                content_norm
            )
            for stm in state_matches:
                dom_name = stm.group(1).strip()
                try:
                    volts = float(stm.group(2).strip())
                    if dom_name in found_domains:
                        found_domains[dom_name].voltage = volts
                except ValueError:
                    pass

            if found_domains:
                for k, v in found_domains.items():
                    self.domains[k] = v
                self.domains_changed.emit()
        except Exception as e:
            print(f"[PowerDomainManager] Note: Could not parse UPF file {self.upf_path}: {e}")

    def export_upf_tcl(self) -> str:
        return self.generate_upf_text()

    def add_domain(self, domain_or_name, voltage: float = 1.8, is_top: bool = False) -> PowerDomain:
        if isinstance(domain_or_name, PowerDomain):
            pd = domain_or_name
        else:
            dtype = "Always-On" if is_top else "Internally Gated"
            pd = PowerDomain(name=str(domain_or_name), voltage=voltage, domain_type=dtype)
        self.domains[pd.name] = pd
        self.domains_changed.emit()
        return pd

    def remove_domain(self, name: str):
        if name in self.domains and name != "PD_TOP":
            del self.domains[name]
            self.domains_changed.emit()

    def get_domain(self, name: str) -> Optional[PowerDomain]:
        return self.domains.get(name)

    def auto_size_level_shifter(self, v_driver: float, v_receiver: float, load_cap_pf: float = 0.05) -> Optional[str]:
        """Returns Sky130 low-power level shifter cell name based on voltage step."""
        if abs(v_driver - v_receiver) < 0.05:
            return None  # Same domain voltage, no shifter needed
        drive = "_1" if load_cap_pf < 0.08 else ("_2" if load_cap_pf < 0.15 else "_4")
        if v_driver < v_receiver:
            return f"sky130_fd_sc_hd__lpflow_lsbuf_lh{drive}"
        else:
            return f"sky130_fd_sc_hd__lpflow_lsbuf_hl{drive}"

    def discover_hierarchical_instances(self) -> Dict[str, str]:
        """
        Discovers all instantiated module blocks in the top module netlist/RTL
        and returns mapping: inst_name -> module_type.
        """
        instances = {}
        if not self.proj_root:
            return instances

        # 1. Inspect reports/*_sizes.json
        sizes_json = os.path.join(self.proj_root, "reports", f"{self.top_module}_sizes.json")
        if os.path.isfile(sizes_json):
            try:
                import json
                with open(sizes_json, "r") as f:
                    d = json.load(f)
                for m in d.get("modules", {}).keys():
                    instances[m] = m
            except Exception:
                pass

        # 2. Inspect synthesized netlist or RTL source files
        candidates = [
            os.path.join(self.proj_root, "netlist", f"{self.top_module}_netlist.v"),
            os.path.join(self.proj_root, "netlist", f"{self.top_module}.v"),
            os.path.join(self.proj_root, "rtl", f"{self.top_module}.v"),
            os.path.join(self.proj_root, "source", f"{self.top_module}.v")
        ]
        path = next((p for p in candidates if os.path.isfile(p)), None)
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                m = re.search(rf"module\s+{self.top_module}\b.*?\bendmodule", content, re.DOTALL)
                text = m.group(0) if m else content
                std_prefixes = ("sky130_", "tap_", "decap_", "fill_", "conb_")
                for im in re.finditer(r"\b([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s*\(", text):
                    mod = im.group(1)
                    inst = im.group(2)
                    if not mod.startswith(std_prefixes) and mod not in (
                        "module", "input", "output", "wire", "reg", "begin", "else", "assign"
                    ):
                        instances[inst] = mod
            except Exception as e:
                print(f"[PowerDomainManager] Note parsing instances: {e}")

        return instances

    def discover_instance_ports(self, inst_name: str) -> List[Dict[str, str]]:
        """
        Extracts all ports, port directions, and connected net names for a given instance.
        Returns list of dicts: [{'name': port, 'direction': 'input'|'output', 'net': net_name}]
        """
        if not self.proj_root or not inst_name:
            return []

        candidates = [
            os.path.join(self.proj_root, "netlist", f"{self.top_module}_netlist.v"),
            os.path.join(self.proj_root, "rtl", f"{self.top_module}.v"),
            os.path.join(self.proj_root, "source", f"{self.top_module}.v")
        ]
        found_conns = {}
        module_type = None
        path = next((p for p in candidates if os.path.isfile(p)), None)
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                im = re.search(rf"\b([A-Za-z0-9_]+)\s+{inst_name}\s*\((.*?)\);", content, re.DOTALL)
                if im:
                    module_type = im.group(1)
                    conns_text = im.group(2)
                    for pm in re.finditer(r"\.([A-Za-z0-9_]+)\s*\(\s*([^)]*)\s*\)", conns_text):
                        found_conns[pm.group(1)] = pm.group(2).strip()
            except Exception:
                pass

        port_dirs = {}
        # Parse module definition to get port directions
        search_dirs = [
            os.path.join(self.proj_root, "rtl"),
            os.path.join(self.proj_root, "source"),
            os.path.join(self.proj_root, "netlist")
        ]
        if module_type:
            for sdir in search_dirs:
                if not os.path.isdir(sdir):
                    continue
                # Try specific file first
                cand_files = [os.path.join(sdir, f"{module_type}.v")]
                for f_name in sorted(os.listdir(sdir)):
                    if f_name.endswith((".v", ".sv")) and f_name != f"{module_type}.v":
                        cand_files.append(os.path.join(sdir, f_name))
                for cand_f in cand_files:
                    if os.path.isfile(cand_f):
                        try:
                            with open(cand_f, "r", encoding="utf-8") as f_in:
                                f_text = f_in.read()
                            if f"module {module_type}" in f_text:
                                f_clean = re.sub(r"//.*", "", f_text)
                                f_clean = re.sub(r"/\*.*?\*/", "", f_clean, flags=re.DOTALL)
                                mod_m = re.search(rf"\bmodule\s+{module_type}\b.*?\bendmodule", f_clean, re.DOTALL)
                                if mod_m:
                                    m_content = mod_m.group(0)
                                    for dm in re.finditer(
                                        r"\b(input|output|inout)\s+(?:wire\s+|reg\s+)?(?:signed\s+)?(?:\[[^\]]+\]\s+)?([A-Za-z0-9_]+)",
                                        m_content
                                    ):
                                        port_dirs[dm.group(2)] = dm.group(1)
                                break
                        except Exception:
                            pass
                if port_dirs:
                    break

        # Fallback to connection list if no module source was found
        all_port_names = list(port_dirs.keys()) if port_dirs else list(found_conns.keys())
        results = []
        for pname in sorted(all_port_names):
            pdir = port_dirs.get(pname, "output" if ("sleep" in pname or "iso" in pname or "status" in pname) else "input")
            net = found_conns.get(pname, "")
            results.append({
                "name": pname,
                "direction": pdir,
                "net": net
            })
        return results

    def generate_upf_text(self) -> str:
        """Generates standard IEEE-1801 Unified Power Format (UPF) script."""
        lines = [
            "## ==============================================================================",
            "## IEEE-1801 UPF Power Intent File (Generated by Silis FP Studio)",
            "## ==============================================================================",
            "upf_version 2.0",
            "",
            "# Top Power Domain",
            "create_power_domain PD_TOP -include_scope",
            "create_supply_port VDD -direction in",
            "create_supply_port VSS -direction in",
            "create_supply_net VDD -domain PD_TOP",
            "create_supply_net VSS -domain PD_TOP",
            "set_domain_supply_net PD_TOP -primary_power_net VDD -primary_ground_net VSS",
            ""
        ]

        for name, pd in self.domains.items():
            if name == "PD_TOP":
                continue
            lines.append(f"# Switched / Sub-Domain: {name}")
            elem_str = " ".join(pd.elements) if pd.elements else name.lower()
            lines.append(f"create_power_domain {name} -elements {{{elem_str}}}")

            v_pwr = f"VDD_{name}"
            v_gated = f"VDD_GATED_{name}"
            lines.append(f"create_supply_net {v_pwr} -domain {name}")
            lines.append(f"create_supply_net {v_gated} -domain {name}")
            lines.append(f"create_supply_net VSS -domain {name} -reuse")

            if pd.domain_type == "Internally Gated":
                lines.append(f"set_domain_supply_net {name} -primary_power_net {v_gated} -primary_ground_net VSS")
                lines.append(f"create_power_switch sw_{name} \\")
                lines.append(f"    -domain {name} \\")
                lines.append(f"    -input_supply_port {{in {v_pwr}}} \\")
                lines.append(f"    -output_supply_port {{out {v_gated}}} \\")
                lines.append(f"    -control_port {{sleep {pd.sleep_en}}} \\")
                lines.append(f"    -on_state {{ON in {{!sleep}}}}")
            else:
                lines.append(f"set_domain_supply_net {name} -primary_power_net {v_pwr} -primary_ground_net VSS")

            # Isolation Rules
            lines.append(f"set_isolation iso_{name} \\")
            lines.append(f"    -domain {name} \\")
            lines.append(f"    -isolation_power_net VDD \\")
            lines.append(f"    -isolation_ground_net VSS \\")
            lines.append(f"    -clamp_value 0 \\")
            lines.append(f"    -applies_to outputs")
            lines.append(f"set_isolation_control iso_{name} \\")
            lines.append(f"    -domain {name} \\")
            lines.append(f"    -isolation_signal {pd.iso_en} \\")
            lines.append(f"    -isolation_sense high")
            lines.append("")

        return "\n".join(lines)
