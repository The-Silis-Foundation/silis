import os
import re
import json
import glob
import math
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
        self.setZValue(100)
        
        if pos_type in ['tl', 'br']: self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif pos_type in ['tr', 'bl']: self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif pos_type in ['tc', 'bc']: self.setCursor(Qt.CursorShape.SizeVerCursor)
        else: self.setCursor(Qt.CursorShape.SizeHorCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if hasattr(self.parentItem(), "handle_moved"):
                self.parentItem().handle_moved(self.pos_type, value)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if self.parentItem() and (self.parentItem().flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable):
            self.parentItem().setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            self.parent_was_movable = True
        else:
            self.parent_was_movable = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if hasattr(self, 'parent_was_movable') and self.parent_was_movable and self.parentItem():
            self.parentItem().setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        s = self.scene()
        if s and s.views():
            v = s.views()[0]
            if hasattr(v, 'parent') and v.parent():
                p = v.parent()
                if hasattr(p, 'save_state'): p.save_state()
                if hasattr(p, 'update_live_tcl'): p.update_live_tcl()

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
        if change in (QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged, QGraphicsItem.GraphicsItemChange.ItemSelectedChange):
            selected = bool(value)
            for h in self.handles.values():
                h.setVisible(selected)
        return super().itemChange(change, value)

class BlockageItem(ResizableRectItem):
    def __init__(self, x, y, w, h, btype, pct, core_rect=None, parent=None):
        super().__init__(x, y, w, h, parent)
        self.btype = btype
        self.pct = pct
        self.core_rect = core_rect
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        if self.btype == "Hard":
            color = QColor(243, 139, 168, 60) # Catppuccin Red (soft transparent)
            pen_color = QColor("#f38ba8")
        elif self.btype == "Soft":
            color = QColor(137, 180, 250, 60) # Catppuccin Blue (soft transparent)
            pen_color = QColor("#89b4fa")
        else: # Partial
            color = QColor(166, 227, 161, 60) # Catppuccin Green (soft transparent)
            pen_color = QColor("#a6e3a1")
            
        self.setBrush(QBrush(color)) 
        self.setPen(QPen(pen_color, 1.5, Qt.PenStyle.DashLine))
        
        self.halo = (0, 0, 0, 0)
        self.halo_rect = QGraphicsRectItem(self)
        self.halo_rect.setPen(QPen(QColor("#6c7086"), 1, Qt.PenStyle.DotLine))
        self.halo_rect.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        
        self.text = QGraphicsTextItem("", self)
        self.text.setDefaultTextColor(QColor("#cdd6f4"))
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
    def __init__(self, x, y, w, h, module_name, is_fence=False, density=0.60, core_rect=None, parent=None):
        super().__init__(x, y, w, h, parent)
        self.module_name = module_name
        self.is_fence = is_fence
        self.density = density
        self.core_rect = core_rect
        self.locked = False
        self.starved = False
        self.multi_boxes = []
        self.halo = (0, 0, 0, 0)
        self.halo_type = "Routing halo"
        self.halo_rect = QGraphicsRectItem(self)
        self.halo_rect.setPen(QPen(QColor("#6c7086"), 1, Qt.PenStyle.DotLine))
        self.halo_rect.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        
        self._update_colors()
        
        self.text = QGraphicsTextItem("", self)
        self.text.setDefaultTextColor(QColor("#cdd6f4"))
        self.text.setTransform(QTransform.fromScale(1, -1))
        self.update_text()

    def _update_colors(self):
        if self.starved:
            # Highlight border red for starved regions
            pen_color = QColor("#f38ba8")  # Catppuccin Red
            color = QColor(243, 139, 168, 80)
            pen_style = Qt.PenStyle.DashLine
        elif self.locked:
            # Highlight locked regions in blue
            pen_color = QColor("#89b4fa")  # Catppuccin Blue
            color = QColor(137, 180, 250, 70)
            pen_style = Qt.PenStyle.SolidLine
        else:
            color = QColor(250, 179, 135, 60) if self.is_fence else QColor(249, 226, 175, 60) # Catppuccin Peach / Yellow
            pen_color = QColor("#fab387") if self.is_fence else QColor("#f9e2af")
            pen_style = Qt.PenStyle.SolidLine
        self.setBrush(QBrush(color))
        self.setPen(QPen(pen_color, 1.8 if (self.starved or self.locked) else 1.5, pen_style))

    def set_locked(self, locked: bool):
        self.locked = locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)
        self._update_colors()
        self.update_text()

    def set_starved(self, starved: bool):
        self.starved = starved
        self._update_colors()
        self.update_text()
        
    def update_text(self):
        t = "FENCE" if self.is_fence else "REGION"
        d = int(self.density * 100)
        lock_tag = " [LOCKED]" if self.locked else ""
        starve_tag = " [OVERFLOW]" if self.starved else ""
        shape_tag = " (L-Shape)" if len(self.multi_boxes) == 2 else (" (Multi-Box)" if len(self.multi_boxes) > 2 else "")
        self.text.setPlainText(f"{t}: {self.module_name}{shape_tag}{lock_tag}{starve_tag}\n{d}% Density")
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
            x = round(new_pos.x(), 3)
            y = round(new_pos.y(), 3)
            
            if hasattr(self, 'core_rect') and self.core_rect:
                w = self.rect().width()
                h = self.rect().height()
                min_x = self.core_rect.x() - self.rect().x()
                min_y = self.core_rect.y() - self.rect().y()
                max_x = self.core_rect.x() + self.core_rect.width() - self.rect().x() - w
                max_y = self.core_rect.y() + self.core_rect.height() - self.rect().y() - h
                if x < min_x: x = min_x
                if y < min_y: y = min_y
                if x > max_x: x = max_x
                if y > max_y: y = max_y
                
            new_pos.setX(x)
            new_pos.setY(y)
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

    def start_drawing_region(self, module_name, is_fence, density):
        self.drawing_region = True
        self.drawing_blockage = False
        self.region_module = module_name
        self.region_is_fence = is_fence
        self.region_density = density
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self.pan_active = True
            self.pan_start_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if self.drawing_blockage and event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.pos())
            self.blockage_start_pos = pos
            cr = getattr(self.parentWidget(), "core_rect", None)
            self.current_blockage = BlockageItem(pos.x(), pos.y(), 0, 0, self.btype, self.pct, cr)
            self.scene().addItem(self.current_blockage)
            return
            
        if self.drawing_region and event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.pos())
            self.region_start_pos = pos
            cr = getattr(self.parentWidget(), "core_rect", None)
            self.current_region = RegionItem(pos.x(), pos.y(), 0, 0, self.region_module, self.region_is_fence, self.region_density, cr)
            parent_w = self.parentWidget()
            if parent_w and hasattr(parent_w, "sp_common_region_halo"):
                h_val = parent_w.sp_common_region_halo.value()
                self.current_region.update_halo(h_val, h_val, h_val, h_val)
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
            
            if hasattr(self.parentWidget(), "core_rect") and self.parentWidget().core_rect:
                cr = self.parentWidget().core_rect
                if px < cr.x(): px = cr.x()
                if py < cr.y(): py = cr.y()
                if px > cr.x() + cr.width(): px = cr.x() + cr.width()
                if py > cr.y() + cr.height(): py = cr.y() + cr.height()
                
            x1 = min(px, self.blockage_start_pos.x())
            y1 = min(py, self.blockage_start_pos.y())
            w = abs(px - self.blockage_start_pos.x())
            h = abs(py - self.blockage_start_pos.y())
            self.current_blockage.setRect(x1, y1, w, h)
            if hasattr(self.parentWidget(), "update_utilization"):
                self.parentWidget().update_utilization()
            return
            
        if self.drawing_region and self.current_region:
            pos = self.mapToScene(event.pos())
            px, py = round(pos.x(), 3), round(pos.y(), 3)
            
            if hasattr(self.parentWidget(), "core_rect") and self.parentWidget().core_rect:
                cr = self.parentWidget().core_rect
                if px < cr.x(): px = cr.x()
                if py < cr.y(): py = cr.y()
                if px > cr.x() + cr.width(): px = cr.x() + cr.width()
                if py > cr.y() + cr.height(): py = cr.y() + cr.height()
                
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
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
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
                        item.list_item.setForeground(QBrush())
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
        self.setBrush(QBrush(QColor("#313244")))
        self.setPen(QPen(QColor("#89b4fa"), 1.5))
        
        self.halo_rect = QGraphicsRectItem(self)
        self.halo_rect.setPen(QPen(QColor("#f38ba8"), 1.5, Qt.PenStyle.DashLine))
        self.halo_rect.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        
        self.text = QGraphicsTextItem(f"{self.inst_name}\n({name})", self)
        self.text.setDefaultTextColor(QColor("#cdd6f4"))
        self.text.setTransform(QTransform.fromScale(1, -1))
        # Center text
        br = self.text.boundingRect()
        self.text.setPos(width/2 - br.width()/2, height/2 + br.height()/2)
        
        self.pin_items = []
        if hasattr(widget_ref, 'macro_pins') and name in widget_ref.macro_pins:
            for pin in widget_ref.macro_pins[name]:
                px1, py1, px2, py2 = pin["rect"]
                pw, ph = px2 - px1, py2 - py1
                p_item = QGraphicsRectItem(px1, py1, pw, ph, self)
                p_item.setBrush(QBrush(Qt.GlobalColor.red))
                p_item.setPen(QPen(Qt.GlobalColor.black, 0))
                p_item.setToolTip(pin["name"])
                
                t_item = QGraphicsTextItem(pin["name"], self)
                t_item.setDefaultTextColor(Qt.GlobalColor.cyan)
                f = t_item.font()
                f.setPixelSize(2) # Very small text for pins
                t_item.setFont(f)
                t_item.setTransform(QTransform.fromScale(1, -1))
                
                self.pin_items.append({"item": p_item, "text": t_item, "rect": (px1, py1, pw, ph)})

    def update_halo(self, l, r, b, t):
        self.halo = (l, r, b, t)
        if self.orientation in ["R90", "R270", "MX90", "MY90", "MXR90", "MYR90"]:
            self.halo_rect.setRect(-l, -b, self.h + l + r, self.w + b + t)
        else:
            self.halo_rect.setRect(-l, -b, self.w + l + r, self.h + b + t)

    def set_orientation(self, orient):
        orient = "MYR90" if orient == "MY90" else ("MXR90" if orient == "MX90" else orient)
        swapped = ["R90", "R270", "MX90", "MY90", "MXR90", "MYR90"]
        old_is_swapped = self.orientation in swapped
        self.orientation = orient
        new_is_swapped = orient in swapped
        
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
        
        mw, mh = self.w, self.h
        for p in getattr(self, 'pin_items', []):
            px1, py1, pw, ph = p["rect"]
            nx, ny, nw, nh = px1, py1, pw, ph
            if orient == "R90": nx, ny, nw, nh = mh - (py1 + ph), px1, ph, pw
            elif orient == "R180": nx, ny, nw, nh = mw - (px1 + pw), mh - (py1 + ph), pw, ph
            elif orient == "R270": nx, ny, nw, nh = py1, mw - (px1 + pw), ph, pw
            elif orient == "MY": nx, ny, nw, nh = mw - (px1 + pw), py1, pw, ph
            elif orient == "MX": nx, ny, nw, nh = px1, mh - (py1 + ph), pw, ph
            elif orient in ["MX90", "MXR90"]: nx, ny, nw, nh = mh - (py1 + ph), mw - (px1 + pw), ph, pw
            elif orient in ["MY90", "MYR90"]: nx, ny, nw, nh = py1, px1, ph, pw
            p["item"].setRect(nx, ny, nw, nh)
            
            t_item = p["text"]
            br = t_item.boundingRect()
            
            # Determine edge
            actual_h = mw if orient in swapped else mh
            pin_cy = ny + nh / 2.0
            
            if pin_cy < actual_h * 0.1: # Bottom edge
                t_item.setTransform(QTransform().scale(1, -1).rotate(-90))
                t_item.setPos(nx + nw/2 + br.height()/4, ny + nh)
            elif pin_cy > actual_h * 0.9: # Top edge
                t_item.setTransform(QTransform().scale(1, -1).rotate(90))
                t_item.setPos(nx + nw/2 - br.height()/4, ny)
            else:
                t_item.setTransform(QTransform().scale(1, -1))
                t_item.setPos(nx + nw/2 - br.width()/2, ny + nh/2 + br.height()/2)
        
        br = self.text.boundingRect()
        self.text.setPos(self.rect().width()/2 - br.width()/2, self.rect().height()/2 + br.height()/2)
        # Trigger re-clamp
        self.setPos(self.itemChange(QGraphicsItem.GraphicsItemChange.ItemPositionChange, self.pos()))
        if getattr(self, 'widget_ref', None):
            self.widget_ref.update_live_tcl()

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
            
            swapped = ["R90", "R270", "MX90", "MY90", "MXR90", "MYR90"]
            w = self.h if self.orientation in swapped else self.w
            h = self.w if self.orientation in swapped else self.h
            if self.core_rect:
                max_x = self.core_rect.width() - w
                max_y = self.core_rect.height() - h
                if x < self.core_rect.x(): x = self.core_rect.x()
                if y < self.core_rect.y(): y = self.core_rect.y()
                if x > self.core_rect.x() + max_x: x = self.core_rect.x() + max_x
                if y > self.core_rect.y() + max_y: y = self.core_rect.y() + max_y
            
            if self.isSelected() and getattr(self, 'widget_ref', None):
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
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if getattr(self, 'widget_ref', None):
                self.widget_ref.update_live_tcl()
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if getattr(self, 'widget_ref', None):
            self.widget_ref.update_live_tcl()
            self.widget_ref.save_state()


