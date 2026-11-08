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
  <a href="#-key-capabilities">Capabilities</a>
  ·
  <a href="#-architecture">Architecture</a>
  ·
  <a href="#-quick-start">Quick Start</a>
  ·
  <a href="#-documentation-manual">Documentation</a>
  ·
  <a href="#-pre-release-packages">Pre-Release Downloads</a>
  ·
  <a href="#-build-guide">Build Guide</a>
</h4>

<p>
  <img alt="License" src="https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge&logo=gnu&logoColor=white">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Linux-lightgrey.svg?style=for-the-badge&logo=linux&logoColor=white">
  <img alt="Language" src="https://img.shields.io/badge/Language-Python%203.12%20%7C%20C%2B%2B17-4169E1.svg?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Release" src="https://img.shields.io/badge/Release-v0.1.0--pre-orange.svg?style=for-the-badge">
</p>

</div>

---

## ⚡ Executive Summary

**Silis (Silicon Scaffold)** is a modern, high-throughput digital ASIC physical design platform and multi-domain power studio bridging the gap between hardware description languages and signoff-quality physical silicon.

Silis orchestrates industry-standard open-source EDA engines—including **OpenROAD**, **Yosys**, **Magic**, **Netgen**, and **SiliconCompiler**—into a unified workflow accessible through:
1. **Interactive Visual CAD (SilisIDE)**: A pure native Qt6 desktop IDE featuring hardware-accelerated DEF inspection (`SiliconPeeker`), OpenROAD visual parity (`LayerViewer`), interactive macro floorplanning, and multi-voltage UPF synthesis.
2. **The Silis Python SDK (`silis.*`)**: A strongly typed, object-oriented API enabling complete tapeout scripts, automated design space exploration, and continuous integration.
3. **Automated CLI Tooling (`silis-flow`, `silis-project`)**: Non-interactive command-line runners for server farms and headless CI/CD.

---

## 📦 Pre-Release Packages (v0.1.0-pre)

Standalone packages are available directly from the [GitHub Releases](https://github.com/The-Silis-Foundation/silis/releases/tag/v0.1.0-pre):

- **Standalone Linux Executable**: [`Silis-x86_64.AppImage`](https://github.com/The-Silis-Foundation/silis/releases/download/v0.1.0-pre/Silis-x86_64.AppImage) (Self-contained binary bundling Python 3.12, Qt6 runtime, and Sky130 technology support).
- **Delta Update Manifest**: [`Silis-x86_64.AppImage.zsync`](https://github.com/The-Silis-Foundation/silis/releases/download/v0.1.0-pre/Silis-x86_64.AppImage.zsync) (Bandwidth-efficient incremental in-app updating).

```bash
# Make executable and launch immediately on Linux:
chmod +x Silis-x86_64.AppImage
./Silis-x86_64.AppImage
```

---

## 🌟 Key Capabilities

- **Zero GUI-SDK Deviance**: 100% architectural parity. Every visual canvas gesture invokes the exact same underlying SDK class method that headless scripts run.
- **Manufacturing Grid & DRC Legalization**: Automatic coordinate quantization ($g = 0.005\ \mu\text{m}$ for Sky130) and unit site row snapping ($y = k \cdot 2.72\ \mu\text{m}$).
- **Multi-Voltage Power Intent (IEEE 1801 UPF 3.0)**: Strict numeric domain voltage extraction, automated isolation clamping, and cross-domain level shifter insertion.
- **Power Distribution Networks (PDN)**: Dual-layer orthogonal power mesh generation with static IR drop compliance ($\le 5\%\ V_{\text{nominal}}$).
- **Automated Macro Placement**: Boundary-aware peripheral placers, OpenROAD RTL-MP sequence pairs, and electrostatic force-field placers.
- **High-Performance C++ Inspection**: Native Pybind11 OpenGL viewers providing smooth pan/zoom, sub-pixel culling, and instant instance navigation.

---

## 🚀 Quick Start (Python SDK)

Create and execute a complete ASIC physical design pipeline in minutes:

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

## 📖 Documentation Manual

The indexed engineering manual is located in [`silis/docs/`](docs/INDEX.md):

| Document | Topic | Description |
| :--- | :--- | :--- |
| **GUI User Manual** | [GUI_USER_MANUAL.md](docs/GUI_USER_MANUAL.md) | Comprehensive interactive IDE walkthrough with annotated screenshots |
| **Architecture Decision Records** | [ADR_0001](docs/architecture/ADR_0001_ZERO_GUI_SDK_DEVIANCE.md) | ADR-0001: Zero GUI-SDK Deviance and Strict Downstream Integrity |
| **Python SDK Reference** | [SILIS_PYTHON_SDK_MANUAL.md](docs/SILIS_PYTHON_SDK_MANUAL.md) | Complete SDK method reference, classes, and exceptions |
| **OpenROAD Flow Reference** | [OPENROAD_FLOW_REFERENCE.md](docs/OPENROAD_FLOW_REFERENCE.md) | Downstream OpenROAD command mapping and execution rules |
| **Floorplanning Master** | [05_advanced_floorplanning.md](docs/book/05_advanced_floorplanning.md) | Advanced slicing trees, halos, and channel corridors |

---

## 🛠️ Build & Installation Guide

### Prerequisites
- Linux (x86_64, Ubuntu 22.04+ or Debian 12 recommended)
- `python3` (>= 3.10), `python3-pip`, `cmake` (>= 3.16), `ninja` or `make`
- Qt6 Development Packages (`qt6-base-dev`, `qt6-webengine-dev`)
- EDA Toolchains in `$PATH`: `yosys`, `openroad`, `magic`, `netgen`

### Building Native C++ Modules
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

## 📜 License & Attribution

Developed by **The Silis Foundation**. Licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**. See [LICENSE](LICENSE) for details.
