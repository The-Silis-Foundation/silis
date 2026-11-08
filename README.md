<div align="center">

<pre>
███████╗ ██╗ ██╗      ██╗ ███████╗
██╔════╝ ██║ ██║      ██║ ██╔════╝
███████╗ ██║ ██║      ██║ ███████╗
╚════██║ ██║ ██║      ██║ ╚════██║
███████║ ██║ ███████╗ ██║ ███████║
╚══════╝ ╚═╝ ╚══════╝ ╚═╝ ╚══════╝
</pre>

# SILIS — Silicon Scaffold
### Production End-to-End RTL-to-GDSII ASIC Design Studio: GUI, CLI & Python SDK

<h4>
  <a href="#overview">Overview</a>
  ·
  <a href="#end-to-end-rtl-to-gdsii-pipeline">RTL-to-GDSII Pipeline</a>
  ·
  <a href="#siliconcompiler-vendoring--co-processor-bridge">SiliconCompiler Bridge</a>
  ·
  <a href="#polyglot-frontend-and-formal-verification">Polyglot Frontend</a>
  ·
  <a href="#floorplanning-and-multi-voltage-power-intent">Floorplanning & UPF</a>
  ·
  <a href="#native-c-acceleration-engines">C++ Engines</a>
  ·
  <a href="#technology-support--ssaforge">PDK & SSAForge</a>
  ·
  <a href="#quick-start-python-sdk">Quick Start</a>
  ·
  <a href="#pre-release-packages">Downloads</a>
  ·
  <a href="#documentation-manual">Documentation</a>
</h4>

<p>
  <img alt="License" src="https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge&logo=gnu&logoColor=white">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Linux-lightgrey.svg?style=for-the-badge&logo=linux&logoColor=white">
  <img alt="Language" src="https://img.shields.io/badge/Language-Python%203.12%20%7C%20C%2B%2B17-4169E1.svg?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Release" src="https://img.shields.io/badge/Release-v0.1.0--pre-orange.svg?style=for-the-badge">
</p>

<br>

<img src="docs/images/screenshots/frontend.jpeg" alt="Silis End-to-End RTL to GDSII EDA Studio Interface" width="100%">

</div>

---

## Overview

**Silis (Silicon Scaffold)** is a unified, end-to-end digital ASIC design studio that takes digital integrated circuits all the way from high-level hardware description language (RTL) sources to tapeout-ready physical GDSII mask layouts and foundry signoff verification.

Silicon design has historically suffered from acute fragmentation: engineers jump between disconnected command-line compilers, disparate configuration schemas, and isolated layout viewers. Silis eliminates this divide by orchestrating industry-standard open-source EDA engines—including **SiliconCompiler**, **OpenROAD**, **Yosys**, **Magic VLSI**, **Netgen LVS**, **SymbiYosys**, **GHDL**, and **Verilator**—into a single, mathematically verified physical design platform.

Silis delivers this complete flow across three synchronized operational modalities:
1. **Interactive Visual CAD (SilisIDE)**: A pure native Qt6 desktop studio featuring hardware-accelerated OpenGL DEF inspection (`SiliconPeeker`), OpenROAD visual parity (`LayerViewerPanel`), gate-level schematic drawers, Intel ROHD-powered waveform viewers (`SignalPeeker`), and real-time congestion analytics.
2. **The Silis Python SDK (`silis.*`)**: A strongly typed, object-oriented physical design API (`SilisProject`, `Pipeline`, `Floorplan`, `PowerNetwork`, `TimingGraph`, `Layout`, `SDCBuilder`) providing complete programmatic flow automation with 100% GUI parity.
3. **Automated CLI Tooling (`silis-flow`, `silis-project`)**: Non-interactive command-line utilities and batch execution runners (`HeadlessASICRunner`) designed for compute clusters and continuous integration pipelines.

---

## End-to-End RTL-to-GDSII Pipeline

Silis unifies every phase of silicon implementation into a coherent, deterministic dataflow:

```
+-----------------------------------------------------------------------------------+
|                            FRONTEND: RTL & CONSTRAINTS                            |
|    SystemVerilog / Verilog / VHDL / C++ HLS  +  IEEE 1801 UPF  +  IEEE 1497 SDC   |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        SYNTHESIS & FORMAL VERIFICATION                            |
|       Yosys Logic Synthesis  |  SymbiYosys Formal Check  |  Gate-Level Netlist    |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                         FLOORPLAN & MULTI-VOLTAGE INTENT                          |
|    Core/Die Legalization  |  Macro Placement (RTL-MP / Corner)  |  UPF Level Shift|
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        POWER DISTRIBUTION NETWORK (PDN)                           |
|        Dual-Layer Orthogonal Grid  |  Power Switches  |  Static IR Drop Check     |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                           PHYSICAL IMPLEMENTATION                                 |
|      Global Placement (RePlAce)  |  CTS (TritonCTS)  |  Detailed Route (Triton)   |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                              SIGNOFF & MASK STREAM                                |
|    OpenSTA Timing  |  Magic / KLayout DRC  |  Netgen LVS  |  Final GDSII Stream   |
+-----------------------------------------------------------------------------------+
```

