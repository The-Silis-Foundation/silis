import sys
from PyQt6.QtWidgets import QApplication
from backendflow.flow.backendflow import BackendWidget

class DummyIDE:
    def __init__(self):
        self.project_config = {}
        self.active_pdk = {"name": "sky130_fd_sc_hd", "lib": "", "tlef": "", "lef": ""}
        self.pdk_mgr = None
        self.current_file = "test.v"
    def get_proj_root(self, ctx): return "/tmp"
    def get_context(self): return "top", "top"

app = QApplication(sys.argv)
w = BackendWidget(DummyIDE())
try:
    w.run_flow_step("CTS")
    print("CTS OK")
except Exception as e:
    print("CTS ERROR:", e)
