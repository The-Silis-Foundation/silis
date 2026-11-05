# Chapter 6: Polyglot RTL Lowering & Formal Verification

Modern silicon systems incorporate IP blocks written in diverse hardware description languages and high-level languages. Silis supports unified multi-language lowering and automated formal property verification.

---

## 1. Multi-Language RTL Lowering (`pipe.convert`)

The `pipe.convert()` method automatically lowers source HDL/HLS files to standard synthesizable Verilog and registers the resulting netlist into the project sources:

```python
# Lower VHDL-2008 to Verilog using GHDL
v_vhdl = pipe.convert("rtl/cpu_core.vhd", src_lang="vhdl", std="08", fsynopsys=True)

# Lower SystemVerilog to standard Verilog using sv2v
v_sv = pipe.convert("rtl/bus_interconnect.sv", src_lang="sv")

# High-Level Synthesis (HLS) from C/C++ to Verilog using Bambu
v_c = pipe.convert("src/fir_filter.c", src_lang="c", hls_top="fir_filter")
```

### Supported Languages & Compilers

| Source Language | Extension | Underlying Compiler | Features |
| :--- | :--- | :--- | :--- |
| **VHDL-2008** | `.vhd`, `.vhdl` | GHDL (`--synth --std=08`) | Synthesizes complex generic packages, arrays, and standard libraries. |
| **SystemVerilog** | `.sv`, `.svh` | `sv2v` | Lowers interfaces, packages, structs, and multi-dimensional arrays. |
| **C / C++ HLS** | `.c`, `.cpp` | Bambu HLS | Generates hardware FSMs, pipelines, and register interfaces from C code. |

---

## 2. Formal Property Verification (`pipe.formal`)

Ensure your RTL properties and assertions are mathematically verified before synthesis:

```python
# Run Bounded Model Checking (BMC) with SymbiYosys
success = pipe.formal(
    properties="formal/checks.sby",
    engine="smtbmc",
    mode="prove",
    depth=20
)

if success:
    print("Formal verification clean: All assertions proven!")
```

### Modes Supported
- `mode="bmc"`: Bounded Model Checking exploring all possible state transitions up to `depth`.
- `mode="prove"`: K-induction proving invariants hold indefinitely across all execution cycles.
- `mode="cover"`: Verifies state reachability and testbench coverage targets.
