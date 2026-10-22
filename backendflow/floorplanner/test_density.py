import sys
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
from silis.backendflow.floorplanner.floorplanner import RegionItem
r1 = RegionItem(0, 0, 10, 10, "A")
r2 = RegionItem(0, 0, 10, 10, "B")
r1.density = 0.4
print(r1.density, r2.density)
assert r1.density == 0.4


