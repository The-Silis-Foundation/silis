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
### Professional Open-Source Digital ASIC Design Environment: GUI, CLI & Python SDK

<h4>
  <a href="#overview">Overview</a>
  ·
  <a href="#core-architectural-pillars">Architecture</a>
  ·
  <a href="#key-capabilities">Capabilities</a>
  ·
  <a href="#quick-start-python-sdk">Quick Start</a>
  ·
  <a href="#pre-release-packages">Downloads</a>
  ·
  <a href="#documentation-manual">Documentation</a>
  ·
  <a href="#build-and-installation-guide">Build Guide</a>
</h4>

<p>
  <img alt="License" src="https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge&logo=gnu&logoColor=white">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Linux-lightgrey.svg?style=for-the-badge&logo=linux&logoColor=white">
  <img alt="Language" src="https://img.shields.io/badge/Language-Python%203.12%20%7C%20C%2B%2B17-4169E1.svg?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Release" src="https://img.shields.io/badge/Release-v0.1.0--pre-orange.svg?style=for-the-badge">
</p>

<br>

<img src="docs/images/screenshots/frontend.jpeg" alt="Silis ASIC EDA Studio Interface" width="100%">

</div>

---

## Overview

**Silis (Silicon Scaffold)** is a digital ASIC physical design studio, declarative floorplanner, and multi-domain power orchestrator designed to bridge high-level hardware description languages and signoff-quality physical silicon.

Silicon physical implementation has traditionally suffered from fragmentation between algorithmic command-line engines and interactive visual design tools. Silis unifies synthesis, macro floorplanning, multi-voltage power architecture (IEEE 1801 UPF 3.0), placement, clock tree synthesis (CTS), and routing under a coherent physical abstraction model.

Silis orchestrates industry-standard open-source EDA engines—including **OpenROAD**, **Yosys**, **Magic VLSI**, **Netgen LVS**, and **SiliconCompiler**—into three strictly synchronized execution modalities:
1. **Interactive Visual CAD (SilisIDE)**: A pure native Qt6 desktop environment featuring C++ OpenGL-accelerated physical layout inspection (`SiliconPeeker`), OpenROAD visual parity (`LayerViewerPanel`), real-time macro manipulation, and analytical congestion heatmaps.
2. **The Silis Python SDK (`silis.*`)**: A strongly typed, object-oriented physical design framework enabling complete tapeout scripts, programmatic floorplan synthesis (FPS), design space exploration, and continuous integration.
3. **Automated CLI Runners (`silis-flow`, `silis-project`)**: Non-interactive command-line utilities for headless compilation pipelines, compute grids, and automated regression suites.

---

## Core Architectural Pillars

### The Parity Law: Zero GUI-SDK Deviance
Silis operates under a strict parity contract: the Graphical User Interface is a presentation shell over the Python SDK. Every interactive gesture on the canvas—such as translating a macro, snapping standard cell row origins, sizing core boundaries, or routing power rails—invokes the identical SDK class methods used by batch scripts. Geometric calculations and DRC assertions never reside solely in GUI event handlers. This architecture ensures that any physical state achieved interactively can be reproduced in automated scripts and validated before downstream execution.

### Downstream Data Integrity & Tapeout Discipline
Downstream physical design engines execute Silis instructions verbatim. To eliminate design rule check (DRC) violations, macro overlaps, and routing divergence:
- **Manufacturing Grid Invariance**: All spatial coordinates, dimensions, and spacing margins are quantized to the process manufacturing grid ($g = 0.005\ \mu\text{m}$ for SkyWater 130nm).
- **Site Row Snapping**: Standard cell and macro origins snap to standard cell row site heights ($y = k \times 2.72\ \mu\text{m}$ for `sky130_fd_sc_hd`).
- **Atomic Script Emission**: All generated OpenROAD TCL scripts, UPF intent definitions, and DEF layouts are committed to disk transactionally to prevent partial file writes.

---

## Key Capabilities

- **Declarative Floorplan Synthesis (FPS)**: Define complex hierarchical floorplans, macro halo keepouts, and voltage islands declaratively using clean geometric constraints.
- **Automated Macro Placement**: Boundary-aware peripheral placers, OpenROAD RTL-MP sequence pairs, and electrostatic force-field analytical placement modes.
- **Multi-Voltage Power Intent (IEEE 1801 UPF 3.0)**: Native extraction of explicit domain voltages, automatic level-shifter insertion for cross-domain nets with potential gradients exceeding $0.05\text{V}$, and isolation clamp rules for gated domains.
- **Power Distribution Network (PDN) Synthesis**: Dual-layer orthogonal power mesh generation with static IR drop pre-flight checks ($\le 5\%\ V_{\text{nominal}}$) and daisy-chained power switch insertion.
- **In-Memory Timing Constraints (IEEE 1497 SDC)**: Fluent Python API for specifying clocks, input/output delays, multicycle paths, and clock uncertainty without external constraint files.
- **Dual Visual Engines**: Fast OpenGL DEF inspection (`SiliconPeeker`) for fluid navigation across multi-million-instance designs, alongside compiled C++ layer viewers offering visual parity with OpenROAD.
- **Multi-Spectral Physical Analytics**: Real-time evaluation of placement cell density, routing track demand vs. capacity congestion, and power dissipation gradients.

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

Create and execute a complete ASIC physical design pipeline using the Silis Python SDK:

```python
import silis

# 1. Initialize Pipeline with target PDK
pipe = silis.Pipeline("sram_soc_system", pdk="sky130")

# 2. In-Memory Timing Constraints (IEEE 1497 SDC)
pipe.sdc.clock("clk", period=10.0, uncertainty=0.2) \
        .inputs(delay=2.0, port="rst_n") \
        .outputs(delay=1.5, port="data*")

# 3. Floorplan with Auto Macro Placer & Fences
pipe.floorplan(
    die_area=[0, 0, 1400, 1400],
    core_margin=20.0,
    auto_macro_placer="peripheral",
    regions=[
        pipe.add_fence("u_alu", origin=(300, 700), density=0.50)
    ]
)

# 4. Standard Cell Placement, CTS & Routing
pipe.place()
pipe.cts()
pipe.route()

# 5. Tapeout GDSII Generation & Signoff
pipe.gds()
report = pipe.signoff()
report.print_summary()

# 6. Interactive Visual Inspection
silis.view_layout("results/temp.def", title="SRAM SoC Signoff Layout")
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
