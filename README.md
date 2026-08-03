<div align="center">

<div align="center">

<pre>
███████╗ ██╗ ██╗      ██╗ ███████╗
██╔════╝ ██║ ██║      ██║ ██╔════╝
███████╗ ██║ ██║      ██║ ███████╗
╚════██║ ██║ ██║      ██║ ╚════██║
███████║ ██║ ███████╗ ██║ ███████║
╚══════╝ ╚═╝ ╚══════╝ ╚═╝ ╚══════╝
</pre>

</div>

# SILIS — Silicon Scaffold

### The Ultimate RTL to GDSII IDE

<h4>
  <a href="#-features">Features</a>
  ·
  <a href="#-development-status">Status</a>
  ·
  <a href="#-whats-working">Capabilities</a>
  ·
  <a href="#-project-structure">Architecture</a>
  ·
  <a href="#-compilation--build-instructions">Build Guide</a>
</h4>

<p>
  <img alt="License" src="https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge&logo=gnu&logoColor=white">
  <img alt="Status" src="https://img.shields.io/badge/Status-Experimental-orange.svg?style=for-the-badge&logo=rocket&logoColor=white">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Linux-lightgrey.svg?style=for-the-badge&logo=linux&logoColor=white">
  <img alt="Powered By" src="https://img.shields.io/badge/Engine-PyQt6%20%7C%20C++-4169E1.svg?style=for-the-badge&logo=python&logoColor=white">
</p>

</div>

---

**Silis** is an **Integrated Development Environment (IDE)** for the RTL to GDSII flow built around speed, aesthetics, and raw efficiency. 

By integrating powerful open-source EDA tools—including **Icarus Verilog**, **Yosys**, **OpenROAD**, **Netgen**, and **KLayout**—Silis bridges the gap between hardware definition and physical silicon. It wraps complex EDA flows in an intuitive interface, making silicon design easier for beginners and blisteringly fast for experts. 

---

## Features

- **Pseudo-Terminal UI**: A fully integrated custom terminal with ghost auto-fill suggestions and command autocompletion to accelerate your workflow.
- **Blazing Fast C++ Renderers**: Seamless Pybind11 integration pushing thousands of standard cells, macros, and power rails into Qt6 at 60 FPS without breaking a sweat!
- **Built-in PDK Manager**: Integrated with Volare for zero-friction PDK downloading, corner selection, and configuration switching.
- **Visual Insights**:
  - **Signal Peeker**: Built-in VCD waveform viewer.
  - **Schematic Viewer**: High-speed JSON structural parsing of your Yosys logic netlists via embedded web-rendering.
  - **Fast Layout Viewer**: A stunningly fast DEF visualizer mapping abstract chip structures, macros, pins, and heatmaps.
  - **GDS3D View**: Spawn an interactive 3D cross-section window of your physical silicon over your IDE!

---

## What's Working Right Now?

- [x] **Verilog Compilation**: One-click (`F1`) Icarus Verilog compilation.
- [x] **Simulation**: Drop your dump VCD in your testbench, and Signal Peeker auto-detects and loads the waveform!
- [x] **Schematic Generation**: Multi-layered graph extraction ranging from hierarchical blocks down to gate-level structural views.
- [x] **Synthesis**: Seamless Yosys + ABC integration.
- [x] **Analysis**: Automatic post-synthesis reports mapping power, area, timing, and cell utilization.
- [x] **Placement & Routing**: End-to-end routing workflows.
- [x] **GDSII Generation**: Generating physical layout GDS files with Magic.
- [x] **Fast Layout Rendering**: Custom C++ engine rendering OpenROAD DEF files in real-time.
- [ ] **RAM Black-boxing**: *Coming soon via OpenRAM integration!*

---

## Native C++ Engines & Integrations

To achieve high performance, Silis relies on several custom C++ engines exposed to Python via `pybind11`:

