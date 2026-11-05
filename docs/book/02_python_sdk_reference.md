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
- `pipe.tapcells() -> bool`: Synthesizes endcap and tapcell grid for standard cell latchup prevention.
- `pipe.pdn() -> bool`: Synthesizes dual-layer orthogonal power distribution network (M4/M5) and multi-voltage domain rings.
- `pipe.iopins(mode="ring", pad_strategy="staggered") -> bool`: Synthesizes peripheral I/O pad ring or block-level boundary pins.
- `pipe.place(density=0.60, pad_left=2, pad_right=2) -> bool`: Runs global and detailed standard cell placement with automatic orphan tapcell purging to eliminate `DPL-0006` site alignment errors.
- `pipe.cts(root_buf=None, buf_list=None, sink_clustering=True) -> bool`: Synthesizes balanced clock trees across macros and registers using TritonCTS.
- `pipe.route(congestion_iterations=60, allow_congestion=True, bottom_layer="met1", top_layer="met5") -> bool`: Executes FastRoute global routing with `-allow_congestion` handoff and TritonRoute detailed routing.
- `pipe.fill() -> bool`: Inserts standard cell decap and metal density fill tiles.
- `pipe.gds() -> bool`: Merges standard cells, macros, and routing into final tapeout GDSII via Magic.
- `pipe.signoff() -> SignoffReport`: Runs STA timing, parasitics extraction, and DRC signoff verification.

### Multi-Voltage Power Intent (`silis.PowerDomain`)
- `domain.set_row_site(site_type="unithd")`: Configures single-height logic rows (`unithd`, $2.72\,\mu\text{m}$) or double-height switch rows (`unithddbl`, $5.44\,\mu\text{m}$).
- `domain.enable_physical_power_switches(enabled=False)`: Toggles between architectural virtual power gating and physical `POWER_SWITCH` cell insertion in OpenROAD.
- `domain.set_primary_voltage(voltage: float)`: Declares domain supply net voltage with IEEE 1801 assertion checks.
- `domain.add_isolation_rule(clamp_value=0, applies_to="outputs")`: Enforces output net clamping on gated power domains.

### Physical Optimization & Diagnostic Methods
- `pipe.get_heatmap(heatmap_type="ir_drop", grid_size=(160, 160), def_path=None) -> dict`: Solves the anisotropic 2D Poisson conductance system (or accumulates congestion/density) and returns `{ "grid": np.ndarray, "raw_max": float, "peak_coord_um": (x, y), "die_bbox_um": [...] }`.
- `pipe.compute_minimum_die_for_pads(num_pads, core_w, core_h, strategy="uniform", pad_margin=250.0) -> dict`: Computes PDK-legal perimeter pad capacity and minimum die dimensions.
- `pipe.optimize_die(target_density=0.50, padring=True, strategy="uniform") -> dict`: Derives core dimensions from standard cell area and sizes the die for pad rings.
- `pipe.apply_clock_ndr(rule_name="2w_2s", min_layer="met3", max_layer="met5") -> bool`: Configures Non-Default Routing width and spacing rules for clock trees.
- `pipe.repair_clock_buffers() -> bool`: Balances clock inverter and buffer chains in OpenROAD.
- `pipe.repair_antennas(iterations=3, diode_cell=None) -> bool`: Inserts antenna diodes to protect transistor gates from plasma charging.
- `pipe.save_checkpoint(tag="stage") -> str`: Saves current OpenDB runtime and DEF snapshot to `results/{tag}.odb` and `results/{tag}.def`.
- `pipe.load_checkpoint(tag="stage") -> bool`: Restores a previously saved database checkpoint without rerunning prior stages.

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
# Open high-speed 2D DEF layout viewer with optional heatmap overlay and rulers
p = silis.view_layout(
    "results/temp.def",
    title="Core PnR Layout",
    heatmap="ir_drop",       # Options: "ir_drop", "congestion", "density", "power_density"
    show_rulers=True,
    detach=True
)

# Launch 3D GDS cross-section viewer
silis.view_gds3d("results/design.gds", tech="sky130")

# Open VCD waveform inspector
silis.view_waveforms("simulation/tb.vcd")
```
