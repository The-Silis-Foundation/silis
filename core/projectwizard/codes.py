import os
import re
import json
import shutil
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from pdkmanagers.pdk.manager import PDKManager, PDKSelector
from pdkmanagers.macro.ipcatalog import MacroPickerWidget

class DragDropListWidget(QListWidget):
    """Custom ListWidget to support drag and drop for files."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.addItem(url.toLocalFile())


class Page1ProjectDetails(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Project Details")
        self.setSubTitle("Specify the project name and location.")
        layout = QVBoxLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Project Name")
        layout.addWidget(QLabel("Project Name:"))
        layout.addWidget(self.name_edit)

        loc_layout = QHBoxLayout()
        self.loc_edit = QLineEdit()
        self.loc_edit.setText(os.path.expanduser("~/silisprojects/NewProject"))
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse)
        loc_layout.addWidget(self.loc_edit)
        loc_layout.addWidget(browse_btn)
        
        layout.addWidget(QLabel("Location:"))
        layout.addLayout(loc_layout)
        
        self.registerField("project_name*", self.name_edit)
        self.registerField("project_loc*", self.loc_edit)
        self.name_edit.textChanged.connect(self.update_loc)

    def update_loc(self, text):
        if text:
            self.loc_edit.setText(os.path.expanduser(f"~/silisprojects/{text}"))

    def browse(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if dir_path:
            self.loc_edit.setText(dir_path)


class Page2Sources(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Add Sources")
        self.setSubTitle("Add RTL (.v, .sv) files to your project.")
        layout = QVBoxLayout(self)

        self.list_widget = DragDropListWidget()
        layout.addWidget(QLabel("RTL Sources (Drag and Drop supported):"))
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Files...")
        add_btn.clicked.connect(self.add_files)
        add_folder_btn = QPushButton("Add Folder...")
        add_folder_btn.clicked.connect(self.add_folder)
        new_btn = QPushButton("Create New File...")
        new_btn.clicked.connect(self.create_file)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(add_folder_btn)
        btn_layout.addWidget(new_btn)
        layout.addLayout(btn_layout)

        self.copy_check = QCheckBox("Copy sources into project directory")
        self.copy_check.setChecked(True)
        self.registerField("copy_sources", self.copy_check)
        layout.addWidget(self.copy_check)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select RTL Files", "", "HDL Files (*.v *.sv *.vhd *.vhdl);;Verilog (*.v *.sv);;VHDL (*.vhd *.vhdl);;All Files (*)")
        for f in files:
            self.list_widget.addItem(f)

    def add_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Source Directory")
        if dir_path:
            self.list_widget.addItem(os.path.abspath(dir_path))

    def create_file(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Create New RTL File", "Enter filename (e.g. module.v):")
        if ok and name.strip():
            name = name.strip()
            if not (name.endswith('.v') or name.endswith('.sv')):
                name += '.v'
            self.list_widget.addItem(f"[NEW] {name}")

    def get_files(self):
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]


class Page3Constraints(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Add Constraints")
        self.setSubTitle("Add SDC constraints for synthesis and PnR.")
        layout = QVBoxLayout(self)

        self.list_widget = DragDropListWidget()
        layout.addWidget(QLabel("Constraints (.sdc) (Drag and Drop supported):"))
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add SDC File...")
        add_btn.clicked.connect(self.add_files)
        new_btn = QPushButton("Create New File...")
        new_btn.clicked.connect(self.create_file)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(new_btn)
        layout.addLayout(btn_layout)

    def create_file(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Create New SDC File", "Enter filename (e.g. timing.sdc):")
        if ok and name.strip():
            name = name.strip()
            if not name.endswith('.sdc'):
                name += '.sdc'
            self.list_widget.addItem(f"[NEW] {name}")

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select SDC Files", "", "SDC (*.sdc);;All Files (*)")
        for f in files:
            self.list_widget.addItem(f)

    def get_files(self):
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]


class Page4Testbenches(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Add Testbenches")
        self.setSubTitle("Add simulation testbenches.")
        layout = QVBoxLayout(self)

        self.list_widget = DragDropListWidget()
        layout.addWidget(QLabel("Testbenches (Drag and Drop supported):"))
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Testbench Files...")
        add_btn.clicked.connect(self.add_files)
        add_folder_btn = QPushButton("Add Folder...")
        add_folder_btn.clicked.connect(self.add_folder)
        new_btn = QPushButton("Create New File...")
        new_btn.clicked.connect(self.create_file)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(add_folder_btn)
        btn_layout.addWidget(new_btn)
        layout.addLayout(btn_layout)

    def add_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Testbench Directory")
        if dir_path:
            self.list_widget.addItem(os.path.abspath(dir_path))

    def create_file(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Create New Testbench File", "Enter filename (e.g. tb_module.v):")
        if ok and name.strip():
            name = name.strip()
            if not (name.endswith('.v') or name.endswith('.sv') or name.endswith('.py') or name.endswith('.vhd')):
                name += '.v'
            self.list_widget.addItem(f"[NEW] {name}")

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Testbench Files", "", "Testbench Files (*.v *.sv *.py *.vhd *.vhdl);;Verilog (*.v *.sv);;Python (*.py);;VHDL (*.vhd *.vhdl);;All Files (*)")
        for f in files:
            self.list_widget.addItem(f)

    def get_files(self):
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]


class Page4bImportOthers(QWizardPage):
    """
    Import Others slide: Provides tabs for Power Management (UPF/CPF)
    and I/O Pin / Pad Ordering configuration.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Additional Design Intent")
        self.setSubTitle("Configure power gating (UPF/CPF) and physical I/O pin / pad constraints.")

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # Tab 1: Power Intent
        tab_power = QWidget()
        lay_p = QVBoxLayout(tab_power)
        lbl_p_info = QLabel("<b>Power Intent (IEEE 1801 UPF / CPF)</b><br>"
                            "Define power domains, isolation cells, and power switch gating rules.<br>"
                            "If omitted, a baseline default template (PD_TOP) is generated automatically in <code>power/design.upf</code>.")
        lbl_p_info.setWordWrap(True)
        lay_p.addWidget(lbl_p_info)

        h_upf = QHBoxLayout()
        self.ed_upf = QLineEdit()
        self.ed_upf.setPlaceholderText("Optional: Browse existing .upf or .cpf file...")
        btn_browse_upf = QPushButton("Browse...")
        btn_browse_upf.clicked.connect(self.browse_upf)
        h_upf.addWidget(self.ed_upf)
        h_upf.addWidget(btn_browse_upf)
        lay_p.addLayout(h_upf)
        lay_p.addStretch()
        self.tabs.addTab(tab_power, "Power Intent (UPF/CPF)")

        # Tab 2: Pin / Pad Order List
        tab_io = QWidget()
        lay_io = QVBoxLayout(tab_io)
        lbl_io_info = QLabel("<b>I/O Pin & Pad Ordering (.cfg / .io)</b><br>"
                             "Define perimeter edge constraints and pin ordering for OpenROAD.<br>"
                             "If omitted, a baseline template is created in <code>io/pin_order.cfg</code>.")
        lbl_io_info.setWordWrap(True)
        lay_io.addWidget(lbl_io_info)

        h_io = QHBoxLayout()
        self.ed_io = QLineEdit()
        self.ed_io.setPlaceholderText("Optional: Browse existing pin_order.cfg or .io file...")
        btn_browse_io = QPushButton("Browse...")
        btn_browse_io.clicked.connect(self.browse_io)
        h_io.addWidget(self.ed_io)
        h_io.addWidget(btn_browse_io)
        lay_io.addLayout(h_io)
        lay_io.addStretch()
        self.tabs.addTab(tab_io, "I/O Pin & Pad Order")

        layout.addWidget(self.tabs)

    def browse_upf(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Power Intent File", "", "Power Files (*.upf *.cpf);;All Files (*)")
        if f:
            self.ed_upf.setText(f)

    def browse_io(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Pin Order File", "", "Pin Config Files (*.cfg *.io *.tcl);;All Files (*)")
        if f:
            self.ed_io.setText(f)

    def get_upf_path(self):
        return self.ed_upf.text().strip()

    def get_io_path(self):
        return self.ed_io.text().strip()


class Page5SiliconTarget(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Silicon Target")
        self.setSubTitle("Select the PDK and Macro IP for physical design.")
        self.selected_macros = {}
        layout = QVBoxLayout(self)

        self.pdk_combo = QComboBox()
        self.pdk_mgr = PDKManager()
        if self.pdk_mgr.configs:
            self.pdk_combo.addItems([cfg['name'] for cfg in self.pdk_mgr.configs])
        else:
            self.pdk_combo.addItems(["sky130_fd_sc_hd"])
        
        pdk_layout = QHBoxLayout()
        pdk_layout.addWidget(self.pdk_combo)
        btn_add = QPushButton("Add Custom PDK...")
        btn_add.clicked.connect(self.add_custom_pdk)
        pdk_layout.addWidget(btn_add)
        
        layout.addWidget(QLabel("Active PDK:"))
        layout.addLayout(pdk_layout)

        layout.addWidget(QLabel("Selected Macro IP:"))
        macro_layout = QHBoxLayout()
        self.macro_list = QListWidget()
        self.macro_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        macro_layout.addWidget(self.macro_list)
        
        btn_catalog = QPushButton("Open IP Catalog\n(Shopping Cart)")
        btn_catalog.setStyleSheet("background: #0078D7; color: white; font-weight: bold; padding: 10px;")
        btn_catalog.clicked.connect(self.open_catalog)
        macro_layout.addWidget(btn_catalog)
        layout.addLayout(macro_layout)

    def add_custom_pdk(self):
        dlg = PDKSelector(self.pdk_mgr, self)
        dlg.exec()
        self.pdk_mgr = PDKManager()
        self.pdk_combo.blockSignals(True)
        self.pdk_combo.clear()
        if self.pdk_mgr.configs:
            self.pdk_combo.addItems([cfg['name'] for cfg in self.pdk_mgr.configs])
        else:
            self.pdk_combo.addItems(["sky130_fd_sc_hd"])
        self.pdk_combo.blockSignals(False)

    def open_catalog(self):
        sel_name = self.pdk_combo.currentText()
        cfg = next((c for c in self.pdk_mgr.configs if c['name'] == sel_name), None)
        if not cfg: 
            QMessageBox.warning(self, "Warning", "Select a valid PDK first.")
            return

        lib_path = cfg.get('lib', '')
        if "libs.ref" in lib_path:
            try:
                volare_base = lib_path.split("libs.ref")[0]
                stdcell_name = lib_path.split("libs.ref/")[1].split("/")[0]
                needs_save = False
                if not cfg.get('tlef'):
                    tlefs = glob.glob(os.path.join(volare_base, "libs.ref", stdcell_name, "techlef", "*__nom.tlef"))
                    if tlefs: cfg['tlef'] = tlefs[0]; needs_save = True
                if not cfg.get('gds'):
                    gdss = glob.glob(os.path.join(volare_base, "libs.ref", stdcell_name, "gds", "*.gds"))
                    if gdss: cfg['gds'] = gdss[0]; needs_save = True
                if not cfg.get('tech'):
                    techs = glob.glob(os.path.join(volare_base, "libs.tech", "magic", "*.tech"))
                    if techs: cfg['tech'] = techs[0]; needs_save = True
                if needs_save: self.pdk_mgr.update_config(cfg)
            except Exception:
                pass
            
        dlg = MacroPickerWidget(cfg, self.pdk_mgr, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, stub, auto = dlg.get_selected_macro()
            if name and name not in self.selected_macros:
                self.selected_macros[name] = (stub, auto)
                self.macro_list.addItem(name)

    def get_pdk(self):
        return self.pdk_combo.currentText()

    def get_macros(self):
        return [item.text() for item in self.macro_list.selectedItems()]


class Page6Summary(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Project Summary")
        self.setSubTitle("Review settings and select the Top Module.")
        layout = QVBoxLayout(self)

        self.top_module_combo = QComboBox()
        self.top_module_combo.setEditable(True)
        layout.addWidget(QLabel("Top Module:"))
        layout.addWidget(self.top_module_combo)

        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)

    def initializePage(self):
        wizard = self.wizard()
        raw_entries = wizard.page(1).get_files()
        rtl_files = []
        for item in raw_entries:
            if item.startswith("[NEW] "):
                rtl_files.append(item)
            elif os.path.isdir(item):
                for root, _, files in os.walk(item):
                    if any(ignored in root for ignored in ['/.', '/build', '__pycache__', '/.git']):
                        continue
                    for f in files:
                        if f.lower().endswith(('.v', '.sv', '.vhd', '.vhdl', '.vhd2008')):
                            rtl_files.append(os.path.join(root, f))
            elif os.path.isfile(item):
                rtl_files.append(item)

        # Run intelligent source scanner and topological sorter if available
        candidates = []
        try:
            from intake.source_scanner import scan_sources
            from intake.dependency_graph import topological_sort
            from intake.top_finder import find_top_candidates

            valid_paths = [f for f in rtl_files if not f.startswith("[NEW] ") and os.path.exists(f)]
            if valid_paths:
                sources = scan_sources(valid_paths)
                sorted_sources = topological_sort(sources)
                cands = find_top_candidates(sorted_sources)
                candidates = [c[0] for c in cands]
        except Exception:
            candidates = []

        if not candidates:
            modules = set()
            module_pattern = re.compile(r'\bmodule\s+([a-zA-Z_][a-zA-Z0-9_]*)\b')
            entity_pattern = re.compile(r'\bentity\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', re.IGNORECASE)
            for f in rtl_files:
                try:
                    with open(f, 'r', encoding='utf-8', errors='ignore') as file:
                        for _ in range(1500):
                            line = file.readline()
                            if not line: break
                            line = line.split('//')[0].split('--')[0]
                            match_m = module_pattern.search(line)
                            if match_m:
                                modules.add(match_m.group(1))
                            match_e = entity_pattern.search(line)
                            if match_e:
                                modules.add(match_e.group(1))
                except Exception:
                    pass
            candidates = list(modules)

        self.top_module_combo.clear()
        self.top_module_combo.addItems(candidates)

        name = wizard.field("project_name")
        loc = wizard.field("project_loc")
        pdk = wizard.page(5).get_pdk()
        
        self.summary_label.setText(f"Name: {name}\nLocation: {loc}\nPDK: {pdk}\n\nClick Finish to generate the project structure.")

    def get_top_module(self):
        return self.top_module_combo.currentText()


class SilisProjectWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Silis Project")
        self.resize(750, 550)
        
        self.addPage(Page1ProjectDetails())
        self.addPage(Page2Sources())
        self.addPage(Page3Constraints())
        self.addPage(Page4Testbenches())
        self.addPage(Page4bImportOthers())
        self.addPage(Page5SiliconTarget())
        self.addPage(Page6Summary())
        
        self.project_path = None
        self.project_config = None

    def accept(self):
        name = self.field("project_name")
        loc = self.field("project_loc")
        copy_src = self.field("copy_sources")
        
        p2 = self.page(1) 
        p3 = self.page(2) 
        p4 = self.page(3) 
        p4b = self.page(4)
        p5 = self.page(5) 
        p6 = self.page(6) 

        try:
            os.makedirs(os.path.join(loc, "rtl"), exist_ok=True)
            os.makedirs(os.path.join(loc, "tb"), exist_ok=True)
            os.makedirs(os.path.join(loc, "constr"), exist_ok=True)
            os.makedirs(os.path.join(loc, "power"), exist_ok=True)
            os.makedirs(os.path.join(loc, "io"), exist_ok=True)
            os.makedirs(os.path.join(loc, "netlist"), exist_ok=True)
            os.makedirs(os.path.join(loc, "reports"), exist_ok=True)
            os.makedirs(os.path.join(loc, "results"), exist_ok=True)

            def route_files(files, dest_dir, prefix=""):
                routed = []
                valid_exts = ('.v', '.sv', '.vhd', '.vhdl', '.vhd2008', '.sdc', '.py', '.c', '.cpp', '.h', '.hpp')
                for item in files:
                    if item.startswith("[NEW] "):
                        basename = os.path.basename(item[6:])
                        if prefix and not basename.startswith(prefix):
                            basename = prefix + basename
                        dest = os.path.join(loc, dest_dir, basename)
                        with open(dest, 'w') as out:
                            out.write(f"// New File: {basename}\n")
                        routed.append(dest)
                        continue

                    if os.path.isdir(item):
                        # Preserve entire subfolder hierarchy under dest_dir
                        for root, _, walk_files in os.walk(item):
                            if any(ignored in root for ignored in ['/.', '/build', '__pycache__', '/.git']):
                                continue
                            for f in walk_files:
                                if f.lower().endswith(valid_exts):
                                    src_f = os.path.join(root, f)
                                    rel_sub = os.path.relpath(src_f, item)
                                    dest = os.path.join(loc, dest_dir, rel_sub)
                                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                                    if copy_src and os.path.abspath(src_f) != os.path.abspath(dest):
                                        shutil.copy2(src_f, dest)
                                        routed.append(dest)
                                    else:
                                        routed.append(dest if copy_src else src_f)
                    elif os.path.isfile(item):
                        basename = os.path.basename(item)
                        if prefix and not basename.startswith(prefix):
                            basename = prefix + basename
                        dest = os.path.join(loc, dest_dir, basename)
                        if copy_src and os.path.abspath(item) != os.path.abspath(dest):
                            shutil.copy2(item, dest)
                            routed.append(dest)
                        else:
                            routed.append(dest if copy_src else item)
                    else:
                        # Fallback for paths that might not yet exist or template markers
                        basename = os.path.basename(item)
                        dest = os.path.join(loc, dest_dir, basename)
                        routed.append(dest)
                return routed

            rtl_files = route_files(p2.get_files(), "rtl")
            
            macros_list = []
            for m_name, (stub_code, auto_gen) in p5.selected_macros.items():
                macros_list.append(m_name)
                
                if auto_gen:
                    stub_file = os.path.join(loc, "rtl", f"{m_name}_stub.v")
                    with open(stub_file, 'w') as f:
                        f.write(stub_code)
                    rtl_files.append(stub_file)

            sdc_files = route_files(p3.get_files(), "constr")
            tb_files = route_files(p4.get_files(), "tb")
            
            auto_sdc = False
            if not sdc_files:
                auto_sdc = True
                default_sdc = os.path.join(loc, "constr", "default.sdc")
                with open(default_sdc, 'w') as f:
                    f.write(f"create_clock -name clk -period 10.0 [get_ports clk]\n")
                sdc_files.append(default_sdc)

            # Detect VHDL / Mixed sources and auto-populate vhdl_work and vhdl_std
            has_vhdl = any(f.lower().endswith(('.vhd', '.vhdl', '.vhd2008')) for f in rtl_files)
            work_lib = "neorv32" if any("neorv32" in f.lower() for f in rtl_files) else "work"

            # Handle Power Intent (UPF)
            upf_src = p4b.get_upf_path() if hasattr(p4b, "get_upf_path") else ""
            final_upf = os.path.join(loc, "power", "design.upf")
            if upf_src and os.path.isfile(upf_src):
                shutil.copy2(upf_src, final_upf)
            else:
                from backendflow.power.upf_engine import create_default_upf
                create_default_upf(final_upf, top_module=p6.get_top_module() or name)

            # Handle Pin / Pad Order List (.cfg / .io)
            io_src = p4b.get_io_path() if hasattr(p4b, "get_io_path") else ""
            final_io = os.path.join(loc, "io", "pin_order.cfg")
            if io_src and os.path.isfile(io_src):
                shutil.copy2(io_src, final_io)
            else:
                with open(final_io, "w") as f_io:
                    f_io.write(f"# Silis Pin Placement Configuration\n# Project: {name}\n\n[NORTH]\n\n[SOUTH]\n\n[EAST]\n\n[WEST]\n")

            config = {
                "project_name": name,
                "top_module": p6.get_top_module(),
                "pdk": p5.get_pdk(),
                "macros": macros_list,
                "auto_sdc": auto_sdc,
                "rtl_files": rtl_files,
                "sdc_files": sdc_files,
                "tb_files": tb_files,
                "upf_file": final_upf,
                "pin_order_file": final_io
            }
            if has_vhdl:
                config["vhdl_work"] = work_lib
                config["vhdl_std"] = "08"
            
            proj_file = os.path.join(loc, "silis.silisproj")
            with open(proj_file, 'w') as f:
                json.dump(config, f, indent=4)

            self.project_path = loc
            self.project_config = config
            import project_registry
            project_registry.register_project(loc)
            super().accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create project:\n{str(e)}")


class SilisLauncher(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Silis")
        self.resize(600, 420)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout(self)

        banner = QLabel()
        banner_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "banneriguess.png"))
        pm = QPixmap(banner_path)
        if not pm.isNull():
            banner.setPixmap(pm.scaledToWidth(580, Qt.TransformationMode.SmoothTransformation))
            banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(banner)

        title = QLabel("Silis - Silicon Scaffold")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(22)
        title.setFont(font)
        layout.addWidget(title)

        btn_new = QPushButton("Create New Project")
        btn_new.setMinimumHeight(45)
        btn_new.clicked.connect(self.new_project)
        layout.addWidget(btn_new)

        layout.addWidget(QLabel("Registered Projects (CLI & GUI):"))
        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self.open_recent)
        layout.addWidget(self.recent_list)

        btn_open = QPushButton("Browse For Project...")
        btn_open.clicked.connect(self.open_project)
        layout.addWidget(btn_open)
        
        self.selected_project_path = None
        self.selected_project_config = None
        self.load_recent()

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def load_recent(self):
        self.recent_list.clear()
        import project_registry
        for proj in project_registry.get_registered_projects():
            display_text = f"{proj['name']} [{proj['top']} | {proj['pdk']}]  —  {proj['path']}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, proj['path'])
            item.setToolTip(f"Path: {proj['path']}\nTop: {proj['top']}\nPDK: {proj['pdk']}")
            self.recent_list.addItem(item)

    def save_recent(self, path):
        import project_registry
        project_registry.register_project(path)

    def new_project(self):
        wizard = SilisProjectWizard(self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            self.selected_project_path = wizard.project_path
            self.selected_project_config = wizard.project_config
            self.save_recent(self.selected_project_path)
            self.accept()

    def open_recent(self, item):
        path = item.data(Qt.ItemDataRole.UserRole) or item.text()
        self.load_project_file(os.path.join(path, "silis.silisproj"))

    def open_project(self):
        proj_file, _ = QFileDialog.getOpenFileName(self, "Open Silis Project", os.path.expanduser("~"), "Silis Project (*.silisproj)")
        if proj_file:
            self.load_project_file(proj_file)

    def load_project_file(self, proj_file):
        if os.path.exists(proj_file):
            try:
                with open(proj_file, 'r') as f:
                    self.selected_project_config = json.load(f)
                self.selected_project_path = os.path.dirname(proj_file)
                self.save_recent(self.selected_project_path)
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not load project: {e}")
        else:
            QMessageBox.warning(self, "Error", "Project file not found.")
