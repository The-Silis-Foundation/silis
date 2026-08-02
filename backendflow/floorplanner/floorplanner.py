import os
import re
import json
import glob
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from backendflow.siliconpeeker.peeker import DEFParser

class InteractiveGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._zoom_factor = 1.15

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.scale(self._zoom_factor, self._zoom_factor)
            else:
                self.scale(1 / self._zoom_factor, 1 / self._zoom_factor)
        else:
            super().wheelEvent(event)


class HoverTextItem(QGraphicsTextItem):
    def __init__(self, text, base_color="#E2E8F0"):
        super().__init__(text)
        self.setAcceptHoverEvents(True)
        self.base_color = QColor(base_color)
        self.hover_color = QColor("#00FFFF")
        self.setDefaultTextColor(self.base_color)
        self.bg_brush = QBrush(QColor("#1E1E1E"))
        
    def hoverEnterEvent(self, event):
        self.setScale(2.5)
        self.setDefaultTextColor(self.hover_color)
        self.setZValue(100)
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        self.setScale(1.0)
        self.setDefaultTextColor(self.base_color)
        self.setZValue(0)
        super().hoverLeaveEvent(event)
        
    def paint(self, painter, option, widget):
        if self.scale() > 1.0:
            painter.setBrush(self.bg_brush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(self.boundingRect())
        super().paint(painter, option, widget)


class FloorplanView(InteractiveGraphicsView):
    macro_dropped = pyqtSignal(str, float, float, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            pos = self.mapToScene(event.position().toPoint())
            data = event.mimeData().text()
            if "|" in data:
                master_name, inst_name = data.split("|", 1)
            else:
                master_name = data
                inst_name = None
            self.macro_dropped.emit(master_name, pos.x(), pos.y(), inst_name)
            event.acceptProposedAction()


class MacroItem(QGraphicsRectItem):
    def __init__(self, name, width, height, core_rect, widget_ref, parent=None):
        super().__init__(0, 0, width, height, parent)
        self.name = name
        self.inst_name = f"{name}_inst"
        self.w = width
        self.h = height
        self.core_rect = core_rect
        self.widget_ref = widget_ref
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setBrush(QBrush(QColor("#4CAF50")))
        self.setPen(QPen(Qt.GlobalColor.black))
        
        self.text = QGraphicsTextItem(f"{self.inst_name}\n({name})", self)
        self.text.setDefaultTextColor(Qt.GlobalColor.white)
        self.text.setTransform(QTransform.fromScale(1, -1))
        # Center text
        br = self.text.boundingRect()
        self.text.setPos(width/2 - br.width()/2, height/2 + br.height()/2)

    def set_inst_name(self, inst_name):
        self.inst_name = inst_name
        self.text.setPlainText(f"{self.inst_name}\n({self.name})")
        br = self.text.boundingRect()
        self.text.setPos(self.w/2 - br.width()/2, self.h/2 + br.height()/2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            x, y = value.x(), value.y()
            x = round(x)
            y = round(y)
            if self.core_rect:
                max_x = self.core_rect.width() - self.w
                max_y = self.core_rect.height() - self.h
                if x < self.core_rect.x(): x = self.core_rect.x()
                if y < self.core_rect.y(): y = self.core_rect.y()
                if x > self.core_rect.x() + max_x: x = self.core_rect.x() + max_x
                if y > self.core_rect.y() + max_y: y = self.core_rect.y() + max_y
            
            if self.isSelected():
                self.widget_ref.sp_sel_x.blockSignals(True)
                self.widget_ref.sp_sel_y.blockSignals(True)
                self.widget_ref.txt_inst_name.blockSignals(True)
                self.widget_ref.sp_sel_x.setValue(x)
                self.widget_ref.sp_sel_y.setValue(y)
                self.widget_ref.txt_inst_name.setText(self.inst_name)
                self.widget_ref.sp_sel_x.blockSignals(False)
                self.widget_ref.sp_sel_y.blockSignals(False)
                self.widget_ref.txt_inst_name.blockSignals(False)
                
            return QPointF(x, y)
        return super().itemChange(change, value)


class InteractiveFloorplannerWidget(QDialog):
    def __init__(self, project_config, pdk_mgr, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Floorplanner")
        self.resize(1200, 800)
        self.project_config = project_config
        self.pdk_mgr = pdk_mgr
        self.floorplan_initialized = False
        self.die_rect = None
        self.core_rect = None
        self.macro_sizes = {}
        self.parse_macro_sizes()
        
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        gb_die = QGroupBox("Die & Core Specifications")
        fl_die = QFormLayout(gb_die)
        self.sp_die_w = QDoubleSpinBox(); self.sp_die_w.setRange(0.1, 100000); self.sp_die_w.setValue(5000)
        self.sp_die_h = QDoubleSpinBox(); self.sp_die_h.setRange(0.1, 100000); self.sp_die_h.setValue(5000)
        self.sp_marg_t = QDoubleSpinBox(); self.sp_marg_t.setRange(0, 10000); self.sp_marg_t.setValue(10)
        self.sp_marg_b = QDoubleSpinBox(); self.sp_marg_b.setRange(0, 10000); self.sp_marg_b.setValue(10)
        self.sp_marg_l = QDoubleSpinBox(); self.sp_marg_l.setRange(0, 10000); self.sp_marg_l.setValue(10)
        self.sp_marg_r = QDoubleSpinBox(); self.sp_marg_r.setRange(0, 10000); self.sp_marg_r.setValue(10)
        fl_die.addRow("Die Width (µm):", self.sp_die_w)
        fl_die.addRow("Die Height (µm):", self.sp_die_h)
        fl_die.addRow("Margin Top (µm):", self.sp_marg_t)
        fl_die.addRow("Margin Bottom (µm):", self.sp_marg_b)
        fl_die.addRow("Margin Left (µm):", self.sp_marg_l)
        fl_die.addRow("Margin Right (µm):", self.sp_marg_r)
        
        self.btn_init = QPushButton("Initialize Floorplan")
        self.btn_init.setStyleSheet("background: #0078D7; color: white; font-weight: bold;")
        self.btn_init.clicked.connect(self.init_floorplan)
        fl_die.addRow(self.btn_init)
        left_layout.addWidget(gb_die)
        
        gb_sel = QGroupBox("Selected Macro")
        fl_sel = QFormLayout(gb_sel)
        self.lbl_sel_name = QLabel("None")
        
        self.txt_inst_name = QLineEdit()
        self.txt_inst_name.setPlaceholderText("Netlist Instance Name")
        self.txt_inst_name.editingFinished.connect(self.on_inst_name_changed)
        
        self.sp_sel_x = QDoubleSpinBox(); self.sp_sel_x.setRange(0, 100000)
        self.sp_sel_y = QDoubleSpinBox(); self.sp_sel_y.setRange(0, 100000)
        fl_sel.addRow("Macro:", self.lbl_sel_name)
        fl_sel.addRow("Instance:", self.txt_inst_name)
        fl_sel.addRow("X (µm):", self.sp_sel_x)
        fl_sel.addRow("Y (µm):", self.sp_sel_y)
        self.sp_sel_x.valueChanged.connect(self.on_spinbox_changed)
        self.sp_sel_y.valueChanged.connect(self.on_spinbox_changed)
        left_layout.addWidget(gb_sel)
        
        btn_tcl = QPushButton("Apply Floorplan & Run")
        btn_tcl.setStyleSheet("background: #0078D7; color: white; font-weight: bold;")
        btn_tcl.clicked.connect(self.generate_floorplan_tcl)
        left_layout.addWidget(btn_tcl)
        left_layout.addStretch()
        splitter.addWidget(left_widget)
        
        mid_widget = QWidget()
        mid_layout = QVBoxLayout(mid_widget)
        self.view = FloorplanView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        # Scale Y by -1 so that Y increases upwards (EDA standard)
        self.view.scale(1, -1)
        self.view.macro_dropped.connect(self.on_macro_dropped)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        mid_layout.addWidget(self.view)
        splitter.addWidget(mid_widget)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.tabs = QTabWidget()
        
        self.macro_list = QListWidget()
        self.macro_list.setDragEnabled(True)
        # Setup Draggable List
        self.macro_list.startDrag = self.start_drag
        self.tabs.addTab(self.macro_list, "Macros")
        
        self.pin_list = QListWidget()
        self.pin_list.setDragEnabled(True)
        self.tabs.addTab(self.pin_list, "I/O Pins")
        
        right_layout.addWidget(self.tabs)
        splitter.addWidget(right_widget)
        
        splitter.setSizes([250, 600, 200])
        self.tabs.setEnabled(False)
        if self.project_config: self.populate_macro_list(self.project_config)

    def start_drag(self, supportedActions):
        item = self.macro_list.currentItem()
        if not item: return
        drag = QDrag(self.macro_list)
        mimeData = QMimeData()
        
        inst_name = item.data(Qt.ItemDataRole.UserRole)
        text = item.text().replace(" [PLACED]", "")
        if inst_name:
            mimeData.setText(f"{text}|{inst_name}")
        else:
            mimeData.setText(text)
        
        drag.setMimeData(mimeData)
        drag.exec(supportedActions)

    def populate_macro_list(self, cfg):
        self.macro_list.clear()
        
        # Try loading from _sizes.json
        proj_root = self.parent().ide.get_proj_root(self.parent().ide.get_context()[0] or "design")
        base = self.parent().ide.get_context()[1]
        if base:
            sizes_json_path = os.path.join(proj_root, "reports", f"{base}_sizes.json").replace("\\", "/")
            if os.path.exists(sizes_json_path):
                try:
                    import json
                    with open(sizes_json_path, 'r') as f:
                        sizes_data = json.load(f)
                    if 'macros' in sizes_data:
                        for inst_name, master_name in sizes_data['macros'].items():
                            item = QListWidgetItem(master_name)
                            item.setData(Qt.ItemDataRole.UserRole, inst_name)
                            self.macro_list.addItem(item)
                        return
                except Exception as e:
                    print("Failed to load sizes.json:", e)

        # Fallback
        if not cfg or 'macros' not in cfg: return
        for m in cfg['macros']:
            item = QListWidgetItem(m)
            self.macro_list.addItem(item)

    def parse_macro_sizes(self):
        try:
            if not self.project_config: return
            pdk_name = self.project_config.get('pdk', '')
            cfg = next((c for c in self.pdk_mgr.configs if c['name'] == pdk_name), None)
            if not cfg: return
            lib_path = cfg.get('lib', '')
            volare_base = lib_path.split("libs.ref")[0]
            search_path = os.path.join(volare_base, "libs.ref", "*", "lef", "*.lef")
            
            for lef in glob.glob(search_path):
                name = os.path.basename(lef).replace('.lef', '')
                if name in self.project_config.get('macros', []):
                    with open(lef, 'r') as f:
                        content = f.read()
                        m = re.search(r'SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)', content)
                        if m:
                            self.macro_sizes[name] = (float(m.group(1)), float(m.group(2)))
        except:
            pass

    def init_floorplan(self):
        w = self.sp_die_w.value(); h = self.sp_die_h.value()
        ml = self.sp_marg_l.value(); mr = self.sp_marg_r.value()
        mt = self.sp_marg_t.value(); mb = self.sp_marg_b.value()
        cw = w - ml - mr; ch = h - mt - mb
        
        if cw <= 0 or ch <= 0:
            QMessageBox.warning(self, "Invalid Dimensions", "Core area became negative. Adjust margins or die size.")
            return
            
        self.scene.clear()
        self.view.setBackgroundBrush(QBrush(QColor("#1E1E1E")))
        self.die_rect = QRectF(0, 0, w, h)
        die_item = self.scene.addRect(self.die_rect, QPen(QColor("#A0AEC0"), 2), QBrush(Qt.BrushStyle.NoBrush))
        die_item.setZValue(-10)
        self.core_rect = QRectF(ml, mb, cw, ch)  # y is mb because Y is up!
        core_item = self.scene.addRect(self.core_rect, QPen(QColor("#4A5568"), 1, Qt.PenStyle.DashLine), QBrush(Qt.BrushStyle.NoBrush))
        core_item.setZValue(-9)
        self.floorplan_initialized = True
        self.tabs.setEnabled(True)
        
        # Auto-discover and populate macros
        proj_root = self.parent().ide.get_proj_root(self.parent().ide.get_context()[0] or "design")
        base = self.parent().ide.get_context()[1]
        def_abs_path = os.path.join(proj_root, "results", "temp.def").replace("\\", "/")
        
        macros_spawned = set()
        
        # 1. Try to load from temp.def
        if os.path.exists(def_abs_path):
            parser = DEFParser(def_abs_path, self.parent().ide)
            for inst_name, rect in parser.comps_map.items():
                if rect.width() / parser.dbu > 50: # It's a macro
                    master_name = parser.comp_masters.get(inst_name, "")
                    w = rect.width() / parser.dbu
                    h = rect.height() / parser.dbu
                    m_item = MacroItem(master_name, w, h, self.core_rect, self)
                    m_item.set_inst_name(inst_name)
                    
                    x = rect.x() / parser.dbu
                    y = rect.y() / parser.dbu
                    
                    if x == 0 and y == 0:
                        x = self.core_rect.center().x()
                        y = self.core_rect.center().y()
                        
                    def clamp(cx, cy):
                        max_x = self.core_rect.width() - w
                        max_y = self.core_rect.height() - h
                        if cx < self.core_rect.x(): cx = self.core_rect.x()
                        if cy < self.core_rect.y(): cy = self.core_rect.y()
                        if cx > self.core_rect.x() + max_x: cx = self.core_rect.x() + max_x
                        if cy > self.core_rect.y() + max_y: cy = self.core_rect.y() + max_y
                        return cx, cy

                    x, y = clamp(x, y)
                    # Cascade if another macro is already at this exact position
                    while any(isinstance(i, MacroItem) and abs(i.pos().x() - x) < 1 and abs(i.pos().y() - y) < 1 for i in self.scene.items()):
                        x += 50
                        y += 50
                        x, y = clamp(x, y)
                        
                    m_item.setPos(x, y)
                    self.scene.addItem(m_item)
                    m_item.setPos(m_item.itemChange(QGraphicsItem.GraphicsItemChange.ItemPositionChange, m_item.pos()))
        
        self.view.fitInView(self.die_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def on_macro_dropped(self, name, x, y, inst_name=None):
        if not self.floorplan_initialized: return
        
        w, h = self.macro_sizes.get(name, (100.0, 100.0))
        m_item = MacroItem(name, w, h, self.core_rect, self)
        
        if inst_name:
            m_item.set_inst_name(inst_name)
        else:
            count = 0
            for item in self.scene.items():
                if isinstance(item, MacroItem) and item.name == name:
                    count += 1
            m_item.set_inst_name(f"{name}_inst_{count}")
            
        m_item.setPos(x, y)
        self.scene.addItem(m_item)
        m_item.setPos(m_item.itemChange(QGraphicsItem.GraphicsItemChange.ItemPositionChange, m_item.pos()))
        for i in range(self.macro_list.count()):
            it = self.macro_list.item(i)
            if it.text() == name or it.text() == f"{name} [PLACED]":
                it.setText(f"{name} [PLACED]")
                it.setForeground(QBrush(QColor("#4CAF50")))

    def on_inst_name_changed(self):
        items = self.scene.selectedItems()
        if items and isinstance(items[0], MacroItem):
            items[0].set_inst_name(self.txt_inst_name.text())
            self.scene.update()

    def on_spinbox_changed(self):
        items = self.scene.selectedItems()
        if items and isinstance(items[0], MacroItem):
            m = items[0]
            m.setPos(self.sp_sel_x.value(), self.sp_sel_y.value())

    def on_selection_changed(self):
        try:
            items = self.scene.selectedItems()
            if items and isinstance(items[0], MacroItem):
                m = items[0]
                self.lbl_sel_name.setText(m.name)
                self.sp_sel_x.blockSignals(True)
                self.sp_sel_y.blockSignals(True)
                self.txt_inst_name.blockSignals(True)
                self.sp_sel_x.setValue(m.pos().x())
                self.sp_sel_y.setValue(m.pos().y())
                self.txt_inst_name.setText(m.inst_name)
                self.sp_sel_x.blockSignals(False)
                self.sp_sel_y.blockSignals(False)
                self.txt_inst_name.blockSignals(False)
            else:
                self.lbl_sel_name.setText("None")
        except RuntimeError:
            pass # Handle C++ object destruction during widget close

    def generate_floorplan_tcl(self):
        if not self.floorplan_initialized: return
        die_w = self.die_rect.width(); die_h = self.die_rect.height()
        core_x1 = self.core_rect.x(); core_y1 = self.core_rect.y()
        core_x2 = core_x1 + self.core_rect.width(); core_y2 = core_y1 + self.core_rect.height()
        tcl = f"initialize_floorplan -die_area \"0 0 {die_w} {die_h}\" -core_area \"{core_x1} {core_y1} {core_x2} {core_y2}\" -site unithd\n"
        for item in self.scene.items():
            if isinstance(item, MacroItem):
                tcl += f"catch {{\n"
                tcl += f"    place_inst -name {{{item.inst_name}}} -origin {{{item.pos().x()} {item.pos().y()}}} -status FIRM -orientation R0\n"
                tcl += f"    add_macro_placement_blockage -halo {{10.0 10.0}}\n"
                tcl += f"    set_placement_padding -instances {{{item.inst_name}}} -left 10 -top 10 -right 10 -bottom 10\n"
                tcl += f"}}\n"
        
        proj_root = self.parent().ide.get_proj_root(self.parent().ide.get_context()[0] or "design")
        def_abs_path = os.path.join(proj_root, "results", "temp.def").replace("\\", "/")
        tcl += f"\nwrite_def \"{def_abs_path}\""
        
        self.parent().term_log.append("[SYS] Applying Custom Floorplan...")
        self.parent().send_command_internal(tcl)
        self.accept()
