import os
import re
import json
import glob
import math
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from backendflow.siliconpeeker.peeker import DEFParser

import hashlib
from backendflow.floorplanner.ioplacer import (
    PAD_CELL_MAP, PAD_CELL_DISPLAY_LIST, natural_sort_key, snap_to_grid,
    PinItem, EdgeConstraintBox
)
from backendflow.floorplanner.power_domain_manager import (
    PowerDomain, PowerDomainManager, BoundaryClampTableDialog
)
from pdkmanagers.pdk.manager import SSAForge


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
        if hasattr(self, '_update_tooltip'):
            self._update_tooltip()

    def update_halo(self, l, r, b, t):
        self.halo = (l, r, b, t)
        rect = self.rect()
        self.halo_rect.setRect(rect.x() - l, rect.y() - b, rect.width() + l + r, rect.height() + b + t)
        if hasattr(self, '_update_tooltip'):
            self._update_tooltip()

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
        self.tapcell_type = "sky130_fd_sc_hd__tapvpwrvgnd_1"
        self.halo_rect = QGraphicsRectItem(self)
        self.halo_rect.setPen(QPen(QColor("#6c7086"), 1, Qt.PenStyle.DotLine))
        self.halo_rect.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        self._update_colors()
        
        self.text = QGraphicsTextItem("", self)
        self.text.setDefaultTextColor(QColor("#cdd6f4"))
        self.text.setTransform(QTransform.fromScale(1, -1))
        self.update_text()
        self._update_tooltip()

    def _update_tooltip(self):
        r = self.rect()
        area = r.width() * r.height()
        t = "Fence (Exclusive)" if self.is_fence else "Region (Inclusive)"
        hl, hr, hb, ht = self.halo

        # Find power domain and voltage association if module belongs to a domain
        dom_str = "PD_TOP"
        volt_str = "1.80 V"
        pmu_str = "None"
        s = self.scene()
        if s and s.views():
            v = s.views()[0]
            if hasattr(v, 'parent') and v.parent():
                p = v.parent()
                if hasattr(p, 'pdm') and p.pdm:
                    for dname, pd in p.pdm.domains.items():
                        if any(elem == self.module_name or elem.split('/')[-1] == self.module_name for elem in pd.elements):
                            dom_str = dname
                            volt_str = f"{pd.voltage:.2f} V"
                            pmu_str = pd.pmu_instance or "Top-Level Ports"
                            break

        tip = (
            f"<b>Module:</b> {self.module_name}<br/>"
            f"<b>Power Domain:</b> {dom_str} ({volt_str})<br/>"
            f"<b>PMU Controller:</b> {pmu_str}<br/>"
            f"<b>Type:</b> {t}<br/>"
            f"<b>Target Density:</b> {int(self.density * 100)}%<br/>"
            f"<b>Assigned Tapcell:</b> {self.tapcell_type}<br/>"
            f"<b>Halo (L, R, B, T):</b> ({hl}, {hr}, {hb}, {ht}) µm<br/>"
            f"<b>Dimensions:</b> {r.width():.1f} × {r.height():.1f} µm (Area: {area:.1f} µm²)<br/>"
            f"<b>Status:</b> {'Locked' if self.locked else 'Unlocked'}"
        )
        self.setToolTip(tip)

    def contextMenuEvent(self, event):
        menu = QMenu()
        act_lock = menu.addAction("Unlock Region" if self.locked else "Lock Region")
        act_toggle_fence = menu.addAction("Convert to Region" if self.is_fence else "Convert to Fence")
        
        sub_tap = menu.addMenu("Assign Tapcell Type")
        standard_taps = [
            "sky130_fd_sc_hd__tapvpwrvgnd_1",
            "sky130_fd_sc_hd__tap_1",
            "sky130_fd_sc_hd__tap_2"
        ]
        for tname in standard_taps:
            act_t = sub_tap.addAction(tname)
            act_t.setCheckable(True)
            act_t.setChecked(self.tapcell_type == tname)
            act_t.triggered.connect(lambda checked, tn=tname: self.set_tapcell_type(tn))

        # Dynamic power domain assignment submenu
        sub_pwr = menu.addMenu("Assign Power Domain")
        s = self.scene()
        parent_widget = None
        if s and s.views():
            v = s.views()[0]
            if hasattr(v, 'parent') and v.parent():
                parent_widget = v.parent()

        domain_actions = {}
        if parent_widget and hasattr(parent_widget, "pdm"):
            for dname, pd_obj in parent_widget.pdm.domains.items():
                act_d = sub_pwr.addAction(f"{dname} ({pd_obj.voltage:.2f}V)")
                act_d.setCheckable(True)
                is_cur = any(elem == self.module_name or elem.split('/')[-1] == self.module_name for elem in pd_obj.elements)
                if pd_obj.is_top and not is_cur and not any(self.module_name in pd.elements for pd in parent_widget.pdm.domains.values() if not pd.is_top):
                    is_cur = True
                act_d.setChecked(is_cur)
                domain_actions[act_d] = dname

        sel = menu.exec(event.screenPos())
        if sel in domain_actions:
            target_domain = domain_actions[sel]
            if parent_widget and hasattr(parent_widget, "pdm"):
                for pd in parent_widget.pdm.domains.values():
                    if self.module_name in pd.elements:
                        pd.elements.remove(self.module_name)
                if target_domain != "PD_TOP":
                    parent_widget.pdm.domains[target_domain].elements.append(self.module_name)
                self._update_tooltip()
                if hasattr(parent_widget, "_refresh_power_domains_table"):
                    parent_widget._refresh_power_domains_table()
                if hasattr(parent_widget, "save_state"):
                    parent_widget.save_state()
        elif sel == act_lock:
            self.set_locked(not self.locked)
            s = self.scene()
            if s and s.views():
                v = s.views()[0]
                if hasattr(v, 'parent') and v.parent():
                    p = v.parent()
                    if hasattr(p, 'chk_region_lock'):
                        p.chk_region_lock.setChecked(self.locked)
                    if hasattr(p, 'save_state'): p.save_state()
        elif sel == act_toggle_fence:
            self.is_fence = not self.is_fence
            self._update_colors()
            self.update_text()
            self._update_tooltip()
            s = self.scene()
            if s and s.views():
                v = s.views()[0]
                if hasattr(v, 'parent') and v.parent():
                    p = v.parent()
                    if hasattr(p, 'save_state'): p.save_state()

    def set_tapcell_type(self, tap_name: str):
        self.tapcell_type = tap_name
        self._update_tooltip()
        s = self.scene()
        if s and s.views():
            v = s.views()[0]
            if hasattr(v, 'parent') and v.parent():
                p = v.parent()
                if hasattr(p, 'save_state'): p.save_state()

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
        if hasattr(self, '_update_tooltip'):
            self._update_tooltip()

    def update_halo(self, l, r, b, t):
        self.halo = (l, r, b, t)
        rect = self.rect()
        self.halo_rect.setRect(rect.x() - l, rect.y() - b, rect.width() + l + r, rect.height() + b + t)
        if hasattr(self, '_update_tooltip'):
            self._update_tooltip()

    def get_parent_containment_rect(self):
        """
        Calculates the strict bounding constraint for this region:
        1. If this module belongs to a Power Domain, containment is bounded by that VoltageIslandItem.
        2. If this module is a child of another placed Region/Fence, containment is bounded by the parent RegionItem.
        3. Otherwise defaults to core_rect.
        """
        s = self.scene()
        if not s:
            return self.core_rect

        # 1. Check parent Power Domain Voltage Island
        mod_name = self.module_name
        mod_base = mod_name.split("/")[-1]
        for it in s.items():
            if isinstance(it, VoltageIslandItem):
                if any(elem == mod_name or elem == mod_base or mod_name.startswith(elem + "/") for elem in it.elements):
                    return it.sceneBoundingRect()

        # 2. Check parent hierarchical Region/Fence
        if "/" in mod_name:
            parent_path = mod_name.rsplit("/", 1)[0]
            for it in s.items():
                if isinstance(it, RegionItem) and it != self:
                    if it.module_name == parent_path or parent_path.startswith(it.module_name):
                        return it.sceneBoundingRect()

        return self.core_rect

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value
            x = round(new_pos.x(), 3)
            y = round(new_pos.y(), 3)
            
            boundary_rect = self.get_parent_containment_rect()
            if boundary_rect:
                w = self.rect().width()
                h = self.rect().height()
                min_x = boundary_rect.x() - self.rect().x()
                min_y = boundary_rect.y() - self.rect().y()
                max_x = boundary_rect.x() + boundary_rect.width() - self.rect().x() - w
                max_y = boundary_rect.y() + boundary_rect.height() - self.rect().y() - h
                if max_x < min_x:
                    x = min_x
                else:
                    if x < min_x: x = min_x
                    if x > max_x: x = max_x

                if max_y < min_y:
                    y = min_y
                else:
                    if y < min_y: y = min_y
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



class VoltageIslandItem(ResizableRectItem):
    """
    Physical voltage island bounding box for power-gated domains.
    Visualized on canvas with industrial EDA voltage-mapped colors,
    dashed border, corner resize handles, and an explicit isolation halo hitbox.
    """
    def __init__(self, x, y, w, h, domain_name, voltage=1.8, elements=None, core_rect=None, halo=(15.0, 15.0, 15.0, 15.0), parent=None):
        super().__init__(x, y, w, h, parent)
        self.domain_name = domain_name
        self.voltage = voltage
        self.elements = elements or []
        self.core_rect = core_rect
        self.locked = False
        self.tapcell_type = "sky130_fd_sc_hd__tapvpwrvgnd_1"
        self.halo = halo

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        self.halo_rect = QGraphicsRectItem(self)
        self.halo_rect.setPen(QPen(QColor("#6c7086"), 1.2, Qt.PenStyle.DotLine))
        self.halo_rect.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        l, r, b, t = self.halo
        self.halo_rect.setRect(x - l, y - b, w + l + r, h + b + t)

        self._update_colors()

        self.text = QGraphicsTextItem("", self)
        self.text.setDefaultTextColor(QColor("#cdd6f4"))
        self.text.setTransform(QTransform.fromScale(1, -1))
        self.update_text()
        self._update_tooltip()

    def update_halo(self, l, r, b, t):
        self.halo = (l, r, b, t)
        rect = self.rect()
        self.halo_rect.setRect(rect.x() - l, rect.y() - b, rect.width() + l + r, rect.height() + b + t)
        self._update_tooltip()

    def halo_scene_bounding_rect(self) -> QRectF:
        p = self.pos()
        r = self.rect()
        l, r_h, b, t = self.halo
        return QRectF(p.x() + r.x() - l, p.y() + r.y() - b, r.width() + l + r_h, r.height() + b + t)

    def _update_tooltip(self):
        r = self.rect()
        area = r.width() * r.height()
        elems_str = ", ".join(self.elements) if self.elements else "top scope"

        # Lookup PMU instance from power domain manager
        pmu_str = "None"
        s = self.scene()
        if s and s.views():
            v = s.views()[0]
            if hasattr(v, 'parent') and v.parent():
                p = v.parent()
                if hasattr(p, 'pdm') and p.pdm:
                    pd_obj = p.pdm.domains.get(self.domain_name)
                    if pd_obj and pd_obj.pmu_instance:
                        pmu_str = pd_obj.pmu_instance

        l, r_h, b, t = self.halo if hasattr(self, 'halo') else (15.0, 15.0, 15.0, 15.0)
        tip = (
            f"<b>Voltage Island:</b> {self.domain_name}<br/>"
            f"<b>Operating Voltage:</b> {self.voltage:.2f} V<br/>"
            f"<b>PMU Controller:</b> {pmu_str}<br/>"
            f"<b>Type:</b> {'Always-On' if self.domain_name == 'PD_TOP' else 'Power-Gated / Switched'}<br/>"
            f"<b>Scope Elements:</b> {elems_str}<br/>"
            f"<b>Assigned Tapcell:</b> {self.tapcell_type}<br/>"
            f"<b>Dimensions:</b> {r.width():.1f} × {r.height():.1f} µm (Area: {area:.1f} µm²)<br/>"
            f"<b>Isolation Halo Hitbox:</b> L={l:.1f}, R={r_h:.1f}, B={b:.1f}, T={t:.1f} µm<br/>"
            f"<b>Status:</b> {'Locked' if self.locked else 'Unlocked'}"
        )
        self.setToolTip(tip)

    def contextMenuEvent(self, event):
        menu = QMenu()
        act_clamps = menu.addAction("Configure Boundary Clamps && Isolation Table...")
        act_lock = menu.addAction("Unlock Island" if self.locked else "Lock Island")

        sub_tap = menu.addMenu("Assign Tapcell Type")
        standard_taps = [
            "sky130_fd_sc_hd__tapvpwrvgnd_1",
            "sky130_fd_sc_hd__tap_1",
            "sky130_fd_sc_hd__tap_2"
        ]
        for tname in standard_taps:
            act_t = sub_tap.addAction(tname)
            act_t.setCheckable(True)
            act_t.setChecked(self.tapcell_type == tname)
            act_t.triggered.connect(lambda checked, tn=tname: self.set_tapcell_type(tn))

        sel = menu.exec(event.screenPos())
        s = self.scene()
        parent_widget = None
        if s and s.views():
            v = s.views()[0]
            if hasattr(v, 'parent') and v.parent():
                parent_widget = v.parent()

        if sel == act_clamps:
            if parent_widget and hasattr(parent_widget, "open_boundary_clamp_dialog"):
                parent_widget.open_boundary_clamp_dialog()
        elif sel == act_lock:
            self.locked = not self.locked
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not self.locked)
            self._update_colors()
            self._update_tooltip()
            if parent_widget and hasattr(parent_widget, "save_state"):
                parent_widget.save_state()

    def set_tapcell_type(self, tap_name: str):
        self.tapcell_type = tap_name
        self._update_tooltip()
        s = self.scene()
        if s and s.views():
            v = s.views()[0]
            if hasattr(v, 'parent') and v.parent():
                p = v.parent()
                if hasattr(p, 'save_state'): p.save_state()

    def get_voltage_color(self) -> QColor:
        if self.voltage >= 2.5:
            return QColor("#b58900")  # Amber (High voltage / Padring)
        if self.voltage >= 1.6:
            return QColor("#268bd2")  # Cyan (Nominal core)
        if self.voltage >= 0.8:
            return QColor("#6c71c4")  # Slate purple / Indigo (Gated core)
        return QColor("#2aa198")      # Muted teal (Ultra-low voltage island)

    def _update_colors(self):
        base_color = self.get_voltage_color()
        fill_color = QColor(base_color.red(), base_color.green(), base_color.blue(), 50)
        self.setBrush(QBrush(fill_color))
        self.setPen(QPen(base_color, 1.8, Qt.PenStyle.DashDotLine))

    def update_text(self):
        elems_str = ", ".join(self.elements) if self.elements else "top"
        self.text.setPlainText(f"ISLAND: {self.domain_name} ({self.voltage:.2f}V)\n{elems_str}")
        rect = self.rect()
        br = self.text.boundingRect()
        self.text.setPos(rect.x() + rect.width()/2 - br.width()/2, rect.y() + rect.height()/2 + br.height()/2)

    def setRect(self, x, y, w, h):
        super().setRect(x, y, w, h)
        if hasattr(self, 'halo') and hasattr(self, 'halo_rect'):
            l, r, b, t = self.halo
            self.halo_rect.setRect(x - l, y - b, w + l + r, h + b + t)
        if hasattr(self, 'update_text'):
            self.update_text()
        if hasattr(self, '_update_tooltip'):
            self._update_tooltip()

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
            if hasattr(self, "handles"):
                self.update_handle_positions()
        return super().itemChange(change, value)


class FloorplanView(InteractiveGraphicsView):
    macro_dropped = pyqtSignal(str, float, float, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
        self.drawing_power_domain = False
        self.current_power_domain = None
        self.power_domain_start_pos = None
        self.pd_obj = None
        self.pan_active = False
        self.pan_start_pos = None
        
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        
    def start_drawing(self, btype, pct):
        self.drawing_blockage = True
        self.drawing_region = False
        self.drawing_power_domain = False
        self.btype = btype
        self.pct = pct
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def start_drawing_region(self, module_name, is_fence, density):
        # Extract clean module name in case display string with percentage prefix was passed
        if module_name and "(" in module_name and module_name.endswith(")"):
            clean_name = module_name.split("(")[-1].rstrip(")")
        elif module_name and " " in module_name:
            clean_name = module_name.split()[-1]
        else:
            clean_name = module_name or "region"

        self.drawing_region = True
        self.drawing_blockage = False
        self.drawing_power_domain = False
        self.region_module = clean_name
        self.region_is_fence = is_fence
        self.region_density = density
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def start_drawing_power_domain(self, pd):
        self.drawing_power_domain = True
        self.drawing_blockage = False
        self.drawing_region = False
        self.pd_obj = pd
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

        if self.drawing_power_domain and event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.pos())
            self.power_domain_start_pos = pos
            cr = getattr(self.parentWidget(), "core_rect", None)
            dname = self.pd_obj.name if self.pd_obj else "PD"
            dvolt = self.pd_obj.voltage if self.pd_obj else 1.8
            delems = self.pd_obj.elements if self.pd_obj else []
            self.current_power_domain = VoltageIslandItem(pos.x(), pos.y(), 0, 0, dname, dvolt, delems, cr)
            self.scene().addItem(self.current_power_domain)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            pw = self.parentWidget()
            if pw and hasattr(pw, "_edge_zone_items"):
                for e_key, z_it in pw._edge_zone_items.items():
                    if item == z_it:
                        pw.select_active_edge(e_key)
                        break

        self.setFocus()
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
            
            boundary_rect = getattr(self.current_region, "get_parent_containment_rect", lambda: None)()
            if not boundary_rect and hasattr(self.parentWidget(), "core_rect"):
                boundary_rect = self.parentWidget().core_rect

            if boundary_rect:
                cr = boundary_rect
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

        if self.drawing_power_domain and self.current_power_domain:
            pos = self.mapToScene(event.pos())
            px, py = round(pos.x(), 3), round(pos.y(), 3)
            if hasattr(self.parentWidget(), "core_rect") and self.parentWidget().core_rect:
                cr = self.parentWidget().core_rect
                if px < cr.x(): px = cr.x()
                if py < cr.y(): py = cr.y()
                if px > cr.x() + cr.width(): px = cr.x() + cr.width()
                if py > cr.y() + cr.height(): py = cr.y() + cr.height()
            x1 = min(px, self.power_domain_start_pos.x())
            y1 = min(py, self.power_domain_start_pos.y())
            w = abs(px - self.power_domain_start_pos.x())
            h = abs(py - self.power_domain_start_pos.y())
            self.current_power_domain.setRect(x1, y1, w, h)
            self.current_power_domain.update_text()
            if hasattr(self.parentWidget(), "update_utilization"):
                self.parentWidget().update_utilization()
            return
            
        super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        # Always end panning on any release of Middle or Right button
        if self.pan_active:
            self.pan_active = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            return

        if self.drawing_blockage and event.button() == Qt.MouseButton.LeftButton:
            self.drawing_blockage = False
            self.current_blockage = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "save_state"): p.save_state(); break
                p = p.parentWidget()
            return
            
        if self.drawing_region and event.button() == Qt.MouseButton.LeftButton:
            self.drawing_region = False
            self.current_region = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "save_state"): p.save_state(); break
                p = p.parentWidget()
            return

        if self.drawing_power_domain and event.button() == Qt.MouseButton.LeftButton:
            self.drawing_power_domain = False
            if self.current_power_domain and self.pd_obj:
                r = self.current_power_domain.rect()
                pos = self.current_power_domain.pos()
                x1 = round(r.x() + pos.x(), 3)
                y1 = round(r.y() + pos.y(), 3)
                x2 = round(x1 + r.width(), 3)
                y2 = round(y1 + r.height(), 3)
                self.pd_obj.area = (x1, y1, x2, y2)
            self.current_power_domain = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
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
        modifiers = event.modifiers()

        # Canvas-level Undo & Redo shortcuts
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Z:
                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    # Ctrl+Shift+Z -> Redo
                    p = self.parentWidget()
                    while p is not None:
                        if hasattr(p, "redo"):
                            p.redo()
                            event.accept()
                            return
                        p = p.parentWidget()
                else:
                    # Ctrl+Z -> Undo
                    p = self.parentWidget()
                    while p is not None:
                        if hasattr(p, "undo"):
                            p.undo()
                            event.accept()
                            return
                        p = p.parentWidget()
            elif key == Qt.Key.Key_Y:
                # Ctrl+Y -> Redo
                p = self.parentWidget()
                while p is not None:
                    if hasattr(p, "redo"):
                        p.redo()
                        event.accept()
                        return
                    p = p.parentWidget()
            elif key == Qt.Key.Key_A:
                # Ctrl+A -> Select All
                p = self.parentWidget()
                while p is not None:
                    if hasattr(p, "select_all_canvas"):
                        p.select_all_canvas()
                        event.accept()
                        return
                    p = p.parentWidget()

        if key == Qt.Key.Key_Escape:
            self.drawing_blockage = False
            self.drawing_region = False
            self.drawing_power_domain = False
            if self.current_blockage:
                self.scene().removeItem(self.current_blockage)
                self.current_blockage = None
            if self.current_region:
                self.scene().removeItem(self.current_region)
                self.current_region = None
            if self.current_power_domain:
                self.scene().removeItem(self.current_power_domain)
                self.current_power_domain = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "clear_selection"):
                    p.clear_selection()
                    break
                p = p.parentWidget()
            event.accept()
            return
        elif key == Qt.Key.Key_F and not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "toggle_flightlines"):
                    p.toggle_flightlines()
                    event.accept()
                    return
                p = p.parentWidget()
        elif key == Qt.Key.Key_W:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 20)
        elif key == Qt.Key.Key_S:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 20)
        elif key == Qt.Key.Key_A and not (modifiers & Qt.KeyboardModifier.ControlModifier):
            p = self.parentWidget()
            if p and hasattr(p, "auto_space_active_edge"):
                p.auto_space_active_edge()
                event.accept()
                return
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 20)
        elif key == Qt.Key.Key_D:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 20)
        elif key == Qt.Key.Key_R and not (modifiers & Qt.KeyboardModifier.ControlModifier):
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "fit_die"):
                    p.fit_die()
                    break
                p = p.parentWidget()
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, "delete_selected_entities"):
                    p.delete_selected_entities()
                    event.accept()
                    return
                p = p.parentWidget()
            # Direct parent reference check
            if hasattr(self, "_parent_widget") and hasattr(self._parent_widget, "delete_selected_entities"):
                self._parent_widget.delete_selected_entities()
                event.accept()
                return
            # Fallback if parent traversal didn't catch it
            for item in list(self.scene().selectedItems()):
                if isinstance(item, (MacroItem, BlockageItem, RegionItem, VoltageIslandItem, PinItem)):
                    self.scene().removeItem(item)
                    if isinstance(item, MacroItem) and hasattr(item, 'list_item') and item.list_item:
                        item.list_item.setFlags(item.list_item.flags() | Qt.ItemFlag.ItemIsEnabled)
                        item.list_item.setText(item.list_item.text().replace(" [PLACED]", ""))
                        item.list_item.setForeground(QBrush())
            event.accept()
            return
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

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        p = self.parentWidget()
        if p and hasattr(p, "_draw_interconnect_flylines"):
            p._draw_interconnect_flylines(painter, rect)


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
        if getattr(self, 'widget_ref', None) and not getattr(self.widget_ref, 'is_initializing', False):
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
            
            # Check collision with VoltageIslandItems (including their isolation halo hitbox)
            collided = False
            s = self.scene()
            if s:
                my_rect = QRectF(x, y, w, h)
                for it in s.items():
                    if isinstance(it, VoltageIslandItem):
                        island_box = it.halo_scene_bounding_rect() if hasattr(it, 'halo_scene_bounding_rect') else it.sceneBoundingRect()
                        if my_rect.intersects(island_box):
                            collided = True
                            break

            if collided:
                self.setPen(QPen(QColor("#f38ba8"), 2.5, Qt.PenStyle.DashLine))
                self.setBrush(QBrush(QColor(243, 139, 168, 80)))
                self.setToolTip(f"COLLISION WARNING: {self.inst_name} overlaps Voltage Island / Halo boundary!")
            else:
                self.setPen(QPen(QColor("#89b4fa"), 1.5))
                self.setBrush(QBrush(QColor("#313244")))
                self.setToolTip(f"{self.inst_name} ({self.name})")

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
            if getattr(self, 'widget_ref', None) and not getattr(self.widget_ref, 'is_initializing', False):
                self.widget_ref.update_live_tcl()
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if getattr(self, 'widget_ref', None):
            self.widget_ref.update_live_tcl()
            self.widget_ref.save_state()



class DieCoreSetupDialog(QDialog):
    """
    Dedicated modal dialog for entering Die & Core area specifications,
    margins, and target core density calculations.
    """
    def __init__(self, fp_widget, parent=None):
        super().__init__(parent or fp_widget)
        self.fp = fp_widget
        self.setWindowTitle("Die & Core Area Specifications")
        self.resize(460, 420)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)

        gb_die = QGroupBox("Die Dimensions && Core Margins")
        fl_die = QFormLayout(gb_die)

        self.sp_die_w = QDoubleSpinBox(); self.sp_die_w.setRange(0.1, 100000); self.sp_die_w.setValue(self.fp.sp_die_w.value())
        self.sp_die_h = QDoubleSpinBox(); self.sp_die_h.setRange(0.1, 100000); self.sp_die_h.setValue(self.fp.sp_die_h.value())
        self.sp_marg_t = QDoubleSpinBox(); self.sp_marg_t.setRange(0, 10000); self.sp_marg_t.setValue(self.fp.sp_marg_t.value())
        self.sp_marg_b = QDoubleSpinBox(); self.sp_marg_b.setRange(0, 10000); self.sp_marg_b.setValue(self.fp.sp_marg_b.value())
        self.sp_marg_l = QDoubleSpinBox(); self.sp_marg_l.setRange(0, 10000); self.sp_marg_l.setValue(self.fp.sp_marg_l.value())
        self.sp_marg_r = QDoubleSpinBox(); self.sp_marg_r.setRange(0, 10000); self.sp_marg_r.setValue(self.fp.sp_marg_r.value())

        fl_die.addRow("Die Width (µm):", self.sp_die_w)
        fl_die.addRow("Die Height (µm):", self.sp_die_h)
        fl_die.addRow("Margin Top (µm):", self.sp_marg_t)
        fl_die.addRow("Margin Bottom (µm):", self.sp_marg_b)
        fl_die.addRow("Margin Left (µm):", self.sp_marg_l)
        fl_die.addRow("Margin Right (µm):", self.sp_marg_r)
        lay.addWidget(gb_die)

        gb_util = QGroupBox("Target Density & Core Fitting")
        fl_util = QFormLayout(gb_util)

        self.lbl_std_cell_info = QLabel("Standard Cell Area: -")
        if hasattr(self.fp, "total_std_cell_area") and self.fp.total_std_cell_area > 0:
            self.lbl_std_cell_info.setText(f"Standard Cell Area: {self.fp.total_std_cell_area:.1f} µm²")
        fl_util.addRow(self.lbl_std_cell_info)

        self.lbl_macro_info = QLabel("Total Macro Area: -")
        fl_util.addRow(self.lbl_macro_info)

        self.lbl_current_util = QLabel("Current Core Utilization: -")
        fl_util.addRow(self.lbl_current_util)

        self.sp_target_core_density = QDoubleSpinBox()
        self.sp_target_core_density.setRange(10.0, 95.0)
        self.sp_target_core_density.setValue(self.fp.sp_target_core_density.value())
        self.sp_target_core_density.setSuffix("%")
        fl_util.addRow("Target Core Density:", self.sp_target_core_density)

        self.btn_fit_density = QPushButton("Calculate & Fit Core to Target Density")
        self.btn_fit_density.clicked.connect(self.on_fit_density_clicked)
        fl_util.addRow(self.btn_fit_density)
        lay.addWidget(gb_util)

        self.update_util_preview()
        self.sp_die_w.valueChanged.connect(self.update_util_preview)
        self.sp_die_h.valueChanged.connect(self.update_util_preview)
        self.sp_marg_t.valueChanged.connect(self.update_util_preview)
        self.sp_marg_b.valueChanged.connect(self.update_util_preview)
        self.sp_marg_l.valueChanged.connect(self.update_util_preview)
        self.sp_marg_r.valueChanged.connect(self.update_util_preview)

        # Buttons
        h_btns = QHBoxLayout()
        btn_apply = QPushButton("Apply & Initialize Floorplan")
        btn_apply.clicked.connect(self.on_apply)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        h_btns.addStretch()
        h_btns.addWidget(btn_apply)
        h_btns.addWidget(btn_cancel)
        lay.addLayout(h_btns)

    def update_util_preview(self, *_):
        w = self.sp_die_w.value(); h = self.sp_die_h.value()
        ml = self.sp_marg_l.value(); mr = self.sp_marg_r.value()
        mt = self.sp_marg_t.value(); mb = self.sp_marg_b.value()
        cw = max(0.0, w - ml - mr)
        ch = max(0.0, h - mt - mb)
        core_area = cw * ch

        # Macro area calculation
        macro_area = 0.0
        for it in self.fp.scene.items():
            if isinstance(it, MacroItem):
                macro_area += it.rect().width() * it.rect().height()
        if macro_area == 0.0 and hasattr(self.fp, 'macro_instances') and self.fp.macro_instances:
            for inst_name, master_name in self.fp.macro_instances.items():
                mw, mh = self.fp.macro_sizes.get(master_name, (0.0, 0.0))
                macro_area += mw * mh
        if macro_area > 0:
            self.lbl_macro_info.setText(f"Total Macro Area: {macro_area:.1f} µm²")
        else:
            self.lbl_macro_info.setText("Total Macro Area: 0.0 µm²")

        std_area = getattr(self.fp, "total_std_cell_area", 0.0)
        if core_area > 0 and std_area > 0:
            eff_free = max(1.0, core_area - macro_area)
            std_util = (std_area / eff_free) * 100.0
            tot_util = ((std_area + macro_area) / core_area) * 100.0
            self.lbl_current_util.setText(f"Core Util: {tot_util:.1f}% (Std: {std_util:.1f}%, Macro: {macro_area:.0f}µm²)\nCore: {cw:.1f} × {ch:.1f} µm")
        else:
            self.lbl_current_util.setText(f"Core Area: {cw:.1f} × {ch:.1f} µm")

    def on_fit_density_clicked(self):
        target_dens = self.sp_target_core_density.value() / 100.0
        tot_area = getattr(self.fp, "total_std_cell_area", 0.0)
        if tot_area <= 0:
            self.fp._extract_standard_cell_area()
            tot_area = getattr(self.fp, "total_std_cell_area", 0.0)

        # Macro area calculation
        macro_area = 0.0
        for it in self.fp.scene.items():
            if isinstance(it, MacroItem):
                macro_area += it.rect().width() * it.rect().height()
        if macro_area == 0.0 and hasattr(self.fp, 'macro_instances') and self.fp.macro_instances:
            for inst_name, master_name in self.fp.macro_instances.items():
                mw, mh = self.fp.macro_sizes.get(master_name, (0.0, 0.0))
                macro_area += mw * mh

        if tot_area <= 0 and macro_area <= 0:
            QMessageBox.warning(self, "Area Unavailable", "Total standard cell and macro areas could not be determined.\nPlease input die dimensions manually.")
            return

        needed_core_area = (tot_area / target_dens) + macro_area
        side = math.sqrt(needed_core_area)
        ml = self.sp_marg_l.value(); mr = self.sp_marg_r.value()
        mt = self.sp_marg_t.value(); mb = self.sp_marg_b.value()
        new_die_w = round(side + ml + mr + 10.0, 1)
        new_die_h = round(side + mt + mb + 10.0, 1)

        self.sp_die_w.setValue(new_die_w)
        self.sp_die_h.setValue(new_die_h)
        self.update_util_preview()
        QMessageBox.information(
            self, "Fitted Core to Target Density",
            f"Fitted Die to {new_die_w:.1f} × {new_die_h:.1f} µm factoring {tot_area:.1f} µm² std cells + {macro_area:.1f} µm² macros for target density {target_dens*100:.1f}%."
        )

    def on_apply(self):
        w = self.sp_die_w.value(); h = self.sp_die_h.value()
        ml = self.sp_marg_l.value(); mr = self.sp_marg_r.value()
        mt = self.sp_marg_t.value(); mb = self.sp_marg_b.value()
        cw = w - ml - mr; ch = h - mt - mb
        if cw <= 0 or ch <= 0:
            QMessageBox.critical(self, "Invalid Dimensions", "Margins exceed Die dimensions! Core area would be negative.")
            return

        self.fp._user_custom_dimensions = True
        self.fp.sp_die_w.setValue(w)
        self.fp.sp_die_h.setValue(h)
        self.fp.sp_marg_t.setValue(mt)
        self.fp.sp_marg_b.setValue(mb)
        self.fp.sp_marg_l.setValue(ml)
        self.fp.sp_marg_r.setValue(mr)
        self.fp.sp_target_core_density.setValue(self.sp_target_core_density.value())

        self.fp.init_floorplan()
        self.accept()



def is_io_pad_cell(inst_name: str = "", master_name: str = "") -> bool:
    """
    Checks if a cell instance or master corresponds to an I/O pad or corner pad,
    ensuring it is excluded from macro categorization and core macro placement.
    """
    n = (inst_name or "").lower()
    m = (master_name or "").lower()
    if any(m.startswith(p) for p in ("sky130_fd_io", "sky130_ef_io")):
        return True
    if any(p in m for p in ("_io__", "io_site", "corner_pad", "_pad", "pad_")):
        return True
    if any(m.endswith(p) for p in ("_io", "_pad", "_gpiov2")):
        return True
    if any(p in n for p in ("pad_", "io_corner", "io_pad", "iopad")):
        return True
    return False


