# Silis Backend Studio (`silis --bend`) Architecture & Implementation Plan

## 1. Overview
The goal of `silis --bend` (or `silis --backend`) is to provide a standalone, frontend-independent Physical Design (PD) environment. A physical design engineer can start from scratch or resume an in-flight physical design using structural netlists (`.v`), timing constraints (`.sdc`), and existing databases (`.def`/`.odb`) while independently configuring and assigning all PDK tech files, physical LEFs, Liberty timing models, and signoff decks.

---

## 2. UI & Panel Architecture (Plugged into `BackendWidget`)

The user interface directly extends and integrates into the existing `BackendWidget` (`silis/core/backendflow/flow/backendflow.py`), preserving its established geometry, visual hierarchy, and styling:

```
+------------------------------------------------------------------------------------------------------------+
| Top Ribbon: [ Init v ] [ Floorplan v ] [ Tapcells ] [ PDN v ] [ IO Pins v ] [ Place ] [ CTS v ] [ Route v ]|
+---------------+--------------------------------------------------------------+-----------------------------+
| Left Panel    | Center Panel (viz_tabs)                                      | Right Panel (Collapsible)   |
| (Existing DEF |                                                              | Physical Design Setup       |
|  Control Bar) |  FastSiliconPeeker (2D Native Layout Viewer)                 | [ Collapse Panel > ]        |
| ------------- |  Clock Tree Viewer                                           | --------------------------- |
| DEF Layers:   |                                                              | Design Handoff:             |
| [x] Cells     |                                                              |  Top Module: [ uart_tx    ] |
| [x] Macros    |                                                              |  Netlist:    [ ... browse ] |
| [x] Tapcells  |                                                              |  SDC:        [ ... browse ] |
| [x] Pins      |                                                              |  DEF / ODB:  [ ... browse ] |
| [ ] Nets      |                                                              |  UPF / CPF:  [ ... browse ] |
| [x] Power     |                                                              |  Pin Order:  [ ... browse ] |
|               |                                                              |                             |
| Launchers:    |                                                              | PDK Deck Configuration:     |
| [ OpenROAD  ] |                                                              |  Tech LEF:   [ ... browse ] |
| [ Magic     ] |                                                              |  Cell LEFs:  [ + Add / Edit]|
| [ Refresh   ] |                                                              |  Macro LEFs: [ + Add / Edit]|
|               |                                                              |  Timing Lib: [ + Add / Edit]|
|               |                                                              |  Extraction: [ ... browse ] |
|               |                                                              |  GDS Stream: [ + Add / Edit]|
|               |                                                              |  DRC/LVS:    [ Tech / SPICE]|
|               |                                                              |                             |
|               |                                                              | [ Apply & Run Init Flow ]   |
+---------------+--------------------------------------------------------------+-----------------------------+
| Bottom Panel: Interactive OpenROAD Terminal & Step Execution Log Console                                   |
+------------------------------------------------------------------------------------------------------------+
```

### Key Layout Details:
1. **Left Panel (Existing)**: Retained at fixed 140px on the left side. Contains DEF layer toggles (`Cells`, `Macros`, `Tapcells`, `Pins`, `Nets`, `Power`), tool launchers (`OpenROAD`, `Magic`), and `Refresh View`.
2. **Center Panel (Existing)**: Contains `viz_tabs` with `FastSiliconPeeker` (native C++ accelerated layout viewer) and `Clock Tree` viewer.
3. **Right Panel (New & Collapsible)**:
   - Dedicated Physical Design Setup panel for design handoff files and manual PDK decks.
   - Expandable/collapsible via a toggle button or header action.
   - When collapsed, the central layout canvas smoothly expands to occupy the available window width.
4. **Bottom Panel (Existing)**: Live OpenROAD process output and interactive TCL command terminal.

---

## 3. Physical Design Inputs & PDK Artifacts

