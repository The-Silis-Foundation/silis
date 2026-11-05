# Chapter 4: SiliconCompiler Compatibility & Handoffs

Silis integrates **SiliconCompiler (SC)** directly into its runtime, enabling bidirectional interoperability between SiliconCompiler workflows and the Silis physical design ecosystem.

---

## 1. Zero-Configuration Vendored Auto-Discovery

SiliconCompiler is vendored directly in `silis/third-party/siliconcompiler`. Importing `silis` automatically exposes SiliconCompiler:

```python
import silis

# SiliconCompiler module auto-discovered and ready
chip = silis.sc.Chip("demo_asic")
```

The `SilisSCPDKAdapter` automatically queries the Silis `PDKManager` and binds Sky130 / GF180 tech LEFs, standard cell LEFs, and Liberty models without requiring manual JSON schema path setup.

---

## 2. Bidirectional Translation Layer

Hardware engineers can freely transition mid-flow between SiliconCompiler and Silis:

```
+---------------------------+                      +---------------------------+
|      SiliconCompiler      |  silis.from_sc(chip) |      Silis Pipeline       |
|        Chip / ASIC        | -------------------> |         Pipeline          |
|  (Frontend / Cloud Run)   | <------------------- |  (Deep Floorplan / Macro) |
+---------------------------+   silis.to_sc(pipe)  +---------------------------+
```

### Case A: Import from SiliconCompiler to Silis (`silis.from_sc`)
Start synthesis or project configuration in SiliconCompiler, then hand off to Silis for interactive floorplanning, custom halo assignment, and fast layout viewing:

```python
import silis
from silis import sc

# 1. Setup in SiliconCompiler
chip = sc.Chip("sram_soc_top")
chip.set("design", "sram_soc_top")
chip.set("asic", "pdk", "sky130")

# 2. Hand off to Silis Pipeline
pipe = silis.from_sc(chip)

# 3. Continue in Silis
pipe.floorplan(die_area=[0, 0, 1400, 1400], auto_macro_placer="peripheral")
pipe.place()
pipe.route()
```

### Case B: Export from Silis to SiliconCompiler (`silis.to_sc`)
Execute custom physical floorplanning and macro legalization in Silis, then export back to an SC `ASIC` object to plug into remote server clouds or verification matrices:

```python
import silis

pipe = silis.Pipeline("sram_soc_system", pdk="sky130")
pipe.floorplan(die_area=[0, 0, 1400, 1400], auto_macro_placer="peripheral")

# Convert pipeline to SiliconCompiler ASIC object
sc_asic = silis.to_sc(pipe)

# Access SiliconCompiler native targets and run steps
print(f"Exported SC Design: {sc_asic.design}")
```

---

## 3. Directory and Artifact Mapping

The `SilisDirectoryAdapter` cleanly maps SiliconCompiler jobdirs to Silis layout deliverables:

| SiliconCompiler Path | Silis Native Path | Description |
| :--- | :--- | :--- |
| `build/<design>/<job>/<step>/outputs/*.def` | `results/temp.def` | Routed physical design exchange DEF |
| `build/<design>/<job>/<step>/outputs/*.v` | `netlist/<design>_netlist.v` | Structural gate-level Verilog |
| `build/<design>/<job>/<step>/reports/*.rpt` | `reports/*.rpt` | Timing, power, and area signoff summaries |
| Constraints FileSet | `pipe.sdc` | Synopsys Design Constraints |