- **Schematic Engine** (`schematicviewer/`): Hosts the `digitaljs.html` renderer inside a native `QWebEngineView` and manages background Yosys graph extraction.
- **Fast Layout Engine** (`backendflow/fast_viewer/` & `backendflow/def_viewer_cpp/`): Bypasses legacy MESA OpenGL errors by rendering millions of layout shapes (macros, pins, standard cells) directly via native Qt primitives.
- **Clock Tree Engine** (`clocktreeviewer/`): Parses STA clock tree JSON outputs (buffers, fanouts, caps) and interactively visualizes the topology using custom C++ Qt drawing.
- **Monaco Editor Engine** (`editor/`): Wraps the Monaco code editor inside a native `QWebEngineView` as the primary IDE text editor. It intelligently falls back to the native `QsciScintilla` editor if the C++ module fails to load, guaranteeing usability on all setups.

## Third-Party App Integrations

Silis embeds and calls out to heavily optimized open-source tools to handle complex EDA tasks:

- **GDS3D** (`third-party/GDS3D/`): A hardware-accelerated 3D physical layout viewer custom-compiled for Silis.
- **OpenSTA** (`third-party/OpenSTA/` and `synthengine/`): Embedded statically for high-performance timing analysis and topology extraction.
- **External CLI Apps**: Tools like **Yosys** (Logic Synthesis), **OpenROAD** (Place & Route), and **Magic** (DRC/GDS extraction) are called dynamically via Python subprocesses. Ensure these are installed in your system `$PATH`.

---

## Compilation & Build Instructions

Before running the IDE, you must compile the custom C++ engines. 

### Prerequisites
- `cmake` (>= 3.16)
- `make` or `ninja`
- `pybind11-dev`
- Qt6 Development Packages (`qt6-base-dev`, `qt6-webengine-dev`, etc.)

### Build Steps

For each engine directory (`schematicviewer`, `clocktreeviewer`, `editor`, `synthengine`, `backendflow/fast_viewer`, `backendflow/def_viewer_cpp`, `third-party/GDS3D`, `third-party/OpenSTA`), follow the standard CMake build process:

```bash
cd <engine_directory>
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

The `CMakeLists.txt` files are configured to generate `.so` libraries that the Python frontend dynamically imports at runtime. 

---

## Project Structure

Clean separation of concerns for active development:

- `prime/` - Production-ready, stable codebase *(Coming soon)*
- `experimental/` - Where the magic happens. Working features under active iteration.
- `dev_*/` - Personal developer playgrounds.
- `reference/` - Core documentation and boilerplate examples.
- `third-party/` - Embedded third-party C++ repositories (GDS3D, OpenSTA).
- `schematicviewer/`, `editor/`, `clocktreeviewer/`, `synthengine/`, `backendflow/` - Core native C++ engines and their Python UI wrappers.

---

## Development Status

**Current status**: Early development, experimental features only.

> *Silis is evolving quickly. While the core features work flawlessly, breaking changes may occur in the `experimental` branch.*

### Quick Links
- [Stable Release: POCPNRV25](https://github.com/The-Silis-Foundation/silis/blob/main/experimental/POCPNRV25)
- Check `experimental/by_JeromeAntonyRobin` for the latest cutting-edge reference builds!

---

## License & Contributions

**Silis** is proudly open-source under the **GNU Affero General Public License v3.0 (AGPL v3)**. 

We believe silicon design tools should be accessible to everyone. The source code is open and will remain open. You are free to modify it for your own workflows!

*Currently, we are not accepting external contributions as the architecture is still being heavily shaped.*

**Conditions:**
- **License and copyright notice** must be included in all copies.
- Source code must be disclosed when distributing or interacting with it over a network.
- All modifications must remain under the AGPL v3.

<div align="center">
  <br>
  <b>Created by <a href="https://github.com/JeromeAntonyRobin">Jerome Antony Robin</a></b><br>
  &copy; 2026 The Silis Foundation
</div>
