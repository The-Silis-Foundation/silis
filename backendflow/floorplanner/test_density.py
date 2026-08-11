from floorplanner import RegionItem
r1 = RegionItem(0, 0, 10, 10, "A")
r2 = RegionItem(0, 0, 10, 10, "B")
r1.density = 0.4
print(r1.density, r2.density)
