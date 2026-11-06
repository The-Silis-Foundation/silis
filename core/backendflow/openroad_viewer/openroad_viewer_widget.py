"""
Silis Authentic OpenROAD Layout Viewer Container Widget
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2020-2025, The OpenROAD Authors

Special Tribute & Acknowledgment:
This module directly embeds the authentic upstream OpenROAD LayoutViewer
and RenderThread developed by The OpenROAD Authors (https://theopenroadproject.org).
Silis extends its deep gratitude and appreciation to the OpenROAD project
maintainers and contributors for their outstanding, ground-breaking work
in open-source ASIC physical design automation.
"""

import os
import sys
import subprocess
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6 import sip

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

class OpenRoadLayoutViewerWidget(QWidget):
    """
    Direct in-process native Qt6 QWidget embedding the genuine OpenROAD LayoutViewer.
    Zero emulation, zero knockoffs, 100% upstream OpenROAD C++ rendering pipeline.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self._wrapper = None
        self._native_viewer = None
        self._loaded = False
        self._current_odb = None

        try:
            import silis_openroad_viewer as orv
            self._wrapper = orv.LayoutViewerWrapper(sip.unwrapinstance(self))
            ptr = self._wrapper.get_qwidget_ptr()
            self._native_viewer = sip.wrapinstance(ptr, QWidget)
            layout.addWidget(self._native_viewer)
            self._loaded = True

            # Connect selection callback
            self._wrapper.set_on_select_callback(self._on_item_selected)
        except Exception as e:
            fallback_label = QLabel(f"Failed to load authentic OpenROAD LayoutViewer:\n{e}")
            fallback_label.setStyleSheet("color: red; padding: 20px; font-family: monospace;")
            layout.addWidget(fallback_label)

    def _on_item_selected(self, type_name: str, name: str):
        # Update parent status or terminal if available
        parent = self.parent()
        while parent:
            if hasattr(parent, 'term_log') and hasattr(parent.term_log, 'append'):
                parent.term_log.append(f"[OPENROAD SELECT] {type_name}: {name}")
                break
            parent = parent.parent()

    def load_odb(self, odb_path: str) -> bool:
        if not self._wrapper or not os.path.isfile(odb_path):
            return False
        ok = self._wrapper.load_odb(odb_path)
        if ok:
            self._current_odb = odb_path
        return ok

    def ensure_odb_and_load(self, def_path: str, active_pdk: dict = None, proj_root: str = None) -> bool:
        """
        Synthesizes an OpenDB binary from LEFs + DEF if needed, then loads it into the LayoutViewer.
        This provides 100% macro/cell internals, pins, obstructions, and nets.
        """
        if not self._wrapper or not os.path.isfile(def_path):
            return False

        if not proj_root:
            proj_root = os.path.dirname(os.path.dirname(os.path.abspath(def_path)))

        odb_path = os.path.join(proj_root, "results", "temp.odb")
        os.makedirs(os.path.dirname(odb_path), exist_ok=True)

        # If ODB exists and is newer than DEF, load directly
        if os.path.isfile(odb_path) and os.path.getmtime(odb_path) >= os.path.getmtime(def_path):
            return self.load_odb(odb_path)

        # Generate ODB via OpenROAD headless batch execution
        tcl_script = os.path.join(proj_root, "results", "generate_odb.tcl")
        tlef = active_pdk.get("tlef", "") if active_pdk else ""
        lef = active_pdk.get("lef", "") if active_pdk else ""

        # Default Sky130 paths if not provided
        if not tlef or not os.path.isfile(tlef):
            tlef = "/home/econsystems/.silis/pdks/sky130A/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef"
        if not lef or not os.path.isfile(lef):
            lef = "/home/econsystems/.silis/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef"

        tcl_cmds = []
        if os.path.isfile(tlef):
            tcl_cmds.append(f'read_lef "{tlef}"')
        if os.path.isfile(lef):
            tcl_cmds.append(f'read_lef "{lef}"')

        # IO LEFs and SRAM LEFs
        pdk_dir = os.path.dirname(lef)
        libs_ref = os.path.abspath(os.path.join(pdk_dir, "..", ".."))
        io_dir = os.path.join(libs_ref, "sky130_fd_io", "lef")
        if os.path.isdir(io_dir):
            for ef_io in ["sky130_ef_io.lef", "sky130_fd_io.lef"]:
                io_lef_path = os.path.join(io_dir, ef_io)
                if os.path.isfile(io_lef_path):
                    tcl_cmds.append(f'read_lef "{io_lef_path}"')

        sram_dir = os.path.join(libs_ref, "sky130_sram_macros", "lef")
        if os.path.isdir(sram_dir):
            for s_lef in os.listdir(sram_dir):
                if s_lef.endswith(".lef"):
                    tcl_cmds.append(f'read_lef "{os.path.join(sram_dir, s_lef)}"')

        # Declare IO sites
        tcl_cmds.append('make_fake_io_site -name IO_SITE -width 1 -height 200')
        tcl_cmds.append('make_fake_io_site -name IO_CSITE -width 200 -height 204')
        tcl_cmds.append(f'read_def -continue_on_errors "{def_path.replace(chr(92), "/")}"')
        tcl_cmds.append(f'write_db "{odb_path.replace(chr(92), "/")}"')
        tcl_cmds.append('exit')

        try:
            with open(tcl_script, "w") as f:
                f.write("\n".join(tcl_cmds) + "\n")

            res = subprocess.run(["openroad", tcl_script], cwd=proj_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            if res.returncode == 0 and os.path.isfile(odb_path):
                return self.load_odb(odb_path)
        except Exception as e:
            print(f"[OpenRoadLayoutViewerWidget] Error generating ODB: {e}")

        # If already existing ODB, fallback load
        if os.path.isfile(odb_path):
            return self.load_odb(odb_path)
        return False

    def fit(self):
        if self._wrapper:
            self._wrapper.fit()
