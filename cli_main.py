"""
cli_main.py
Main CLI Dispatcher for Silis ASIC Flow.
Parses headless commands (--init, --run-*, --tcl) and dispatches to
cli_project.py, cli_flow.py, or tui_editor.py.
"""

import os
import sys
import argparse

import cli_project
import cli_flow


def parse_macro_flag(macro_strings):
    """
    Parses macro CLI strings formatted like:
    'u_sram_0 100 100 -cell sky130_sram_1kbyte -orient R90 --halo 10 10 10 10'
    """
    parsed = []
    if not macro_strings:
        return parsed
    for s in macro_strings:
        parts = s.split()
        if len(parts) >= 3:
            inst = parts[0]
            x, y = float(parts[1]), float(parts[2])
            cell = ""
            orient = "R0"
            halo = [0, 0, 0, 0]
            i = 3
            while i < len(parts):
                if parts[i] in ["-cell", "--cell"] and i + 1 < len(parts):
                    cell = parts[i+1]; i += 2
                elif parts[i] in ["-orient", "-orientation", "--orient"] and i + 1 < len(parts):
                    orient = parts[i+1]; i += 2
                elif parts[i] in ["-halo", "--halo"] and i + 4 < len(parts):
                    halo = [float(parts[i+1]), float(parts[i+2]), float(parts[i+3]), float(parts[i+4])]
                    i += 5
                else:
                    i += 1
            parsed.append({"inst": inst, "cell": cell, "pos": [x, y], "orient": orient, "halo": halo})
    return parsed


def parse_region_flag(region_strings, is_fence_default=False):
    """
    Parses region / fence CLI strings formatted like:
    'u_crypto 500 500 900 900 -density 0.65 --halo 5 5 5 5'
    """
    parsed = []
    if not region_strings:
        return parsed
    for s in region_strings:
        parts = s.split()
        if len(parts) >= 5:
            mod = parts[0]
            box = [float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])]
            density = 0.60
            rtype = "exclusive" if is_fence_default else "inclusive"
            halo = [0, 0, 0, 0]
            i = 5
            while i < len(parts):
                if parts[i] in ["-density", "--density"] and i + 1 < len(parts):
                    density = float(parts[i+1]); i += 2
                elif parts[i] in ["-type", "--type"] and i + 1 < len(parts):
                    rtype = parts[i+1].lower(); i += 2
                elif parts[i] in ["inclusive", "exclusive"]:
                    rtype = parts[i]; i += 1
                elif parts[i] in ["-halo", "--halo"] and i + 4 < len(parts):
                    halo = [float(parts[i+1]), float(parts[i+2]), float(parts[i+3]), float(parts[i+4])]
                    i += 5
                else:
                    i += 1
            parsed.append({
                "module": mod,
                "box": box,
                "density": density,
                "is_fence": (rtype == "exclusive"),
                "halo": halo
            })
    return parsed


def parse_blockage_flag(blockage_strings):
    """
    Parses blockage CLI strings formatted like:
    '400 400 500 500 -type partial -density 40'
    """
    parsed = []
    if not blockage_strings:
        return parsed
    for s in blockage_strings:
        parts = s.split()
        if len(parts) >= 4:
            box = [float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])]
            btype = "Hard"
            density = 50
            i = 4
            while i < len(parts):
                if parts[i] in ["-type", "--type"] and i + 1 < len(parts):
                    btype = parts[i+1].capitalize(); i += 2
                elif parts[i] in ["hard", "soft", "partial"]:
                    btype = parts[i].capitalize(); i += 1
                elif parts[i] in ["-density", "--density"] and i + 1 < len(parts):
                    density = float(parts[i+1]); i += 2
                elif parts[i].isdigit():
                    density = float(parts[i]); i += 1
                else:
                    i += 1
            parsed.append({"box": box, "type": btype, "density": density})
    return parsed


