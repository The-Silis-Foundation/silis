# Chapter 3: Command-Line Interface (CLI) Manual

The Silis platform provides a suite of high-throughput CLI entrypoints designed for automated build scripts, CI pipelines, and headless servers.

---

## 1. CLI Commands Overview

| Command | Entry File | Purpose |
| :--- | :--- | :--- |
| `silis-flow` | `cli_flow.py` | Headless execution of individual or full ASIC flow steps. |
| `silis-project` | `cli_project.py` | Project creation, manifest scaffolding, and dependency inspection. |
| `silis-main` | `cli_main.py` | Unified CLI router dispatching GUI, TUI, and batch tasks. |
| `silis-tui` | `tui_repl.py` | Full-screen interactive terminal REPL and code editor. |

---

## 2. `silis-flow`: Headless Flow Execution

Execute steps directly without launching a graphical window:

```bash
# Run complete end-to-end flow
python3 silis/cli_flow.py --project silis/projects/sram_soc_system --step all

# Run specific individual steps
python3 silis/cli_flow.py --project silis/projects/sram_soc_system --step synth
python3 silis/cli_flow.py --project silis/projects/sram_soc_system --step floorplan
python3 silis/cli_flow.py --project silis/projects/sram_soc_system --step place
python3 silis/cli_flow.py --project silis/projects/sram_soc_system --step route
python3 silis/cli_flow.py --project silis/projects/sram_soc_system --step gds
python3 silis/cli_flow.py --project silis/projects/sram_soc_system --step signoff
```

### Flow CLI Arguments
- `--project <path>`: Path to the target Silis project directory.
- `--step <name>`: Target step: `synth`, `floorplan`, `tapcells`, `pdn`, `iopins`, `place`, `cts`, `route`, `gds`, `signoff`, or `all`.
- `--pdk <name>`: Override target process development kit (`sky130`, `gf180`).
- `--headless`: Force headless execution regardless of display environment.

---

## 3. `silis-project`: Project Management

Scaffold and manage Silis ASIC projects from the terminal:

```bash
# Initialize a new project
python3 silis/cli_project.py init --name my_riscv_soc --top top_soc --pdk sky130

# Add Verilog and SDC sources
python3 silis/cli_project.py add-src --project my_riscv_soc --file rtl/core.v
python3 silis/cli_project.py add-sdc --project my_riscv_soc --file constraints/timing.sdc

# Inspect project hierarchy and utilization
python3 silis/cli_project.py info --project my_riscv_soc
```

---

## 4. `silis-tui`: Terminal User Interface (REPL)

For environments without an X11 server (e.g. remote cloud instances or SSH sessions), `silis-tui` provides a rich text-mode interface powered by `prompt_toolkit`:

```bash
python3 silis/tui_repl.py --project silis/projects/sram_soc_system
```

Features include:
- Autocompletion for pipeline commands and project paths.
- Split-screen log viewing with live status spinners.
- Built-in syntax-highlighted editor (`tui_editor.py`).
