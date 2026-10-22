# Chapter 7: End-to-End Reference Examples

The Silis repository includes end-to-end reference flows demonstrating production-grade tapeout pipelines using the Python SDK. The complete scripts are stored in [`silis/docs/reference/`](../reference/).

---

## 1. Pure Python SDK Quad-Core SRAM SoC

- **Script Path**: [`silis/docs/reference/run_pure_python_sdk.py`](../reference/run_pure_python_sdk.py)
- **Architecture**: Quad-core RISC-V SoC with integrated Sky130 SRAM macro, UART, timers, and bus arbiters.
- **Workflow Highlights**:
  - Full headless execution via `silis.Pipeline`.
  - Fluent in-memory `SDCBuilder` constraints.
  - Peripheral macro placement leaving open center core cavity.
  - TritonRoute detailed routing and signoff report extraction.

### Code Walkthrough
```python
import silis

# 1. Initialize Pipeline
pipe = silis.Pipeline("sram_soc_quad_pure_sdk", pdk="sky130")

# 2. Timing Constraints
pipe.sdc.clock("clk", period=10.0, uncertainty=0.2) \
        .inputs(delay=2.0, port="rst_n") \
        .outputs(delay=1.5, port="data*")

# 3. Floorplan
pipe.floorplan(
    die_area=[0, 0, 1400, 1400],
    core_margin=20.0,
    auto_macro_placer="peripheral"
)

# 4. Physical Implementation
pipe.place()
pipe.cts()
pipe.route()

# 5. Signoff
rpt = pipe.signoff()
rpt.print_summary()
```

---

## 2. High-Density GEMM RV32 Pentium SoC Flow

- **Script Path**: [`silis/docs/reference/run_gemm_pentium_e2e.py`](../reference/run_gemm_pentium_e2e.py)
- **Architecture**: Complete Heterogeneous SoC combining a 32-bit RISC-V Pentium-compatible CPU core with a systolic GEMM matrix multiplication accelerator.
- **Complexity**:
  - 89,559 standard cells across 1.708 mm² core area.
  - 531,360 routing vias and 2.483 meters of on-chip wirelength.
  - Signoff-clean: **0 DRC violations**, **WNS = 0.000 ns (Timing MET)**.
  - Final merged tapeout GDS: 212 MB.