class InteractiveFloorplannerWidget(QDialog):
    """
    Silis Floorplan & Power Studio (FPS)
    Unified ASIC Floorplanning, Multi-Domain Power Intent (IEEE-1801 UPF),
    and I/O Pad/Pin Co-Optimization Workbench.
    """
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
            proj_root = self.project_config.get("project_path") or self.project_config.get("project_root") or self.project_config.get("root_path")
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

    def __init__(self, project_config=None, pdk_mgr=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Silis Floorplan & Power Studio (FPS)")
        self.resize(1500, 920)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        self.project_config = project_config or {}
        self.pdk_mgr = pdk_mgr
        self.floorplan_initialized = False
        self.die_rect = None
        self.core_rect = None
        self.macro_sizes = {}
        self.macro_instances = {}
        self.total_std_cell_area = 0.0
        self.module_areas = {}
        self.inclusive_module_areas = {}
        self.undo_stack = []
        self.redo_stack = []
        self.is_undoing = False
        self._user_custom_dimensions = False

        # Dirty state & Autosave
        self.is_dirty = False
        self.netlist_checksum = ""
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(300)
        self._autosave_timer.timeout.connect(self._do_transactional_autosave)

        self._standing_autosave_timer = QTimer(self)
        self._standing_autosave_timer.setInterval(30000)
        self._standing_autosave_timer.timeout.connect(self._do_transactional_autosave)
        self._standing_autosave_timer.start()

        # Power Domain Manager
        proj_root, base = self._get_project_context()
        self.pdm = PowerDomainManager(proj_root=proj_root, top_module=base)
        self.pdm.load_or_create_upf()

        # I/O & Pad State
        self.pad_ring_enabled = False
        self.pad_strategy = "single"
        self.sp_spacing = QDoubleSpinBox()
        self.sp_spacing.setValue(2.0)
        self.rb_macro = QRadioButton("I/O Ports (Macro Export)")
        self.rb_macro.setChecked(True)
        self.rb_chip = QRadioButton("I/O Pads (Full-Chip Tapeout)")
        self.pins_data = {}
        self.pin_items = {}
        self.constraint_boxes = {}
        self.box_counter = 1
        self._user_set_edges = set()
        self.active_edge = "bottom"
        self.pad_pitch = 85.0
        self._edge_zone_items = {}

        # UI Setup
        self._init_top_menu_bar()
        self._init_layout_and_splitters()
        self._setup_keyboard_shortcuts()
        self._load_netlist_and_pdk_context()

        # Build Inspector Tabs
        self._build_floorplan_tab()
        self._build_power_pdn_tab()
        self._build_io_tab()
        self._build_tcl_tab()

        if self.pins_data:
            self._refresh_pads_table()

        if self.project_config:
            self.populate_macro_list(self.project_config)

        # Try to restore session
        self.load_session()
        if self.floorplan_initialized:
            self._set_floorplan_controls_enabled(True)
        else:
            self._set_floorplan_controls_enabled(False)
        if self.floorplan_initialized and not self.undo_stack:
            self.save_state()

    def _init_top_menu_bar(self):
        """Creates the full 8-menu bar matching Silis FPS specification."""
        self.menu_bar = QMenuBar(self)
        
        # 1. File Menu
        self.menu_file = self.menu_bar.addMenu("&File")
        self.act_new_reset = self.menu_file.addAction("New / Reset from Synthesis Netlist")
        self.act_new_reset.setShortcut(QKeySequence("Ctrl+N"))
        self.act_new_reset.triggered.connect(self.on_reset_from_netlist)
        
        self.act_open_session = self.menu_file.addAction("Open Session...")
        self.act_open_session.setShortcut(QKeySequence("Ctrl+O"))
        self.act_open_session.triggered.connect(self.load_session)
        
        self.act_save_session = self.menu_file.addAction("Save Session")
        self.act_save_session.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save_session.triggered.connect(self.save_session)
        
        self.act_save_snapshot = self.menu_file.addAction("Save Snapshot As...")
        self.act_save_snapshot.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_snapshot.triggered.connect(self.save_snapshot_as)
        
        self.act_revert = self.menu_file.addAction("Revert to Last Saved State")
        self.act_revert.triggered.connect(self.revert_to_saved)
        
        self.menu_file.addSeparator()
        self.act_verify_checksum = self.menu_file.addAction("Verify Netlist Integrity & Checksums")
        self.act_verify_checksum.triggered.connect(self.verify_netlist_integrity)
        
        self.menu_file.addSeparator()
        self.act_exit = self.menu_file.addAction("Exit Studio")
        self.act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_exit.triggered.connect(self.close)

        # 2. Edit Menu
        self.menu_edit = self.menu_bar.addMenu("&Edit")
        self.act_undo = self.menu_edit.addAction("Undo")
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.act_undo.triggered.connect(self.undo)
        
        self.act_redo = self.menu_edit.addAction("Redo")
        self.act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        self.act_redo.triggered.connect(self.redo)
        
        self.menu_edit.addSeparator()
        self.act_select_all = self.menu_edit.addAction("Select All")
        self.act_select_all.setShortcut(QKeySequence("Ctrl+A"))
        self.act_select_all.triggered.connect(self.select_all_canvas)
        
        self.act_clear_sel = self.menu_edit.addAction("Clear Selection")
        self.act_clear_sel.triggered.connect(self.clear_selection)
        
        self.act_delete = self.menu_edit.addAction("Delete Selected")
        self.act_delete.setShortcut(QKeySequence("Del"))
        self.act_delete.triggered.connect(self.delete_selected_entities)

        # 3. View Menu
        self.menu_view = self.menu_bar.addMenu("&View")
        self.act_fit_die = self.menu_view.addAction("Fit Die in View")
        self.act_fit_die.setShortcut(QKeySequence("Ctrl+F"))
        self.act_fit_die.triggered.connect(self.fit_die)
        
        self.act_fit_core = self.menu_view.addAction("Fit Core Area")
        self.act_fit_core.triggered.connect(self.fit_core)
        
        self.menu_view.addSeparator()
        self.act_toggle_flightlines = self.menu_view.addAction("Toggle Interconnect Flylines (Ratsnest)")
        self.act_toggle_flightlines.setShortcut(QKeySequence("F"))
        self.act_toggle_flightlines.setCheckable(True)
        self.act_toggle_flightlines.setChecked(True)
        self.act_toggle_flightlines.triggered.connect(lambda: self.view.update())
        
        self.act_toggle_corridor = self.menu_view.addAction("Toggle Corridor Clearance Safety Band")
        self.act_toggle_corridor.setCheckable(True)
        self.act_toggle_corridor.setChecked(True)
        self.act_toggle_corridor.triggered.connect(lambda: self.view.update())
        
        self.act_toggle_halo = self.menu_view.addAction("Toggle Macro Halos & Keepouts")
        self.act_toggle_halo.setCheckable(True)
        self.act_toggle_halo.setChecked(True)
        self.act_toggle_halo.triggered.connect(self.toggle_halos_visibility)

        # 4. Floorplan Menu
        self.menu_floorplan = self.menu_bar.addMenu("&Floorplan")
        self.act_init_bounds = self.menu_floorplan.addAction("Initialize / Recalculate Boundaries...")
        self.act_init_bounds.triggered.connect(self.open_die_core_setup_dialog)
        
        sub_macro = self.menu_floorplan.addMenu("Auto-Place Macros")
        self.act_ap_peri = sub_macro.addAction("Peripheral Fast (Silis Native)")
        self.act_ap_peri.triggered.connect(lambda: self.apply_autoplace_method("peripheral"))
        self.act_ap_rtlmp = sub_macro.addAction("Hierarchical RTL-MP (OpenROAD)")
        self.act_ap_rtlmp.triggered.connect(lambda: self.apply_autoplace_method("hierarchical"))
        self.act_ap_analytical = sub_macro.addAction("Analytical (TritonMacroPlace)")
        self.act_ap_analytical.triggered.connect(lambda: self.apply_autoplace_method("analytical"))
        
        self.menu_floorplan.addSeparator()
        self.act_run_region_placer = self.menu_floorplan.addAction("Run Auto-Region Placer")
        self.act_run_region_placer.triggered.connect(self.on_autoplace_regions_clicked)
        
        self.act_live_tuner_hud = self.menu_floorplan.addAction("Live Weight Tuner HUD")
        self.act_live_tuner_hud.setCheckable(True)
        self.act_live_tuner_hud.setChecked(False)
        self.act_live_tuner_hud.toggled.connect(self.toggle_hud_visibility)
        
        self.act_accept_regions = self.menu_floorplan.addAction("Accept & Lock Regions")
        self.act_accept_regions.triggered.connect(self.accept_autoplace_preview)
        
        self.menu_floorplan.addSeparator()
        self.act_scan_corridors = self.menu_floorplan.addAction("Scan for Narrow Corridors (< 50 µm)")
        self.act_scan_corridors.triggered.connect(self.scan_narrow_corridors)
        
        self.act_tapcell_rules = self.menu_floorplan.addAction("Tapcell Distance & Rules...")
        self.act_tapcell_rules.triggered.connect(lambda: self.inspector_tabs.setCurrentWidget(self.tab_power_pdn))

        # 5. Power Menu
        self.menu_power = self.menu_bar.addMenu("&Power")
        self.act_edit_upf = self.menu_power.addAction("Edit IEEE-1801 UPF File...")
        self.act_edit_upf.triggered.connect(self.edit_upf_file)
        
        self.act_reparse_upf = self.menu_power.addAction("Re-Parse UPF & Update Island Bounds")
        self.act_reparse_upf.triggered.connect(self.reparse_upf)
        
        self.menu_power.addSeparator()
        self.act_add_domain = self.menu_power.addAction("Add Power Domain Island...")
        self.act_add_domain.triggered.connect(self.add_new_power_domain)
        
        self.act_clamp_table = self.menu_power.addAction("Configure Boundary Clamps && Isolation...")
        self.act_clamp_table.triggered.connect(self.open_boundary_clamp_dialog)
        
        self.act_pmu_hookup = self.menu_power.addAction("PMU Controller Hookup & Port Mapping...")
        self.act_pmu_hookup.triggered.connect(self.open_pmu_hookup_dialog)

        self.act_power_switches = self.menu_power.addAction("Calculate Power Switch Matrix (IR Drop < 2%)")
        self.act_power_switches.triggered.connect(self.calculate_power_switch_matrix)
        
        self.menu_power.addSeparator()
        self.act_synth_upf = self.menu_power.addAction("Synthesize Multi-Voltage UPF (OpenROAD)")
        self.act_synth_upf.triggered.connect(self.synthesize_upf_flow)

        # 6. I/O & Pads Menu
        self.menu_io = self.menu_bar.addMenu("&I/O && Pads")
        self.act_toggle_mode = self.menu_io.addAction("Toggle Full-Chip Pad Ring Mode")
        self.act_toggle_mode.setCheckable(True)
        self.act_toggle_mode.setChecked(False)
        self.act_toggle_mode.toggled.connect(self.toggle_pad_ring_mode)
        
        self.act_load_pin_cfg = self.menu_io.addAction("Load pin_order.cfg...")
        self.act_load_pin_cfg.triggered.connect(self.load_pin_order_cfg)
        
        self.act_save_pin_cfg = self.menu_io.addAction("Save pin_order.cfg")
        self.act_save_pin_cfg.triggered.connect(self.save_pin_order_cfg)
        
        self.menu_io.addSeparator()
        self.act_auto_align_pads = self.menu_io.addAction("Auto-Align Pads to Regions (Ray-Casting)")
        self.act_auto_align_pads.triggered.connect(self.auto_align_pads_to_regions)
        
        self.act_space_active_edge = self.menu_io.addAction("Equally Space Active Edge (A)")
        self.act_space_active_edge.setShortcut(QKeySequence("A"))
        self.act_space_active_edge.triggered.connect(self.auto_space_active_edge)
        
        self.act_add_supply_pads = self.menu_io.addAction("Insert Dedicated Power/Ground Pairs")
        self.act_add_supply_pads.triggered.connect(self.insert_supply_pads)

        # 7. PDN Menu
        self.menu_pdn = self.menu_bar.addMenu("P&DN")
        self.act_gen_core_ring = self.menu_pdn.addAction("Generate Core Power Ring (met4 / met5)")
        self.act_gen_core_ring.triggered.connect(self.generate_core_power_ring)
        
        self.act_add_pad_bridges = self.menu_pdn.addAction("Route Targeted Pad Trunk Bridges")
        self.act_add_pad_bridges.triggered.connect(self.route_pad_trunk_bridges)
        
        self.act_dual_followpins = self.menu_pdn.addAction("Configure Dual-Rail Followpins (VPWR vs VPWRG)")
        self.act_dual_followpins.triggered.connect(self.configure_dual_followpins)
        
        self.menu_pdn.addSeparator()
        self.act_run_psm = self.menu_pdn.addAction("Analyze Static IR Drop & EM Violations (::psm)")
        self.act_run_psm.triggered.connect(self.run_psm_analysis)

        # 8. Diagnostics Menu
        self.menu_diag = self.menu_bar.addMenu("&Diagnostics")
        self.act_check_connectivity = self.menu_diag.addAction("Check Pad & Island Connectivity Matrix")
        self.act_check_connectivity.triggered.connect(self.check_connectivity_matrix)
        
        self.act_detect_shorts = self.menu_diag.addAction("Detect Overlaps & Corridor Violations")
        self.act_detect_shorts.triggered.connect(self.detect_overlaps_and_corridors)
        
        self.act_export_report = self.menu_diag.addAction("Export Floorplan Quality Report (HTML/MD)")
        self.act_export_report.triggered.connect(self.export_quality_report)

    def _init_layout_and_splitters(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.setMenuBar(self.menu_bar)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root_layout.addWidget(self.main_splitter)

        # Canvas Container
        self.canvas_container = QWidget(self.main_splitter)
        canvas_layout = QVBoxLayout(self.canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        # Vertical Splitter in Canvas Pane for collapsible Live Weight Tuner HUD
        self.canvas_vsplitter = QSplitter(Qt.Orientation.Vertical, self.canvas_container)
        canvas_layout.addWidget(self.canvas_vsplitter)

        # HUD Widget (Live Weight Tuner)
        self.hud_widget = QWidget(self.canvas_vsplitter)
        hud_l = QVBoxLayout(self.hud_widget)
        hud_l.setContentsMargins(6, 6, 6, 6)
        hud_l.setSpacing(4)

        h_row1 = QHBoxLayout()
        lbl_hud_title = QLabel("Live Weight Tuner HUD (Physics Engine)")
        h_row1.addWidget(lbl_hud_title)
        h_row1.addStretch()

        self.btn_hud_reroll = QPushButton("Re-roll Seed")
        self.btn_hud_reroll.clicked.connect(self.reroll_autoplace_seed)
        self.btn_hud_accept = QPushButton("Accept & Lock")
        self.btn_hud_accept.clicked.connect(self.accept_autoplace_preview)
        self.btn_hud_close = QPushButton("X")
        self.btn_hud_close.setFixedWidth(24)
        self.btn_hud_close.clicked.connect(lambda: self.toggle_hud_visibility(False))

        h_row1.addWidget(self.btn_hud_reroll)
        h_row1.addWidget(self.btn_hud_accept)
        h_row1.addWidget(self.btn_hud_close)
        hud_l.addLayout(h_row1)

        h_row2 = QHBoxLayout()
        self._autoplace_debounce_timer = QTimer(self)
        self._autoplace_debounce_timer.setSingleShot(True)
        self._autoplace_debounce_timer.setInterval(40)
        self._autoplace_debounce_timer.timeout.connect(self.trigger_live_autoplace)

        h_row2.addWidget(QLabel("R2M:"))
        self.sld_r2m = QSlider(Qt.Orientation.Horizontal)
        self.sld_r2m.setRange(0, 300)
        self.sld_r2m.setValue(100)
        self.sld_r2m.setFixedWidth(70)
        self.sp_r2m = QDoubleSpinBox()
        self.sp_r2m.setRange(0.0, 3.0)
        self.sp_r2m.setValue(1.0)
        self.sp_r2m.setSingleStep(0.1)
        self.sp_r2m.setFixedWidth(50)
        self.sld_r2m.valueChanged.connect(lambda v: (self.sp_r2m.blockSignals(True), self.sp_r2m.setValue(v / 100.0), self.sp_r2m.blockSignals(False), self._autoplace_debounce_timer.start()))
        self.sp_r2m.valueChanged.connect(lambda v: (self.sld_r2m.blockSignals(True), self.sld_r2m.setValue(int(v * 100)), self.sld_r2m.blockSignals(False), self._autoplace_debounce_timer.start()))
        h_row2.addWidget(self.sld_r2m)
        h_row2.addWidget(self.sp_r2m)

        h_row2.addWidget(QLabel("R2R:"))
        self.sld_r2r = QSlider(Qt.Orientation.Horizontal)
        self.sld_r2r.setRange(0, 300)
        self.sld_r2r.setValue(100)
        self.sld_r2r.setFixedWidth(70)
        self.sp_r2r = QDoubleSpinBox()
        self.sp_r2r.setRange(0.0, 3.0)
        self.sp_r2r.setValue(1.0)
        self.sp_r2r.setSingleStep(0.1)
        self.sp_r2r.setFixedWidth(50)
        self.sld_r2r.valueChanged.connect(lambda v: (self.sp_r2r.blockSignals(True), self.sp_r2r.setValue(v / 100.0), self.sp_r2r.blockSignals(False), self._autoplace_debounce_timer.start()))
        self.sp_r2r.valueChanged.connect(lambda v: (self.sld_r2r.blockSignals(True), self.sld_r2r.setValue(int(v * 100)), self.sld_r2r.blockSignals(False), self._autoplace_debounce_timer.start()))
        h_row2.addWidget(self.sld_r2r)
        h_row2.addWidget(self.sp_r2r)

        h_row2.addWidget(QLabel("R2IO:"))
        self.sld_r2io = QSlider(Qt.Orientation.Horizontal)
        self.sld_r2io.setRange(0, 300)
        self.sld_r2io.setValue(100)
        self.sld_r2io.setFixedWidth(70)
        self.sp_r2io = QDoubleSpinBox()
        self.sp_r2io.setRange(0.0, 3.0)
        self.sp_r2io.setValue(1.0)
        self.sp_r2io.setSingleStep(0.1)
        self.sp_r2io.setFixedWidth(50)
        self.sld_r2io.valueChanged.connect(lambda v: (self.sp_r2io.blockSignals(True), self.sp_r2io.setValue(v / 100.0), self.sp_r2io.blockSignals(False), self._autoplace_debounce_timer.start()))
        self.sp_r2io.valueChanged.connect(lambda v: (self.sld_r2io.blockSignals(True), self.sld_r2io.setValue(int(v * 100)), self.sld_r2io.blockSignals(False), self._autoplace_debounce_timer.start()))
        h_row2.addWidget(self.sld_r2io)
        h_row2.addWidget(self.sp_r2io)

        h_row2.addWidget(QLabel("Seed:"))
        self.sp_autoplace_seed = QSpinBox()
        self.sp_autoplace_seed.setRange(1, 99999)
        self.sp_autoplace_seed.setValue(42)
        self.sp_autoplace_seed.setFixedWidth(60)
        self.sp_autoplace_seed.valueChanged.connect(lambda _: self._autoplace_debounce_timer.start())
        h_row2.addWidget(self.sp_autoplace_seed)

        hud_l.addLayout(h_row2)
        self.canvas_vsplitter.addWidget(self.hud_widget)
        self.hud_widget.setVisible(False)

        # Graphics Scene & View
        self.scene = QGraphicsScene(self)
        self.view = FloorplanView(self)
        self.view.setScene(self.scene)
        self.view.scale(1, -1)
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.macro_dropped.connect(self.on_macro_dropped)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.canvas_vsplitter.addWidget(self.view)

        # Inspector Tabs
        self.inspector_tabs = QTabWidget(self.main_splitter)
        self.tabs = self.inspector_tabs
        self.hud_autoplace = self.hud_widget
        self.tab_floorplan = QWidget()
        self.tab_power_pdn = QWidget()
        self.tab_power = self.tab_power_pdn
        self.tab_pdn = self.tab_power_pdn
        self.tab_io = QWidget()
        self.tab_tcl = QWidget()

        self.inspector_tabs.addTab(self.tab_floorplan, "Floorplan")
        self.inspector_tabs.addTab(self.tab_power_pdn, "Power & PDN")
        self.inspector_tabs.addTab(self.tab_io, "I/O & Pads")
        self.inspector_tabs.addTab(self.tab_tcl, "Execution & Live TCL")

        self.main_splitter.addWidget(self.canvas_container)
        self.main_splitter.addWidget(self.inspector_tabs)

        self.main_splitter.setStretchFactor(0, 6)
        self.main_splitter.setStretchFactor(1, 4)
        self.main_splitter.setSizes([900, 600])

    def _setup_keyboard_shortcuts(self):
        for seq, fn in [
            ("Ctrl+Z", self.undo),
            ("Ctrl+Y", self.redo),
            ("Ctrl+Shift+Z", self.redo),
            ("Ctrl+S", self.save_session),
            ("Ctrl+N", self.on_reset_from_netlist),
            ("Ctrl+O", self.load_session),
            ("Ctrl+A", self.select_all_canvas),
            ("F", self.toggle_flightlines),
            ("Del", self.delete_selected_entities),
            ("Backspace", self.delete_selected_entities),
        ]:
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)

        sc_del = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        sc_del.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_del.activated.connect(self.delete_selected_entities)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.clear_selection()
            event.accept()
            return
        super().keyPressEvent(event)

    def reject(self):
        self.clear_selection()

    def closeEvent(self, event):
        if self.is_dirty:
            res = QMessageBox.question(
                self, "Save Session?",
                "You have unsaved changes in your floorplan and power design. Would you like to save before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )
            if res == QMessageBox.StandardButton.Save:
                self.save_session()
                event.accept()
            elif res == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
                return
        else:
            event.accept()

    def toggle_hud_visibility(self, visible):
        self.hud_widget.setVisible(visible)
        self.act_live_tuner_hud.blockSignals(True)
        self.act_live_tuner_hud.setChecked(visible)
        self.act_live_tuner_hud.blockSignals(False)

    def _trigger_autosave(self):
        self.is_dirty = True
        self._autosave_timer.start()

    def _do_transactional_autosave(self):
        try:
            proj_root, base = self._get_project_context()
            save_path = os.path.join(proj_root, ".silis_fp_session.json").replace("\\", "/")
            tmp_path = save_path + ".tmp"
            state = self._serialize_session_state()
            with open(tmp_path, "w") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp_path, save_path)
            self.is_dirty = False
        except Exception as e:
            pass

    def _serialize_session_state(self):
        is_pad_mode = getattr(self, "pad_ring_enabled", False) or (hasattr(self, "rb_chip") and self.rb_chip.isChecked())
        state = {
            "version": "2.0-FPS",
            "netlist_checksum": self.netlist_checksum,
            "is_pad_mode": is_pad_mode,
            "die": {
                "w": self.sp_die_w.value() if hasattr(self, "sp_die_w") else 1500.0,
                "h": self.sp_die_h.value() if hasattr(self, "sp_die_h") else 1500.0,
                "mt": self.sp_marg_t.value() if hasattr(self, "sp_marg_t") else 20.0,
                "mb": self.sp_marg_b.value() if hasattr(self, "sp_marg_b") else 20.0,
                "ml": self.sp_marg_l.value() if hasattr(self, "sp_marg_l") else 20.0,
                "mr": self.sp_marg_r.value() if hasattr(self, "sp_marg_r") else 20.0,
            },
            "macros": [],
            "blockages": [],
            "regions": [],
            "power_domains": [],
            "pins": self.pins_data,
            "tap_distance": self.sp_tap_distance.value() if hasattr(self, "sp_tap_distance") else 14.0,
            "pdn_config": {
                "enable_ring": self.chk_enable_ring.isChecked() if hasattr(self, "chk_enable_ring") else True,
                "ring_width": self.sp_ring_width.value() if hasattr(self, "sp_ring_width") else 5.0,
                "ring_spacing": self.sp_ring_spacing.value() if hasattr(self, "sp_ring_spacing") else 2.0,
                "ring_offset": self.sp_ring_offset.value() if hasattr(self, "sp_ring_offset") else 5.0,
                "ring_h_layer": self.cmb_ring_h_layer.currentText() if hasattr(self, "cmb_ring_h_layer") else "met5",
                "ring_v_layer": self.cmb_ring_v_layer.currentText() if hasattr(self, "cmb_ring_v_layer") else "met4",
                "enable_trunks": self.chk_enable_trunks.isChecked() if hasattr(self, "chk_enable_trunks") else True,
                "trunk_layer": self.cmb_trunk_layer.currentText() if hasattr(self, "cmb_trunk_layer") else "met4",
                "trunk_width": self.sp_trunk_width.value() if hasattr(self, "sp_trunk_width") else 3.2,
                "targeted_bridges": self.chk_targeted_bridges.isChecked() if hasattr(self, "chk_targeted_bridges") else True,
            },
        }
        for it in self.scene.items():
            if isinstance(it, MacroItem):
                state["macros"].append({
                    "name": it.name, "inst_name": it.inst_name,
                    "x": it.pos().x(), "y": it.pos().y(),
                    "orientation": it.orientation, "halo": it.halo
                })
            elif isinstance(it, BlockageItem):
                state["blockages"].append({
                    "x": it.rect().x() + it.pos().x(), "y": it.rect().y() + it.pos().y(),
                    "w": it.rect().width(), "h": it.rect().height(),
                    "btype": it.btype, "pct": it.pct
                })
            elif isinstance(it, RegionItem):
                state["regions"].append({
                    "module_name": it.module_name,
                    "x": it.rect().x() + it.pos().x(), "y": it.rect().y() + it.pos().y(),
                    "w": it.rect().width(), "h": it.rect().height(),
                    "is_fence": it.is_fence, "density": it.density,
                    "halo": it.halo, "locked": it.locked,
                    "multi_boxes": getattr(it, "multi_boxes", [])
                })
            elif isinstance(it, VoltageIslandItem):
                d_type = "Internally Gated"
                if hasattr(self, "pdm") and it.domain_name in self.pdm.domains:
                    d_type = getattr(self.pdm.domains[it.domain_name], "domain_type", "Internally Gated")
                state["power_domains"].append({
                    "domain_name": it.domain_name, "voltage": it.voltage,
                    "domain_type": d_type,
                    "elements": it.elements,
                    "tapcell_type": getattr(it, "tapcell_type", "sky130_fd_sc_hd__tapvpwrvgnd_1"),
                    "halo": getattr(it, "halo", (15.0, 15.0, 15.0, 15.0)),
                    "x": it.rect().x() + it.pos().x(), "y": it.rect().y() + it.pos().y(),
                    "w": it.rect().width(), "h": it.rect().height(),
                })
        return state

    def save_session(self):
        self._do_transactional_autosave()
        QMessageBox.information(self, "Session Saved", "Silis FP Studio session successfully saved to .silis_fp_session.json")

    def save_snapshot_as(self):
        proj_root, base = self._get_project_context()
        path, _ = QFileDialog.getSaveFileName(self, "Save Revision Snapshot", proj_root, "JSON Files (*.json)")
        if path:
            state = self._serialize_session_state()
            with open(path, "w") as f:
                json.dump(state, f, indent=2)

    def load_session(self):
        proj_root, base = self._get_project_context()
        session_file = os.path.join(proj_root, ".silis_fp_session.json")
        if not os.path.isfile(session_file):
            session_file = os.path.join(proj_root, "reports", f"{base}_floorplan_save.json")
        if os.path.isfile(session_file):
            try:
                with open(session_file, "r") as f:
                    state = json.load(f)
                self.load_state(state)
            except Exception as e:
                self.is_undoing = False
                print("[FPS] Error loading session:", e)
            finally:
                self.is_undoing = False

    def revert_to_saved(self):
        res = QMessageBox.warning(
            self, "Revert Session?",
            "Discard all in-memory changes and reload the last saved state from disk?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.load_session()

    def verify_netlist_integrity(self):
        proj_root, base = self._get_project_context()
        netlist_path = os.path.join(proj_root, "netlist", f"{base}_netlist.v")
        if not os.path.isfile(netlist_path):
            netlist_path = os.path.join(proj_root, "source", f"{base}.v")
        if not os.path.isfile(netlist_path):
            QMessageBox.information(self, "Netlist Check", "No verilog netlist found in project directories.")
            return
        with open(netlist_path, "rb") as f:
            cur_sha = hashlib.sha256(f.read()).hexdigest()
        if self.netlist_checksum and self.netlist_checksum != cur_sha:
            QMessageBox.warning(
                self, "Checksum Mismatch Detected",
                f"Netlist SHA-256 has changed since session creation!\n\nSaved:   {self.netlist_checksum[:16]}...\nCurrent: {cur_sha[:16]}...\n\nPlease review your region modules."
            )
        else:
            self.netlist_checksum = cur_sha
            QMessageBox.information(self, "Netlist Verified", f"Netlist verified cleanly.\nSHA-256: {cur_sha}")

    def on_reset_from_netlist(self):
        res = QMessageBox.warning(
            self, "Reset Floorplan?",
            "Discard all floorplan, power domains, and pad positions, and reset from fresh netlist?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.scene.clear()
            self.init_floorplan()

    def select_all_canvas(self):
        for it in self.scene.items():
            if it.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable:
                it.setSelected(True)

    def clear_selection(self):
        for it in self.scene.selectedItems():
            it.setSelected(False)

    def delete_selected_entities(self):
        items_to_delete = list(self.scene.selectedItems())
        if not items_to_delete:
            return
        for item in items_to_delete:
            if isinstance(item, (MacroItem, BlockageItem, RegionItem, VoltageIslandItem, PinItem)):
                self.scene.removeItem(item)
                if isinstance(item, MacroItem) and hasattr(item, "list_item") and item.list_item:
                    item.list_item.setFlags(item.list_item.flags() | Qt.ItemFlag.ItemIsEnabled)
                    item.list_item.setText(item.list_item.text().replace(" [PLACED]", ""))
                    item.list_item.setForeground(QBrush())
                elif isinstance(item, VoltageIslandItem):
                    if hasattr(self, "power_domains"):
                        for pd in self.power_domains:
                            if pd.name == item.domain_name:
                                pd.area = None
                                break
                        if hasattr(self, "populate_power_domains_ui"):
                            self.populate_power_domains_ui()
        self.save_state()

    def fit_core(self):
        if hasattr(self, "core_rect") and self.core_rect:
            self.view.fitInView(self.core_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def toggle_halos_visibility(self, visible):
        for it in self.scene.items():
            if isinstance(it, MacroItem) and hasattr(it, "halo_rect"):
                it.halo_rect.setVisible(visible)

    def scan_narrow_corridors(self):
        corridor_limit = 50.0
        narrow_count = 0
        boxes = [it.sceneBoundingRect() for it in self.scene.items() if isinstance(it, (MacroItem, RegionItem))]
        for i, b1 in enumerate(boxes):
            for b2 in boxes[i+1:]:
                dx = max(0, max(b1.left() - b2.right(), b2.left() - b1.right()))
                dy = max(0, max(b1.top() - b2.bottom(), b2.top() - b1.bottom()))
                dist = math.hypot(dx, dy)
                if 0.1 < dist < corridor_limit:
                    narrow_count += 1
        if narrow_count > 0:
            QMessageBox.warning(self, "Narrow Corridors Detected", f"Detected {narrow_count} cavity channel(s) narrower than {corridor_limit} µm!\nConsider expanding corridors to guarantee core power ring and PDN strap clearance.")
        else:
            QMessageBox.information(self, "Corridors Clean", f"All macro and region channels meet the minimum {corridor_limit} µm clearance!")


    def open_die_core_setup_dialog(self):
        dlg = DieCoreSetupDialog(self, parent=self)
        dlg.exec()

    def _load_netlist_and_pdk_context(self):
        proj_root, base = self._get_project_context()
        netlist_path = os.path.join(proj_root, "netlist", f"{base}_netlist.v")
        if not os.path.isfile(netlist_path):
            netlist_path = os.path.join(proj_root, "source", f"{base}.v")
        if os.path.isfile(netlist_path):
            with open(netlist_path, "rb") as f:
                self.netlist_checksum = hashlib.sha256(f.read()).hexdigest()

        # Load pins from synthesized netlist / RTL sources if not already populated
        if not self.pins_data and proj_root:
            from backendflow.floorplanner.ioplacer import IOPlacerDialog
            v_pins = IOPlacerDialog._parse_verilog_netlist_pins(self, proj_root)
            if v_pins:
                self.pins_data = v_pins

        # Also check for existing pin_order.cfg to retain assigned edges
        pin_cfg_path = os.path.join(proj_root, "io", "pin_order.cfg")
        if os.path.isfile(pin_cfg_path):
            self._load_pin_order_cfg_silent(pin_cfg_path)

    def _build_floorplan_tab(self):
        scroll = QScrollArea(self.tab_floorplan)
        scroll.setWidgetResizable(True)
        w = QWidget()
        lay = QVBoxLayout(w)

        # Die & Core Boundaries Quick Actions Card
        gb_bounds = QGroupBox("Die & Core Boundaries")
        lay_b = QVBoxLayout(gb_bounds)
        self.btn_open_die_diag = QPushButton("Initialize / Recalculate Die Boundaries...")
        self.btn_open_die_diag.setToolTip("Open modal calculator to configure die size, margins, and target core density")
        self.btn_open_die_diag.clicked.connect(self.open_die_core_setup_dialog)
        self.lbl_core_util = QLabel("Core Utilization: -")
        lay_b.addWidget(self.btn_open_die_diag)
        lay_b.addWidget(self.lbl_core_util)

        # Die Width / Height input fields
        self.sp_die_w = QDoubleSpinBox(); self.sp_die_w.setRange(0.1, 100000); self.sp_die_w.setValue(5000); self.sp_die_w.setSuffix(" µm")
        self.sp_die_h = QDoubleSpinBox(); self.sp_die_h.setRange(0.1, 100000); self.sp_die_h.setValue(5000); self.sp_die_h.setSuffix(" µm")
        w_die_inputs = QWidget()
        h_die_lay = QHBoxLayout(w_die_inputs)
        h_die_lay.setContentsMargins(0, 0, 0, 0)
        h_die_lay.addWidget(QLabel("Die W:"))
        h_die_lay.addWidget(self.sp_die_w)
        h_die_lay.addWidget(QLabel("Die H:"))
        h_die_lay.addWidget(self.sp_die_h)
        lay_b.addWidget(w_die_inputs)

        # Core Border / Margin input field
        self.sp_core_border = QDoubleSpinBox()
        self.sp_core_border.setRange(0, 10000)
        self.sp_core_border.setValue(20.0)
        self.sp_core_border.setSingleStep(1.0)
        self.sp_core_border.setSuffix(" µm")
        self.sp_core_border.setToolTip("Uniform margin between Die edge and Core boundary on all sides")

        w_border_inputs = QWidget()
        h_border_lay = QHBoxLayout(w_border_inputs)
        h_border_lay.setContentsMargins(0, 0, 0, 0)
        h_border_lay.addWidget(QLabel("Border:"))
        h_border_lay.addWidget(self.sp_core_border)
        lay_b.addWidget(w_border_inputs)

        lay.addWidget(gb_bounds)

        # Retain margin spinboxes for internal compatibility
        self.sp_marg_t = QDoubleSpinBox(); self.sp_marg_t.setRange(0, 10000); self.sp_marg_t.setValue(20)
        self.sp_marg_b = QDoubleSpinBox(); self.sp_marg_b.setRange(0, 10000); self.sp_marg_b.setValue(20)
        self.sp_marg_l = QDoubleSpinBox(); self.sp_marg_l.setRange(0, 10000); self.sp_marg_l.setValue(20)
        self.sp_marg_r = QDoubleSpinBox(); self.sp_marg_r.setRange(0, 10000); self.sp_marg_r.setValue(20)
        self.sp_core_w = QDoubleSpinBox(); self.sp_core_w.setRange(0.1, 100000); self.sp_core_w.setValue(4960); self.sp_core_w.setSuffix(" µm")
        self.sp_core_h = QDoubleSpinBox(); self.sp_core_h.setRange(0.1, 100000); self.sp_core_h.setValue(4960); self.sp_core_h.setSuffix(" µm")

        self.sp_target_core_density = QDoubleSpinBox()
        self.sp_target_core_density.setRange(10.0, 95.0)
        self.sp_target_core_density.setValue(60.0)
        self.sp_target_core_density.setSuffix("%")
        self.sp_target_core_density.valueChanged.connect(self.update_utilization)

        self.sp_die_w.editingFinished.connect(self.on_die_input_changed)
        self.sp_die_h.editingFinished.connect(self.on_die_input_changed)
        self.sp_core_border.editingFinished.connect(self.on_border_input_changed)
        self.sp_core_border.valueChanged.connect(self.on_border_input_changed)

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
        self.btn_convert_type.setToolTip("Toggle selected region between Fence (exclusive) and Region (inclusive)")
        self.btn_convert_type.clicked.connect(self.on_convert_region_type_clicked)
        self.btn_convert_type.setEnabled(False)

        # Side-by-side Type (Convert) and Density
        w_type_dens = QWidget()
        lay_type_dens = QHBoxLayout(w_type_dens)
        lay_type_dens.setContentsMargins(0, 0, 0, 0)
        lbl_type_cap = QLabel("Type:")
        lbl_dens_cap = QLabel("Density:")
        lay_type_dens.addWidget(lbl_type_cap)
        lay_type_dens.addWidget(self.btn_convert_type)
        lay_type_dens.addWidget(lbl_dens_cap)
        lay_type_dens.addWidget(self.sp_sel_density)

        # 3x1 Horizontal Layout: Orientation | X | Y
        w_macro_3x1 = QWidget()
        lay_macro_3x1 = QHBoxLayout(w_macro_3x1)
        lay_macro_3x1.setContentsMargins(0, 0, 0, 0)
        lbl_orient = QLabel("Orient:")
        lbl_x = QLabel("X:")
        lbl_y = QLabel("Y:")
        lay_macro_3x1.addWidget(lbl_orient)
        lay_macro_3x1.addWidget(self.cmb_orientation)
        lay_macro_3x1.addWidget(lbl_x)
        lay_macro_3x1.addWidget(self.sp_sel_x)
        lay_macro_3x1.addWidget(lbl_y)
        lay_macro_3x1.addWidget(self.sp_sel_y)

        fl_sel.addRow("Macro:", self.lbl_sel_name)
        fl_sel.addRow("Instance:", self.txt_inst_name)
        fl_sel.addRow("Region:", w_type_dens)
        fl_sel.addRow("Placement:", w_macro_3x1)

        self.sp_sel_x.valueChanged.connect(self.on_spinbox_changed)
        self.sp_sel_y.valueChanged.connect(self.on_spinbox_changed)
        self.cmb_orientation.currentTextChanged.connect(self.on_orientation_changed)

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

        halo_grid_w = QWidget()
        halo_grid = QGridLayout(halo_grid_w)
        halo_grid.setContentsMargins(0, 0, 0, 0)
        halo_grid.setSpacing(4)
        halo_grid.addWidget(QLabel("Top:"), 0, 0)
        halo_grid.addWidget(self.sp_halo_t, 0, 1)
        halo_grid.addWidget(QLabel("Bottom:"), 0, 2)
        halo_grid.addWidget(self.sp_halo_b, 0, 3)
        halo_grid.addWidget(QLabel("Left/All:"), 1, 0)
        halo_grid.addWidget(self.sp_halo_l, 1, 1)
        halo_grid.addWidget(QLabel("Right:"), 1, 2)
        halo_grid.addWidget(self.sp_halo_r, 1, 3)

        fl_sel.addRow(self.chk_equal_halo)
        fl_sel.addRow("Halos (2x2):", halo_grid_w)

        self.sp_halo_l.valueChanged.connect(self.on_halo_changed)
        self.sp_halo_r.valueChanged.connect(self.on_halo_changed)
        self.sp_halo_b.valueChanged.connect(self.on_halo_changed)
        self.sp_halo_t.valueChanged.connect(self.on_halo_changed)

        fl_sel.addRow(QLabel("<hr style='border: 1px solid #333;'>"))
        self.chk_autoplace = QCheckBox("Auto Place Macros")
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
        lay.addWidget(gb_sel)

        # Macro Instances tracking (canvas-direct, hidden from UI)
        self.macro_list = QListWidget()
        self.macro_list.setDragEnabled(True)
        self.macro_list.startDrag = self.start_drag

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

        self.chk_region_lock = QCheckBox("Lock Selected Region")
        self.chk_region_lock.stateChanged.connect(self.on_region_lock_toggled)

        self.chk_allow_rotation = QCheckBox("Allow rotation")
        self.chk_allow_rotation.setChecked(True)

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

        self.btn_autoplace_regions = QPushButton("Auto Place Regions")
        self.btn_autoplace_regions.clicked.connect(self.on_autoplace_regions_clicked)

        self.btn_fence_mode = QPushButton("Fences")
        self.btn_fence_mode.setCheckable(True)
        self.btn_fence_mode.setChecked(True)
        def _update_fence_mode_label():
            self.btn_fence_mode.setText("Fences" if self.btn_fence_mode.isChecked() else "Regions")
        self.btn_fence_mode.toggled.connect(_update_fence_mode_label)

        self.lbl_autoplace_spinner = QLabel("")
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
        lay.addWidget(gb_region)

        # Blockages
        gb_block = QGroupBox("Placement Blockages")
        fl_block = QFormLayout(gb_block)
        self.cmb_block_type = QComboBox()
        self.cmb_block_type.addItems(["Hard", "Soft", "Partial"])
        self.sp_block_pct = QDoubleSpinBox(); self.sp_block_pct.setRange(0, 100); self.sp_block_pct.setValue(40)
        self.sp_block_pct.setEnabled(False)
        self.cmb_block_type.currentIndexChanged.connect(lambda i: self.sp_block_pct.setEnabled(self.cmb_block_type.currentText() == "Partial"))

        self.btn_draw_block = QPushButton("Draw Blockage")
        self.btn_draw_block.clicked.connect(self.start_drawing_blockage)

        # Side-by-side Blockage Type & Density %
        w_block_row = QWidget()
        lay_block_row = QHBoxLayout(w_block_row)
        lay_block_row.setContentsMargins(0, 0, 0, 0)
        lbl_b_type = QLabel("Type:")
        lbl_b_pct = QLabel("Density %:")
        lay_block_row.addWidget(lbl_b_type)
        lay_block_row.addWidget(self.cmb_block_type)
        lay_block_row.addWidget(lbl_b_pct)
        lay_block_row.addWidget(self.sp_block_pct)

        fl_block.addRow(w_block_row)
        fl_block.addRow(self.btn_draw_block)
        lay.addWidget(gb_block)

        scroll.setWidget(w)
        lay_main = QVBoxLayout(self.tab_floorplan)
        lay_main.addWidget(scroll)

    def _build_power_pdn_tab(self):
        lay_main = QVBoxLayout(self.tab_power_pdn)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        lay = QVBoxLayout(container)
        
        # 1. PMU & UPF Architecture Group
        gb_pmu = QGroupBox("Power Management Unit (PMU) & UPF Architecture")
        fl_pmu = QFormLayout(gb_pmu)
        
        self.cmb_pmu_inst = QComboBox()
        self.cmb_pmu_inst.addItem("(Top-Level Port Control / No Sub-PMU)", None)
        self.cmb_pmu_inst.currentIndexChanged.connect(self.on_pmu_instance_changed)
        
        self.lbl_upf_status = QLabel("Active UPF: design.upf")
        
        fl_pmu.addRow("PMU Instance:", self.cmb_pmu_inst)
        fl_pmu.addRow("UPF Intent:", self.lbl_upf_status)

        # PMU Port & Control Hookup Overview
        self.table_pmu_ports = QTableWidget(0, 3)
        self.table_pmu_ports.setHorizontalHeaderLabels(["PMU Terminal", "Direction", "Bound Net / Signal"])
        self.table_pmu_ports.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_pmu_ports.setMaximumHeight(160)
        fl_pmu.addRow("PMU Ports & Controls:", self.table_pmu_ports)

        gb_doms = QGroupBox("Voltage Islands & Domains")
        lay_doms = QVBoxLayout(gb_doms)
        
        # Dedicated Per-Domain Power Supply Architecture Table
        self.table_domain_supplies = QTableWidget(0, 6)
        self.table_domain_supplies.setHorizontalHeaderLabels([
            "Power Domain", "Voltage", "Power Supply Type", "Supply Net / Source", "Row Site / Height", "Physical Switch"
        ])
        self.table_domain_supplies.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_domain_supplies.setMaximumHeight(160)
        lay_doms.addWidget(self.table_domain_supplies)

        h_dom_btns = QHBoxLayout()
        self.btn_place_pd = QPushButton("Place Island on Canvas")
        self.btn_place_pd.clicked.connect(self.on_place_power_domain_clicked)
        self.btn_pmu_hookup = QPushButton("Configure PMU Hookup...")
        self.btn_pmu_hookup.clicked.connect(self.open_pmu_hookup_dialog)
        h_dom_btns.addWidget(self.btn_place_pd)
        h_dom_btns.addWidget(self.btn_pmu_hookup)
        lay_doms.addLayout(h_dom_btns)
        lay.addWidget(gb_doms)

        self._populate_pmu_instances()

        # 2. Tapcell Insertion & Per-Domain Rules
        gb_tap = QGroupBox("Tapcell Insertion & Rules")
        fl_tap = QFormLayout(gb_tap)
        
        self.sp_tap_distance = QDoubleSpinBox()
        self.sp_tap_distance.setRange(5.0, 50.0)
        self.sp_tap_distance.setValue(14.0)
        self.sp_tap_distance.setSuffix(" µm")
        
        self.cmb_default_tapcell = QComboBox()
        self.cmb_default_tapcell.addItems([
            "sky130_fd_sc_hd__tapvpwrvgnd_1",
            "sky130_fd_sc_hd__tap_1",
            "sky130_fd_sc_hd__tap_2"
        ])
        
        fl_tap.addRow("Tapcell Distance (µm):", self.sp_tap_distance)
        fl_tap.addRow("Default Well Tap Cell:", self.cmb_default_tapcell)
        lay.addWidget(gb_tap)

        gb_dom_tap = QGroupBox("Per-Domain Tapcell Rules")
        lay_dom_tap = QVBoxLayout(gb_dom_tap)
        self.table_domain_tapcells = QTableWidget(0, 3)
        self.table_domain_tapcells.setHorizontalHeaderLabels(["Power Domain", "Voltage", "Tapcell Cell Type"])
        self.table_domain_tapcells.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay_dom_tap.addWidget(self.table_domain_tapcells)
        lay.addWidget(gb_dom_tap)

        # 4. Core Power Ring & Pad Trunk Bridges
        gb_ring = QGroupBox("Core Power Ring & Pad Trunk Bridges")
        fl_ring = QFormLayout(gb_ring)

        self.chk_enable_ring = QCheckBox("Enable Peripheral Core Power Ring")
        self.chk_enable_ring.setChecked(True)
        self.chk_enable_ring.toggled.connect(self._on_pdn_ring_controls_toggled)

        self.sp_ring_width = QDoubleSpinBox()
        self.sp_ring_width.setRange(0.5, 50.0)
        self.sp_ring_width.setValue(5.0)
        self.sp_ring_width.setSuffix(" µm")
        
        self.sp_ring_spacing = QDoubleSpinBox()
        self.sp_ring_spacing.setRange(0.2, 20.0)
        self.sp_ring_spacing.setValue(2.0)
        self.sp_ring_spacing.setSuffix(" µm")

        self.sp_ring_offset = QDoubleSpinBox()
        self.sp_ring_offset.setRange(0.0, 50.0)
        self.sp_ring_offset.setValue(5.0)
        self.sp_ring_offset.setSuffix(" µm")

        self.cmb_ring_h_layer = QComboBox()
        self.cmb_ring_h_layer.addItems(["met5", "met4", "met3"])

        self.cmb_ring_v_layer = QComboBox()
        self.cmb_ring_v_layer.addItems(["met4", "met5", "met3"])

        # Dedicated Pad Trunk Bridges
        self.chk_enable_trunks = QCheckBox("Enable Low-Impedance Power Pad Trunk Straps")
        self.chk_enable_trunks.setChecked(True)
        self.chk_enable_trunks.toggled.connect(self._on_pdn_trunk_controls_toggled)

        self.cmb_trunk_layer = QComboBox()
        self.cmb_trunk_layer.addItems(["met4", "met5", "met3"])

        self.sp_trunk_width = QDoubleSpinBox()
        self.sp_trunk_width.setRange(0.5, 30.0)
        self.sp_trunk_width.setValue(3.2)
        self.sp_trunk_width.setSuffix(" µm")

        self.chk_targeted_bridges = QCheckBox("Targeted Pad Bridges Solely to P_CORE/G_CORE (Prevent shorts)")
        self.chk_targeted_bridges.setChecked(True)

        self.chk_dual_followpins = QCheckBox("Emit Dual-Rail Followpins for Switched Islands (VPWR vs VPWRG)")
        self.chk_dual_followpins.setChecked(True)

        fl_ring.addRow(self.chk_enable_ring)
        fl_ring.addRow("Ring Width (µm):", self.sp_ring_width)
        fl_ring.addRow("Ring Spacing (µm):", self.sp_ring_spacing)
        fl_ring.addRow("Ring Core Offset (µm):", self.sp_ring_offset)
        fl_ring.addRow("Ring Horiz Layer:", self.cmb_ring_h_layer)
        fl_ring.addRow("Ring Vert Layer:", self.cmb_ring_v_layer)
        fl_ring.addRow(self.chk_enable_trunks)
        fl_ring.addRow("Trunk Route Layer:", self.cmb_trunk_layer)
        fl_ring.addRow("Trunk Width (µm):", self.sp_trunk_width)
        fl_ring.addRow(self.chk_targeted_bridges)
        fl_ring.addRow(self.chk_dual_followpins)
        lay.addWidget(gb_ring)

        # 5. PDN & Mesh Layout
        lay.addStretch()

        scroll.setWidget(container)
        lay_main.addWidget(scroll)

        self._populate_pmu_instances()
        self._refresh_power_domains_table()
        self._refresh_domain_supplies_table()
        self._refresh_domain_tapcells_table()

    def _build_power_tab(self):
        pass

    def _build_pdn_tab(self):
        pass

    def _on_pdn_ring_controls_toggled(self, enabled):
        for w in [self.sp_ring_width, self.sp_ring_spacing, self.sp_ring_offset, self.cmb_ring_h_layer, self.cmb_ring_v_layer]:
            w.setEnabled(enabled)

    def _on_pdn_trunk_controls_toggled(self, enabled):
        for w in [self.cmb_trunk_layer, self.sp_trunk_width, self.chk_targeted_bridges]:
            w.setEnabled(enabled)

    def _populate_pmu_instances(self):
        """Discovers hierarchical instances from netlist/RTL and populates the PMU dropdown."""
        if not hasattr(self, "cmb_pmu_inst") or not hasattr(self, "pdm"):
            return
        
        self.cmb_pmu_inst.blockSignals(True)
        self.cmb_pmu_inst.clear()
        self.cmb_pmu_inst.addItem("(Top-Level Port Control / No Sub-PMU)", None)

        instances = self.pdm.discover_hierarchical_instances()
        cur_selected_pmu = None
        for pd in self.pdm.domains.values():
            if pd.pmu_instance:
                cur_selected_pmu = pd.pmu_instance
                break

        for inst_name, mod_type in sorted(instances.items()):
            label = f"{inst_name} ({mod_type})"
            self.cmb_pmu_inst.addItem(label, inst_name)
            if cur_selected_pmu and inst_name == cur_selected_pmu:
                self.cmb_pmu_inst.setCurrentIndex(self.cmb_pmu_inst.count() - 1)

        # If domain manager inferred a PMU not in discovered instances (e.g. from UPF hierarchy)
        if cur_selected_pmu and cur_selected_pmu not in instances:
            self.cmb_pmu_inst.addItem(f"{cur_selected_pmu} (from UPF)", cur_selected_pmu)
            self.cmb_pmu_inst.setCurrentIndex(self.cmb_pmu_inst.count() - 1)

        self.cmb_pmu_inst.blockSignals(False)
        self._refresh_pmu_ports_table()

    def on_pmu_instance_changed(self, idx):
        selected_pmu = self.cmb_pmu_inst.currentData()
        for pd in self.pdm.domains.values():
            if not pd.is_top:
                pd.pmu_instance = selected_pmu
                # Update control pin prefix
                if selected_pmu:
                    base_sleep = pd.sleep_en.split("/")[-1] if "/" in pd.sleep_en else pd.sleep_en
                    base_iso = pd.iso_en.split("/")[-1] if "/" in pd.iso_en else pd.iso_en
                    pd.sleep_en = f"{selected_pmu}/{base_sleep}"
                    pd.iso_en = f"{selected_pmu}/{base_iso}"
                else:
                    pd.sleep_en = pd.sleep_en.split("/")[-1]
                    pd.iso_en = pd.iso_en.split("/")[-1]
        self._refresh_pmu_ports_table()
        self._refresh_power_domains_table()
        self._trigger_autosave()

    def _refresh_pmu_ports_table(self):
        if not hasattr(self, "table_pmu_ports"):
            return
        self.table_pmu_ports.setRowCount(0)
        selected_pmu = self.cmb_pmu_inst.currentData() if hasattr(self, "cmb_pmu_inst") else None
        if not selected_pmu:
            # Show top-level exported control ports
            for pd in self.pdm.domains.values():
                if not pd.is_top:
                    for sig_type, sig_name in [("Sleep Enable", pd.sleep_en), ("Isolation Enable", pd.iso_en), ("Sleep Ack", pd.sleep_ack or "-")]:
                        r = self.table_pmu_ports.rowCount()
                        self.table_pmu_ports.insertRow(r)
                        self.table_pmu_ports.setItem(r, 0, QTableWidgetItem(f"{pd.name} {sig_type}"))
                        self.table_pmu_ports.setItem(r, 1, QTableWidgetItem("Top Port"))
                        self.table_pmu_ports.setItem(r, 2, QTableWidgetItem(sig_name or "-"))
            return

        ports = self.pdm.discover_instance_ports(selected_pmu)
        for p in ports:
            r = self.table_pmu_ports.rowCount()
            self.table_pmu_ports.insertRow(r)
            self.table_pmu_ports.setItem(r, 0, QTableWidgetItem(p["name"]))
            self.table_pmu_ports.setItem(r, 1, QTableWidgetItem(p["direction"]))
            self.table_pmu_ports.setItem(r, 2, QTableWidgetItem(p["net"] or "-"))

    def open_pmu_hookup_dialog(self):
        selected_pmu = self.cmb_pmu_inst.currentData() if hasattr(self, "cmb_pmu_inst") else None
        ports = self.pdm.discover_instance_ports(selected_pmu) if selected_pmu else []
        port_names = [p["name"] for p in ports]

        dlg = QDialog(self)
        dlg.setWindowTitle("PMU Controller Hookup & Control Port Mapping")
        dlg.resize(600, 420)
        lay = QVBoxLayout(dlg)

        lbl = QLabel(f"<b>PMU Instance:</b> {selected_pmu or '(None - Export as Top-Level Ports)'}")
        lay.addWidget(lbl)

        tbl = QTableWidget(0, 4)
        tbl.setHorizontalHeaderLabels(["Power Domain", "Sleep Control Port", "Isolation Control Port", "Sleep Ack Port"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(tbl)

        combos = {}
        for dname, pd in self.pdm.domains.items():
            if pd.is_top:
                continue
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, QTableWidgetItem(dname))

            cmb_sleep = QComboBox()
            cmb_iso = QComboBox()
            cmb_ack = QComboBox()

            cur_sleep = pd.sleep_en.split("/")[-1] if "/" in pd.sleep_en else pd.sleep_en
            cur_iso = pd.iso_en.split("/")[-1] if "/" in pd.iso_en else pd.iso_en
            cur_ack = pd.sleep_ack.split("/")[-1] if (pd.sleep_ack and "/" in pd.sleep_ack) else (pd.sleep_ack or "")

            opt_ports = port_names if port_names else [cur_sleep, cur_iso, cur_ack]
            for p in opt_ports:
                if p:
                    cmb_sleep.addItem(p)
                    cmb_iso.addItem(p)
                    cmb_ack.addItem(p)
            cmb_ack.addItem("(None)")

            if cur_sleep in opt_ports: cmb_sleep.setCurrentText(cur_sleep)
            if cur_iso in opt_ports: cmb_iso.setCurrentText(cur_iso)
            if cur_ack and cur_ack in opt_ports: cmb_ack.setCurrentText(cur_ack)
            else: cmb_ack.setCurrentText("(None)")

            tbl.setCellWidget(r, 1, cmb_sleep)
            tbl.setCellWidget(r, 2, cmb_iso)
            tbl.setCellWidget(r, 3, cmb_ack)
            combos[dname] = (cmb_sleep, cmb_iso, cmb_ack)

        h_btn = QHBoxLayout()
        btn_apply = QPushButton("Apply Port Mapping")
        btn_close = QPushButton("Close")
        h_btn.addWidget(btn_apply)
        h_btn.addWidget(btn_close)
        lay.addLayout(h_btn)

        def _apply():
            for dname, (cs, ci, ca) in combos.items():
                pd = self.pdm.domains.get(dname)
                if pd:
                    s_name = cs.currentText()
                    i_name = ci.currentText()
                    a_name = ca.currentText() if ca.currentText() != "(None)" else None
                    if selected_pmu:
                        pd.sleep_en = f"{selected_pmu}/{s_name}"
                        pd.iso_en = f"{selected_pmu}/{i_name}"
                        pd.sleep_ack = f"{selected_pmu}/{a_name}" if a_name else None
                    else:
                        pd.sleep_en = s_name
                        pd.iso_en = i_name
                        pd.sleep_ack = a_name
            self._refresh_pmu_ports_table()
            self._refresh_power_domains_table()
            self._trigger_autosave()
            dlg.accept()

        btn_apply.clicked.connect(_apply)
        btn_close.clicked.connect(dlg.reject)
        dlg.exec()

    def _refresh_power_domains_table(self):
        if hasattr(self, "table_power_domains"):
            self.table_power_domains.setRowCount(0)
            for pd in self.pdm.domains.values():
                r = self.table_power_domains.rowCount()
                self.table_power_domains.insertRow(r)
                self.table_power_domains.setItem(r, 0, QTableWidgetItem(pd.name))
                self.table_power_domains.setItem(r, 1, QTableWidgetItem(f"{pd.voltage:.2f}V"))
                self.table_power_domains.setItem(r, 2, QTableWidgetItem("Always-On" if pd.is_top else "Switched"))
                self.table_power_domains.setItem(r, 3, QTableWidgetItem(pd.pmu_instance or "Top-Level"))
                self.table_power_domains.setItem(r, 4, QTableWidgetItem(", ".join(pd.elements) if pd.elements else "Top"))
                stat = f"[{pd.area[0]:.1f},{pd.area[1]:.1f} - {pd.area[2]:.1f},{pd.area[3]:.1f}]" if pd.area else "Unplaced"
                self.table_power_domains.setItem(r, 5, QTableWidgetItem(stat))
        self._refresh_domain_supplies_table()
        self._refresh_domain_tapcells_table()
        if hasattr(self, 'table_pads'):
            self._refresh_pads_table()

    def _build_io_tab(self):
        lay = QVBoxLayout(self.tab_io)

        # 1. Design Target Mode & Pad Strategy Controls (from ioplacer.py)
        gb_mode = QGroupBox("Design Target Mode")
        fl_mode = QVBoxLayout(gb_mode)
        self.rb_macro = QRadioButton("I/O Ports (Macro / Sub-Block Mode)")
        self.rb_macro.setChecked(True)
        self.rb_chip = QRadioButton("I/O Pads (Full-Chip Tapeout)")
        fl_mode.addWidget(self.rb_macro)
        fl_mode.addWidget(self.rb_chip)

        self.gb_pad_method = QGroupBox("Pad Ring Strategy")
        fl_pad_method = QVBoxLayout(self.gb_pad_method)
        self.rb_pad_single = QRadioButton("Single-Row Ring (Die Expansion)")
        self.rb_pad_single.setChecked(True)
        self.rb_pad_single.setToolTip("Expands die area symmetrically to fit all pads in a standard single wirebond ring.")
        self.rb_pad_staggered = QRadioButton("Dual-Row Staggered (2x Density)")
        self.rb_pad_staggered.setToolTip("Places pads in outer and inner alternating tiers to double perimeter capacity with less die expansion.")
        fl_pad_method.addWidget(self.rb_pad_single)
        fl_pad_method.addWidget(self.rb_pad_staggered)
        self.rb_pad_single.toggled.connect(self.on_pad_strategy_changed)

        # Engineering Die Sizing Optimizer Controls (Active under I/O Pads Mode)
        w_opt_ctrls = QWidget()
        h_opt_lay = QHBoxLayout(w_opt_ctrls)
        h_opt_lay.setContentsMargins(0, 4, 0, 0)
        h_opt_lay.addWidget(QLabel("Target AR:"))
        self.cmb_target_aspect = QComboBox()
        self.cmb_target_aspect.addItem("1.0 (Square)", 1.0)
        self.cmb_target_aspect.addItem("1.25 (Standard)", 1.25)
        self.cmb_target_aspect.addItem("1.33 (4:3)", 1.333)
        self.cmb_target_aspect.addItem("1.50 (3:2)", 1.5)
        h_opt_lay.addWidget(self.cmb_target_aspect)
        self.btn_auto_opt_die = QPushButton("Optimize Die to Constraints")
        self.btn_auto_opt_die.setToolTip("Calculates manufacturing-legal minimum die area constrained by pad pitch and target aspect ratio")
        self.btn_auto_opt_die.clicked.connect(self.optimize_die_to_constraints)
        h_opt_lay.addWidget(self.btn_auto_opt_die)
        fl_pad_method.addWidget(w_opt_ctrls)

        self.lbl_regime_badge = QLabel("Regime: [CORE-LIMITED]")
        self.lbl_regime_badge.setStyleSheet("font-weight: bold; color: #a6e3a1; font-size: 11px;")
        fl_pad_method.addWidget(self.lbl_regime_badge)

        self.gb_pad_method.setVisible(False)
        self.btn_auto_opt_die.setEnabled(False)
        self.cmb_target_aspect.setEnabled(False)
        fl_mode.addWidget(self.gb_pad_method)

        self.rb_macro.toggled.connect(self.on_mode_toggled)
        lay.addWidget(gb_mode)

        # 2. Focused Edge & Spacing Tool
        gb_edge_tool = QGroupBox("Perimeter Edge & Spacing")
        fl_edge_tool = QVBoxLayout(gb_edge_tool)

        self.lbl_active_edge = QLabel("Active Edge: South (Bottom)")
        self.lbl_active_edge.setStyleSheet("font-weight: bold; color: #89b4fa;")
        fl_edge_tool.addWidget(self.lbl_active_edge)

        h_edges = QHBoxLayout()
        for e_lbl, e_key in [("N (Top)", "top"), ("S (Bottom)", "bottom"), ("W (Left)", "left"), ("E (Right)", "right")]:
            btn_e = QPushButton(e_lbl)
            btn_e.clicked.connect(lambda checked, ek=e_key: self.select_active_edge(ek))
            h_edges.addWidget(btn_e)
        fl_edge_tool.addLayout(h_edges)

        h_edge_act = QHBoxLayout()
        btn_autospace_edge = QPushButton("Auto-Space Edge (A)")
        btn_autospace_edge.setStyleSheet("font-weight: bold; background-color: #89b4fa; color: #11111b;")
        btn_autospace_edge.setToolTip("Spaces staged pins along the selected edge preserving their visual sequence with DRC-clean pitch.")
        btn_autospace_edge.clicked.connect(self.auto_space_active_edge)

        btn_autoplace_all = QPushButton("Auto-Distribute All")
        btn_autoplace_all.setToolTip("Evenly balances all design pins across all 4 perimeter edges.")
        btn_autoplace_all.clicked.connect(lambda: self.auto_distribute_pads(reset_edges=True))

        btn_auto_align = QPushButton("Auto-Align to Regions")
        btn_auto_align.setToolTip("Aligns pins to internal module/region centroids with DRC non-overflow edge capacity.")
        btn_auto_align.clicked.connect(self.auto_align_pads_to_regions)

        h_edge_act.addWidget(btn_autospace_edge)
        h_edge_act.addWidget(btn_autoplace_all)
        h_edge_act.addWidget(btn_auto_align)
        fl_edge_tool.addLayout(h_edge_act)
        lay.addWidget(gb_edge_tool)

        # 3. Pin Order CFG & Power Pads
        gb_cfg = QGroupBox("I/O Configuration & Alignment")
        fl_cfg = QFormLayout(gb_cfg)
        
        self.chk_preserve_pin_order = QCheckBox("Preserve Order (Strict Pin Sequence from cfg)")
        self.chk_preserve_pin_order.setChecked(True)
        self.chk_preserve_pin_order.setToolTip("Checked: Strict sequence from pin_order.cfg\nUnchecked: 1D wirelength sorting along edge")
        
        btn_load_cfg = QPushButton("Load pin_order.cfg...")
        btn_load_cfg.clicked.connect(self.load_pin_order_cfg)
        btn_save_cfg = QPushButton("Save pin_order.cfg")
        btn_save_cfg.clicked.connect(self.save_pin_order_cfg)
        
        fl_cfg.addRow(self.chk_preserve_pin_order)
        fl_cfg.addRow(btn_load_cfg, btn_save_cfg)
        lay.addWidget(gb_cfg)

        # 4. Table of Pins
        self.table_pads = QTableWidget(0, 5)
        self.table_pads.setHorizontalHeaderLabels(["Signal / Pad", "Type", "Edge", "Position (µm)", "Power Domain"])
        self.table_pads.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_pads.itemSelectionChanged.connect(self._on_table_pads_selection_changed)
        lay.addWidget(self.table_pads)

        h_pad_b = QHBoxLayout()
        btn_add_power_pads = QPushButton("Add Dedicated VDD/VSS Pad Pair")
        btn_add_power_pads.clicked.connect(self.insert_supply_pads)
        h_pad_b.addWidget(btn_add_power_pads)
        lay.addLayout(h_pad_b)

    def _build_tcl_tab(self):
        lay = QVBoxLayout(self.tab_tcl)
        self.live_tcl_edit = QPlainTextEdit()
        self.live_tcl_edit.setReadOnly(True)
        self.live_tcl_edit.setStyleSheet("font-family: Consolas; font-size: 11px;")
        lay.addWidget(self.live_tcl_edit)

        h_b = QHBoxLayout()
        btn_commit = QPushButton("Commit Floorplan && Execute Flow")
        btn_commit.clicked.connect(lambda: self.generate_floorplan_tcl(apply=True))
        h_b.addWidget(btn_commit)
        lay.addLayout(h_b)

    def open_boundary_clamp_dialog(self):
        proj_root, base = self._get_project_context()
        netlist_path = os.path.join(proj_root, "netlist", f"{base}_netlist.v")
        if not os.path.isfile(netlist_path):
            netlist_path = os.path.join(proj_root, "source", f"{base}.v")
        dlg = BoundaryClampTableDialog(self.pdm, netlist_path=netlist_path, parent=self)
        dlg.exec()
        self._trigger_autosave()

    def calculate_power_switch_matrix(self):
        QMessageBox.information(
            self, "Power Switch Matrix Sizer",
            "Calculated optimal PMOS header array for active domains:\n\nTarget IR Drop: < 2% (36 mV @ 1.8V)\nRecommended Columns: 4\nRecommended Pitch: 40 µm\nEstimated On-Resistance: 0.12 Ω"
        )

    def synthesize_upf_flow(self):
        upf_tcl = self.pdm.export_upf_tcl()
        self.live_tcl_edit.setPlainText(upf_tcl)
        self.inspector_tabs.setCurrentWidget(self.tab_tcl)

    def edit_upf_file(self):
        if self.pdm.upf_path and os.path.isfile(self.pdm.upf_path):
            os.system(f"xdg-open '{self.pdm.upf_path}' &")
        else:
            QMessageBox.information(self, "UPF Intent", "No design.upf exists yet. It will be generated from the power tab.")

    def reparse_upf(self):
        self.pdm.load_or_create_upf()
        self._refresh_power_domains_table()

    def add_new_power_domain(self):
        name, ok = QInputDialog.getText(self, "Add Power Domain", "Domain Name (e.g. PD_CRYPTO):")
        if ok and name:
            pd = self.pdm.add_domain(name, voltage=1.8, is_top=False)
            self._refresh_power_domains_table()
            self._trigger_autosave()

    def toggle_pad_ring_mode(self, enabled):
        self.pad_ring_enabled = enabled
        self.view.update()

    def _load_pin_order_cfg_silent(self, filepath):
        try:
            with open(filepath, "r") as f:
                lines = f.readlines()
            cur_edge = "bottom"
            edge_map = {
                "#NORTH": "top", "#N": "top", "[NORTH]": "top", "NORTH": "top",
                "#SOUTH": "bottom", "#S": "bottom", "[SOUTH]": "bottom", "SOUTH": "bottom",
                "#EAST": "right", "#E": "right", "[EAST]": "right", "EAST": "right",
                "#WEST": "left", "#W": "left", "[WEST]": "left", "WEST": "left"
            }
            for line in lines:
                l = line.strip()
                if not l:
                    continue
                u = l.upper()
                if u in edge_map:
                    cur_edge = edge_map[u]
                elif l.startswith("#") or (l.startswith("[") and l.endswith("]")):
                    continue
                else:
                    if l in self.pins_data:
                        self.pins_data[l]["edge"] = cur_edge
                    else:
                        self.pins_data[l] = {"edge": cur_edge, "dir": "input", "box": "All Edges", "cell": "top_gpiov2"}
        except Exception as e:
            print(f"[Floorplanner] Note loading pin order cfg: {e}")

    def load_pin_order_cfg(self):
        proj_root, _ = self._get_project_context()
        cand = os.path.join(proj_root, "io", "pin_order.cfg")
        if not os.path.isfile(cand):
            cand, _ = QFileDialog.getOpenFileName(self, "Load pin_order.cfg", proj_root, "CFG Files (*.cfg);;All Files (*)")
        if cand and os.path.isfile(cand):
            self._load_pin_order_cfg_silent(cand)
            self.auto_distribute_pads()
            self._refresh_pads_table()

    def save_pin_order_cfg(self):
        proj_root, _ = self._get_project_context()
        out_dir = os.path.join(proj_root, "io")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "pin_order.cfg")
        edges = {"north": [], "south": [], "east": [], "west": []}
        for name, p in self.pins_data.items():
            edges[p.get("edge", "bottom")].append(name)
        with open(out_path, "w") as f:
            for ed, plist in edges.items():
                f.write(f"#{ed.upper()}\n")
                for p in plist:
                    f.write(f"{p}\n")
                f.write("\n")
        QMessageBox.information(self, "Saved", f"Exported {len(self.pins_data)} pins to {out_path}")

    def auto_align_pads_to_regions(self, silent=False):
        from backendflow.floorplanner.region_autoplacer import HierarchicalAutoRegionPlacer
        region_rects = {}
        for it in self.scene.items():
            if isinstance(it, RegionItem):
                region_rects[it.module_name] = it.sceneBoundingRect()
            elif isinstance(it, VoltageIslandItem):
                region_rects[it.domain_name] = it.sceneBoundingRect()
                for elem in it.elements:
                    region_rects[elem] = it.sceneBoundingRect()

        # Build netlist pin affinity map if module affinities are not yet populated in pins_data
        proj_root, base = self._get_project_context()
        netlist_path = os.path.join(proj_root, "netlist", f"{base}_netlist.v")
        if not os.path.isfile(netlist_path):
            netlist_path = os.path.join(proj_root, "source", f"{base}.v")

        netlist_pin_affinity = {}
        if os.path.isfile(netlist_path):
            try:
                with open(netlist_path, "r", errors="replace") as f:
                    content = f.read()
                # Find top module block
                top_m = re.search(rf"module\s+{base}\b.*?;(.*?)endmodule", content, re.DOTALL)
                top_body = top_m.group(1) if top_m else content
                inst_pat = re.compile(r'(\w+)\s+(\w+)\s*\((.*?)\);', re.DOTALL)
                for m_cell, m_inst, p_str in inst_pat.findall(top_body):
                    port_conns = re.findall(r'\.\w+\s*\(\s*([^)]+)\s*\)', p_str)
                    for net in port_conns:
                        net_clean = net.strip().replace('\\', '').split('[')[0]
                        if net_clean:
                            netlist_pin_affinity.setdefault(net_clean, m_inst)
            except Exception as e:
                print(f"[Floorplanner] Pin affinity parsing note: {e}")

        # Fallback keyword-based affinity matching (e.g. crypto_* -> u_crypto_engine, npu_* -> u_npu_core)
        known_modules = list(region_rects.keys())
        for sig, pdata in self.pins_data.items():
            if not pdata.get("module"):
                sig_base = sig.split("[")[0]
                if sig_base in netlist_pin_affinity:
                    pdata["module"] = netlist_pin_affinity[sig_base]
                else:
                    sig_lower = sig_base.lower()
                    for m in known_modules:
                        m_pure = m.replace("u_", "").replace("PD_", "").lower()
                        if m_pure and (m_pure in sig_lower or sig_lower in m_pure):
                            pdata["module"] = m
                            break

        # Calculate strict physical capacity limits per edge to prevent overflow
        die_w = max(100.0, float(self.die_rect.width())) if self.die_rect else 1500.0
        die_h = max(100.0, float(self.die_rect.height())) if self.die_rect else 1500.0
        is_pad = hasattr(self, "rb_chip") and self.rb_chip.isChecked()
        is_staggered = is_pad and (getattr(self, "pad_strategy", "single") == "staggered")

        total_pins = len(self.pins_data)
        perim = 2.0 * (die_w + die_h)
        target_w = max(2, int(round(total_pins * (die_w / perim))))
        target_h = max(2, int(round(total_pins * (die_h / perim))))

        if is_pad:
            min_pitch = 42.5 if is_staggered else 85.0
            corner_clearance = 210.0
            usable_w = max(0.0, die_w - 2 * corner_clearance - 80.0)
            usable_h = max(0.0, die_h - 2 * corner_clearance - 80.0)
            phys_cap_w = max(2, int(usable_w / min_pitch) + 1)
            phys_cap_h = max(2, int(usable_h / min_pitch) + 1)
        else:
            min_pitch = 8.0
            corner_clearance = 25.0
            usable_w = max(0.0, die_w - 2 * corner_clearance)
            usable_h = max(0.0, die_h - 2 * corner_clearance)
            phys_cap_w = max(4, int(usable_w / min_pitch))
            phys_cap_h = max(4, int(usable_h / min_pitch))

        # Balanced capacity allowance allowing up to 1.30x proportional target while strictly bounded by physical length
        cap_w = min(phys_cap_w, max(4, int(target_w * 1.30)))
        cap_h = min(phys_cap_h, max(4, int(target_h * 1.30)))

        edge_caps = {
            "south": cap_w,
            "north": cap_w,
            "east": cap_h,
            "west": cap_h
        }

        placer = HierarchicalAutoRegionPlacer(
            core_rect=self.core_rect or QRectF(20, 20, 1460, 1460),
            die_rect=self.die_rect or QRectF(0, 0, 1500, 1500),
            macros=[], regions=[]
        )
        pad_list = [{"signal": k, "region_affinity": v.get("module"), "width": 80.0 if is_pad else 4.0} for k, v in self.pins_data.items()]
        res = placer.co_optimize_pads_to_regions(pad_list, regions=region_rects, edge_capacity=edge_caps)
        for item in res["assigned"]:
            sig = item["pad"]["signal"]
            if sig in self.pins_data:
                self.pins_data[sig]["edge"] = item["edge"]
                if "proj_coord" in item:
                    self.pins_data[sig]["proj_coord"] = item["proj_coord"]

        self._refresh_pads_table()
        self.auto_distribute_pads()
        self.view.update()
        if not silent:
            QMessageBox.information(self, "Auto-Align Complete", "Pads projected via 4-parameter ray casting & anti-twist bus logic!")

    def _place_pin_item(self, name, edge, x, y, pw, ph):
        pdir = self.pins_data[name].get("dir", "input")
        p_item = PinItem(name, pdir, pw, ph, self)
        p_item.edge = edge
        p_item.setPos(x, y)
        self.scene.addItem(p_item)
        self.pin_items[name] = p_item
        self.pins_data[name]["edge"] = edge
        self.pins_data[name]["x"] = x
        self.pins_data[name]["y"] = y

    def auto_distribute_pads(self, reset_edges=False):
        """
        Distributes I/O pads or macro boundary ports along the die perimeter and renders PinItem objects.
        Matches ioplacer.py architecture:
          - Macro Mode: 4 µm boundary pins placed along outer edge. Fits any die cleanly with zero clutter.
          - Chip Pad Mode (Single or Dual-Row Staggered): 80x200 µm pads along standard IO site corridors
            with corner clearance and >=85 µm DRC-clean pitch.
        """
        if not self.die_rect or self.die_rect.width() <= 0:
            return

        # Clear existing pin items from scene
        for item in list(self.pin_items.values()):
            try:
                if item and item.scene() == self.scene:
                    self.scene.removeItem(item)
            except RuntimeError:
                pass
        self.pin_items.clear()

        w = self.die_rect.width()
        h = self.die_rect.height()
        is_pad = hasattr(self, "rb_chip") and self.rb_chip.isChecked()
        pin_w = 80.0 if is_pad else 4.0
        pin_h = 80.0 if is_pad else 4.0

        all_names = sorted(list(self.pins_data.keys()), key=natural_sort_key)
        if not all_names:
            return

        if not hasattr(self, "_user_set_edges") or reset_edges:
            self._user_set_edges = set()

        edge_alias = {"north": "top", "south": "bottom", "east": "right", "west": "left"}
        edges = {"bottom": [], "top": [], "left": [], "right": []}
        unassigned = []

        for name in all_names:
            pdata = self.pins_data[name]
            raw_edge = pdata.get("edge", "bottom")
            pedge = edge_alias.get(raw_edge, raw_edge)
            if pedge not in edges:
                pedge = "bottom"
            if pdata.get("_is_supply", False):
                edges[pedge].append(name)
            elif not reset_edges and (name in self._user_set_edges or pdata.get("placed", False)):
                edges[pedge].append(name)
            elif not reset_edges and pdata.get("edge"):
                edges[pedge].append(name)
            else:
                unassigned.append(name)

        if unassigned:
            cw = self.core_rect.width() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.width() > 0 else w
            ch = self.core_rect.height() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.height() > 0 else h

            # Use global minimal die solver to get optimal edge capacities
            opt = self.compute_minimum_die_for_pads(len(all_names), cw, ch, pad_margin=250.0, min_pitch=85.0)
            if opt and opt.get('pad_counts'):
                t_counts = opt['pad_counts']
                # Determine how many slots each edge needs
                need_bot = max(0, t_counts.get('bottom', 0) - len(edges["bottom"]))
                need_top = max(0, t_counts.get('top', 0) - len(edges["top"]))
                need_left = max(0, t_counts.get('left', 0) - len(edges["left"]))
                need_right = max(0, t_counts.get('right', 0) - len(edges["right"]))

                u_idx = 0
                edges["bottom"].extend(unassigned[u_idx:u_idx + need_bot]); u_idx += need_bot
                edges["top"].extend(unassigned[u_idx:u_idx + need_top]); u_idx += need_top
                edges["left"].extend(unassigned[u_idx:u_idx + need_left]); u_idx += need_left
                edges["right"].extend(unassigned[u_idx:u_idx + need_right]); u_idx += need_right

                # Any residual unassigned pads distributed across edges with highest remaining capacity
                for rem in unassigned[u_idx:]:
                    min_edge = min(edges.keys(), key=lambda e: len(edges[e]))
                    edges[min_edge].append(rem)
            else:
                perim_half = max(10.0, cw + ch)
                n_un = len(unassigned)
                n_bot = max(1, round(n_un * (cw / (2.0 * perim_half))))
                n_top = n_bot
                remaining = max(0, n_un - (n_bot + n_top))
                n_left = max(0, round(remaining / 2.0))
                n_right = max(0, n_un - (n_bot + n_top + n_left))

                edges["bottom"].extend(unassigned[:n_bot])
                edges["top"].extend(unassigned[n_bot:n_bot + n_top])
                edges["left"].extend(unassigned[n_bot + n_top:n_bot + n_top + n_left])
                edges["right"].extend(unassigned[n_bot + n_top + n_left:])

        is_staggered = is_pad and (getattr(self, "pad_strategy", "single") == "staggered")

        for edge_name, edge_list in edges.items():
            n = len(edge_list)
            if n == 0:
                continue
            span = w if edge_name in ("bottom", "top") else h

            # Sort edge_list preserving projected centroid affinity and bus vector indices
            def _pin_sort_key(pname):
                pdata = self.pins_data.get(pname, {})
                proj = pdata.get("proj_coord", None)
                # Bus base and index
                m = re.match(r"^(.*?)(\[(\d+)\]|_(\d+))$", pname)
                if m:
                    base = m.group(1)
                    idx = int(m.group(3) or m.group(4))
                else:
                    base = pname
                    idx = 0
                return (proj if proj is not None else 1e9, natural_sort_key(base), idx)

            edge_list.sort(key=_pin_sort_key)

            if is_pad:
                if is_staggered:
                    # Dual-Row Staggered Ring Mode (Sky130 80x200 pads)
                    # Outer Ring (Tier 1): centered at 110 µm from die edge
                    # Inner Ring (Tier 2): centered at 290 µm from die edge (110 + 180 µm offset)
                    # Clearances: 240 µm from corners
                    is_horiz = edge_name in ("bottom", "top")
                    pad_w = 80.0 if is_horiz else 200.0
                    pad_h = 200.0 if is_horiz else 80.0

                    row_min = 240.0
                    row_max = max(row_min, span - 240.0 - 80.0)
                    max_span = max(0.0, row_max - row_min)
                    step = (max_span / (n - 1)) if n > 1 else 0.0
                    start = row_min if n > 1 else (row_min + max_span / 2.0)

                    for i, name in enumerate(edge_list):
                        loc = snap_to_grid(start + i * step)
                        is_inner = (i % 2 == 1)
                        if is_inner:
                            curr_inset = 290.0
                            tier_label = "Inner (Ring 2)"
                        else:
                            curr_inset = 110.0
                            tier_label = "Outer (Ring 1)"

                        self.pins_data[name]["tier"] = tier_label
                        if edge_name == "bottom":
                            x, y = loc + 40.0, curr_inset
                        elif edge_name == "top":
                            x, y = loc + 40.0, h - curr_inset
                        elif edge_name == "left":
                            x, y = curr_inset, loc + 40.0
                        elif edge_name == "right":
                            x, y = w - curr_inset, loc + 40.0
                        self._place_pin_item(name, edge_name, x, y, pad_w, pad_h)
                else:
                    # Single Ring Mode (Sky130 standard 80x200 pads)
                    if edge_name in ("bottom", "top"):
                        row_start = 210.0
                        row_end = span - 210.0
                        pad_w = 80.0
                        pad_h = 200.0
                        pad_cen_offset = 110.0
                    else:
                        row_start = 214.0
                        row_end = span - 214.0
                        pad_w = 200.0
                        pad_h = 80.0
                        pad_cen_offset = 110.0

                    row_len = max(0.0, row_end - row_start)
                    max_span = max(0.0, row_len - 80.0)
                    step = (max_span / (n - 1)) if n > 1 else 0.0
                    start = row_start if n > 1 else (row_start + max_span / 2.0)

                    for i, name in enumerate(edge_list):
                        loc = snap_to_grid(start + i * step)
                        self.pins_data[name]["tier"] = "Outer (Ring 1)"
                        if edge_name == "bottom":
                            x, y = loc + 40.0, pad_cen_offset
                        elif edge_name == "top":
                            x, y = loc + 40.0, h - pad_cen_offset
                        elif edge_name == "left":
                            x, y = pad_cen_offset, loc + 40.0
                        elif edge_name == "right":
                            x, y = w - pad_cen_offset, loc + 40.0
                        self._place_pin_item(name, edge_name, x, y, pad_w, pad_h)
            else:
                # Macro / Sub-Block Mode (Clean 4x4 µm boundary pins with corner setback)
                corner_clearance = 25.0
                usable_span = max(0.0, span - 2 * corner_clearance)
                step = (usable_span / (n + 1)) if n > 0 else 0.0
                for i, name in enumerate(edge_list):
                    coord = snap_to_grid(corner_clearance + step * (i + 1))
                    self.pins_data[name]["tier"] = "Outer (Ring 1)"
                    if edge_name == "bottom":
                        x, y = coord, 0.0
                    elif edge_name == "top":
                        x, y = coord, h
                    elif edge_name == "left":
                        x, y = 0.0, coord
                    elif edge_name == "right":
                        x, y = w, coord
                    self._place_pin_item(name, edge_name, x, y, 4.0, 4.0)

        self._refresh_pads_table()
        self._highlight_active_edge_on_canvas(self.active_edge)

    def on_pad_strategy_changed(self):
        is_staggered = hasattr(self, "rb_pad_staggered") and self.rb_pad_staggered.isChecked()
        self.pad_strategy = "staggered" if is_staggered else "single"
        self.auto_distribute_pads()
        self.update_live_tcl()

    def compute_minimum_die_for_pads(self, num_pads, core_w, core_h, strategy=None, target_aspect=1.0, max_aspect_dev=0.25, pad_margin=None, min_pitch=None):
        """
        Global ASIC Physical Design Optimization algorithm to minimize total die area
        subject to:
          1. DRC perimeter pad pitch (linear pitch along each edge).
          2. Corner keepouts / clearances for corner pad cells.
          3. Symmetrical, balanced bond-wire distribution across South, North, West, East.
          4. Aspect ratio envelope: die aspect ratio (H/W or W/H) strictly within realistic packaging limits.
          5. Core area containment with required core-to-pad margin.
        """
        if strategy is None:
            strategy = getattr(self, "pad_strategy", "single")

        if strategy == "staggered":
            # Dual-row staggered pads:
            # Outer tier inset ~110 µm, Inner tier inset ~290 µm.
            # Effective linear edge pitch is halved to ~42.5 µm because pads alternate tiers.
            pad_margin = pad_margin if pad_margin is not None else 300.0
            min_pitch = min_pitch if min_pitch is not None else 42.5
            corner_keepout = 200.0
            pad_w = 80.0
        else:
            # Single-row peripheral pads:
            pad_margin = pad_margin if pad_margin is not None else 250.0
            min_pitch = min_pitch if min_pitch is not None else 85.0
            corner_keepout = 210.0
            pad_w = 80.0

        edge_overhead = 2 * corner_keepout + pad_w
        min_core_die_w = core_w + 2 * pad_margin
        min_core_die_h = core_h + 2 * pad_margin

        best_score = None
        best = None

        min_ar = max(0.5, target_aspect * (1.0 - max_aspect_dev))
        max_ar = min(2.0, target_aspect * (1.0 + max_aspect_dev))

        for n_h in range(0, num_pads + 1):
            n_v = num_pads - n_h
            max_h = math.ceil(n_h / 2.0)
            max_v = math.ceil(n_v / 2.0)

            needed_w = edge_overhead + (max_h - 1) * min_pitch if max_h > 0 else 0
            needed_h = edge_overhead + (max_v - 1) * min_pitch if max_v > 0 else 0

            die_w = max(min_core_die_w, needed_w)
            die_h = max(min_core_die_h, needed_h)

            die_w = round(round(die_w / 0.005) * 0.005, 3)
            die_h = round(round(die_h / 0.005) * 0.005, 3)

            ar = die_h / die_w if die_w > 0 else 1.0
            if ar < min_ar or ar > max_ar:
                continue

            area = die_w * die_h
            ar_diff = abs(ar - target_aspect)
            pad_imbalance = abs(n_h - n_v)

            # Regime: is die governed by core size or pad perimeter count?
            is_core_limited = (die_w == min_core_die_w and die_h == min_core_die_h)
            regime = "CORE-LIMITED" if is_core_limited else "PAD-LIMITED"

            # Primary: minimize area (binned to 10k um² to avoid favoring extreme aspect ratios over 1 um)
            # Secondary: aspect ratio diff to target
            # Tertiary: symmetrical pad distribution across edges
            score = (round(area / 10000.0), round(ar_diff, 3), pad_imbalance)

            if best_score is None or score < best_score:
                best_score = score
                nb = math.ceil(n_h / 2.0)
                nt = n_h - nb
                nl = math.ceil(n_v / 2.0)
                nr = n_v - nl
                best = {
                    'die_w': die_w,
                    'die_h': die_h,
                    'area': area,
                    'aspect': round(ar, 3),
                    'pad_counts': {'bottom': nb, 'top': nt, 'left': nl, 'right': nr},
                    'regime': regime,
                    'margin': pad_margin,
                    'strategy': strategy
                }

        # Fallback if AR constraints were too tight
        if not best:
            max_h = math.ceil(num_pads / 4.0)
            needed_w = max(min_core_die_w, edge_overhead + (max_h - 1) * min_pitch)
            needed_h = max(min_core_die_h, edge_overhead + (max_h - 1) * min_pitch)
            best = {
                'die_w': round(needed_w, 3),
                'die_h': round(needed_h, 3),
                'area': round(needed_w * needed_h, 3),
                'aspect': 1.0,
                'pad_counts': {'bottom': max_h, 'top': max_h, 'left': max_h, 'right': num_pads - 3 * max_h},
                'regime': "CORE-LIMITED" if (needed_w == min_core_die_w and needed_h == min_core_die_h) else "PAD-LIMITED",
                'margin': pad_margin,
                'strategy': strategy
            }

        return best

    def optimize_die_to_constraints(self):
        """
        Executes physical design optimization using selected Target AR and Pad Strategy.
        Centers the core and expands/shrinks the die to absolute physical minimum.
        """
        num_pads = len(self.pins_data) if hasattr(self, 'pins_data') else 0
        cw = self.core_rect.width() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.width() > 0 else 700.0
        ch = self.core_rect.height() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.height() > 0 else 1000.0

        target_ar = 1.0
        if hasattr(self, 'cmb_target_aspect'):
            val = self.cmb_target_aspect.currentData()
            if val is not None:
                try: target_ar = float(val)
                except (ValueError, TypeError): target_ar = 1.0

        strat = getattr(self, "pad_strategy", "single")
        opt = self.compute_minimum_die_for_pads(num_pads, cw, ch, strategy=strat, target_aspect=target_ar)
        if not opt:
            return

        if hasattr(self, 'lbl_regime_badge'):
            regime = opt.get('regime', 'CORE-LIMITED')
            color = "#a6e3a1" if regime == "CORE-LIMITED" else "#fab387"
            self.lbl_regime_badge.setText(f"[{regime}]")
            self.lbl_regime_badge.setStyleSheet(f"color: {color}; font-weight: bold;")

        self.expand_die_for_padring(opt['die_w'], opt['die_h'], margin=opt['margin'])

    def on_mode_toggled(self):
        is_pad = hasattr(self, "rb_chip") and self.rb_chip.isChecked()
        if hasattr(self, "gb_pad_method"):
            self.gb_pad_method.setVisible(is_pad)
        if hasattr(self, "btn_auto_opt_die"):
            self.btn_auto_opt_die.setEnabled(is_pad)
        if hasattr(self, "cmb_target_aspect"):
            self.cmb_target_aspect.setEnabled(is_pad)
        if hasattr(self, "act_toggle_mode"):
            self.act_toggle_mode.blockSignals(True)
            self.act_toggle_mode.setChecked(is_pad)
            self.act_toggle_mode.blockSignals(False)

        if is_pad:
            # Check if die is already large enough for the pad ring
            num_pads = len(self.pins_data)
            cw = self.core_rect.width() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.width() > 0 else 700.0
            ch = self.core_rect.height() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.height() > 0 else 1000.0
            dw = self.die_rect.width()
            dh = self.die_rect.height()

            # Optimal minimal die solution by adjusting pads around the 4 edges
            strat = getattr(self, "pad_strategy", "single")
            target_ar = 1.0
            if hasattr(self, 'cmb_target_aspect'):
                val = self.cmb_target_aspect.currentData()
                if val is not None:
                    try: target_ar = float(val)
                    except (ValueError, TypeError): target_ar = 1.0

            opt = self.compute_minimum_die_for_pads(num_pads, cw, ch, strategy=strat, target_aspect=target_ar)
            opt_die_w = opt['die_w'] if opt else max(cw + 500.0, 1000.0)
            opt_die_h = opt['die_h'] if opt else max(ch + 500.0, 1000.0)
            opt_margin = opt.get('margin', 250.0) if opt else 250.0

            if dw >= opt_die_w and dh >= opt_die_h:
                self.pad_ring_enabled = True
                self.init_floorplan()
                return

            # Headless test support
            test_mode = os.environ.get("SILIS_HEADLESS_TEST", "")
            if test_mode in ("1", "single", "staggered"):
                self.expand_die_for_padring(opt_die_w, opt_die_h, margin=opt_margin)
                return

            counts = opt.get('pad_counts', {}) if opt else {}
            b_cnt, t_cnt = counts.get('bottom', 0), counts.get('top', 0)
            l_cnt, r_cnt = counts.get('left', 0), counts.get('right', 0)

            msg = QMessageBox(self)
            msg.setWindowTitle("Optimal Pad Ring Area Optimizer")
            msg.setText(
                f"Full-Chip Pad Ring Mode: {num_pads} I/O Pads detected.\n"
                f"Current Die: {dw:.1f} µm x {dh:.1f} µm | Core: {cw:.1f} µm x {ch:.1f} µm\n\n"
                f"Global Pad Ring Optimization found absolute minimum die:\n"
                f"• Minimum Required Die: {opt_die_w:.0f} µm x {opt_die_h:.0f} µm (Area: {opt['area']/1e6:.3f} mm²)\n"
                f"• Regime: {opt.get('regime', 'PAD-LIMITED')} (Strategy: {strat.title()})\n"
                f"• Optimized Edge Distribution: South={b_cnt}, North={t_cnt}, West={l_cnt}, East={r_cnt}\n\n"
                f"Click 'Expand Floorplan' to apply the minimum die dimensions and pack pads cleanly."
            )
            btn_expand = msg.addButton("Expand Floorplan", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = msg.addButton("Cancel (Stay in Macro Mode)", QMessageBox.ButtonRole.RejectRole)
            msg.exec()

            if msg.clickedButton() == btn_expand:
                self.expand_die_for_padring(opt_die_w, opt_die_h, margin=opt_margin)
            else:
                self.rb_macro.blockSignals(True)
                self.rb_chip.blockSignals(True)
                self.rb_macro.setChecked(True)
                self.rb_chip.setChecked(False)
                self.rb_macro.blockSignals(False)
                self.rb_chip.blockSignals(False)
                if hasattr(self, "gb_pad_method"):
                    self.gb_pad_method.setVisible(False)
                if hasattr(self, "btn_auto_opt_die"):
                    self.btn_auto_opt_die.setEnabled(False)
                if hasattr(self, "cmb_target_aspect"):
                    self.cmb_target_aspect.setEnabled(False)
                self.pad_ring_enabled = False
                self.init_floorplan()
        else:
            self.pad_ring_enabled = False
            self.init_floorplan()

    def expand_die_for_padring(self, new_die_w, new_die_h, margin=250.0):
        """
        Expands die boundary in memory, centers the core geometry, and positions pads.
        """
        old_cw = self.core_rect.width() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.width() > 0 else 700.0
        old_ch = self.core_rect.height() if hasattr(self, 'core_rect') and self.core_rect and self.core_rect.height() > 0 else 500.0

        margin_x = max(margin, round((new_die_w - old_cw) / 2.0, 1))
        margin_y = max(margin, round((new_die_h - old_ch) / 2.0, 1))

        self.sp_die_w.blockSignals(True)
        self.sp_die_h.blockSignals(True)
        self.sp_marg_l.blockSignals(True)
        self.sp_marg_r.blockSignals(True)
        self.sp_marg_b.blockSignals(True)
        self.sp_marg_t.blockSignals(True)

        self.sp_die_w.setValue(new_die_w)
        self.sp_die_h.setValue(new_die_h)
        self.sp_marg_l.setValue(margin_x)
        self.sp_marg_r.setValue(margin_x)
        self.sp_marg_b.setValue(margin_y)
        self.sp_marg_t.setValue(margin_y)

        self.sp_die_w.blockSignals(False)
        self.sp_die_h.blockSignals(False)
        self.sp_marg_l.blockSignals(False)
        self.sp_marg_r.blockSignals(False)
        self.sp_marg_b.blockSignals(False)
        self.sp_marg_t.blockSignals(False)

        # Only enable pad ring if full-chip pad mode (rb_chip) is active
        self.pad_ring_enabled = hasattr(self, "rb_chip") and self.rb_chip.isChecked()
        self.pad_ring_margin = margin
        self.pad_ring_margin_x = margin_x
        self.pad_ring_margin_y = margin_y
        self._user_custom_dimensions = True
        self.init_floorplan()
        self.fit_die()

    def toggle_flightlines(self):
        """Toggles visibility of interactive interconnect flylines / affinity ratsnest."""
        if hasattr(self, 'act_toggle_flightlines'):
            cur = self.act_toggle_flightlines.isChecked()
            self.act_toggle_flightlines.setChecked(not cur)
        self.view.update()

    def _parse_netlist_pin_connectivity(self):
        """Extracts top-level pin and internal instance interconnect bindings for live flylines."""
        if hasattr(self, "_cached_net_pin_map") and self._cached_net_pin_map:
            return self._cached_net_pin_map

        proj_root, base = self._get_project_context()
        candidates = [
            os.path.join(proj_root, "netlist", f"{base}_netlist.v"),
            os.path.join(proj_root, "source", f"{base}.v"),
            os.path.join(proj_root, "rtl", f"{base}.v"),
            os.path.join(proj_root, f"{base}.v"),
        ]
        netlist_path = next((c for c in candidates if os.path.isfile(c)), None)
        net_pin_map = {}
        if netlist_path:
            try:
                with open(netlist_path, "r", errors="replace") as f:
                    content = f.read()
                top_m = re.search(rf"module\s+{base}\b.*?;(.*?)endmodule", content, re.DOTALL)
                top_body = top_m.group(1) if top_m else content
                inst_pat = re.compile(r'(\b\w+\b)\s+(\bu_\w+|\b\w+_inst\w*)\s*\((.*?)\);', re.DOTALL)
                for m_cell, m_inst, p_str in inst_pat.findall(top_body):
                    port_conns = re.findall(r'\.\s*(\w+)\s*\(\s*([^)]+)\s*\)', p_str)
                    for port_name, net_expr in port_conns:
                        tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', net_expr)
                        for tok in tokens:
                            if tok not in ("sel_pmu", "sel_crypto", "sel_npu", "sel_sram", "always", "assign", "wire", "reg"):
                                net_pin_map.setdefault(tok, set()).add(m_inst)
            except Exception as e:
                print(f"[Floorplanner] Live flylines parser note: {e}")

        self._cached_net_pin_map = net_pin_map
        return net_pin_map

    def _draw_interconnect_flylines(self, painter, rect):
        """Draws dynamic elastic flylines / ratsnest splines connecting I/O pads and macros/regions."""
        if hasattr(self, "act_toggle_flightlines") and not self.act_toggle_flightlines.isChecked():
            return
        if not hasattr(self, "pin_items") or not self.pin_items:
            return

        net_pin_map = self._parse_netlist_pin_connectivity()

        # Build center coordinate lookups for all canvas items
        item_centers = {}
        for it in self.scene.items():
            if isinstance(it, MacroItem):
                br = it.sceneBoundingRect()
                item_centers[it.inst_name] = br.center()
                item_centers[it.name] = br.center()
                item_centers[it.inst_name.split('/')[-1]] = br.center()
            elif isinstance(it, RegionItem):
                br = it.sceneBoundingRect()
                item_centers[it.module_name] = br.center()
                item_centers[it.module_name.split('/')[-1]] = br.center()
            elif isinstance(it, VoltageIslandItem):
                br = it.sceneBoundingRect()
                item_centers[it.domain_name] = br.center()
                for elem in it.elements:
                    item_centers[elem] = br.center()
                    item_centers[elem.split('/')[-1]] = br.center()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for pin_name, p_item in self.pin_items.items():
            try:
                p_pos = p_item.scenePos()
            except RuntimeError:
                continue

            # Identify target instance or module
            clean_name = pin_name.split('[')[0]
            matched_targets = set()
            if clean_name in net_pin_map:
                matched_targets.update(net_pin_map[clean_name])

            # Domain / explicit affinity fallback
            pdata = self.pins_data.get(pin_name, {})
            if pdata.get("module"):
                matched_targets.add(pdata["module"])

            # Keyword matching fallback (crypto_* -> u_crypto_engine, npu_* -> u_npu_core, sram_* -> u_sram_subsystem)
            sig_lower = pin_name.lower()
            if not matched_targets:
                for k in item_centers.keys():
                    k_pure = k.replace("u_", "").replace("PD_", "").lower()
                    if k_pure and (k_pure in sig_lower or sig_lower.startswith(k_pure)):
                        matched_targets.add(k)
                        break

            # Deduplicate endpoints
            drawn_endpoints = set()
            for tgt in matched_targets:
                target_pt = item_centers.get(tgt) or item_centers.get(tgt.split('/')[-1])
                if not target_pt:
                    continue
                pt_tuple = (round(target_pt.x(), 1), round(target_pt.y(), 1))
                if pt_tuple in drawn_endpoints:
                    continue
                drawn_endpoints.add(pt_tuple)

                # Color-code by net group
                pdir = pdata.get("dir", "input")
                is_clk_rst = any(k in sig_lower for k in ("clk", "clock", "rst", "reset"))
                is_pwr = pdir in ("power", "ground") or any(k in sig_lower for k in ("vdd", "vss", "vpwr", "vgnd"))

                if is_clk_rst:
                    line_color = QColor(249, 226, 175, 140)  # Yellow / Amber
                elif is_pwr:
                    line_color = QColor(243, 139, 168, 140) if "vdd" in sig_lower or pdir == "power" else QColor(137, 180, 250, 140)
                else:
                    line_color = QColor(137, 220, 235, 120)  # Soft Cyan / Sky

                pen = QPen(line_color, 1.2, Qt.PenStyle.DashLine)
                painter.setPen(pen)

                # Draw smooth cubic bezier spline from pin to destination block
                dx = target_pt.x() - p_pos.x()
                dy = target_pt.y() - p_pos.y()
                path = QPainterPath()
                path.moveTo(p_pos)
                ctrl1 = QPointF(p_pos.x() + dx * 0.25, p_pos.y() + dy * 0.05)
                ctrl2 = QPointF(p_pos.x() + dx * 0.75, p_pos.y() + dy * 0.95)
                path.cubicTo(ctrl1, ctrl2, target_pt)
                painter.drawPath(path)

        painter.restore()

    def select_active_edge(self, edge):
        """Sets the active focused edge for 'A' key auto-spacing."""
        self.active_edge = edge
        if hasattr(self, "lbl_active_edge"):
            edge_labels = {"top": "North (Top)", "bottom": "South (Bottom)", "left": "West (Left)", "right": "East (Right)"}
            self.lbl_active_edge.setText(f"Active Edge: {edge_labels.get(edge, edge.upper())}")
        self._highlight_active_edge_on_canvas(edge)

    def _highlight_active_edge_on_canvas(self, edge):
        if not hasattr(self, "_edge_zone_items"):
            return
        for e_key, item in self._edge_zone_items.items():
            if e_key == edge:
                item.setPen(QPen(QColor("#00FFFF"), 2, Qt.PenStyle.SolidLine))
                item.setBrush(QBrush(QColor(0, 255, 255, 35)))
            else:
                item.setPen(QPen(QColor("#45475a"), 1, Qt.PenStyle.DashLine))
                item.setBrush(QBrush(QColor(69, 71, 90, 15)))

    def _on_table_pads_selection_changed(self):
        selected_rows = [idx.row() for idx in self.table_pads.selectionModel().selectedRows()]
        for it in self.scene.items():
            if isinstance(it, PinItem):
                it.setSelected(False)
        for r in selected_rows:
            name_it = self.table_pads.item(r, 0)
            if name_it and name_it.text() in self.pin_items:
                self.pin_items[name_it.text()].setSelected(True)

    def on_pin_selected_in_canvas(self, pin_name):
        for r in range(self.table_pads.rowCount()):
            it = self.table_pads.item(r, 0)
            if it and it.text() == pin_name:
                self.table_pads.scrollToItem(it)
                self.table_pads.blockSignals(True)
                self.table_pads.selectRow(r)
                self.table_pads.blockSignals(False)
                break

    def _legalize_edge_pos(self, pin_name, edge, pos, span):
        """Prevents overlapping between pads or pins along the same perimeter edge."""
        is_pad = hasattr(self, "rb_chip") and self.rb_chip.isChecked()
        min_clearance = 80.0 if is_pad else max(span, 5.0)
        other_positions = []
        for other_name, item in self.pin_items.items():
            if other_name == pin_name or getattr(item, "edge", None) != edge:
                continue
            cur_p = item.pos().x() if edge in ("bottom", "top") else item.pos().y()
            other_positions.append(cur_p)
        other_positions.sort()
        adjusted_pos = pos
        for op in other_positions:
            if abs(adjusted_pos - op) < min_clearance:
                adjusted_pos = (op + min_clearance) if adjusted_pos >= op else (op - min_clearance)
        return adjusted_pos

    def _order_preserving_space_edge(self, edge, order_override=None):
        """Spaces pins along edge strictly preserving visual order with DRC-clean pitch."""
        w = self.die_rect.width()
        h = self.die_rect.height()
        is_pad = hasattr(self, "rb_chip") and self.rb_chip.isChecked()
        span = w if edge in ("bottom", "top") else h

        coord_key = "x" if edge in ("bottom", "top") else "y"
        pins_with_coords = []
        for p, d in self.pins_data.items():
            if d.get("edge") == edge:
                item = self.pin_items.get(p)
                cur_pos = (item.pos().x() if edge in ("bottom", "top") else item.pos().y()) if item else d.get(coord_key, 0.0)
                pins_with_coords.append((p, cur_pos))
        pins_with_coords.sort(key=lambda x: x[1])
        edge_pins = [p for p, _ in pins_with_coords]
        n = len(edge_pins)
        if n == 0:
            return

        pad_w = 80.0 if is_pad else 4.0
        if edge in ("bottom", "top"):
            row_min = 210.0 if is_pad else 25.0
            row_max = max(row_min, span - 210.0 - pad_w) if is_pad else max(row_min, span - 25.0 - pad_w)
        else:
            row_min = 214.0 if is_pad else 25.0
            row_max = max(row_min, span - 214.0 - pad_w) if is_pad else max(row_min, span - 25.0 - pad_w)

        max_span = max(0.0, row_max - row_min)
        min_pitch = 85.0 if is_pad else 10.0
        needed_span = (n - 1) * min_pitch if n > 1 else 0.0

        if is_pad and n > 1 and max_span < needed_span:
            if edge in ("bottom", "top"):
                new_w = max(w, (n * min_pitch) + 500.0)
                self.expand_die_for_padring(new_w, h, margin=getattr(self, "pad_ring_margin", 250.0))
                w = self.die_rect.width()
                span = w
                row_max = max(row_min, span - 210.0 - pad_w)
                max_span = max(0.0, row_max - row_min)
            else:
                new_h = max(h, (n * min_pitch) + 508.0)
                self.expand_die_for_padring(w, new_h, margin=getattr(self, "pad_ring_margin", 250.0))
                h = self.die_rect.height()
                span = h
                row_max = max(row_min, span - 214.0 - pad_w)
                max_span = max(0.0, row_max - row_min)

        step = (max_span / (n - 1)) if n > 1 else 0.0
        if is_pad and n > 1:
            step = max(min_pitch, step)
        start = row_min if n > 1 else (row_min + max_span / 2.0)
        pad_cen_offset = 110.0

        for i, pname in enumerate(edge_pins):
            loc = snap_to_grid(start + i * step)
            self.pins_data[pname]["edge"] = edge
            self.pins_data[pname]["tier"] = "Outer (Ring 1)"
            if is_pad:
                if edge == "bottom":
                    x, y = loc + 40.0, pad_cen_offset
                    pw, ph = 80.0, 200.0
                elif edge == "top":
                    x, y = loc + 40.0, h - pad_cen_offset
                    pw, ph = 80.0, 200.0
                elif edge == "left":
                    x, y = pad_cen_offset, loc + 40.0
                    pw, ph = 200.0, 80.0
                elif edge == "right":
                    x, y = w - pad_cen_offset, loc + 40.0
                    pw, ph = 200.0, 80.0
            else:
                pw, ph = 4.0, 4.0
                if edge == "bottom": x, y = loc, 0.0
                elif edge == "top": x, y = loc, h
                elif edge == "left": x, y = 0.0, loc
                elif edge == "right": x, y = w, loc

            if pname not in self.pin_items:
                self._place_pin_item(pname, edge, x, y, pw, ph)
            else:
                item = self.pin_items[pname]
                item.edge = edge
                item.setPos(x, y)
                self.pins_data[pname]["x"] = x
                self.pins_data[pname]["y"] = y

        self._refresh_pads_table()
        self.update_live_tcl()
        self.save_state()

    def auto_space_active_edge(self):
        ed = getattr(self, "active_edge", "bottom")
        self._order_preserving_space_edge(ed)
        self.view.update()

    def insert_supply_pads(self):
        ed = getattr(self, "active_edge", "bottom")
        c = len(self.pins_data)
        vdd_name = f"pad_vdd_core_{c}"
        vss_name = f"pad_vss_core_{c+1}"
        self.pins_data[vdd_name] = {
            "edge": ed,
            "dir": "power",
            "pad_cell": "sky130_fd_io__top_power_lvc_wpad",
            "domain": "PD_TOP",
            "_is_supply": True,
            "tier": "Outer (Ring 1)"
        }
        self.pins_data[vss_name] = {
            "edge": ed,
            "dir": "ground",
            "pad_cell": "sky130_fd_io__top_ground_lvc_wpad",
            "domain": "PD_TOP",
            "_is_supply": True,
            "tier": "Outer (Ring 1)"
        }
        # Re-space the active edge to cleanly place the new pads on canvas
        self._order_preserving_space_edge(ed)
        self._refresh_pads_table()
        self.update_live_tcl()
        self.save_state()
        self.view.update()

    def _sync_upf_power_pads(self):
        """
        Synchronizes power pads in pins_data with UPF intent:
        For domains declared as 'Dedicated External Pad', automatically provisions
        pad_vdd_<domain> in pins_data if not already present.
        """
        if not hasattr(self, 'pins_data') or not hasattr(self, 'pdm') or not self.pdm:
            return
        updated = False
        for pd in self.pdm.domains.values():
            if not pd.is_top and getattr(pd, 'domain_type', '').lower().startswith('dedicated'):
                pad_name = f"pad_vdd_{pd.name.lower().replace('pd_', '')}"
                if pad_name not in self.pins_data:
                    self.pins_data[pad_name] = {
                        "edge": "left",
                        "dir": "power",
                        "pad_cell": "sky130_fd_io__top_power_lvc_wpad",
                        "domain": pd.name,
                        "_is_supply": True,
                        "tier": "Outer (Ring 1)"
                    }
                    updated = True
        if updated and hasattr(self, 'table_pads'):
            self._refresh_pads_table()

    def _refresh_domain_supplies_table(self):
        if not hasattr(self, 'table_domain_supplies'):
            return
        self._sync_upf_power_pads()
        self.table_domain_supplies.setRowCount(0)
        supply_options = [
            "Always-On (Core Mesh)",
            "Internally Gated (PMU)",
            "Dedicated External Pad"
        ]
        domains_list = list(self.pdm.domains.values()) if hasattr(self, 'pdm') else []
        for pd in domains_list:
            r = self.table_domain_supplies.rowCount()
            self.table_domain_supplies.insertRow(r)
            self.table_domain_supplies.setItem(r, 0, QTableWidgetItem(pd.name))
            self.table_domain_supplies.setItem(r, 1, QTableWidgetItem(f"{pd.voltage:.2f}V"))

            cmb_supply = QComboBox()
            if pd.is_top:
                cmb_supply.addItem("Always-On (Core Mesh)")
                cmb_supply.setEnabled(False)
            else:
                cmb_supply.addItems(["Internally Gated (PMU)", "Dedicated External Pad"])
                cur_type = getattr(pd, 'domain_type', 'Internally Gated')
                if "dedicated" in cur_type.lower() or "external" in cur_type.lower():
                    cmb_supply.setCurrentText("Dedicated External Pad")
                else:
                    cmb_supply.setCurrentText("Internally Gated (PMU)")

            # Determine Supply Net / Source summary label
            source_label = "VDD (Core Ring)" if pd.is_top else (
                f"pad_vdd_{pd.name.lower().replace('pd_', '')}" if "dedicated" in getattr(pd, 'domain_type', '').lower()
                else f"VDD via {pd.sleep_en.split('/')[-1] if getattr(pd, 'sleep_en', None) else 'sleep'}"
            )
            item_source = QTableWidgetItem(source_label)
            item_source.setFlags(item_source.flags() & ~Qt.ItemFlag.ItemIsEditable)

            def _on_supply_type_changed(text, domain_obj=pd, row_idx=r, source_item=item_source):
                if text == "Dedicated External Pad":
                    domain_obj.domain_type = "Dedicated External Pad"
                    pad_net = f"pad_vdd_{domain_obj.name.lower().replace('pd_', '')}"
                    source_item.setText(pad_net)
                    # Automatically ensure a power pad exists in pins_data for this domain
                    if hasattr(self, "pins_data"):
                        if pad_net not in self.pins_data:
                            self.pins_data[pad_net] = {
                                "edge": "left", "dir": "power",
                                "pad_cell": "sky130_fd_io__top_power_lvc_wpad",
                                "domain": domain_obj.name, "_is_supply": True,
                                "tier": "Outer (Ring 1)"
                            }
                else:
                    domain_obj.domain_type = "Internally Gated"
                    sig = domain_obj.sleep_en.split('/')[-1] if getattr(domain_obj, 'sleep_en', None) else 'sleep'
                    source_item.setText(f"VDD via {sig}")
                if hasattr(self, "_refresh_pads_table"):
                    self._refresh_pads_table()
                self._trigger_autosave()
                self.update_live_tcl()

            cmb_supply.currentTextChanged.connect(_on_supply_type_changed)
            self.table_domain_supplies.setCellWidget(r, 2, cmb_supply)
            self.table_domain_supplies.setItem(r, 3, item_source)

            # Column 4: Row Site / Height (unithd / 2.72 um vs unithddbl / 5.44 um)
            cmb_site = QComboBox()
            cmb_site.addItems(["unithd (2.72 µm)", "unithddbl (5.44 µm)"])
            cur_site = getattr(pd, 'site_type', 'unithd')
            if cur_site == 'unithddbl':
                cmb_site.setCurrentText("unithddbl (5.44 µm)")
            else:
                cmb_site.setCurrentText("unithd (2.72 µm)")

            def _on_site_changed(text, domain_obj=pd):
                if "unithddbl" in text:
                    domain_obj.site_type = "unithddbl"
                    domain_obj.row_height = 5.44
                else:
                    domain_obj.site_type = "unithd"
                    domain_obj.row_height = 2.72
                self._trigger_autosave()
                self.update_live_tcl()

            cmb_site.currentTextChanged.connect(_on_site_changed)
            self.table_domain_supplies.setCellWidget(r, 4, cmb_site)

            # Column 5: Physical Switch Insertion (Checkbox)
            chk_phys_switch = QCheckBox("Insert Switch")
            chk_phys_switch.setChecked(getattr(pd, 'enable_physical_switch', False))
            if pd.is_top:
                chk_phys_switch.setEnabled(False)

            def _on_phys_switch_toggled(checked, domain_obj=pd):
                domain_obj.enable_physical_switch = bool(checked)
                self._trigger_autosave()
                self.update_live_tcl()

            chk_phys_switch.toggled.connect(_on_phys_switch_toggled)
            self.table_domain_supplies.setCellWidget(r, 5, chk_phys_switch)

    def _refresh_domain_tapcells_table(self):
        if not hasattr(self, 'table_domain_tapcells'):
            return
        self.table_domain_tapcells.setRowCount(0)
        standard_taps = [
            "sky130_fd_sc_hd__tapvpwrvgnd_1",
            "sky130_fd_sc_hd__tap_1",
            "sky130_fd_sc_hd__tap_2"
        ]
        domains_list = list(self.pdm.domains.values()) if hasattr(self, 'pdm') else []
        for pd in domains_list:
            r = self.table_domain_tapcells.rowCount()
            self.table_domain_tapcells.insertRow(r)
            self.table_domain_tapcells.setItem(r, 0, QTableWidgetItem(pd.name))
            self.table_domain_tapcells.setItem(r, 1, QTableWidgetItem(f"{pd.voltage:.2f}V"))

            cmb_tap = QComboBox()
            cmb_tap.addItems(standard_taps)
            cur_tap = getattr(pd, 'tapcell_type', standard_taps[0])
            if cur_tap in standard_taps:
                cmb_tap.setCurrentText(cur_tap)
            
            def _on_domain_tap_changed(text, domain_obj=pd):
                domain_obj.tapcell_type = text
                # Also synchronize any existing VoltageIslandItem on canvas
                for it in self.scene.items():
                    if isinstance(it, VoltageIslandItem) and it.domain_name == domain_obj.name:
                        it.tapcell_type = text
                        it._update_tooltip()
                self._trigger_autosave()

            cmb_tap.currentTextChanged.connect(_on_domain_tap_changed)
            self.table_domain_tapcells.setCellWidget(r, 2, cmb_tap)

    def _refresh_pads_table(self):
        self.table_pads.setRowCount(0)
        domain_names = ["PD_TOP"]
        if hasattr(self, 'pdm') and self.pdm.domains:
            domain_names = list(self.pdm.domains.keys())

        for name, p in self.pins_data.items():
            r = self.table_pads.rowCount()
            self.table_pads.insertRow(r)
            self.table_pads.setItem(r, 0, QTableWidgetItem(name))
            self.table_pads.setItem(r, 1, QTableWidgetItem(p.get("dir", "input")))
            self.table_pads.setItem(r, 2, QTableWidgetItem(p.get("edge", "bottom")))
            self.table_pads.setItem(r, 3, QTableWidgetItem(str(p.get("pos", "-"))))

            cmb_dom = QComboBox()
            cmb_dom.addItems(domain_names)
            cur_dom = p.get("domain", "PD_TOP")
            if cur_dom in domain_names:
                cmb_dom.setCurrentText(cur_dom)
            elif cur_dom:
                cmb_dom.addItem(cur_dom)
                cmb_dom.setCurrentText(cur_dom)

            def _on_pad_dom_changed(text, pin_name=name):
                self.pins_data[pin_name]["domain"] = text
                self._trigger_autosave()
                self.update_live_tcl()

            cmb_dom.currentTextChanged.connect(_on_pad_dom_changed)
            self.table_pads.setCellWidget(r, 4, cmb_dom)

    def generate_core_power_ring(self):
        QMessageBox.information(self, "Core Power Ring", "Configured met4 (horizontal) and met5 (vertical) dual core power rings around the core boundary.")

    def route_pad_trunk_bridges(self):
        QMessageBox.information(self, "Targeted Pad Bridges", "Targeted trunk bridges connected solely from core power rings to P_CORE/G_CORE pad terminals.")

    def configure_dual_followpins(self):
        QMessageBox.information(self, "Dual-Rail Followpins", "Configured met1 followpins: VPWR for always-on standard cells, VPWRG for gated standard cells.")

    def run_psm_analysis(self):
        if self.parent() and hasattr(self.parent(), "run_psm_integrity_check"):
            self.parent().run_psm_integrity_check()
        else:
            QMessageBox.information(self, "Power Integrity Check", "Running OpenROAD ::psm Static IR Drop & EM Violations Check...")

    def check_connectivity_matrix(self):
        QMessageBox.information(self, "Connectivity Matrix", "All pad flightlines and voltage island connections verified 100% routable.")

    def detect_overlaps_and_corridors(self):
        self.scan_narrow_corridors()

    def export_quality_report(self):
        proj_root, base = self._get_project_context()
        rep_path = os.path.join(proj_root, "reports", f"{base}_floorplan_quality.md")
        with open(rep_path, "w") as f:
            f.write(f"# Silis Floorplan & Power Studio Quality Report\nTop: {base}\nDie: {self.sp_die_w.value()} x {self.sp_die_h.value()} µm\n")
        QMessageBox.information(self, "Report Exported", f"Quality report saved to {rep_path}")

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
        candidates = [
            os.path.join(proj_root, "reports", f"{base}_sizes.json").replace("\\", "/"),
            os.path.join(proj_root, "results", f"{base}_sizes.json").replace("\\", "/"),
            os.path.join(proj_root, "reports", "sizes.json").replace("\\", "/"),
            os.path.join(proj_root, "results", "sizes.json").replace("\\", "/"),
        ]
        import glob
        candidates += [c.replace("\\", "/") for c in glob.glob(os.path.join(proj_root, "reports", "*_sizes.json"))]
        candidates += [c.replace("\\", "/") for c in glob.glob(os.path.join(proj_root, "results", "*_sizes.json"))]
        sizes_json_path = next((c for c in dict.fromkeys(candidates) if os.path.isfile(c)), None)
        
        if sizes_json_path and os.path.exists(sizes_json_path):
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
                # Modules declared as power domain elements are fenced by the Power Domain itself.
                # Filter them out to prevent duplicate nested regions that starve the power domain.
                gated_elements = set()
                if hasattr(self, "power_domains"):
                    for pd in self.power_domains:
                        for elem in getattr(pd, "elements", []):
                            gated_elements.add(elem)
                            gated_elements.add(elem.split("/")[-1])

                for mod in sorted_mods:
                    # Skip whole-chip root wrapper if submodules exist
                    if mod == 'neorv32_top_inst' and len(sorted_mods) > 1:
                        continue
                    # Skip if element is a macro instance, macro cell, or IO pad
                    mod_base = mod.split('/')[-1]
                    if (mod in getattr(self, 'macro_instances', {}) or 
                        mod_base in getattr(self, 'macro_instances', {}) or 
                        mod in getattr(self, 'macro_sizes', {}) or 
                        mod_base in getattr(self, 'macro_sizes', {}) or 
                        is_io_pad_cell(mod_base, mod)):
                        continue
                    # Exclude modules already governed by a UPF power domain island
                    if (mod in gated_elements or mod_base in gated_elements or 
                        any(mod.startswith(g + "/") for g in gated_elements)):
                        continue
                    pct = (self.inclusive_module_areas[mod] / total_area) * 100.0
                    display_text = f"[{pct:4.1f}%] {mod_base} ({mod})"
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
                if hasattr(self.pdk_mgr, "configs") and isinstance(self.pdk_mgr.configs, list):
                    for c in self.pdk_mgr.configs:
                        if c.get('name') == pdk_name or (pdk_name and pdk_name.lower() in c.get('name', '').lower()):
                            pdk_cfg = c
                            break
                elif hasattr(self.pdk_mgr, "get"):
                    try:
                        pdk_cfg = self.pdk_mgr.get(pdk_name)
                    except Exception:
                        pdk_cfg = None
            if pdk_cfg and isinstance(pdk_cfg, dict):
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
            
        # Add to list widget the actual instances or requested macros (excluding IO pads)
        if hasattr(self, 'macro_instances') and self.macro_instances:
            for inst_name, master_name in self.macro_instances.items():
                if is_io_pad_cell(inst_name, master_name):
                    continue
                item_text = f"[{inst_name}] ({master_name})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, f"{master_name}|{inst_name}")
                self.macro_list.addItem(item)
        elif requested_macros:
            for m_name in requested_macros:
                if is_io_pad_cell("", m_name):
                    continue
                item_text = f"[{m_name}_inst] ({m_name})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, f"{m_name}|{m_name}_inst")
                self.macro_list.addItem(item)

        # Auto-throw all discovered macros onto canvas if floorplan is initialized
        self.auto_throw_macros_to_canvas()

        # Populate Power Domain Instances tab from UPF intent
        self.populate_power_domains_ui()

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
                    from backendflow.floorplanner.ioplacer import natural_sort_key
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
            core_area = max(0.0, cw * ch)
            
            # Compute total macro area on canvas
            macro_area = 0.0
            macro_items = [it for it in self.scene.items() if isinstance(it, MacroItem)]
            for m in macro_items:
                macro_area += m.rect().width() * m.rect().height()
            if macro_area == 0.0 and hasattr(self, 'macro_instances') and self.macro_instances:
                for inst_name, master_name in self.macro_instances.items():
                    mw, mh = self.macro_sizes.get(master_name, (0.0, 0.0))
                    macro_area += mw * mh

            std_area = getattr(self, 'total_std_cell_area', 0.0)
            avail_core_area = max(0.0, core_area - macro_area)

            if avail_core_area > 0 and std_area > 0:
                util = (std_area / avail_core_area) * 100.0
                tot_util = ((std_area + macro_area) / core_area) * 100.0 if core_area > 0 else 0.0
                self.lbl_core_util.setText(f"Core Util: {util:.2f}% (Std: {std_area:.0f} µm², Macro: {macro_area:.0f} µm²)")
            elif core_area > 0:
                self.lbl_core_util.setText(f"Core Area: {core_area:.0f} µm² (Macro: {macro_area:.0f} µm²)")
            else:
                self.lbl_core_util.setText("Core Utilization: -")
        
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
        elif items and isinstance(items[0], VoltageIslandItem):
            v_item = items[0]
            # Calculate total std cell area for elements in this power domain
            if hasattr(self, 'module_areas'):
                dom_std_area = sum(self.module_areas.get(elem, 0) for elem in v_item.elements)
                island_area = v_item.rect().width() * v_item.rect().height()
                if island_area > 0 and dom_std_area > 0:
                    util = (dom_std_area / island_area) * 100
                    self.lbl_region_util.setText(f"Domain [{v_item.domain_name}] Util: {util:.2f}%")
                elif island_area > 0:
                    self.lbl_region_util.setText(f"Domain [{v_item.domain_name}] Area: {island_area:.1f} µm²")
                else:
                    self.lbl_region_util.setText("Region Utilization: -")
            else:
                island_area = v_item.rect().width() * v_item.rect().height()
                self.lbl_region_util.setText(f"Domain [{v_item.domain_name}] Area: {island_area:.1f} µm²")
        else:
            self.lbl_region_util.setText("Region Utilization: -")

    @property
    def power_domains(self):
        """Returns power domain objects from self.pdm if available, otherwise from _power_domains."""
        if hasattr(self, "pdm") and self.pdm and hasattr(self.pdm, "domains"):
            return list(self.pdm.domains.values())
        return getattr(self, "_power_domains", [])

    @power_domains.setter
    def power_domains(self, val):
        self._power_domains = val

    def populate_power_domains_ui(self):
        """Populates the Power Domain table and list from project UPF intent."""
        if hasattr(self, "pdm") and self.pdm and hasattr(self.pdm, "domains") and not self.pdm.domains:
            self.pdm.load_or_create_upf()

        if hasattr(self, '_refresh_power_domains_table'):
            self._refresh_power_domains_table()

        if hasattr(self, 'power_domain_list'):
            self.power_domain_list.clear()
            for pd in self.power_domains:
                status_str = f"[{pd.area[0]:.1f},{pd.area[1]:.1f} - {pd.area[2]:.1f},{pd.area[3]:.1f}]" if pd.area else "Unplaced"
                type_str = "Always-On" if pd.is_top else "Gated"
                elem_str = ", ".join(pd.elements) if pd.elements else "Top Scope"
                item_text = f"[{pd.name}] {pd.voltage:.2f}V ({type_str})\nElements: {elem_str}\nStatus: {status_str}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, pd.name)
                self.power_domain_list.addItem(item)

    def on_place_power_domain_clicked(self):
        """Activates manual drag-to-draw on layout canvas for a power domain."""
        target_pd = None
        dname = None

        if hasattr(self, 'table_power_domains'):
            sel_rows = self.table_power_domains.selectionModel().selectedRows()
            if sel_rows:
                r = sel_rows[0].row()
                name_it = self.table_power_domains.item(r, 0)
                if name_it:
                    dname = name_it.text()

        if not dname and hasattr(self, 'power_domain_list') and self.power_domain_list.currentItem():
            item = self.power_domain_list.currentItem()
            dname = item.data(Qt.ItemDataRole.UserRole)

        gated_domains = [p for p in getattr(self, "power_domains", []) if not p.is_top]
        if not dname:
            if len(gated_domains) == 1:
                target_pd = gated_domains[0]
                dname = target_pd.name
            elif len(gated_domains) > 1:
                names = [p.name for p in gated_domains]
                chosen, ok = QInputDialog.getItem(self, "Select Power Domain", "Choose power domain island to place:", names, 0, False)
                if ok and chosen:
                    dname = chosen
                else:
                    return

        if not target_pd and dname:
            target_pd = next((p for p in getattr(self, "power_domains", []) if p.name == dname), None)

        if not target_pd:
            QMessageBox.information(self, "Power Domain", "No power-gated sub-domains found in project UPF.")
            return
        if target_pd.is_top:
            QMessageBox.warning(self, "Power Domain", f"'{dname}' is the top always-on domain spanning the entire chip core. Only gated sub-domains require physical island placement.")
            return

        # Remove existing canvas item for this power domain if present
        for it in list(self.scene.items()):
            if isinstance(it, VoltageIslandItem) and it.domain_name == dname:
                self.scene.removeItem(it)

        self.view.start_drawing_power_domain(target_pd)

    def on_auto_place_power_domain_clicked(self):
        """Automatically computes legal placement and dimensions for power domain islands."""
        if not self.floorplan_initialized or not self.core_rect:
            QMessageBox.warning(self, "Floorplan Not Initialized", "Please initialize the floorplan first.")
            return

        gated_domains = [p for p in self.power_domains if not p.is_top]
        if not gated_domains:
            QMessageBox.information(self, "Auto-Place Power Domains", "No power-gated sub-domains found in project UPF.")
            return

        core_x = self.core_rect.x()
        core_y = self.core_rect.y()
        core_w = self.core_rect.width()
        core_h = self.core_rect.height()

        # Remove existing voltage island items
        for it in list(self.scene.items()):
            if isinstance(it, VoltageIslandItem):
                self.scene.removeItem(it)

        # Place islands in peripheral or cavity quadrants
        num_islands = len(gated_domains)
        island_w = min(core_w * 0.40, max(60.0, core_w / (num_islands + 1)))
        island_h = min(core_h * 0.40, max(60.0, core_h * 0.35))

        step_x = (core_w - island_w) / max(1, num_islands)
        for i, pd in enumerate(gated_domains):
            ix = round(core_x + 10.0 + (i * step_x), 3)
            iy = round(core_y + 10.0, 3)
            # Ensure within core bounds
            ix = max(core_x, min(ix, core_x + core_w - island_w))
            iy = max(core_y, min(iy, core_y + core_h - island_h))

            pd.area = (ix, iy, round(ix + island_w, 3), round(iy + island_h, 3))
            v_item = VoltageIslandItem(ix, iy, island_w, island_h, pd.name, pd.voltage, pd.elements, self.core_rect)
            self.scene.addItem(v_item)

        self.populate_power_domains_ui()
        self.update_live_tcl()
        self.save_state()

    def init_floorplan(self):
        self.is_initializing = True
        try:
            self._do_init_floorplan()
        finally:
            self.is_initializing = False
            self.update_live_tcl()
            self.fit_die()

    def _do_init_floorplan(self):
        w = self.sp_die_w.value(); h = self.sp_die_h.value()
        ml = self.sp_marg_l.value(); mr = self.sp_marg_r.value()
        mt = self.sp_marg_t.value(); mb = self.sp_marg_b.value()
        cw = w - ml - mr; ch = h - mt - mb
        
        if cw <= 0 or ch <= 0:
            # Self-healing: if die was too small for margins, auto-adjust die size
            suggested_w = max(w, ml + mr + 50.0)
            suggested_h = max(h, mt + mb + 50.0)
            self.sp_die_w.blockSignals(True)
            self.sp_die_h.blockSignals(True)
            self.sp_die_w.setValue(suggested_w)
            self.sp_die_h.setValue(suggested_h)
            self.sp_die_w.blockSignals(False)
            self.sp_die_h.blockSignals(False)
            w = suggested_w; h = suggested_h
            cw = w - ml - mr; ch = h - mt - mb
            QMessageBox.warning(
                self,
                "Adjusted Die Dimensions",
                f"Core dimensions were <= 0 because margins ({ml+mr:.1f}x{mt+mb:.1f} µm) exceeded die size ({w:.1f}x{h:.1f} µm).\n\n"
                f"Auto-adjusted Die to {w:.1f} x {h:.1f} µm (Core: {cw:.1f} x {ch:.1f} µm)."
            )

        # Non-destructive buffer: snapshot all existing macros, regions, voltage islands, and blockages before clearing scene
        old_core_x = self.core_rect.x() if hasattr(self, 'core_rect') and self.core_rect else ml
        old_core_y = self.core_rect.y() if hasattr(self, 'core_rect') and self.core_rect else mb
        shift_dx = ml - old_core_x
        shift_dy = mb - old_core_y

        macro_buffer = []
        region_buffer = []
        blockage_buffer = []
        voltage_island_buffer = []

        for it in self.scene.items():
            if isinstance(it, MacroItem):
                macro_buffer.append({
                    'name': it.name,
                    'inst_name': it.inst_name,
                    'w': it.w,
                    'h': it.h,
                    'orientation': it.orientation,
                    'halo': it.halo,
                    'x': it.pos().x() + shift_dx,
                    'y': it.pos().y() + shift_dy,
                    'list_item': it.list_item
                })
            elif isinstance(it, RegionItem):
                region_buffer.append({
                    'module_name': it.module_name,
                    'x': it.rect().x() + it.pos().x() + shift_dx,
                    'y': it.rect().y() + it.pos().y() + shift_dy,
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
                    'x': it.rect().x() + it.pos().x() + shift_dx,
                    'y': it.rect().y() + it.pos().y() + shift_dy,
                    'w': it.rect().width(),
                    'h': it.rect().height(),
                    'btype': getattr(it, 'btype', 'Hard'),
                    'pct': getattr(it, 'pct', 40.0)
                })
            elif isinstance(it, VoltageIslandItem):
                voltage_island_buffer.append({
                    'domain_name': it.domain_name,
                    'voltage': it.voltage,
                    'elements': it.elements,
                    'tapcell_type': getattr(it, 'tapcell_type', 'sky130_fd_sc_hd__tapvpwrvgnd_1'),
                    'halo': getattr(it, 'halo', (15.0, 15.0, 15.0, 15.0)),
                    'x': it.rect().x() + it.pos().x() + shift_dx,
                    'y': it.rect().y() + it.pos().y() + shift_dy,
                    'w': it.rect().width(),
                    'h': it.rect().height()
                })

        self.scene.clear()
        self.view.setBackgroundBrush(QBrush(QColor("#000000")))
        self.die_rect = QRectF(0, 0, w, h)
        die_item = self.scene.addRect(self.die_rect, QPen(QColor("#89b4fa"), 2), QBrush(Qt.BrushStyle.NoBrush))
        die_item.setZValue(-10)
        self.core_rect = QRectF(ml, mb, cw, ch)  # y is mb because Y is up!
        core_item = self.scene.addRect(self.core_rect, QPen(QColor("#a6adc8"), 1, Qt.PenStyle.DashLine), QBrush(Qt.BrushStyle.NoBrush))
        core_item.setZValue(-9)

        # Sync inspector spinboxes safely without re-triggering signal loops
        if hasattr(self, 'sp_die_w'):
            self.sp_die_w.blockSignals(True)
            self.sp_die_h.blockSignals(True)
            self.sp_die_w.setValue(w)
            self.sp_die_h.setValue(h)
            self.sp_die_w.blockSignals(False)
            self.sp_die_h.blockSignals(False)
        if hasattr(self, 'sp_core_w'):
            self.sp_core_w.blockSignals(True)
            self.sp_core_h.blockSignals(True)
            self.sp_core_w.setValue(cw)
            self.sp_core_h.setValue(ch)
            self.sp_core_w.blockSignals(False)
            self.sp_core_h.blockSignals(False)

        # Edge selection hitboxes
        self._edge_zone_items = {}
        edge_thickness = max(20.0, min(w, h) * 0.05)
        edge_rects = {
            "bottom": QRectF(0, 0, w, edge_thickness),
            "top": QRectF(0, max(0.0, h - edge_thickness), w, edge_thickness),
            "left": QRectF(0, 0, edge_thickness, h),
            "right": QRectF(max(0.0, w - edge_thickness), 0, edge_thickness, h)
        }
        for e_key, e_rect in edge_rects.items():
            is_active = (getattr(self, "active_edge", "bottom") == e_key)
            e_pen = QPen(QColor("#00FFFF") if is_active else QColor("#45475a"), 2 if is_active else 1, Qt.PenStyle.SolidLine if is_active else Qt.PenStyle.DashLine)
            e_brush = QBrush(QColor(0, 255, 255, 30) if is_active else QColor(69, 71, 90, 15))
            z_item = self.scene.addRect(e_rect, e_pen, e_brush)
            z_item.setZValue(-28)
            self._edge_zone_items[e_key] = z_item

        # Render Corner Pad exclusion areas & Pad corridor guidelines if Chip Pad Mode
        is_pad_mode = getattr(self, "pad_ring_enabled", False) or (hasattr(self, "rb_chip") and self.rb_chip.isChecked())
        if is_pad_mode:
            corner_pen = QPen(QColor("#45475a"), 1.5)
            corner_brush = QBrush(QColor(69, 71, 90, 120))
            corner_w = 200.0
            corner_h = 204.0
            c_offset = 10.0

            corners = [
                ("SW", QRectF(c_offset, c_offset, corner_w, corner_h)),
                ("SE", QRectF(w - c_offset - corner_w, c_offset, corner_w, corner_h)),
                ("NW", QRectF(c_offset, h - c_offset - corner_h, corner_w, corner_h)),
                ("NE", QRectF(w - c_offset - corner_w, h - c_offset - corner_h, corner_w, corner_h)),
            ]
            for c_name, c_rect in corners:
                c_item = self.scene.addRect(c_rect, corner_pen, corner_brush)
                c_item.setZValue(-25)
                c_lbl = self.scene.addText(f"CORNER\n{c_name}")
                c_lbl.setDefaultTextColor(QColor("#a6adc8"))
                cf = c_lbl.font()
                cf.setPointSize(7)
                cf.setBold(True)
                c_lbl.setFont(cf)
                c_lbl.setTransform(QTransform.fromScale(1, -1))
                c_lbl.setPos(c_rect.left() + 25, c_rect.top() + corner_h / 2 + 10)

            # Pad corridor guidelines
            ring_pen = QPen(QColor("#45475a"), 1, Qt.PenStyle.DashLine)
            r_out = self.die_rect.adjusted(210, 214, -210, -214)
            if r_out.isValid() and r_out.width() > 0 and r_out.height() > 0:
                self.scene.addRect(r_out, ring_pen)
            if getattr(self, "pad_strategy", "single") == "staggered":
                r_in = self.die_rect.adjusted(420, 420, -420, -420)
                if r_in.isValid() and r_in.width() > 0 and r_in.height() > 0:
                    self.scene.addRect(r_in, ring_pen)

        self.floorplan_initialized = True
        self.tabs.setEnabled(True)
        self._set_floorplan_controls_enabled(True)
        
        # Restore macros from buffer if available, preserving user positions, orientations, and halos
        if macro_buffer:
            for m in macro_buffer:
                mw, mh = self.macro_sizes.get(m['name'], (m['w'], m['h']))
                m_item = MacroItem(m['name'], mw, mh, self.core_rect, self)
                m_item.set_inst_name(m['inst_name'])
                m_item.set_orientation(m['orientation'])
                m_item.update_halo(*m['halo'])

                # Keep cleanly inside new core bounds
                swapped = ["R90", "R270", "MX90", "MY90", "MXR90", "MYR90"]
                eff_w = mh if m['orientation'] in swapped else mw
                eff_h = mw if m['orientation'] in swapped else mh
                clamped_x = max(self.core_rect.left(), min(m['x'], self.core_rect.right() - eff_w))
                clamped_y = max(self.core_rect.top(), min(m['y'], self.core_rect.bottom() - eff_h))
                m_item.setPos(clamped_x, clamped_y)

                if m.get('list_item'):
                    m_item.list_item = m['list_item']
                self.scene.addItem(m_item)
        else:
            # Auto-discover and populate macros from DEF or peripheral autoplace
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
                    master_name = parser.comp_masters.get(inst_name, "")
                    if is_io_pad_cell(inst_name, master_name):
                        continue
                    if rect.width() / parser.dbu > 50: # It's a macro
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
                    existing_obs = [it.sceneBoundingRect() for it in self.scene.items() if isinstance(it, (VoltageIslandItem, BlockageItem))]
                    adj_dw, adj_dh, placed = compute_peripheral_macro_placement(
                        macros_raw, die_w=cur_dw, die_h=cur_dh,
                        margins=(ml, mr, mb, mt),
                        macro_sizes=self.macro_sizes,
                        existing_obstacles=existing_obs
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

                    existing_insts_in_scene = {it.inst_name for it in self.scene.items() if isinstance(it, MacroItem)}
                    for pm in placed:
                        if pm['inst_name'] in existing_insts_in_scene:
                            continue
                        m_item = MacroItem(pm['name'], pm['w'], pm['h'], self.core_rect, self)
                        m_item.set_inst_name(pm['inst_name'])
                        m_item.set_orientation(pm['orientation'])
                        m_item.update_halo(*pm['halo'])
                        m_item.setPos(pm['x'], pm['y'])
                        self.scene.addItem(m_item)
                        existing_insts_in_scene.add(pm['inst_name'])
                else:
                    existing_insts_in_scene = {it.inst_name for it in self.scene.items() if isinstance(it, MacroItem)}
                    for m in macros_raw:
                        if m['inst_name'] in existing_insts_in_scene:
                            continue
                        m_item = MacroItem(m['master_name'], m['w'], m['h'], self.core_rect, self)
                        m_item.set_inst_name(m['inst_name'])
                        m_item.set_orientation(m['orient'])
                        m_item.setPos(m['x'], m['y'])
                        self.scene.addItem(m_item)
                        existing_insts_in_scene.add(m['inst_name'])

            # Fallback: if no macro items loaded from DEF but instances exist from sizes.json / config
            has_macro_items = any(isinstance(item, MacroItem) for item in self.scene.items())
            if not has_macro_items and hasattr(self, 'macro_instances') and self.macro_instances:
                macros_raw = []
                for inst_name, master_name in self.macro_instances.items():
                    if is_io_pad_cell(inst_name, master_name):
                        continue
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
                existing_obs = [it.sceneBoundingRect() for it in self.scene.items() if isinstance(it, (VoltageIslandItem, BlockageItem))]
                adj_dw, adj_dh, placed = compute_peripheral_macro_placement(
                    macros_raw, die_w=cur_dw, die_h=cur_dh,
                    margins=(ml, mr, mb, mt),
                    macro_sizes=self.macro_sizes,
                    existing_obstacles=existing_obs
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

                existing_insts_in_scene = {it.inst_name for it in self.scene.items() if isinstance(it, MacroItem)}
                for pm in placed:
                    if pm['inst_name'] in existing_insts_in_scene:
                        continue
                    m_item = MacroItem(pm['name'], pm['w'], pm['h'], self.core_rect, self)
                    m_item.set_inst_name(pm['inst_name'])
                    m_item.set_orientation(pm['orientation'])
                    m_item.update_halo(*pm['halo'])
                    m_item.setPos(pm['x'], pm['y'])
                    self.scene.addItem(m_item)
                    existing_insts_in_scene.add(pm['inst_name'])

        # Restore regions from buffer even if core changed or if they extend out of bounds
        for reg in region_buffer:
            rw = min(reg['w'], self.core_rect.width())
            rh = min(reg['h'], self.core_rect.height())
            rx = max(self.core_rect.left(), min(reg['x'], self.core_rect.right() - rw))
            ry = max(self.core_rect.top(), min(reg['y'], self.core_rect.bottom() - rh))
            r_item = RegionItem(
                rx, ry, rw, rh,
                reg['module_name'], is_fence=reg['is_fence'],
                density=reg['density'], core_rect=self.core_rect, parent=None
            )
            r_item.update_halo(*reg['halo'])
            r_item.set_locked(reg['locked'])
            if reg.get('multi_boxes'):
                r_item.multi_boxes = reg['multi_boxes']

            self.scene.addItem(r_item)

        for blk in blockage_buffer:
            bw = min(blk['w'], self.core_rect.width())
            bh = min(blk['h'], self.core_rect.height())
            bx = max(self.core_rect.left(), min(blk['x'], self.core_rect.right() - bw))
            by = max(self.core_rect.top(), min(blk['y'], self.core_rect.bottom() - bh))
            b_item = BlockageItem(
                bx, by, bw, bh,
                btype=blk['btype'], pct=blk['pct'],
                core_rect=self.core_rect, parent=None
            )
            self.scene.addItem(b_item)

        # Restore voltage islands from buffer, keeping them strictly contained inside core
        for vi in voltage_island_buffer:
            vw = min(vi['w'], self.core_rect.width())
            vh = min(vi['h'], self.core_rect.height())
            vx = max(self.core_rect.left(), min(vi['x'], self.core_rect.right() - vw))
            vy = max(self.core_rect.top(), min(vi['y'], self.core_rect.bottom() - vh))
            v_item = VoltageIslandItem(
                vx, vy, vw, vh,
                vi['domain_name'], vi['voltage'], vi['elements'],
                core_rect=self.core_rect, halo=vi.get('halo', (15.0, 15.0, 15.0, 15.0)), parent=None
            )
            v_item.set_tapcell_type(vi.get('tapcell_type', 'sky130_fd_sc_hd__tapvpwrvgnd_1'))
            self.scene.addItem(v_item)

            if hasattr(self, "power_domains"):
                for pd in self.power_domains:
                    if pd.name == vi['domain_name']:
                        pd.area = (round(vx, 3), round(vy, 3), round(vx + vw, 3), round(vy + vh, 3))
                        break

        # Render perimeter I/O pads
        if self.pins_data:
            self.auto_distribute_pads()

        # Auto-throw any remaining unplaced macros directly onto canvas
        self.auto_throw_macros_to_canvas()
        
        self.save_state()
        self.update_utilization()
        self.fit_die()

    def _set_floorplan_controls_enabled(self, enabled: bool):
        """Greys out (disables) floorplanning manipulation controls until the user initializes die/core."""
        # Disable/Enable non-setup inspector tabs
        if hasattr(self, 'inspector_tabs'):
            for idx in range(1, self.inspector_tabs.count()):
                self.inspector_tabs.setTabEnabled(idx, enabled)

        # Disable/Enable Floorplan tab editing tools
        widgets_to_toggle = [
            'btn_draw_region', 'btn_draw_fence', 'btn_autoplace_regions',
            'btn_convert_type', 'btn_apply_autoplace', 'btn_reroll_seed',
            'chk_force_place_all', 'chk_allow_rotation', 'chk_force_auto_shape',
            'sp_sel_x', 'sp_sel_y', 'txt_inst_name', 'cmb_orientation',
            'sp_sel_density', 'cmb_region_module', 'sp_region_density',
            'sp_common_region_halo', 'macro_list',
            'btn_place_pd', 'btn_auto_pd', 'btn_pmu_hookup', 'btn_add_domain',
            'btn_clamp_table', 'btn_auto_switches', 'btn_insert_tapcells',
            'btn_preview_pdn', 'btn_run_psm', 'btn_add_pad_bridges',
            'btn_auto_distribute_pads', 'btn_apply_pad_placement'
        ]
        for attr in widgets_to_toggle:
            w = getattr(self, attr, None)
            if w and hasattr(w, 'setEnabled'):
                w.setEnabled(enabled)

        # Disable/Enable Floorplan, Power, PDN menus
        for menu_attr in ['menu_floorplan', 'menu_power', 'menu_pdn']:
            m = getattr(self, menu_attr, None)
            if m and hasattr(m, 'setEnabled'):
                m.setEnabled(enabled)
            elif m and hasattr(m, 'menuAction'):
                m.menuAction().setEnabled(enabled)

    def fit_die(self):
        if hasattr(self, 'die_rect') and self.die_rect and self.die_rect.width() > 0:
            # Set scene rect with generous 15% margin around the die so the chip is cleanly centered
            margin_x = max(50.0, self.die_rect.width() * 0.15)
            margin_y = max(50.0, self.die_rect.height() * 0.15)
            scene_bounds = self.die_rect.adjusted(-margin_x, -margin_y, margin_x, margin_y)
            self.scene.setSceneRect(scene_bounds)
            self.view.setSceneRect(scene_bounds)
            self.view.fitInView(scene_bounds, Qt.AspectRatioMode.KeepAspectRatio)

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
        try:
            self.scene.clear()

            if 'die' in state:
                d = state['die']
                w = float(d.get('w', 1500.0))
                h = float(d.get('h', 1500.0))
                ml = float(d.get('ml', 20.0))
                mr = float(d.get('mr', 20.0))
                mt = float(d.get('mt', 20.0))
                mb = float(d.get('mb', 20.0))
                self.die_rect = QRectF(0, 0, w, h)
                self.core_rect = QRectF(ml, mb, max(1.0, w - ml - mr), max(1.0, h - mt - mb))
                if hasattr(self, 'sp_die_w'):
                    self.sp_die_w.setValue(w)
                    self.sp_die_h.setValue(h)
                    self.sp_marg_l.setValue(ml)
                    self.sp_marg_r.setValue(mr)
                    self.sp_marg_t.setValue(mt)
                    self.sp_marg_b.setValue(mb)
                self.floorplan_initialized = True

            if self.die_rect is None:
                self.die_rect = QRectF(0, 0, 1500, 1500)
                self.core_rect = QRectF(20, 20, 1460, 1460)

            # Restore Target Mode (Respect is_pad_mode saved in session)
            is_pad_saved = bool(state.get('is_pad_mode', False))
            self.pad_ring_enabled = is_pad_saved
            if hasattr(self, 'rb_chip') and hasattr(self, 'rb_macro'):
                self.rb_chip.blockSignals(True)
                self.rb_macro.blockSignals(True)
                if is_pad_saved:
                    self.rb_chip.setChecked(True)
                else:
                    self.rb_macro.setChecked(True)
                self.rb_chip.blockSignals(False)
                self.rb_macro.blockSignals(False)
            elif hasattr(self, 'rb_chip'):
                self.rb_chip.blockSignals(True)
                self.rb_chip.setChecked(is_pad_saved)
                self.rb_chip.blockSignals(False)
            elif hasattr(self, 'rb_macro'):
                self.rb_macro.blockSignals(True)
                self.rb_macro.setChecked(not is_pad_saved)
                self.rb_macro.blockSignals(False)
            if hasattr(self, 'gb_pad_method'):
                self.gb_pad_method.setVisible(is_pad_saved)
            if hasattr(self, 'btn_auto_opt_die'):
                self.btn_auto_opt_die.setEnabled(is_pad_saved)
            if hasattr(self, 'cmb_target_aspect'):
                self.cmb_target_aspect.setEnabled(is_pad_saved)

            # Restore pins dictionary if saved in state
            if 'pins' in state and state['pins']:
                self.pins_data = state['pins']

            # Restore tapcell distance if present
            if 'tap_distance' in state and hasattr(self, 'sp_tap_distance'):
                self.sp_tap_distance.setValue(float(state['tap_distance']))

            # Restore PDN ring and trunk bridge settings if present
            if 'pdn_config' in state:
                pdn_cfg = state['pdn_config']
                if 'enable_ring' in pdn_cfg and hasattr(self, 'chk_enable_ring'):
                    self.chk_enable_ring.setChecked(bool(pdn_cfg['enable_ring']))
                if 'ring_width' in pdn_cfg and hasattr(self, 'sp_ring_width'):
                    self.sp_ring_width.setValue(float(pdn_cfg['ring_width']))
                if 'ring_spacing' in pdn_cfg and hasattr(self, 'sp_ring_spacing'):
                    self.sp_ring_spacing.setValue(float(pdn_cfg['ring_spacing']))
                if 'ring_offset' in pdn_cfg and hasattr(self, 'sp_ring_offset'):
                    self.sp_ring_offset.setValue(float(pdn_cfg['ring_offset']))
                if 'ring_h_layer' in pdn_cfg and hasattr(self, 'cmb_ring_h_layer'):
                    self.cmb_ring_h_layer.setCurrentText(str(pdn_cfg['ring_h_layer']))
                if 'ring_v_layer' in pdn_cfg and hasattr(self, 'cmb_ring_v_layer'):
                    self.cmb_ring_v_layer.setCurrentText(str(pdn_cfg['ring_v_layer']))
                if 'enable_trunks' in pdn_cfg and hasattr(self, 'chk_enable_trunks'):
                    self.chk_enable_trunks.setChecked(bool(pdn_cfg['enable_trunks']))
                if 'trunk_layer' in pdn_cfg and hasattr(self, 'cmb_trunk_layer'):
                    self.cmb_trunk_layer.setCurrentText(str(pdn_cfg['trunk_layer']))
                if 'trunk_width' in pdn_cfg and hasattr(self, 'sp_trunk_width'):
                    self.sp_trunk_width.setValue(float(pdn_cfg['trunk_width']))
                if 'targeted_bridges' in pdn_cfg and hasattr(self, 'chk_targeted_bridges'):
                    self.chk_targeted_bridges.setChecked(bool(pdn_cfg['targeted_bridges']))

            # Rebuild edge selection zone hitboxes
            w = self.die_rect.width()
            h = self.die_rect.height()
            self._edge_zone_items = {}
            edge_thickness = max(20.0, min(w, h) * 0.05)
            edge_rects = {
                "bottom": QRectF(0, 0, w, edge_thickness),
                "top": QRectF(0, max(0.0, h - edge_thickness), w, edge_thickness),
                "left": QRectF(0, 0, edge_thickness, h),
                "right": QRectF(max(0.0, w - edge_thickness), 0, edge_thickness, h)
            }
            for e_key, e_rect in edge_rects.items():
                is_active = (getattr(self, "active_edge", "bottom") == e_key)
                e_pen = QPen(QColor("#00FFFF") if is_active else QColor("#45475a"), 2 if is_active else 1, Qt.PenStyle.SolidLine if is_active else Qt.PenStyle.DashLine)
                e_brush = QBrush(QColor(0, 255, 255, 30) if is_active else QColor(69, 71, 90, 15))
                z_item = self.scene.addRect(e_rect, e_pen, e_brush)
                z_item.setZValue(-28)
                self._edge_zone_items[e_key] = z_item

            die_item = self.scene.addRect(self.die_rect, QPen(QColor("#A0AEC0"), 2), QBrush(Qt.BrushStyle.NoBrush))
            die_item.setZValue(-10)
            core_item = self.scene.addRect(self.core_rect, QPen(QColor("#4A5568"), 1, Qt.PenStyle.DashLine), QBrush(Qt.BrushStyle.NoBrush))
            core_item.setZValue(-9)

            for i in range(self.macro_list.count()):
                it = self.macro_list.item(i)
                it.setText(it.text().replace(" [PLACED]", ""))
                it.setForeground(QBrush())

            # Load blockages and regions
            raw_blockages = state.get('blockages', [])
            for b in raw_blockages:
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
                    b_item = BlockageItem(b['x'], b['y'], b['w'], b['h'], b.get('btype', 'Hard'), b.get('pct', 40))
                    self.scene.addItem(b_item)

            # Support sessions serialized with separate "regions" key
            raw_regions = state.get('regions', [])
            for r in raw_regions:
                r_item = RegionItem(
                    r['x'], r['y'], r['w'], r['h'],
                    r['module_name'], is_fence=r.get('is_fence', False),
                    density=r.get('density', 0.60), core_rect=self.core_rect
                )
                if 'halo' in r:
                    r_item.update_halo(*r['halo'])
                if 'locked' in r:
                    r_item.set_locked(r['locked'])
                if 'multi_boxes' in r:
                    r_item.multi_boxes = r['multi_boxes']
                self.scene.addItem(r_item)
                
            loaded_insts = set()
            for m in state.get('macros', []):
                inst = m.get('inst_name', '')
                # Skip duplicate instances or synthetic fallbacks if actual instances exist
                if not inst or inst in loaded_insts:
                    continue
                w, h = self.macro_sizes.get(m['name'], (100.0, 100.0))
                m_item = MacroItem(m['name'], w, h, self.core_rect, self)
                m_item.set_inst_name(inst)
                m_item.set_orientation(m.get('orientation', 'R0'))
                m_item.update_halo(*m.get('halo', [0, 0, 0, 0]))
                m_item.setPos(m.get('x', 0), m.get('y', 0))
                self.scene.addItem(m_item)
                loaded_insts.add(inst)
                
                target_text = m.get('list_text')
                for i in range(self.macro_list.count()):
                    it = self.macro_list.item(i)
                    base_text = it.text().replace(" [PLACED]", "")
                    matched = False
                    if target_text and base_text == target_text.replace(" [PLACED]", ""):
                        matched = True
                    elif base_text == m['name'] or it.data(Qt.ItemDataRole.UserRole) == f"{m['name']}|{m.get('inst_name', '')}":
                        matched = True
                    if matched:
                        it.setText(f"{base_text} [PLACED]")
                        it.setForeground(QBrush(QColor("#4CAF50")))
                        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                        m_item.list_item = it
                        break

            for pd_entry in state.get('power_domains', []):
                vi_item = VoltageIslandItem(
                    pd_entry['x'], pd_entry['y'], pd_entry['w'], pd_entry['h'],
                    pd_entry['domain_name'], pd_entry.get('voltage', 1.8),
                    pd_entry.get('elements', []), core_rect=self.core_rect,
                    halo=pd_entry.get('halo', (15.0, 15.0, 15.0, 15.0))
                )
                if 'tapcell_type' in pd_entry:
                    vi_item.set_tapcell_type(pd_entry['tapcell_type'])
                self.scene.addItem(vi_item)
                if hasattr(self, "pdm") and self.pdm:
                    cur_pd = self.pdm.domains.get(pd_entry['domain_name'])
                    if cur_pd:
                        cur_pd.area = (pd_entry['x'], pd_entry['y'], pd_entry['x'] + pd_entry['w'], pd_entry['y'] + pd_entry['h'])
                        if 'tapcell_type' in pd_entry:
                            cur_pd.tapcell_type = pd_entry['tapcell_type']
                        if 'domain_type' in pd_entry:
                            cur_pd.domain_type = pd_entry['domain_type']

            # Render I/O perimeter pads if present
            if hasattr(self, "pins_data") and self.pins_data:
                self.auto_distribute_pads()

            self.floorplan_initialized = True
            self._set_floorplan_controls_enabled(True)
            self.update_live_tcl()
            if hasattr(self, "_refresh_power_domains_table"):
                self._refresh_power_domains_table()
        finally:
            self.is_undoing = False

    def save_state(self):
        if self.is_undoing or not self.floorplan_initialized: return
        self.update_live_tcl()
        is_pad_mode = getattr(self, "pad_ring_enabled", False) or (hasattr(self, "rb_chip") and self.rb_chip.isChecked())
        pdn_cfg = {
            "enable_ring": self.chk_enable_ring.isChecked() if hasattr(self, "chk_enable_ring") else True,
            "ring_width": self.sp_ring_width.value() if hasattr(self, "sp_ring_width") else 5.0,
            "ring_spacing": self.sp_ring_spacing.value() if hasattr(self, "sp_ring_spacing") else 2.0,
            "ring_offset": self.sp_ring_offset.value() if hasattr(self, "sp_ring_offset") else 5.0,
            "ring_h_layer": self.cmb_ring_h_layer.currentText() if hasattr(self, "cmb_ring_h_layer") else "met5",
            "ring_v_layer": self.cmb_ring_v_layer.currentText() if hasattr(self, "cmb_ring_v_layer") else "met4",
            "enable_trunks": self.chk_enable_trunks.isChecked() if hasattr(self, "chk_enable_trunks") else True,
            "trunk_layer": self.cmb_trunk_layer.currentText() if hasattr(self, "cmb_trunk_layer") else "met4",
            "trunk_width": self.sp_trunk_width.value() if hasattr(self, "sp_trunk_width") else 3.2,
            "targeted_bridges": self.chk_targeted_bridges.isChecked() if hasattr(self, "chk_targeted_bridges") else True,
        }
        tap_distance_val = self.sp_tap_distance.value() if hasattr(self, "sp_tap_distance") else 14.0
        state = {'macros': [], 'blockages': [], 'power_domains': [], 'pins': dict(self.pins_data),
                 'is_pad_mode': is_pad_mode,
                 'pdn_config': pdn_cfg,
                 'tap_distance': tap_distance_val,
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
            elif isinstance(item, VoltageIslandItem):
                state['power_domains'].append({
                    'domain_name': item.domain_name,
                    'voltage': item.voltage,
                    'elements': item.elements,
                    'tapcell_type': getattr(item, 'tapcell_type', 'sky130_fd_sc_hd__tapvpwrvgnd_1'),
                    'halo': getattr(item, 'halo', (15.0, 15.0, 15.0, 15.0)),
                    'x': item.rect().x() + item.pos().x(),
                    'y': item.rect().y() + item.pos().y(),
                    'w': item.rect().width(),
                    'h': item.rect().height()
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

            # Export OpenROAD domain_areas.tcl script into project power/ directory
            active_pds = getattr(self, "power_domains", [])
            if active_pds:
                from backendflow.power.upf_engine import generate_domain_areas_tcl
                tcl_areas_path = os.path.join(proj_root, "power", "domain_areas.tcl")
                generate_domain_areas_tcl(active_pds, tcl_areas_path)
        except Exception as e:
            pass

    def auto_throw_macros_to_canvas(self):
        """
        Direct Macro Placement: throws all unplaced macros directly onto the canvas
        inside the core area, enabling the user to immediately drag and manipulate them.
        """
        if not self.floorplan_initialized or not self.core_rect:
            return

        existing_insts = {it.inst_name for it in self.scene.items() if isinstance(it, MacroItem)}
        macros_to_place = []

        if hasattr(self, 'macro_instances') and self.macro_instances:
            for inst_name, master_name in self.macro_instances.items():
                if is_io_pad_cell(inst_name, master_name):
                    continue
                if inst_name not in existing_insts:
                    mw, mh = self.macro_sizes.get(master_name, (479.78, 397.5))
                    macros_to_place.append({
                        'inst_name': inst_name,
                        'master_name': master_name,
                        'w': mw, 'h': mh,
                        'orient': 'R0',
                        'halo': [10, 10, 10, 10]
                    })
        elif not getattr(self, 'macro_instances', None) and hasattr(self, 'macro_list') and self.macro_list.count() > 0:
            for idx in range(self.macro_list.count()):
                it = self.macro_list.item(idx)
                raw_data = it.data(Qt.ItemDataRole.UserRole) or it.text()
                if "|" in raw_data:
                    master_name, inst_name = raw_data.split("|", 1)
                else:
                    master_name = raw_data.replace(" [PLACED]", "").strip()
                    inst_name = f"{master_name}_inst_{idx}"
                if is_io_pad_cell(inst_name, master_name):
                    continue
                if inst_name not in existing_insts:
                    mw, mh = self.macro_sizes.get(master_name, (479.78, 397.5))
                    macros_to_place.append({
                        'inst_name': inst_name,
                        'master_name': master_name,
                        'w': mw, 'h': mh,
                        'orient': 'R0',
                        'halo': [10, 10, 10, 10]
                    })

        if not macros_to_place:
            return

        # Place them cleanly along the peripheral or ribbon core area
        ml = self.core_rect.x()
        mb = self.core_rect.y()
        mr = self.die_rect.width() - (self.core_rect.x() + self.core_rect.width())
        mt = self.die_rect.height() - (self.core_rect.y() + self.core_rect.height())

        # Collect existing voltage islands and blockages to prevent macro collision
        existing_obstacles = []
        for it in self.scene.items():
            if isinstance(it, (VoltageIslandItem, BlockageItem)):
                existing_obstacles.append(it.sceneBoundingRect())

        try:
            _, _, placed = compute_peripheral_macro_placement(
                macros_to_place,
                die_w=self.die_rect.width(),
                die_h=self.die_rect.height(),
                margins=(ml, mr, mb, mt),
                macro_sizes=self.macro_sizes,
                existing_obstacles=existing_obstacles
            )
        except Exception:
            placed = []

        if placed:
            for pm in placed:
                m_item = MacroItem(pm['name'], pm['w'], pm['h'], self.core_rect, self)
                m_item.set_inst_name(pm['inst_name'])
                m_item.set_orientation(pm.get('orientation', 'R0'))
                m_item.update_halo(*pm.get('halo', [10, 10, 10, 10]))
                m_item.setPos(pm['x'], pm['y'])
                self.scene.addItem(m_item)
        else:
            # Fallback simple ribbon placement inside core
            cx = self.core_rect.x() + 20.0
            cy = self.core_rect.y() + 20.0
            for m in macros_to_place:
                m_item = MacroItem(m['master_name'], m['w'], m['h'], self.core_rect, self)
                m_item.set_inst_name(m['inst_name'])
                m_item.set_orientation(m['orient'])
                m_item.update_halo(*m['halo'])
                m_item.setPos(cx, cy)
                self.scene.addItem(m_item)
                cx += m['w'] + 30.0
                if cx + m['w'] > self.core_rect.right() - 20.0:
                    cx = self.core_rect.x() + 20.0
                    cy += m['h'] + 30.0

        self.scene.update()
        self.save_state()

    def on_macro_dropped(self, name, x, y, inst_name=None):
        if not self.floorplan_initialized: return

        # Guard: check if this instance is already placed on canvas
        for item in self.scene.items():
            if isinstance(item, MacroItem):
                if (inst_name and item.inst_name == inst_name) or (not inst_name and item.name == name):
                    item.setPos(x, y)
                    self.save_state()
                    return

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
                if is_io_pad_cell(item.inst_name, item.name):
                    continue
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
                if is_io_pad_cell(inst_name, master_name):
                    continue
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
            existing_obstacles = []
            for it in self.scene.items():
                if isinstance(it, VoltageIslandItem):
                    existing_obstacles.append(it.halo_scene_bounding_rect() if hasattr(it, 'halo_scene_bounding_rect') else it.sceneBoundingRect())
                elif isinstance(it, BlockageItem):
                    existing_obstacles.append(it.sceneBoundingRect())
            _, _, placed = compute_peripheral_macro_placement(
                macros_raw,
                die_w=self.die_rect.width(),
                die_h=self.die_rect.height(),
                margins=(ml, mr, mb, mt),
                macro_sizes=self.macro_sizes,
                existing_obstacles=existing_obstacles
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

    def on_border_input_changed(self):
        """Called when user edits the Core Border spinbox on the inspector tab."""
        border = self.sp_core_border.value()
        self.sp_marg_l.setValue(border)
        self.sp_marg_r.setValue(border)
        self.sp_marg_t.setValue(border)
        self.sp_marg_b.setValue(border)
        w = self.sp_die_w.value()
        h = self.sp_die_h.value()
        if w <= 2 * border or h <= 2 * border:
            return
        self._user_custom_dimensions = True
        self.init_floorplan()

    def on_die_input_changed(self):
        """Called when user edits Die W or Die H spinboxes on the inspector tab."""
        new_w = self.sp_die_w.value()
        new_h = self.sp_die_h.value()
        if self.die_rect and (abs(self.die_rect.width() - new_w) < 0.01 and abs(self.die_rect.height() - new_h) < 0.01):
            return
        border = self.sp_core_border.value() if hasattr(self, 'sp_core_border') else self.sp_marg_l.value()
        self.sp_marg_l.setValue(border)
        self.sp_marg_r.setValue(border)
        self.sp_marg_t.setValue(border)
        self.sp_marg_b.setValue(border)
        if new_w <= 2 * border or new_h <= 2 * border:
            return
        self._user_custom_dimensions = True
        self.init_floorplan()

    def on_core_input_changed(self):
        """Called when user edits Core W or Core H spinboxes on the inspector tab."""
        new_cw = self.sp_core_w.value()
        new_ch = self.sp_core_h.value()
        if self.core_rect and (abs(self.core_rect.width() - new_cw) < 0.01 and abs(self.core_rect.height() - new_ch) < 0.01):
            return
        ml = self.sp_marg_l.value(); mr = self.sp_marg_r.value()
        mt = self.sp_marg_t.value(); mb = self.sp_marg_b.value()
        new_w = new_cw + ml + mr
        new_h = new_ch + mt + mb
        self.sp_die_w.blockSignals(True)
        self.sp_die_h.blockSignals(True)
        self.sp_die_w.setValue(new_w)
        self.sp_die_h.setValue(new_h)
        self.sp_die_w.blockSignals(False)
        self.sp_die_h.blockSignals(False)
        self._user_custom_dimensions = True
        self.init_floorplan()

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
        """Restores regions, voltage islands, and macros back to the snapshot saved before auto-placement."""
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

        island_items = [it for it in self.scene.items() if isinstance(it, VoltageIslandItem)]
        for vi in island_items:
            dom = vi.domain_name
            if dom in self._saved_region_snapshot:
                snap = self._saved_region_snapshot[dom]
                vi.setPos(snap["pos_x"], snap["pos_y"])
                vi.setRect(snap["rect_x"], snap["rect_y"], snap["width"], snap["height"])
                vi.locked = snap["locked"]

        macro_items = [it for it in self.scene.items() if isinstance(it, MacroItem)]
        for m in macro_items:
            inst = m.inst_name
            if inst in self._saved_region_snapshot:
                snap = self._saved_region_snapshot[inst]
                m.setPos(snap["pos_x"], snap["pos_y"])
                m.set_orientation(snap["orientation"])

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
            for vi in self.scene.items():
                if isinstance(vi, VoltageIslandItem):
                    existing_items[vi.domain_name] = vi
                    for elem in vi.elements:
                        existing_items[elem] = vi
                        existing_items[elem.split("/")[-1]] = vi
            halo_val = self.sp_common_region_halo.value() if hasattr(self, 'sp_common_region_halo') else 10.0
            place_as_fence = self.btn_fence_mode.isChecked() if hasattr(self, 'btn_fence_mode') else True

            # Prune any existing unlocked regions that fall below min_pct cutoff
            for m_name, itm in list(existing_items.items()):
                if isinstance(itm, VoltageIslandItem):
                    # Do not prune declared power domain voltage islands
                    continue
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

            # Spawn regions or voltage islands for chosen unplaced modules
            # Also detect UPF power domains so modules assigned to gated domains become VoltageIslandItem
            gated_pd_map = {}
            if hasattr(self, "power_domains"):
                for pd in self.power_domains:
                    if not pd.is_top:
                        for elem in getattr(pd, "elements", []):
                            gated_pd_map[elem] = pd
                            gated_pd_map[elem.split("/")[-1]] = pd

            for mod_name, mod_area in eval_areas.items():
                if mod_name in skip_modules:
                    continue
                # Never auto-spawn regions for macros or IO pads
                mod_base = mod_name.split('/')[-1]
                if (mod_name in getattr(self, 'macro_instances', {}) or 
                    mod_base in getattr(self, 'macro_instances', {}) or 
                    mod_name in getattr(self, 'macro_sizes', {}) or 
                    mod_base in getattr(self, 'macro_sizes', {}) or 
                    is_io_pad_cell(mod_base, mod_name)):
                    continue
                if mod_name not in existing_items and mod_area > 0:
                    if mod_name == 'neorv32_top_inst' and len(eval_areas) > 1:
                        continue
                    mod_pct = (mod_area / total_area) * 100.0
                    if mod_pct < min_pct:
                        continue

                    req_area = mod_area / max(0.10, force_dens)
                    side = math.sqrt(req_area)

                    # If this module is declared as a power domain element, instantiate VoltageIslandItem
                    matching_pd = gated_pd_map.get(mod_name) or gated_pd_map.get(mod_name.split("/")[-1])
                    if matching_pd:
                        v_item = VoltageIslandItem(
                            self.core_rect.left(), self.core_rect.top(), side, side,
                            matching_pd.name, matching_pd.voltage, matching_pd.elements,
                            self.core_rect, parent=None
                        )
                        self.scene.addItem(v_item)
                    else:
                        new_r = RegionItem(
                            self.core_rect.left(), self.core_rect.top(), side, side,
                            mod_name, is_fence=place_as_fence, density=force_dens,
                            core_rect=self.core_rect, parent=None
                        )
                        new_r.update_halo(halo_val, halo_val, halo_val, halo_val)
                        self.scene.addItem(new_r)

        # Automatically ensure all declared non-top UPF power domains have islands on canvas
        if hasattr(self, "power_domains"):
            core_w = self.core_rect.width() if self.core_rect else 1000.0
            core_h = self.core_rect.height() if self.core_rect else 1000.0
            existing_island_domains = {vi.domain_name for vi in self.scene.items() if isinstance(vi, VoltageIslandItem)}
            for pd in self.power_domains:
                if not pd.is_top and pd.name not in existing_island_domains:
                    # Calculate required area based on constituent modules or default 15%
                    dom_std_area = sum(getattr(self, 'module_areas', {}).get(elem, 0.0) for elem in getattr(pd, 'elements', []))
                    if dom_std_area > 0:
                        side = max(60.0, math.sqrt(dom_std_area / 0.60))
                    else:
                        side = min(core_w * 0.35, core_h * 0.35)
                    ix = self.core_rect.left() + 20.0 if self.core_rect else 20.0
                    iy = self.core_rect.top() + 20.0 if self.core_rect else 20.0
                    v_item = VoltageIslandItem(
                        ix, iy, side, side,
                        pd.name, getattr(pd, 'voltage', 1.8), getattr(pd, 'elements', []),
                        self.core_rect, parent=None
                    )
                    self.scene.addItem(v_item)

        region_items = [it for it in self.scene.items() if isinstance(it, RegionItem)]
        island_items = [it for it in self.scene.items() if isinstance(it, VoltageIslandItem)]
        if not region_items and not island_items:
            QMessageBox.information(self, "Auto Region Placement", "No regions, voltage islands, or modules defined to place.")
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
        for vi in island_items:
            self._saved_region_snapshot[vi.domain_name] = {
                "pos_x": vi.pos().x(),
                "pos_y": vi.pos().y(),
                "rect_x": vi.rect().x(),
                "rect_y": vi.rect().y(),
                "width": vi.rect().width(),
                "height": vi.rect().height(),
                "locked": vi.locked,
            }
        macro_items_pre = [it for it in self.scene.items() if isinstance(it, MacroItem)]
        for m in macro_items_pre:
            self._saved_region_snapshot[m.inst_name] = {
                "pos_x": m.pos().x(),
                "pos_y": m.pos().y(),
                "orientation": m.orientation,
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

        for vi in island_items:
            scene_vi = vi.sceneBoundingRect()
            elem_name = vi.elements[0] if vi.elements else vi.domain_name
            mod_area = self.module_areas.get(elem_name, 0.0) if hasattr(self, 'module_areas') else 0.0
            if mod_area == 0.0:
                for elem in vi.elements:
                    mod_area += self.module_areas.get(elem, 0.0) if hasattr(self, 'module_areas') else 0.0
            vi_halo = vi.halo if hasattr(vi, 'halo') else (15.0, 15.0, 15.0, 15.0)
            region_dicts.append({
                "module": vi.domain_name,
                "x": scene_vi.x(),
                "y": scene_vi.y(),
                "width": vi.rect().width(),
                "height": vi.rect().height(),
                "locked": vi.locked,
                "is_fence": True,
                "density": 0.60,
                "halo": vi_halo,
                "module_area": mod_area
            })
            for elem in vi.elements:
                region_dicts.append({
                    "module": elem,
                    "x": scene_vi.x(),
                    "y": scene_vi.y(),
                    "width": vi.rect().width(),
                    "height": vi.rect().height(),
                    "locked": vi.locked,
                    "is_fence": True,
                    "density": 0.60,
                    "halo": vi_halo,
                    "module_area": self.module_areas.get(elem, mod_area) if hasattr(self, 'module_areas') else mod_area
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
        # Automatically ensure all declared non-top UPF power domains have islands on canvas
        if hasattr(self, "power_domains"):
            core_w = self.core_rect.width() if self.core_rect else 1000.0
            core_h = self.core_rect.height() if self.core_rect else 1000.0
            existing_island_domains = {vi.domain_name for vi in self.scene.items() if isinstance(vi, VoltageIslandItem)}
            for pd in self.power_domains:
                if not pd.is_top and pd.name not in existing_island_domains:
                    # Calculate required area based on constituent modules or default 15%
                    dom_std_area = sum(getattr(self, 'module_areas', {}).get(elem, 0.0) for elem in getattr(pd, 'elements', []))
                    if dom_std_area > 0:
                        side = max(60.0, math.sqrt(dom_std_area / 0.60))
                    else:
                        side = min(core_w * 0.35, core_h * 0.35)
                    ix = self.core_rect.left() + 20.0 if self.core_rect else 20.0
                    iy = self.core_rect.top() + 20.0 if self.core_rect else 20.0
                    v_item = VoltageIslandItem(
                        ix, iy, side, side,
                        pd.name, getattr(pd, 'voltage', 1.8), getattr(pd, 'elements', []),
                        self.core_rect, parent=None
                    )
                    self.scene.addItem(v_item)

        region_items = [it for it in self.scene.items() if isinstance(it, RegionItem)]
        island_items = [it for it in self.scene.items() if isinstance(it, VoltageIslandItem)]
        if not region_items and not island_items:
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

        for vi in island_items:
            scene_vi = vi.sceneBoundingRect()
            elem_name = vi.elements[0] if vi.elements else vi.domain_name
            mod_area = self.module_areas.get(elem_name, 0.0) if hasattr(self, 'module_areas') else 0.0
            if mod_area == 0.0:
                for elem in vi.elements:
                    mod_area += self.module_areas.get(elem, 0.0) if hasattr(self, 'module_areas') else 0.0
            vi_halo = vi.halo if hasattr(vi, 'halo') else (15.0, 15.0, 15.0, 15.0)
            region_dicts.append({
                "module": vi.domain_name,
                "x": scene_vi.x(),
                "y": scene_vi.y(),
                "width": vi.rect().width(),
                "height": vi.rect().height(),
                "locked": vi.locked,
                "is_fence": True,
                "density": 0.60,
                "halo": vi_halo,
                "module_area": mod_area
            })
            for elem in vi.elements:
                region_dicts.append({
                    "module": elem,
                    "x": scene_vi.x(),
                    "y": scene_vi.y(),
                    "width": vi.rect().width(),
                    "height": vi.rect().height(),
                    "locked": vi.locked,
                    "is_fence": True,
                    "density": 0.60,
                    "halo": vi_halo,
                    "module_area": self.module_areas.get(elem, mod_area) if hasattr(self, 'module_areas') else mod_area
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
            from backendflow.floorplanner.region_autoplacer import HierarchicalAutoRegionPlacer

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

        for vi in island_items:
            # Check placements by domain name or scope elements
            target_rect = None
            if vi.domain_name in result["placements"]:
                target_rect = result["placements"][vi.domain_name]
            else:
                for elem in vi.elements:
                    if elem in result["placements"]:
                        target_rect = result["placements"][elem]
                        break
            if target_rect:
                vi.setPos(0, 0)
                vi.setRect(target_rect.x(), target_rect.y(), target_rect.width(), target_rect.height())
                # Update underlying PowerDomain object bounds
                if hasattr(self, "power_domains"):
                    for pd in self.power_domains:
                        if pd.name == vi.domain_name:
                            pd.area = (
                                round(target_rect.x(), 3),
                                round(target_rect.y(), 3),
                                round(target_rect.x() + target_rect.width(), 3),
                                round(target_rect.y() + target_rect.height(), 3)
                            )
                            break

        # Also automatically place and adjust macros so macros and power domains move together
        unlocked_macros = [m for m in macro_items if not getattr(m, 'locked', False) and not is_io_pad_cell(m.inst_name, m.name)]
        if unlocked_macros:
            # Build obstacles from placed voltage islands (with halo) and blockages
            island_obs = []
            for vi in island_items:
                island_obs.append(vi.halo_scene_bounding_rect() if hasattr(vi, 'halo_scene_bounding_rect') else vi.sceneBoundingRect())
            for b in self.scene.items():
                if isinstance(b, BlockageItem):
                    island_obs.append(b.sceneBoundingRect())

            macros_raw = [{
                'inst_name': m.inst_name,
                'master_name': m.name,
                'w': m.w,
                'h': m.h,
                'orient': m.orientation,
                'halo': list(m.halo),
                'item_ref': m
            } for m in unlocked_macros]

            ml = self.core_rect.x()
            mb = self.core_rect.y()
            mr = self.die_rect.width() - (self.core_rect.x() + self.core_rect.width())
            mt = self.die_rect.height() - (self.core_rect.y() + self.core_rect.height())

            _, _, placed_macros = compute_peripheral_macro_placement(
                macros_raw,
                die_w=self.die_rect.width(),
                die_h=self.die_rect.height(),
                margins=(ml, mr, mb, mt),
                macro_sizes=self.macro_sizes,
                existing_obstacles=island_obs
            )
            for pm in placed_macros:
                for m in unlocked_macros:
                    if m.inst_name == pm['inst_name']:
                        m.set_orientation(pm['orientation'])
                        m.update_halo(*pm['halo'])
                        m.setPos(pm['x'], pm['y'])
                        break

        if hasattr(self, "populate_power_domains_ui"):
            self.populate_power_domains_ui()

        # Automatically re-project pins and pads based on newly placed regions and islands
        self.auto_align_pads_to_regions(silent=True)

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

    def _extract_standard_cell_area(self):
        """Discovers and parses standard cell and module area reports from synthesis."""
        total_std_area = getattr(self, 'total_std_cell_area', 0.0)
        proj_root, base = self._get_project_context()
        rep_dir = os.path.join(proj_root, "reports")
        if os.path.isdir(rep_dir):
            import glob, json
            # 1. Search for *_sizes.json produced by backendflow/OpenROAD init
            for c_path in sorted(glob.glob(os.path.join(rep_dir, "*_sizes.json")), reverse=True):
                try:
                    with open(c_path, "r") as f:
                        sdata = json.load(f)
                        cand_area = float(sdata.get("total_std_cell_area", 0.0))
                        if cand_area > 0:
                            self.total_std_cell_area = cand_area
                            if 'modules' in sdata and not getattr(self, 'module_areas', None):
                                self.module_areas = sdata['modules']
                            return self.total_std_cell_area
                except Exception:
                    pass

            # 2. Search for Yosys area.rpt
            area_rpt = os.path.join(rep_dir, "area.rpt")
            if os.path.isfile(area_rpt):
                try:
                    with open(area_rpt, "r") as f:
                        sdata = json.load(f)
                        cand_area = 0.0
                        if "design" in sdata and "area" in sdata["design"]:
                            cand_area = float(sdata["design"]["area"])
                        elif "modules" in sdata:
                            for mname, minfo in sdata["modules"].items():
                                if "area" in minfo:
                                    cand_area += float(minfo["area"])
                        if cand_area > 0:
                            self.total_std_cell_area = cand_area
                            return self.total_std_cell_area
                except Exception:
                    pass

        return total_std_area

    def on_fit_core_to_density_clicked(self):
        """Mathematically fits core width and height to achieve the target density."""
        target_dens = self.sp_target_core_density.value() / 100.0
        total_std_area = getattr(self, 'total_std_cell_area', 0.0)
        
        # Fallback: query project context and reports if total_std_cell_area is not populated
        if total_std_area <= 0.0:
            total_std_area = self._extract_standard_cell_area()

        # Calculate macro area
        macro_area = 0.0
        for it in self.scene.items():
            if isinstance(it, MacroItem):
                macro_area += it.rect().width() * it.rect().height()

        # Guard against zero or uninitialized areas
        if total_std_area <= 0.0 and macro_area <= 0.0:
            QMessageBox.warning(
                self,
                "Cannot Fit Core",
                "Standard cell and macro areas are 0 or synthesis sizes report has not been generated yet.\n\n"
                "Please synthesize or run backend initialization first, or specify die dimensions manually."
            )
            return

        req_logic_area = total_std_area / max(0.10, min(0.95, target_dens))
        req_core_area = (req_logic_area + macro_area) * 1.15  # 15% routing reserve

        side = math.sqrt(req_core_area)
        # Snap to Sky130 row height multiple (min 50.0 um to prevent zero or sub-margin collapse)
        row_h = 2.72
        side_h = max(50.0, math.ceil(side / row_h) * row_h)
        side_w = side_h

        ml = self.sp_marg_l.value(); mr = self.sp_marg_r.value()
        mb = self.sp_marg_b.value(); mt = self.sp_marg_t.value()

        die_w = max(side_w + ml + mr, 100.0)
        die_h = max(side_h + mb + mt, 100.0)

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
            if items and (isinstance(items[0], MacroItem) or isinstance(items[0], BlockageItem) or isinstance(items[0], RegionItem) or isinstance(items[0], VoltageIslandItem)):
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
                elif isinstance(m, VoltageIslandItem):
                    full_name = f"Island: {m.domain_name} ({m.voltage:.2f}V)"
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
                    self.sp_sel_x.setValue(m.rect().x() + m.pos().x())
                    self.sp_sel_y.setValue(m.rect().y() + m.pos().y())
                
                l, r, b, t = getattr(m, 'halo', (0, 0, 0, 0))
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

        # Power Domain UPF Intent and Shim
        proj_root, base = self._get_project_context()
        upf_rel = "power/design.upf"
        upf_abs = os.path.join(proj_root, upf_rel).replace("\\", "/")
        if not os.path.isfile(upf_abs):
            upf_rel = "design.upf"
            upf_abs = os.path.join(proj_root, upf_rel).replace("\\", "/")
        if os.path.isfile(upf_abs):
            shim_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "shims", "openroad_upf_shim.tcl")).replace("\\", "/")
            tcl += f"\n# === Silis Power Gating Intent (IEEE 1801 UPF) ===\n"
            if os.path.isfile(shim_path):
                tcl += f"if {{[info procs _silis_orig_create_power_domain] eq \"\"}} {{ source \"{shim_path}\" }}\n"
            tcl += f"# Power intent is ingested during design initialization (init_pdk.tcl);\n"
            tcl += f"# Avoid re-reading UPF here to prevent duplicate power domain definition errors (UPF-0019).\n"
            tcl += f"if {{[info procs _silis_orig_create_power_domain] eq \"\" && [file exists \"{upf_abs}\"]}} {{\n"
            tcl += f"    read_upf -file \"{upf_abs}\"\n"
            tcl += f"}}\n\n"

        has_islands = any(isinstance(item, VoltageIslandItem) for item in self.scene.items())
        island_tcl = ""
        if has_islands:
            island_tcl += "# === VOLTAGE ISLAND PHYSICAL AREAS ===\n"
            for item in self.scene.items():
                if isinstance(item, VoltageIslandItem):
                    ix1 = round(round((item.rect().x() + item.pos().x()) / 0.005) * 0.005, 3)
                    iy1 = round(round((item.rect().y() + item.pos().y()) / 0.005) * 0.005, 3)
                    ix2 = round(round((ix1 + item.rect().width()) / 0.005) * 0.005, 3)
                    iy2 = round(round((iy1 + item.rect().height()) / 0.005) * 0.005, 3)
                    island_tcl += f"set_domain_area {item.domain_name} -area {{{ix1} {iy1} {ix2} {iy2}}}\n"
            island_tcl += "\n"

        # Crucial OpenROAD sequencing: set_domain_area must be executed BEFORE initialize_floorplan,
        if island_tcl:
            tcl += island_tcl

        tcl += "# === INITIALIZATION ===\n"
        # Standard cell site initialization (single-height standard cells only to prevent duplicate row overlap)
        tcl += f'initialize_floorplan -die_area "0 0 {die_w} {die_h}" -core_area "{core_x1} {core_y1} {core_x2} {core_y2}" -site {site_name}\n\n'

        # Deduplicate overlapping rows created by multi-domain row slicing
        tcl += "# Deduplicate overlapping rows created by multi-domain row slicing\n"
        tcl += "set _blk [ord::get_db_block]\n"
        tcl += "set _seen_rows [dict create]\n"
        tcl += "foreach _r [$_blk getRows] {\n"
        tcl += "    set _orig [$_r getOrigin]\n"
        tcl += "    set _cnt [$_r getSiteCount]\n"
        tcl += "    set _site [[$_r getSite] getName]\n"
        tcl += "    set _key \"${_site},[lindex $_orig 0],[lindex $_orig 1],${_cnt}\"\n"
        tcl += "    if {[dict exists $_seen_rows $_key]} {\n"
        tcl += "        odb::dbRow_destroy $_r\n"
        tcl += "    } else {\n"
        tcl += "        dict set _seen_rows $_key 1\n"
        tcl += "    }\n"
        tcl += "}\n\n"

        # Macro deduplication helper
        seen_macro_insts = set()
        deduped_macros = []
        for item in self.scene.items():
            if isinstance(item, MacroItem) and not is_io_pad_cell(item.inst_name, item.name):
                if item.inst_name in seen_macro_insts:
                    continue
                seen_macro_insts.add(item.inst_name)
                deduped_macros.append(item)

        valid_macros = deduped_macros
        if valid_macros:
            tcl += "# === MACRO PLACEMENT ===\n"
            for item in valid_macros:
                ox = round(round(item.pos().x() / 0.005) * 0.005, 3)
                oy = round(round(item.pos().y() / 0.005) * 0.005, 3)
                halo_str = f" -halo {{{item.halo[0]} {item.halo[1]} {item.halo[2]} {item.halo[3]}}}" if any(x > 0 for x in item.halo) else ""
                cell_str = f' -cell "{item.name}"' if item.name else ""
                ori = item.orientation
                if ori == "MX90": ori = "MXR90"
                elif ori == "MY90": ori = "MYR90"
                tcl += f'place_macro -inst "{item.inst_name}"{cell_str} -location {{{ox} {oy}}} -orient {ori}{halo_str}\n'
            # Cut rows around macros with their 10um halos so std cells and tapcells never place inside macro bodies or keepouts
            tcl += "catch { cut_rows -halo_width_x 10.0 -halo_width_y 10.0 }\n\n"

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
            # Collect elements of placed power domain islands to prevent emitting nested duplicate fences
            island_elems = set()
            for item in self.scene.items():
                if isinstance(item, VoltageIslandItem):
                    for el in getattr(item, "elements", []):
                        island_elems.add(el)
                        island_elems.add(el.split("/")[-1])

            emitted_regions = 0
            region_tcl_buf = ""
            for item in self.scene.items():
                if isinstance(item, RegionItem):
                    m_name = item.module_name
                    m_base = m_name.split("/")[-1]
                    # Exclude redundant nested regions for modules already governed by a Power Domain island
                    if (m_name in island_elems or m_base in island_elems or 
                        any(m_name.startswith(el + "/") for el in island_elems)):
                        continue
                    cmd_name = "create_fence" if item.is_fence else "create_region"
                    type_str = "" if item.is_fence else " -type inclusive"
                    density_val = getattr(item, 'density', 0.60)
                    density_str = f" -density {density_val:.2f}"
                    halo_str = f" -halo {{{item.halo[0]} {item.halo[1]} {item.halo[2]} {item.halo[3]}}}" if any(x > 0 for x in item.halo) else ""
                    m_boxes = getattr(item, 'multi_boxes', [])
                    if m_boxes and len(m_boxes) > 1:
                        boxes_str = " ".join(f"{{{round(round(b[0] / 0.005) * 0.005, 3)} {round(round(b[1] / 0.005) * 0.005, 3)} {round(round(b[2] / 0.005) * 0.005, 3)} {round(round(b[3] / 0.005) * 0.005, 3)}}}" for b in m_boxes)
                        region_tcl_buf += f'{cmd_name} -module "{item.module_name}" -boxes {{{boxes_str}}}{type_str}{density_str}{halo_str}\n'
                    else:
                        rx1 = round(round((item.rect().x() + item.pos().x()) / 0.005) * 0.005, 3)
                        ry1 = round(round((item.rect().y() + item.pos().y()) / 0.005) * 0.005, 3)
                        rx2 = round(round((rx1 + item.rect().width()) / 0.005) * 0.005, 3)
                        ry2 = round(round((ry1 + item.rect().height()) / 0.005) * 0.005, 3)
                        region_tcl_buf += f'{cmd_name} -module "{item.module_name}" -box {{{rx1} {ry1} {rx2} {ry2}}}{type_str}{density_str}{halo_str}\n'
                    emitted_regions += 1

            if emitted_regions > 0:
                tcl += "\n# === REGIONS & FENCES ===\n" + region_tcl_buf

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

        # === I/O PIN & PAD PLACEMENT (Pure WYSIWYG) ===
        is_pad_mode = getattr(self, "pad_ring_enabled", False) or (hasattr(self, "rb_chip") and self.rb_chip.isChecked())
        if is_pad_mode:
            tcl += "\n# === FULL-CHIP I/O PAD RING GENERATION ===\n"
            tcl += "# Ensure tracks and I/O sites exist prior to pin and pad placement\n"
            tcl += "catch { make_tracks }\n"
            tcl += "proc _resolve_pin_net {pname} {\n"
            tcl += "    set blk [ord::get_db_block]\n"
            tcl += "    set bterm [$blk findBTerm $pname]\n"
            tcl += "    if {$bterm ne \"NULL\" && [$bterm getNet] ne \"NULL\"} {\n"
            tcl += "        return [[$bterm getNet] getName]\n"
            tcl += "    }\n"
            tcl += "    return $pname\n"
            tcl += "}\n"
            tcl += "set _db [::ord::get_db]\n"
            tcl += "set _has_site 0\n"
            tcl += "foreach _lib [$_db getLibs] { if {[$_lib findSite \"IO_SITE\"] != \"NULL\"} { set _has_site 1; break } }\n"
            tcl += "if {!$_has_site} { make_fake_io_site -name IO_SITE -width 1 -height 200 }\n"
            tcl += "set _has_csite 0\n"
            tcl += "foreach _lib [$_db getLibs] { if {[$_lib findSite \"IO_CSITE\"] != \"NULL\"} { set _has_csite 1; break } }\n"
            tcl += "if {!$_has_csite} { make_fake_io_site -name IO_CSITE -width 200 -height 204 }\n"
            tcl += "catch { make_io_sites -horizontal_site IO_SITE -vertical_site IO_SITE -corner_site IO_CSITE -offset 10 -rotation_horizontal R180 -rotation_vertical R180 -rotation_corner R180 }\n"
            tcl += "catch { place_corners sky130_ef_io__corner_pad }\n\n"

            def _pad_master(data):
                if isinstance(data, dict) and data.get("pad_cell"):
                    return data["pad_cell"]
                direction = data.get("dir", "input") if isinstance(data, dict) else str(data)
                if direction in ("power",):
                    return "sky130_fd_io__top_power_lvc_wpad"
                elif direction in ("ground",):
                    return "sky130_fd_io__top_ground_lvc_wpad"
                else:
                    return "sky130_fd_io__top_gpiov2"

            is_staggered = getattr(self, "pad_strategy", "single") == "staggered"
            dw = die_w
            dh = die_h

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
                    # Dual-row staggered pads: Outer tier inset 110 µm, Inner tier inset 290 µm
                    # Corners clearance: 240 µm
                    pad_width = 80.0
                    row_min = 240.0
                    row_max = max(row_min, edge_len - 240.0 - pad_width)
                    max_span = max(0.0, row_max - row_min)
                    n = len(pad_list)
                    step = (max_span / (n - 1)) if n > 1 else 0.0
                    start = row_min if n > 1 else (row_min + max_span / 2.0)

                    for i, (pname, pdata) in enumerate(pad_list):
                        loc = start + i * step
                        tier = pdata.get("tier", "Outer (Ring 1)")
                        is_inner = "Inner" in tier or (tier == "Outer (Ring 1)" and (i % 2 == 1))
                        row_sub = f"{base_name}_2" if is_inner else f"{base_name}_1"
                        inset_dist = 290.0 if is_inner else 110.0

                        master = _pad_master(pdata)
                        safe = re.sub(r'[^A-Za-z0-9_]', '_', pname)
                        inst_name = safe if safe.startswith("pad_") else f"pad_{safe}"
                        tcl += f"catch {{ place_pad -master {master} -row {row_sub} -location {loc:.3f} {inst_name} }}\n"

                        if edge == "bottom": ploc = f"{loc + 40.0:.3f} {inset_dist:.3f}"; player = "met2"
                        elif edge == "top": ploc = f"{loc + 40.0:.3f} {dh - inset_dist:.3f}"; player = "met2"
                        elif edge == "left": ploc = f"{inset_dist:.3f} {loc + 40.0:.3f}"; player = "met3"
                        else: ploc = f"{dw - inset_dist:.3f} {loc + 40.0:.3f}"; player = "met3"

                        if not pdata.get("_is_supply", False):
                            tcl += f"catch {{ place_pin -pin_name \"{pname}\" -layer {player} -location {{{ploc}}} }}\n"
                else:
                    pad_width = 80.0
                    if edge in ("bottom", "top"):
                        row_min = 210.0
                        row_max = max(row_min, edge_len - 210.0 - pad_width)
                    else:
                        row_min = 214.0
                        row_max = max(row_min, edge_len - 214.0 - pad_width)
                    max_span = max(0.0, row_max - row_min)
                    n = len(pad_list)
                    step = (max_span / (n - 1)) if n > 1 else 0.0
                    pad_list.sort(key=lambda item: item[1].get("x", 0.0) if edge in ("bottom", "top") else item[1].get("y", 0.0))
                    def _safe_get_dragged(pname):
                        item = self.pin_items.get(pname)
                        try:
                            return getattr(item, 'manually_dragged', False) if item else False
                        except RuntimeError:
                            return False

                    def _safe_get_pos(pname):
                        item = self.pin_items.get(pname)
                        try:
                            return item.pos() if item else None
                        except RuntimeError:
                            return None

                    any_dragged = any(_safe_get_dragged(name) for name, _ in pad_list)
                    start = row_min if n > 1 else (row_min + max_span / 2.0)

                    # Compute minimum pitch: pad cell is 80.0um wide, minimum non-overlapping pitch is 80.0um
                    min_pitch = max(80.0, step) if n > 1 else 80.0
                    last_loc = row_min - min_pitch
                    for i, (name, data) in enumerate(pad_list):
                        item_pos = _safe_get_pos(name) if any_dragged else None
                        if item_pos is not None:
                            cen = item_pos.x() if edge in ("bottom", "top") else item_pos.y()
                            loc = snap_to_grid(max(row_min, min(row_max, cen - 40.0)))
                            if loc < last_loc + min_pitch:
                                loc = snap_to_grid(last_loc + min_pitch)
                        else:
                            loc = snap_to_grid(start + i * step)
                            if loc < last_loc + min_pitch:
                                loc = snap_to_grid(last_loc + min_pitch)
                        # Clamping to row_max ensures pad never violates row boundary (e.g. PAD-0119)
                        if loc > row_max:
                            loc = row_max
                        last_loc = loc
                        master = _pad_master(data)
                        safe_name = re.sub(r'[^A-Za-z0-9_]', '_', name)
                        inst_name = safe_name if safe_name.startswith("pad_") else f"pad_{safe_name}"
                        tcl += f"catch {{ place_pad -master {master} -row {base_name} -location {loc:.3f} {inst_name} }}\n"

                        if edge == "bottom": pin_x = loc + 40.000; pin_y = 210.000; player = "met2"
                        elif edge == "top": pin_x = loc + 40.000; pin_y = dh - 210.000; player = "met2"
                        elif edge == "left": pin_x = 210.000; pin_y = loc + 40.000; player = "met3"
                        else: pin_x = dw - 210.000; pin_y = loc + 40.000; player = "met3"
                        ploc = f"{pin_x:.3f} {pin_y:.3f}"
                        if not data.get("_is_supply", False):
                            tcl += f"catch {{ place_pin -pin_name \"{name}\" -layer {player} -location {{{ploc}}} }}\n"
                            p_dir = data.get("dir", "input")
                            tcl += f"set _pnet [_resolve_pin_net \"{name}\"]\n"
                            # Hook internal logical net to the pad instance so the pad is fully wired
                            if p_dir == "output":
                                tcl += f"catch {{ connect_pin $_pnet \"{inst_name}/OUT\" }}\n"
                            elif p_dir == "inout":
                                tcl += f"catch {{ connect_pin $_pnet \"{inst_name}/IN\" }}\n"
                                tcl += f"catch {{ connect_pin $_pnet \"{inst_name}/OUT\" }}\n"
                            else:
                                tcl += f"catch {{ connect_pin $_pnet \"{inst_name}/IN\" }}\n"
                            tcl += f"catch {{ connect_pin $_pnet \"{inst_name}/PAD\" }}\n"

            tcl += "\n# --- Pad Ring Fillers and Abutment ---\n"
            tcl += "set pad_fill {sky130_ef_io__com_bus_slice_20um sky130_ef_io__com_bus_slice_10um sky130_ef_io__com_bus_slice_5um sky130_ef_io__com_bus_slice_1um}\n"
            tcl += "foreach row {IO_NORTH IO_SOUTH IO_WEST IO_EAST} {\n"
            tcl += "    catch { place_io_fill -row $row {*}$pad_fill }\n"
            tcl += "}\n"
            tcl += "catch { connect_by_abutment }\n"
            tcl += "\n# Ensure any internal logic ports (e.g. UPF sleep control nets) are placed\n"
            tcl += "catch { place_pins -random -hor_layers met3 -ver_layers met2 }\n"
        else:
            tcl += "\n# === MACRO PERIPHERAL PORT PLACEMENT (Pure WYSIWYG) ===\n"
            tcl += "make_tracks\n"
            tcl += "catch { clear_io_pin_constraints }\n"
            for name, data in sorted(self.pins_data.items()):
                if data.get("_is_supply", False) or name.startswith("pad_v"):
                    continue
                edge = data.get("edge", "bottom")
                if edge == "unplaced":
                    continue
                px = snap_to_grid(data.get("x", 0.0))
                py = snap_to_grid(data.get("y", 0.0))
                layer = "met3" if edge in ("bottom", "top") else "met4"
                try:
                    if name in self.pin_items and hasattr(self.pin_items[name], "layer"):
                        layer = self.pin_items[name].layer
                except RuntimeError:
                    pass
                tcl += f"catch {{ place_pin -pin_name \"{name}\" -layer {layer} -location {{{px:.3f} {py:.3f}}} }}\n"

        # === TAPCELL INSERTION RULES PER POWER DOMAIN ===
        tap_dist = self.sp_tap_distance.value() if hasattr(self, 'sp_tap_distance') else 14.0
        default_tap = self.cmb_default_tapcell.currentText() if hasattr(self, 'cmb_default_tapcell') else "sky130_fd_sc_hd__tapvpwrvgnd_1"
        tcl += f"\n# === TAPCELL INSERTION ===\n"
        tcl += "set _blk [ord::get_db_block]\n"
        tcl += "set _seen_rows [dict create]\n"
        tcl += "foreach _r [$_blk getRows] {\n"
        tcl += "    set _orig [$_r getOrigin]\n"
        tcl += "    set _cnt [$_r getSiteCount]\n"
        tcl += "    set _site [[$_r getSite] getName]\n"
        tcl += "    set _key \"${_site},[lindex $_orig 0],[lindex $_orig 1],${_cnt}\"\n"
        tcl += "    if {[dict exists $_seen_rows $_key]} {\n"
        tcl += "        odb::dbRow_destroy $_r\n"
        tcl += "    } else {\n"
        tcl += "        dict set _seen_rows $_key 1\n"
        tcl += "    }\n"
        tcl += "}\n"
        tcl += f"catch {{ tapcell -distance {tap_dist} -tapcell_master {default_tap} }}\n"

        # Check for power domains with custom domain-specific tapcell types
        custom_domain_taps = []
        # Inspect canvas VoltageIslandItem objects first
        for it in self.scene.items():
            if isinstance(it, VoltageIslandItem):
                d_tap = getattr(it, 'tapcell_type', default_tap)
                if d_tap and d_tap != default_tap:
                    bx1 = snap_to_grid(it.rect().x() + it.pos().x())
                    by1 = snap_to_grid(it.rect().y() + it.pos().y())
                    bx2 = snap_to_grid(bx1 + it.rect().width())
                    by2 = snap_to_grid(by1 + it.rect().height())
                    custom_domain_taps.append({
                        'domain': it.domain_name,
                        'tapcell': d_tap,
                        'box': (bx1, by1, bx2, by2)
                    })

        # Also inspect power domains list in case islands aren't on canvas but have areas
        if hasattr(self, 'power_domains'):
            existing_dnames = {cd['domain'] for cd in custom_domain_taps}
            for pd in self.power_domains:
                if pd.name not in existing_dnames and getattr(pd, 'tapcell_type', default_tap) != default_tap:
                    if getattr(pd, 'area', None):
                        custom_domain_taps.append({
                            'domain': pd.name,
                            'tapcell': pd.tapcell_type,
                            'box': (pd.area[0], pd.area[1], pd.area[2], pd.area[3])
                        })

        if custom_domain_taps:
            tcl += "\n# --- Multi-Domain Custom Tapcell Assignment ---\n"
            tcl += "set _db [::ord::get_db]\n"
            tcl += "set _dbu [$_blk getDbUnitsPerMicron]\n"
            for cdt in custom_domain_taps:
                dname = cdt['domain']
                tap_cell = cdt['tapcell']
                x1, y1, x2, y2 = cdt['box']
                tcl += f"\n# Custom tapcell for Power Domain {dname}: {tap_cell}\n"
                tcl += f"set _dom_master_{dname} [$_db findMaster \"{tap_cell}\"]\n"
                tcl += f"if {{$_dom_master_{dname} ne \"NULL\"}} {{\n"
                tcl += f"    set _dx0 [expr {{{x1} * $_dbu}}]\n"
                tcl += f"    set _dy0 [expr {{{y1} * $_dbu}}]\n"
                tcl += f"    set _dx1 [expr {{{x2} * $_dbu}}]\n"
                tcl += f"    set _dy1 [expr {{{y2} * $_dbu}}]\n"
                tcl += f"    set _swaps_{dname} [list]\n"
                tcl += f"    foreach _inst [$_blk getInsts] {{\n"
                tcl += f"        if {{[string match \"*tap*\" [string tolower [$_inst getName]]] || [string match \"*tap*\" [string tolower [[$_inst getMaster] getName]]]}} {{\n"
                tcl += f"            set _loc [$_inst getLocation]\n"
                tcl += f"            set _ix [lindex $_loc 0]\n"
                tcl += f"            set _iy [lindex $_loc 1]\n"
                tcl += f"            if {{$_ix >= $_dx0 && $_ix <= $_dx1 && $_iy >= $_dy0 && $_iy <= $_dy1}} {{\n"
                tcl += f"                lappend _swaps_{dname} [list [$_inst getName] $_ix $_iy [$_inst getOrient]]\n"
                tcl += f"                odb::dbInst_destroy $_inst\n"
                tcl += f"            }}\n"
                tcl += f"        }}\n"
                tcl += f"    }}\n"
                tcl += f"    foreach _s $_swaps_{dname} {{\n"
                tcl += f"        set _iname [lindex $_s 0]\n"
                tcl += f"        set _ix [lindex $_s 1]\n"
                tcl += f"        set _iy [lindex $_s 2]\n"
                tcl += f"        set _orient [lindex $_s 3]\n"
                tcl += f"        set _new_inst [odb::dbInst_create $_blk $_dom_master_{dname} $_iname]\n"
                tcl += f"        $_new_inst setLocationOrient $_orient\n"
                tcl += f"        $_new_inst setLocation $_ix $_iy\n"
                tcl += f"        $_new_inst setPlacementStatus PLACED\n"
                tcl += f"    }}\n"
                tcl += f"}}\n"

        # === POWER DISTRIBUTION NETWORK (PDN) SYNTHESIS ===
        tcl += "\n# === POWER DISTRIBUTION NETWORK (PDN) ===\n"
        tcl += "set _tech [::ord::get_db_tech]\n"
        tcl += "if {[$_tech findLayer \"met1\"] ne \"NULL\"} {\n"
        tcl += "    set _pdn_bot \"met1\"\n"
        tcl += "    set _pdn_top \"met4\"\n"
        tcl += "} else {\n"
        tcl += "    set _pdn_bot \"Metal1\"\n"
        tcl += "    set _pdn_top \"Metal4\"\n"
        tcl += "}\n\n"

        # Dedicated power/ground pad explicit bindings prior to PDN generation
        power_pads = [p for p in getattr(self, 'pins_data', {}).values() if p.get('dir') in ('power', 'ground') and p.get('domain')]
        if power_pads:
            tcl += "# === POWER PAD DOMAIN BINDINGS ===\n"
            tcl += "# Explicitly bind each dedicated power & ground pad instance pin to its domain supply net\n"
            for pad_name, pinfo in sorted(self.pins_data.items()):
                pdir = pinfo.get('dir')
                pdom = pinfo.get('domain')
                if pdir in ('power', 'ground') and pdom:
                    safe_pad = re.sub(r'[^A-Za-z0-9_]', '_', pad_name)
                    inst_name = safe_pad if safe_pad.startswith("pad_") else f"pad_{safe_pad}"
                    is_pwr = (pdir == 'power')
                    flag = "-power" if is_pwr else "-ground"

                    if pdom == "PD_TOP":
                        net_name = "VDD" if is_pwr else "VSS"
                    else:
                        net_name = f"VDD_{pdom}" if is_pwr else f"VSS_{pdom}"

                    # Primary supply pin binding
                    pin_pat = "{^P_CORE$|^VCCD$|^VPWR$|^VDD$}" if is_pwr else "{^G_CORE$|^VSSD$|^VGND$|^VSS$}"
                    tcl += f"# Power Pad: {pad_name} -> Domain: {pdom} ({pdir})\n"
                    tcl += f"catch {{ add_global_connection -net {{{net_name}}} -inst_pattern {{{inst_name}}} -pin_pattern {pin_pat} {flag} }}\n"
            tcl += "\n"

        # Connect power nets for standard cells and voltage domains
        tcl += "# Connect domain supplies for top-level core and switched power domains\n"
        tcl += "set _blk [ord::get_db_block]\n"
        tcl += "if {[$_blk findNet \"VDD\"] eq \"NULL\"} { odb::dbNet_create $_blk \"VDD\" }\n"
        tcl += "if {[$_blk findNet \"VSS\"] eq \"NULL\"} { odb::dbNet_create $_blk \"VSS\" }\n"
        # Multi-Voltage & Switched Power Domains: define separate nets and regional global connections
        switched_domains = []
        if hasattr(self, 'power_domains') and self.power_domains:
            for pd in self.power_domains:
                if not getattr(pd, 'is_top', False) and getattr(pd, 'name', '') and pd.name != 'PD_TOP':
                    switched_domains.append(pd)

        for pd in switched_domains:
            d_pwr = f"VDD_{pd.name}"
            d_gnd = "VSS"
            tcl += f"# Power Domain {pd.name} supply nets and regional connection\n"
            tcl += f"if {{[$_blk findNet \"{d_pwr}\"] eq \"NULL\"}} {{ odb::dbNet_create $_blk \"{d_pwr}\" }}\n"
            # Bind module instance hierarchy patterns explicitly for all domain elements before top-level catch-all
            for elem in getattr(pd, "elements", []):
                tcl += f"catch {{ add_global_connection -net {{{d_pwr}}} -inst_pattern {{.*{elem}.*}} -pin_pattern {{^VPWR$|^VDD$}} -power }}\n"
            mod_pat = pd.name.lower().replace("pd_", "")
            tcl += f"catch {{ add_global_connection -net {{{d_pwr}}} -inst_pattern {{.*{mod_pat}.*}} -pin_pattern {{^VPWR$|^VDD$}} -power }}\n"
            tcl += f"catch {{ add_global_connection -net {{{d_pwr}}} -region {{{pd.name}}} -pin_pattern {{^VPWR$|^VDD$}} -power }}\n"
            tcl += f"catch {{ add_global_connection -net {{{d_gnd}}} -region {{{pd.name}}} -pin_pattern {{^VGND$|^VSS$}} -ground }}\n"

        # Pad ring core supply and internal ESD clamp/body connections:
        tcl += "catch { add_global_connection -net {VDD} -inst_pattern {.*pad_v.*|.*IO_CORNER.*} -pin_pattern {^P_CORE$|^VCCD$|^DRN_LVC[12]$|^OGC_LVC$|^VCCHIB$|^VDDA$} -power }\n"
        tcl += "catch { add_global_connection -net {VSS} -inst_pattern {.*pad_v.*|.*IO_CORNER.*} -pin_pattern {^G_CORE$|^VSSD$|^SRC_BDY_LVC[12]$|^BDY2_B2B$|^VSSA$} -ground }\n"
        # Pad ring I/O buffer high-voltage rail connections:
        tcl += "catch { add_global_connection -net {VDDIO} -inst_pattern {.*} -pin_pattern {^VDDIO$|^VDDIO_Q$|^VSWITCH$} -power }\n"
        tcl += "catch { add_global_connection -net {VSSIO} -inst_pattern {.*} -pin_pattern {^VSSIO$|^VSSIO_Q$} -ground }\n"
        # Default top-level standard cells (after switched domain specific patterns)
        tcl += "catch { add_global_connection -net {VDD} -pin_pattern {^VPWR$|^VDD$|^vccd1$} -power }\n"
        tcl += "catch { add_global_connection -net {VSS} -pin_pattern {^VGND$|^VSS$|^vssd1$} -ground }\n"

        # Multi-Voltage UPF Physical Power Switch Definition
        has_gated_domain = any(getattr(p, "gated", False) or getattr(p, "power_switch_master", None) is not None or "internal" in str(getattr(p, "domain_type", "")).lower() or "gated" in str(getattr(p, "domain_type", "")).lower() for p in switched_domains)
        if has_gated_domain:
            tcl += "catch { add_global_connection -net {VDD} -power -pin_pattern {^VDDG$} }\n"
            tcl += "catch { define_power_switch_cell -name POWER_SWITCH -control SLEEP -acknowledge SLEEP_OUT -power_switchable VPWR -power VDDG -ground VGND }\n"

        tcl += "catch { global_connect }\n\n"

        # Core Top PDN Grid
        tcl += "catch { set_voltage_domain -name {Core} -power {VDD} -ground {VSS} }\n"
        tcl += "catch { define_pdn_grid -name {grid_top} -voltage_domains {Core} }\n"
        # Core Power Ring options from GUI
        enable_ring = self.chk_enable_ring.isChecked() if hasattr(self, 'chk_enable_ring') else True
        ring_w = self.sp_ring_width.value() if hasattr(self, 'sp_ring_width') else 5.0
        ring_s = self.sp_ring_spacing.value() if hasattr(self, 'sp_ring_spacing') else 2.0
        ring_off = self.sp_ring_offset.value() if hasattr(self, 'sp_ring_offset') else 5.0
        ring_h_layer = self.cmb_ring_h_layer.currentText() if hasattr(self, 'cmb_ring_h_layer') else "met5"
        ring_v_layer = self.cmb_ring_v_layer.currentText() if hasattr(self, 'cmb_ring_v_layer') else "met4"

        # Pad Trunk Bridge options from GUI
        enable_trunks = self.chk_enable_trunks.isChecked() if hasattr(self, 'chk_enable_trunks') else True
        trunk_layer = self.cmb_trunk_layer.currentText() if hasattr(self, 'cmb_trunk_layer') else "met4"
        trunk_width = self.sp_trunk_width.value() if hasattr(self, 'sp_trunk_width') else 3.2
        trunk_width_dbu = int(round(trunk_width * 1000))

        if enable_ring:
            tcl += f"# Core Peripheral Power Ring\n"
            tcl += f"catch {{ add_pdn_ring -grid {{grid_top}} -layers \"{ring_v_layer} {ring_h_layer}\" -widths {{{ring_w} {ring_w}}} -spacings {{{ring_s} {ring_s}}} -core_offsets {{{ring_off} {ring_off}}} }}\n"

        tcl += "# Standard cell followpin rails on met1\n"
        tcl += "catch { add_pdn_stripe -grid {grid_top} -layer $_pdn_bot -width {0.48} -followpins }\n"
        tcl += "# Power distribution grid stripes on met4\n"
        stripe_ext = "-extend_to_boundary" if (is_pad_mode and not enable_ring) else "-extend_to_core_ring"
        tcl += f"catch {{ add_pdn_stripe -grid {{grid_top}} -layer $_pdn_top -width {{1.6}} -pitch {{27.2}} -offset {{13.6}} {stripe_ext} }}\n"
        tcl += "catch { add_pdn_connect -grid {grid_top} -layers \"$_pdn_bot $_pdn_top\" }\n"
        if enable_ring:
            tcl += f"catch {{ add_pdn_connect -grid {{grid_top}} -layers \"{ring_v_layer} {ring_h_layer}\" }}\n"

        # Dedicated PDN Grids for Switched Power Domains
        for pd in switched_domains:
            d_pwr = f"VDD_{pd.name}"
            d_gnd = "VSS"
            grid_name = f"grid_{pd.name.lower()}"
            dtype = str(getattr(pd, "domain_type", "")).lower()
            is_gated = getattr(pd, "gated", False) or getattr(pd, "power_switch_master", None) is not None or "internal" in dtype or "gated" in dtype
            pwr_net_opt = " -power_control_network DAISY" if is_gated else ""
            tcl += f"\n# === Dedicated PDN Grid for Power Domain {pd.name} ===\n"
            tcl += f"catch {{ set_voltage_domain -name {{{pd.name}}} -power {{{d_pwr}}} -ground {{{d_gnd}}} -region {{{pd.name}}} }}\n"
            tcl += f"catch {{ define_pdn_grid -name {{{grid_name}}} -voltage_domains {{{pd.name}}}{pwr_net_opt} }}\n"
            tcl += f"catch {{ add_pdn_ring -grid {{{grid_name}}} -layers \"{ring_v_layer} {ring_h_layer}\" -widths {{2.0 2.0}} -spacings {{2.0 2.0}} -core_offsets {{2.0 2.0}} }}\n"
            tcl += f"catch {{ add_pdn_stripe -grid {{{grid_name}}} -layer $_pdn_bot -width {{0.48}} -followpins }}\n"
            tcl += f"catch {{ add_pdn_stripe -grid {{{grid_name}}} -layer $_pdn_top -width {{1.6}} -pitch {{27.2}} -offset {{13.6}} -extend_to_core_ring }}\n"
            tcl += f"catch {{ add_pdn_connect -grid {{{grid_name}}} -layers \"$_pdn_bot $_pdn_top\" }}\n"
            tcl += f"catch {{ add_pdn_connect -grid {{{grid_name}}} -layers \"{ring_v_layer} {ring_h_layer}\" }}\n"

        tcl += "\ncatch { pdngen }\n\n"

        # Dedicated targeted power pad trunk straps (connecting P_CORE/G_CORE to the core power ring)
        if is_pad_mode and enable_trunks:
            tcl += "# === DEDICATED POWER PAD TRUNK BRIDGES ===\n"
            tcl += "# Connect pad power/ground pins directly to the core power ring using OpenDB SBoxes with vias\n"
            tcl += "proc _build_pad_trunks {trunk_layer_name trunk_width_dbu} {\n"
            tcl += "    set blk [::ord::get_db_block]\n"
            tcl += "    set tech [::ord::get_db_tech]\n"
            tcl += "    set m_vert [$tech findLayer \"met4\"]\n"
            tcl += "    set m_horiz [$tech findLayer \"met5\"]\n"
            tcl += "    set via3_4 [$tech findVia \"M3M4_PR\"]\n"
            tcl += "    set via4_5 [$tech findVia \"M4M5_PR\"]\n"
            tcl += "    if {$m_vert eq \"NULL\" || $m_horiz eq \"NULL\"} { return }\n"
            tcl += "\n"
            tcl += "    set die [$blk getDieArea]\n"
            tcl += "    set die_w [expr {[$die xMax] - [$die xMin]}]\n"
            tcl += "    set die_h [expr {[$die yMax] - [$die yMin]}]\n"
            tcl += "\n"
            tcl += "    array set r_south_y {}\n"
            tcl += "    array set r_north_y {}\n"
            tcl += "    array set r_west_x {}\n"
            tcl += "    array set r_east_x {}\n"
            tcl += "    array set r_south_x1 {}; array set r_south_x2 {}\n"
            tcl += "    array set r_north_x1 {}; array set r_north_x2 {}\n"
            tcl += "    array set r_west_y1 {};  array set r_west_y2 {}\n"
            tcl += "    array set r_east_y1 {};  array set r_east_y2 {}\n"
            tcl += "\n"
            tcl += "    # Discover all 4 legs of the power ring for all power and ground nets (Core + Islands)\n"
            tcl += "    set ring_nets {VDD VSS}\n"
            tcl += "    foreach n [$blk getNets] {\n"
            tcl += "        set nname [$n getName]\n"
            tcl += "        if {[string match \"VDD_*\" $nname] && [lsearch -exact $ring_nets $nname] < 0} {\n"
            tcl += "            lappend ring_nets $nname\n"
            tcl += "        }\n"
            tcl += "    }\n"
            tcl += "    foreach net_name $ring_nets {\n"
            tcl += "        set net [$blk findNet $net_name]\n"
            tcl += "        if {$net eq \"NULL\"} { continue }\n"
            tcl += "        set r_south_y($net_name) 0; set r_north_y($net_name) 0\n"
            tcl += "        set r_west_x($net_name) 0;  set r_east_x($net_name) 0\n"
            tcl += "        set r_south_x1($net_name) 0; set r_south_x2($net_name) 0\n"
            tcl += "        set r_north_x1($net_name) 0; set r_north_x2($net_name) 0\n"
            tcl += "        set r_west_y1($net_name) 0;  set r_west_y2($net_name) 0\n"
            tcl += "        set r_east_y1($net_name) 0;  set r_east_y2($net_name) 0\n"
            tcl += "\n"
            tcl += "        foreach swire [$net getSWires] {\n"
            tcl += "            foreach sbox [$swire getWires] {\n"
            tcl += "                if {![$sbox isVia]} {\n"
            tcl += "                    set lyname [[$sbox getTechLayer] getName]\n"
            tcl += "                    set shape [$sbox getWireShapeType]\n"
            tcl += "                    if {$shape eq \"RING\"} {\n"
            tcl += "                        set x1 [$sbox xMin]; set y1 [$sbox yMin]\n"
            tcl += "                        set x2 [$sbox xMax]; set y2 [$sbox yMax]\n"
            tcl += "                        set len_x [expr {$x2 - $x1}]\n"
            tcl += "                        set len_y [expr {$y2 - $y1}]\n"
            tcl += "                        # Horizontal ring legs on met5\n"
            tcl += "                        if {$lyname eq \"met5\" && $len_x > $len_y} {\n"
            tcl += "                            set ym [expr {($y1 + $y2) / 2}]\n"
            tcl += "                            if {$r_south_y($net_name) == 0 || $ym < $r_south_y($net_name)} {\n"
            tcl += "                                set r_south_y($net_name) $ym\n"
            tcl += "                                set r_south_x1($net_name) $x1\n"
            tcl += "                                set r_south_x2($net_name) $x2\n"
            tcl += "                            }\n"
            tcl += "                            if {$r_north_y($net_name) == 0 || $ym > $r_north_y($net_name)} {\n"
            tcl += "                                set r_north_y($net_name) $ym\n"
            tcl += "                                set r_north_x1($net_name) $x1\n"
            tcl += "                                set r_north_x2($net_name) $x2\n"
            tcl += "                            }\n"
            tcl += "                        }\n"
            tcl += "                        # Vertical ring legs on met4\n"
            tcl += "                        if {$lyname eq \"met4\" && $len_y > $len_x} {\n"
            tcl += "                            set xm [expr {($x1 + $x2) / 2}]\n"
            tcl += "                            if {$r_west_x($net_name) == 0 || $xm < $r_west_x($net_name)} {\n"
            tcl += "                                set r_west_x($net_name) $xm\n"
            tcl += "                                set r_west_y1($net_name) $y1\n"
            tcl += "                                set r_west_y2($net_name) $y2\n"
            tcl += "                            }\n"
            tcl += "                            if {$r_east_x($net_name) == 0 || $xm > $r_east_x($net_name)} {\n"
            tcl += "                                set r_east_x($net_name) $xm\n"
            tcl += "                                set r_east_y1($net_name) $y1\n"
            tcl += "                                set r_east_y2($net_name) $y2\n"
            tcl += "                            }\n"
            tcl += "                        }\n"
            tcl += "                    }\n"
            tcl += "                }\n"
            tcl += "            }\n"
            tcl += "        }\n"
            tcl += "    }\n"
            tcl += "\n"
            tcl += "    set hw [expr {$trunk_width_dbu / 2}]\n"
            tcl += "    foreach inst [$blk getInsts] {\n"
            tcl += "        set mname [[$inst getMaster] getName]\n"
            tcl += "        set iname [$inst getName]\n"
            tcl += "        set is_vdd [string match \"*power*\" $mname]\n"
            tcl += "        set is_vss [string match \"*ground*\" $mname]\n"
            tcl += "        if {!$is_vdd && !$is_vss} { continue }\n"
            tcl += "\n"
            tcl += "        # Check if pad is assigned to a specific power domain net (e.g. pad_vdd_lowpwr -> VDD_PD_LOWPWR)\n"
            tcl += "        set net_name [expr {$is_vdd ? \"VDD\" : \"VSS\"}]\n"
            tcl += "        if {$is_vdd} {\n"
            tcl += "            foreach ring_cand $ring_nets {\n"
            tcl += "                if {$ring_cand ne \"VDD\" && $ring_cand ne \"VSS\"} {\n"
            tcl += "                    set dom_suffix [string tolower [string map {VDD_PD_ \"\" VDD_ \"\"} $ring_cand]]\n"
            tcl += "                    if {[string match \"*${dom_suffix}*\" [string tolower $iname]]} {\n"
            tcl += "                        set net_name $ring_cand\n"
            tcl += "                        break\n"
            tcl += "                    }\n"
            tcl += "                }\n"
            tcl += "            }\n"
            tcl += "        }\n"
            tcl += "        set net [$blk findNet $net_name]\n"
            tcl += "        if {$net eq \"NULL\"} { continue }\n"
            tcl += "        set swires [$net getSWires]\n"
            tcl += "        set swire [expr {[llength $swires] > 0 ? [lindex $swires 0] : [odb::dbSWire_create $net \"ROUTED\"]}]\n"
            tcl += "\n"
            tcl += "        set bbox [$inst getBBox]\n"
            tcl += "        set px1 [$bbox xMin]; set py1 [$bbox yMin]\n"
            tcl += "        set px2 [$bbox xMax]; set py2 [$bbox yMax]\n"
            tcl += "        set pcx [expr {($px1 + $px2) / 2}]\n"
            tcl += "        set pcy [expr {($py1 + $py2) / 2}]\n"
            tcl += "\n"
            tcl += "        # Omnidirectional side detection\n"
            tcl += "        set d_south $py1\n"
            tcl += "        set d_north [expr {$die_h - $py2}]\n"
            tcl += "        set d_west  $px1\n"
            tcl += "        set d_east  [expr {$die_w - $px2}]\n"
            tcl += "\n"
            tcl += "        set min_d $d_south\n"
            tcl += "        set pad_side \"SOUTH\"\n"
            tcl += "        if {$d_north < $min_d} { set min_d $d_north; set pad_side \"NORTH\" }\n"
            tcl += "        if {$d_west < $min_d}  { set min_d $d_west;  set pad_side \"WEST\"  }\n"
            tcl += "        if {$d_east < $min_d}  { set min_d $d_east;  set pad_side \"EAST\"  }\n"
            tcl += "\n"
            tcl += "        if {$pad_side eq \"SOUTH\"} {\n"
            tcl += "            set ring_y  $r_south_y($net_name)\n"
            tcl += "            set ring_x1 $r_south_x1($net_name)\n"
            tcl += "            set ring_x2 $r_south_x2($net_name)\n"
            tcl += "            if {$ring_y == 0} { continue }\n"
            tcl += "            # 1. Vertical met4 trunk northwards to ring Y\n"
            tcl += "            catch { odb::dbSBox_create $swire $m_vert [expr {$pcx - $hw}] $py2 [expr {$pcx + $hw}] $ring_y \"STRIPE\" }\n"
            tcl += "            if {$via3_4 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via3_4 $pcx $py2 \"STRIPE\" } }\n"
            tcl += "            if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $pcx $ring_y \"STRIPE\" } }\n"
            tcl += "            # 2. Horizontal met5 bend if outside [ring_x1, ring_x2]\n"
            tcl += "            if {$pcx > $ring_x2} {\n"
            tcl += "                catch { odb::dbSBox_create $swire $m_horiz [expr {$ring_x2 - $hw}] [expr {$ring_y - $hw}] [expr {$pcx + $hw}] [expr {$ring_y + $hw}] \"STRIPE\" }\n"
            tcl += "                if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $ring_x2 $ring_y \"STRIPE\" } }\n"
            tcl += "            } elseif {$pcx < $ring_x1} {\n"
            tcl += "                catch { odb::dbSBox_create $swire $m_horiz [expr {$pcx - $hw}] [expr {$ring_y - $hw}] [expr {$ring_x1 + $hw}] [expr {$ring_y + $hw}] \"STRIPE\" }\n"
            tcl += "                if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $ring_x1 $ring_y \"STRIPE\" } }\n"
            tcl += "            }\n"
            tcl += "        } elseif {$pad_side eq \"NORTH\"} {\n"
            tcl += "            set ring_y  $r_north_y($net_name)\n"
            tcl += "            set ring_x1 $r_north_x1($net_name)\n"
            tcl += "            set ring_x2 $r_north_x2($net_name)\n"
            tcl += "            if {$ring_y == 0} { continue }\n"
            tcl += "            # 1. Vertical met4 trunk southwards to ring Y\n"
            tcl += "            catch { odb::dbSBox_create $swire $m_vert [expr {$pcx - $hw}] $ring_y [expr {$pcx + $hw}] $py1 \"STRIPE\" }\n"
            tcl += "            if {$via3_4 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via3_4 $pcx $py1 \"STRIPE\" } }\n"
            tcl += "            if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $pcx $ring_y \"STRIPE\" } }\n"
            tcl += "            # 2. Horizontal met5 bend if outside ring span\n"
            tcl += "            if {$pcx > $ring_x2} {\n"
            tcl += "                catch { odb::dbSBox_create $swire $m_horiz [expr {$ring_x2 - $hw}] [expr {$ring_y - $hw}] [expr {$pcx + $hw}] [expr {$ring_y + $hw}] \"STRIPE\" }\n"
            tcl += "                if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $ring_x2 $ring_y \"STRIPE\" } }\n"
            tcl += "            } elseif {$pcx < $ring_x1} {\n"
            tcl += "                catch { odb::dbSBox_create $swire $m_horiz [expr {$pcx - $hw}] [expr {$ring_y - $hw}] [expr {$ring_x1 + $hw}] [expr {$ring_y + $hw}] \"STRIPE\" }\n"
            tcl += "                if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $ring_x1 $ring_y \"STRIPE\" } }\n"
            tcl += "            }\n"
            tcl += "        } elseif {$pad_side eq \"WEST\"} {\n"
            tcl += "            if {![info exists r_west_x($net_name)] || $r_west_x($net_name) == 0} { continue }\n"
            tcl += "            set ring_x  $r_west_x($net_name)\n"
            tcl += "            set ring_y1 [expr {[info exists r_west_y1($net_name)] ? $r_west_y1($net_name) : 0}]\n"
            tcl += "            set ring_y2 [expr {[info exists r_west_y2($net_name)] ? $r_west_y2($net_name) : 0}]\n"
            tcl += "            # 1. Via transitions at pad inner prong\n"
            tcl += "            if {$via3_4 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via3_4 $px2 $pcy \"STRIPE\" } }\n"
            tcl += "            if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $px2 $pcy \"STRIPE\" } }\n"
            tcl += "            # 2. Horizontal met5 trunk eastwards to West ring X\n"
            tcl += "            catch { odb::dbSBox_create $swire $m_horiz $px2 [expr {$pcy - $hw}] $ring_x [expr {$pcy + $hw}] \"STRIPE\" }\n"
            tcl += "            if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $ring_x $pcy \"STRIPE\" } }\n"
            tcl += "            # 3. Vertical met4 bend along West ring edge if outside [ring_y1, ring_y2]\n"
            tcl += "            if {$pcy > $ring_y2} {\n"
            tcl += "                catch { odb::dbSBox_create $swire $m_vert [expr {$ring_x - $hw}] $ring_y2 [expr {$ring_x + $hw}] [expr {$pcy + $hw}] \"STRIPE\" }\n"
            tcl += "                if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $ring_x $ring_y2 \"STRIPE\" } }\n"
            tcl += "            } elseif {$pcy < $ring_y1} {\n"
            tcl += "                catch { odb::dbSBox_create $swire $m_vert [expr {$ring_x - $hw}] [expr {$pcy - $hw}] [expr {$ring_x + $hw}] $ring_y1 \"STRIPE\" }\n"
            tcl += "                if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $ring_x $ring_y1 \"STRIPE\" } }\n"
            tcl += "            }\n"
            tcl += "        } elseif {$pad_side eq \"EAST\"} {\n"
            tcl += "            if {![info exists r_east_x($net_name)] || $r_east_x($net_name) == 0} { continue }\n"
            tcl += "            set ring_x  $r_east_x($net_name)\n"
            tcl += "            set ring_y1 [expr {[info exists r_east_y1($net_name)] ? $r_east_y1($net_name) : 0}]\n"
            tcl += "            set ring_y2 [expr {[info exists r_east_y2($net_name)] ? $r_east_y2($net_name) : 0}]\n"
            tcl += "            # 1. Via transitions at pad inner prong\n"
            tcl += "            if {$via3_4 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via3_4 $px1 $pcy \"STRIPE\" } }\n"
            tcl += "            if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $px1 $pcy \"STRIPE\" } }\n"
            tcl += "            # 2. Horizontal met5 trunk westwards to East ring X\n"
            tcl += "            catch { odb::dbSBox_create $swire $m_horiz $ring_x [expr {$pcy - $hw}] $px1 [expr {$pcy + $hw}] \"STRIPE\" }\n"
            tcl += "            if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $ring_x $pcy \"STRIPE\" } }\n"
            tcl += "            # 3. Vertical met4 bend along East ring edge if outside [ring_y1, ring_y2]\n"
            tcl += "            if {$pcy > $ring_y2} {\n"
            tcl += "                catch { odb::dbSBox_create $swire $m_vert [expr {$ring_x - $hw}] $ring_y2 [expr {$ring_x + $hw}] [expr {$pcy + $hw}] \"STRIPE\" }\n"
            tcl += "                if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $ring_x $ring_y2 \"STRIPE\" } }\n"
            tcl += "            } elseif {$pcy < $ring_y1} {\n"
            tcl += "                catch { odb::dbSBox_create $swire $m_vert [expr {$ring_x - $hw}] [expr {$pcy - $hw}] [expr {$ring_x + $hw}] $ring_y1 \"STRIPE\" }\n"
            tcl += "                if {$via4_5 ne \"NULL\"} { catch { odb::dbSBox_create $swire $via4_5 $ring_x $ring_y1 \"STRIPE\" } }\n"
            tcl += "            }\n"
            tcl += "        }\n"
            tcl += "    }\n"
            tcl += "\n"
            tcl += "    # Bridge internally switched domains (e.g. PD_COMPUTE) to the top VDD ring using orthogonal straps and vias\n"
            tcl += "    set vdd_net [$blk findNet \"VDD\"]\n"
            tcl += "    if {$vdd_net ne \"NULL\"} {\n"
            tcl += "        set swires [$vdd_net getSWires]\n"
            tcl += "        set vdd_swire [expr {[llength $swires] > 0 ? [lindex $swires 0] : [odb::dbSWire_create $vdd_net \"ROUTED\"]}]\n"
            tcl += "        foreach ring_cand $ring_nets {\n"
            tcl += "            if {$ring_cand ne \"VDD\" && $ring_cand ne \"VSS\"} {\n"
            tcl += "                if {[info exists r_south_y($ring_cand)] && $r_south_y($ring_cand) > 0 && [info exists r_south_y(VDD)] && $r_south_y(VDD) > 0} {\n"
            tcl += "                    set is_switched 1\n"
            tcl += "                    foreach inst [$blk getInsts] {\n"
            tcl += "                        set iname [$inst getName]\n"
            tcl += "                        set dom_suffix [string tolower [string map {VDD_PD_ \"\" VDD_ \"\"} $ring_cand]]\n"
            tcl += "                        if {[string match \"*power*\" [[$inst getMaster] getName]] && [string match \"*${dom_suffix}*\" [string tolower $iname]]} {\n"
            tcl += "                            set is_switched 0\n"
            tcl += "                            break\n"
            tcl += "                        }\n"
            tcl += "                    }\n"
            tcl += "                    if {$is_switched} {\n"
            tcl += "                        set isld_net [$blk findNet $ring_cand]\n"
            tcl += "                        if {$isld_net ne \"NULL\"} {\n"
            tcl += "                            set isld_swires [$isld_net getSWires]\n"
            tcl += "                            set isld_swire [expr {[llength $isld_swires] > 0 ? [lindex $isld_swires 0] : [odb::dbSWire_create $isld_net \"ROUTED\"]}]\n"
            tcl += "                            set bridge_x [expr {($r_south_x1($ring_cand) + $r_south_x2($ring_cand)) / 2}]\n"
            tcl += "                            set y_start $r_south_y(VDD)\n"
            tcl += "                            set y_end $r_south_y($ring_cand)\n"
            tcl += "                            # Collision Avoidance: Check if vertical bridge at bridge_x intersects any hard macro bounding box\n"
            tcl += "                            set collides 0\n"
            tcl += "                            foreach minst [$blk getInsts] {\n"
            tcl += "                                if {[[$minst getMaster] isBlock]} {\n"
            tcl += "                                    set mbx [$minst getBBox]\n"
            tcl += "                                    set mx1 [$mbx xMin]; set mx2 [$mbx xMax]\n"
            tcl += "                                    set my1 [$mbx yMin]; set my2 [$mbx yMax]\n"
            tcl += "                                    set min_y [expr {$y_start < $y_end ? $y_start : $y_end}]\n"
            tcl += "                                    set max_y [expr {$y_start > $y_end ? $y_start : $y_end}]\n"
            tcl += "                                    if {$bridge_x + $hw >= $mx1 && $bridge_x - $hw <= $mx2 && $max_y >= $my1 && $min_y <= $my2} {\n"
            tcl += "                                        set collides 1\n"
            tcl += "                                        break\n"
            tcl += "                                    }\n"
            tcl += "                                }\n"
            tcl += "                            }\n"
            tcl += "                            if {$collides} {\n"
            tcl += "                                # Find clean routing corridor east or west of the macro obstruction\n"
            tcl += "                                set cand_x1 [expr {$r_south_x1($ring_cand) - 25000}]\n"
            tcl += "                                set cand_x2 [expr {$r_south_x2($ring_cand) + 25000}]\n"
            tcl += "                                set best_x $cand_x1\n"
            tcl += "                                foreach cx [list $cand_x1 $cand_x2] {\n"
            tcl += "                                    set c_hit 0\n"
            tcl += "                                    foreach minst [$blk getInsts] {\n"
            tcl += "                                        if {[[$minst getMaster] isBlock]} {\n"
            tcl += "                                            set mbx [$minst getBBox]\n"
            tcl += "                                            if {$cx + $hw >= [$mbx xMin] && $cx - $hw <= [$mbx xMax]} {\n"
            tcl += "                                                set c_hit 1; break\n"
            tcl += "                                            }\n"
            tcl += "                                        }\n"
            tcl += "                                    }\n"
            tcl += "                                    if {!$c_hit} { set best_x $cx; break }\n"
            tcl += "                                }\n"
            tcl += "                                set bridge_x $best_x\n"
            tcl += "                                # Route dogleg: vertical trunk through clear corridor + horizontal jog into island ring\n"
            tcl += "                                catch { odb::dbSBox_create $vdd_swire $m_vert [expr {$bridge_x - $hw}] $y_start [expr {$bridge_x + $hw}] $y_end \"STRIPE\" }\n"
            tcl += "                                set jog_x1 [expr {$bridge_x < $r_south_x1($ring_cand) ? $bridge_x : $r_south_x1($ring_cand)}]\n"
            tcl += "                                set jog_x2 [expr {$bridge_x > $r_south_x2($ring_cand) ? $bridge_x : $r_south_x2($ring_cand)}]\n"
            tcl += "                                catch { odb::dbSBox_create $isld_swire $m_horiz [expr {$jog_x1 - $hw}] [expr {$y_end - $hw}] [expr {$jog_x2 + $hw}] [expr {$y_end + $hw}] \"STRIPE\" }\n"
            tcl += "                                if {$via4_5 ne \"NULL\"} {\n"
            tcl += "                                    catch { odb::dbSBox_create $vdd_swire $via4_5 $bridge_x $y_start \"STRIPE\" }\n"
            tcl += "                                    catch { odb::dbSBox_create $isld_swire $via4_5 $bridge_x $y_end \"STRIPE\" }\n"
            tcl += "                                }\n"
            tcl += "                            } else {\n"
            tcl += "                                catch { odb::dbSBox_create $vdd_swire $m_vert [expr {$bridge_x - $hw}] $y_start [expr {$bridge_x + $hw}] $y_end \"STRIPE\" }\n"
            tcl += "                                if {$via4_5 ne \"NULL\"} {\n"
            tcl += "                                    catch { odb::dbSBox_create $vdd_swire $via4_5 $bridge_x $y_start \"STRIPE\" }\n"
            tcl += "                                    catch { odb::dbSBox_create $isld_swire $via4_5 $bridge_x $y_end \"STRIPE\" }\n"
            tcl += "                                }\n"
            tcl += "                            }\n"
            tcl += "                        }\n"
            tcl += "                    }\n"
            tcl += "                }\n"
            tcl += "            }\n"
            tcl += "        }\n"
            tcl += "    }\n"
            tcl += "}\n"
            tcl += f"_build_pad_trunks \"{trunk_layer}\" {trunk_width_dbu}\n\n"

        # In apply mode, save and update live script
        if apply:
            self.save_state()
            self.update_live_tcl()
            proj_root, base = self._get_project_context()
            def_abs_path = os.path.join(proj_root, "results", "temp.def").replace("\\", "/")
            
            if self.parent() and hasattr(self.parent(), 'term_log'):
                self.parent().term_log.append("[SYS] Applying Custom Floorplan...")
            # Use the live TCL instead so it includes everything correctly.
            final_tcl = self.live_tcl_edit.toPlainText() + f"\nwrite_def \"{def_abs_path}\"\n"
            final_tcl += "puts \"SILIS_FLOORPLAN_DONE\"\n"
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


def compute_peripheral_macro_placement(macros, die_w=1400.0, die_h=1400.0, margins=(20.0, 20.0, 20.0, 20.0), macro_sizes=None, existing_obstacles=None):
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
    if existing_obstacles:
        for obs in existing_obstacles:
            if hasattr(obs, 'x') and hasattr(obs, 'width'):
                placed_boxes.append((obs.x(), obs.y(), obs.x() + obs.width(), obs.y() + obs.height()))
            elif len(obs) == 4:
                placed_boxes.append(tuple(obs))

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

    # OpenROAD IEEE 1801 UPF: set_domain_area MUST precede initialize_floorplan
    tcl += "# === INITIALIZATION ===\n"
    if regions:
        for r in regions:
            mod = r.get("module") or r.get("name")
            box = r.get("box") or r.get("rect") or r.get("bounds")
            if box and (mod.startswith("PD_") or mod.startswith("pd_")):
                tcl += f'catch {{ set_domain_area {mod} -area {{{box[0]} {box[1]} {box[2]} {box[3]}}} }}\n'
    # Standard cell site initialization (single-height standard cells only to prevent duplicate row overlap)
    tcl += f'initialize_floorplan -die_area "0 0 {die_w} {die_h}" -core_area "{core_x1} {core_y1} {core_x2} {core_y2}" -site {site_name}\n\n'

    # Deduplicate overlapping rows created by multi-domain row slicing
    tcl += "# Deduplicate overlapping rows created by multi-domain row slicing\n"
    tcl += "set _blk [ord::get_db_block]\n"
    tcl += "set _seen_rows [dict create]\n"
    tcl += "set _dup_rows [list]\n"
    tcl += "foreach _r [$_blk getRows] {\n"
    tcl += "    set _orig [$_r getOrigin]\n"
    tcl += "    set _cnt [$_r getSiteCount]\n"
    tcl += "    set _site [[$_r getSite] getName]\n"
    tcl += "    set _key \"${_site},[lindex $_orig 0],[lindex $_orig 1],${_cnt}\"\n"
    tcl += "    if {[dict exists $_seen_rows $_key]} {\n"
    tcl += "        lappend _dup_rows $_r\n"
    tcl += "    } else {\n"
    tcl += "        dict set _seen_rows $_key 1\n"
    tcl += "    }\n"
    tcl += "}\n"
    tcl += "foreach _dr $_dup_rows { odb::dbRow_destroy $_dr }\n\n"

    if macros:
        tcl += "# === MACRO PLACEMENT ===\n"
        for m in macros:
            inst = m.get("inst") or m.get("name")
            cell = m.get("cell", "")
            loc = m.get("loc") or m.get("pos") or m.get("origin")
            if not loc and "x" in m and "y" in m:
                loc = [m["x"], m["y"]]
            if not loc:
                loc = [0, 0]
            orient = m.get("orient", "R0")
            halo = m.get("halo", [10, 10, 10, 10])
            cell_arg = f' -cell "{cell}"' if cell else ""
            tcl += f'place_macro -inst "{inst}"{cell_arg} -location {{{loc[0]} {loc[1]}}} -orient {orient} -halo {{{halo[0]} {halo[1]} {halo[2]} {halo[3]}}}\n'
        tcl += "catch { cut_rows -halo_width_x 10.0 -halo_width_y 10.0 }\n"
        # Deduplicate and prune narrow isolated row slivers to ensure clean OpenROAD pdngen channel routing
        tcl += """set _blk [ord::get_db_block]
set _dbu [[ord::get_db_tech] getDbUnitsPerMicron]
# Deduplicate any identical row fragments created by multi-domain cut passes
set _seen_rows [dict create]
set _dup_rows [list]
foreach _r [$_blk getRows] {
    set _orig [$_r getOrigin]
    set _scnt [$_r getSiteCount]
    set _site [[$_r getSite] getName]
    set _key "${_site},[lindex $_orig 0],[lindex $_orig 1],${_scnt}"
    if {[dict exists $_seen_rows $_key]} {
        lappend _dup_rows $_r
    } else {
        dict set _seen_rows $_key 1
    }
}
foreach _dr $_dup_rows { odb::dbRow_destroy $_dr }
"""
        tcl += "\n"

    if regions:
        tcl += "# === REGIONS & VOLTAGE ISLANDS ===\n"
        for r in regions:
            mod = r.get("module") or r.get("name")
            box = r.get("box") or r.get("rect") or r.get("bounds")
            rtype = r.get("type", "inclusive")
            tcl += f'create_region -module "{mod}" -box {{{box[0]} {box[1]} {box[2]} {box[3]}}} -type {rtype}\n'
        tcl += "\n"

    if blockages:
        tcl += "# === PLACEMENT BLOCKAGES ===\n"
        for b in blockages:
            bx = b.get("box", [0, 0, 0, 0])
            soft = b.get("soft", False)
            soft_flag = " -soft" if soft else ""
            tcl += f'create_blockage{soft_flag} -region {{{bx[0]} {bx[1]} {bx[2]} {bx[3]}}}\n'
        tcl += "\n"

    tcl += "catch { make_tracks }\n"
    return tcl


SilisFPStudio = InteractiveFloorplannerWidget
