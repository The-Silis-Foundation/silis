<h1 align="center"><b>SILIS - Silicon Scaffold</b></h1>
<p align="center">
    <a href="https://www.gnu.org/licenses/agpl-3.0"><img src="https://img.shields.io/badge/License-AGPL_v3-blue.svg" alt="License: AGPL v3"/></a>
    <a href="https://github.com/JeromeAntonyRobin/silis"><img src="https://img.shields.io/badge/Status-Experimental-orange.svg" alt="Status: Experimental"/></a>
</p>

silis is an **integrated development environment (IDE)** for RTL to GDSII flow based and built upon several open-source softwares including **Icarus Verilog, Yosys, OpenROAD, Netgen, KLayout** and custom scripts that make the silicon design flow **easier for beginners and faster for experts** due to its **keyboard-first, UX-first approach**.

silis aims to perform all ASIC design steps from RTL design to GDSII generation.

silis is available under the **GNU Affero General Public License v3.0 (AGPL v3)**. It is meant to be used, forked, and modified. **The source code is open and will remain available even after application releases—feel free to modify it to your needs and your workflow.**

---

# Still In Development!

## [Click Here](https://github.com/The-Silis-Foundation/silis/blob/main/experimental/POCPNRV25) to use the latest stable version

**Current status**: Early development, experimental features only.

**Latest stable**: Check `experimental/by_JeromeAntonyRobin` for the latest "Reference Build".

## What works right now
- [x] **Verilog Compilation**: complie codes with f1 using icarus verilog
- [x] **Psuedo-Terminal**: Works flawlessly, ghost autofill suggestions and command suggestions (front-end only, backend coming soon!)
- [x] **Waveform Viewer**: in-built wavefrom viewer called signal peeker that automatically detects .vcd files (if given dump vcd in test bench)
- [x] **schematic Generation and viewer**: using graphviz as schematic engine
- [x] **PDK Manager**: in built PDK manager with volare integration and customizable pdk corner selection and custom config
- [x] **Synthesis**: Using Yosys and abc
- [x] **Post-synthesis report generation**: report generation with power-area-timing informations, cell utilisations and more.
- [x] **Placement and Routing**: works.
- [x] **DEF file visualizer**: in-built DEF file visualizer called silisconpeeker, a lightwieght visualisation tool for abstract view of the chip structure, has layers and overlay features like heatmap (cell density)
- [x] **GDS Generation**: using Magic
- [x] **inbuilt GDS viewer**: its slow. but works
- [x] **GDS3D Integration**: spawns a GDS3D window over silis IDE window thats resized along with the silis IDE window ( buggy with wayland, usable tho ;) )
- [ ] **RAM Black-boxing and placement**: using OenRAM, i guess..

## Project structure
- `prime/` - Production-ready code (when we have it)
- `experimental/` - Working features, still rough
- `dev_*/` - Personal dev playgrounds (ignore these)
- `reference/` - Documentation and examples

## For contributors
We're not ready for external contributions yet.

## Created by [Jerome Antony Robin](https://github.com/JeromeAntonyRobin)

## License
**GNU Affero General Public License v3.0 (AGPL v3)**

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

**Permissions:**
* Commercial use
* Modification
* Distribution
* Private use

**Conditions:**
* **License and copyright notice**: Must be included in all copies.
* **State changes**: You must state significant changes made to the software.
* **Disclose Source**: Source code must be made available when distributing the software or **interacting with it over a network**.
* **Same License**: Modifications must be released under the same AGPL v3 license.

&copy; 2026 The Silis Foundation
