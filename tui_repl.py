"""
tui_repl.py
Interactive EDA & TCL Command Shell for Silis with real-time Tab Autocomplete.
Supports:
  - Tab autocomplete for all Silis commands & flags (--run-*, --init, --projects, etc.)
  - Tab autocomplete for all OpenROAD, OpenSTA, and Yosys TCL commands (800+ commands)
  - Tab autocomplete for project names, file paths, and macro options
  - Command history with persistent ~/.silis_history
  - Clean ANSI-styled prompt with current project and target PDK status
  - Direct execution of Silis flow steps or arbitrary OpenROAD/TCL commands
"""

import os
import sys
import glob
import shlex
import readline
import subprocess
import json

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(REPO_ROOT, "third-party", "python-packages")
if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

# ANSI styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_MAGENTA = "\033[35m"
C_BLUE = "\033[34m"
C_GRAY = "\033[90m"

# Core Silis REPL & CLI commands
SILIS_COMMANDS = [
    # Top-level REPL commands
    "help", "status", "clear", "exit", "quit", "project", "projects", "pdk",
    "init", "synth", "floorplan", "tapcells", "pdn", "iopins", "place",
    "cts", "route", "antenna", "sta", "pat", "drc", "gds", "all",
    "tcl", "openroad", "edit", "edrun", "reset", "opengui", "gui", "bash", "sh",

    # CLI Flags supported in REPL
    "--init", "--run-synth", "--run-init", "--run-floorplan", "--run-tapcells",
    "--run-pdn", "--run-iopins", "--run-place", "--run-cts", "--run-route",
    "--run-antenna", "--run-sta", "--run-pat", "--run-drc", "--run-gds",
    "--run-all", "--step", "--projects", "--list", "--register", "--unregister",
    "--die-area", "--core-margin", "--fence", "--region", "--blockage",
    "--tcl", "--pdk", "--top", "--rtl", "--tb", "--sdc", "--macro"
]

# Standard TCL keywords
TCL_KEYWORDS = [
    "set", "puts", "source", "if", "else", "elseif", "for", "foreach", "while",
    "switch", "proc", "return", "break", "continue", "expr", "catch", "eval",
    "incr", "append", "lappend", "lindex", "llength", "lrange", "lsearch",
    "split", "join", "string", "array", "info", "file", "open", "close",
    "read", "write", "flush", "seek", "tell", "glob", "exec", "error", "exit"
]

# Curated High-Frequency OpenROAD & Yosys TCL commands
BUILTIN_EDA_COMMANDS = [
    # Floorplanning & Placement
    "initialize_floorplan", "make_tracks", "auto_place_pins", "place_pins",
    "global_placement", "detailed_placement", "check_placement", "place_macro",
    "create_voltage_domain", "define_corners", "set_wire_rc", "reorder_scan_chain",
    
    # Tapcells, Endcaps & PDN
    "tapcell", "add_pdn_stripe", "add_pdn_ring", "add_pdn_connect",
    "set_pdn_domain", "pdngen", "define_pdn_grid",
    
    # Clock Tree & Timing Optimization
    "clock_tree_synthesis", "repair_clock_nets", "repair_hold_violations",
    "repair_setup_violations", "repair_design", "repair_tie_fanout",
    "repair_antennas", "buffer_ports", "remove_buffers",
    
    # Global & Detailed Routing
    "global_route", "detailed_route", "estimate_parasitics",
    "write_guides", "read_guides", "set_routing_layers",
    
    # Signoff, STA, DRC & Stream-out
    "read_liberty", "read_lef", "read_def", "read_sdc", "read_verilog", "read_db",
    "write_def", "write_db", "write_gds", "write_spef",
    "report_checks", "report_power", "report_tns", "report_wns", "report_worst_slack",
    "report_clock_skew", "report_floating_nets", "check_antennas", "drc_check",
    
    # Yosys Synthesis Commands
    "synth", "dfflegalize", "dfflibmap", "abc", "abc9", "stat", "flatten",
    "clean", "opt", "opt_clean", "opt_merge", "techmap", "tee", "plugin",
    "ghdl", "read_verilog", "write_verilog"
]

