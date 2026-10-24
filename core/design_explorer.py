import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeView, QLineEdit,
    QHeaderView, QMenu, QDialog, QListWidget, QListWidgetItem, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QAbstractItemModel
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon, QAction

class HierarchyNode:
    def __init__(self, name, node_type, file_path=None, line=1, col=1, decl_name=None, parent=None):
        self.name = name
        self.node_type = node_type  # 'top', 'module', 'instance', 'port', 'cell', 'signal'
        self.file_path = file_path
        self.line = line
        self.col = col
        self.decl_name = decl_name or name
        self.parent = parent
        self.children = []

    def add_child(self, child):
        child.parent = self
        self.children.append(child)

class DesignHierarchyModel(QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(["Design Hierarchy", "Type"])

    def populate(self, tree_data):
        self.clear()
        self.setHorizontalHeaderLabels(["Design Hierarchy", "Type"])
        if not tree_data:
            return

        def build_items(node):
            item_name = QStandardItem(node.name)
            item_name.setData(node, Qt.ItemDataRole.UserRole)
            
            # Styling / Icons based on node_type
            type_label = node.node_type
            if node.node_type == "instance":
                type_label = f"[{node.decl_name}]"
            item_type = QStandardItem(type_label)
            item_type.setData(node, Qt.ItemDataRole.UserRole)

            for child in node.children:
                child_items = build_items(child)
                item_name.appendRow(child_items)
            return [item_name, item_type]

        for root_node in tree_data:
            self.appendRow(build_items(root_node))

class FindInstanceDialog(QDialog):
    instanceSelected = pyqtSignal(str, str, int, int) # (inst_path, file_path, line, col)

    def __init__(self, instances, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find Instance (QuickPick)")
        self.setMinimumWidth(550)
        self.setMinimumHeight(350)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        lbl = QLabel("Type instance or module path:")
        layout.addWidget(lbl)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("e.g. top.u_alu or simple_alu")
        self.search_edit.textChanged.connect(self.filter_instances)
        layout.addWidget(self.search_edit)
        
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_item_chosen)
        layout.addWidget(self.list_widget)
        
        self.all_instances = instances # list of tuples: (full_path, decl_type, file_path, line, col)
        self.filter_instances("")

    def filter_instances(self, query):
        self.list_widget.clear()
        q = query.strip().lower()
        count = 0
        for inst_path, decl_type, f_path, line, col in self.all_instances:
            if not q or (q in inst_path.lower() or q in decl_type.lower()):
                item = QListWidgetItem(f"{inst_path}  [{decl_type}]  ({os.path.basename(f_path) if f_path else ''}:{line})")
                item.setData(Qt.ItemDataRole.UserRole, (inst_path, f_path, line, col))
                self.list_widget.addItem(item)
                count += 1
                if count >= 200: # Cap to match sv-pathfinder
                    break

    def on_item_chosen(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.instanceSelected.emit(*data)
            self.accept()

class DesignExplorerPanel(QWidget):
    goToSource = pyqtSignal(str, int, int)          # file, line, col
    openSchematic = pyqtSignal(str)                 # module_name
    showInWaveform = pyqtSignal(str)                # signal_name

    def __init__(self, ide=None, parent=None, file_explorer=None):
        super().__init__(parent)
        self.ide = ide
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Tabs: Files | Hierarchy | Modules
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.layout.addWidget(self.tabs)
        
        # 1. Files Tab: silis QFileSystemModel explorer
        if file_explorer is not None:
            self.file_explorer = file_explorer
        else:
            try:
                from silis import SilisExplorer
                self.file_explorer = SilisExplorer(self.ide)
            except Exception:
                import sys
                main_mod = sys.modules.get('__main__')
                if main_mod and hasattr(main_mod, 'SilisExplorer'):
                    self.file_explorer = main_mod.SilisExplorer(self.ide)
                else:
                    self.file_explorer = QTreeView(self)
        self.tabs.addTab(self.file_explorer, "Files")
        
        # 2. Hierarchy Tab: TreeView of elaborated modules/instances
        self.hier_widget = QWidget()
        hier_lay = QVBoxLayout(self.hier_widget)
        hier_lay.setContentsMargins(2, 2, 2, 2)
        
        # Top bar with Quick Search & Refresh
        tb_lay = QHBoxLayout()
        self.search_btn = QLineEdit()
        self.search_btn.setPlaceholderText("Filter hierarchy (Ctrl+I to Find)...")
        self.search_btn.textChanged.connect(self.filter_hierarchy)
        tb_lay.addWidget(self.search_btn)

        from PyQt6.QtWidgets import QPushButton
        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setFixedWidth(28)
        self.btn_refresh.setToolTip("Scan & Refresh Design Hierarchy")
        self.btn_refresh.clicked.connect(self.scan_workspace)
        tb_lay.addWidget(self.btn_refresh)
        hier_lay.addLayout(tb_lay)
        
        self.hier_tree = QTreeView()
        self.hier_model = DesignHierarchyModel(self)
        self.hier_tree.setModel(self.hier_model)
        self.hier_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.hier_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hier_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.hier_tree.doubleClicked.connect(self.on_node_double_clicked)
        hier_lay.addWidget(self.hier_tree)
        
        self.tabs.addTab(self.hier_widget, "Hierarchy")
        
        # 3. Modules Tab
        self.modules_list = QListWidget()
        self.modules_list.itemDoubleClicked.connect(self.on_module_item_double_clicked)
        self.tabs.addTab(self.modules_list, "Modules")

        self.indexed_instances = []
        self.active_design_data = None

    def scan_workspace(self):
        """Scans workspace RTL files directly to immediately build the hierarchy tree without waiting for synthesis."""
        if not self.ide or not hasattr(self.ide, 'cwd'):
            return
        cwd = self.ide.cwd
        import glob
        import re

        rtl_files = []
        if hasattr(self.ide, 'project_config') and self.ide.project_config and self.ide.project_config.get("rtl_files"):
            for f in self.ide.project_config.get("rtl_files"):
                abs_f = f if os.path.isabs(f) else os.path.join(cwd, f)
                if os.path.isfile(abs_f):
                    rtl_files.append(abs_f)
        if not rtl_files:
            rtl_files = (glob.glob(os.path.join(cwd, "source", "*.v")) +
                         glob.glob(os.path.join(cwd, "source", "*.sv")) +
                         glob.glob(os.path.join(cwd, "*.v")) +
                         glob.glob(os.path.join(cwd, "*.sv")))

        if not rtl_files:
            return

        # Simple fast AST scanner for Verilog / SystemVerilog modules & instances
        modules = {}
        for f_path in rtl_files:
            abs_f_path = os.path.abspath(f_path)
            try:
                with open(abs_f_path, 'r', errors='ignore') as f:
                    orig_content = f.read()
            except Exception:
                continue

            # Mask out comments and procedural blocks (always, initial, function, task)
            # using space substitution so string length and byte positions remain 100% 1:1 with orig_content
            masked = re.sub(r'//[^\n]*', lambda m: ' ' * len(m.group(0)), orig_content)
            masked = re.sub(r'/\*[\s\S]*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), masked)
            masked_clean = re.sub(r'\b(always|always_ff|always_comb|always_latch|initial|function|task)\b[\s\S]*?\bend(?:function|task)?\b',
                                  lambda m: re.sub(r'[^\n]', ' ', m.group(0)), masked)

            # Find module definitions
            mod_iter = re.finditer(r'\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\([\s\S]*?\)\s*)?\s*(?:\(([\s\S]*?)\))?\s*;([\s\S]*?)\bendmodule\b', masked)
            for m in mod_iter:
                mod_name = m.group(1)
                line_no = orig_content[:m.start()].count('\n') + 1

                # Extract ports with exact line numbers
                ports = {}
                port_decl_re = re.compile(r'\b(input|output|inout)\s+(?:(?:wire|reg|logic|bit|signed|\s+|\[[\d:]+\])*)\s*([A-Za-z_][A-Za-z0-9_$]*)')
                for p_match in port_decl_re.finditer(masked):
                    if m.start() <= p_match.start() <= m.end():
                        p_dir = p_match.group(1)
                        p_name = p_match.group(2)
                        p_line = orig_content[:p_match.start()].count('\n') + 1
                        ports[p_name] = {
                            "direction": p_dir,
                            "attributes": {"src": f"{abs_f_path}:{p_line}.1"}
                        }

                # Match sub-module instantiations outside procedural blocks
                cells = {}
                inst_re = re.compile(r'\b([A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\([\s\S]*?\)\s*)?\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\(([\s\S]*?)\)\s*;')
                for im in inst_re.finditer(masked_clean):
                    if m.start() <= im.start() <= m.end():
                        cell_type, inst_name = im.group(1), im.group(2)
                        if cell_type not in ('module', 'input', 'output', 'inout', 'wire', 'reg', 'logic', 'bit', 'assign', 'always', 'always_ff', 'always_comb'):
                            inst_line = orig_content[:im.start()].count('\n') + 1
                            cells[inst_name] = {
                                "type": cell_type,
                                "attributes": {"src": f"{abs_f_path}:{inst_line}.1"}
                            }

                modules[mod_name] = {
                    "attributes": {"src": f"{abs_f_path}:{line_no}.1"},
                    "ports": ports,
                    "cells": cells
                }

        if modules:
            top_mod = None
            if hasattr(self.ide, 'project_config') and self.ide.project_config:
                top_mod = self.ide.project_config.get("top_module")
            if not top_mod or top_mod not in modules:
                # Top module is one not instantiated by any other module
                all_instantiated = {c_data.get("type") for m in modules.values() for c_data in m.get("cells", {}).values()}
                candidates = [m for m in modules if m not in all_instantiated]
                top_mod = candidates[0] if candidates else list(modules.keys())[0]

            self.build_hierarchy({"modules": modules}, top_module=top_mod)

    def filter_hierarchy(self, text):
        pass

    def open_find_instance_dialog(self):
        dlg = FindInstanceDialog(self.indexed_instances, self)
        dlg.instanceSelected.connect(self.on_instance_located)
        dlg.exec()

    def on_instance_located(self, inst_path, f_path, line, col):
        if f_path and os.path.exists(f_path):
            self.goToSource.emit(f_path, line, col)
        # Also navigate schematic
        leaf = inst_path.split(".")[-1]
        self.openSchematic.emit(leaf)

    def load_design_json(self, json_path, top_module=None):
        if not os.path.exists(json_path):
            return
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            self.build_hierarchy(data, top_module)
        except Exception as e:
            print(f"Error loading design JSON into Hierarchy Tree: {e}")

    def build_hierarchy(self, data, top_module=None):
        self.active_design_data = data
        modules = data.get("modules", {})
        if not modules:
            return

        if not top_module or top_module not in modules:
            # Pick the module marked top: 1 or the first module
            top_module = next((m for m, m_data in modules.items() if m_data.get("attributes", {}).get("top") == 1), list(modules.keys())[0])

        self.indexed_instances = []
        self.modules_list.clear()

        # Populate Modules View
        for mod_name, mod_data in modules.items():
            inst_count = 0
            for other_m, other_d in modules.items():
                for c_name, c_data in other_d.get("cells", {}).items():
                    if c_data.get("type") == mod_name:
                        inst_count += 1
            src_pos = mod_data.get("attributes", {}).get("src", "")
            f_path, line, col = self._parse_src(src_pos)
            item = QListWidgetItem(f"{mod_name}  ({inst_count} instances)")
            item.setData(Qt.ItemDataRole.UserRole, (mod_name, f_path, line, col))
            self.modules_list.addItem(item)

        # Recursively construct elaborated hierarchy
        def expand_scope(mod_name, inst_path="", parent_node=None):
            m_data = modules.get(mod_name, {})
            src_pos = m_data.get("attributes", {}).get("src", "")
            f_path, line, col = self._parse_src(src_pos)
            
            node_name = inst_path if inst_path else mod_name
            node = HierarchyNode(node_name, "module" if inst_path else "top", f_path, line, col, decl_name=mod_name)
            
            if inst_path:
                self.indexed_instances.append((inst_path, mod_name, f_path, line, col))

            # Add Ports
            ports = m_data.get("ports", {})
            for p_name, p_data in ports.items():
                p_dir = p_data.get("direction", "port")
                p_src = p_data.get("attributes", {}).get("src", "")
                pf_path, pline, pcol = self._parse_src(p_src) if p_src else (f_path, line, col)
                node.add_child(HierarchyNode(f"{p_name} ({p_dir})", "port", pf_path, pline, pcol))

            # Add Child Instances
            cells = m_data.get("cells", {})
            for c_name, c_data in cells.items():
                c_type = c_data.get("type", "")
                c_src = c_data.get("attributes", {}).get("src", "")
                cf_path, cline, ccol = self._parse_src(c_src) or (f_path, line, col)
                child_path = f"{inst_path}.{c_name}" if inst_path else c_name

                if c_type in modules:
                    # Submodule instantiation
                    child_node = expand_scope(c_type, child_path, node)
                    child_node.name = f"{c_name} ({c_type})"
                    child_node.line = cline
                    child_node.col = ccol
                    child_node.file_path = cf_path
                    node.add_child(child_node)
                else:
                    # Logic cell primitive
                    if not c_data.get("hide_name"):
                        self.indexed_instances.append((child_path, c_type, cf_path, cline, ccol))
                        node.add_child(HierarchyNode(f"{c_name} [{c_type}]", "cell", cf_path, cline, ccol))

            return node

        root = expand_scope(top_module)
        self.hier_model.populate([root])
        self.hier_tree.expandToDepth(1)

    def _parse_src(self, src_str):
        if not src_str or ":" not in src_str:
            return None, 1, 1
        try:
            parts = src_str.split(":")
            f_path = parts[0]
            line_parts = parts[1].split("-")[0].split(".")
            line = int(line_parts[0])
            col = int(line_parts[1]) if len(line_parts) > 1 else 1
            if not os.path.isabs(f_path) and self.ide and hasattr(self.ide, 'cwd'):
                f_path = os.path.join(self.ide.cwd, f_path)
            return f_path, line, col
        except Exception:
            return None, 1, 1

    def on_node_double_clicked(self, index):
        item = self.hier_model.itemFromIndex(index)
        if not item: return
        node = item.data(Qt.ItemDataRole.UserRole)
        if node:
            if node.file_path and os.path.exists(node.file_path):
                self.goToSource.emit(node.file_path, node.line, node.col)
            if node.decl_name:
                self.openSchematic.emit(node.decl_name)

    def on_module_item_double_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            mod_name, f_path, line, col = data
            if f_path and os.path.exists(f_path):
                self.goToSource.emit(f_path, line, col)
            self.openSchematic.emit(mod_name)

    def show_context_menu(self, pos):
        index = self.hier_tree.indexAt(pos)
        if not index.isValid(): return
        item = self.hier_model.itemFromIndex(index)
        if not item: return
        node = item.data(Qt.ItemDataRole.UserRole)
        if not node: return

        menu = QMenu(self)
        
        act_source = menu.addAction("Go to Source")
        act_source.triggered.connect(lambda: self.goToSource.emit(node.file_path, node.line, node.col) if node.file_path else None)
        
        act_schem = menu.addAction("Show in Schematic")
        act_schem.triggered.connect(lambda: self.openSchematic.emit(node.decl_name))
        
        act_wave = menu.addAction("Show in Waveform")
        act_wave.triggered.connect(lambda: self.showInWaveform.emit(node.name))

        menu.exec(self.hier_tree.viewport().mapToGlobal(pos))
