# Silis Architecture Quick Map (Scope: silis/)

## 1. Core Structure
- **`silis.core.sdk.pipeline` (`silis/core/sdk/pipeline.py`)**:
  Authoritative programmatic Python SDK for physical design orchestration (`synth`, `floorplan`, `tapcells`, `pdn`, `iopins`, `place`, `cts`, `route`, `sta`).
- **`silis.core.sdk.project` (`silis/core/sdk/project.py`)**:
  Project definition, PDK setup, multi-domain power domain graph, macro discovery.
- **`silis.core.backendflow.floorplanner` (`silis/core/backendflow/floorplanner/floorplanner.py`)**:
  Interactive Qt floorplanner + programmatic TCL generator (`generate_floorplan_tcl_from_data`). Handles die, core, site rows, macros, halos, fences, regions, and blockages.
- **`silis.core.backendflow.shims.openroad_upf_shim` (`silis/core/backendflow/shims/openroad_upf_shim.tcl`)**:
  OpenROAD IEEE-1801 (UPF 2.0/3.0) compatibility shim normalizing syntax, power switches, isolation, and power domains.
- **`silis.core.cli.flow` (`silis/core/cli/flow.py`)**:
  `HeadlessASICRunner` dispatching steps directly to OpenROAD via streaming IPC.

## 2. Ignore Boundaries
- `third-party/` (SiliconCompiler, external tools, git submodules) -> **NEVER index or modify**
- `dist/`, `build/`, `*.egg-info/` -> **NEVER index or modify**

## 3. Data Integrity Invariants
- Coordinates quantized to 0.005 µm (5 DBU for Sky130).
- Standard cell row height: 2.72 µm (`unithd`).
- No arbitrary row destruction inside active power domains or between macro edges.
