# Silis Foundation Engineering Manual
## The Complete Reference Guide to the Silis ASIC Ecosystem

Welcome to the **Silis Foundation Engineering Manual**. Silis is an integrated silicon development platform uniting interactive graphical CAD, a headless Python SDK, automated CLI pipelines, and SiliconCompiler interoperability.

---

## 📑 Book Contents & Chapter Index

- **[Chapter 1: Architecture & Platform Overview](book/01_architecture_overview.md)**
  - Core philosophy: GUI, CLI, and Python SDK parity
  - Native C++ acceleration engines (Pybind11, OpenGL, Qt6)
  - PDK management and auto-resolution (Sky130, GF180, Volare)
- **[Chapter 2: The Silis Python SDK Reference](book/02_python_sdk_reference.md)**
  - `silis.Project`: Netlist introspection, cell area estimation, and path resolution
  - `silis.Pipeline`: End-to-end execution (`init`, `synth`, `floorplan`, `place`, `cts`, `route`, `signoff`)
  - `SDCBuilder`: Fluent in-memory timing constraint formulation
  - Layout & Signoff viewers: `view_layout`, `view_gds3d`, `view_waveforms`, `view_schematic`
- **[Chapter 3: Command-Line Interface (CLI) Manual](book/03_cli_reference.md)**
  - Headless execution: `silis-flow` and `silis-project`
  - Automated step runners and batch execution
  - Terminal interactive environment (TUI REPL & Editor)
- **[Chapter 4: SiliconCompiler Compatibility & Handoffs](book/04_siliconcompiler_compatibility.md)**
  - Vendored auto-discovery architecture (`silis.sc`)
  - Zero-config PDK bridging via `SilisSCPDKAdapter`
  - Mid-flow bidirectional translation: `silis.from_sc(chip)` & `silis.to_sc(pipe)`
  - SC jobdir and manifest mapping
- **[Chapter 5: Advanced Floorplanning, Macros & Regions](book/05_advanced_floorplanning.md)**
  - Automated macro placer modes: `peripheral`, `hierarchical` (RTL-MP), and `openroad` (TritonMacroPlace)
  - Ergonomic helpers: `place_macro(..., halo=10)`, `add_fence()`, `add_blockage()`
  - Auto Region Shaper and Hierarchical Cavity Placer
- **[Chapter 6: Polyglot RTL Lowering & Formal Verification](book/06_polyglot_and_formal.md)**
  - Multi-language synthesis: VHDL-2008 (`ghdl`), SystemVerilog (`sv2v`), and C/C++ HLS (`bambu`)
  - Formal property verification with SymbiYosys (`pipe.formal()`)
- **[Chapter 7: End-to-End Reference Examples](book/07_reference_examples.md)**
  - Pure Python SDK Quad-Core SRAM SoC (`run_pure_python_sdk.py`)
  - High-density GEMM RV32 Pentium SoC tapeout run (`run_gemm_pentium_e2e.py`)

---

## 🚀 Quick Start Example

```python
import silis

# 1. Initialize Pipeline
pipe = silis.Pipeline("sram_soc_system", pdk="sky130")

# 2. In-Memory Timing Constraints
pipe.sdc.clock("clk", period=10.0, uncertainty=0.2).inputs(2.0, "rst_n").outputs(1.5, "data*")

# 3. Floorplan with Auto Macro Placer & Fences
pipe.floorplan(
    die_area=[0, 0, 1400, 1400],
    core_margin=20.0,
    auto_macro_placer="peripheral",
    regions=[
        pipe.add_fence("u_alu", origin=(300, 700), density=0.50)
    ]
)

# 4. Physical Implementation & Signoff
pipe.place()
pipe.cts()
pipe.route()
report = pipe.signoff()
report.print_summary()

# 5. Interactive Visual Inspection
silis.view_layout("results/temp.def", title="SRAM SoC Signoff Layout")
```

---

## 📚 Code References
Runnable reference scripts are located in [`silis/docs/reference/`](reference/):
- [`run_pure_python_sdk.py`](reference/run_pure_python_sdk.py) — 100% headless Python script building an SRAM SoC.
- [`run_gemm_pentium_e2e.py`](reference/run_gemm_pentium_e2e.py) — Signoff-clean GEMM accelerator SoC flow.
