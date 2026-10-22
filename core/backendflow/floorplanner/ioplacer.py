import os
import re
import math


def natural_sort_key(s):
    """Sort strings containing numbers in human/natural numerical order: a[0], a[1], ... a[10]"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def snap_to_grid(val, grid=0.005):
    """Snap coordinate to standard manufacturing grid (default Sky130 5nm / 0.005 um)."""
    return round(round(float(val) / grid) * grid, 3)
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QSpinBox,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QPlainTextEdit, QGroupBox, QFormLayout, QRadioButton,
    QButtonGroup, QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem, QGraphicsItem,
    QTabWidget, QAbstractItemView
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QItemSelectionModel
from PyQt6.QtGui import QColor, QPen, QBrush, QTransform, QFont

from backendflow.macro_exporter import run_macro_package_export

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def tune_floorplan_script_for_padring(fp_path, new_die_w, new_die_h, margin_x, margin_y):
    """
    Non-destructively patches an existing run_floorplan.tcl script to expand the die
    and center the core area, macros, regions, fences, and blockages.
    Preserves 100% of the user's custom edits, comments, flags, and manual code.
    Idempotent: will not shift coordinates twice if already tuned to the target dimensions.
    """
    if not os.path.isfile(fp_path):
        return False
    try:
        with open(fp_path, "r") as f:
            content = f.read()

        # Check if already tuned to this exact expanded die
        die_m = re.search(r'-die_area\s+"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)"', content)
        if die_m:
            cur_w = float(die_m.group(3))
            cur_h = float(die_m.group(4))
            if abs(cur_w - new_die_w) < 1.0 and abs(cur_h - new_die_h) < 1.0:
                return True

        # 1. Update initialize_floorplan
        def repl_fp(m):
            cmd = m.group(0)
            core_m = re.search(r'-core_area\s+"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)"', cmd)
            site_m = re.search(r'-site\s+(\S+)', cmd)
            site = site_m.group(1) if site_m else "unithd"
            if core_m:
                cx1, cy1, cx2, cy2 = map(float, core_m.groups())
                cw = cx2 - cx1
                ch = cy2 - cy1
                nx1 = margin_x
                ny1 = margin_y
                nx2 = margin_x + cw
                ny2 = margin_y + ch
            else:
                nx1, ny1, nx2, ny2 = margin_x, margin_y, new_die_w - margin_x, new_die_h - margin_y
            return f'initialize_floorplan -die_area "0 0 {new_die_w:.1f} {new_die_h:.1f}" -core_area "{nx1:.1f} {ny1:.1f} {nx2:.1f} {ny2:.1f}" -site {site}'

        content = re.sub(r'initialize_floorplan\s+[^\n]+', repl_fp, content)

        # 2. Shift place_macro coordinates by (+margin_x, +margin_y)
        def repl_macro(m):
            full = m.group(0)
            loc_m = re.search(r'-location\s+\{([0-9.]+)\s+([0-9.]+)\}', full)
            if loc_m:
                ox, oy = float(loc_m.group(1)), float(loc_m.group(2))
                nx, ny = ox + margin_x, oy + margin_y
                return full[:loc_m.start()] + f'-location {{{nx:.3f} {ny:.3f}}}' + full[loc_m.end():]
            return full

        content = re.sub(r'place_macro\s+[^\n]+', repl_macro, content)

        # 3. Shift create_region / create_fence boxes
        def repl_box(m):
            full = m.group(0)
            box_m = re.search(r'-box\s+\{([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\}', full)
            if box_m:
                x1, y1, x2, y2 = map(float, box_m.groups())
                nx1, ny1, nx2, ny2 = x1 + margin_x, y1 + margin_y, x2 + margin_x, y2 + margin_y
                return full[:box_m.start()] + f'-box {{{nx1:.3f} {ny1:.3f} {nx2:.3f} {ny2:.3f}}}' + full[box_m.end():]
            return full

        content = re.sub(r'(?:create_region|create_fence)\s+[^\n]+', repl_box, content)

        # 4. Shift create_blockage regions
        def repl_blockage(m):
            full = m.group(0)
            reg_m = re.search(r'-region\s+\{([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\}', full)
            if reg_m:
                x1, y1, x2, y2 = map(float, reg_m.groups())
                nx1, ny1, nx2, ny2 = x1 + margin_x, y1 + margin_y, x2 + margin_x, y2 + margin_y
                return full[:reg_m.start()] + f'-region {{{nx1:.3f} {ny1:.3f} {nx2:.3f} {ny2:.3f}}}' + full[reg_m.end():]
            return full

        content = re.sub(r'create_blockage\s+[^\n]+', repl_blockage, content)

        with open(fp_path, "w") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"[IOPlacer] Error tuning floorplan script: {e}")
        return False


class PinItem(QGraphicsRectItem):
    """
    Represents an I/O Port or I/O Pad placed along the die boundary.
    Supports magnetic snapping along perimeter edges.
    """
    def __init__(self, pin_name, direction, width, height, placer_dialog, parent=None):
        super().__init__(-width/2, -height/2, width, height, parent)
        self.pin_name = pin_name
        self.direction = direction  # input, output, inout, power, ground
        self.w = width
        self.h = height
        self.dialog = placer_dialog
        self.edge = "bottom"  # bottom, top, left, right
        self.layer = "met3"
        self.assigned_box = "All Edges"

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self._apply_color()

        self.text_item = QGraphicsTextItem(pin_name, self)
        font = self.text_item.font()
        font.setPointSize(7)
        font.setBold(True)
        self.text_item.setFont(font)
        self.text_item.setDefaultTextColor(QColor("#cdd6f4"))
        self.text_item.setTransform(QTransform.fromScale(1, -1))
        tbr = self.text_item.boundingRect()
        self.text_item.setPos(-tbr.width()/2, tbr.height()/2 + 4)

    def _apply_color(self):
        # Harmonized Catppuccin Mocha EDA palette
        if self.direction == "input":
            fill = QColor("#a6e3a1")  # Green
        elif self.direction == "output":
            fill = QColor("#89b4fa")  # Blue
        elif self.direction == "inout":
            fill = QColor("#cba6f7")  # Mauve
        elif self.direction in ["power", "ground"]:
            fill = QColor("#f9e2af")  # Yellow
        else:
            fill = QColor("#89dceb")  # Sky
        self.setBrush(QBrush(fill))
        self.setPen(QPen(QColor("#11111b"), 1))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            self.manually_dragged = True
            # Magnetic Snap to Die Edge
            die_rect = self.dialog.die_rect
            if die_rect.isValid() and die_rect.width() > 0:
                snapped_pos = self._snap_to_edge(new_pos, die_rect)
                return snapped_pos
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value:
                self.setPen(QPen(QColor("#00FFFF"), 2))
                if hasattr(self.dialog, "on_pin_selected_in_canvas") and not getattr(self.dialog, "_syncing_selection", False):
                    self.dialog.on_pin_selected_in_canvas(self.pin_name)
            else:
                self.setPen(QPen(QColor("#F0F6FC"), 1))
        return super().itemChange(change, value)

    def _snap_to_edge(self, pt, die_rect):
        x = pt.x()
        y = pt.y()
        x_min, x_max = min(die_rect.left(), die_rect.right()), max(die_rect.left(), die_rect.right())
        y_min, y_max = min(die_rect.top(), die_rect.bottom()), max(die_rect.top(), die_rect.bottom())

        dl = abs(x - x_min)
        dr = abs(x - x_max)
        db = abs(y - y_min)
        dt = abs(y - y_max)
        min_d = min(dl, dr, db, dt)

        grid = self.dialog.sp_spacing.value() if hasattr(self.dialog, 'sp_spacing') else 2.0
        if grid < 0.05:
            grid = 0.05

        if min_d == dl:
            self.edge = "left"
            y_snap = round(y / grid) * grid
            y_snap = max(y_min + self.h/2 + 2, min(y_max - self.h/2 - 2, y_snap))
            # Pad overlap avoidance
            if hasattr(self.dialog, "_legalize_edge_pos"):
                y_snap = self.dialog._legalize_edge_pos(self.pin_name, "left", y_snap, self.h)
            return QPointF(x_min, y_snap)
        elif min_d == dr:
            self.edge = "right"
            y_snap = round(y / grid) * grid
            y_snap = max(y_min + self.h/2 + 2, min(y_max - self.h/2 - 2, y_snap))
            if hasattr(self.dialog, "_legalize_edge_pos"):
                y_snap = self.dialog._legalize_edge_pos(self.pin_name, "right", y_snap, self.h)
            return QPointF(x_max, y_snap)
        elif min_d == dt:
            self.edge = "top"
            x_snap = round(x / grid) * grid
            x_snap = max(x_min + self.w/2 + 2, min(x_max - self.w/2 - 2, x_snap))
            if hasattr(self.dialog, "_legalize_edge_pos"):
                x_snap = self.dialog._legalize_edge_pos(self.pin_name, "top", x_snap, self.w)
            return QPointF(x_snap, y_max)
        else:
            self.edge = "bottom"
            x_snap = round(x / grid) * grid
            x_snap = max(x_min + self.w/2 + 2, min(x_max - self.w/2 - 2, x_snap))
            if hasattr(self.dialog, "_legalize_edge_pos"):
                x_snap = self.dialog._legalize_edge_pos(self.pin_name, "bottom", x_snap, self.w)
            return QPointF(x_snap, y_min)


class EdgeConstraintBox(QGraphicsRectItem):
    """
    Visual perimeter edge constraint region where a group of pins is constrained.
    """
    def __init__(self, name, edge, start_um, end_um, die_rect, parent=None):
        super().__init__(parent)
        self.box_name = name
        self.edge = edge  # top, bottom, left, right
        self.start_um = start_um
        self.end_um = end_um
        self.die_rect = die_rect

        self.setZValue(-5)
        self.setBrush(QBrush(QColor(137, 180, 250, 50)))  # Catppuccin Blue subtle fill
        self.setPen(QPen(QColor("#89b4fa"), 1.5, Qt.PenStyle.DashLine))

        self.label_item = QGraphicsTextItem(name, self)
        font = self.label_item.font()
        font.setPointSize(8)
        font.setBold(True)
        self.label_item.setFont(font)
        self.label_item.setDefaultTextColor(QColor("#89b4fa"))
        self.label_item.setTransform(QTransform.fromScale(1, -1))

        self.update_geometry(die_rect)

    def update_geometry(self, die_rect):
        self.die_rect = die_rect
        x_min, x_max = min(die_rect.left(), die_rect.right()), max(die_rect.left(), die_rect.right())
        y_min, y_max = min(die_rect.top(), die_rect.bottom()), max(die_rect.top(), die_rect.bottom())
        depth = 30.0  # Constraint strip depth in um
        if self.edge == "bottom":
            x1 = self.start_um
            w = max(10.0, self.end_um - self.start_um)
            self.setRect(x1, y_min - depth, w, depth)
            self.label_item.setPos(x1 + 4, y_min - 4)
        elif self.edge == "top":
            x1 = self.start_um
            w = max(10.0, self.end_um - self.start_um)
            self.setRect(x1, y_max, w, depth)
            self.label_item.setPos(x1 + 4, y_max + depth - 4)
        elif self.edge == "left":
            y1 = self.start_um
            h = max(10.0, self.end_um - self.start_um)
            self.setRect(x_min - depth, y1, depth, h)
            self.label_item.setPos(x_min - depth + 4, y1 + h - 4)
        elif self.edge == "right":
            y1 = self.start_um
            h = max(10.0, self.end_um - self.start_um)
            self.setRect(x_max, y1, depth, h)
            self.label_item.setPos(x_max + 4, y1 + h - 4)


class PinTableWidget(QTableWidget):
    """
    Table widget supporting reliable multi-selection:
    - Shift-click: selects contiguous range between clicked rows (standard spreadsheet/table expectation)
    - Ctrl-click: toggles individual row selection without affecting others
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_clicked_row = 0

    def mousePressEvent(self, event):
        idx = self.indexAt(event.pos())
        if idx.isValid() and event.button() == Qt.MouseButton.LeftButton:
            row = idx.row()
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
                # Both Shift and Ctrl toggle individual rows, not a range
                is_selected = row in [i.row() for i in self.selectionModel().selectedRows()]
                flag = QItemSelectionModel.SelectionFlag.Deselect if is_selected else QItemSelectionModel.SelectionFlag.Select
                self.selectionModel().select(self.model().index(row, 0), flag | QItemSelectionModel.SelectionFlag.Rows)
                self.last_clicked_row = row
                return
            else:
                self.last_clicked_row = row
        super().mousePressEvent(event)