class InteractiveFloorplannerWidget(QDialog):
    def _get_project_context(self):
        """Safely returns (proj_root, top_module_base) whether invoked inside GUI or standalone/CLI."""
        proj_root = ""
        base = ""
        try:
            p = self.parent()
            if p and hasattr(p, 'ide') and p.ide:
                ctx = p.ide.get_context()
                proj_root = p.ide.get_proj_root(ctx[0] or "design")
                base = ctx[1]
        except Exception:
            pass
        if not proj_root and self.project_config:
            proj_root = self.project_config.get("project_path") or self.project_config.get("root_path")
            if not proj_root:
                for k in ["rtl_files", "sdc_files", "tb_files"]:
                    if self.project_config.get(k) and len(self.project_config[k]) > 0:
                        first_f = self.project_config[k][0]
                        if os.path.isabs(first_f):
                            parent_dir = os.path.dirname(first_f)
                            if os.path.basename(parent_dir) in ["source", "src", "rtl"]:
                                proj_root = os.path.dirname(parent_dir)
                            else:
                                proj_root = parent_dir
                            break
            base = self.project_config.get("top_module") or self.project_config.get("project_name") or "top"
        if not proj_root:
            proj_root = os.getcwd()
        if not base:
            base = "design"
        return proj_root, base

    def __init__(self, project_config, pdk_mgr, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Floorplanner")
        self.resize(1400, 900)
        self.setWindowTitle("Interactive Floorplanner")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
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
        left_widget.setMaximumWidth(320)
        left_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left_widget)
        gb_die = QGroupBox("Die & Core Specifications")
        fl_die = QFormLayout(gb_die)
        self.sp_die_w = QDoubleSpinBox(); self.sp_die_w.setRange(0.1, 100000); self.sp_die_w.setValue(5000)
        self.sp_die_h = QDoubleSpinBox(); self.sp_die_h.setRange(0.1, 100000); self.sp_die_h.setValue(5000)
        self.sp_marg_t = QDoubleSpinBox(); self.sp_marg_t.setRange(0, 10000); self.sp_marg_t.setValue(20)
        self.sp_marg_b = QDoubleSpinBox(); self.sp_marg_b.setRange(0, 10000); self.sp_marg_b.setValue(20)
        self.sp_marg_l = QDoubleSpinBox(); self.sp_marg_l.setRange(0, 10000); self.sp_marg_l.setValue(20)
        self.sp_marg_r = QDoubleSpinBox(); self.sp_marg_r.setRange(0, 10000); self.sp_marg_r.setValue(20)

        self._user_custom_dimensions = False
        def _mark_user_dims(*_):
            self._user_custom_dimensions = True
        self.sp_die_w.valueChanged.connect(_mark_user_dims)
        self.sp_die_h.valueChanged.connect(_mark_user_dims)
        self.sp_marg_t.valueChanged.connect(_mark_user_dims)
        self.sp_marg_b.valueChanged.connect(_mark_user_dims)
        self.sp_marg_l.valueChanged.connect(_mark_user_dims)
        self.sp_marg_r.valueChanged.connect(_mark_user_dims)
        fl_die.addRow("Die Width (µm):", self.sp_die_w)
        fl_die.addRow("Die Height (µm):", self.sp_die_h)
        fl_die.addRow("Margin Top (µm):", self.sp_marg_t)
        fl_die.addRow("Margin Bottom (µm):", self.sp_marg_b)
        fl_die.addRow("Margin Left (µm):", self.sp_marg_l)
        fl_die.addRow("Margin Right (µm):", self.sp_marg_r)
        
        self.lbl_core_util = QLabel("Core Utilization: -")
        fl_die.addRow(self.lbl_core_util)
        
        self.sp_target_core_density = QDoubleSpinBox()
        self.sp_target_core_density.setRange(10.0, 95.0)
        self.sp_target_core_density.setValue(60.0)
        self.sp_target_core_density.setSuffix("%")
        self.sp_target_core_density.valueChanged.connect(self.update_utilization)
        fl_die.addRow("Target Core Density:", self.sp_target_core_density)
        
        self.btn_fit_core_density = QPushButton("Fit Core to Target Density")
        self.btn_fit_core_density.setStyleSheet("background: #313244; color: #cdd6f4; font-size: 11px;")
        self.btn_fit_core_density.clicked.connect(self.on_fit_core_to_density_clicked)
        fl_die.addRow(self.btn_fit_core_density)

        self.btn_init = QPushButton("Initialize Floorplan")
        self.btn_init.setStyleSheet("background: #0078D7; color: white; font-weight: bold;")
        self.btn_init.clicked.connect(self.init_floorplan)
        fl_die.addRow(self.btn_init)
        left_layout.addWidget(gb_die)
        
        # Selected Macro / Region
        gb_sel = QGroupBox("Selected Macro / Region")
        fl_sel = QFormLayout(gb_sel)
        self.lbl_sel_name = QLabel("None")
        self.lbl_sel_name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        self.txt_inst_name = QLineEdit()
        self.txt_inst_name.setPlaceholderText("Netlist Instance Name")
        self.txt_inst_name.setMaximumWidth(200)
        self.txt_inst_name.editingFinished.connect(self.on_inst_name_changed)
        
        self.sp_sel_x = QDoubleSpinBox(); self.sp_sel_x.setRange(0, 100000)
        self.sp_sel_y = QDoubleSpinBox(); self.sp_sel_y.setRange(0, 100000)
        self.cmb_orientation = QComboBox()
        self.cmb_orientation.addItems(["R0", "R90", "R180", "R270", "MX", "MY", "MXR90", "MYR90"])
        self.sp_sel_density = QDoubleSpinBox()
        self.sp_sel_density.setRange(0.0, 1.0)
        self.sp_sel_density.setSingleStep(0.05)
        self.sp_sel_density.valueChanged.connect(self.on_sel_density_changed)
        self.btn_convert_type = QPushButton("Convert Type")
        self.btn_convert_type.setStyleSheet("font-size: 11px; background: #45475a; color: #cdd6f4;")
        self.btn_convert_type.setToolTip("Toggle selected region between Fence (exclusive) and Region (inclusive)")
        self.btn_convert_type.clicked.connect(self.on_convert_region_type_clicked)
        self.btn_convert_type.setEnabled(False)

        fl_sel.addRow("Macro:", self.lbl_sel_name)
        fl_sel.addRow("Density:", self.sp_sel_density)
        fl_sel.addRow("Type:", self.btn_convert_type)
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

        # Auto Place Macros Checkbox & Methodology Selector
        fl_sel.addRow(QLabel("<hr style='border: 1px solid #333;'>"))
        self.chk_autoplace = QCheckBox("Auto Place Macros")
        self.chk_autoplace.setStyleSheet("font-weight: bold; color: #58a6ff;")
        self.cmb_autoplace_method = QComboBox()
        self.cmb_autoplace_method.addItems([
            "Peripheral (Silis Fast)",
            "Hierarchical (OpenROAD RTL-MP)",
            "Analytical (TritonMacroPlace)"
        ])
        self.cmb_autoplace_method.setEnabled(False)
        self.chk_autoplace.toggled.connect(self.on_autoplace_toggled)
        self.cmb_autoplace_method.currentIndexChanged.connect(self.on_autoplace_method_changed)
        
        fl_sel.addRow(self.chk_autoplace)
        fl_sel.addRow("Methodology:", self.cmb_autoplace_method)

        left_layout.addWidget(gb_sel)
        
        btn_tcl = QPushButton("Apply Floorplan & Run")
        btn_tcl.setStyleSheet("background: #0078D7; color: white; font-weight: bold;")
        btn_tcl.clicked.connect(lambda: self.generate_floorplan_tcl(apply=True))
        left_layout.addWidget(btn_tcl)
        
        btn_fit = QPushButton("Fit Die in View")
        btn_fit.clicked.connect(self.fit_die)
        left_layout.addWidget(btn_fit)
        
        left_layout.addStretch()
        
        left_tabs = QTabWidget()
        left_tabs.setMaximumWidth(340)
        left_tabs.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        left_tabs.addTab(left_widget, "Controls")
        self.live_tcl_edit = QPlainTextEdit()
        self.live_tcl_edit.setReadOnly(True)
        self.live_tcl_edit.setStyleSheet("font-family: Consolas; font-size: 11px;")
        left_tabs.addTab(self.live_tcl_edit, "Live TCL")
        splitter.addWidget(left_tabs)
        
        mid_widget = QWidget()
        mid_layout = QVBoxLayout(mid_widget)

        # Docked Region Placement Live Tuner & Preview Bar (Professional Native Qt)
        self.hud_autoplace = QGroupBox("Region Placement Live Preview & Weight Tuning", mid_widget)
        hud_l = QVBoxLayout(self.hud_autoplace)
        hud_l.setContentsMargins(6, 6, 6, 6)
        hud_l.setSpacing(4)

        # Row 1: Status & Action buttons
        h_row1 = QHBoxLayout()
        lbl_hud_status = QLabel("Interactive Preview Active — Adjust weights to tune layout in real time:")
        h_row1.addWidget(lbl_hud_status)
        h_row1.addStretch()

        self.btn_hud_reroll = QPushButton("Re-roll Seed")
        self.btn_hud_reroll.clicked.connect(self.reroll_autoplace_seed)

        self.btn_hud_accept = QPushButton("Accept")
        self.btn_hud_accept.setDefault(True)
        self.btn_hud_accept.clicked.connect(self.accept_autoplace_preview)

        self.btn_hud_undo = QPushButton("Cancel / Revert")
        self.btn_hud_undo.clicked.connect(self.cancel_autoplace_preview)

        h_row1.addWidget(self.btn_hud_reroll)
        h_row1.addWidget(self.btn_hud_accept)
        h_row1.addWidget(self.btn_hud_undo)
        hud_l.addLayout(h_row1)

        # Row 2: Sliders and spinboxes for R2M, R2R, R2IO, Halo, Seed
        h_row2 = QHBoxLayout()

        self._autoplace_debounce_timer = QTimer(self)
        self._autoplace_debounce_timer.setSingleShot(True)
        self._autoplace_debounce_timer.setInterval(40)  # 40ms debounce for 25 FPS buttery smooth dragging
        self._autoplace_debounce_timer.timeout.connect(self.trigger_live_autoplace)

        # R2M (Region-to-Macro)
        h_row2.addWidget(QLabel("R2M:"))
        self.sld_r2m = QSlider(Qt.Orientation.Horizontal)
        self.sld_r2m.setRange(0, 300)
        self.sld_r2m.setValue(100)
        self.sld_r2m.setFixedWidth(80)
        self.sp_r2m = QDoubleSpinBox()
        self.sp_r2m.setRange(0.0, 3.0)
        self.sp_r2m.setValue(1.0)
        self.sp_r2m.setSingleStep(0.1)
        self.sp_r2m.setFixedWidth(55)
        
        self.sld_r2m.valueChanged.connect(lambda v: (self.sp_r2m.blockSignals(True), self.sp_r2m.setValue(v / 100.0), self.sp_r2m.blockSignals(False), self._autoplace_debounce_timer.start()))
        self.sp_r2m.valueChanged.connect(lambda v: (self.sld_r2m.blockSignals(True), self.sld_r2m.setValue(int(v * 100)), self.sld_r2m.blockSignals(False), self._autoplace_debounce_timer.start()))
        h_row2.addWidget(self.sld_r2m)
        h_row2.addWidget(self.sp_r2m)

        # R2R (Region-to-Region)
        h_row2.addWidget(QLabel("R2R:"))
        self.sld_r2r = QSlider(Qt.Orientation.Horizontal)
        self.sld_r2r.setRange(0, 300)
        self.sld_r2r.setValue(100)
        self.sld_r2r.setFixedWidth(80)
        self.sp_r2r = QDoubleSpinBox()
        self.sp_r2r.setRange(0.0, 3.0)
        self.sp_r2r.setValue(1.0)
        self.sp_r2r.setSingleStep(0.1)
        self.sp_r2r.setFixedWidth(55)
        self.sld_r2r.valueChanged.connect(lambda v: (self.sp_r2r.blockSignals(True), self.sp_r2r.setValue(v / 100.0), self.sp_r2r.blockSignals(False), self._autoplace_debounce_timer.start()))
        self.sp_r2r.valueChanged.connect(lambda v: (self.sld_r2r.blockSignals(True), self.sld_r2r.setValue(int(v * 100)), self.sld_r2r.blockSignals(False), self._autoplace_debounce_timer.start()))
        h_row2.addWidget(self.sld_r2r)
        h_row2.addWidget(self.sp_r2r)

        # R2IO (Region-to-IO)
        h_row2.addWidget(QLabel("R2IO:"))
        self.sld_r2io = QSlider(Qt.Orientation.Horizontal)
        self.sld_r2io.setRange(0, 300)
        self.sld_r2io.setValue(100)
        self.sld_r2io.setFixedWidth(80)
        self.sp_r2io = QDoubleSpinBox()
        self.sp_r2io.setRange(0.0, 3.0)
        self.sp_r2io.setValue(1.0)
        self.sp_r2io.setSingleStep(0.1)
        self.sp_r2io.setFixedWidth(55)
        self.sld_r2io.valueChanged.connect(lambda v: (self.sp_r2io.blockSignals(True), self.sp_r2io.setValue(v / 100.0), self.sp_r2io.blockSignals(False), self._autoplace_debounce_timer.start()))
        self.sp_r2io.valueChanged.connect(lambda v: (self.sld_r2io.blockSignals(True), self.sld_r2io.setValue(int(v * 100)), self.sld_r2io.blockSignals(False), self._autoplace_debounce_timer.start()))
        h_row2.addWidget(self.sld_r2io)
        h_row2.addWidget(self.sp_r2io)

        # Seed spinbox
        h_row2.addWidget(QLabel("Seed:"))
        self.sp_autoplace_seed = QSpinBox()
        self.sp_autoplace_seed.setRange(1, 99999)
        self.sp_autoplace_seed.setValue(42)
        self.sp_autoplace_seed.setFixedWidth(65)
        self.sp_autoplace_seed.valueChanged.connect(lambda _: self._autoplace_debounce_timer.start())
        h_row2.addWidget(self.sp_autoplace_seed)

        hud_l.addLayout(h_row2)
        self.hud_autoplace.setVisible(False)
        mid_layout.addWidget(self.hud_autoplace)

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
        right_widget.setMaximumWidth(340)
        right_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
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
        self.cmb_region_module.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.cmb_region_module.setMinimumContentsLength(16)
        self.cmb_region_module.setMaximumWidth(220)
        self.sp_region_density = QDoubleSpinBox()
        self.sp_region_density.setRange(0.0, 1.0)
        self.sp_region_density.setValue(0.60)
        self.sp_region_density.setSingleStep(0.05)
        self.sp_region_density.valueChanged.connect(self.on_sel_density_changed)

        self.sp_common_region_halo = QDoubleSpinBox()
        self.sp_common_region_halo.setRange(0.0, 500.0)
        self.sp_common_region_halo.setValue(10.0)
        self.sp_common_region_halo.setSingleStep(1.0)
        self.sp_common_region_halo.setSuffix(" µm")
        self.sp_common_region_halo.valueChanged.connect(self.on_common_halo_changed)

        self.btn_draw_region = QPushButton("Create Region")
        self.btn_draw_fence = QPushButton("Create Fence")
        self.lbl_region_util = QLabel("Region Utilization: -")
        
        self.btn_draw_region.clicked.connect(lambda: self.view.start_drawing_region(self.cmb_region_module.currentData() or self.cmb_region_module.currentText(), False, self.sp_region_density.value()))
        self.btn_draw_fence.clicked.connect(lambda: self.view.start_drawing_region(self.cmb_region_module.currentData() or self.cmb_region_module.currentText(), True, self.sp_region_density.value()))

        # Auto-Place Controls
        self.chk_region_lock = QCheckBox("Lock Selected Region")
        self.chk_region_lock.stateChanged.connect(self.on_region_lock_toggled)

        self.chk_allow_rotation = QCheckBox("Allow rotation")
        self.chk_allow_rotation.setChecked(True)

        # Affinity Mode Radio Buttons
        self.rb_aff_hybrid = QRadioButton("Hybrid (Recommended)")
        self.rb_aff_netlist = QRadioButton("Netlist Interconnect Graph")
        self.rb_aff_hierarchy = QRadioButton("Hierarchical Architecture Tree")
        self.rb_aff_hybrid.setChecked(True)
        self.bg_affinity = QButtonGroup(self)
        self.bg_affinity.addButton(self.rb_aff_hybrid)
        self.bg_affinity.addButton(self.rb_aff_netlist)
        self.bg_affinity.addButton(self.rb_aff_hierarchy)

        self.chk_force_place_all = QCheckBox("Force Place All")
        self.sp_force_density = QDoubleSpinBox()
        self.sp_force_density.setRange(10.0, 95.0)
        self.sp_force_density.setValue(60.0)
        self.sp_force_density.setSuffix("%")
        self.sp_force_density.setEnabled(False)

        self.sp_min_module_pct = QDoubleSpinBox()
        self.sp_min_module_pct.setRange(0.1, 50.0)
        self.sp_min_module_pct.setValue(2.0)
        self.sp_min_module_pct.setSingleStep(0.5)
        self.sp_min_module_pct.setSuffix("%")
        self.sp_min_module_pct.setToolTip("Minimum % of chip std cell area required to create an automatic region fence")
        self.sp_min_module_pct.setEnabled(False)

        def _on_force_toggled(checked):
            self.sp_force_density.setEnabled(checked)
            self.sp_min_module_pct.setEnabled(checked)
        self.chk_force_place_all.toggled.connect(_on_force_toggled)

        h_force = QHBoxLayout()
        h_force.addWidget(self.chk_force_place_all)
        h_force.addWidget(QLabel("Dens:"))
        h_force.addWidget(self.sp_force_density)

        h_filter = QHBoxLayout()
        h_filter.addWidget(QLabel("Min Area Cutoff:"))
        h_filter.addWidget(self.sp_min_module_pct)

        self.chk_force_auto_shape = QCheckBox("Force Auto Shape")

        self.btn_autoplace_regions = QPushButton("Auto Place")
        self.btn_autoplace_regions.setStyleSheet("font-weight: bold; background-color: #89b4fa; color: #11111b;")
        self.btn_autoplace_regions.clicked.connect(self.on_autoplace_regions_clicked)

        self.btn_fence_mode = QPushButton("Fences")
        self.btn_fence_mode.setCheckable(True)
        self.btn_fence_mode.setChecked(True)
        self.btn_fence_mode.setToolTip("Toggle placement type: Checked = Fences (exclusive), Unchecked = Regions (inclusive)")
        self.btn_fence_mode.setStyleSheet("QPushButton { background-color: #fab387; color: #11111b; font-weight: bold; } QPushButton:!checked { background-color: #f9e2af; color: #11111b; }")
        def _update_fence_mode_label():
            self.btn_fence_mode.setText("Fences" if self.btn_fence_mode.isChecked() else "Regions")
        self.btn_fence_mode.toggled.connect(_update_fence_mode_label)

        self.lbl_autoplace_spinner = QLabel("")
        self.lbl_autoplace_spinner.setStyleSheet("color: #89b4fa; font-weight: bold; font-family: monospace; font-size: 14px;")
        self.lbl_autoplace_spinner.setFixedWidth(18)

        h_autoplace = QHBoxLayout()
        h_autoplace.addWidget(self.btn_autoplace_regions, stretch=3)
        h_autoplace.addWidget(self.lbl_autoplace_spinner)
        h_autoplace.addWidget(self.btn_fence_mode, stretch=2)

        self.btn_restore_regions = QPushButton("Restore Regions")
        self.btn_restore_regions.setEnabled(False)
        self.btn_restore_regions.clicked.connect(self.on_restore_regions_clicked)
        
        fl_region.addRow("Module:", self.cmb_region_module)
        fl_region.addRow("Density:", self.sp_region_density)
        fl_region.addRow("Halo:", self.sp_common_region_halo)
        fl_region.addRow(self.btn_draw_region, self.btn_draw_fence)
        fl_region.addRow(self.lbl_region_util)
        fl_region.addRow(self.chk_region_lock)
        fl_region.addRow("Affinity:", self.rb_aff_hybrid)
        fl_region.addRow("", self.rb_aff_netlist)
        fl_region.addRow("", self.rb_aff_hierarchy)
        fl_region.addRow(self.chk_allow_rotation)
        fl_region.addRow(h_force)
        fl_region.addRow(h_filter)
        fl_region.addRow(self.chk_force_auto_shape)
        fl_region.addRow(h_autoplace)
        fl_region.addRow(self.btn_restore_regions)
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
        
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([280, 800, 280])
        self.tabs.setEnabled(False)
        if self.project_config: self.populate_macro_list(self.project_config)
        
        try:
            proj_root, base = self._get_project_context()
            save_path = os.path.join(proj_root, "reports", f"{base}_floorplan_save.json").replace("\\", "/")
            if os.path.exists(save_path):
                import json
                with open(save_path, 'r') as f:
                    state = json.load(f)
                if 'die' in state:
                    self.sp_die_w.setValue(state['die']['w'])
                    self.sp_die_h.setValue(state['die']['h'])
                    self.sp_marg_t.setValue(state['die']['mt'])
                    self.sp_marg_b.setValue(state['die']['mb'])
                    self.sp_marg_l.setValue(state['die']['ml'])
                    self.sp_marg_r.setValue(state['die']['mr'])
                    
                    w = state['die']['w']; h = state['die']['h']
                    ml = state['die']['ml']; mr = state['die']['mr']
                    mt = state['die']['mt']; mb = state['die']['mb']
                    self.die_rect = QRectF(0, 0, w, h)
                    self.core_rect = QRectF(ml, mb, w - ml - mr, h - mt - mb)
                    self.view.setBackgroundBrush(QBrush(QColor("#000000")))
                    self.floorplan_initialized = True
                    self.tabs.setEnabled(True)
                    self.undo_stack.append(state)
                    self.load_state(state)
                    # fit die on load
                    QTimer.singleShot(100, self.fit_die)
        except Exception as e:
            print("Failed to load floorplan state:", e)

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
            
        proj_root, base = self._get_project_context()
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

                # Compute true inclusive hierarchical areas
                self.inclusive_module_areas = {}
                for m, a in self.module_areas.items():
                    parts = m.split('/')
                    for i in range(1, len(parts) + 1):
                        prefix = '/'.join(parts[:i])
                        self.inclusive_module_areas[prefix] = self.inclusive_module_areas.get(prefix, 0.0) + a

                # Populate combo box with contribution % badges
                self.cmb_region_module.clear()
                total_area = max(1.0, self.total_std_cell_area)
                sorted_mods = sorted(
                    self.inclusive_module_areas.keys(),
                    key=lambda m: self.inclusive_module_areas[m],
                    reverse=True
                )
                for mod in sorted_mods:
                    # Skip whole-chip root wrapper if submodules exist
                    if mod == 'neorv32_top_inst' and len(sorted_mods) > 1:
                        continue
                    pct = (self.inclusive_module_areas[mod] / total_area) * 100.0
                    display_text = f"[{pct:4.1f}%] {mod.split('/')[-1]} ({mod})"
                    self.cmb_region_module.addItem(display_text, mod)
            except Exception as e:
                print("Floorplanner: Error reading sizes json:", e)
        
        # Now find sizes in LEFs
        try:
            import glob, re
            search_dirs = [
                proj_root,
                os.path.join(proj_root, "source")
            ]
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            bundled_pdk = os.path.join(repo_root, "third-party", "pdks")
            if os.path.isdir(bundled_pdk):
                search_dirs.append(bundled_pdk)

            pdk_name = self.project_config.get('pdk', '') if hasattr(self, 'project_config') and self.project_config else ''
            pdk_cfg = None
            if self.pdk_mgr:
                for c in self.pdk_mgr.configs:
                    if c['name'] == pdk_name or (pdk_name and pdk_name.lower() in c['name'].lower()):
                        pdk_cfg = c
                        break
            if pdk_cfg:
                lib_path = pdk_cfg.get('lib', '')
                if "libs.ref" in lib_path:
                    search_dirs.append(lib_path.split("libs.ref")[0])

            env_pdk = os.environ.get("PDK_ROOT")
            if env_pdk and os.path.isdir(env_pdk):
                search_dirs.append(env_pdk)

            for m_name in requested_macros:
                found_lef = None
                for d in search_dirs:
                    if not os.path.exists(d): continue
                    for lef in glob.glob(os.path.join(d, "**", f"{m_name}.lef"), recursive=True):
                        if os.path.isfile(lef):
                            found_lef = lef
                            break
                    if found_lef: break

                if found_lef:
                    with open(found_lef, 'r') as f:
                        content = f.read()
                    m = re.search(r'SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)', content)
                    if m:
                        self.macro_sizes[m_name] = (float(m.group(1)), float(m.group(2)))
                        print(f"[FLOORPLAN] Loaded true scale for macro '{m_name}': {self.macro_sizes[m_name][0]} x {self.macro_sizes[m_name][1]} um")

                    if not hasattr(self, 'macro_pins'): self.macro_pins = {}
                    self.macro_pins[m_name] = []
                    pin_blocks = re.findall(r'PIN\s+(\S+)(.*?)END\s+\1', content, re.DOTALL)
                    for pname, pcontent in pin_blocks:
                        rect_match = re.search(r'RECT\s+([0-9.-]+)\s+([0-9.-]+)\s+([0-9.-]+)\s+([0-9.-]+)', pcontent)
                        if rect_match:
                            px1, py1, px2, py2 = map(float, rect_match.groups())
                            self.macro_pins[m_name].append({"name": pname, "rect": (px1, py1, px2, py2)})
        except Exception as e:
            print("Floorplanner: Error parsing LEF sizes:", e)
            
        # Add to list widget the actual instances or requested macros
        if hasattr(self, 'macro_instances') and self.macro_instances:
            for inst_name, master_name in self.macro_instances.items():
                item_text = f"[{inst_name}] ({master_name})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, f"{master_name}|{inst_name}")
                self.macro_list.addItem(item)
        elif requested_macros:
            for m_name in requested_macros:
                item_text = f"[{m_name}_inst] ({m_name})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, f"{m_name}|{m_name}_inst")
                self.macro_list.addItem(item)

        # Populate I/O Pins tab if pins or netlist context exist
        if hasattr(self, 'pin_list'):
            self.pin_list.clear()
            pins_found = []
            proj_root = getattr(self, "proj_root", "")
            if not proj_root and hasattr(self, "project_config") and isinstance(self.project_config, dict):
                proj_root = self.project_config.get("project_root", "")
            if proj_root:
                def_path = os.path.join(proj_root, "results", "temp.def")
                if os.path.isfile(def_path):
                    try:
                        with open(def_path, "r") as f:
                            in_pins = False
                            for line in f:
                                if "PINS " in line and not line.strip().startswith("-"):
                                    in_pins = True
                                elif in_pins:
                                    if "END PINS" in line:
                                        break
                                    m_pin = re.search(r"-\s+(\S+)\b", line)
                                    if m_pin:
                                        pins_found.append(m_pin.group(1))
                    except Exception:
                        pass
            if not pins_found and hasattr(self, 'top_module') and self.top_module and proj_root:
                try:
                    from silis.backendflow.floorplanner.ioplacer import natural_sort_key
                    netlist_dir = os.path.join(proj_root, "netlist")
                    candidates = [
                        os.path.join(netlist_dir, f"{self.top_module}_netlist.v"),
                        os.path.join(proj_root, "results", "synth.v")
                    ]
                    for cand in candidates:
                        if os.path.isfile(cand):
                            with open(cand, "r") as f:
                                content = f.read()
                            m_top = re.search(rf"module\s+{self.top_module}\b(?:\s*#\s*\(.*?\))?\s*\((.*?)\);(.*?)(?:endmodule)", content, re.DOTALL)
                            if m_top:
                                text_block = m_top.group(1) + "\n" + m_top.group(2)
                                for pm in re.finditer(r"(?:^|[;,(\s])\s*(input|output|inout)\s+(?:wire\s+|reg\s+)?(?:signed\s+)?(?:\[(\d+):(\d+)\]\s+)?([^;,)]+)", text_block, re.MULTILINE):
                                    msb, lsb = pm.group(2), pm.group(3)
                                    pnames = [n.strip() for n in pm.group(4).split(",") if n.strip()]
                                    for pn in pnames:
                                        pn = re.sub(r'//.*$', '', pn).strip()
                                        if not pn or pn.startswith("//"):
                                            continue
                                        if msb is not None and lsb is not None:
                                            h, l = int(msb), int(lsb)
                                            s = 1 if h >= l else -1
                                            for idx in range(l, h + s, s):
                                                pins_found.append(f"{pn}[{idx}]")
                                        else:
                                            pins_found.append(pn)
                                break
                except Exception:
                    pass

            for p in sorted(list(dict.fromkeys(pins_found)), key=lambda x: [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', x)]):
                item = QListWidgetItem(f"[Pin] {p}")
                item.setData(Qt.ItemDataRole.UserRole, p)
                self.pin_list.addItem(item)
            
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

        # Non-destructive buffer: snapshot all existing regions and blockages before clearing scene
        region_buffer = []
        blockage_buffer = []
        for it in self.scene.items():
            if isinstance(it, RegionItem):
                region_buffer.append({
                    'module_name': it.module_name,
                    'x': it.rect().x() + it.pos().x(),
                    'y': it.rect().y() + it.pos().y(),
                    'w': it.rect().width(),
                    'h': it.rect().height(),
                    'is_fence': it.is_fence,
                    'density': getattr(it, 'density', 0.60),
                    'halo': getattr(it, 'halo', (0, 0, 0, 0)),
                    'locked': getattr(it, 'locked', False),
                    'multi_boxes': getattr(it, 'multi_boxes', [])
                })
            elif isinstance(it, BlockageItem):
                blockage_buffer.append({
                    'x': it.rect().x() + it.pos().x(),
                    'y': it.rect().y() + it.pos().y(),
                    'w': it.rect().width(),
                    'h': it.rect().height(),
                    'btype': getattr(it, 'btype', 'Hard'),
                    'pct': getattr(it, 'pct', 40.0)
                })

        self.scene.clear()
        self.view.setBackgroundBrush(QBrush(QColor("#000000")))
        self.die_rect = QRectF(0, 0, w, h)
        die_item = self.scene.addRect(self.die_rect, QPen(QColor("#89b4fa"), 2), QBrush(Qt.BrushStyle.NoBrush))
        die_item.setZValue(-10)
        self.core_rect = QRectF(ml, mb, cw, ch)  # y is mb because Y is up!
        core_item = self.scene.addRect(self.core_rect, QPen(QColor("#a6adc8"), 1, Qt.PenStyle.DashLine), QBrush(Qt.BrushStyle.NoBrush))
        core_item.setZValue(-9)
        self.floorplan_initialized = True
        self.tabs.setEnabled(True)
        
        # Auto-discover and populate macros
        proj_root, base = self._get_project_context()
        def_abs_path = os.path.join(proj_root, "results", "temp.def").replace("\\", "/")
        
        macros_spawned = set()
        
        # 1. Try to load from temp.def if user hasn't explicitly specified dimensions
        if os.path.exists(def_abs_path) and not getattr(self, '_user_custom_dimensions', False):
            parent_ide = self.parent().ide if (self.parent() and hasattr(self.parent(), 'ide')) else None
            parser = DEFParser(def_abs_path, parent_ide)
            if hasattr(parser, 'die_rect') and parser.die_rect and parser.die_rect.width() > 0:
                def_die_w = parser.die_rect.width() / parser.dbu
                def_die_h = parser.die_rect.height() / parser.dbu
                if def_die_w > 10 and def_die_h > 10:
                    w = def_die_w
                    h = def_die_h
                    cw = max(1.0, w - ml - mr)
                    ch = max(1.0, h - mt - mb)
                    self.die_rect = QRectF(0, 0, w, h)
                    self.core_rect = QRectF(ml, mb, cw, ch)
                    die_item.setRect(self.die_rect)
                    core_item.setRect(self.core_rect)
                    self.sp_die_w.setValue(int(def_die_w))
                    self.sp_die_h.setValue(int(def_die_h))

            macros_raw = []
            def_to_ord = {
                "N": "R0", "W": "R90", "S": "R180", "E": "R270",
                "FN": "MY", "FW": "MX90", "FS": "MX", "FE": "MY90",
                "R0": "R0", "R90": "R90", "R180": "R180", "R270": "R270",
                "MY": "MY", "MX": "MX", "MX90": "MX90", "MY90": "MY90"
            }
            for inst_name, rect in parser.comps_map.items():
                if rect.width() / parser.dbu > 50: # It's a macro
                    master_name = parser.comp_masters.get(inst_name, "")
                    orient_def = parser.comp_orients.get(inst_name, "N") if hasattr(parser, 'comp_orients') else "N"
                    orient_ord = def_to_ord.get(orient_def, "R0")
                    if master_name in self.macro_sizes:
                        w, h = self.macro_sizes[master_name]
                    else:
                        w = rect.width() / parser.dbu
                        h = rect.height() / parser.dbu
                        if orient_def in ["W", "E", "FW", "FE", "R90", "R270", "MX90", "MY90"]:
                            w, h = h, w
                        
                    x = rect.x() / parser.dbu
                    y = rect.y() / parser.dbu
                    macros_raw.append({
                        'inst_name': inst_name,
                        'master_name': master_name,
                        'w': w, 'h': h,
                        'orient': orient_ord,
                        'x': x, 'y': y,
                        'is_unplaced': (x == 0 and y == 0)
                    })

            has_unplaced = any(m['is_unplaced'] for m in macros_raw)
            if has_unplaced and macros_raw:
                cur_dw = self.die_rect.width()
                cur_dh = self.die_rect.height()
                adj_dw, adj_dh, placed = compute_peripheral_macro_placement(
                    macros_raw, die_w=cur_dw, die_h=cur_dh,
                    margins=(ml, mr, mb, mt),
                    macro_sizes=self.macro_sizes
                )
                if adj_dw > cur_dw or adj_dh > cur_dh:
                    w = adj_dw; h = adj_dh
                    cw = max(1.0, w - ml - mr)
                    ch = max(1.0, h - mt - mb)
                    self.die_rect = QRectF(0, 0, w, h)
                    self.core_rect = QRectF(ml, mb, cw, ch)
                    die_item.setRect(self.die_rect)
                    core_item.setRect(self.core_rect)
                    self.sp_die_w.setValue(int(adj_dw))
                    self.sp_die_h.setValue(int(adj_dh))

                for pm in placed:
                    m_item = MacroItem(pm['name'], pm['w'], pm['h'], self.core_rect, self)
                    m_item.set_inst_name(pm['inst_name'])
                    m_item.set_orientation(pm['orientation'])
                    m_item.update_halo(*pm['halo'])
                    m_item.setPos(pm['x'], pm['y'])
                    self.scene.addItem(m_item)
            else:
                for m in macros_raw:
                    m_item = MacroItem(m['master_name'], m['w'], m['h'], self.core_rect, self)
                    m_item.set_inst_name(m['inst_name'])
                    m_item.set_orientation(m['orient'])
                    m_item.setPos(m['x'], m['y'])
                    self.scene.addItem(m_item)

        # Fallback: if no macro items loaded from DEF but instances exist from sizes.json / config
        has_macro_items = any(isinstance(item, MacroItem) for item in self.scene.items())
        if not has_macro_items and hasattr(self, 'macro_instances') and self.macro_instances:
            macros_raw = []
            for inst_name, master_name in self.macro_instances.items():
                def_w, def_h = self.macro_sizes.get(master_name, (479.78, 397.5))
                macros_raw.append({
                    'inst_name': inst_name,
                    'master_name': master_name,
                    'w': def_w, 'h': def_h,
                    'orient': 'R0',
                    'x': 0, 'y': 0,
                    'is_unplaced': True
                })
            cur_dw = self.die_rect.width()
            cur_dh = self.die_rect.height()
            adj_dw, adj_dh, placed = compute_peripheral_macro_placement(
                macros_raw, die_w=cur_dw, die_h=cur_dh,
                margins=(ml, mr, mb, mt),
                macro_sizes=self.macro_sizes
            )
            if adj_dw > cur_dw or adj_dh > cur_dh:
                w = adj_dw; h = adj_dh
                cw = max(1.0, w - ml - mr)
                ch = max(1.0, h - mt - mb)
                self.die_rect = QRectF(0, 0, w, h)
                self.core_rect = QRectF(ml, mb, cw, ch)
                die_item.setRect(self.die_rect)
                core_item.setRect(self.core_rect)
                self.sp_die_w.setValue(int(adj_dw))
                self.sp_die_h.setValue(int(adj_dh))

            for pm in placed:
                m_item = MacroItem(pm['name'], pm['w'], pm['h'], self.core_rect, self)
                m_item.set_inst_name(pm['inst_name'])
                m_item.set_orientation(pm['orientation'])
                m_item.update_halo(*pm['halo'])
                m_item.setPos(pm['x'], pm['y'])
                self.scene.addItem(m_item)

        # Restore regions from buffer even if core changed or if they extend out of bounds
        for reg in region_buffer:
            r_item = RegionItem(
                reg['x'], reg['y'], reg['w'], reg['h'],
                reg['module_name'], is_fence=reg['is_fence'],
                density=reg['density'], core_rect=self.core_rect, parent=None
            )
            r_item.update_halo(*reg['halo'])
            r_item.set_locked(reg['locked'])
            if reg.get('multi_boxes'):
                r_item.multi_boxes = reg['multi_boxes']

            # Out-of-bounds detection: Keep on canvas, style with warning border
            out_of_bounds = (
                reg['x'] < self.core_rect.left() or
                reg['y'] < self.core_rect.top() or
                reg['x'] + reg['w'] > self.core_rect.right() or
                reg['y'] + reg['h'] > self.core_rect.bottom()
            )
            if out_of_bounds:
                r_item.setPen(QPen(QColor("#fab387"), 2, Qt.PenStyle.DashDotLine))
                r_item.setToolTip(f"OUT OF BOUNDS: {reg['module_name']} extends outside current core area. Adjust position or hit Auto Place.")

            self.scene.addItem(r_item)

        for blk in blockage_buffer:
            b_item = BlockageItem(
                blk['x'], blk['y'], blk['w'], blk['h'],
                btype=blk['btype'], pct=blk['pct'],
                core_rect=self.core_rect, parent=None
            )
            self.scene.addItem(b_item)
        
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
            it.setForeground(QBrush())

        for b in state['blockages']:
            if b.get('is_region'):
                r_item = RegionItem(b['x'], b['y'], b['w'], b['h'], b['module_name'], b['is_fence'], b.get('density', 0.60), core_rect=self.core_rect)
                if 'halo' in b:
                    r_item.update_halo(*b['halo'])
                if 'locked' in b:
                    r_item.set_locked(b['locked'])
                if 'multi_boxes' in b:
                    r_item.multi_boxes = b['multi_boxes']
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
        self.update_live_tcl()

    def save_state(self):
        if self.is_undoing or not self.floorplan_initialized: return
        self.update_live_tcl()
        state = {'macros': [], 'blockages': [], 
                 'die': {'w': self.sp_die_w.value(), 'h': self.sp_die_h.value(),
                         'mt': self.sp_marg_t.value(), 'mb': self.sp_marg_b.value(),
                         'ml': self.sp_marg_l.value(), 'mr': self.sp_marg_r.value()}}
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
                    'x': item.rect().x() + item.pos().x(), 'y': item.rect().y() + item.pos().y(),
                    'w': item.rect().width(), 'h': item.rect().height(),
                    'btype': item.btype, 'pct': item.pct
                })
            elif isinstance(item, RegionItem):
                state['blockages'].append({
                    'is_region': True,
                    'x': item.rect().x() + item.pos().x(), 'y': item.rect().y() + item.pos().y(),
                    'w': item.rect().width(), 'h': item.rect().height(),
                    'module_name': item.module_name, 'is_fence': item.is_fence,
                    'density': item.density,
                    'halo': item.halo,
                    'locked': item.locked,
                    'multi_boxes': getattr(item, 'multi_boxes', [])
                })
        import json
        if self.undo_stack:
            last = json.dumps(self.undo_stack[-1], sort_keys=True)
            curr = json.dumps(state, sort_keys=True)
            if last == curr: return
        self.undo_stack.append(state)
        self.redo_stack.clear()
        
        try:
            proj_root, base = self._get_project_context()
            save_path = os.path.join(proj_root, "reports", f"{base}_floorplan_save.json").replace("\\", "/")
            with open(save_path, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            pass

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

    def on_autoplace_toggled(self, checked):
        self.cmb_autoplace_method.setEnabled(checked)
        if checked:
            self.apply_autoplace_method(self.cmb_autoplace_method.currentText())
        self.update_live_tcl()
        self.save_state()

    def on_autoplace_method_changed(self, index):
        if self.chk_autoplace.isChecked():
            self.apply_autoplace_method(self.cmb_autoplace_method.currentText())
            self.update_live_tcl()
            self.save_state()

    def apply_autoplace_method(self, method_text):
        if not self.floorplan_initialized or not self.core_rect:
            return

        method = "peripheral"
        if "Hierarchical" in method_text:
            method = "hierarchical"
        elif "Analytical" in method_text:
            method = "openroad"

        # Collect all macros currently in scene or known from instances
        macros_raw = []
        existing_items = [it for it in self.scene.items() if isinstance(it, MacroItem)]
        
        if existing_items:
            for item in existing_items:
                macros_raw.append({
                    'inst_name': item.inst_name,
                    'master_name': item.name,
                    'w': item.w,
                    'h': item.h,
                    'orient': item.orientation,
                    'halo': list(item.halo),
                    'item_ref': item
                })
        elif hasattr(self, 'macro_instances') and self.macro_instances:
            for inst_name, master_name in self.macro_instances.items():
                def_w, def_h = self.macro_sizes.get(master_name, (479.78, 397.5))
                macros_raw.append({
                    'inst_name': inst_name,
                    'master_name': master_name,
                    'w': def_w,
                    'h': def_h,
                    'orient': 'R0',
                    'halo': [10, 10, 10, 10],
                    'item_ref': None
                })

        if not macros_raw:
            return

        ml = self.core_rect.x()
        mb = self.core_rect.y()
        mr = self.die_rect.width() - (self.core_rect.x() + self.core_rect.width())
        mt = self.die_rect.height() - (self.core_rect.y() + self.core_rect.height())

        if method == "peripheral":
            # Peripheral layout solver
            _, _, placed = compute_peripheral_macro_placement(
                macros_raw,
                die_w=self.die_rect.width(),
                die_h=self.die_rect.height(),
                margins=(ml, mr, mb, mt),
                macro_sizes=self.macro_sizes
            )
            for pm in placed:
                target_item = None
                for m in macros_raw:
                    if m['inst_name'] == pm['inst_name']:
                        target_item = m.get('item_ref')
                        break
                if target_item:
                    target_item.set_orientation(pm['orientation'])
                    target_item.update_halo(*pm['halo'])
                    target_item.setPos(pm['x'], pm['y'])
                else:
                    m_item = MacroItem(pm['name'], pm['w'], pm['h'], self.core_rect, self)
                    m_item.set_inst_name(pm['inst_name'])
                    m_item.set_orientation(pm['orientation'])
                    m_item.update_halo(*pm['halo'])
                    m_item.setPos(pm['x'], pm['y'])
                    self.scene.addItem(m_item)
                    # Mark placed in list
                    for idx in range(self.macro_list.count()):
                        it = self.macro_list.item(idx)
                        if pm['name'] in it.text():
                            it.setText(f"{it.text().replace(' [PLACED]', '')} [PLACED]")
                            it.setForeground(QBrush(QColor("#4CAF50")))
                            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                            m_item.list_item = it
                            break

        elif method in ("hierarchical", "openroad"):
            # Non-overlapping Ribbon placement for hierarchical / analytical modes
            core_x1 = self.core_rect.x()
            core_y1 = self.core_rect.y()
            core_x2 = core_x1 + self.core_rect.width()
            core_y2 = core_y1 + self.core_rect.height()

            cursor_x = core_x1 + 30.0
            cursor_y = core_y1 + 30.0
            max_row_h = 0.0

            for i, m in enumerate(macros_raw):
                orient = m.get('orient', 'R0')
                swapped = ["R90", "R270", "MX90", "MY90", "MXR90", "MYR90"]
                eff_w = m['h'] if orient in swapped else m['w']
                eff_h = m['w'] if orient in swapped else m['h']
                halo = m.get('halo', [10, 10, 10, 10])

                if cursor_x + eff_w + halo[1] > core_x2 - 30.0:
                    # Wrap to next row
                    cursor_x = core_x1 + 30.0
                    cursor_y += max_row_h + 30.0
                    max_row_h = 0.0

                x = round(round(cursor_x / 0.005) * 0.005, 3)
                y = round(round(cursor_y / 0.005) * 0.005, 3)

                max_row_h = max(max_row_h, eff_h + halo[3])
                cursor_x += eff_w + halo[1] + 30.0

                target_item = m.get('item_ref')
                if target_item:
                    target_item.setPos(x, y)
                else:
                    m_item = MacroItem(m['master_name'], m['w'], m['h'], self.core_rect, self)
                    m_item.set_inst_name(m['inst_name'])
                    m_item.set_orientation(orient)
                    m_item.update_halo(*halo)
                    m_item.setPos(x, y)
                    self.scene.addItem(m_item)
                    for idx in range(self.macro_list.count()):
                        it = self.macro_list.item(idx)
                        if m['master_name'] in it.text():
                            it.setText(f"{it.text().replace(' [PLACED]', '')} [PLACED]")
                            it.setForeground(QBrush(QColor("#4CAF50")))
                            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                            m_item.list_item = it
                            break

        self.scene.update()

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

    def on_sel_density_changed(self):
        items = self.scene.selectedItems()
        if not items: return
        val = self.sp_sel_density.value()
        for item in items:
            if isinstance(item, RegionItem):
                item.density = val
                if hasattr(item, 'update_text'):
                    item.update_text()
        if hasattr(self, 'sp_region_density'):
            self.sp_region_density.blockSignals(True)
            self.sp_region_density.setValue(val)
            self.sp_region_density.blockSignals(False)
        self.update_live_tcl()
        self.save_state()

    def on_region_lock_toggled(self, state):
        items = self.scene.selectedItems()
        is_locked = (state == Qt.CheckState.Checked.value or state is True or state == 2)
        for item in items:
            if isinstance(item, RegionItem):
                item.set_locked(is_locked)
        self.update_live_tcl()
        self.save_state()

    def on_convert_region_type_clicked(self):
        """Converts the selected RegionItem between exclusive Fence and inclusive Region."""
        items = self.scene.selectedItems()
        if not items or not isinstance(items[0], RegionItem):
            return
        r = items[0]
        r.is_fence = not r.is_fence
        r._update_colors()
        r.update_text()
        self.btn_convert_type.setText("To Region" if r.is_fence else "To Fence")
        self.btn_convert_type.setStyleSheet(
            "font-size: 11px; background: #fab387; color: #11111b; font-weight: bold;"
            if r.is_fence else
            "font-size: 11px; background: #f9e2af; color: #11111b; font-weight: bold;"
        )
        self.update_live_tcl()
        self.save_state()

    def on_common_halo_changed(self):
        """Uniformly applies common halo to all existing RegionItem and Fence items on the canvas."""
        val = self.sp_common_region_halo.value()
        for it in self.scene.items():
            if isinstance(it, RegionItem):
                it.update_halo(val, val, val, val)
        self.scene.update()
        self.update_live_tcl()
        self.save_state()

    def on_restore_regions_clicked(self):
        """Restores regions back to the snapshot saved before auto-placement."""
        if not hasattr(self, "_saved_region_snapshot") or not self._saved_region_snapshot:
            return

        region_items = [it for it in self.scene.items() if isinstance(it, RegionItem)]
        for r_item in region_items:
            mod = r_item.module_name
            if mod in self._saved_region_snapshot:
                snap = self._saved_region_snapshot[mod]
                r_item.setPos(snap["pos_x"], snap["pos_y"])
                r_item.setRect(snap["rect_x"], snap["rect_y"], snap["width"], snap["height"])
                r_item.set_locked(snap["locked"])
                r_item.set_starved(False)

        self.btn_restore_regions.setEnabled(False)
        self.scene.update()
        self.update_live_tcl()
        self.save_state()

    def on_autoplace_regions_clicked(self):
        """
        Executes hierarchical auto-placement of defined regions.
        Preserves user sizes/aspect-ratios while packing them legally into core cavities.
        Handles narrow corridors and space starvation with one-click Auto-Expand.
        """
        # If Force Place All is checked, synchronize canvas regions with the min area cutoff
        if self.chk_force_place_all.isChecked() and hasattr(self, 'module_areas') and self.module_areas:
            force_dens = self.sp_force_density.value() / 100.0
            min_pct = self.sp_min_module_pct.value()
            total_area = max(1.0, getattr(self, 'total_std_cell_area', sum(self.module_areas.values())))

            eval_areas = getattr(self, 'inclusive_module_areas', None) or self.module_areas
            existing_items = {it.module_name: it for it in self.scene.items() if isinstance(it, RegionItem)}
            halo_val = self.sp_common_region_halo.value() if hasattr(self, 'sp_common_region_halo') else 10.0
            place_as_fence = self.btn_fence_mode.isChecked() if hasattr(self, 'btn_fence_mode') else True

            # Prune any existing unlocked regions that fall below min_pct cutoff
            for m_name, itm in list(existing_items.items()):
                m_area = eval_areas.get(m_name, self.module_areas.get(m_name, 0.0))
                m_pct = (m_area / total_area) * 100.0
                if m_pct < min_pct and not getattr(itm, 'locked', False):
                    self.scene.removeItem(itm)
                    del existing_items[m_name]

            # Detect hierarchy conflicts between qualifying modules (Parent vs Child)
            all_eval_mods = sorted(list(eval_areas.keys()))
            conflicts = []
            for i, m1 in enumerate(all_eval_mods):
                for m2 in all_eval_mods[i+1:]:
                    if m2.startswith(m1 + "/") or m2.startswith(m1 + "."):
                        pct1 = (eval_areas[m1] / total_area) * 100.0
                        pct2 = (eval_areas[m2] / total_area) * 100.0
                        if pct1 >= min_pct and pct2 >= min_pct:
                            conflicts.append((m1, m2))

            skip_modules = set()
            if conflicts:
                c_p, c_c = conflicts[0]
                short_p = c_p.split("/")[-1]
                short_c = c_c.split("/")[-1]
                msg = QMessageBox(self)
                msg.setWindowTitle("Hierarchy Region Conflict")
                msg.setIcon(QMessageBox.Icon.Question)
                msg.setText(
                    f"Hierarchy Conflict Detected:\n\n"
                    f"Parent:  {short_p}\n"
                    f"Child:   {short_c}\n\n"
                    f"Both modules exceed the {min_pct:.0f}% area cutoff.\n"
                    f"Would you like to place the parent module or the child module?"
                )
                btn_p = msg.addButton("Place Parent", QMessageBox.ButtonRole.AcceptRole)
                btn_c = msg.addButton("Place Child", QMessageBox.ButtonRole.RejectRole)
                msg.addButton("Place Both", QMessageBox.ButtonRole.ActionRole)
                msg.exec()
                if msg.clickedButton() == btn_p:
                    skip_modules.add(c_c)
                    if c_c in existing_items and not existing_items[c_c].locked:
                        self.scene.removeItem(existing_items[c_c])
                        del existing_items[c_c]
                elif msg.clickedButton() == btn_c:
                    skip_modules.add(c_p)
                    if c_p in existing_items and not existing_items[c_p].locked:
                        self.scene.removeItem(existing_items[c_p])
                        del existing_items[c_p]

            # Spawn regions for chosen unplaced modules
            for mod_name, mod_area in eval_areas.items():
                if mod_name in skip_modules:
                    continue
                if mod_name not in existing_items and mod_area > 0:
                    if mod_name == 'neorv32_top_inst' and len(eval_areas) > 1:
                        continue
                    mod_pct = (mod_area / total_area) * 100.0
                    if mod_pct < min_pct:
                        continue

                    req_area = mod_area / max(0.10, force_dens)
                    side = math.sqrt(req_area)
                    new_r = RegionItem(
                        self.core_rect.left(), self.core_rect.top(), side, side,
                        mod_name, is_fence=place_as_fence, density=force_dens,
                        core_rect=self.core_rect, parent=None
                    )
                    new_r.update_halo(halo_val, halo_val, halo_val, halo_val)
                    self.scene.addItem(new_r)

        region_items = [it for it in self.scene.items() if isinstance(it, RegionItem)]
        if not region_items:
            QMessageBox.information(self, "Auto Region Placement", "No regions or modules defined to place.")
            return

        # 1. Inline loading spinner animation sequence (- \| / -)
        spin_chars = ["-", "\\", "|", "/"]
        spin_state = [0]
        def _tick_spinner():
            spin_state[0] = (spin_state[0] + 1) % 4
            self.lbl_autoplace_spinner.setText(spin_chars[spin_state[0]])
            QApplication.processEvents()

        _tick_spinner()

        # Capture snapshot for non-destructive restore
        self._saved_region_snapshot = {}
        for r in region_items:
            self._saved_region_snapshot[r.module_name] = {
                "pos_x": r.pos().x(),
                "pos_y": r.pos().y(),
                "rect_x": r.rect().x(),
                "rect_y": r.rect().y(),
                "width": r.rect().width(),
                "height": r.rect().height(),
                "locked": r.locked,
                "multi_boxes": getattr(r, 'multi_boxes', [])
            }
        self.btn_restore_regions.setEnabled(True)

        _tick_spinner()

        # 2. Gather design context (macros, blockages, pins, netlist)
        macro_items = [it for it in self.scene.items() if isinstance(it, MacroItem)]
        macro_dicts = []
        for m in macro_items:
            macro_dicts.append({
                "inst": m.inst_name,
                "name": m.name,
                "x": m.pos().x(),
                "y": m.pos().y(),
                "width": m.rect().width(),
                "height": m.rect().height(),
                "halo": m.halo,
            })

        blockage_items = [it for it in self.scene.items() if isinstance(it, BlockageItem)]
        blockage_rects = [it.sceneBoundingRect() for it in blockage_items]

        region_dicts = []
        for r in region_items:
            scene_r = r.sceneBoundingRect()
            mod_area = self.module_areas.get(r.module_name, 0.0) if hasattr(self, 'module_areas') else 0.0
            region_dicts.append({
                "module": r.module_name,
                "x": scene_r.x(),
                "y": scene_r.y(),
                "width": r.rect().width(),
                "height": r.rect().height(),
                "locked": r.locked,
                "is_fence": r.is_fence,
                "density": r.density,
                "halo": r.halo,
                "module_area": mod_area
            })

        proj_root, base = self._get_project_context()
        netlist_path = os.path.join(proj_root, "netlist", f"{base}_netlist.v")
        if not os.path.isfile(netlist_path):
            netlist_path = os.path.join(proj_root, "source", f"{base}.v")

        # Determine chosen affinity mode
        if self.rb_aff_netlist.isChecked():
            aff_mode = "netlist"
        elif self.rb_aff_hierarchy.isChecked():
            aff_mode = "hierarchy"
        else:
            aff_mode = "hybrid"

        allow_rot = self.chk_allow_rotation.isChecked()
        force_auto_shape = self.chk_force_auto_shape.isChecked()
        force_density = (self.sp_force_density.value() / 100.0) if self.chk_force_place_all.isChecked() else None

        _tick_spinner()

        # Gather top-level pin locations for R2IO affinity attraction
        pin_dicts = []
        if hasattr(self, 'pin_list'):
            pin_count = self.pin_list.count()
            if pin_count > 0:
                cw = self.core_rect.width()
                ch = self.core_rect.height()
                cx = self.core_rect.x()
                cy = self.core_rect.y()
                perim = 2 * (cw + ch)
                step = perim / max(1, pin_count)
                for idx in range(pin_count):
                    it = self.pin_list.item(idx)
                    p_name = it.data(Qt.ItemDataRole.UserRole) or it.text().replace("[Pin] ", "")
                    dist = idx * step
                    if dist < cw:
                        px, py = cx + dist, cy
                    elif dist < cw + ch:
                        px, py = cx + cw, cy + (dist - cw)
                    elif dist < (2 * cw + ch):
                        px, py = cx + cw - (dist - (cw + ch)), cy + ch
                    else:
                        px, py = cx, cy + ch - (dist - (2 * cw + ch))
                    pin_dicts.append({"name": p_name, "x": px, "y": py})

        # 3. Open Live Preview HUD Bar
        self.hud_autoplace.setVisible(True)
        self.trigger_live_autoplace()

    def trigger_live_autoplace(self):
        """Executes fast reactive placement solver using current HUD parameters and previews on canvas."""
        region_items = [it for it in self.scene.items() if isinstance(it, RegionItem)]
        if not region_items:
            return

        macro_items = [it for it in self.scene.items() if isinstance(it, MacroItem)]
        macro_dicts = [{
            "inst": m.inst_name, "name": m.name, "x": m.pos().x(), "y": m.pos().y(),
            "width": m.rect().width(), "height": m.rect().height(), "halo": m.halo
        } for m in macro_items]
        blockage_rects = [it.sceneBoundingRect() for it in self.scene.items() if isinstance(it, BlockageItem)]

        region_dicts = []
        for r in region_items:
            scene_r = r.sceneBoundingRect()
            mod_area = self.module_areas.get(r.module_name, 0.0) if hasattr(self, 'module_areas') else 0.0
            region_dicts.append({
                "module": r.module_name, "x": scene_r.x(), "y": scene_r.y(),
                "width": r.rect().width(), "height": r.rect().height(), "locked": r.locked,
                "is_fence": r.is_fence, "density": r.density, "halo": r.halo, "module_area": mod_area
            })

        proj_root, base = self._get_project_context()
        netlist_path = os.path.join(proj_root, "netlist", f"{base}_netlist.v")
        if not os.path.isfile(netlist_path):
            netlist_path = os.path.join(proj_root, "source", f"{base}.v")

        aff_mode = "hybrid"
        if hasattr(self, "rb_aff_netlist") and self.rb_aff_netlist.isChecked():
            aff_mode = "netlist"
        elif hasattr(self, "rb_aff_hierarchy") and self.rb_aff_hierarchy.isChecked():
            aff_mode = "hierarchy"

        # Get HUD live weights
        w_r2m = self.sp_r2m.value() if hasattr(self, "sp_r2m") else 1.0
        w_r2r = self.sp_r2r.value() if hasattr(self, "sp_r2r") else 1.0
        w_r2io = self.sp_r2io.value() if hasattr(self, "sp_r2io") else 1.0
        seed = self.sp_autoplace_seed.value() if hasattr(self, "sp_autoplace_seed") else 42

        # Top-level pins
        pin_dicts = []
        if hasattr(self, 'pin_list') and self.pin_list.count() > 0:
            cw, ch = self.core_rect.width(), self.core_rect.height()
            cx, cy = self.core_rect.x(), self.core_rect.y()
            step = (2 * (cw + ch)) / max(1, self.pin_list.count())
            for idx in range(self.pin_list.count()):
                it = self.pin_list.item(idx)
                p_name = it.data(Qt.ItemDataRole.UserRole) or it.text().replace("[Pin] ", "")
                dist = idx * step
                if dist < cw: px, py = cx + dist, cy
                elif dist < cw + ch: px, py = cx + cw, cy + (dist - cw)
                elif dist < (2 * cw + ch): px, py = cx + cw - (dist - (cw + ch)), cy + ch
                else: px, py = cx, cy + ch - (dist - (2 * cw + ch))
                pin_dicts.append({"name": p_name, "x": px, "y": py})

        try:
            from backendflow.floorplanner.region_autoplacer import HierarchicalAutoRegionPlacer
        except ImportError:
            from silis.backendflow.floorplanner.region_autoplacer import HierarchicalAutoRegionPlacer

        force_dens = (self.sp_force_density.value() / 100.0) if self.chk_force_place_all.isChecked() else None
        cached_graph = getattr(self, "_cached_interconnect_graph", None)
        placer = HierarchicalAutoRegionPlacer(
            core_rect=self.core_rect,
            die_rect=self.die_rect,
            macros=macro_dicts,
            regions=region_dicts,
            blockages=blockage_rects,
            pins=pin_dicts,
            netlist_path=netlist_path,
            affinity_mode=aff_mode,
            allow_rotation=self.chk_allow_rotation.isChecked(),
            ignore_narrow_corridors=True,
            force_auto_shape=self.chk_force_auto_shape.isChecked(),
            force_density=force_dens,
            seed=seed,
            w_r2m=w_r2m,
            w_r2r=w_r2r,
            w_r2io=w_r2io,
            allow_non_rectangular=True,
            interconnect_graph=cached_graph,
        )

        result = placer.solve()
        if not cached_graph and "interconnect_graph" in result:
            self._cached_interconnect_graph = result["interconnect_graph"]

        # Update preview on canvas
        multi_map = result.get("multi_boxes", {})
        for r in region_items:
            mod = r.module_name
            if mod in result["placements"]:
                placed_rect = result["placements"][mod]
                r.setPos(0, 0)
                r.setRect(placed_rect.x(), placed_rect.y(), placed_rect.width(), placed_rect.height())
                r.set_starved(False)
                if mod in multi_map:
                    r.multi_boxes = multi_map[mod]
                else:
                    r.multi_boxes = []
            elif mod in result.get("starved_regions", []):
                r.set_starved(True)

        if hasattr(self, "lbl_autoplace_spinner"):
            self.lbl_autoplace_spinner.setText("")

        self.scene.update()

    def accept_autoplace_preview(self):
        """Accepts current layout preview, hides HUD, updates TCL and saves state."""
        self.hud_autoplace.setVisible(False)
        self.update_live_tcl()
        self.save_state()

    def reroll_autoplace_seed(self):
        """Picks a new random seed and triggers live layout regeneration."""
        import random
        new_seed = random.randint(1, 99999)
        self.sp_autoplace_seed.setValue(new_seed)

    def cancel_autoplace_preview(self):
        """Discards preview, hides HUD and restores original snapshot."""
        self.hud_autoplace.setVisible(False)
        self.on_restore_regions_clicked()

    def on_fit_core_to_density_clicked(self):
        """Mathematically fits core width and height to achieve the target density."""
        target_dens = self.sp_target_core_density.value() / 100.0
        total_std_area = getattr(self, 'total_std_cell_area', 0.0)
        
        # Calculate macro area
        macro_area = 0.0
        for it in self.scene.items():
            if isinstance(it, MacroItem):
                macro_area += it.rect().width() * it.rect().height()

        req_logic_area = total_std_area / max(0.10, target_dens)
        req_core_area = (req_logic_area + macro_area) * 1.15  # 15% routing reserve

        side = math.sqrt(req_core_area)
        # Snap to Sky130 row height multiple
        row_h = 2.72
        side_h = math.ceil(side / row_h) * row_h
        side_w = side_h

        ml = self.sp_marg_l.value(); mr = self.sp_marg_r.value()
        mb = self.sp_marg_b.value(); mt = self.sp_marg_t.value()

        die_w = side_w + ml + mr
        die_h = side_h + mb + mt

        self.sp_die_w.setValue(round(die_w, 1))
        self.sp_die_h.setValue(round(die_h, 1))
        self._user_custom_dimensions = True
        self.init_floorplan()

    def auto_expand_core(self, new_core_w: float, new_core_h: float):
        """Expands the core area and re-runs auto-placement."""
        cur_die_w = self.die_rect.width()
        cur_die_h = self.die_rect.height()
        margin_x = 20.0
        margin_y = 20.0

        new_die_w = max(cur_die_w, new_core_w + (margin_x * 2))
        new_die_h = max(cur_die_h, new_core_h + (margin_y * 2))

        self.core_rect = QRectF(margin_x, margin_y, new_core_w, new_core_h)
        self.die_rect = QRectF(0, 0, new_die_w, new_die_h)

        if hasattr(self, "sp_die_w"):
            self.sp_die_w.setValue(new_die_w)
            self.sp_die_h.setValue(new_die_h)
        if hasattr(self, "sp_core_x"):
            self.sp_core_x.setValue(margin_x)
            self.sp_core_y.setValue(margin_y)
            self.sp_core_w.setValue(new_core_w)
            self.sp_core_h.setValue(new_core_h)

        self._user_custom_dimensions = True
        self.init_floorplan()
        # Re-trigger auto-placement inside newly expanded canvas
        self.on_autoplace_regions_clicked()


    def on_spinbox_changed(self):
        items = self.scene.selectedItems()
        if items and isinstance(items[0], MacroItem):
            items[0].setPos(self.sp_sel_x.value(), self.sp_sel_y.value())
            self.save_state()

    def on_selection_changed(self):
        try:
            self.update_utilization()
            items = self.scene.selectedItems()
            if not items:
                self.lbl_sel_name.setText("None")
                self.sp_sel_density.setEnabled(False)
                if hasattr(self, 'btn_convert_type'):
                    self.btn_convert_type.setEnabled(False)
                    self.btn_convert_type.setText("Convert Type")
                    self.btn_convert_type.setStyleSheet("font-size: 11px; background: #45475a; color: #cdd6f4;")
                return
            if items and (isinstance(items[0], MacroItem) or isinstance(items[0], BlockageItem) or isinstance(items[0], RegionItem)):
                m = items[0]
                if isinstance(m, MacroItem):
                    full_name = m.name
                    metrics = self.lbl_sel_name.fontMetrics()
                    elided = metrics.elidedText(full_name, Qt.TextElideMode.ElideMiddle, 190)
                    self.lbl_sel_name.setText(elided)
                    self.lbl_sel_name.setToolTip(full_name)
                    self.sp_sel_density.setEnabled(False)
                    if hasattr(self, 'btn_convert_type'):
                        self.btn_convert_type.setEnabled(False)
                        self.btn_convert_type.setText("Convert Type")
                        self.btn_convert_type.setStyleSheet("font-size: 11px; background: #45475a; color: #cdd6f4;")
                elif isinstance(m, BlockageItem):
                    self.lbl_sel_name.setText(f"Blockage ({m.btype})")
                    self.lbl_sel_name.setToolTip(f"Blockage ({m.btype})")
                    self.sp_sel_density.setEnabled(False)
                    if hasattr(self, 'btn_convert_type'):
                        self.btn_convert_type.setEnabled(False)
                        self.btn_convert_type.setText("Convert Type")
                        self.btn_convert_type.setStyleSheet("font-size: 11px; background: #45475a; color: #cdd6f4;")
                elif isinstance(m, RegionItem):
                    full_name = f"Region: {m.module_name}"
                    metrics = self.lbl_sel_name.fontMetrics()
                    elided = metrics.elidedText(full_name, Qt.TextElideMode.ElideMiddle, 190)
                    self.lbl_sel_name.setText(elided)
                    self.lbl_sel_name.setToolTip(full_name)
                    self.sp_sel_density.setEnabled(True)
                    self.sp_sel_density.blockSignals(True)
                    self.sp_sel_density.setValue(m.density)
                    self.sp_sel_density.blockSignals(False)
                    if hasattr(self, 'btn_convert_type'):
                        self.btn_convert_type.setEnabled(True)
                        self.btn_convert_type.setText("To Region" if m.is_fence else "To Fence")
                        self.btn_convert_type.setStyleSheet(
                            "font-size: 11px; background: #fab387; color: #11111b; font-weight: bold;"
                            if m.is_fence else
                            "font-size: 11px; background: #f9e2af; color: #11111b; font-weight: bold;"
                        )
                    if hasattr(self, 'sp_region_density'):
                        self.sp_region_density.blockSignals(True)
                        self.sp_region_density.setValue(m.density)
                        self.sp_region_density.blockSignals(False)
                    if hasattr(self, 'chk_region_lock'):
                        self.chk_region_lock.blockSignals(True)
                        self.chk_region_lock.setChecked(m.locked)
                        self.chk_region_lock.blockSignals(False)
                    if hasattr(self, 'cmb_region_module'):
                        self.cmb_region_module.blockSignals(True)
                        for ci in range(self.cmb_region_module.count()):
                            if self.cmb_region_module.itemData(ci) == m.module_name:
                                self.cmb_region_module.setCurrentIndex(ci)
                                break
                        else:
                            idx = self.cmb_region_module.findText(m.module_name)
                            if idx >= 0:
                                self.cmb_region_module.setCurrentIndex(idx)
                        self.cmb_region_module.blockSignals(False)
                
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

    def update_live_tcl(self):
        tcl = self.generate_floorplan_tcl(apply=False)
        if hasattr(self, 'live_tcl_edit'):
            self.live_tcl_edit.setPlainText(tcl)

    def generate_floorplan_tcl(self, apply=True):
        if not self.floorplan_initialized: return ""
        die_w = self.die_rect.width(); die_h = self.die_rect.height()
        core_x1 = self.core_rect.x(); core_y1 = self.core_rect.y()
        core_x2 = core_x1 + self.core_rect.width(); core_y2 = core_y1 + self.core_rect.height()
        
        site_name = "unithd"
        try:
            from pdkmanagers.pdk.manager import SSAForge
            pdk_name = ""
            if hasattr(self, 'parent') and self.parent() and getattr(self.parent(), 'active_pdk', None):
                pdk_name = self.parent().active_pdk.get('name', '')
            elif self.project_config:
                pdk_name = self.project_config.get('pdk', '')
            site_name = SSAForge.get(pdk_name, "site") or "unithd"
        except Exception:
            pass

        helper_tcl = os.path.join(os.path.dirname(__file__), "silis_fp.tcl").replace("\\", "/")
        tcl = f'if {{[info procs create_fence] eq ""}} {{ source "{helper_tcl}" }}\n\n'
        tcl += "# === INITIALIZATION ===\n"
        tcl += f'initialize_floorplan -die_area "0 0 {die_w} {die_h}" -core_area "{core_x1} {core_y1} {core_x2} {core_y2}" -site {site_name}\n\n'
        
        has_macros = any(isinstance(item, MacroItem) for item in self.scene.items())
        if has_macros:
            tcl += "# === MACRO PLACEMENT ===\n"
            for item in self.scene.items():
                if isinstance(item, MacroItem):
                    ox = round(round(item.pos().x() / 0.005) * 0.005, 3)
                    oy = round(round(item.pos().y() / 0.005) * 0.005, 3)
                    halo_str = f" -halo {{{item.halo[0]} {item.halo[1]} {item.halo[2]} {item.halo[3]}}}" if any(x > 0 for x in item.halo) else ""
                    cell_str = f' -cell "{item.name}"' if item.name else ""
                    ori = item.orientation
                    if ori == "MX90": ori = "MXR90"
                    elif ori == "MY90": ori = "MYR90"
                    tcl += f'place_macro -inst "{item.inst_name}"{cell_str} -location {{{ox} {oy}}} -orient {ori}{halo_str}\n'

        # If Auto Place is checked with Hierarchical or Analytical mode, inject OpenROAD macro placer pass
        if getattr(self, 'chk_autoplace', None) and self.chk_autoplace.isChecked():
            curr_method = self.cmb_autoplace_method.currentText()
            if "Hierarchical" in curr_method:
                tcl += "\n# === OpenROAD Hierarchical RTL Macro Placer ===\n"
                tcl += "make_tracks\n"
                tcl += "catch { rtl_macro_placer -halo_width 10.0 -halo_height 10.0 -report_directory reports/rtlmp }\n"
            elif "Analytical" in curr_method:
                tcl += "\n# === OpenROAD Analytical TritonMacroPlace ===\n"
                tcl += "make_tracks\n"
                tcl += "catch { macro_placement -halo {10.0 10.0} }\n"
                    
        has_regions = any(isinstance(item, RegionItem) for item in self.scene.items())
        if has_regions:
            tcl += "\n# === REGIONS & FENCES ===\n"
            for item in self.scene.items():
                if isinstance(item, RegionItem):
                    cmd_name = "create_fence" if item.is_fence else "create_region"
                    type_str = "" if item.is_fence else " -type inclusive"
                    density_val = getattr(item, 'density', 0.60)
                    density_str = f" -density {density_val:.2f}"
                    halo_str = f" -halo {{{item.halo[0]} {item.halo[1]} {item.halo[2]} {item.halo[3]}}}" if any(x > 0 for x in item.halo) else ""
                    m_boxes = getattr(item, 'multi_boxes', [])
                    if m_boxes and len(m_boxes) > 1:
                        boxes_str = " ".join(f"{{{round(round(b[0] / 0.005) * 0.005, 3)} {round(round(b[1] / 0.005) * 0.005, 3)} {round(round(b[2] / 0.005) * 0.005, 3)} {round(round(b[3] / 0.005) * 0.005, 3)}}}" for b in m_boxes)
                        tcl += f'{cmd_name} -module "{item.module_name}" -boxes {{{boxes_str}}}{type_str}{density_str}{halo_str}\n'
                    else:
                        rx1 = round(round((item.rect().x() + item.pos().x()) / 0.005) * 0.005, 3)
                        ry1 = round(round((item.rect().y() + item.pos().y()) / 0.005) * 0.005, 3)
                        rx2 = round(round((rx1 + item.rect().width()) / 0.005) * 0.005, 3)
                        ry2 = round(round((ry1 + item.rect().height()) / 0.005) * 0.005, 3)
                        tcl += f'{cmd_name} -module "{item.module_name}" -box {{{rx1} {ry1} {rx2} {ry2}}}{type_str}{density_str}{halo_str}\n'

        has_blockages = any(isinstance(item, BlockageItem) for item in self.scene.items())
        if has_blockages:
            tcl += "\n# === BLOCKAGES ===\n"
            for item in self.scene.items():
                if isinstance(item, BlockageItem):
                    x1 = round(round((item.rect().x() + item.pos().x()) / 0.005) * 0.005, 3)
                    y1 = round(round((item.rect().y() + item.pos().y()) / 0.005) * 0.005, 3)
                    x2 = round(round((x1 + item.rect().width()) / 0.005) * 0.005, 3)
                    y2 = round(round((y1 + item.rect().height()) / 0.005) * 0.005, 3)
                    if item.btype == "Partial":
                        tcl += f"catch {{ create_blockage -region {{{x1} {y1} {x2} {y2}}} -max_density {item.pct} }}\n"
                    elif item.btype == "Soft":
                        tcl += f"catch {{ create_blockage -region {{{x1} {y1} {x2} {y2}}} -soft }}\n"
                    else:
                        tcl += f"catch {{ create_blockage -region {{{x1} {y1} {x2} {y2}}} }}\n"

        if apply:
            self.save_state()
            self.update_live_tcl()
            proj_root, base = self._get_project_context()
            def_abs_path = os.path.join(proj_root, "results", "temp.def").replace("\\", "/")
            
            if self.parent() and hasattr(self.parent(), 'term_log'):
                self.parent().term_log.append("[SYS] Applying Custom Floorplan...")
            # Use the live TCL instead so it includes everything correctly.
            final_tcl = self.live_tcl_edit.toPlainText() + f"\nwrite_def \"{def_abs_path}\"\nputs \"SILIS_FLOORPLAN_DONE\"\n"
            step_script = os.path.join(proj_root, "run_floorplan.tcl").replace("\\", "/")
            try:
                with open(step_script, 'w') as f:
                    f.write(final_tcl)
            except Exception:
                pass
            if self.parent() and hasattr(self.parent(), 'send_command_internal'):
                self.parent().send_command_internal(f'source "{step_script}"')
            self.accept()
        return tcl


def compute_peripheral_macro_placement(macros, die_w=1400.0, die_h=1400.0, margins=(20.0, 20.0, 20.0, 20.0), macro_sizes=None):
    """
    Computes strict non-overlapping peripheral macro placement for all macros.
    Places macros sequentially along periphery boundaries (Bottom, Right, Top, Left)
    with guaranteed channel clearances, halo margins, and zero overlaps.
    """
    if isinstance(margins, (int, float)):
        ml = mr = mb = mt = float(margins)
    elif len(margins) == 4:
        ml, mr, mb, mt = margins
    else:
        ml = mr = mb = mt = 20.0
        
    pad = 20.0
    macro_sizes = macro_sizes or {}

    core_x1 = ml
    core_y1 = mb
    core_x2 = die_w - mr
    core_y2 = die_h - mt

    # Placed bounding boxes list for overlap checking: [(x1, y1, x2, y2)]
    placed_boxes = []
    placed = []

    def _collides(bx1, by1, bx2, by2):
        for ox1, oy1, ox2, oy2 in placed_boxes:
            if not (bx2 <= ox1 or bx1 >= ox2 or by2 <= oy1 or by1 >= oy2):
                return True
        return False

    # Candidate perimeter slots
    for i, m in enumerate(macros):
        inst = m.get('inst_name') or m.get('inst')
        cell = m.get('master_name') or m.get('name') or m.get('cell') or ''
        def_w, def_h = macro_sizes.get(cell, (479.78, 397.5))
        w = m.get('w', def_w)
        h = m.get('h', def_h)
        orient = m.get('orient') or m.get('orientation', 'R0')
        halo = m.get('halo', [10, 10, 10, 10])
        hl, hr, hb, ht = halo[0], halo[1], halo[2], halo[3]

        swapped = ["R90", "R270", "MX90", "MY90", "MXR90", "MYR90"]
        eff_w = h if orient in swapped else w
        eff_h = w if orient in swapped else h

        total_w = eff_w + hl + hr
        total_h = eff_h + hb + ht

        # 4 Priority corners first:
        # Slot 0: Bottom-Left
        # Slot 1: Bottom-Right
        # Slot 2: Top-Left
        # Slot 3: Top-Right
        candidate_coords = [
            (core_x1 + pad + hl, core_y1 + pad + hb),
            (core_x2 - pad - eff_w - hr, core_y1 + pad + hb),
            (core_x1 + pad + hl, core_y2 - pad - eff_h - ht),
            (core_x2 - pad - eff_w - hr, core_y2 - pad - eff_h - ht),
        ]

        assigned_x = None
        assigned_y = None

        if i < len(candidate_coords):
            cx, cy = candidate_coords[i]
            bx1 = cx - hl
            by1 = cy - hb
            bx2 = cx + eff_w + hr
            by2 = cy + eff_h + ht
            if bx1 >= core_x1 and by1 >= core_y1 and bx2 <= core_x2 and by2 <= core_y2 and not _collides(bx1, by1, bx2, by2):
                assigned_x, assigned_y = cx, cy

        # If priority slot was taken or collided, find perimeter clearance along core edges
        if assigned_x is None:
            # 1. Try bottom edge running left-to-right
            step_x = core_x1 + pad + hl
            while step_x + eff_w + hr <= core_x2 - pad:
                bx1 = step_x - hl
                by1 = core_y1 + pad
                bx2 = step_x + eff_w + hr
                by2 = core_y1 + pad + total_h
                if not _collides(bx1, by1, bx2, by2):
                    assigned_x = step_x
                    assigned_y = core_y1 + pad + hb
                    break
                step_x += 20.0

        if assigned_x is None:
            # 2. Try top edge running left-to-right
            step_x = core_x1 + pad + hl
            while step_x + eff_w + hr <= core_x2 - pad:
                bx1 = step_x - hl
                by1 = core_y2 - pad - total_h
                bx2 = step_x + eff_w + hr
                by2 = core_y2 - pad
                if not _collides(bx1, by1, bx2, by2):
                    assigned_x = step_x
                    assigned_y = core_y2 - pad - eff_h - ht
                    break
                step_x += 20.0

        if assigned_x is None:
            # 3. Try left edge running bottom-to-top
            step_y = core_y1 + pad + hb
            while step_y + eff_h + ht <= core_y2 - pad:
                bx1 = core_x1 + pad
                by1 = step_y - hb
                bx2 = core_x1 + pad + total_w
                by2 = step_y + eff_h + ht
                if not _collides(bx1, by1, bx2, by2):
                    assigned_x = core_x1 + pad + hl
                    assigned_y = step_y
                    break
                step_y += 20.0

        if assigned_x is None:
            # 4. Try right edge running bottom-to-top
            step_y = core_y1 + pad + hb
            while step_y + eff_h + ht <= core_y2 - pad:
                bx1 = core_x2 - pad - total_w
                by1 = step_y - hb
                bx2 = core_x2 - pad
                by2 = step_y + eff_h + ht
                if not _collides(bx1, by1, bx2, by2):
                    assigned_x = core_x2 - pad - eff_w - hr
                    assigned_y = step_y
                    break
                step_y += 20.0

        # Fallback grid slot if all edges packed
        if assigned_x is None:
            assigned_x = core_x1 + pad + hl + ((i % 3) * (total_w + 20.0))
            assigned_y = core_y1 + pad + hb + ((i // 3) * (total_h + 20.0))

        assigned_x = max(core_x1 + hl, min(core_x2 - eff_w - hr, assigned_x))
        assigned_y = max(core_y1 + hb, min(core_y2 - eff_h - ht, assigned_y))

        assigned_x = round(round(assigned_x / 0.005) * 0.005, 3)
        assigned_y = round(round(assigned_y / 0.005) * 0.005, 3)

        placed_boxes.append((
            assigned_x - hl,
            assigned_y - hb,
            assigned_x + eff_w + hr,
            assigned_y + eff_h + ht
        ))

        placed.append({
            'name': cell,
            'inst_name': inst,
            'x': assigned_x,
            'y': assigned_y,
            'orientation': orient,
            'halo': halo,
            'w': w,
            'h': h,
            'list_text': f"[{inst}] ({cell})"
        })

    return die_w, die_h, placed


def generate_floorplan_tcl_from_data(die_area, core_margin, macros=None, regions=None, blockages=None, pdk_name=None, site=None):
    """
    Headless & programmatic ASIC floorplan TCL generator.
    Produces identical clean TCL to InteractiveFloorplannerWidget.
    """
    if isinstance(die_area, str):
        die_area = [float(x) for x in die_area.replace('"', '').replace(',', ' ').split()]
    else:
        die_area = [float(x) for x in die_area]

    macros = macros or []
    regions = regions or []
    blockages = blockages or []
    die_w = die_area[2] - die_area[0]
    die_h = die_area[3] - die_area[1]
    if isinstance(core_margin, (int, float)):
        cm_l = cm_r = cm_b = cm_t = float(core_margin)
    elif len(core_margin) == 4:
        cm_l, cm_r, cm_b, cm_t = core_margin
    else:
        cm_l = cm_r = cm_b = cm_t = 10.0
    core_x1 = die_area[0] + cm_l
    core_y1 = die_area[1] + cm_b
    core_x2 = die_area[2] - cm_r
    core_y2 = die_area[3] - cm_t

    site_name = site
    if not site_name:
        try:
            from pdkmanagers.pdk.manager import SSAForge
            site_name = SSAForge.get(pdk_name, "site") if pdk_name else "unithd"
        except Exception:
            site_name = "unithd"
    if not site_name:
        site_name = "unithd"

    helper_tcl = os.path.join(os.path.dirname(__file__), "silis_fp.tcl").replace("\\", "/")
    tcl = f'if {{[info procs create_fence] eq ""}} {{ source "{helper_tcl}" }}\n\n'
    tcl += "# === INITIALIZATION ===\n"
    tcl += f'initialize_floorplan -die_area "0 0 {die_w} {die_h}" -core_area "{core_x1} {core_y1} {core_x2} {core_y2}" -site {site_name}\n\n'

    if macros:
        tcl += "# === MACRO PLACEMENT ===\n"
        for m in macros:
            inst = m.get('inst') or m.get('inst_name')
            cell = m.get('cell') or m.get('name', '')
            if 'pos' in m:
                raw_x, raw_y = m['pos'][0], m['pos'][1]
            elif 'location' in m:
                raw_x, raw_y = m['location'][0], m['location'][1]
            else:
                raw_x, raw_y = m.get('x', 0.0), m.get('y', 0.0)

            # If coordinates are specified relative to core, shift to absolute die coordinates
            if raw_x < core_x1 and (raw_x + core_x1) < core_x2:
                raw_x += core_x1
            if raw_y < core_y1 and (raw_y + core_y1) < core_y2:
                raw_y += core_y1
            ox = round(round(raw_x / 0.005) * 0.005, 3)
            oy = round(round(raw_y / 0.005) * 0.005, 3)
            orient = m.get('orient') or m.get('orientation', 'R0')
            if orient == "MX90": orient = "MXR90"
            elif orient == "MY90": orient = "MYR90"
            halo = m.get('halo', [0, 0, 0, 0])
            if isinstance(halo, (list, tuple)):
                if len(halo) == 2:
                    halo = [halo[0], halo[1], halo[0], halo[1]]
                elif len(halo) < 4:
                    halo = list(halo) + [0] * (4 - len(halo))
            elif isinstance(halo, (int, float)):
                halo = [halo, halo, halo, halo]
            else:
                halo = [0, 0, 0, 0]
            halo_str = f" -halo {{{halo[0]} {halo[1]} {halo[2]} {halo[3]}}}" if any(x > 0 for x in halo) else ""
            cell_str = f' -cell "{cell}"' if cell else ""
            tcl += f'place_macro -inst "{inst}"{cell_str} -location {{{ox} {oy}}} -orient {orient}{halo_str}\n'

    # Collect all regions and blockages (GUI saves regions inside blockages array with is_region=True)
    final_regions = list(regions)
    final_blockages = []
    for b in blockages:
        if b.get('is_region'):
            final_regions.append(b)
        else:
            final_blockages.append(b)

    # Check if any regions have is_autoplace: True or missing boxes
    autoplace_needed = any(r.get('is_autoplace', False) or ('box' not in r and 'rect' not in r and 'x' not in r) for r in final_regions)
    if autoplace_needed:
        try:
            try:
                from backendflow.floorplanner.region_autoplacer import HierarchicalAutoRegionPlacer
            except ImportError:
                try:
                    from silis.backendflow.floorplanner.region_autoplacer import HierarchicalAutoRegionPlacer
                except ImportError:
                    from .region_autoplacer import HierarchicalAutoRegionPlacer
            from PyQt6.QtCore import QRectF
            placer_regions = []
            for r in final_regions:
                mod = r.get('module') or r.get('module_name')
                w = r.get('w', r.get('width', 150.0))
                h = r.get('h', r.get('height', 150.0))
                locked = r.get('locked', r.get('lock', False))
                is_fence = r.get('is_fence', True) if r.get('type') != 'inclusive' else False
                placer_regions.append({
                    'module': mod,
                    'width': w,
                    'height': h,
                    'locked': locked,
                    'is_fence': is_fence,
                    'x': r.get('x', 0.0),
                    'y': r.get('y', 0.0)
                })

            placer = HierarchicalAutoRegionPlacer(
                core_rect=QRectF(core_x1, core_y1, core_x2 - core_x1, core_y2 - core_y1),
                die_rect=QRectF(0, 0, die_w, die_h),
                macros=macros,
                regions=placer_regions,
                blockages=[QRectF(b['box'][0], b['box'][1], b['box'][2]-b['box'][0], b['box'][3]-b['box'][1]) for b in final_blockages if 'box' in b],
                allow_rotation=True,
                ignore_narrow_corridors=True
            )
            sol = placer.solve()
            for r in final_regions:
                mod = r.get('module') or r.get('module_name')
                if mod in sol['placements']:
                    pbox = sol['placements'][mod]
                    r['box'] = [pbox.x(), pbox.y(), pbox.x() + pbox.width(), pbox.y() + pbox.height()]
        except Exception as e:
            print(f"[FloorplanTCL] Warning running headless auto-placement: {e}")

    if final_regions:
        tcl += "\n# === REGIONS & FENCES ===\n"
        for r in final_regions:
            mod = r.get('module') or r.get('module_name')
            if 'box' in r and r['box'] is not None:
                box = r['box']
            elif 'rect' in r and r['rect'] is not None:
                box = r['rect']
            else:
                rx = r.get('x', 0.0)
                ry = r.get('y', 0.0)
                rw = r.get('w', 100.0)
                rh = r.get('h', 100.0)
                box = [rx, ry, rx + rw, ry + rh]
            is_fence = r.get('is_fence', True) if r.get('type') != 'inclusive' else False
            density = r.get('density', 0.60)
            halo = r.get('halo', [0, 0, 0, 0])
            rx1 = round(round(box[0] / 0.005) * 0.005, 3)
            ry1 = round(round(box[1] / 0.005) * 0.005, 3)
            rx2 = round(round(box[2] / 0.005) * 0.005, 3)
            ry2 = round(round(box[3] / 0.005) * 0.005, 3)
            cmd_name = "create_fence" if is_fence else "create_region"
            type_str = "" if is_fence else " -type inclusive"
            halo_str = f" -halo {{{halo[0]} {halo[1]} {halo[2]} {halo[3]}}}" if any(x > 0 for x in halo) else ""
            m_boxes = r.get('multi_boxes', [])
            if m_boxes and len(m_boxes) > 1:
                boxes_str = " ".join(f"{{{round(round(b[0] / 0.005) * 0.005, 3)} {round(round(b[1] / 0.005) * 0.005, 3)} {round(round(b[2] / 0.005) * 0.005, 3)} {round(round(b[3] / 0.005) * 0.005, 3)}}}" for b in m_boxes)
                tcl += f'{cmd_name} -module "{mod}" -boxes {{{boxes_str}}}{type_str} -density {density:.2f}{halo_str}\n'
            else:
                tcl += f'{cmd_name} -module "{mod}" -box {{{rx1} {ry1} {rx2} {ry2}}}{type_str} -density {density:.2f}{halo_str}\n'

    if final_blockages:
        tcl += "\n# === BLOCKAGES ===\n"
        for b in final_blockages:
            if 'box' in b and b['box'] is not None:
                box = b['box']
            elif 'rect' in b and b['rect'] is not None:
                box = b['rect']
            else:
                bx = b.get('x', 0.0)
                by = b.get('y', 0.0)
                bw = b.get('w', 100.0)
                bh = b.get('h', 100.0)
                box = [bx, by, bx + bw, by + bh]
            btype = b.get('type') or b.get('btype', 'hard').capitalize()
            density = b.get('density') or b.get('pct', 50)
            x1 = round(round(box[0] / 0.005) * 0.005, 3)
            y1 = round(round(box[1] / 0.005) * 0.005, 3)
            x2 = round(round(box[2] / 0.005) * 0.005, 3)
            y2 = round(round(box[3] / 0.005) * 0.005, 3)
            if btype.lower() == "partial":
                tcl += f"catch {{ create_blockage -region {{{x1} {y1} {x2} {y2}}} -max_density {density} }}\n"
            elif btype.lower() == "soft":
                tcl += f"catch {{ create_blockage -region {{{x1} {y1} {x2} {y2}}} -soft }}\n"
            else:
                tcl += f"catch {{ create_blockage -region {{{x1} {y1} {x2} {y2}}} }}\n"

    return tcl

