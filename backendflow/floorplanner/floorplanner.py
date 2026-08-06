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
        if event.angleDelta().y() > 0:
            self.scale(self._zoom_factor, self._zoom_factor)
        else:
            self.scale(1 / self._zoom_factor, 1 / self._zoom_factor)


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


class ResizeHandle(QGraphicsRectItem):
    def __init__(self, pos_type, parent):
        super().__init__(-3, -3, 6, 6, parent)
        self.pos_type = pos_type 
        self.setBrush(QBrush(Qt.GlobalColor.white))
        self.setPen(QPen(Qt.GlobalColor.black))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        
        if pos_type in ['tl', 'br']: self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif pos_type in ['tr', 'bl']: self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif pos_type in ['tc', 'bc']: self.setCursor(Qt.CursorShape.SizeVerCursor)
        else: self.setCursor(Qt.CursorShape.SizeHorCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if hasattr(self.parentItem(), "handle_moved"):
                self.parentItem().handle_moved(self.pos_type, value)
        return super().itemChange(change, value)

class ResizableRectItem(QGraphicsRectItem):
    def __init__(self, x, y, w, h, parent=None):
        super().__init__(x, y, w, h, parent)
        self.handles = {}
        for pt in ['tl', 'tc', 'tr', 'lc', 'rc', 'bl', 'bc', 'br']:
            hnd = ResizeHandle(pt, self)
            self.handles[pt] = hnd
            hnd.hide()
        self.updating_handles = False
        self.update_handle_positions()

    def update_handle_positions(self):
        self.updating_handles = True
        r = self.rect()
        self.handles['tl'].setPos(r.left(), r.top())
        self.handles['tc'].setPos(r.center().x(), r.top())
        self.handles['tr'].setPos(r.right(), r.top())
        self.handles['lc'].setPos(r.left(), r.center().y())
        self.handles['rc'].setPos(r.right(), r.center().y())
        self.handles['bl'].setPos(r.left(), r.bottom())
        self.handles['bc'].setPos(r.center().x(), r.bottom())
        self.handles['br'].setPos(r.right(), r.bottom())
        self.updating_handles = False

    def handle_moved(self, pos_type, new_pos):
        if self.updating_handles: return
        r = self.rect()
        nx, ny = new_pos.x(), new_pos.y()
        left, right, top, bottom = r.left(), r.right(), r.top(), r.bottom()
        
        if 'l' in pos_type: left = nx
        if 'r' in pos_type: right = nx
        if 't' in pos_type: top = ny
        if 'b' in pos_type: bottom = ny
        
        if right < left: left, right = right, left
        if bottom < top: top, bottom = bottom, top
            
        new_w = max(1.0, right - left)
        new_h = max(1.0, bottom - top)
        
        self.setRect(left, top, new_w, new_h)

    def setRect(self, x, y, w, h):
        super().setRect(x, y, w, h)
        self.update_handle_positions()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            selected = bool(value)
            for h in self.handles.values():
                h.setVisible(selected)
        return super().itemChange(change, value)

class BlockageItem(ResizableRectItem):
    def __init__(self, x, y, w, h, btype, pct, parent=None):
        super().__init__(x, y, w, h, parent)
        self.btype = btype
        self.pct = pct
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        if self.btype == "Hard":
            color = QColor(255, 100, 100, 100) # Red
            pen_color = Qt.GlobalColor.darkRed
        elif self.btype == "Soft":
            color = QColor(100, 100, 255, 100) # Blue
            pen_color = Qt.GlobalColor.darkBlue
        else: # Partial
            color = QColor(100, 255, 100, 100) # Green
            pen_color = Qt.GlobalColor.darkGreen
            
        self.setBrush(QBrush(color)) 
        self.setPen(QPen(pen_color, 2, Qt.PenStyle.DashLine))
        
        self.halo = (0, 0, 0, 0)
        self.halo_rect = QGraphicsRectItem(self)
        self.halo_rect.setPen(QPen(Qt.GlobalColor.gray, 2, Qt.PenStyle.DotLine))
        self.halo_rect.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        
        self.text = QGraphicsTextItem("", self)
        self.text.setDefaultTextColor(QColor(150, 150, 150))
        self.text.setTransform(QTransform.fromScale(1, -1))
        self.update_text()

        self.update_text()
        
    def update_text(self):
        if self.btype == "Partial": txt = f"PARTIAL: {self.pct}%"
        elif self.btype == "Soft": txt = "SOFT"
        else: txt = "HARD"
        self.text.setPlainText(txt)
        rect = self.rect()
        br = self.text.boundingRect()
        self.text.setPos(rect.x() + rect.width()/2 - br.width()/2, rect.y() + rect.height()/2 + br.height()/2)

    def setRect(self, x, y, w, h):
        super().setRect(x, y, w, h)
        l, r, b, t = self.halo
        self.halo_rect.setRect(x - l, y - b, w + l + r, h + b + t)
        if hasattr(self, 'update_text'):
            self.update_text()

    def update_halo(self, l, r, b, t):
        self.halo = (l, r, b, t)
        rect = self.rect()
        self.halo_rect.setRect(rect.x() - l, rect.y() - b, rect.width() + l + r, rect.height() + b + t)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value
            new_pos.setX(round(new_pos.x(), 3))
            new_pos.setY(round(new_pos.y(), 3))
            return new_pos
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if hasattr(self, "handles"):
                self.update_handle_positions()
        return super().itemChange(change, value)

class RegionItem(ResizableRectItem):
    def __init__(self, x, y, w, h, module_name, is_fence=False, parent=None):
        super().__init__(x, y, w, h, parent)
        self.module_name = module_name
        self.is_fence = is_fence
        self.halo = (0, 0, 0, 0)
        self.halo_type = "Routing halo"
        self.halo_rect = QGraphicsRectItem(self)
        self.halo_rect.setPen(QPen(Qt.GlobalColor.gray, 2, Qt.PenStyle.DotLine))
        self.halo_rect.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        
        color = QColor(255, 165, 0, 100) if is_fence else QColor(255, 255, 0, 100)
        pen_color = Qt.GlobalColor.darkYellow
        self.setBrush(QBrush(color))
        self.setPen(QPen(pen_color, 2, Qt.PenStyle.SolidLine))
        
        self.text = QGraphicsTextItem("", self)
        self.text.setDefaultTextColor(Qt.GlobalColor.black)
        self.text.setTransform(QTransform.fromScale(1, -1))
        self.update_text()
        
    def update_text(self):
        t = "FENCE" if self.is_fence else "REGION"
        self.text.setPlainText(f"{t}: {self.module_name}")
        rect = self.rect()
        br = self.text.boundingRect()
        self.text.setPos(rect.x() + rect.width()/2 - br.width()/2, rect.y() + rect.height()/2 + br.height()/2)

    def setRect(self, x, y, w, h):
        super().setRect(x, y, w, h)
        l, r, b, t = self.halo
        self.halo_rect.setRect(x - l, y - b, w + l + r, h + b + t)
        if hasattr(self, 'update_text'):
            self.update_text()

    def update_halo(self, l, r, b, t):
        self.halo = (l, r, b, t)
        rect = self.rect()
        self.halo_rect.setRect(rect.x() - l, rect.y() - b, rect.width() + l + r, rect.height() + b + t)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value
            new_pos.setX(round(new_pos.x(), 3))
            new_pos.setY(round(new_pos.y(), 3))
            return new_pos
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if hasattr(self.scene(), "update_utilization"):
                self.scene().update_utilization()
            if hasattr(self, "handles"):
                self.update_handle_positions()
        return super().itemChange(change, value)



class FloorplanView(InteractiveGraphicsView):
    macro_dropped = pyqtSignal(str, float, float, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.drawing_blockage = False
        self.current_blockage = None
        self.blockage_start_pos = None
        self.btype = "Hard"
        self.pct = 0
        self.drawing_region = False
        self.current_region = None
        self.region_start_pos = None
        self.region_module = ""
        self.region_is_fence = False
        self.pan_active = False
        self.pan_start_pos = None
        
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        
    def start_drawing(self, btype, pct):
        self.drawing_blockage = True
        self.drawing_region = False
        self.btype = btype
        self.pct = pct
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def start_drawing_region(self, module_name, is_fence):
        self.drawing_region = True
        self.drawing_blockage = False
        self.region_module = module_name
        self.region_is_fence = is_fence
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.pan_active = True
            self.pan_start_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if self.drawing_blockage and event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.pos())
            self.blockage_start_pos = QPointF(round(pos.x(), 3), round(pos.y(), 3))
            self.current_blockage = BlockageItem(self.blockage_start_pos.x(), self.blockage_start_pos.y(), 0, 0, self.btype, self.pct)
            self.scene().addItem(self.current_blockage)
            return
            
        if self.drawing_region and event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.pos())
            self.region_start_pos = QPointF(round(pos.x(), 3), round(pos.y(), 3))
            self.current_region = RegionItem(self.region_start_pos.x(), self.region_start_pos.y(), 0, 0, self.region_module, self.region_is_fence)
            self.scene().addItem(self.current_region)
            return

        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        if self.pan_active:
            delta = event.pos() - self.pan_start_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self.pan_start_pos = event.pos()
            return

        if self.drawing_blockage and self.current_blockage:
            pos = self.mapToScene(event.pos())
            px, py = round(pos.x(), 3), round(pos.y(), 3)
            x1 = min(px, self.blockage_start_pos.x())
            y1 = min(py, self.blockage_start_pos.y())
            w = abs(px - self.blockage_start_pos.x())
            h = abs(py - self.blockage_start_pos.y())
            self.current_blockage.setRect(x1, y1, w, h)
            self.current_blockage.update_text()
            return
            
        if self.drawing_region and self.current_region:
            pos = self.mapToScene(event.pos())
            px, py = round(pos.x(), 3), round(pos.y(), 3)
            x1 = min(px, self.region_start_pos.x())
            y1 = min(py, self.region_start_pos.y())
            w = abs(px - self.region_start_pos.x())
            h = abs(py - self.region_start_pos.y())
            self.current_region.setRect(x1, y1, w, h)
            self.current_region.update_text()
            if hasattr(self.parentWidget(), "update_utilization"):
                self.parentWidget().update_utilization()
            return
            
        super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.pan_active = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if self.drawing_blockage and event.button() == Qt.MouseButton.LeftButton:
            self.drawing_blockage = False
            self.current_blockage = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "save_state"): p.save_state(); break
                p = p.parentWidget()
            return
            
        if self.drawing_region and event.button() == Qt.MouseButton.LeftButton:
            self.drawing_region = False
            self.current_region = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "save_state"): p.save_state(); break
                p = p.parentWidget()
            return
        
        super().mouseReleaseEvent(event)
        
        # Save state on mouse release in case items were moved
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "save_state"):
                    p.save_state()
                    break
                p = p.parentWidget()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            if self.drawing_blockage:
                self.drawing_blockage = False
                if self.current_blockage:
                    self.scene().removeItem(self.current_blockage)
                    self.current_blockage = None
                self.setCursor(Qt.CursorShape.ArrowCursor)
        elif key == Qt.Key.Key_W:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 20)
        elif key == Qt.Key.Key_S:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 20)
        elif key == Qt.Key.Key_A:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 20)
        elif key == Qt.Key.Key_D:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 20)
        elif key == Qt.Key.Key_R:
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "fit_die"):
                    p.fit_die()
                    break
                p = p.parentWidget()
        elif key == Qt.Key.Key_Delete or key == Qt.Key.Key_Backspace:
            for item in self.scene().selectedItems():
                if isinstance(item, MacroItem) or isinstance(item, BlockageItem) or isinstance(item, RegionItem):
                    self.scene().removeItem(item)
                    if isinstance(item, MacroItem) and hasattr(item, 'list_item') and item.list_item:
                        item.list_item.setFlags(item.list_item.flags() | Qt.ItemFlag.ItemIsEnabled)
                        item.list_item.setText(item.list_item.text().replace(" [PLACED]", ""))
                        item.list_item.setForeground(QBrush(QColor("white")))
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "save_state"):
                    p.save_state()
                    break
                p = p.parentWidget()
        super().keyPressEvent(event)

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
            self.macro_dropped.emit(master_name, round(pos.x(), 3), round(pos.y(), 3), inst_name)
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
        self.list_item = None
        self.halo = (0, 0, 0, 0)
        self.orientation = "R0"
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setBrush(QBrush(QColor("#4CAF50")))
        self.setPen(QPen(Qt.GlobalColor.black))
        
        self.halo_rect = QGraphicsRectItem(self)
        self.halo_rect.setPen(QPen(Qt.GlobalColor.gray, 2, Qt.PenStyle.DotLine))
        self.halo_rect.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        
        self.text = QGraphicsTextItem(f"{self.inst_name}\n({name})", self)
        self.text.setDefaultTextColor(Qt.GlobalColor.white)
        self.text.setTransform(QTransform.fromScale(1, -1))
        # Center text
        br = self.text.boundingRect()
        self.text.setPos(width/2 - br.width()/2, height/2 + br.height()/2)

    def update_halo(self, l, r, b, t):
        self.halo = (l, r, b, t)
        if self.orientation in ["R90", "R270", "MX90", "MY90"]:
            self.halo_rect.setRect(-l, -b, self.h + l + r, self.w + b + t)
        else:
            self.halo_rect.setRect(-l, -b, self.w + l + r, self.h + b + t)

    def set_orientation(self, orient):
        old_is_swapped = self.orientation in ["R90", "R270", "MX90", "MY90"]
        self.orientation = orient
        new_is_swapped = orient in ["R90", "R270", "MX90", "MY90"]
        
        if old_is_swapped != new_is_swapped:
            cx = self.pos().x() + self.rect().width() / 2.0
            cy = self.pos().y() + self.rect().height() / 2.0
            if new_is_swapped:
                self.setRect(0, 0, self.h, self.w)
            else:
                self.setRect(0, 0, self.w, self.h)
            self.setPos(cx - self.rect().width() / 2.0, cy - self.rect().height() / 2.0)
            
        l, r, b, t = self.halo
        self.update_halo(l, r, b, t)
        
        br = self.text.boundingRect()
        self.text.setPos(self.rect().width()/2 - br.width()/2, self.rect().height()/2 + br.height()/2)
        # Trigger re-clamp
        self.setPos(self.itemChange(QGraphicsItem.GraphicsItemChange.ItemPositionChange, self.pos()))

    def set_inst_name(self, inst_name):
        self.inst_name = inst_name
        self.text.setPlainText(f"{self.inst_name}\n({self.name})")
        br = self.text.boundingRect()
        self.text.setPos(self.rect().width()/2 - br.width()/2, self.rect().height()/2 + br.height()/2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Snap to grid (3 decimal places)
            new_pos = value
            x = round(new_pos.x(), 3)
            y = round(new_pos.y(), 3)
            
            w = self.h if self.orientation in ["R90", "R270", "MX90", "MY90"] else self.w
            h = self.w if self.orientation in ["R90", "R270", "MX90", "MY90"] else self.h
            if self.core_rect:
                max_x = self.core_rect.width() - w
                max_y = self.core_rect.height() - h
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
        self.resize(1400, 900)
        self.project_config = project_config
        self.pdk_mgr = pdk_mgr
        self.floorplan_initialized = False
        self.die_rect = None
        self.core_rect = None
        self.macro_sizes = {}
        self.undo_stack = []
        self.redo_stack = []
        self.is_undoing = False
        
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(self.redo)
        
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
        
        self.lbl_core_util = QLabel("Core Utilization: -")
        fl_die.addRow(self.lbl_core_util)
        
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
        self.cmb_orientation = QComboBox()
        self.cmb_orientation.addItems(["R0", "R90", "R180", "R270", "MX", "MY", "MX90", "MY90"])
        fl_sel.addRow("Macro:", self.lbl_sel_name)
        fl_sel.addRow("Instance:", self.txt_inst_name)
        fl_sel.addRow("Orientation:", self.cmb_orientation)
        fl_sel.addRow("X (µm):", self.sp_sel_x)
        fl_sel.addRow("Y (µm):", self.sp_sel_y)
        self.sp_sel_x.valueChanged.connect(self.on_spinbox_changed)
        self.sp_sel_y.valueChanged.connect(self.on_spinbox_changed)
        self.cmb_orientation.currentTextChanged.connect(self.on_orientation_changed)

        # Halo Settings
        self.chk_equal_halo = QCheckBox("Equal Halo (µm)")
        self.chk_equal_halo.setChecked(True)
        self.chk_equal_halo.toggled.connect(self.on_halo_equal_toggled)
        
        self.sp_halo_l = QDoubleSpinBox(); self.sp_halo_l.setRange(0, 100000)
        self.sp_halo_r = QDoubleSpinBox(); self.sp_halo_r.setRange(0, 100000)
        self.sp_halo_b = QDoubleSpinBox(); self.sp_halo_b.setRange(0, 100000)
        self.sp_halo_t = QDoubleSpinBox(); self.sp_halo_t.setRange(0, 100000)
        self.sp_halo_r.setEnabled(False)
        self.sp_halo_b.setEnabled(False)
        self.sp_halo_t.setEnabled(False)

        fl_sel.addRow(self.chk_equal_halo)
        fl_sel.addRow("Halo Left/All:", self.sp_halo_l)
        fl_sel.addRow("Halo Right:", self.sp_halo_r)
        fl_sel.addRow("Halo Bottom:", self.sp_halo_b)
        fl_sel.addRow("Halo Top:", self.sp_halo_t)

        self.sp_halo_l.valueChanged.connect(self.on_halo_changed)
        self.sp_halo_r.valueChanged.connect(self.on_halo_changed)
        self.sp_halo_b.valueChanged.connect(self.on_halo_changed)
        self.sp_halo_t.valueChanged.connect(self.on_halo_changed)

        left_layout.addWidget(gb_sel)
        
        btn_tcl = QPushButton("Apply Floorplan & Run")
        btn_tcl.setStyleSheet("background: #0078D7; color: white; font-weight: bold;")
        btn_tcl.clicked.connect(self.generate_floorplan_tcl)
        left_layout.addWidget(btn_tcl)
        
        btn_fit = QPushButton("Fit Die in View")
        btn_fit.clicked.connect(self.fit_die)
        left_layout.addWidget(btn_fit)
        
        left_layout.addStretch()
        splitter.addWidget(left_widget)
        
        mid_widget = QWidget()
        mid_layout = QVBoxLayout(mid_widget)
        self.view = FloorplanView(self)
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
        
        # Regions & Fences
        gb_region = QGroupBox("Regions & Fences")
        fl_region = QFormLayout(gb_region)
        self.cmb_region_module = QComboBox()
        self.btn_draw_region = QPushButton("Create Region")
        self.btn_draw_fence = QPushButton("Create Fence")
        self.lbl_region_util = QLabel("Region Utilization: -")
        
        self.btn_draw_region.clicked.connect(lambda: self.view.start_drawing_region(self.cmb_region_module.currentText(), False))
        self.btn_draw_fence.clicked.connect(lambda: self.view.start_drawing_region(self.cmb_region_module.currentText(), True))
        
        fl_region.addRow("Module:", self.cmb_region_module)
        fl_region.addRow(self.btn_draw_region, self.btn_draw_fence)
        fl_region.addRow(self.lbl_region_util)
        right_layout.addWidget(gb_region)
        
        gb_block = QGroupBox("Blockages")
        fl_block = QFormLayout(gb_block)
        self.cmb_block_type = QComboBox()
        self.cmb_block_type.addItems(["Hard", "Soft", "Partial"])
        self.sp_block_pct = QDoubleSpinBox(); self.sp_block_pct.setRange(0, 100); self.sp_block_pct.setValue(40)
        self.sp_block_pct.setEnabled(False)
        self.cmb_block_type.currentIndexChanged.connect(lambda i: self.sp_block_pct.setEnabled(self.cmb_block_type.currentText() == "Partial"))
        
        self.btn_draw_block = QPushButton("Draw Blockage")
        self.btn_draw_block.clicked.connect(self.start_drawing_blockage)
        
        fl_block.addRow("Type:", self.cmb_block_type)
        fl_block.addRow("Density %:", self.sp_block_pct)
        fl_block.addRow(self.btn_draw_block)
        
        right_layout.addWidget(gb_block)
        
        splitter.addWidget(right_widget)
        
        splitter.setSizes([250, 600, 200])
        self.tabs.setEnabled(False)
        if self.project_config: self.populate_macro_list(self.project_config)

    def on_halo_equal_toggled(self, checked):
        self.sp_halo_r.setEnabled(not checked)
        self.sp_halo_b.setEnabled(not checked)
        self.sp_halo_t.setEnabled(not checked)
        if checked:
            v = self.sp_halo_l.value()
            self.sp_halo_r.setValue(v)
            self.sp_halo_b.setValue(v)
            self.sp_halo_t.setValue(v)
        self.on_halo_changed()

    def on_halo_changed(self):
        if self.chk_equal_halo.isChecked():
            v = self.sp_halo_l.value()
            self.sp_halo_r.blockSignals(True)
            self.sp_halo_b.blockSignals(True)
            self.sp_halo_t.blockSignals(True)
            self.sp_halo_r.setValue(v)
            self.sp_halo_b.setValue(v)
            self.sp_halo_t.setValue(v)
            self.sp_halo_r.blockSignals(False)
            self.sp_halo_b.blockSignals(False)
            self.sp_halo_t.blockSignals(False)
        
        items = self.scene.selectedItems()
        if items and (isinstance(items[0], MacroItem) or isinstance(items[0], BlockageItem) or isinstance(items[0], RegionItem)):
            l = self.sp_halo_l.value()
            r = self.sp_halo_r.value()
            b = self.sp_halo_b.value()
            t = self.sp_halo_t.value()
            items[0].update_halo(l, r, b, t)
            self.save_state()

    def start_drawing_blockage(self):
        self.view.start_drawing(self.cmb_block_type.currentText(), self.sp_block_pct.value())

    def start_drag(self, supportedActions):
        item = self.macro_list.currentItem()
        if not item or not (item.flags() & Qt.ItemFlag.ItemIsEnabled): return
        drag = QDrag(self.macro_list)
        mimeData = QMimeData()
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            mimeData.setText(data)
        else:
            mimeData.setText(item.text().replace(" [PLACED]", ""))
        
        drag.setMimeData(mimeData)
        drag.exec(supportedActions)

    def populate_macro_list(self, cfg):
        self.macro_list.clear()
        
        self.macro_sizes = {}
        requested_macros = set()
        if cfg and 'macros' in cfg:
            requested_macros.update(cfg['macros'])
            
        proj_root = self.parent().ide.get_proj_root(self.parent().ide.get_context()[0] or "design")
        base = self.parent().ide.get_context()[1]
        sizes_json_path = os.path.join(proj_root, "reports", f"{base}_sizes.json").replace("\\", "/")
        
        if os.path.exists(sizes_json_path):
            try:
                import json
                with open(sizes_json_path, 'r') as f:
                    sizes_data = json.load(f)
                
                self.macro_instances = {}
                if 'macros' in sizes_data:
                    for inst_name, master_name in sizes_data['macros'].items():
                        requested_macros.add(master_name)
                        self.macro_instances[inst_name] = master_name
                
                self.total_std_cell_area = sizes_data.get('total_std_cell_area', 0.0)
                self.module_areas = sizes_data.get('modules', {})
                self.cmb_region_module.clear()
                self.cmb_region_module.addItems(list(self.module_areas.keys()))
            except Exception as e:
                print("Floorplanner: Error reading sizes json:", e)
        
        # Now find sizes in LEFs
        try:
            pdk_name = self.project_config.get('pdk', '')
            pdk_cfg = next((c for c in self.pdk_mgr.configs if c['name'] == pdk_name), None)
            if pdk_cfg:
                lib_path = pdk_cfg.get('lib', '')
                if "libs.ref" in lib_path:
                    volare_base = lib_path.split("libs.ref")[0]
                    search_path = os.path.join(volare_base, "libs.ref", "*", "lef", "*.lef")
                    import glob, re
                    for lef in glob.glob(search_path):
                        name = os.path.basename(lef).replace('.lef', '')
                        if name in requested_macros:
                            with open(lef, 'r') as f:
                                m = re.search(r'SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)', f.read())
                                if m:
                                    self.macro_sizes[name] = (float(m.group(1)), float(m.group(2)))
                                    print(f"Floorplanner: Found LEF size for {name} -> {self.macro_sizes[name]}")
        except Exception as e:
            print("Floorplanner: Error parsing LEF sizes:", e)
            
        # Add to list widget only the actual instances
        if hasattr(self, 'macro_instances'):
            for inst_name, master_name in self.macro_instances.items():
                item_text = f"[{inst_name}] ({master_name})"
                item = QListWidgetItem(item_text)
                # Store the instance name and master name so start_drag can use it
                item.setData(Qt.ItemDataRole.UserRole, f"{master_name}|{inst_name}")
                self.macro_list.addItem(item)
            
    def update_utilization(self):
        if self.core_rect:
            cw, ch = self.core_rect.width(), self.core_rect.height()
            core_area = cw * ch
            if core_area > 0 and hasattr(self, 'total_std_cell_area'):
                util = (self.total_std_cell_area / core_area) * 100
                self.lbl_core_util.setText(f"Core Utilization: {util:.2f}%")
        
        items = self.scene.selectedItems()
        if items and isinstance(items[0], RegionItem):
            reg = items[0]
            if hasattr(self, 'module_areas'):
                mod_area = self.module_areas.get(reg.module_name, 0)
                reg_area = reg.rect().width() * reg.rect().height()
                if reg_area > 0:
                    util = (mod_area / reg_area) * 100
                    self.lbl_region_util.setText(f"Region Utilization: {util:.2f}%")
                else:
                    self.lbl_region_util.setText("Region Utilization: -")
        else:
            self.lbl_region_util.setText("Region Utilization: -")

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
                    
                    orient_def = parser.comp_orients.get(inst_name, "N")
                    def_to_ord = {"N": "R0", "W": "R90", "S": "R180", "E": "R270", "FN": "MY", "FS": "MX", "FW": "MX90", "FE": "MY90"}
                    orient_ord = def_to_ord.get(orient_def, "R0")
                    
                    # DEFParser swaps w/h in its bb_rect for W/E/FW/FE, so un-swap for base size
                    if orient_def in ["W", "E", "FW", "FE"]:
                        w, h = h, w
                        
                    m_item = MacroItem(master_name, w, h, self.core_rect, self)
                    m_item.set_inst_name(inst_name)
                    m_item.set_orientation(orient_ord)
                    
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
        
        self.save_state()
        self.fit_die()

    def fit_die(self):
        if hasattr(self, 'die_rect') and self.die_rect:
            self.view.fitInView(self.die_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def undo(self):
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            self.load_state(self.undo_stack[-1])

    def redo(self):
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.undo_stack.append(state)
            self.load_state(state)

    def load_state(self, state):
        self.is_undoing = True
        self.scene.clear()
        
        die_item = self.scene.addRect(self.die_rect, QPen(QColor("#A0AEC0"), 2), QBrush(Qt.BrushStyle.NoBrush))
        die_item.setZValue(-10)
        core_item = self.scene.addRect(self.core_rect, QPen(QColor("#4A5568"), 1, Qt.PenStyle.DashLine), QBrush(Qt.BrushStyle.NoBrush))
        core_item.setZValue(-9)

        for i in range(self.macro_list.count()):
            it = self.macro_list.item(i)
            it.setText(it.text().replace(" [PLACED]", ""))
            it.setForeground(QBrush(QColor("white")))

        for b in state['blockages']:
            if b.get('is_region'):
                r_item = RegionItem(b['x'], b['y'], b['w'], b['h'], b['module_name'], b['is_fence'])
                self.scene.addItem(r_item)
            else:
                b_item = BlockageItem(b['x'], b['y'], b['w'], b['h'], b['btype'], b['pct'])
                self.scene.addItem(b_item)
            
        for m in state['macros']:
            w, h = self.macro_sizes.get(m['name'], (100.0, 100.0))
            m_item = MacroItem(m['name'], w, h, self.core_rect, self)
            m_item.set_inst_name(m['inst_name'])
            m_item.set_orientation(m['orientation'])
            m_item.update_halo(*m['halo'])
            m_item.setPos(m['x'], m['y'])
            self.scene.addItem(m_item)
            
            if m['list_text']:
                for i in range(self.macro_list.count()):
                    it = self.macro_list.item(i)
                    base_text = it.text().replace(" [PLACED]", "")
                    if base_text == m['list_text'].replace(" [PLACED]", ""):
                        it.setText(f"{base_text} [PLACED]")
                        it.setForeground(QBrush(QColor("#4CAF50")))
                        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                        m_item.list_item = it
                        break
        self.is_undoing = False

    def save_state(self):
        if self.is_undoing or not self.floorplan_initialized: return
        state = {'macros': [], 'blockages': []}
        for item in self.scene.items():
            if isinstance(item, MacroItem):
                state['macros'].append({
                    'name': item.name, 'inst_name': item.inst_name,
                    'x': item.pos().x(), 'y': item.pos().y(),
                    'orientation': item.orientation, 'halo': item.halo,
                    'list_text': item.list_item.text() if item.list_item else None
                })
            elif isinstance(item, BlockageItem):
                state['blockages'].append({
                    'x': item.rect().x(), 'y': item.rect().y(),
                    'w': item.rect().width(), 'h': item.rect().height(),
                    'btype': item.btype, 'pct': item.pct
                })
            elif isinstance(item, RegionItem):
                state['blockages'].append({
                    'is_region': True,
                    'x': item.rect().x(), 'y': item.rect().y(),
                    'w': item.rect().width(), 'h': item.rect().height(),
                    'module_name': item.module_name, 'is_fence': item.is_fence
                })
        import json
        if self.undo_stack:
            last = json.dumps(self.undo_stack[-1], sort_keys=True)
            curr = json.dumps(state, sort_keys=True)
            if last == curr: return
        self.undo_stack.append(state)
        self.redo_stack.clear()

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
            it_data = it.data(Qt.ItemDataRole.UserRole)
            if (inst_name and it_data == f"{name}|{inst_name}") or (not inst_name and (it.text() == name or it.text() == f"{name} [PLACED]")):
                base_text = it.text().replace(" [PLACED]", "")
                it.setText(f"{base_text} [PLACED]")
                it.setForeground(QBrush(QColor("#4CAF50")))
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                m_item.list_item = it
                break

        self.save_state()

    def on_inst_name_changed(self):
        items = self.scene.selectedItems()
        if items and isinstance(items[0], MacroItem):
            items[0].set_inst_name(self.txt_inst_name.text())
            self.scene.update()
            self.save_state()

    def on_orientation_changed(self, text):
        items = self.scene.selectedItems()
        if items and isinstance(items[0], MacroItem):
            items[0].set_orientation(text)
            self.save_state()

    def on_spinbox_changed(self):
        items = self.scene.selectedItems()
        if items and isinstance(items[0], MacroItem):
            items[0].setPos(self.sp_sel_x.value(), self.sp_sel_y.value())
            self.save_state()

    def on_selection_changed(self):
        try:
            self.update_utilization()
            items = self.scene.selectedItems()
            if items and (isinstance(items[0], MacroItem) or isinstance(items[0], BlockageItem) or isinstance(items[0], RegionItem)):
                m = items[0]
                if isinstance(m, MacroItem):
                    self.lbl_sel_name.setText(m.name)
                elif isinstance(m, BlockageItem):
                    self.lbl_sel_name.setText(f"Blockage ({m.btype})")
                elif isinstance(m, RegionItem):
                    self.lbl_sel_name.setText(f"Region ({m.module_name})")
                
                self.sp_sel_x.blockSignals(True)
                self.sp_sel_y.blockSignals(True)
                self.txt_inst_name.blockSignals(True)
                self.cmb_orientation.blockSignals(True)
                
                self.sp_halo_l.blockSignals(True)
                self.sp_halo_r.blockSignals(True)
                self.sp_halo_b.blockSignals(True)
                self.sp_halo_t.blockSignals(True)
                self.chk_equal_halo.blockSignals(True)

                if isinstance(m, MacroItem):
                    self.sp_sel_x.setValue(m.pos().x())
                    self.sp_sel_y.setValue(m.pos().y())
                    self.txt_inst_name.setText(m.inst_name)
                    self.cmb_orientation.setCurrentText(m.orientation)
                else:
                    self.sp_sel_x.setValue(m.rect().x())
                    self.sp_sel_y.setValue(m.rect().y())
                
                l, r, b, t = m.halo
                self.sp_halo_l.setValue(l)
                self.sp_halo_r.setValue(r)
                self.sp_halo_b.setValue(b)
                self.sp_halo_t.setValue(t)
                is_eq = (l == r == b == t)
                self.chk_equal_halo.setChecked(is_eq)
                self.sp_halo_r.setEnabled(not is_eq)
                self.sp_halo_b.setEnabled(not is_eq)
                self.sp_halo_t.setEnabled(not is_eq)

                self.sp_sel_x.blockSignals(False)
                self.sp_sel_y.blockSignals(False)
                self.txt_inst_name.blockSignals(False)
                self.cmb_orientation.blockSignals(False)
                
                self.sp_halo_l.blockSignals(False)
                self.sp_halo_r.blockSignals(False)
                self.sp_halo_b.blockSignals(False)
                self.sp_halo_t.blockSignals(False)
                self.chk_equal_halo.blockSignals(False)
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
                
                ox = item.pos().x()
                oy = item.pos().y()
                if item.orientation in ["R90", "MX90"]:
                    ox += item.h
                elif item.orientation == "R180":
                    ox += item.w
                    oy += item.h
                elif item.orientation in ["R270", "MY90"]:
                    oy += item.w
                elif item.orientation == "MX":
                    oy += item.h
                elif item.orientation == "MY":
                    ox += item.w
                    
                tcl += f"  place_inst -name {{{item.inst_name}}} -cell {{{item.name}}} -origin {{{ox} {oy}}} -status FIRM -orientation {item.orientation}\n"
                tcl += f"}}\n"
                if any(x > 0 for x in item.halo):
                    l, r, b, t = item.halo
                    bx1 = max(0, (item.rect().x() + item.pos().x()) - l)
                    by1 = max(0, (item.rect().y() + item.pos().y()) - b)
                    bx2 = min(die_w, (item.rect().x() + item.pos().x()) + item.rect().width() + r)
                    by2 = min(die_h, (item.rect().y() + item.pos().y()) + item.rect().height() + t)
                    tcl += f"catch {{ create_blockage -region {{{bx1} {by1} {bx2} {by2}}} }}\n"
            elif isinstance(item, BlockageItem):
                x1 = item.rect().x() + item.pos().x()
                y1 = item.rect().y() + item.pos().y()
                x2 = x1 + item.rect().width()
                y2 = y1 + item.rect().height()
                tcl += f"catch {{\n"
                if item.btype == "Partial":
                    tcl += f"  create_blockage -region {{{x1} {y1} {x2} {y2}}} -max_density {item.pct}\n"
                elif item.btype == "Soft":
                    tcl += f"  create_blockage -region {{{x1} {y1} {x2} {y2}}} -soft\n"
                else:
                    tcl += f"  create_blockage -region {{{x1} {y1} {x2} {y2}}}\n"
                tcl += f"}}\n"
                if any(x > 0 for x in item.halo):
                    l, r, b, t = item.halo
                    bx1 = max(0, (item.rect().x() + item.pos().x()) - l)
                    by1 = max(0, (item.rect().y() + item.pos().y()) - b)
                    bx2 = min(die_w, (item.rect().x() + item.pos().x()) + item.rect().width() + r)
                    by2 = min(die_h, (item.rect().y() + item.pos().y()) + item.rect().height() + t)
                    tcl += f"catch {{ create_blockage -region {{{bx1} {by1} {bx2} {by2}}} }}\n"
            elif isinstance(item, RegionItem):
                x1 = item.rect().x() + item.pos().x()
                y1 = item.rect().y() + item.pos().y()
                x2 = x1 + item.rect().width()
                y2 = y1 + item.rect().height()
                reg_name = f"region_{item.module_name.replace('/', '_')}"
                rtype = "EXCLUSIVE" if item.is_fence else "INCLUSIVE"
                x1_dbu = int(x1 * 1000)
                y1_dbu = int(y1 * 1000)
                x2_dbu = int(x2 * 1000)
                y2_dbu = int(y2 * 1000)
                # Use brace-quoting throughout — never backslash-escaped quotes through stdin pipe
                tcl += f"catch {{\n"
                tcl += f"  set r [odb::dbRegion_create [::ord::get_db_block] {{{reg_name}}}]\n"
                tcl += f"  $r setRegionType {{{rtype}}}\n"
                # dbBox_create isolated — if this build's SWIG crashes on it, addInst still runs
                tcl += f"  catch {{ odb::dbBox_create $r {x1_dbu} {y1_dbu} {x2_dbu} {y2_dbu} }}\n"
                tcl += f"  foreach inst [[::ord::get_db_block] getInsts] {{\n"
                tcl += f"    if {{ [string match {{{item.module_name}/*}} [$inst getName]] || [$inst getName] eq {{{item.module_name}}} }} {{\n"
                tcl += f"      $r addInst $inst\n"
                tcl += f"    }}\n"
                tcl += f"  }}\n"
                tcl += f"}}\n"
                if any(x > 0 for x in item.halo):
                    l, r, b, t = item.halo
                    rx1 = item.rect().x() + item.pos().x()
                    ry1 = item.rect().y() + item.pos().y()
                    rx2 = rx1 + item.rect().width()
                    ry2 = ry1 + item.rect().height()
                    
                    if l > 0:
                        tcl += f"catch {{ create_blockage -region {{{max(0, rx1-l)} {max(0, ry1-b)} {rx1} {min(die_h, ry2+t)}}} }}\n"
                    if r > 0:
                        tcl += f"catch {{ create_blockage -region {{{rx2} {max(0, ry1-b)} {min(die_w, rx2+r)} {min(die_h, ry2+t)}}} }}\n"
                    if b > 0:
                        tcl += f"catch {{ create_blockage -region {{{max(0, rx1)} {max(0, ry1-b)} {min(die_w, rx2)} {ry1}}} }}\n"
                    if t > 0:
                        tcl += f"catch {{ create_blockage -region {{{max(0, rx1)} {ry2} {min(die_w, rx2)} {min(die_h, ry2+t)}}} }}\n"
        
        proj_root = self.parent().ide.get_proj_root(self.parent().ide.get_context()[0] or "design")
        def_abs_path = os.path.join(proj_root, "results", "temp.def").replace("\\", "/")
        tcl += f"\nwrite_def \"{def_abs_path}\""
        
        self.parent().term_log.append("[SYS] Applying Custom Floorplan...")
        self.parent().send_command_internal(tcl)
        self.accept()
