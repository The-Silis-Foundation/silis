# Chapter 2: The Silis Python SDK Reference

The `silis` Python SDK provides a fluent, programmatic interface to orchestrate entire digital ASIC flows directly in Python.

---

## 1. Importing the SDK

```python
import silis

# Core Classes
from silis import Pipeline, Project, SignoffReport, DRCReport
from silis.sdk.sdc import SDCBuilder

# Layout & Inspection Tools
from silis import view_layout, view_gds3d, view_waveforms, view_schematic
```

---

## 2. `silis.Project` API Reference

`Project` manages project directories, manifests (`silis.silisproj`), netlists, and area estimations.

### Constructor
```python
project = silis.Project("sram_soc_system", project_dir="/path/to/project", pdk="sky130")
```

### Methods
- `project.get_sizes(refresh=False) -> dict`: Parses `{top_module}_sizes.json` returning standard cell area, cell count, and macro instance mappings.
- `project.get_module_area(module="core") -> float`: Returns the total standard cell area in $\mu\text{m}^2$ for the given hierarchical module.
- `project.get_required_area(module="core", target_density=0.40) -> float`: Calculates the physical area required to achieve the requested utilization density.
- `project.suggest_box(module="core", origin=(0, 0), target_density=0.40, aspect_ratio=1.0) -> [x1, y1, x2, y2]`: Mathematically calculates a PDK grid-snapped bounding box.

---

## 3. `silis.Pipeline` API Reference

`Pipeline` executes each stage of the physical implementation flow sequentially or selectively.

### Flow Execution Methods
- `pipe.init()`: Generates initial directories, builds synthesis scripts, and extracts design sizing metrics.
- `pipe.synth(dft=False, scan_in="scan_in", scan_out="scan_out", scan_en="scan_en") -> bool`: Executes Yosys logic synthesis and optional scan insertion.
- `pipe.floorplan(die_area, core_margin, auto_macro_placer=None, macros=None, regions=None, blockages=None) -> bool`:
  - `auto_macro_placer`: `"peripheral"` (Silis fast solver), `"hierarchical"` (OpenROAD RTL-MP), or `"openroad"` (TritonMacroPlace).
  - `macros`: List of placed macros (via `pipe.place_macro(...)`).
  - `regions`: List of region/fence dictionaries (via `pipe.add_fence(...)`).
  - `blockages`: Placement obstruction regions.
- `pipe.place(density=0.60, pad=4) -> bool`: Runs global and detailed standard cell placement.
- `pipe.cts() -> bool`: Synthesizes clock trees using TritonCTS.
- `pipe.route() -> bool`: Executes global and detailed routing with TritonRoute.
- `pipe.gds() -> bool`: Merges standard cells, macros, and routing into final tapeout GDSII via Magic.
- `pipe.signoff() -> SignoffReport`: Runs STA timing, parasitics extraction, and DRC signoff verification.

---

## 4. `SDCBuilder` API Reference

Instead of writing fragile `.sdc` files by hand, `pipe.sdc` provides a fluent builder:

```python
pipe.sdc \
    .clock("clk", period=10.0, uncertainty=0.2) \
    .inputs(delay=2.0, port="rst_n", clock="clk") \
    .outputs(delay=1.5, port="data*", clock="clk") \
    .false_path(from_pin="rst_n")
```

- `.clock(name, period, uncertainty=0.0)`: Defines a primary system clock.
- `.inputs(delay, port, clock)`: Constrains input arrival times. Wildcards supported (`data*`).
- `.outputs(delay, port, clock)`: Constrains output departure times.
- `.false_path(from_pin=None, to_pin=None)`: Defines timing exceptions.
- `.generate() -> str`: Emits standard Synopsys Design Constraints syntax.

---

## 5. Visual Layout & Inspection Helpers

```python
# Open high-speed 2D DEF layout viewer
p = silis.view_layout("results/temp.def", title="Core PnR Layout", detach=True)

# Launch 3D GDS cross-section viewer
silis.view_gds3d("results/design.gds", tech="sky130")

# Open VCD waveform inspector
silis.view_waveforms("simulation/tb.vcd")
```
