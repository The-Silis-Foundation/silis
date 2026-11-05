# Chapter 1: Architecture & Platform Overview

The **Silis Foundation** platform is built on an architectural triad: **GUI (SilisIDE)**, **CLI (silis-flow / silis-project)**, and the **Python SDK (`silis.*`)**. 

All three modalities operate over the exact same physical design abstractions, configuration manifests, and EDA tool invocations.

```
                    +-------------------------------------------------------+
                    |                   User Entrypoints                    |
                    |    SilisIDE (Qt6)   |   CLI Commands   |  Python SDK  |
                    +-------------------------------------------------------+
                                                |
                                                v
                    +-------------------------------------------------------+
                    |               Unified Pipeline & Project              |
                    |        silis.Pipeline     |      silis.Project        |
                    +-------------------------------------------------------+
                                                |
                                                v
                    +-------------------------------------------------------+
                    |                SiliconCompiler Bridge                 |
                    |          silis.from_sc()   |   silis.to_sc()          |
                    +-------------------------------------------------------+
                                                |
                                                v
                    +-------------------------------------------------------+
                    |              Native EDA & C++ Engines                 |
                    |  OpenROAD  |  Yosys  |  GHDL  |  Magic  |  FastViewer |
                    +-------------------------------------------------------+
```

---

## 1. Core Platform Principles

1. **Total Headless Purity**:
   - The Python SDK (`silis.Pipeline`, `silis.Project`, `silis.ReportEngine`) runs completely headless in CI/CD server clusters with zero dependencies on X11 or PyQt6 GUI runtimes.
2. **Deterministic Manufacturing Snapping**:
   - Every layout coordinate, bounding box, halo, and blockage automatically snaps to the sub-micron PDK manufacturing grid ($0.005\ \mu\text{m}$) and standard cell site row height ($2.72\ \mu\text{m}$ for Sky130).
3. **Multi-Engine Acceleration**:
   - CPU-intensive rendering and graph operations (such as DEF parsing, clock-tree topology extraction, and Monaco code editing) are implemented as native C++ modules exposed to Python via Pybind11.

---

## 2. Directory Layout & Repository Structure

```
silis/
├── backendflow/          # Physical design implementations & Floorplanner
│   ├── fast_viewer/      # High-performance C++ DEF layout viewer
│   ├── floorplanner/     # Interactive floorplanner widget & TCL generators
│   └── siliconpeeker/    # Standalone DEF layout inspection tool
├── clocktreeviewer/      # C++ STA clock tree visualizer
├── docs/                 # Engineering manuals, book chapters & reference scripts
│   ├── book/             # Indexed technical documentation chapters
│   └── reference/        # End-to-end runnable Python SDK reference scripts
├── editor/               # Monaco WebEngine & Scintilla text editors
├── pdkmanagers/          # PDK resolution (Sky130, GF180, Volare integration)
├── sdk/                  # Core Python SDK modules (Pipeline, Project, SDC, Viewers)
├── synthesisscripts/     # Yosys synthesis dashboard & PAT report parser
├── terminal/             # Embedded C++ terminal emulator
└── third-party/          # Vendored toolchains (SiliconCompiler, GDS3D, OpenSTA)
```

---

## 3. PDK Management Architecture

Silis integrates **Volare** and the internal `PDKManager` / `SSAForge` subsystem:
- Automatically crawls installed PDKs in standard paths (`$PDK_ROOT`, `~/.volare`, `silis/third-party/pdks`).
- Resolves Tech LEFs, Standard Cell LEFs, Macro LEFs, and Liberty timing corners (`nom`, `min`, `max`, `ss`, `ff`).
- Injects resolved paths directly into Yosys synthesis scripts, OpenROAD floorplanning, and SiliconCompiler chip targets without requiring manual path entry.