### A. Design Handoff Inputs
- **Top Module Name**: Logical top-level design name.
- **Structural Netlist (`.v` / `.vg`)**: PDK-mapped gate-level netlist (from Yosys, Design Compiler, Genus, etc.).
- **Timing Constraints (`.sdc`)**: SDC 2.1 clocks, I/O delays, false paths, and multicycle paths.
- **Existing Layout Database (`.def` / `.odb`)** *(Optional)*: Pre-existing floorplan, placed, or routed database to resume.
- **Power Intent (`.upf` / `.cpf`)** *(Optional)*: Multi-voltage domain definitions, power switches, isolation cells, and level shifters.
- **Pin / Pad Order List (`.cfg` / `.tcl`)** *(Optional)*: Die edge assignments, layer constraints, and pin ordering.

### B. PDK Configuration Deck (Manual Selection Mode)
- **Technology LEF (`.tlef`)**: Manufacturing grid, metal pitches, tracks, and site definitions.
- **Standard Cell LEFs (`.lef`)**: Core standard cells and I/O cell abstract views.
- **Macro LEFs (`.lef`)**: Hard macro abstracts (SRAMs, PLLs, analog IP).
- **Liberty Timing Libraries (`.lib`)**:
  - Early / Fast corner (`ff`) for hold verification.
  - Late / Slow corner (`ss`) for setup verification.
  - Typical corner (`tt`) for placement and power estimation.
- **Extraction Rules (`rules.openrcx`)**: Technology rules for wire parasitic RC extraction.
- **Tapeout & Signoff Decks**:
  - Standard cell GDS streams (`.gds`) for tapeout stream merge.
  - Magic tech file (`.tech`) for DRC verification.
  - Transistor SPICE netlists (`.spice` / `.cdl`) for Netgen LVS.

---

## 4. Project Registry & Persistence (`backend_only` project type)

Projects created or configured in this mode are registered in `.silisproj` with `project_type: "backend_only"`:

```json
{
  "project_name": "uart_transceiver_backend",
  "project_type": "backend_only",
  "version": "1.0",
  "design": {
    "top_module": "uart_transceiver",
    "netlist": "netlist/uart_transceiver_netlist.v",
    "sdc": "constr/uart_transceiver.sdc",
    "initial_def": "results/floorplanned.def",
    "upf": "",
    "io_pin_cfg": ""
  },
  "pdk": {
    "mode": "manual",
    "tech_lef": "pdk/sky130_fd_sc_hd.tlef",
    "std_cell_lefs": [
      "pdk/sky130_fd_sc_hd.lef"
    ],
    "macro_lefs": [],
    "liberty_timing": {
      "typical": "pdk/sky130_fd_sc_hd__tt_025C_1v80.lib",
      "early_fast": "pdk/sky130_fd_sc_hd__ff_n40C_1v95.lib",
      "late_slow": "pdk/sky130_fd_sc_hd__ss_100C_1v60.lib"
    },
    "extraction_rules": "pdk/sky130A.openrcx",
    "gds_files": [
      "pdk/sky130_fd_sc_hd.gds"
    ],
    "drc_tech": "pdk/sky130A.tech",
    "lvs_spice": "pdk/sky130_fd_sc_hd.spice"
  }
}
```

---

## 5. Execution & CLI Integration

1. **Command Line Execution**:
   - `silis --bend` or `silis --backend`: Launches the standalone Backend Studio.
   - `silis --bend <file_or_dir>`: If a directory, DEF file, or netlist file is provided, it is immediately bound to the session.
2. **CLI Parser (`silis/core/cli/main.py`)**:
   - Register `--bend` and `--backend` flags.
3. **GUI Orchestrator (`silis/silis.py`)**:
   - Detect `--bend` mode on startup.
   - Launch `BackendStudioWindow` (or instantiate `BackendWidget` as central widget directly) without constructing frontend editor tabs, testbench explorers, or synthesis pipelines.