# Common EDA Command Flags
EDA_FLAGS = [
    "-die_area", "-core_area", "-site", "-core_margin",
    "-density", "-halo", "-module", "-box", "-region",
    "-grid", "-layer", "-layers", "-width", "-pitch", "-offset",
    "-hor_layers", "-ver_layers", "-min_distance",
    "-guide_file", "-congestion_iterations", "-output_drc",
    "-bottom_routing_layer", "-top_routing_layer", "-allow_congestion",
    "-root_buf", "-buf_list", "-sink_clustering_enable",
    "-iterations", "-diode_cell",
    "-corner", "-path_delay", "-fields", "-slack", "-endpoint",
    "-report_file", "-top", "-liberty", "-noattr"
]


def load_dynamic_openroad_commands():
    """Extracts live commands dynamically from OpenROAD subprocess."""
    cmds = set(BUILTIN_EDA_COMMANDS)
    try:
        p = subprocess.Popen(
            ["openroad"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, _ = p.communicate("puts [info commands]\nexit\n", timeout=3)
        for line in out.splitlines():
            if "set_wire_rc" in line or "global_route" in line or "read_lef" in line:
                for token in line.split():
                    token = token.strip()
                    if token and not token.startswith("_") and not token.startswith("::"):
                        cmds.add(token)
    except Exception:
        pass
    return sorted(list(cmds))


class SilisCompleter:
    """Readline tab autocompleter for Silis REPL."""
    def __init__(self, runner=None):
        self.runner = runner
        self.eda_commands = load_dynamic_openroad_commands()
        self.all_words = sorted(list(set(
            SILIS_COMMANDS + TCL_KEYWORDS + self.eda_commands + EDA_FLAGS
        )))
        self.matches = []

    def complete(self, text, state):
        if state == 0:
            line = readline.get_line_buffer()
            begidx = readline.get_begidx()
            endidx = readline.get_endidx()
            
            # Extract true current word from line buffer
            current_word = line[begidx:endidx]
            # If word is preceded by '-', expand prefix
            if begidx > 0 and line[begidx - 1] == "-":
                dash_start = begidx - 1
                while dash_start > 0 and line[dash_start - 1] == "-":
                    dash_start -= 1
                current_word = line[dash_start:endidx]
            
            line_before = line[:begidx].strip()
            query = current_word if current_word else text

            # 1. File/path autocompletion if typing a path or following file keywords
            if "/" in query or query.startswith(".") or query.startswith("~") or any(line_before.endswith(k) for k in ["source", "read_def", "read_lef", "read_sdc", "write_def", "--tcl", "--rtl", "--tb", "--sdc"]):
                self.matches = self._complete_path(query)
            elif not line_before:
                # First word: prioritize top-level Silis and primary TCL commands
                candidates = SILIS_COMMANDS + TCL_KEYWORDS + self.eda_commands
                self.matches = [c for c in candidates if c.startswith(query)]
            elif query.startswith("-"):
                # Flag autocompletion
                candidates = [f for f in EDA_FLAGS if f.startswith(query)] + [s for s in SILIS_COMMANDS if s.startswith(query)]
                self.matches = candidates
            else:
                # General dictionary matching
                self.matches = [w for w in self.all_words if w.startswith(query)]

            self.matches = sorted(list(set(self.matches)))

        try:
            return self.matches[state]
        except IndexError:
            return None


    def _complete_path(self, text):
        path = os.path.expanduser(text)
        dirname, rest = os.path.split(path)
        search_dir = dirname if dirname else "."
        try:
            entries = os.listdir(search_dir)
            matches = []
            for e in entries:
                if e.startswith(rest):
                    full = os.path.join(dirname, e) if dirname else e
                    if os.path.isdir(full):
                        full += "/"
                    matches.append(full)
            return matches
        except Exception:
            return []


class SilisInteractiveShell:
    """Interactive TUI REPL for Silis ASIC Flow."""
    def __init__(self, project_arg=None):
        import cli_flow
        self.cli_flow = cli_flow
        self.proj_file = cli_flow.find_project_file(project_arg)
        self.runner = None
        if self.proj_file:
            try:
                try:
                    from .env.gui_driver import SilisGUIDriver
                except ImportError:
                    env_path = os.path.join(REPO_ROOT, ".env")
                    if env_path not in sys.path:
                        sys.path.insert(0, env_path)
                    from gui_driver import SilisGUIDriver
                self.runner = SilisGUIDriver(self.proj_file, verbose=True)
            except Exception as e:
                try:
                    self.runner = cli_flow.HeadlessASICRunner(self.proj_file)
                    # Flush pending OpenROAD background output so prompt is cleanly rendered
                    if self.runner.backend and self.runner.backend.proc:
                        self.runner.backend.proc.waitForReadyRead(600)
                except Exception as e2:
                    print(f"{C_RED}[WARN] Failed to initialize project runner: {e2}{C_RESET}")

        self.completer = SilisCompleter(self.runner)
        self.history_file = os.path.expanduser("~/.silis_history")
        self._setup_readline()

    def _setup_readline(self):
        readline.set_completer(self.completer.complete)
        readline.set_completer_delims(" \t\n\"';=")
        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set show-all-if-ambiguous on")
        readline.parse_and_bind("set completion-ignore-case off")
        if os.path.exists(self.history_file):
            try:
                readline.read_history_file(self.history_file)
            except Exception:
                pass

    def _save_history(self):
        try:
            readline.write_history_file(self.history_file)
        except Exception:
            pass

    def _print_banner(self):
        proj_name = "None"
        pdk_name = "None"
        if self.runner and self.runner.config:
            proj_name = self.runner.config.get("top_module", self.runner.config.get("project_name", "Unknown"))
            pdk_name = self.runner.config.get("pdk", "sky130")

        banner = f"""
{C_CYAN}{C_BOLD}╔════════════════════════════════════════════════════════════════════════════╗
║                   SILIS — ASIC SILICON SCAFFOLD INTERACTIVE SHELL          ║
║      Tab Autocomplete for Silis Flow & OpenROAD / Yosys TCL Commands       ║
╚════════════════════════════════════════════════════════════════════════════╝{C_RESET}
  {C_BOLD}Active Design:{C_RESET} {C_GREEN}{proj_name}{C_RESET}   {C_BOLD}PDK:{C_RESET} {C_YELLOW}{pdk_name}{C_RESET}   {C_GRAY}(Type 'help' or press <TAB> twice for commands){C_RESET}
"""
        print(banner)

    def _print_help(self):
        help_text = f"""
{C_BOLD}AVAILABLE COMMANDS & FLOW STEPS:{C_RESET}

  {C_CYAN}Flow Steps:{C_RESET}
    {C_GREEN}synth{C_RESET}      : Run Yosys RTL synthesis
    {C_GREEN}floorplan{C_RESET}  : Run floorplanning, macro auto-placement & fences
    {C_GREEN}tapcells{C_RESET}   : Insert well-tap and endcap cells
    {C_GREEN}pdn{C_RESET}        : Synthesize Power Distribution Network stripes
    {C_GREEN}iopins{C_RESET}     : Place boundary IO pins
    {C_GREEN}place{C_RESET}      : Global & detailed standard cell placement
    {C_GREEN}cts{C_RESET}        : Clock Tree Synthesis (TritonCTS)
    {C_GREEN}route{C_RESET}      : Global & detailed routing (TritonRoute)
    {C_GREEN}antenna{C_RESET}    : Check antenna rule violations
    {C_GREEN}sta / pat{C_RESET}  : Multi-corner Static Timing & Power Analysis
    {C_GREEN}drc{C_RESET}        : Magic layout DRC verification
    {C_GREEN}gds{C_RESET}        : Stream-out GDSII stream file
    {C_GREEN}all{C_RESET}        : Execute entire flow from RTL to GDS

  {C_CYAN}Interactive & TCL Shell:{C_RESET}
    {C_YELLOW}edrun [tcl/file]{C_RESET} : Open script in terminal editor (nano/vi/custom); runs script on exit
    {C_YELLOW}edit [step]{C_RESET}      : Open step script in terminal editor for fine-tuning
    {C_YELLOW}editor [cmd]{C_RESET}     : View or set preferred terminal editor (e.g. `editor nano`, `editor vi`, `editor nvim`)
    {C_YELLOW}opengui [tab]{C_RESET}    : Open Silis GUI at current project stage (synth, layout, compile, etc.)
    {C_YELLOW}tcl <command>{C_RESET}    : Execute arbitrary TCL in OpenROAD (e.g. `tcl report_checks -path_delay max`)
    {C_YELLOW}projects{C_RESET}         : List all registered ASIC projects
    {C_YELLOW}project <name>{C_RESET}   : Switch active design project
    {C_YELLOW}reset{C_RESET}            : Reboot OpenROAD backend process

  {C_CYAN}General:{C_RESET}
    {C_BLUE}status{C_RESET}   : Show active project, top module, and checkpoint status
    {C_BLUE}clear{C_RESET}    : Clear terminal screen
    {C_BLUE}exit / quit{C_RESET}: Exit interactive shell
"""
        print(help_text)

    def _print_status(self):
        if not self.runner:
            print(f"{C_RED}[ERR] No active project loaded. Use 'project <name>' or 'projects' to switch.{C_RESET}")
            return
        cfg = self.runner.config
        root = self.runner.proj_dir
        top = cfg.get("top_module", "Unknown")
        pdk = cfg.get("pdk", "Unknown")
        has_v = os.path.exists(os.path.join(root, "netlist", f"{top}_netlist.v"))
        has_def = os.path.exists(os.path.join(root, "results", "temp.def"))
        has_gds = os.path.exists(os.path.join(root, "results", "design.gds")) or os.path.exists(os.path.join(root, "results", f"{top}.gds"))

        print("\n" + "=" * 60)
        print(f" {C_BOLD}SILIS PROJECT STATUS: {top}{C_RESET}")
        print("=" * 60)
        print(f"  • Project Directory: {root}")
        print(f"  • Top Module:        {top}")
        print(f"  • Target PDK:        {pdk}")
        print(f"  • Netlist:           {C_GREEN+'Present' if has_v else C_RED+'Missing'}{C_RESET}")
        print(f"  • Layout DEF:        {C_GREEN+'Present' if has_def else C_RED+'Missing'}{C_RESET}")
        print(f"  • GDS Stream-out:    {C_GREEN+'Present' if has_gds else C_GRAY+'Not Generated'}{C_RESET}")
        print("=" * 60 + "\n")

    def run(self):
        self._print_banner()
        while True:
            try:
                top_name = self.runner.config.get("top_module", "silis") if (self.runner and self.runner.config) else "silis"
                prompt = f"{C_CYAN}silis{C_RESET}:{C_YELLOW}{top_name}{C_RESET}❯ "
                line = input(prompt).strip()
            except (KeyboardInterrupt, EOFError):
                print("\n[Exiting Silis Shell]")
                break

            if not line:
                continue

            self._save_history()
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ["exit", "quit", "q"]:
                break
            elif cmd in ["help", "h", "?"]:
                self._print_help()
            elif cmd in ["clear", "cls"]:
                os.system("clear")
            elif cmd.startswith("!"):
                # Raw Linux shell escape: !ls -la, !top, etc.
                subprocess.run(line[1:].strip(), shell=True, executable="/bin/bash")
                continue
            elif cmd in ["bash", "sh"]:
                # If typed alone, launch subshell; if arguments passed, execute in bash
                if not arg.strip():
                    print(f"{C_CYAN}[SILIS] Spawning subshell. Type 'exit' to return to Silis REPL.{C_RESET}")
                    subprocess.run(["/bin/bash"])
                else:
                    subprocess.run(arg.strip(), shell=True, executable="/bin/bash")
                continue
            elif cmd == "cd":
                # Native directory change: syncs both Python process and OpenROAD engine
                target_dir = os.path.expanduser(arg.strip()) if arg.strip() else os.path.expanduser("~")
                try:
                    os.chdir(target_dir)
                    if self.runner and self.runner.backend:
                        self.runner.backend.send_command_internal(f'cd "{target_dir}"')
                    print(f"{C_GRAY}[CWD: {os.getcwd()}]{C_RESET}")
                except Exception as e:
                    print(f"{C_RED}[ERR] cd: {e}{C_RESET}")
                continue
            elif cmd in ["ls", "pwd", "mkdir", "rm", "rmdir", "cp", "mv", "cat", "less", "head", "tail", "grep", "find", "tree", "echo", "which", "git", "chmod", "export", "sed", "awk"]:
                # Native Linux utilities and bash pipeline pass-through
                subprocess.run(line, shell=True, executable="/bin/bash")
                continue
            elif cmd == "status":
                self._print_status()
            elif cmd in ["projects", "list"]:
                import project_registry
                projects = project_registry.get_registered_projects()
                print("\n" + "=" * 80)
                print("  📂 REGISTERED ASIC PROJECTS")
                print("=" * 80)
                for idx, p in enumerate(projects, 1):
                    print(f"  [{idx}] {p['name']:<20} {p['top']:<16} {p['pdk']:<10} {p['path']}")
                print("=" * 80 + "\n")
            elif cmd == "project":
                if not arg:
                    print(f"{C_RED}[ERR] Usage: project <name_or_path>{C_RESET}")
                    continue
                new_proj = self.cli_flow.find_project_file(arg)
                if new_proj:
                    if self.runner:
                        self.runner.close()
                    self.proj_file = new_proj
                    try:
                        try:
                            from .env.gui_driver import SilisGUIDriver
                        except ImportError:
                            env_path = os.path.join(REPO_ROOT, ".env")
                            if env_path not in sys.path:
                                sys.path.insert(0, env_path)
                            from gui_driver import SilisGUIDriver
                        self.runner = SilisGUIDriver(self.proj_file, verbose=True)
                    except Exception:
                        self.runner = self.cli_flow.HeadlessASICRunner(self.proj_file)
                    print(f"{C_GREEN}[SUCCESS] Switched active project to '{self.runner.config.get('top_module')}'{C_RESET}")
                else:
                    print(f"{C_RED}[ERR] Project '{arg}' not found.{C_RESET}")
            elif cmd in ["opengui", "gui"]:
                proj_path = self.proj_file
                if not proj_path and self.runner:
                    proj_path = self.runner.proj_file
                if not proj_path:
                    print(f"{C_RED}[ERR] No active project loaded to open in GUI.{C_RESET}")
                    continue
                
                # Determine target tab if explicitly requested or auto-detect based on stage
                tab_target = arg.strip().lower() if arg.strip() else ""
                cmd_args = [sys.executable, os.path.join(REPO_ROOT, "silis.py"), proj_path]
                if tab_target:
                    cmd_args.extend(["--tab", tab_target])
                
                print(f"{C_GREEN}[SILIS] Spawning Silis GUI for '{os.path.basename(proj_path)}' (Tab: {tab_target or 'Auto-detect current stage'})...{C_RESET}")
                subprocess.Popen(cmd_args, cwd=os.path.dirname(os.path.abspath(proj_path)))
            elif cmd == "reset":
                if self.runner and self.runner.backend:
                    self.runner.backend.reset_backend()
                    print(f"{C_GREEN}[SUCCESS] OpenROAD backend process rebooted.{C_RESET}")
            elif cmd == "init":
                if self.runner:
                    self.runner.run_step("init")
            elif cmd == "synth":
                if self.runner:
                    self.runner.run_synthesis()
            elif cmd == "floorplan":
                if self.runner:
                    self.runner.run_step("floorplan")
            elif cmd in ["tapcells", "pdn", "iopins", "place", "cts", "route", "antenna", "sta", "pat", "drc", "gds"]:
                if self.runner:
                    self.runner.run_step(cmd)
            elif cmd == "all":
                if self.runner:
                    if hasattr(self.runner, 'run_flow'):
                        self.runner.run_flow("all")
                    else:
                        if self.runner.run_synthesis():
                            if self.runner.run_init():
                                self.runner.run_floorplan()
                                for st in ["tapcells", "pdn", "iopins", "place", "cts", "route", "antenna", "sta"]:
                                    if not self.runner.run_step(st):
                                        break
            elif cmd == "tcl":
                if not arg:
                    print(f"{C_RED}[ERR] Usage: tcl <openroad_tcl_command>{C_RESET}")
                    continue
                if self.runner:
                    self.runner.execute_tcl(arg, "interactive")
            elif cmd in ["editor", "set-editor"]:
                # Configure or inspect external terminal editor
                import tui_editor
                if not arg.strip():
                    current_ed = tui_editor.get_preferred_editor()
                    print(f"{C_CYAN}[SILIS] Current editor:{C_RESET} {C_GREEN}{current_ed}{C_RESET}")
                    print(f"{C_GRAY}Usage: editor <nano | vi | vim | nvim | emacs | ...>{C_RESET}")
                else:
                    new_ed = arg.strip()
                    tui_editor.set_preferred_editor(new_ed)
                    print(f"{C_GREEN}[SUCCESS] External editor set to: {new_ed}{C_RESET}")
            elif cmd == "edit":
                import tui_editor
                preferred = tui_editor.get_preferred_editor() or "editor"
                step_to_edit = arg if arg else "floorplan"
                print(f"{C_CYAN}[SILIS] Opening editor ({preferred}) for '{step_to_edit}'...{C_RESET}")
                if self.runner:
                    self.runner.run_step(step_to_edit, tcl_arg="__EDIT__")
            elif cmd == "edrun":
                # edrun [tcl / file]: opens terminal editor (nano with vi fallback / custom) and executes on save & exit
                import tui_editor
                preferred = tui_editor.get_preferred_editor() or "editor"
                init_script = arg.strip()
                # Check if arg is a path to an existing TCL file
                if init_script and os.path.isfile(init_script):
                    try:
                        with open(init_script, "r") as f:
                            init_script = f.read()
                    except Exception:
                        pass
                
                title = f"Silis TCL Interactive Editor - {top_name}"
                res = tui_editor.open_terminal_editor(initial_text=init_script, title=title)
                if res and res.strip():
                    script_to_run = res.strip()
                    # Sanitize line continuations: strip any trailing whitespace after backslashes
                    import re
                    script_to_run = re.sub(r'\\([ \t]+)\n', '\\\\\n', script_to_run)
                    
                    # If the script includes frontend synthesis, execute it first via runner
                    if re.search(r'^\s*synth\b', script_to_run, re.MULTILINE):
                        if self.runner:
                            self.runner.run_synthesis()

                    print(f"\n{C_CYAN}[SILIS] Executing submitted TCL script directly...{C_RESET}")
                    if self.runner:
                        # Ensure design and LEF/DEF/netlist are linked in OpenROAD before executing arbitrary design queries
                        self.runner.ensure_design_loaded()
                        # Write to scratch script and source it in OpenROAD for clean multi-line execution
                        scratch_path = os.path.join(self.runner.proj_dir, ".silis_edrun.tcl")
                        try:
                            with open(scratch_path, "w") as f:
                                f.write(script_to_run + "\n")
                            self.runner.execute_tcl(f'source "{scratch_path}"', "interactive")
                        except Exception as e:
                            print(f"{C_RED}[ERR] Failed to execute edrun script: {e}{C_RESET}")
                    else:
                        print(f"{C_RED}[ERR] No active project runner available to execute script.{C_RESET}")
                else:
                    print(f"{C_GRAY}[Editor] Cancelled or empty. No commands executed.{C_RESET}")
            elif cmd == "source":
                # Special handling for source <script.tcl> in REPL
                script_target = arg.strip().strip('"').strip("'")
                if not os.path.isabs(script_target) and self.runner:
                    cand = os.path.join(self.runner.proj_dir, script_target)
                    if os.path.isfile(cand):
                        script_target = cand
                    elif os.path.isfile(os.path.join(REPO_ROOT, script_target)):
                        script_target = os.path.join(REPO_ROOT, script_target)

                if os.path.isfile(script_target):
                    try:
                        with open(script_target, "r") as f:
                            content = f.read()
                        import re
                        content = re.sub(r'\\([ \t]+)\n', '\\\\\n', content)
                        if re.search(r'^\s*synth\b', content, re.MULTILINE):
                            if self.runner:
                                self.runner.run_synthesis()
                        if self.runner:
                            # If script has initialize_floorplan or link_design, run init if not already linked
                            if re.search(r'\b(initialize_floorplan|link_design)\b', content):
                                self.runner.run_init()
                            else:
                                self.runner.ensure_design_loaded()
                            self.runner.execute_tcl(f'source "{script_target}"', "interactive")
                    except Exception as e:
                        print(f"{C_RED}[ERR] Failed to source script '{script_target}': {e}{C_RESET}")
                else:
                    if self.runner:
                        self.runner.ensure_design_loaded()
                        self.runner.execute_tcl(line, "interactive")
            else:
                # If typed line is a direct TCL command or EDA keyword, execute it in OpenROAD!
                first_word = line.split()[0]
                if first_word in self.completer.eda_commands or first_word in TCL_KEYWORDS:
                    if self.runner:
                        self.runner.execute_tcl(line, "interactive")
                else:
                    # Fallback to standard CLI handling
                    import cli_main
                    try:
                        cli_main.handle_cli(shlex.split(line))
                    except Exception as e:
                        print(f"{C_RED}[ERR] Unknown command '{cmd}': {e}{C_RESET}")

        if self.runner:
            self.runner.close()


def run_interactive_shell(project_arg=None):
    """Entry point for Silis Interactive TUI shell."""
    shell = SilisInteractiveShell(project_arg)
    shell.run()


if __name__ == "__main__":
    proj = sys.argv[1] if len(sys.argv) > 1 else None
    run_interactive_shell(proj)
