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
  <a href="#-build-guide">Build Guide</a>
</h4>

<p>
  <img alt="License" src="https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge&logo=gnu&logoColor=white">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Linux-lightgrey.svg?style=for-the-badge&logo=linux&logoColor=white">
  <img alt="Language" src="https://img.shields.io/badge/Language-Python%203.12%20%7C%20C%2B%2B17-4169E1.svg?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Signoff Status" src="https://img.shields.io/badge/Signoff-Clean%20(DRT--0199)-success.svg?style=for-the-badge">
</p>

</div>

---

## ⚡ Executive Summary

**Silis (Silicon Scaffold)** is a modern, high-throughput digital ASIC design platform bridging the gap between hardware description languages and signoff-quality physical silicon. 

Silis orchestrates industry-standard open-source EDA engines—including **Yosys**, **OpenROAD**, **Magic**, **Netgen**, and **SiliconCompiler**—into a unified workflow accessible through:
1. **Interactive Visual CAD (SilisIDE)**: A reactive desktop IDE with Monaco code editing, C++ accelerated DEF/GDS3D layout viewers, and real-time floorplanning.
2. **The Silis Python SDK (`silis.*`)**: A fluent, headless API enabling complete tapeout scripts, automated design space exploration, and continuous integration.
3. **Automated CLI Tooling (`silis-flow`, `silis-project`)**: Non-interactive command-line runners for server farms and headless CI/CD.

---

## 🌟 Key Capabilities

- **Unified Flow Modalities**: Total feature parity across the Qt6 Graphical IDE, headless Python SDK, and terminal CLI.
- **SiliconCompiler Compatibility (`silis.sc`)**: Vendored, zero-configuration SC interoperability. Perform mid-flow handoffs (`silis.from_sc` / `silis.to_sc`) with automated PDK bridging.
- **Automated Macro Placement**: Built-in support for **Peripheral** (fast geometric boundary solver), **Hierarchical** (OpenROAD RTL-MP sequence pairs), and **Analytical** (TritonMacroPlace electrostatic force-field) placer modes.
- **Fluent In-Memory SDC Constraints**: Define clocks, I/O delays, and false paths in Python (`pipe.sdc.clock("clk", 10.0)...`) without fragile constraint files.
- **Polyglot RTL Lowering**: Multi-language frontend lowering VHDL-2008 (`ghdl`), SystemVerilog (`sv2v`), and C/C++ HLS (`bambu`) into standard synthesizable Verilog.
- **Automated Formal Verification**: Embedded property verification wrapping SymbiYosys (`pipe.formal()`).
- **High-Performance C++ Engines**: Native Pybind11 modules powering high-frame-rate DEF layout inspection (`SiliconPeeker`), STA clock-tree topology visualization, and interactive terminals.

---

## 🚀 Quick Start (Python SDK)

Create and execute a complete ASIC physical design pipeline in minutes:

```python
import silis

# 1. Initialize Pipeline with target PDK
pipe = silis.Pipeline("sram_soc_system", pdk="sky130")

# 2. In-Memory Timing Constraints
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

| Chapter | Topic | Link |
| :--- | :--- | :--- |
| **Chapter 1** | Platform Architecture & Principles | [01_architecture_overview.md](docs/book/01_architecture_overview.md) |
| **Chapter 2** | Python SDK Reference Guide | [02_python_sdk_reference.md](docs/book/02_python_sdk_reference.md) |
| **Chapter 3** | Command-Line Interface (CLI) Manual | [03_cli_reference.md](docs/book/03_cli_reference.md) |
| **Chapter 4** | SiliconCompiler Compatibility & Handoffs | [04_siliconcompiler_compatibility.md](docs/book/04_siliconcompiler_compatibility.md) |
| **Chapter 5** | Advanced Floorplanning, Macros & Regions | [05_advanced_floorplanning.md](docs/book/05_advanced_floorplanning.md) |
| **Chapter 6** | Polyglot RTL Lowering & Formal Verification | [06_polyglot_and_formal.md](docs/book/06_polyglot_and_formal.md) |
| **Chapter 7** | End-to-End Reference Examples | [07_reference_examples.md](docs/book/07_reference_examples.md) |

---

## 🛠️ Build & Installation Guide

### Prerequisites
- Linux (x86_64, Ubuntu 22.04+ or Debian 12 recommended)
- `python3` (>= 3.10), `python3-pip`, `cmake` (>= 3.16), `ninja` or `make`
- Qt6 Development Packages (`qt6-base-dev`, `qt6-webengine-dev`)
- EDA Toolchains in `$PATH`: `yosys`, `openroad`, `magic`, `netgen`, `iverilog`

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

# Run Python SDK Verification Suite
python3 silis/tests/verify_everything.py
```

---

## 📜 License & Attribution

Developed by **The Silis Foundation**. Licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**. See [LICENSE](LICENSE) for details.