---

## SiliconCompiler Vendoring & Co-Processor Bridge

Silis vendors and deeply integrates **SiliconCompiler** (`silis/third-party/siliconcompiler/`), providing zero-configuration co-processor bridging between SiliconCompiler design manifests and Silis pipelines via `silis.sc`.

### Bi-Directional Handoffs (`silis.from_sc` & `silis.to_sc`)
Defined in `silis.core.sdk.sc_bridge`, Silis provides native, lossless translation between SC chips and Silis pipelines:

- **Ingesting from SiliconCompiler (`silis.from_sc(chip)`)**:
  - **PDK Schema Adaptation**: Automatically maps SiliconCompiler PDK names (`skywater130`, `gf180mcu`, `ihp130`, `asap7`, `freepdk45`) to Silis `SSAForge` technology definitions and resolves technology LEF and Liberty paths.
  - **Manifest & Fileset Harvesting**: Traverses modern SC filesets (`rtl`, `verilog`, `sv`, `vhdl`, `macro`, `lef`, `lib`, `sdc`) as well as legacy manifest keys.
  - **Timing Constraint Translation**: Ingests clock frequencies, pin delays, and jitter models via `SDCBuilder.from_sc_chip(chip)` directly into an in-memory SDC timing graph.
  - **Checkpoint Synchronization**: Deploys `SilisDirectoryAdapter` to locate the latest physical layout DEF checkpoint across SC task directories (`detailedroute`, `route`, `cts`, `detailedplace`, `floorplan`) and imports it directly into the active Silis workspace.

- **Exporting to SiliconCompiler (`silis.to_sc(pipe)`)**:
  - Hydrates an initialized `siliconcompiler.ASIC` instance with the active design parameters.
  - Serializes in-memory SDC constraints and RTL source trees back to SC manifest filesets.
  - Stages legalized, DRC-clean floorplan DEFs directly into SiliconCompiler step workdirs (e.g. `floorplan/outputs/<design>.def`) for downstream pipeline execution.

---

## Polyglot Frontend and Formal Verification

Silis natively ingests, translates, and verifies heterogeneous digital hardware representations:

- **Polyglot RTL Lowering**:
  - **SystemVerilog (IEEE 1800-2017)**: Lowered via bundled `sv2v` into synthesizable Verilog-2005 (handling interfaces, structs, packages, typedefs, and generate blocks).
  - **VHDL (IEEE 1076-1993 / 2008)**: Lowered via GHDL with Synopsys package support (`-fsynopsys`) and explicit latch preservation.
  - **C/C++ High-Level Synthesis (HLS)**: Algorithmic blocks compiled into cycle-accurate synthesizable Verilog via Bambu HLS.
- **Cycle-Accurate Simulation**:
  - Multithreaded compilation and execution via bundled **Verilator** with native timing, coverage analysis, and direct UVM 1.2 package linking (`uvm_pkg.sv`, `uvm_dpi.cc`).
  - Fallback functional simulation via Icarus Verilog (`iverilog` / `vvp`).
- **Interactive Waveform Peeker (`SignalPeeker`)**:
  - Hardware-accelerated waveform inspection powered by Intel's ROHD Wave Viewer running over a native `QWebEngineView`, featuring hierarchical signal navigation, transition jumping, bus radix formatting, and time markers.
- **Formal Verification (`pipe.formal()`)**:
  - Integrated bounded model checking (BMC) and k-induction proofs wrapping **SymbiYosys (SBY)** with configurable solver backends (`smtbmc`, `yices`, `z3`, `boolector`).

---

## Floorplanning and Multi-Voltage Power Intent

### Declarative Floorplan Synthesis (FPS) & Strict Legalization
Silis floorplanning is governed by strict semiconductor tapeout invariants:
- **Manufacturing Grid Invariance**: Every spatial coordinate, width, height, and margin is quantized to the technology manufacturing grid ($g = 0.005\ \mu\text{m}$ for SkyWater 130nm / 5 DBU).
- **Site Row Snapping**: Standard cell and macro $y$-origins snap strictly to standard cell site rows ($y = k \times 2.72\ \mu\text{m}$ for `sky130_fd_sc_hd`).
- **Multi-Mode Macro Placement**:
  - **Peripheral Boundary Solver**: Places memory macros across the four die corners with terminals facing inward toward the core cavity, accompanied by perimeter walking with guaranteed halo keepouts.
  - **RTL-MP & TritonMacroPlace**: Hierarchical clustering, sequence-pair simulated annealing, and electrostatic wirelength-weighted placement via OpenROAD engines.
