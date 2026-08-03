import os
import sys

class DummyIDE:
    def get_proj_root(self, ctx): return "/tmp"
    def get_context(self): return "top", "top"

class SSAForge:
    DEFAULT_PDK = "sky130_fd_sc_hd"
    ALIASES = {}
    @staticmethod
    def get_cts_cmd(p, l): return "clock_tree_synthesis"

class BackendWidget:
    def __init__(self):
        self.ide = DummyIDE()
        self.active_pdk = {"name": "sky130"}
    def ask_command(self, title, label, text):
        print(f"DIALOG OPENED FOR {title} with text:\n{text}")
        return text, True
    def send_command_internal(self, text):
        pass

    def run_flow_step(self, step_name):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        results_dir = os.path.join(proj_root, "results"); os.makedirs(results_dir, exist_ok=True)
        reports_dir = os.path.join(proj_root, "reports"); os.makedirs(reports_dir, exist_ok=True)
        def_abs_path = os.path.join(results_dir, "temp.def").replace("\\", "/")
        write_cmd = f"write_def \"{def_abs_path}\""

        cmd = ""
        pdk_name = self.active_pdk.get('name', SSAForge.DEFAULT_PDK) if self.active_pdk else SSAForge.DEFAULT_PDK
        lib_path = self.active_pdk.get('lib', None) if self.active_pdk else None

        def load_template(filename, replacements):
            template_path = os.path.join("/home/jerome/silis/backendflow/flow", filename)
            try:
                with open(template_path, 'r') as f:
                    content = f.read()
                for k, v in replacements.items():
                    content = content.replace(f"{{{k}}}", str(v))
                return content
            except Exception as e:
                return f"# Error loading {filename}: {e}"

        if step_name == "CTS":
            cts_cmd = SSAForge.get_cts_cmd(pdk_name, lib_path)
            cmd = load_template("cts.tcl", {"cts_cmd": cts_cmd, "write_cmd": write_cmd})
        elif step_name == "Route":
            guide_path = os.path.join(results_dir, "route.guide").replace("\\", "/")
            drc_path = os.path.join(reports_dir, "drc.rpt").replace("\\", "/")
            fix_script = os.path.join(proj_root, "fix.tcl").replace("\\", "/")
            try: 
                with open(fix_script, 'w') as f: f.write("test")
            except: pass
            cmd = load_template("route.tcl", {"fix_script": fix_script, "guide_path": guide_path, "drc_path": drc_path, "write_cmd": write_cmd})

        if cmd:
            cmd = cmd.replace("; ", "\n").replace(";", "\n")
            text, ok = self.ask_command(f"Run {step_name}", "Confirm TCL Command:", cmd)

bw = BackendWidget()
bw.run_flow_step("CTS")
bw.run_flow_step("Route")
