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
        add_btn = QPushButton("[+] Add Existing Files")
        add_btn.clicked.connect(self.add_files)
        add_folder_btn = QPushButton("[+] Add Folder")
        add_folder_btn.clicked.connect(self.add_folder)
        new_btn = QPushButton("[+] Create New File")
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
        files, _ = QFileDialog.getOpenFileNames(self, "Select RTL Files", "", "Verilog (*.v *.sv);;All Files (*)")
        for f in files:
            self.list_widget.addItem(f)

    def add_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Source Directory")
        if dir_path:
            for root, _, files in os.walk(dir_path):
                for f in files:
                    if f.endswith('.v') or f.endswith('.sv') or f.endswith('.vhd') or f.endswith('.vhdl'):
                        self.list_widget.addItem(os.path.join(root, f))

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
        add_btn = QPushButton("[+] Add .sdc File")
        add_btn.clicked.connect(self.add_files)
        new_btn = QPushButton("[+] Create New File")
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
        add_btn = QPushButton("[+] Add Testbench")
        add_btn.clicked.connect(self.add_files)
        new_btn = QPushButton("[+] Create New File")
        new_btn.clicked.connect(self.create_file)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(new_btn)
        layout.addLayout(btn_layout)

    def create_file(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Create New Testbench File", "Enter filename (e.g. tb_module.v):")
        if ok and name.strip():
            name = name.strip()
            if not (name.endswith('.v') or name.endswith('.sv')):
                name += '.v'
            self.list_widget.addItem(f"[NEW] {name}")

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Testbench Files", "", "Verilog (*.v *.sv);;All Files (*)")
        for f in files:
            self.list_widget.addItem(f)

    def get_files(self):
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]


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
        rtl_files = wizard.page(1).get_files()
        
        modules = set()
        module_pattern = re.compile(r'\bmodule\s+([a-zA-Z_][a-zA-Z0-9_]*)\b')
        entity_pattern = re.compile(r'\bentity\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', re.IGNORECASE)
        for f in rtl_files:
            try:
                with open(f, 'r', encoding='utf-8', errors='ignore') as file:
                    for _ in range(1500):
                        line = file.readline()
                        if not line: break
                        
                        # Strip inline comments to avoid natural language matches
                        line = line.split('//')[0].split('--')[0]
                        
                        match_m = module_pattern.search(line)
                        if match_m:
                            modules.add(match_m.group(1))
                            
                        match_e = entity_pattern.search(line)
                        if match_e:
                            modules.add(match_e.group(1))
            except Exception:
                pass
        
        self.top_module_combo.clear()
        self.top_module_combo.addItems(list(modules))

        name = wizard.field("project_name")
        loc = wizard.field("project_loc")
        pdk = wizard.page(4).get_pdk()
        
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
        p5 = self.page(4) 
        p6 = self.page(5) 

        try:
            os.makedirs(os.path.join(loc, "source"), exist_ok=True)
            os.makedirs(os.path.join(loc, "netlist"), exist_ok=True)
            os.makedirs(os.path.join(loc, "reports"), exist_ok=True)
            os.makedirs(os.path.join(loc, "results"), exist_ok=True)

            def route_files(files, dest_dir, prefix=""):
                routed = []
                for f in files:
                    if f.startswith("[NEW] "):
                        basename = f[6:]
                        if prefix and not basename.startswith(prefix):
                            basename = prefix + basename
                        dest = os.path.join(loc, dest_dir, basename)
                        with open(dest, 'w') as out:
                            out.write(f"// New File: {basename}\n")
                        routed.append(dest)
                        continue
                        
                    basename = os.path.basename(f)
                    if prefix and not basename.startswith(prefix):
                        basename = prefix + basename
                    dest = os.path.join(loc, dest_dir, basename)
                    if copy_src and os.path.abspath(f) != os.path.abspath(dest):
                        shutil.copy2(f, dest)
                        routed.append(dest)
                    else:
                        routed.append(f)
                return routed

            rtl_files = route_files(p2.get_files(), "source")
            
            macros_list = []
            for m_name, (stub_code, auto_gen) in p5.selected_macros.items():
                macros_list.append(m_name)
                
                if auto_gen:
                    stub_file = os.path.join(loc, "source", f"{m_name}_stub.v")
                    with open(stub_file, 'w') as f:
                        f.write(stub_code)
                    rtl_files.append(stub_file)

            sdc_files = route_files(p3.get_files(), "source")
            tb_files = route_files(p4.get_files(), "source", prefix="tb_")
            
            auto_sdc = False
            if not sdc_files:
                auto_sdc = True
                default_sdc = os.path.join(loc, "source", "default.sdc")
                with open(default_sdc, 'w') as f:
                    f.write(f"create_clock -name clk -period 10.0 [get_ports clk]\n")
                sdc_files.append(default_sdc)

            config = {
                "project_name": name,
                "top_module": p6.get_top_module(),
                "pdk": p5.get_pdk(),
                "macros": macros_list,
                "auto_sdc": auto_sdc,
                "rtl_files": rtl_files,
                "sdc_files": sdc_files,
                "tb_files": tb_files
            }
            
            proj_file = os.path.join(loc, "silis.silisproj")
            with open(proj_file, 'w') as f:
                json.dump(config, f, indent=4)

            self.project_path = loc
            self.project_config = config
            super().accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create project:\n{str(e)}")


class SilisLauncher(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Silis")
        self.resize(550, 400)
        layout = QVBoxLayout(self)

        banner = QLabel()
        pm = QPixmap("/home/jerome/silis/banneriguess.png")
        if not pm.isNull():
            banner.setPixmap(pm.scaledToWidth(530, Qt.TransformationMode.SmoothTransformation))
            banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(banner)

        title = QLabel("Silis - Silicon Scaffold")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(24)
        title.setFont(font)
        layout.addWidget(title)

        btn_new = QPushButton("Create New Project")
        btn_new.setMinimumHeight(50)
        btn_new.clicked.connect(self.new_project)
        layout.addWidget(btn_new)

        layout.addWidget(QLabel("Recent Projects:"))
        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self.open_recent)
        layout.addWidget(self.recent_list)

        btn_open = QPushButton("Browse For Project...")
        btn_open.clicked.connect(self.open_project)
        layout.addWidget(btn_open)
        
        self.selected_project_path = None
        self.selected_project_config = None
        self.cache_file = os.path.expanduser("~/.silis_recent.json")
        self.load_recent()

    def load_recent(self):
        self.recent_list.clear()
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    recent_paths = json.load(f)
                for p in recent_paths:
                    if os.path.exists(p):
                        self.recent_list.addItem(p)
            except Exception:
                pass

    def save_recent(self, path):
        recent = []
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    recent = json.load(f)
            except Exception:
                pass
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        with open(self.cache_file, 'w') as f:
            json.dump(recent[:10], f)

    def new_project(self):
        wizard = SilisProjectWizard(self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            self.selected_project_path = wizard.project_path
            self.selected_project_config = wizard.project_config
            self.save_recent(self.selected_project_path)
            self.accept()

    def open_recent(self, item):
        path = item.text()
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
