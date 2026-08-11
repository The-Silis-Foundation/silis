import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRectF
import floorplanner

app = QApplication(sys.argv)
scene = floorplanner.QGraphicsScene()
ri = floorplanner.RegionItem(0, 0, 100, 100, "core/alu", False, 0.6, QRectF(0,0,1000,1000))
scene.addItem(ri)
print("Handles before select:", [h.isVisible() for h in ri.handles.values()])
ri.setSelected(True)
print("Handles after select:", [h.isVisible() for h in ri.handles.values()])