- **Fences & Soft Keepouts**: Programmatic definition of exclusive voltage fences and regional blockages.

### IEEE 1801 Multi-Voltage Power Intent (UPF 3.0)
- **UPF Normalization Shim**: Automatically adapts industry-standard UPF commands to OpenROAD subsets, enforcing idempotency to prevent duplicate domain faults (`[ERROR UPF-0019]`), translating `-include_scope` to `-elements`, and mapping power switches to physical cell masters.
- **Level Shifter & Isolation Rules**: Formal verification ensures all cross-domain nets crossing a potential gradient ($|V_1 - V_2| > 0.05\text{V}$) declare level shifters, and power-gated domain outputs clamp via isolation rules.
- **PDN & Static IR Drop Physics**: Dual-layer orthogonal power meshes (`met4` vertical trunks, `met5` horizontal straps) with pre-route special net promotion and static IR drop signoff via `::psm` ($\le 5\%\ V_{\text{nominal}}$).

---

## Native C++ Acceleration Engines

To eliminate Python GUI latency on multi-million instance netlists, Silis implements native compiled C++ modules:

| Engine | Location | Role & Performance Profile |
| :--- | :--- | :--- |
| **`silis_def_viewer`** | `core/backendflow/def_viewer_cpp/` | Embedded X11 window (`QWindow.fromWinId`) for GPU-accelerated DEF rendering. |
| **`FastSiliconPeeker`** | `core/backendflow/siliconpeeker/` | Zero-overhead C++ ingest of standard cell coordinates (`std_coords_flat`), spatial quadtrees, and 2D Poisson conductance heatmaps. |
| **`schematic_engine`** | `core/schematicviewer/` | Native C++ logic netlist parser and layout generator interfacing with WebEngine and DigitalJS/ELK. |
| **`fast_layout_viewer`** | `core/backendflow/fast_viewer/` | Hardware-accelerated GDS/DEF geometry peeker. |
| **`VSCodeTerminalWidget`** | `core/terminal/` | Native pseudoterminal (PTY) emulation for seamless in-app terminal operations. |

---

## Technology Support & SSAForge

Silis decouples physical design algorithms from foundry-specific PDK conventions through **SSAForge (Silis Standard Aliases)** (`silis.core.pdkmanagers.pdk.manager`):

- **Technology-Decoupled Aliasing**: Maps canonical logical functions (`tap_cell`, `cts_root`, `cts_leaf`, `tie_hi`, `tie_lo`, `driver`, `min_layer`, `max_layer`, `site`) to foundry cell masters.
- **Supported Technology Nodes**:
  - **SkyWater 130nm** (`sky130_fd_sc_hd`, `unithd` site, 2.72 $\mu\text{m}$ pitch)
  - **GlobalFoundries 180nm MCU** (`gf180mcu_fd_sc_mcu9t5v0` / `7t5v0`)
  - **IHP 130nm BiCMOS** (`ihp130_sg13g2`)
  - **ASAP7 7nm FinFET** (`asap7`)
  - **FreePDK45** (`FreePDK45`)
- **Volare PDK Management**: Embedded Volare interface for automatic downloading, version pinning, and switching of foundry PDK builds.

---

## Core Architectural Pillars

### The Parity Law: Zero GUI-SDK Deviance
Silis enforces strict parity: *The GUI is a presentation shell over the Python SDK.* Every interactive gesture on canvas—such as moving a macro, sizing a fence, running synthesis, or routing a power mesh—invokes the identical SDK class method called by batch scripts. This guarantees that any physical state achieved interactively can be reproduced in a headless 5-line Python script for continuous integration.

### Downstream Data Integrity & Atomic Emission
Downstream engines execute Silis instructions verbatim. All OpenROAD TCL scripts, UPF manifests, and DEF files are generated defensively and written to disk transactionally (`.tmp` file followed by an atomic `os.replace`), preventing partial writes or corrupted runs.

---

## Pre-Release Packages