def handle_cli(args_list):
    """
    Dispatches CLI arguments. Returns True if a CLI command was handled,
    or False if GUI mode should proceed.
    """
    if not args_list:
        return False

    parser = argparse.ArgumentParser(
        prog="silis",
        description="Silis - ASIC Silicon Scaffold CLI & GUI Flow Runner",
        add_help=False
    )

    # Project init options
    parser.add_argument("--init", nargs="?", const="__INTERACTIVE__", default=None,
                        help="Initialize new ASIC project. Omit arg for guided TUI wizard.")
    parser.add_argument("--rtl", nargs="+", help="RTL source files or directories")
    parser.add_argument("--tb", nargs="+", help="Testbench files or directories")
    parser.add_argument("--sdc", nargs="+", help="SDC timing constraint files")
    parser.add_argument("--pdk", default="sky130", help="Silicon PDK target: sky130 or gf180mcu")
    parser.add_argument("--top", default=None, help="Top-level module name")
    parser.add_argument("--macro", nargs="+", action="append", help="Macro instances or cells")

    # Flow step commands
    parser.add_argument("--run-synth", nargs="?", const="__DEFAULT__", help="Run Yosys RTL synthesis")
    parser.add_argument("--run-init", nargs="?", const="__DEFAULT__", help="Run OpenROAD design link & init")
    parser.add_argument("--run-floorplan", nargs="?", const="__DEFAULT__", help="Run Floorplanning with macros & fences")
    parser.add_argument("--run-tapcells", nargs="?", const="__DEFAULT__", help="Run Tapcell & Endcap insertion")
    parser.add_argument("--run-pdn", nargs="?", const="__DEFAULT__", help="Run Power Distribution Network")
    parser.add_argument("--run-iopins", nargs="?", const="__DEFAULT__", help="Run IO Pin placement")
    parser.add_argument("--run-place", nargs="?", const="__DEFAULT__", help="Run Global & Detailed Placement")
    parser.add_argument("--run-cts", nargs="?", const="__DEFAULT__", help="Run Clock Tree Synthesis")
    parser.add_argument("--run-route", nargs="?", const="__DEFAULT__", help="Run Global & Detailed Routing")
    parser.add_argument("--run-antenna", nargs="?", const="__DEFAULT__", help="Run Antenna violation check")
    parser.add_argument("--run-sta", nargs="?", const="__DEFAULT__", help="Run Static Timing Signoff")
    parser.add_argument("--run-pat", nargs="?", const="__DEFAULT__", help="Run Power, Area, Timing (PAT) signoff")
    parser.add_argument("--run-drc", nargs="?", const="__DEFAULT__", help="Run DRC verification")
    parser.add_argument("--run-dft", nargs="?", const="__DEFAULT__", help="Run DFT scan analysis and ATPG pattern generation")
    parser.add_argument("--dft", action="store_true", help="Enable scan flop replacement & SCANDEF generation during synthesis")
    parser.add_argument("--export-stil", metavar="PATH", help="Export ATPG test patterns to IEEE 1450 STIL file")
    parser.add_argument("--export-tb", metavar="PATH", help="Export ATPG self-checking Verilog simulation testbench")
    parser.add_argument("--run-fill", nargs="?", const="__DEFAULT__", help="Run Decap insertion and metal layer density fill")
    parser.add_argument("--run-gds", nargs="?", const="__DEFAULT__", help="Run GDSII stream-out")
    parser.add_argument("--run-lvs", nargs="?", const="__DEFAULT__", help="Run Layout Versus Schematic (LVS) verification")
    parser.add_argument("--run-gls", nargs="?", const="__DEFAULT__", help="Run Gate-Level Simulation (GLS) with timing annotation")
    parser.add_argument("--export-sdf", nargs="?", const="__DEFAULT__", metavar="PATH", help="Export Standard Delay Format (SDF) timing file")
    parser.add_argument("--tapeout", "--run-tapeout", dest="run_tapeout", nargs="?", const="__DEFAULT__", help="Run final foundry tapeout packaging and checklist audit")
    parser.add_argument("--run-all", nargs="?", const="__DEFAULT__", help="Run full ASIC flow (RTL to GDS & Tapeout)")
    parser.add_argument("--step", nargs="+", help="Run generic flow step: <step_name> [project]")

    # Floorplan fine-tuning arguments
    parser.add_argument("--die-area", help="Die area bounding box: 'x1 y1 x2 y2'")
    parser.add_argument("--core-margin", type=float, default=10.0, help="Core margin in microns")
    parser.add_argument("--fence", nargs="+", action="append", help="Fence region: 'module x1 y1 x2 y2 [-density D] [--halo L R B T]'")
    parser.add_argument("--region", nargs="+", action="append", help="Region: 'module x1 y1 x2 y2 [-density D] [-type inclusive|exclusive]'")
    parser.add_argument("--blockage", nargs="+", action="append", help="Blockage: 'x1 y1 x2 y2 [-type hard|soft|partial] [-density D]'")

    # TCL fine-tuning argument
    parser.add_argument("--tcl", nargs="?", const="__EDIT__", default=None,
                        help="TCL fine-tuning: omit for batch run, pass string/file, or pass alone to open LazyVim TUI editor")

    # Project registry commands
    parser.add_argument("--projects", "--list", dest="list_projects", action="store_true",
                        help="List all registered ASIC projects (shared across CLI and GUI)")
    parser.add_argument("--register", metavar="PATH", help="Register an existing ASIC project in the registry")
    parser.add_argument("--unregister", metavar="PATH", help="Remove an ASIC project from the registry")

    # Interactive Shell mode
    parser.add_argument("-i", "--shell", "--interactive", dest="interactive_shell", nargs="?", const="__DEFAULT__",
                        help="Launch interactive Silis TUI shell with tab autocomplete for all Silis & TCL commands")

    parser.add_argument("-h", "--help", action="store_true", help="Show this help message")

    # Check if any known CLI command was passed
    known_flags = [
        "--init", "--run-synth", "--run-init", "--run-floorplan", "--run-tapcells",
        "--run-pdn", "--run-iopins", "--run-place", "--run-cts", "--run-route",
        "--run-antenna", "--run-sta", "--run-pat", "--run-drc", "--run-dft", "--dft",
        "--export-stil", "--export-tb", "--run-fill", "--run-gds", "--run-lvs", "--run-gls",
        "--export-sdf", "--tapeout", "--run-tapeout", "--run-all", "--step",
        "--projects", "--list", "--register", "--unregister", "-i", "--shell", "--interactive", "-h", "--help"
    ]
    if not any(arg in known_flags for arg in args_list):
        return False


    args, unknown = parser.parse_known_args(args_list)

    if args.help:
        parser.print_help()
        return True

    import project_registry

    if args.list_projects:
        projects = project_registry.get_registered_projects()
        print("\n" + "=" * 90)
        print("  📂 SILIS REGISTERED ASIC PROJECTS (CLI & GUI)")
        print("=" * 90)
        if not projects:
            print("  No projects currently registered. Create one with 'silis --init' or via the GUI.")
        else:
            print(f"  {'#':<3} {'PROJECT NAME':<20} {'TOP MODULE':<18} {'PDK':<10} {'STATUS':<12} {'LOCATION'}")
            print("  " + "─" * 86)
            for idx, p in enumerate(projects, 1):
                status_parts = []
                if p["has_netlist"]: status_parts.append("Synth")
                if p["has_def"]: status_parts.append("DEF")
                status_str = "+".join(status_parts) if status_parts else "New"
                print(f"  {idx:<3} {p['name']:<20} {p['top']:<18} {p['pdk']:<10} {status_str:<12} {p['path']}")
        print("=" * 90 + "\n")
        return True

    if args.register:
        ok = project_registry.register_project(args.register)
        if ok:
            print(f"[SUCCESS] Registered project '{args.register}' in Silis project registry.")
        else:
            print(f"[ERR] Failed to register '{args.register}'. Ensure directory exists.")
            sys.exit(1)
        return True

    if args.unregister:
        ok = project_registry.unregister_project(args.unregister)
        if ok:
            print(f"[SUCCESS] Unregistered project '{args.unregister}' from Silis project registry.")
        else:
            print(f"[ERR] Project '{args.unregister}' was not found in registry.")
            sys.exit(1)
        return True

    # Interactive Shell mode
    if getattr(args, "interactive_shell", None) is not None:
        target_proj = args.interactive_shell if args.interactive_shell != "__DEFAULT__" else None
        import tui_repl
        tui_repl.run_interactive_shell(target_proj)
        return True

    # 1. Project Initialization

    if args.init is not None:
        if args.init == "__INTERACTIVE__" and not args.rtl and not args.top:
            cli_project.run_interactive_init()
        else:
            proj_name = args.init if args.init != "__INTERACTIVE__" else (args.top or "my_design")
            macros_flat = [m for sub in (args.macro or []) for m in (sub if isinstance(sub, list) else [sub])]
            res = cli_project.run_cli_init(
                name=proj_name, rtl=args.rtl, tb=args.tb, sdc=args.sdc,
                pdk=args.pdk, macros=macros_flat, top=args.top
            )
            if not res:
                sys.exit(1)
        return True

    # 2. Flow Step Runner
    step_map = {
        "run_synth": "synth",
        "run_init": "init",
        "run_floorplan": "floorplan",
        "run_tapcells": "tapcells",
        "run_pdn": "pdn",
        "run_iopins": "iopins",
        "run_place": "place",
        "run_cts": "cts",
        "run_route": "route",
        "run_antenna": "antenna",
        "run_sta": "sta",
        "run_pat": "pat",
        "run_drc": "drc",
        "run_dft": "dft",
        "run_fill": "fill",
        "run_gds": "gds",
        "run_lvs": "lvs",
        "run_gls": "gls",
        "export_sdf": "sdf",
        "run_tapeout": "tapeout",
        "run_all": "all",
    }

    active_step = None
    target_project = None

    for attr, sname in step_map.items():
        val = getattr(args, attr, None)
        if val is not None:
            active_step = sname
            target_project = val if val != "__DEFAULT__" else None
            break

    if not active_step and args.step:
        active_step = args.step[0].lower()
        target_project = args.step[1] if len(args.step) > 1 else None

    if target_project and target_project.endswith(".sdf"):
        export_val = target_project
        target_project = unknown[0] if unknown else None
        args.export_sdf = export_val
    elif unknown and not target_project:
        target_project = unknown[0]

    if not active_step:
        return False

    # Locate project file
    proj_file = cli_flow.find_project_file(target_project)
    if not proj_file:
        print(f"[ERR] No 'silis.silisproj' found for project '{target_project or '.'}'.")
        print("Run 'silis --init' first to create a project.")
        sys.exit(1)

    runner = cli_flow.HeadlessASICRunner(proj_file)
    step_success = True
    try:
        if active_step == "synth":
            step_success = runner.run_synthesis(tcl_arg=args.tcl, dft=getattr(args, "dft", False))
        elif active_step == "dft":
            step_success = runner.run_step("DFT")
            top = runner.config.get("top_module", "design")
            if getattr(args, "export_stil", None):
                src = os.path.join(runner.proj_dir, "results", f"{top}_atpg.stil")
                if os.path.isfile(src):
                    import shutil
                    shutil.copy2(src, args.export_stil)
                    print(f"[DFT EXPORT] Saved STIL patterns to: {args.export_stil}")
            if getattr(args, "export_tb", None):
                src = os.path.join(runner.proj_dir, "results", f"{top}_atpg_tb.v")
                if os.path.isfile(src):
                    import shutil
                    shutil.copy2(src, args.export_tb)
                    print(f"[DFT EXPORT] Saved ATPG Verilog TB to: {args.export_tb}")
        elif active_step == "sdf":
            step_success = runner.run_step("sdf")
            top = runner.config.get("top_module", "design")
            export_target = getattr(args, "export_sdf", None)
            if export_target and export_target != "__DEFAULT__":
                src = os.path.join(runner.proj_dir, "results", f"{top}.sdf")
                if os.path.isfile(src):
                    import shutil
                    shutil.copy2(src, export_target)
                    print(f"[SDF EXPORT] Saved SDF timing file to: {export_target}")
        elif active_step == "init":
            step_success = runner.run_init(tcl_arg=args.tcl)
        elif active_step == "floorplan":
            die_box = None
            if args.die_area:
                die_box = [float(x) for x in args.die_area.split()]

            # Flatten multi-argument lists
            macro_strings = [m for sub in (args.macro or []) for m in (sub if isinstance(sub, list) else [sub])]
            fence_strings = [m for sub in (args.fence or []) for m in (sub if isinstance(sub, list) else [sub])]
            region_strings = [m for sub in (args.region or []) for m in (sub if isinstance(sub, list) else [sub])]
            blockage_strings = [m for sub in (args.blockage or []) for m in (sub if isinstance(sub, list) else [sub])]

            macros_parsed = parse_macro_flag(macro_strings)
            fences_parsed = parse_region_flag(fence_strings, is_fence_default=True)
            regions_parsed = parse_region_flag(region_strings, is_fence_default=False)
            blockages_parsed = parse_blockage_flag(blockage_strings)

            all_regions = fences_parsed + regions_parsed
            if not runner.run_init():
                step_success = False
            else:
                step_success = runner.run_floorplan(
                    tcl_arg=args.tcl, die_area=die_box, core_margin=args.core_margin,
                    macros=macros_parsed, regions=all_regions, blockages=blockages_parsed
                )
        elif active_step == "all":
            if runner.run_synthesis(tcl_arg=args.tcl, dft=getattr(args, "dft", False)):
                if runner.run_init():
                    runner.run_floorplan()
                    for st in ["tapcells", "pdn", "iopins", "place", "cts", "route", "fill", "gds", "sta", "drc", "dft", "lvs", "gls", "tapeout"]:
                        if not runner.run_step(st):
                            step_success = False
                            break
                else:
                    step_success = False
            else:
                step_success = False
        else:
            step_success = runner.run_step(active_step, tcl_arg=args.tcl)
    finally:
        runner.close()

    if not step_success:
        sys.exit(1)

    return True


if __name__ == "__main__":
    if not handle_cli(sys.argv[1:]):
        print("Silis CLI: Please provide arguments or run with --help or --projects.")
