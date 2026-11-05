# Chapter 5: Advanced Floorplanning, Macros & Regions

Floorplanning defines the boundary between RTL design and physical silicon. Silis provides automated macro placement engines and concise, ergonomic region controls.

---

## 1. Automated Macro Placer Engines

When invoking `pipe.floorplan(auto_macro_placer=...)`, Silis supports three distinct algorithmic methodologies:

```python
pipe.floorplan(
    die_area=[0, 0, 1400, 1400],
    core_margin=20.0,
    auto_macro_placer="peripheral"  # "peripheral" | "hierarchical" | "openroad"
)
```

### 1. `"peripheral"` (Silis Geometric Fast Solver)
- **Principle**: Evaluates the aspect ratios and pin boundaries of all discovered macros, packing them into periphery corners facing external I/O rings.
- **Advantage**: Instant runtime (< 10 ms), leaving an open, contiguous center core cavity for high-density standard cell placement and minimal congestion.

### 2. `"hierarchical"` (OpenROAD RTL-MP)
- **Principle**: Traverses the RTL module hierarchy tree. Clusters standard cells with the macros they interface with using sequence pairs and simulated annealing.
- **Advantage**: Best for multi-subsystem SoCs (CPUs, DSPs, bus crossbars) where minimizing logic-to-macro wirelength is paramount.

### 3. `"openroad"` (Analytical TritonMacroPlace)
- **Principle**: Treats macros and cells as positively charged particles in an electrostatic potential field while nets act as elastic attraction springs (e-Place engine).
- **Advantage**: Global analytical wirelength optimization using Nesterov's accelerated gradient descent.

---

## 2. Concise Pythonic Ergonomic Helpers

Silis eliminates verbose dictionary boilerplate with clean helper one-liners:

### Manual Macro Placement with Scalar Halos
```python
# Automatically expands scalar halo (10.0) to all 4 edges [10, 10, 10, 10]
macro = pipe.place_macro("u_sram_0", at=(100, 100), orient="MY", halo=10.0)
```

### Auto-Sizing Standard Cell Fences
```python
# Automatically calculates optimal width & height from cell area and target density
fence = pipe.add_fence("u_alu", origin=(300, 700), density=0.50)
```

### Soft and Hard Placement Blockages
```python
# Creates routing-safe placement obstruction
blockage = pipe.add_blockage((500, 500, 800, 800), soft=True)
```

---

## 3. Auto Region Placer & Shaper

In the Floorplanner GUI and SDK, regions can be automatically placed and shaped:
- **Auto Shaper**: Calculates bounding box dimensions using $W = \sqrt{\frac{A_{\text{cell}}}{\text{density}} \times AR}$ and snaps coordinates to standard cell row heights (`2.72` $\mu$m on Sky130).
- **Hierarchical Placer**: Detects free core cavities, clusters sibling modules together, and assigns regions without overlapping neighboring macros or blockages.

---

## 4. Multi-Voltage Power Intent & Domain Site Rows (GUI & SDK)

Silis provides unified user control over IEEE 1801 multi-voltage power domains across both the graphical interface and the Python SDK.

### 4.1 Interactive GUI Controls (`InteractiveFloorplannerWidget`)
In the **Power & PDN** inspector tab:
- **`table_domain_supplies`**: For every defined power domain (e.g. `PD_TOP`, `PD_NPU`, `PD_CRYPTO`), the table provides 6 interactive columns:
  1. **Domain Name**: Symbolic UPF domain identifier.
  2. **Primary Supply Net**: Name of the domain VDD rail.
  3. **Voltage (V)**: Nominal voltage setting (e.g. `1.800 V`, `0.950 V`).
  4. **Ground Net**: VSS reference rail.
  5. **Row Site**: Dropdown allowing the designer to choose between:
     - `unithd (2.72 µm)`: Standard single-height logic rows.
     - `unithddbl (5.44 µm)`: Double-height rows required for physical power switch cells.
  6. **Physical Switch**: Checkbox toggle (`Insert Switch`) opting into downstream physical cell mapping (`map_power_switch`).

### 4.2 Python SDK Parity (`silis.PowerDomain`)
The GUI interacts with the exact same underlying methods available to headless Python scripts:
```python
pwr_net = pipe.project.power_network
npu_domain = pwr_net.get_domain("PD_NPU")

# Configure row site height for the domain
npu_domain.set_row_site("unithd")  # or "unithddbl"

# Configure physical power switch cell mapping
npu_domain.enable_physical_power_switches(False)
```