Standalone release deliverables are published on [GitHub Releases](https://github.com/The-Silis-Foundation/silis/releases/tag/v0.1.0-pre):

- **Standalone Linux Package**: [`Silis-x86_64.AppImage`](https://github.com/The-Silis-Foundation/silis/releases/download/v0.1.0-pre/Silis-x86_64.AppImage) (Self-contained Linux executable bundling Python 3.12, Qt6 runtime, and SkyWater 130nm technology resources).
- **Differential Update Manifest**: [`Silis-x86_64.AppImage.zsync`](https://github.com/The-Silis-Foundation/silis/releases/download/v0.1.0-pre/Silis-x86_64.AppImage.zsync) (Bandwidth-efficient incremental updates via Zsync).

```bash
# Make executable and launch immediately on Linux:
chmod +x Silis-x86_64.AppImage
./Silis-x86_64.AppImage
```

---

## Quick Start (Python SDK)

Execute a complete end-to-end RTL-to-GDSII pipeline from Python:

```python
import silis

# 1. Initialize Pipeline with RTL source and target PDK
pipe = silis.Pipeline("sram_soc_system", pdk="sky130")
pipe.add_source("rtl/sram_soc_top.v")
pipe.add_source("rtl/alu.v")

# 2. Logic Synthesis & Technology Mapping (Yosys)
pipe.synth(top="sram_soc_top")

# 3. In-Memory Timing Constraints (IEEE 1497 SDC)
pipe.sdc.clock("clk", period=10.0, uncertainty=0.2) \
        .inputs(delay=2.0, port="rst_n") \
        .outputs(delay=1.5, port="data*")

# 4. Floorplan with Auto Macro Placer & Voltage Fences
pipe.floorplan(
    die_area=[0, 0, 1400, 1400],
    core_margin=20.0,
    auto_macro_placer="peripheral",
    regions=[
        pipe.add_fence("u_alu", origin=(300, 700), density=0.50)
    ]
)

# 5. Standard Cell Placement, CTS & Routing
pipe.place()
pipe.cts()
pipe.route()

# 6. Physical Verification & Signoff (DRC/LVS/Timing)
report = pipe.signoff()
report.print_summary()

# 7. Final GDSII Stream-out & Inspection
pipe.gds()
silis.view_layout("results/temp.def", title="SRAM SoC Signoff Layout")
```

### SiliconCompiler Co-Processing Example

```python
import silis
import siliconcompiler as sc

# 1. Create a SiliconCompiler chip object
chip = sc.Chip("heartbeat")
chip.input("heartbeat.v")
chip.set("option", "pdk", "skywater130")

# 2. Handoff to Silis for interactive floorplanning & UPF power intent
pipe = silis.from_sc(chip)
pipe.floorplan(die_area=[0, 0, 1000, 1000], core_margin=15.0)

# 3. Hand back to SiliconCompiler for downstream compilation
chip = silis.to_sc(pipe)
chip.run()
```

---

## Documentation Manual

The indexed engineering manual is located in [`silis/docs/`](docs/INDEX.md):

| Document | Topic | Description |
| :--- | :--- | :--- |
| **GUI User Manual** | [GUI_USER_MANUAL.md](docs/GUI_USER_MANUAL.md) | Comprehensive interactive IDE walkthrough with annotated dark mode screenshots |
| **Architecture Decision Records** | [ADR_0001](docs/architecture/ADR_0001_ZERO_GUI_SDK_DEVIANCE.md) | ADR-0001: Zero GUI-SDK Deviance and Strict Downstream Integrity |
| **Python SDK Reference** | [SILIS_PYTHON_SDK_MANUAL.md](docs/SILIS_PYTHON_SDK_MANUAL.md) | Complete SDK method reference, classes, and exceptions |
| **OpenROAD Flow Reference** | [OPENROAD_FLOW_REFERENCE.md](docs/OPENROAD_FLOW_REFERENCE.md) | Downstream OpenROAD command mapping and execution rules |
| **Floorplanning Master** | [05_advanced_floorplanning.md](docs/book/05_advanced_floorplanning.md) | Advanced slicing trees, halos, and channel corridors |

---

## Build and Installation Guide

### Prerequisites
- Linux (x86_64, Ubuntu 22.04+ or Debian 12 recommended)
- `python3` (>= 3.10), `python3-pip`, `cmake` (>= 3.16), `ninja` or `make`
- Qt6 Development Packages (`qt6-base-dev`, `qt6-webengine-dev`)
- EDA Toolchains in `$PATH`: `openroad`, `yosys`, `magic`, `netgen`

### Building Native Acceleration Modules
```bash
# Build native acceleration engines
cd silis/schematicviewer && mkdir -p build && cd build && cmake .. && make -j$(nproc) && cd ../../..
cd silis/clocktreeviewer && mkdir -p build && cd build && cmake .. && make -j$(nproc) && cd ../../..
cd silis/terminal        && mkdir -p build && cd build && cmake .. && make -j$(nproc) && cd ../../..
cd silis/editor          && mkdir -p build && cd build && cmake .. && make -j$(nproc) && cd ../../..
```

### Running the Environments
```bash
# Launch Graphical Desktop IDE
python3 silis/silis.py

# Launch Headless CLI Flow
python3 silis/cli_flow.py --project silis/projects/sram_soc_system --step all

# Run Headless UI State & Physical Verification Suite
QT_QPA_PLATFORM=offscreen SILIS_HEADLESS_TEST=1 python3 silis/tests/test_ui_state_verifier.py
```

---

## License & Attribution

Developed by **The Silis Foundation**. Licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**. See [LICENSE](LICENSE) for details.