class IOPlacerCanvasView(QGraphicsView):
    def __init__(self, placer_dialog, parent=None):
        super().__init__(parent)
        self.dialog = placer_dialog
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setBackgroundBrush(QBrush(QColor("#000000")))
        self.scale(1, -1)  # EDA coordinates (Y upwards)
        self.drawing_box_mode = False
        self.box_drag_start = None
        self.preview_rect_item = None
        self.pan_active = False
        self.pan_start_pos = None

    def wheelEvent(self, event):
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self.pan_active = True
            self.pan_start_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if self.drawing_box_mode and event.button() == Qt.MouseButton.LeftButton:
            scene_pt = self.mapToScene(event.pos())
            self.box_drag_start = scene_pt
            if not self.preview_rect_item:
                self.preview_rect_item = QGraphicsRectItem()
                pen = QPen(QColor("#00FFFF"), 2, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                self.preview_rect_item.setPen(pen)
                self.preview_rect_item.setBrush(QBrush(QColor(0, 255, 255, 40)))
                self.preview_rect_item.setZValue(150)
                self.scene().addItem(self.preview_rect_item)
            self.preview_rect_item.setRect(QRectF(scene_pt.x(), scene_pt.y(), 0, 0))
            self.preview_rect_item.setVisible(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.pan_active and self.pan_start_pos:
            delta = event.pos() - self.pan_start_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self.pan_start_pos = event.pos()
            event.accept()
            return

        if self.drawing_box_mode and self.box_drag_start and self.preview_rect_item:
            scene_pt = self.mapToScene(event.pos())
            rx = min(self.box_drag_start.x(), scene_pt.x())
            ry = min(self.box_drag_start.y(), scene_pt.y())
            rw = abs(self.box_drag_start.x() - scene_pt.x())
            rh = abs(self.box_drag_start.y() - scene_pt.y())
            self.preview_rect_item.setRect(QRectF(rx, ry, rw, rh))
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self.pan_active = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if self.drawing_box_mode and event.button() == Qt.MouseButton.LeftButton and self.box_drag_start:
            scene_pt = self.mapToScene(event.pos())
            if self.preview_rect_item:
                self.scene().removeItem(self.preview_rect_item)
                self.preview_rect_item = None
            self.dialog.create_edge_constraint_from_drag(self.box_drag_start, scene_pt)
            self.box_drag_start = None
            self.drawing_box_mode = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if hasattr(self.dialog, "update_live_tcl"):
            self.dialog.update_live_tcl()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            if self.drawing_box_mode:
                self.drawing_box_mode = False
                if self.preview_rect_item:
                    self.scene().removeItem(self.preview_rect_item)
                    self.preview_rect_item = None
                self.box_drag_start = None
                self.setCursor(Qt.CursorShape.ArrowCursor)
                event.accept()
                return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected_items = self.scene().selectedItems()
            if selected_items:
                for item in selected_items:
                    if isinstance(item, EdgeConstraintBox):
                        self.dialog.remove_box_by_item(item)
                    elif isinstance(item, PinItem):
                        self.dialog.unplace_pin_item(item)
                event.accept()
                return
        super().keyPressEvent(event)


class IOPlacerDialog(QDialog):
    """
    Standalone I/O Placer Dialog matching the InteractiveFloorplannerWidget UI design.
    Features:
      - Dual Mode: I/O Ports (Macro Export) vs I/O Pads (Full-Chip Tapeout)
      - Die boundary visualization
      - Edge constraint region drawing (Perimeter boxes: Top, Bottom, Left, Right)
      - Interactive Pin Table with edge box binding, direction, layer, coordinates
      - Drag-and-drop magnetic edge snapping
      - Pitch & spacing controls
      - Live OpenROAD TCL generator
      - Export as Hard Macro Package button
    """
    def __init__(self, project_config=None, pdk_mgr=None, parent=None):
        super().__init__(parent)
        self.project_config = project_config or {}
        self.pdk_mgr = pdk_mgr
        self.parent_flow = parent

        self.setWindowTitle("Silis I/O Placer Studio")
        self.resize(1300, 820)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)

        self.die_rect = QRectF(0, 0, 1500, 1500)
        self.core_rect = QRectF(10, 10, 1480, 1480)
        self.original_die_rect = QRectF(0, 0, 1500, 1500)
        self.original_core_rect = QRectF(10, 10, 1480, 1480)
        self.floorplan_entities = {
            "macros": [],
            "fences": [],
            "regions": [],
            "blockages": []
        }
        self.pad_ring_enabled = False
        self.pad_strategy = "single"
        self.pins_data = {}  # {name: {"dir": "input", "edge": "bottom", "x": 0.0, "y": 0.0, "box": "All"}}
        self.pin_items = {}  # {name: PinItem}
        self.constraint_boxes = {}  # {name: EdgeConstraintBox}
        self.box_counter = 1

        self._cached_selected_pins = []
        self._user_set_edges = set()   # pins whose edge was explicitly set by the user

        self._init_ui()
        self._load_design_context()
        self.update_live_tcl()

    def _apply_dark_stylesheet(self):
        pass

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # -------------------------------------------------------------
        # 1. Left Column: Mode, Edge Constraints & Action Controls
        # -------------------------------------------------------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Dual Mode Selector
        gb_mode = QGroupBox("Design Target Mode")
        fl_mode = QVBoxLayout(gb_mode)
        self.rb_macro = QRadioButton("I/O Ports (Macro Export)")
        self.rb_macro.setChecked(True)
        self.rb_chip = QRadioButton("I/O Pads (Full-Chip Tapeout)")
        fl_mode.addWidget(self.rb_macro)
        fl_mode.addWidget(self.rb_chip)

        # Pad Packaging Method Selector (Visible when I/O Pads is active)
        self.gb_pad_method = QGroupBox("Pad Ring Strategy")
        fl_pad_method = QVBoxLayout(self.gb_pad_method)
        self.rb_pad_single = QRadioButton("Single-Row (Die Expansion)")
        self.rb_pad_single.setChecked(True)
        self.rb_pad_single.setToolTip("Expands die area symmetrically to fit all pads in a standard single wirebond ring.")
        self.rb_pad_staggered = QRadioButton("Dual-Row Staggered (2x Density)")
        self.rb_pad_staggered.setToolTip("Places pads in outer and inner alternating tiers to double perimeter capacity with less die expansion.")
        fl_pad_method.addWidget(self.rb_pad_single)
        fl_pad_method.addWidget(self.rb_pad_staggered)
        self.rb_pad_single.toggled.connect(self.on_pad_strategy_changed)
        self.gb_pad_method.setVisible(False)
        fl_mode.addWidget(self.gb_pad_method)

        self.rb_macro.toggled.connect(self.on_mode_toggled)
        left_layout.addWidget(gb_mode)

        # Pitch & Layer Controls
        gb_routing = QGroupBox("Routing & Spacing")
        fl_routing = QFormLayout(gb_routing)
        self.cmb_hor_layer = QComboBox()
        self.cmb_hor_layer.addItems(["met3", "met1", "met5"])
        self.cmb_ver_layer = QComboBox()
        self.cmb_ver_layer.addItems(["met2", "met4"])
        self.sp_spacing = QDoubleSpinBox()
        self.sp_spacing.setRange(0.2, 50.0)
        self.sp_spacing.setValue(1.0)
        self.sp_spacing.setSingleStep(0.5)
        self.sp_spacing.valueChanged.connect(self.on_spacing_changed)

        fl_routing.addRow("Horizontal Layer:", self.cmb_hor_layer)
        fl_routing.addRow("Vertical Layer:", self.cmb_ver_layer)
        fl_routing.addRow("Min Pitch (µm):", self.sp_spacing)
        left_layout.addWidget(gb_routing)

        # Edge Constraint Region Drawing
        gb_boxes = QGroupBox("Perimeter Constraint Boxes")
        fl_boxes = QVBoxLayout(gb_boxes)
        btn_draw_box = QPushButton("Draw Edge Constraint Box")
        btn_draw_box.clicked.connect(self.start_draw_box_mode)
        fl_boxes.addWidget(btn_draw_box)

        self.cmb_active_boxes = QComboBox()
        self.cmb_active_boxes.addItem("All Edges")
        fl_boxes.addWidget(QLabel("Active Boxes:"))
        fl_boxes.addWidget(self.cmb_active_boxes)

        btn_del_box = QPushButton("Remove Selected Box")
        btn_del_box.clicked.connect(self.remove_selected_box)
        fl_boxes.addWidget(btn_del_box)
        left_layout.addWidget(gb_boxes)

        # Action Buttons
        btn_autoplace = QPushButton("Auto-Distribute All Pins")
        btn_autoplace.clicked.connect(self.auto_distribute_pins)
        left_layout.addWidget(btn_autoplace)

        btn_fit = QPushButton("Fit View")
        btn_fit.clicked.connect(self.fit_view)
        left_layout.addWidget(btn_fit)

        left_layout.addStretch()

        btn_apply = QPushButton("Apply Pin Placement & Run")
        btn_apply.clicked.connect(self.apply_and_run)
        left_layout.addWidget(btn_apply)

        splitter.addWidget(left_widget)

        # -------------------------------------------------------------
        # 2. Middle Column: EDA Canvas View
        # -------------------------------------------------------------
        mid_widget = QWidget()
        mid_layout = QVBoxLayout(mid_widget)
        self.canvas_view = IOPlacerCanvasView(self)
        self.scene = QGraphicsScene()
        self.canvas_view.setScene(self.scene)
        self.scene.selectionChanged.connect(self.on_canvas_selection_changed)
        mid_layout.addWidget(self.canvas_view)
        splitter.addWidget(mid_widget)

        # -------------------------------------------------------------
        # 3. Right Column: Pin Table & Live TCL Script Preview
        # -------------------------------------------------------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self.right_tabs = QTabWidget()

        # Tab 1: Pin Table
        tab_pins = QWidget()
        tab_pins_lay = QVBoxLayout(tab_pins)
        self.table_pins = PinTableWidget()
        self.table_pins.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_pins.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_pins.setColumnCount(6)
        self.table_pins.setHorizontalHeaderLabels(["Pin Name", "Direction", "Edge", "Tier / Ring", "Box Region", "Coord (µm)"])
        self.table_pins.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_pins.itemSelectionChanged.connect(self.on_table_selection_changed)
        tab_pins_lay.addWidget(self.table_pins)
        self.right_tabs.addTab(tab_pins, "Pins")

        # Tab 2: Live TCL
        tab_tcl = QWidget()
        tab_tcl_lay = QVBoxLayout(tab_tcl)
        self.txt_live_tcl = QPlainTextEdit()
        self.txt_live_tcl.setReadOnly(True)
        tab_tcl_lay.addWidget(self.txt_live_tcl)
        self.right_tabs.addTab(tab_tcl, "Live OpenROAD TCL")

        right_layout.addWidget(self.right_tabs)
        splitter.addWidget(right_widget)

        splitter.setSizes([260, 640, 400])

    def _get_project_root(self):
        """
        Robustly resolves active project root directory from IDE context, project config, or directory hierarchy.
        """
        # 1. Direct keys in project_config
        if isinstance(self.project_config, dict):
            for k in ("project_root", "project_dir", "cwd"):
                p = self.project_config.get(k)
                if p and os.path.isdir(p):
                    return os.path.abspath(p)
            for file_list_key in ("rtl_files", "sdc_files", "tb_files"):
                flist = self.project_config.get(file_list_key, [])
                if flist and isinstance(flist, list) and flist[0]:
                    cand = os.path.dirname(os.path.abspath(flist[0]))
                    if os.path.basename(cand) in ["source", "netlist", "results", "reports", "build"]:
                        cand = os.path.dirname(cand)
                    if os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "silis.silisproj")):
                        return cand
                    elif os.path.isdir(cand):
                        return cand

        # 2. From parent_flow.ide
        if self.parent_flow and hasattr(self.parent_flow, "ide") and self.parent_flow.ide:
            ide = self.parent_flow.ide
            if hasattr(ide, "get_proj_root"):
                try:
                    ctx = ide.get_context()[0] if hasattr(ide, "get_context") else "design"
                    cand = ide.get_proj_root(ctx or "design")
                    if cand and os.path.isdir(cand):
                        return os.path.abspath(cand)
                except Exception:
                    pass
            for attr in ("project_path", "cwd"):
                p = getattr(ide, attr, None)
                if p and os.path.isdir(p):
                    return os.path.abspath(p)

        # 3. From parent_flow directly
        if self.parent_flow:
            for attr in ("cwd", "project_path", "results_dir"):
                p = getattr(self.parent_flow, attr, None)
                if p:
                    cand = os.path.dirname(p) if attr == "results_dir" else p
                    if os.path.isdir(cand):
                        return os.path.abspath(cand)

        # 4. Search upward from current working directory
        cwd = os.path.abspath(os.getcwd())
        curr = cwd
        while curr and curr != '/' and curr != os.path.dirname(curr):
            try:
                if any(f.endswith('.silisproj') or f.endswith('.silis') for f in os.listdir(curr)):
                    return curr
            except Exception:
                pass
            curr = os.path.dirname(curr)

        # 5. Look for known project directory under silis/projects/ matching project_name
        if isinstance(self.project_config, dict):
            pname = self.project_config.get("project_name", "")
            if pname:
                for base in [cwd, os.path.join(cwd, "silis", "projects"), os.path.join(cwd, "projects")]:
                    cand = os.path.join(base, pname) if not base.endswith(pname) else base
                    if os.path.isdir(cand):
                        return os.path.abspath(cand)

        return cwd

    def _parse_verilog_netlist_pins(self, proj_root):
        """
        Extracts pin names and directions from synthesized Verilog netlist if DEF pins are unpopulated.
        """
        pins = {}
        candidates = []
        top = self.project_config.get("top_module", "") if isinstance(self.project_config, dict) else ""
        if top:
            candidates.append(os.path.join(proj_root, "netlist", f"{top}_netlist.v"))
            candidates.append(os.path.join(proj_root, "netlist", f"{top}_scan.v"))
        candidates.append(os.path.join(proj_root, "results", "synth.v"))
        netlist_dir = os.path.join(proj_root, "netlist")
        if os.path.isdir(netlist_dir):
            for f in sorted(os.listdir(netlist_dir)):
                if f.endswith(".v"):
                    candidates.append(os.path.join(netlist_dir, f))

        netlist_path = next((p for p in candidates if os.path.isfile(p)), None)
        if not netlist_path:
            return pins

        try:
            with open(netlist_path, "r") as f:
                content = f.read()

            target_block = content
            if top:
                # Support both ANSI module headers: module top (...); body endmodule
                # and non-ANSI declarations. We search up to endmodule.
                m_top = re.search(rf"module\s+{top}\b(?:\s*#\s*\(.*?\))?\s*\((.*?)\);(.*?)(?:endmodule)", content, re.DOTALL)
                if m_top:
                    header_ports = m_top.group(1)
                    body_content = m_top.group(2)
                    target_block = header_ports + "\n" + body_content

            # Match: input/output/inout [wire/reg] [signed] [msb:lsb] name1, name2 ...; or in header
            for m in re.finditer(r"(?:^|[;,(\s])\s*(input|output|inout)\s+(?:wire\s+|reg\s+)?(?:signed\s+)?(?:\[(\d+):(\d+)\]\s+)?([^;,)]+)", target_block, re.MULTILINE):
                direction = m.group(1).lower()
                msb = m.group(2)
                lsb = m.group(3)
                names_str = m.group(4)
                names = [n.strip() for n in names_str.split(",") if n.strip()]

                for name in names:
                    # Clean any trailing comments or stray characters
                    name = re.sub(r'//.*$', '', name).strip()
                    if not name or name.startswith("//"):
                        continue
                    if msb is not None and lsb is not None:
                        high, low = int(msb), int(lsb)
                        step = 1 if high >= low else -1
                        for idx in range(low, high + step, step):
                            pin_name = f"{name}[{idx}]"
                            pins[pin_name] = {"dir": direction, "edge": "bottom", "x": 0.0, "y": 0.0, "box": "All Edges"}
                    else:
                        pins[name] = {"dir": direction, "edge": "bottom", "x": 0.0, "y": 0.0, "box": "All Edges"}
        except Exception as e:
            print(f"[IOPlacer] Note parsing verilog netlist: {e}")

        return pins

    def _load_design_context(self):
        """
        Loads die dimensions, floorplan entities and I/O pins from netlist / temp.def / project config.
        """
        proj_root = self._get_project_root()

        fp_script = os.path.join(proj_root, "run_floorplan.tcl") if proj_root else ""
        if os.path.isfile(fp_script):
            self._parse_floorplan_script(fp_script)

        def_path = os.path.join(proj_root, "results", "temp.def").replace("\\", "/") if proj_root else ""
        if os.path.isfile(def_path):
            self._parse_def_pins_and_die(def_path)

        # Fallback to Verilog netlist if DEF had no pins
        if not self.pins_data and proj_root:
            v_pins = self._parse_verilog_netlist_pins(proj_root)
            if v_pins:
                self.pins_data = v_pins

        # Only use mock pins if there is zero project context
        if not self.pins_data:
            w, h = 1500.0, 1500.0
            self.die_rect = QRectF(0, 0, w, h)
            self.core_rect = QRectF(10.0, 10.0, w - 20.0, h - 20.0)
            self.original_die_rect = QRectF(self.die_rect)
            self.original_core_rect = QRectF(self.core_rect)
            self._populate_mock_pins()

        self._draw_die_boundary()
        self.auto_distribute_pins()

    def _parse_floorplan_script(self, fp_script):
        try:
            with open(fp_script, "r") as f:
                content = f.read()

            self.floorplan_entities = {
                "macros": [],
                "fences": [],
                "regions": [],
                "blockages": []
            }

            # Parse macros
            macro_cmds = re.findall(
                r'place_macro\s+-inst\s+"([^"]+)"\s+-cell\s+"([^"]+)"\s+-location\s+\{([\d\.\-]+)\s+([\d\.\-]+)\}(.*)',
                content
            )
            for inst, cell, mx, my, extra in macro_cmds:
                mw, mh = (479.78, 397.5) if "sram" in cell.lower() else (200.0, 200.0)
                self.floorplan_entities["macros"].append({
                    "inst": inst,
                    "cell": cell,
                    "x": float(mx),
                    "y": float(my),
                    "w": mw,
                    "h": mh,
                    "extra": extra
                })

            # Parse fences
            fence_cmds = re.findall(
                r'create_fence\s+-module\s+"([^"]+)"\s+-box\s+\{([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\}(.*)',
                content
            )
            for mod, x1, y1, x2, y2, extra in fence_cmds:
                self.floorplan_entities["fences"].append({
                    "module": mod,
                    "box": (float(x1), float(y1), float(x2), float(y2)),
                    "extra": extra
                })

            # Parse regions
            region_cmds = re.findall(
                r'create_region\s+-module\s+"([^"]+)"\s+-box\s+\{([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\}(.*)',
                content
            )
            for mod, x1, y1, x2, y2, extra in region_cmds:
                self.floorplan_entities["regions"].append({
                    "module": mod,
                    "box": (float(x1), float(y1), float(x2), float(y2)),
                    "extra": extra
                })

            # Parse blockages
            blockage_cmds = re.findall(
                r'(catch\s*\{\s*)?create_blockage\s+-region\s+\{([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\s+([\d\.\-]+)\}(.*)',
                content
            )
            for catch_prefix, x1, y1, x2, y2, extra in blockage_cmds:
                self.floorplan_entities["blockages"].append({
                    "coords": (float(x1), float(y1), float(x2), float(y2)),
                    "catch": bool(catch_prefix),
                    "extra": extra
                })
        except Exception as e:
            print(f"[IOPlacer] Note parsing floorplan script: {e}")

    def _parse_def_pins_and_die(self, def_path):
        dbu = 1000.0
        die_w, die_h = 1500.0, 1500.0
        pins = {}

        try:
            with open(def_path, "r") as f:
                content = f.read()

            # Parse UNITS
            m_dbu = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)", content)
            if m_dbu:
                dbu = float(m_dbu.group(1))

            # Parse DIEAREA
            m_die = re.search(r"DIEAREA\s*\(\s*(\d+)\s+(\d+)\s*\)\s*\(\s*(\d+)\s+(\d+)\s*\)", content)
            if m_die:
                x1, y1, x2, y2 = map(float, m_die.groups())
                die_w = (x2 - x1) / dbu
                die_h = (y2 - y1) / dbu

            self.die_rect = QRectF(0, 0, die_w, die_h)
            self.site_name = "unithd"

            # Parse core bounding box and site from stdcell rows
            row_matches = re.findall(r"ROW\s+\S+\s+(\S+)\s+(\d+)\s+(\d+)\s+\S+\s+DO\s+(\d+)\s+BY\s+\d+\s+STEP\s+(\d+)", content)
            stdcell_matches = [r for r in row_matches if r[0] not in ("IO_SITE", "IO_CSITE")]
            if stdcell_matches:
                self.site_name = stdcell_matches[0][0]
                min_rx = min(float(r[1]) / dbu for r in stdcell_matches)
                min_ry = min(float(r[2]) / dbu for r in stdcell_matches)
                max_rx = max((float(r[1]) + float(r[3]) * float(r[4])) / dbu for r in stdcell_matches)
                max_ry = max(float(r[2]) for r in stdcell_matches) / dbu
                self.core_rect = QRectF(min_rx, min_ry, max_rx - min_rx, max_ry - min_ry)
            else:
                self.core_rect = QRectF(10.0, 10.0, max(10.0, die_w - 20.0), max(10.0, die_h - 20.0))

            self.original_die_rect = QRectF(self.die_rect)
            self.original_core_rect = QRectF(self.core_rect)

            # Parse PINS block
            m_pins_block = re.search(r"PINS\s+(\d+)\s*;(.*?)END\s+PINS", content, re.DOTALL)
            if m_pins_block:
                pin_entries = m_pins_block.group(2).strip().split(";")
                for p_str in pin_entries:
                    p_str = p_str.strip()
                    if not p_str:
                        continue
                    m_name = re.search(r"-\s*(\S+)", p_str)
                    if not m_name:
                        continue
                    pname = m_name.group(1)
                    m_dir = re.search(r"\+\s*DIRECTION\s+(\S+)", p_str)
                    pdir = m_dir.group(1).lower() if m_dir else "input"

                    # Parse existing coordinates if placed
                    m_loc = re.search(r"\+\s*(?:PLACED|FIXED)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", p_str)
                    px = float(m_loc.group(1)) / dbu if m_loc else 0.0
                    py = float(m_loc.group(2)) / dbu if m_loc else 0.0

                    # Validate coordinates against die boundaries
                    is_valid_coord = bool(m_loc and (0 <= px <= die_w and 0 <= py <= die_h))
                    edge = "bottom"
                    if is_valid_coord and (die_w > 0 and die_h > 0):
                        dl = abs(px)
                        dr = abs(px - die_w)
                        db = abs(py)
                        dt = abs(py - die_h)
                        min_d = min(dl, dr, db, dt)
                        if min_d == dl:
                            edge = "left"
                        elif min_d == dr:
                            edge = "right"
                        elif min_d == dt:
                            edge = "top"
                        else:
                            edge = "bottom"
                    else:
                        # Reset invalid or unplaced coordinates so auto-distribution places them on perimeter
                        px = 0.0
                        py = 0.0

                    pins[pname] = {
                        "dir": pdir,
                        "edge": edge,
                        "x": px,
                        "y": py,
                        "box": "All Edges"
                    }

        except Exception as e:
            print(f"[IOPlacer] Error parsing DEF: {e}")

        if pins:
            self.pins_data = pins

    def _populate_mock_pins(self):
        # 16-pin mock interface for standalone testing
        mock_inputs = ["clk", "rst_n", "we", "re", "din[0]", "din[1]", "din[2]", "din[3]"]
        mock_outputs = ["dout[0]", "dout[1]", "dout[2]", "dout[3]", "valid", "ready"]
        mock_pwr = ["VDD", "VSS"]
        self.pins_data = {}
        for p in mock_inputs:
            self.pins_data[p] = {"dir": "input", "edge": "bottom", "x": 0.0, "y": 0.0, "box": "All Edges"}
        for p in mock_outputs:
            self.pins_data[p] = {"dir": "output", "edge": "top", "x": 0.0, "y": 0.0, "box": "All Edges"}
        for p in mock_pwr:
            self.pins_data[p] = {"dir": "power" if p == "VDD" else "ground", "edge": "left", "x": 0.0, "y": 0.0, "box": "All Edges"}

    def _draw_die_boundary(self):
        self.scene.clear()
        self.pin_items.clear()
        self.constraint_boxes.clear()

        # Background Die Outline
        die_pen = QPen(QColor("#89b4fa"), 2)
        die_brush = QBrush(QColor("#11111b"))
        self.die_item = self.scene.addRect(self.die_rect, die_pen, die_brush)
        self.die_item.setZValue(-30)

        # Labels for edges
        w, h = self.die_rect.width(), self.die_rect.height()
        self._add_edge_label("BOTTOM", w / 2, -25)
        self._add_edge_label("TOP", w / 2, h + 15)
        self._add_edge_label("LEFT", -50, h / 2)
        self._add_edge_label("RIGHT", w + 20, h / 2)

        is_pad_mode = getattr(self, "pad_ring_enabled", False) or (hasattr(self, "rb_chip") and self.rb_chip.isChecked())
        if is_pad_mode:
            shift_x = getattr(self, "pad_ring_margin_x", getattr(self, "pad_ring_margin", 250.0))
            shift_y = getattr(self, "pad_ring_margin_y", getattr(self, "pad_ring_margin", 250.0))

            # Draw Pad Ring corridor guidelines
            ring_pen = QPen(QColor("#45475a"), 1, Qt.PenStyle.DashLine)
            r_out = self.die_rect.adjusted(200, 200, -200, -200)
            if r_out.isValid() and r_out.width() > 0 and r_out.height() > 0:
                self.scene.addRect(r_out, ring_pen)
            if getattr(self, "pad_strategy", "single") == "staggered":
                r_in = self.die_rect.adjusted(420, 420, -420, -420)
                if r_in.isValid() and r_in.width() > 0 and r_in.height() > 0:
                    self.scene.addRect(r_in, ring_pen)

            # Draw Centered Core Area box
            core_pen = QPen(QColor("#a6e3a1"), 2, Qt.PenStyle.DashLine)
            core_brush = QBrush(QColor(24, 24, 37, 180))
            core_item = self.scene.addRect(self.core_rect, core_pen, core_brush)
            core_item.setZValue(-20)

            lbl = self.scene.addText(f"CENTERED CORE DESIGN ({self.core_rect.width():.0f} × {self.core_rect.height():.0f} µm)")
            lbl.setDefaultTextColor(QColor("#a6e3a1"))
            f = lbl.font()
            f.setPointSize(8)
            f.setBold(True)
            lbl.setFont(f)
            lbl.setTransform(QTransform.fromScale(1, -1))
            lbl.setPos(self.core_rect.left() + 15, self.core_rect.top() + 25)
        else:
            shift_x = 0.0
            shift_y = 0.0

        # Draw Blockages
        for blk in self.floorplan_entities.get("blockages", []):
            bx1, by1, bx2, by2 = blk["coords"]
            b_rect = QRectF(bx1 + shift_x, by1 + shift_y, max(1.0, bx2 - bx1), max(1.0, by2 - by1))
            blk_pen = QPen(QColor("#6c7086"), 1, Qt.PenStyle.DotLine)
            blk_brush = QBrush(QColor(108, 112, 134, 40))
            b_item = self.scene.addRect(b_rect, blk_pen, blk_brush)
            b_item.setZValue(-15)

        # Draw Fences & Regions
        for fr in self.floorplan_entities.get("fences", []) + self.floorplan_entities.get("regions", []):
            fx1, fy1, fx2, fy2 = fr["box"]
            fr_rect = QRectF(fx1 + shift_x, fy1 + shift_y, max(1.0, fx2 - fx1), max(1.0, fy2 - fy1))
            fr_pen = QPen(QColor("#cba6f7"), 1.5, Qt.PenStyle.DashLine)
            fr_brush = QBrush(QColor(203, 166, 247, 30))
            fr_item = self.scene.addRect(fr_rect, fr_pen, fr_brush)
            fr_item.setZValue(-14)
            flbl = self.scene.addText(fr.get("module", ""))
            flbl.setDefaultTextColor(QColor("#cba6f7"))
            ff = flbl.font()
            ff.setPointSize(7)
            flbl.setFont(ff)
            flbl.setTransform(QTransform.fromScale(1, -1))
            flbl.setPos(fr_rect.left() + 5, fr_rect.top() + 18)

        # Draw Hard Macros
        for m in self.floorplan_entities.get("macros", []):
            mx = m["x"] + shift_x
            my = m["y"] + shift_y
            mw = m.get("w", 250.0)
            mh = m.get("h", 200.0)
            m_rect = QRectF(mx, my, mw, mh)
            m_pen = QPen(QColor("#fab387"), 2)
            m_brush = QBrush(QColor(49, 50, 68, 220))
            m_item = self.scene.addRect(m_rect, m_pen, m_brush)
            m_item.setZValue(-12)
            mlbl = self.scene.addText(m["inst"])
            mlbl.setDefaultTextColor(QColor("#fab387"))
            mf = mlbl.font()
            mf.setPointSize(8)
            mf.setBold(True)
            mlbl.setFont(mf)
            mlbl.setTransform(QTransform.fromScale(1, -1))
            mlbl.setPos(mx + 8, my + 24)

        # Labels for edges
        w, h = self.die_rect.width(), self.die_rect.height()
        self._add_edge_label("BOTTOM", w / 2, -25)
        self._add_edge_label("TOP", w / 2, h + 15)
        self._add_edge_label("LEFT", -50, h / 2)
        self._add_edge_label("RIGHT", w + 20, h / 2)

    def _add_edge_label(self, text, x, y):
        lbl = self.scene.addText(text)
        lbl.setDefaultTextColor(QColor("#a6adc8"))
        f = lbl.font()
        f.setPointSize(8)
        lbl.setFont(f)
        lbl.setTransform(QTransform.fromScale(1, -1))
        lbl.setPos(x, y)

    def _populate_table(self):
        self.table_pins.blockSignals(True)
        self.table_pins.setRowCount(0)
        self.table_pins.setRowCount(len(self.pins_data))

        box_options = ["All Edges"] + list(self.constraint_boxes.keys())
        edge_options = ["bottom", "top", "left", "right"]

        tier_options = ["Outer (Ring 1)", "Inner (Ring 2)"]
        row = 0
        for name, data in sorted(self.pins_data.items()):
            item_name = QTableWidgetItem(name)
            item_name.setFlags(item_name.flags() & ~Qt.ItemFlag.ItemIsEditable)

            item_dir = QTableWidgetItem(data["dir"])
            item_dir.setFlags(item_dir.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Edge Dropdown
            cmb_edge = QComboBox()
            cmb_edge.addItems(edge_options)
            cur_edge = data.get("edge", "bottom")
            if cur_edge in edge_options:
                cmb_edge.setCurrentText(cur_edge)
            cmb_edge.currentTextChanged.connect(lambda edge_val, pname=name: self._on_pin_edge_dropdown_changed(pname, edge_val))

            # Tier / Ring Dropdown (Outer vs Inner)
            cmb_tier = QComboBox()
            cmb_tier.addItems(tier_options)
            cur_tier = data.get("tier", "Outer (Ring 1)")
            cmb_tier.setCurrentText(cur_tier)
            cmb_tier.currentTextChanged.connect(lambda tier_val, pname=name: self._on_pin_tier_dropdown_changed(pname, tier_val))

            # Box Region Dropdown
            cmb_box = QComboBox()
            cmb_box.addItems(box_options)
            cur_box = data.get("box", "All Edges")
            if cur_box in box_options:
                cmb_box.setCurrentText(cur_box)
            cmb_box.currentTextChanged.connect(lambda box_val, pname=name: self._on_pin_box_dropdown_changed(pname, box_val))

            item_coord = QTableWidgetItem(f"({data['x']:.1f}, {data['y']:.1f})")
            item_coord.setFlags(item_coord.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table_pins.setItem(row, 0, item_name)
            self.table_pins.setItem(row, 1, item_dir)
            self.table_pins.setCellWidget(row, 2, cmb_edge)
            self.table_pins.setCellWidget(row, 3, cmb_tier)
            self.table_pins.setCellWidget(row, 4, cmb_box)
            self.table_pins.setItem(row, 5, item_coord)
            row += 1

        self.table_pins.blockSignals(False)

    def _on_pin_edge_dropdown_changed(self, pin_name, new_edge):
        if getattr(self, '_updating_batch_dropdown', False):
            return

        # Determine target pins: check current selection or cached selection
        selected_rows = [idx.row() for idx in self.table_pins.selectionModel().selectedRows()]
        selected_pin_names = [self.table_pins.item(r, 0).text() for r in selected_rows if self.table_pins.item(r, 0)]
        if not selected_pin_names and getattr(self, '_cached_selected_pins', None):
            selected_pin_names = self._cached_selected_pins

        targets = selected_pin_names if (pin_name in selected_pin_names and len(selected_pin_names) > 1) else [pin_name]

        self._updating_batch_dropdown = True
        for p in targets:
            if p in self.pins_data:
                self.pins_data[p]["edge"] = new_edge
                # If moved to another edge, reset box if box belongs to a different edge
                cur_box = self.pins_data[p].get("box")
                if cur_box in self.constraint_boxes and self.constraint_boxes[cur_box].edge != new_edge:
                    self.pins_data[p]["box"] = "All Edges"

                # Sync dropdown widget in table for target row
                for r in range(self.table_pins.rowCount()):
                    it = self.table_pins.item(r, 0)
                    if it and it.text() == p:
                        cmb = self.table_pins.cellWidget(r, 2)
                        if cmb and cmb.currentText() != new_edge:
                            cmb.blockSignals(True)
                            cmb.setCurrentText(new_edge)
                            cmb.blockSignals(False)
                        cmb_b = self.table_pins.cellWidget(r, 4)
                        if cmb_b and cmb_b.currentText() != self.pins_data[p]["box"]:
                            cmb_b.blockSignals(True)
                            cmb_b.setCurrentText(self.pins_data[p]["box"])
                            cmb_b.blockSignals(False)
                        break

        self._updating_batch_dropdown = False
        # Track that the user explicitly set an edge for these pins
        for p in targets:
            self._user_set_edges.add(p)
        self._relayout_edge_pins(new_edge)
        self._update_table_coords()
        self.update_live_tcl()

    def _on_pin_tier_dropdown_changed(self, pin_name, new_tier):
        if getattr(self, '_updating_batch_dropdown', False):
            return

        selected_rows = [idx.row() for idx in self.table_pins.selectionModel().selectedRows()]
        selected_pin_names = [self.table_pins.item(r, 0).text() for r in selected_rows if self.table_pins.item(r, 0)]
        if not selected_pin_names and getattr(self, '_cached_selected_pins', None):
            selected_pin_names = self._cached_selected_pins

        targets = selected_pin_names if (pin_name in selected_pin_names and len(selected_pin_names) > 1) else [pin_name]

        affected_edges = set()
        self._updating_batch_dropdown = True
        for p in targets:
            if p in self.pins_data:
                self.pins_data[p]["tier"] = new_tier
                affected_edges.add(self.pins_data[p].get("edge", "bottom"))

                for r in range(self.table_pins.rowCount()):
                    it = self.table_pins.item(r, 0)
                    if it and it.text() == p:
                        cmb_tier = self.table_pins.cellWidget(r, 3)
                        if cmb_tier and cmb_tier.currentText() != new_tier:
                            cmb_tier.blockSignals(True)
                            cmb_tier.setCurrentText(new_tier)
                            cmb_tier.blockSignals(False)
                        break

        self._updating_batch_dropdown = False
        for ed in affected_edges:
            self._relayout_edge_pins(ed)
        self._update_table_coords()
        self.update_live_tcl()

    def _on_pin_box_dropdown_changed(self, pin_name, new_box):
        if getattr(self, '_updating_batch_dropdown', False):
            return

        selected_rows = [idx.row() for idx in self.table_pins.selectionModel().selectedRows()]
        selected_pin_names = [self.table_pins.item(r, 0).text() for r in selected_rows if self.table_pins.item(r, 0)]
        if not selected_pin_names and getattr(self, '_cached_selected_pins', None):
            selected_pin_names = self._cached_selected_pins

        targets = selected_pin_names if (pin_name in selected_pin_names and len(selected_pin_names) > 1) else [pin_name]

        affected_edges = set()
        self._updating_batch_dropdown = True
        for p in targets:
            if p in self.pins_data:
                self.pins_data[p]["box"] = new_box
                if new_box in self.constraint_boxes:
                    c_box = self.constraint_boxes[new_box]
                    self.pins_data[p]["edge"] = c_box.edge
                    affected_edges.add(c_box.edge)
                else:
                    affected_edges.add(self.pins_data[p].get("edge", "bottom"))

                for r in range(self.table_pins.rowCount()):
                    it = self.table_pins.item(r, 0)
                    if it and it.text() == p:
                        # Sync Box dropdown (column 4)
                        cmb = self.table_pins.cellWidget(r, 4)
                        if cmb and cmb.currentText() != new_box:
                            cmb.blockSignals(True)
                            cmb.setCurrentText(new_box)
                            cmb.blockSignals(False)
                        # Sync Edge dropdown if it changed (column 2)
                        cmb_edge = self.table_pins.cellWidget(r, 2)
                        target_edge = self.pins_data[p]["edge"]
                        if cmb_edge and cmb_edge.currentText() != target_edge:
                            cmb_edge.blockSignals(True)
                            cmb_edge.setCurrentText(target_edge)
                            cmb_edge.blockSignals(False)
                        break

        self._updating_batch_dropdown = False

        # Live re-layout pins along affected edges and boxes!
        for ed in affected_edges:
            self._relayout_edge_pins(ed)

        self._update_table_coords()
        self.update_live_tcl()

    def _relayout_edge_pins(self, edge):
        """
        Dynamically redistributes pins along an edge.
        Pins assigned to constraint boxes are distributed within their box spans.
        Unassigned pins on that edge are distributed evenly along the remaining edge space.
        """
        w = self.die_rect.width()
        h = self.die_rect.height()
        is_pad = self.rb_chip.isChecked()
        pw = 80.0 if is_pad else 4.0
        ph = 80.0 if is_pad else 4.0

        # 1. Pins with boxes on this edge
        edge_boxes = {b_name: b_obj for b_name, b_obj in self.constraint_boxes.items() if b_obj.edge == edge}
        for b_name, b_obj in edge_boxes.items():
            box_pins = [p for p, d in self.pins_data.items() if d.get("box") == b_name and d.get("edge") == edge]
            if not box_pins:
                continue
            s_um = min(b_obj.start_um, b_obj.end_um)
            e_um = max(b_obj.start_um, b_obj.end_um)
            span = max(10.0, e_um - s_um)
            step = span / (len(box_pins) + 1)
            for i, p in enumerate(box_pins):
                coord = s_um + step * (i + 1)
                x = coord if edge in ("bottom", "top") else (0.0 if edge == "left" else w)
                y = (0.0 if edge == "bottom" else h) if edge in ("bottom", "top") else coord
                if p not in self.pin_items:
                    self._place_pin_item(p, edge, x, y, pw, ph)
                else:
                    item = self.pin_items[p]
                    item.edge = edge
                    item.setPos(x, y)
                    self.pins_data[p]["x"] = x
                    self.pins_data[p]["y"] = y

        # 2. Pins without boxes on this edge — space them evenly along the edge
        unboxed_pins = [p for p, d in self.pins_data.items() if d.get("edge") == edge and d.get("box", "All Edges") == "All Edges"]
        if unboxed_pins:
            is_staggered = is_pad and (getattr(self, "pad_strategy", "single") == "staggered")
            inner_offset = 210.0 if is_staggered else 0.0
            span = w if edge in ("bottom", "top") else h
            row_start = 210.0 if is_pad else 0.0
            avail_span = max(100.0, span - 2.0 * row_start)
            step = avail_span / max(len(unboxed_pins), 1)

            for i, p in enumerate(unboxed_pins):
                coord = (row_start + step * (i + 0.5)) if is_pad else ((span / (len(unboxed_pins) + 1)) * (i + 1))
                tier = self.pins_data[p].get("tier", "Outer (Ring 1)")
                curr_inset = inner_offset if ("Inner" in tier or (is_staggered and i % 2 == 1)) else 0.0

                if edge == "bottom":
                    x = coord
                    y = curr_inset
                elif edge == "top":
                    x = coord
                    y = h - curr_inset
                elif edge == "left":
                    x = curr_inset
                    y = coord
                elif edge == "right":
                    x = w - curr_inset
                    y = coord

                if p not in self.pin_items:
                    self._place_pin_item(p, edge, x, y, pw, ph)
                else:
                    item = self.pin_items[p]
                    item.edge = edge
                    item.setPos(x, y)
                    self.pins_data[p]["x"] = x
                    self.pins_data[p]["y"] = y

    def _update_table_coords(self):
        for row in range(self.table_pins.rowCount()):
            name_item = self.table_pins.item(row, 0)
            if name_item:
                pname = name_item.text()
                if pname in self.pins_data:
                    d = self.pins_data[pname]
                    coord_item = self.table_pins.item(row, 5)
                    if coord_item:
                        coord_item.setText(f"({d['x']:.1f}, {d['y']:.1f})")

    def auto_distribute_pins(self):
        """
        Evenly distributes pins along the perimeter of the die based on edge and constraint boxes.
        """
        for item in self.pin_items.values():
            self.scene.removeItem(item)
        self.pin_items.clear()

        w = self.die_rect.width()
        h = self.die_rect.height()
        is_pad = self.rb_chip.isChecked()
        pin_w = 80.0 if is_pad else 4.0
        pin_h = 80.0 if is_pad else 4.0

        # Auto-distribute across all 4 edges proportionally based on aspect ratio
        all_names = sorted(list(self.pins_data.keys()), key=natural_sort_key)
        total = len(all_names)

        cw = self.original_core_rect.width() if hasattr(self, 'original_core_rect') else (self.core_rect.width() if hasattr(self, 'core_rect') and self.core_rect.width() > 0 else self.die_rect.width())
        ch = self.original_core_rect.height() if hasattr(self, 'original_core_rect') else (self.core_rect.height() if hasattr(self, 'core_rect') and self.core_rect.height() > 0 else self.die_rect.height())
        perim_half = max(10.0, cw + ch)

        # Proportional count: bottom and top get width proportion, left and right get height proportion
        n_bot = max(1, round(total * (cw / (2.0 * perim_half))))
        n_top = n_bot
        remaining = max(2, total - (n_bot + n_top))
        n_left = max(1, round(remaining / 2.0))
        n_right = total - (n_bot + n_top + n_left)

        idx0 = 0
        idx1 = idx0 + n_bot
        idx2 = idx1 + n_top
        idx3 = idx2 + n_left

        edges = {
            "bottom": all_names[idx0:idx1],
            "top": all_names[idx1:idx2],
            "left": all_names[idx2:idx3],
            "right": all_names[idx3:]
        }

        # Track that all pins now have an assigned edge so TCL sets edge constraints
        if not hasattr(self, "_user_set_edges"):
            self._user_set_edges = set()
        for name in all_names:
            self._user_set_edges.add(name)

        # Place across 4 edges
        # In Staggered Dual-Ring mode: alternating pads go to Outer (offset 0) and Inner (offset 210um)
        is_staggered = is_pad and (getattr(self, "pad_strategy", "single") == "staggered")
        inner_offset = 210.0 if is_staggered else 0.0

        for edge_name, edge_list in edges.items():
            n = len(edge_list)
            if n == 0:
                continue
            span = w if edge_name in ("bottom", "top") else h

            if is_pad:
                if is_staggered:
                    n1 = math.ceil(n / 2.0)
                    n2 = n - n1
                    row_min1 = 280.0
                    row_max1 = max(row_min1, span - 280.0 - 80.0)
                    max_span1 = max(0.0, row_max1 - row_min1)
                    min_span1 = (n1 - 1) * 85.0 if n1 > 1 else 0.0
                    step1 = max(85.0, (max_span1 / (n1 - 1))) if n1 > 1 else 0.0
                    start1 = row_min1 if n1 > 1 else (row_min1 + max_span1 / 2.0)

                    # Inner ring offset by 500um corner clearance and 45um stagger shift to avoid corner coordinate collision
                    row_min2 = 500.0
                    row_max2 = max(row_min2, span - 500.0 - 80.0)
                    max_span2 = max(0.0, row_max2 - row_min2)
                    step2 = max(85.0, (max_span2 / (n2 - 1))) if n2 > 1 else 0.0
                    start2 = (row_min2 + 45.0) if n2 > 1 else (row_min2 + max_span2 / 2.0)

                    idx1 = 0
                    idx2 = 0
                    for i, name in enumerate(edge_list):
                        is_inner = (i % 2 == 1)
                        if is_inner:
                            coord = start2 + idx2 * step2
                            curr_inset = 210.0
                            tier_label = "Inner (Ring 2)"
                            idx2 += 1
                        else:
                            coord = start1 + idx1 * step1
                            curr_inset = 0.0
                            tier_label = "Outer (Ring 1)"
                            idx1 += 1

                        self.pins_data[name]["tier"] = tier_label
                        if edge_name == "bottom":
                            x, y = coord, curr_inset
                        elif edge_name == "top":
                            x, y = coord, h - curr_inset
                        elif edge_name == "left":
                            x, y = curr_inset, coord
                        elif edge_name == "right":
                            x, y = w - curr_inset, coord
                        self._place_pin_item(name, edge_name, x, y, pin_w, pin_h)
                else:
                    # Single Ring:
                    # Safe clearance: 260um minimum offset from die vertex (corner cell 200um + 60um buffer)
                    # Safe end: span - 260um - 80um (pad width)
                    row_min = 260.0
                    row_max = max(row_min, span - 260.0 - 80.0)
                    max_span = max(0.0, row_max - row_min)
                    min_span_needed = (n - 1) * 85.0 if n > 1 else 0.0
                    if n > 1 and max_span < min_span_needed:
                        step = 85.0  # Enforce minimum 85um physical pad pitch
                    else:
                        step = (max_span / (n - 1)) if n > 1 else 0.0
                    start = row_min if n > 1 else (row_min + max_span / 2.0)
                    for i, name in enumerate(edge_list):
                        coord = start + i * step
                        self.pins_data[name]["tier"] = "Outer (Ring 1)"
                        if edge_name == "bottom":
                            x, y = coord, 0.0
                        elif edge_name == "top":
                            x, y = coord, h
                        elif edge_name == "left":
                            x, y = 0.0, coord
                        elif edge_name == "right":
                            x, y = w, coord
                        self._place_pin_item(name, edge_name, x, y, pin_w, pin_h)
            else:
                # Macro Mode (Pins)
                step = span / (n + 1)
                for i, name in enumerate(edge_list):
                    coord = snap_to_grid(step * (i + 1))
                    self.pins_data[name]["tier"] = "Outer (Ring 1)"
                    if edge_name == "bottom":
                        x, y = coord, 0.0
                    elif edge_name == "top":
                        x, y = coord, h
                    elif edge_name == "left":
                        x, y = 0.0, coord
                    elif edge_name == "right":
                        x, y = w, coord
                    self._place_pin_item(name, edge_name, x, y, pin_w, pin_h)

        self._populate_table()
        self.update_live_tcl()
        self.fit_view()

    def _place_pin_item(self, name, edge, x, y, pw, ph):
        pdir = self.pins_data[name]["dir"]
        p_item = PinItem(name, pdir, pw, ph, self)
        p_item.edge = edge
        p_item.setPos(x, y)
        self.scene.addItem(p_item)
        self.pin_items[name] = p_item
        self.pins_data[name]["edge"] = edge
        self.pins_data[name]["x"] = x
        self.pins_data[name]["y"] = y

    def start_draw_box_mode(self):
        self.canvas_view.drawing_box_mode = True
        self.canvas_view.setCursor(Qt.CursorShape.CrossCursor)

    def create_edge_constraint_from_drag(self, pt1, pt2):
        die = self.die_rect
        x1, y1 = pt1.x(), pt1.y()
        x2, y2 = pt2.x(), pt2.y()

        x_min, x_max = min(die.left(), die.right()), max(die.left(), die.right())
        y_min, y_max = min(die.top(), die.bottom()), max(die.top(), die.bottom())

        # Classify edge
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        dl = abs(mid_x - x_min)
        dr = abs(mid_x - x_max)
        db = abs(mid_y - y_min)
        dt = abs(mid_y - y_max)
        min_d = min(dl, dr, db, dt)

        if min_d == db:
            edge = "bottom"
            start_um = min(x1, x2)
            end_um = max(x1, x2)
        elif min_d == dt:
            edge = "top"
            start_um = min(x1, x2)
            end_um = max(x1, x2)
        elif min_d == dl:
            edge = "left"
            start_um = min(y1, y2)
            end_um = max(y1, y2)
        else:
            edge = "right"
            start_um = min(y1, y2)
            end_um = max(y1, y2)

        box_name = f"Region_{edge.capitalize()}_{self.box_counter}"
        self.box_counter += 1

        c_box = EdgeConstraintBox(box_name, edge, start_um, end_um, self.die_rect)
        self.scene.addItem(c_box)
        self.constraint_boxes[box_name] = c_box

        self.cmb_active_boxes.addItem(box_name)
        self.cmb_active_boxes.setCurrentText(box_name)

        # Do NOT auto-assign pins — user assigns them explicitly via the dropdown.
        self._populate_table()
        self.update_live_tcl()

    def remove_box_by_item(self, box_item):
        for name, item in list(self.constraint_boxes.items()):
            if item == box_item:
                self.scene.removeItem(item)
                del self.constraint_boxes[name]
                idx = self.cmb_active_boxes.findText(name)
                if idx >= 0:
                    self.cmb_active_boxes.removeItem(idx)
                for p_info in self.pins_data.values():
                    if p_info.get("box") == name:
                        p_info["box"] = "All Edges"
                break
        self._populate_table()
        self.update_live_tcl()

    def unplace_pin_item(self, pin_item):
        pname = pin_item.pin_name
        if pname in self.pin_items:
            self.scene.removeItem(pin_item)
            del self.pin_items[pname]
            if pname in self.pins_data:
                self.pins_data[pname]["x"] = 0.0
                self.pins_data[pname]["y"] = 0.0
                self.pins_data[pname]["edge"] = "unplaced"
            self._update_table_coords()
            self.update_live_tcl()

    def remove_selected_box(self):
        curr = self.cmb_active_boxes.currentText()
        if curr in self.constraint_boxes:
            c_box = self.constraint_boxes.pop(curr)
            self.scene.removeItem(c_box)
            idx = self.cmb_active_boxes.findText(curr)
            if idx >= 0:
                self.cmb_active_boxes.removeItem(idx)

            for p_info in self.pins_data.values():
                if p_info.get("box") == curr:
                    p_info["box"] = "All Edges"

            self._populate_table()
            self.update_live_tcl()

    def _legalize_edge_pos(self, pin_name, edge, pos, span):
        """
        Prevents overlapping between pads or pins placed along the same die perimeter edge.
        Ensures a clearance margin between neighboring pads.
        """
        is_pad = self.rb_chip.isChecked()
        min_clearance = max(span, 45.0 if is_pad else 5.0)

        other_positions = []
        for other_name, item in self.pin_items.items():
            if other_name == pin_name or item.edge != edge:
                continue
            cur_p = item.pos().x() if edge in ("bottom", "top") else item.pos().y()
            other_positions.append(cur_p)

        other_positions.sort()
        adjusted_pos = pos

        # Check collision and push if overlapping
        for op in other_positions:
            if abs(adjusted_pos - op) < min_clearance:
                if adjusted_pos >= op:
                    adjusted_pos = op + min_clearance
                else:
                    adjusted_pos = op - min_clearance

        return adjusted_pos

    def _check_pad_capacity(self, num_pads, pad_pitch=85.0):
        """
        Calculates physical perimeter capacity for I/O pads:
        Capacity = 2 * (Die Width + Die Height) / (pad_pitch)
        sky130 GPIO pads are 80um wide, so min pitch is ~85um.
        If num_pads exceeds capacity, returns (False, required_perimeter, available_perimeter, min_die_dim)
        """
        w = self.die_rect.width()
        h = self.die_rect.height()
        avail_perimeter = 2.0 * (w + h)
        req_perimeter = num_pads * pad_pitch
        if req_perimeter > avail_perimeter:
            min_dim = math.ceil(req_perimeter / 4.0)
            return False, req_perimeter, avail_perimeter, min_dim
        return True, req_perimeter, avail_perimeter, 0.0

    def on_pad_strategy_changed(self):
        is_staggered = self.rb_pad_staggered.isChecked()
        self.pad_strategy = "staggered" if is_staggered else "single"
        # Re-run auto distribution to update canvas with chosen tier offsets
        self.auto_distribute_pins()
        self.update_live_tcl()

    def on_mode_toggled(self):
        is_pad = self.rb_chip.isChecked()
        self.gb_pad_method.setVisible(is_pad)

        if is_pad:
            # Check pad perimeter capacity with physical 85um pitch
            num_pads = len(self.pins_data)
            pads_per_side = math.ceil(num_pads / 4.0)
            cw = self.core_rect.width() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.width() > 0 else 700.0
            ch = self.core_rect.height() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.height() > 0 else 1000.0

            # Calculate proportional pads based on core aspect ratio (W : H)
            cw = self.core_rect.width() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.width() > 0 else 700.0
            ch = self.core_rect.height() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.height() > 0 else 1000.0
            perim_half = cw + ch

            # Proportion of pads for horizontal (bottom/top) vs vertical (left/right) edges
            pads_h = max(1, round(num_pads * (cw / (2.0 * perim_half))))
            pads_v = max(1, round((num_pads - 2 * pads_h) / 2.0))

            # Method 1: Single Ring — preserve rectangular aspect ratio with uniform pad margins
            req_span_w_single = (pads_h * 85.0) + 420.0
            req_span_h_single = (pads_v * 85.0) + 420.0
            # Symmetrically expand keeping aspect ratio
            single_die_w = max(cw + 500.0, req_span_w_single)
            single_die_h = max(ch + 500.0, req_span_h_single)

            # Method 2: Dual-Ring Staggered — 2 tiers cut required side length significantly
            tier_h = math.ceil(pads_h / 2.0)
            tier_v = math.ceil(pads_v / 2.0)
            req_span_w_staggered = (tier_h * 85.0) + 950.0
            req_span_h_staggered = (tier_v * 85.0) + 950.0
            staggered_die_w = max(cw + 850.0, req_span_w_staggered)
            staggered_die_h = max(ch + 850.0, req_span_h_staggered)

            if os.environ.get("SILIS_HEADLESS_TEST", "") in ("1", "single"):
                self.rb_pad_single.setChecked(True)
                self.pad_strategy = "single"
                self.expand_die_for_padring(single_die_w, single_die_h, margin=250.0)
                return
            elif os.environ.get("SILIS_HEADLESS_TEST", "") == "staggered":
                self.rb_pad_staggered.setChecked(True)
                self.pad_strategy = "staggered"
                self.expand_die_for_padring(staggered_die_w, staggered_die_h, margin=420.0)
                return

            msg = QMessageBox(self)
            msg.setWindowTitle("Pad Ring Strategy Advisory")
            msg.setText(
                f"Full-Chip Pad Ring Mode: {num_pads} I/O Pads detected.\n"
                f"Core Dimensions: {cw:.1f} µm x {ch:.1f} µm (Aspect Ratio: {cw/ch:.2f})\n\n"
                f"Proportional Pad Allocation (Preserves Aspect Ratio):\n"
                f"• Bottom & Top: {pads_h} pads each\n"
                f"• Left & Right: {pads_v} pads each\n\n"
                f"Select your Physical Design packaging strategy:\n\n"
                f"• Method 1 [Single-Row Wirebond]:\n"
                f"  Standard single peripheral ring (85 µm pitch).\n"
                f"  Expanded Die: {single_die_w:.0f} µm x {single_die_h:.0f} µm (Rectangular)\n\n"
                f"• Method 2 [Dual-Ring Staggered (2x Density)]:\n"
                f"  Two concentric alternating pad tiers (Outer + Inner zipper).\n"
                f"  Expanded Die: {staggered_die_w:.0f} µm x {staggered_die_h:.0f} µm (Compact)\n"
                f"  Saves substantial silicon area!"
            )
            btn_single = msg.addButton("Method 1: Single Ring", QMessageBox.ButtonRole.AcceptRole)
            btn_staggered = msg.addButton("Method 2: Dual Staggered", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = msg.addButton("Cancel (Stay Port Mode)", QMessageBox.ButtonRole.RejectRole)
            msg.exec()

            clicked = msg.clickedButton()
            if clicked == btn_single:
                self.rb_pad_single.setChecked(True)
                self.pad_strategy = "single"
                self.expand_die_for_padring(single_die_w, single_die_h, margin=250.0)
            elif clicked == btn_staggered:
                self.rb_pad_staggered.setChecked(True)
                self.pad_strategy = "staggered"
                self.expand_die_for_padring(staggered_die_w, staggered_die_h, margin=420.0)
            else:
                self.rb_macro.blockSignals(True)
                self.rb_chip.blockSignals(True)
                self.rb_macro.setChecked(True)
                self.rb_chip.setChecked(False)
                self.rb_macro.blockSignals(False)
                self.rb_chip.blockSignals(False)
                self.gb_pad_method.setVisible(False)
                is_pad = False
                self.pad_ring_enabled = False
                if hasattr(self, "original_die_rect"):
                    self.die_rect = QRectF(self.original_die_rect)
                if hasattr(self, "original_core_rect"):
                    self.core_rect = QRectF(self.original_core_rect)
                self._draw_die_boundary()
                self.auto_distribute_pins()
        else:
            self.pad_ring_enabled = False
            if hasattr(self, "original_die_rect"):
                self.die_rect = QRectF(self.original_die_rect)
            if hasattr(self, "original_core_rect"):
                self.core_rect = QRectF(self.original_core_rect)
            self._draw_die_boundary()
            self.auto_distribute_pins()

        size = 80.0 if is_pad else 4.0
        for item in self.pin_items.values():
            item.setRect(-size/2, -size/2, size, size)
        self.update_live_tcl()

    def expand_die_for_padring(self, new_die_w, new_die_h, margin=250.0):
        """
        Expands die boundary in memory and redraws canvas while centering the core geometry.
        Enables automatic creation of OpenROAD IO pad ring sites on apply.
        """
        # Compute offset shift to center core inside new die
        old_cw = self.original_core_rect.width() if hasattr(self, 'original_core_rect') else (self.core_rect.width() if hasattr(self, 'core_rect') else 700.0)
        old_ch = self.original_core_rect.height() if hasattr(self, 'original_core_rect') else (self.core_rect.height() if hasattr(self, 'core_rect') else 1000.0)

        # Center the core area: [margin_x, margin_y] to [margin_x + cw, margin_y + ch]
        margin_x = round((new_die_w - old_cw) / 2.0, 1)
        margin_y = round((new_die_h - old_ch) / 2.0, 1)
        if margin_x < margin:
            margin_x = margin
        if margin_y < margin:
            margin_y = margin

        # Shift core rect to the center of the expanded die
        self.core_rect = QRectF(margin_x, margin_y, old_cw, old_ch)
        self.die_rect = QRectF(0, 0, new_die_w, new_die_h)
        self.pad_ring_enabled = True
        self.pad_ring_margin = margin
        self.pad_ring_margin_x = margin_x
        self.pad_ring_margin_y = margin_y
        self._draw_die_boundary()
        self.auto_distribute_pins()

        # Update constraint boxes geometry to new die
        for c_box in self.constraint_boxes.values():
            c_box.update_geometry(self.die_rect)
        self._update_table_coords()
        self.fit_view()

    def on_spacing_changed(self):
        self.update_live_tcl()

    def on_pin_selected_in_canvas(self, pin_name):
        # Do NOT call selectRow here — it clears all other selections.
        # Just highlight the corresponding row without changing multi-selection.
        for row in range(self.table_pins.rowCount()):
            it = self.table_pins.item(row, 0)
            if it and it.text() == pin_name:
                self.table_pins.scrollToItem(it)
                break

    def on_canvas_selection_changed(self):
        try:
            if not self.scene:
                return
            for item in self.scene.selectedItems():
                if isinstance(item, PinItem):
                    self.pins_data[item.pin_name]["x"] = item.pos().x()
                    self.pins_data[item.pin_name]["y"] = item.pos().y()
                    self.pins_data[item.pin_name]["edge"] = item.edge
            self._update_table_coords()
            self.update_live_tcl()
        except RuntimeError:
            pass

    def on_table_selection_changed(self):
        selected_rows = set(idx.row() for idx in self.table_pins.selectedIndexes())
        self._cached_selected_pins = [
            self.table_pins.item(r, 0).text() for r in sorted(selected_rows) if self.table_pins.item(r, 0)
        ]
        self._syncing_selection = True
        self.scene.blockSignals(True)
        for name, item in self.pin_items.items():
            item.setSelected(False)
        for row in selected_rows:
            pname = self.table_pins.item(row, 0).text()
            if pname in self.pin_items:
                self.pin_items[pname].setSelected(True)
        self.scene.blockSignals(False)
        self._syncing_selection = False

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self.fit_view)

    def fit_view(self):
        rect = self.die_rect.adjusted(-60, -60, 60, 60)
        self.canvas_view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def generate_tcl_script(self):
        hor_layer = self.cmb_hor_layer.currentText()
        ver_layer = self.cmb_ver_layer.currentText()
        pitch = self.sp_spacing.value()
        is_pad = self.rb_chip.isChecked()

        # Locate sky130 IO pad LEFs dynamically
        _io_lefs = []
        _io_cand_dirs = [
            os.path.join(REPO_ROOT, "third-party", "pdks", "sky130A", "libs.ref", "sky130_fd_io", "lef"),
            os.path.join(REPO_ROOT, "third-party", "pdks", "volare", "sky130", "versions", "0fe599b2afb6708d281543108caf8310912f54af", "sky130A", "libs.ref", "sky130_fd_io", "lef"),
            os.path.expanduser("~/.silis/pdks/sky130A/libs.ref/sky130_fd_io/lef"),
            os.path.expanduser("~/.silis/pdks/sky130B/libs.ref/sky130_fd_io/lef"),
        ]
        if os.environ.get("PDK_ROOT"):
            _io_cand_dirs.append(os.path.join(os.environ["PDK_ROOT"], "sky130A", "libs.ref", "sky130_fd_io", "lef"))
        for d in _io_cand_dirs:
            for f in ("sky130_ef_io.lef", "sky130_fd_io.lef"):
                p = os.path.join(d, f)
                if os.path.isfile(p) and p not in _io_lefs:
                    _io_lefs.append(p)

        lines = [
            "# ==============================================================================",
            "# Silis I/O Placement TCL (Generated by Silis I/O Placer)",
            "# ==============================================================================",
            "set tech [::ord::get_db_tech]",
            f"set io_hor \"{hor_layer}\"",
            f"set io_ver \"{ver_layer}\"",
            ""
        ]

        if is_pad:
            lines.append("# --- Full-Chip Pad Ring Placement (SiliconCompiler-Compliant Abutment & Zero DRC) ---")

            # Load sky130 IO pad LEFs
            for _lef in _io_lefs:
                lines.append(f"catch {{ read_lef \"{_lef}\" }}")
            lines.append("")

            # IO Sites creation (Exact SiliconCompiler geometry: site 1x200, corner 200x204)
            lines.append("# Create I/O Sites for Pad Placement")
            lines.append("catch { make_fake_io_site -name IO_SITE -width 1 -height 200 }")
            lines.append("catch { make_fake_io_site -name IO_CSITE -width 200 -height 204 }")
            lines.append("catch { make_io_sites -horizontal_site IO_SITE -vertical_site IO_SITE -corner_site IO_CSITE -offset 10 -rotation_horizontal R180 -rotation_vertical R180 -rotation_corner R180 }")
            lines.append("catch { place_corners sky130_ef_io__corner_pad }")
            lines.append("")

            # Master cell selection per pin direction
            def _pad_master(direction):
                if direction in ("power",):
                    return "sky130_fd_io__top_power_hvc_wpad"
                elif direction in ("ground",):
                    return "sky130_fd_io__top_ground_hvc_wpad"
                else:
                    return "sky130_fd_io__top_gpiov2"

            is_staggered = getattr(self, "pad_strategy", "single") == "staggered"
            dw = self.die_rect.width()
            dh = self.die_rect.height()

            lines.append("# Place pads & top-level design pins along perimeter")
            # Group pads by edge
            edge_pads = {"bottom": [], "top": [], "left": [], "right": []}
            for name, data in sorted(self.pins_data.items()):
                edge = data.get("edge", "bottom")
                if edge != "unplaced":
                    edge_pads[edge if edge in edge_pads else "bottom"].append((name, data))

            edge_to_row_name = {
                "bottom": "IO_SOUTH",
                "top": "IO_NORTH",
                "left": "IO_WEST",
                "right": "IO_EAST"
            }

            for edge, pad_list in edge_pads.items():
                if not pad_list:
                    continue
                edge_len = dw if edge in ("bottom", "top") else dh
                base_name = edge_to_row_name.get(edge, "IO_SOUTH")

                if is_staggered:
                    # In dual-ring staggered mode: separate into Outer (Ring 1) and Inner (Ring 2)
                    r1_pads = []
                    r2_pads = []
                    for i, (pname, pdata) in enumerate(pad_list):
                        tier = pdata.get("tier", "Outer (Ring 1)")
                        if "Inner" in tier or (tier == "Outer (Ring 1)" and (i % 2 == 1)):
                            r2_pads.append((pname, pdata))
                        else:
                            r1_pads.append((pname, pdata))

                    # Place Ring 1 (Outer)
                    pad_width = 80.0
                    if r1_pads:
                        row_min1 = 280.0
                        row_max1 = max(row_min1, edge_len - 280.0 - pad_width)
                        max_span1 = max(0.0, row_max1 - row_min1)
                        n1 = len(r1_pads)
                        min_span1 = (n1 - 1) * 85.0 if n1 > 1 else 0.0
                        if n1 > 1 and max_span1 < min_span1:
                            print(f"[IOPlacer WARNING] Edge '{edge}' Ring 1 ({edge_len:.1f}um) pitch violation for {n1} pads. Enforcing 85um min pitch.")
                            step1 = 85.0
                        else:
                            step1 = (max_span1 / (n1 - 1)) if n1 > 1 else 0.0
                        start1 = row_min1 if n1 > 1 else (row_min1 + max_span1 / 2.0)
                        for i, (pname, pdata) in enumerate(r1_pads):
                            loc = start1 + i * step1
                            master = _pad_master(pdata.get("dir", "input"))
                            safe = re.sub(r'[^A-Za-z0-9_]', '_', pname)
                            lines.append(f"catch {{ place_pad -master {master} -row {base_name}_1 -location {loc:.3f} pad_{safe} }}")
                            # Place matching top-level design pin on the core-facing inner edge
                            if edge == "bottom":
                                ploc = f"{loc:.3f} 210.000"
                                player = hor_layer
                            elif edge == "top":
                                ploc = f"{loc:.3f} {dh - 210.0:.3f}"
                                player = hor_layer
                            elif edge == "left":
                                ploc = f"210.000 {loc:.3f}"
                                player = ver_layer
                            else:
                                ploc = f"{dw - 210.0:.3f} {loc:.3f}"
                                player = ver_layer
                            lines.append(f"catch {{ place_pin -pin_name \"{pname}\" -layer {player} -location {{{ploc}}} }}")

                    # Place Ring 2 (Inner with corner clearance & stagger shift)
                    if r2_pads:
                        row_min2 = 500.0
                        row_max2 = max(row_min2, edge_len - 500.0 - pad_width)
                        max_span2 = max(0.0, row_max2 - row_min2)
                        n2 = len(r2_pads)
                        min_span2 = (n2 - 1) * 85.0 if n2 > 1 else 0.0
                        if n2 > 1 and max_span2 < min_span2:
                            print(f"[IOPlacer WARNING] Edge '{edge}' Ring 2 ({edge_len:.1f}um) pitch violation for {n2} pads. Enforcing 85um min pitch.")
                            step2 = 85.0
                        else:
                            step2 = (max_span2 / (n2 - 1)) if n2 > 1 else 0.0
                        start2 = (row_min2 + 45.0) if n2 > 1 else (row_min2 + max_span2 / 2.0)
                        for i, (pname, pdata) in enumerate(r2_pads):
                            loc = start2 + i * step2
                            master = _pad_master(pdata.get("dir", "input"))
                            safe = re.sub(r'[^A-Za-z0-9_]', '_', pname)
                            lines.append(f"catch {{ place_pad -master {master} -row {base_name}_2 -location {loc:.3f} pad_{safe} }}")
                            # Place matching top-level design pin on the core-facing inner edge
                            if edge == "bottom":
                                ploc = f"{loc:.3f} 420.000"
                                player = hor_layer
                            elif edge == "top":
                                ploc = f"{loc:.3f} {dh - 420.0:.3f}"
                                player = hor_layer
                            elif edge == "left":
                                ploc = f"420.000 {loc:.3f}"
                                player = ver_layer
                            else:
                                ploc = f"{dw - 420.0:.3f} {loc:.3f}"
                                player = ver_layer
                            lines.append(f"catch {{ place_pin -pin_name \"{pname}\" -layer {player} -location {{{ploc}}} }}")
                else:
                    # Standard Single Ring:
                    # Pad width in sky130 is exactly 80.0um.
                    # Corner site width is 200.0um (with 10um offset, corner ends at 210.0um).
                    # Safe start offset is 220.0um (clear of corner).
                    # Safe end offset is edge_len - 220.0um - pad_width (80.0um).
                    pad_width = 80.0
                    min_pitch = 80.0  # Physical hard lower bound to prevent overlap
                    row_min = 220.0
                    row_max = max(row_min, edge_len - 220.0 - pad_width)
                    max_span = max(0.0, row_max - row_min)
                    n = len(pad_list)

                    if n > 1:
                        # Maximize uniform spacing, but strictly enforce min_pitch >= 80.0um
                        step = max_span / (n - 1)
                        if step < min_pitch:
                            print(f"[IOPlacer WARNING] Edge '{edge}' ({edge_len:.1f}um) cannot hold {n} pads with 80um pitch (needs >= {(n-1)*80.0 + 440.0 + pad_width:.1f}um). Clamping to 80.0um to guarantee ZERO overlap.")
                            step = min_pitch
                    else:
                        step = 0.0

                    start = row_min if n > 1 else (row_min + max_span / 2.0)
                    for i, (name, data) in enumerate(pad_list):
                        loc = snap_to_grid(start + i * step)
                        master = _pad_master(data.get("dir", "input"))
                        safe_name = re.sub(r'[^A-Za-z0-9_]', '_', name)
                        lines.append(f"catch {{ place_pad -master {master} -row {base_name} -location {loc:.3f} pad_{safe_name} }}")
                        core_x1 = self.core_rect.left() if hasattr(self, 'core_rect') and self.core_rect.width() > 0 else 250.0
                        core_y1 = self.core_rect.top() if hasattr(self, 'core_rect') and self.core_rect.height() > 0 else 250.0
                        core_x2 = self.core_rect.right() if hasattr(self, 'core_rect') and self.core_rect.width() > 0 else (dw - 250.0)
                        core_y2 = self.core_rect.bottom() if hasattr(self, 'core_rect') and self.core_rect.height() > 0 else (dh - 250.0)

                        if edge == "bottom":
                            ploc = f"{loc:.3f} {core_y1:.3f}"
                            player = hor_layer
                        elif edge == "top":
                            ploc = f"{loc:.3f} {core_y2:.3f}"
                            player = hor_layer
                        elif edge == "left":
                            ploc = f"{core_x1:.3f} {loc:.3f}"
                            player = ver_layer
                        else:
                            ploc = f"{core_x2:.3f} {loc:.3f}"
                            player = ver_layer
                        lines.append(f"catch {{ place_pin -pin_name \"{name}\" -layer {player} -location {{{ploc}}} }}")

            # Fill any remaining spaces between pads and connect abutment for continuous power ring
            lines.append("")
            lines.append("# --- Fill remaining gaps and connect abutment for continuous supply rails ---")
            lines.append("set pad_fill {sky130_ef_io__com_bus_slice_20um sky130_ef_io__com_bus_slice_10um sky130_ef_io__com_bus_slice_5um sky130_ef_io__com_bus_slice_1um}")
            lines.append("foreach row {IO_NORTH IO_SOUTH IO_WEST IO_EAST} {")
            lines.append("    catch { place_io_fill -row $row {*}$pad_fill }")
            lines.append("}")
            lines.append("catch { connect_by_abutment }")

        else:
            lines.append("# --- Macro Peripheral Port Placement (Pure WYSIWYG) ---")
            lines.append("clear_io_pin_constraints")

            # In Pure WYSIWYG mode, every placed pin is stamped at its exact visual canvas coordinates.
            # No fuzzy simulated annealing solver is invoked. What you see is what OpenROAD places.
            for name, data in sorted(self.pins_data.items(), key=lambda item: natural_sort_key(item[0])):
                edge = data.get("edge", "bottom")
                if edge == "unplaced":
                    continue
                px = snap_to_grid(data.get("x", 0.0))
                py = snap_to_grid(data.get("y", 0.0))
                # Assign appropriate routing layer based on orientation:
                # Top / Bottom edges use horizontal layer ($io_hor, e.g. met3)
                # Left / Right edges use vertical layer ($io_ver, e.g. met4)
                layer = hor_layer if edge in ("bottom", "top") else ver_layer
                if name in self.pin_items and hasattr(self.pin_items[name], "layer"):
                    layer = self.pin_items[name].layer
                lines.append(f"catch {{ place_pin -pin_name \"{name}\" -layer {layer} -location {{{px:.3f} {py:.3f}}} }}")

        return "\n".join(lines)

    def update_live_tcl(self):
        script = self.generate_tcl_script()
        self.txt_live_tcl.setPlainText(script)

    def on_export_hard_macro(self):
        """
        Triggers full-spectrum macro package generation into ~/.silis/macrocache/<pdk>/<macro_name>/
        """
        proj_root = self._get_project_root()

        macro_name = self.project_config.get("macro_name", "")
        if not macro_name:
            macro_name = os.path.basename(proj_root.rstrip("/\\")) or "user_macro"

        pdk_name = self.project_config.get("pdk", "sky130")

        try:
            pkg_path = run_macro_package_export(
                project_root=proj_root,
                macro_name=macro_name,
                pdk_name=pdk_name
            )
            QMessageBox.information(
                self,
                "Macro Package Export Complete",
                f"Production Hard Macro Package successfully exported to:\n\n{pkg_path}\n\n"
                "Package contains full SkyWater deliverables:\n"
                "- Abstract LEF with internal routing blockage\n"
                "- Full Merged GDSII\n"
                "- Verilog Blackbox Stub & Gate Sim Model\n"
                "- SPICE Netlist & SDC\n"
                "- Multi-Corner SPEF & Liberty Models (SS/TT/FF/SS_cold/FF_hot)\n"
                "- Machine-readable manifest.json & README.md\n\n"
                "Available immediately in Macro IP Catalog."
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not export macro package:\n{e}")

    def apply_and_run(self):
        """
        Applies TCL script directly into current backend flow execution.
        If Pad Mode is active, tunes run_floorplan.tcl in-place preserving all user edits,
        and seamlessly replays the recorded session steps into a fresh OpenROAD instance.
        """
        tcl_script = self.generate_tcl_script()
        proj_root = self._get_project_root()

        results_dir = os.path.join(proj_root, "results")
        os.makedirs(results_dir, exist_ok=True)
        def_abs_path = os.path.join(results_dir, "temp.def").replace("\\", "/")

        final_tcl = tcl_script + f'\nwrite_def "{def_abs_path}"\nputs "SILIS_IO_PINS_DONE"\n'

        step_script = os.path.join(proj_root, "run_io_pins.tcl").replace("\\", "/")
        try:
            with open(step_script, "w") as f:
                f.write(final_tcl)
        except Exception as e:
            print(f"[IOPlacer] Error writing run_io_pins.tcl: {e}")

        is_pad = self.rb_chip.isChecked()
        if is_pad and getattr(self, "pad_ring_enabled", False):
            # 1. Non-destructively tune existing run_floorplan.tcl preserving all user edits:
            fp_script = os.path.join(proj_root, "run_floorplan.tcl")
            margin_x = getattr(self, "pad_ring_margin_x", getattr(self, "pad_ring_margin", 250.0))
            margin_y = getattr(self, "pad_ring_margin_y", getattr(self, "pad_ring_margin", 250.0))
            tune_floorplan_script_for_padring(fp_script, self.die_rect.width(), self.die_rect.height(), margin_x, margin_y)

            # 2. Check if parent_flow has a command journal to replay:
            if self.parent_flow and hasattr(self.parent_flow, "cmd_journal") and self.parent_flow.cmd_journal:
                replay_lines = ["# Preemptive Session Replay with Tuned Floorplan"]
                seen_cmds = set()
                pre_place_cmds = []
                downstream_cmds = []
                io_cmd = f'source "{step_script}"'

                for cmd in self.parent_flow.cmd_journal:
                    # Skip previous IO pin runs and recursive replay_flow runs
                    if "run_io_pins.tcl" in cmd or "replay_flow.tcl" in cmd:
                        continue
                    if cmd in seen_cmds:
                        continue
                    seen_cmds.add(cmd)
                    # Check if command belongs to place/cts/route/downstream
                    if any(step in cmd for step in ["run_place.tcl", "run_cts.tcl", "run_route.tcl"]):
                        downstream_cmds.append(cmd)
                    else:
                        pre_place_cmds.append(cmd)

                # Ensure init_pdk.tcl is always executed first so LEFs, netlist, and design are linked!
                init_cmds = []
                other_pre_cmds = []
                for cmd in pre_place_cmds:
                    if "init_pdk.tcl" in cmd:
                        if not init_cmds:
                            init_cmds.append(cmd)
                    else:
                        other_pre_cmds.append(cmd)

                if not init_cmds:
                    init_tcl = os.path.join(proj_root, "init_pdk.tcl").replace("\\", "/")
                    if os.path.isfile(init_tcl):
                        init_cmds = [f'source "{init_tcl}"']

                # Order: init_pdk (network/LEF/linking) -> floorplan/tap/pdn -> IO pins -> place/cts/route
                replay_lines.extend(init_cmds)
                replay_lines.extend(other_pre_cmds)
                replay_lines.append(io_cmd)
                replay_lines.extend(downstream_cmds)
                replay_lines.append('puts "SILIS_REPLAY_DONE"')

                replay_path = os.path.join(proj_root, "replay_flow.tcl").replace("\\", "/")
                try:
                    with open(replay_path, "w") as f:
                        f.write("\n".join(replay_lines) + "\n")
                except Exception as e:
                    print(f"[IOPlacer] Error writing replay_flow.tcl: {e}")

                if hasattr(self.parent_flow, "replay_session_with_script"):
                    self.parent_flow.replay_session_with_script(replay_path)
                    self.accept()
                    return

        # Fallback or standard Macro Mode execution
        if self.parent_flow:
            if hasattr(self.parent_flow, "term_log"):
                self.parent_flow.term_log.append("[SYS] Applying Custom I/O Pin Placement...")
            if hasattr(self.parent_flow, "send_command_internal"):
                self.parent_flow.send_command_internal(f'source "{step_script}"')
            elif hasattr(self.parent_flow, "send_command"):
                self.parent_flow.send_command(f'source "{step_script}"')

        self.accept()
