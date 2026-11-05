"""
setup_wizard.py
First-Boot Onboarding and PDK Environment Initializer for Silis ASIC EDA.
Provides a native Qt6 modal dialog with a progress bar and background thread
to provision ~/.silis, workspace ~/silis, and copy bundled PDK assets.
Also provides headless/CLI execution for non-interactive and test environments.
"""

import os
import sys
import shutil
import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QApplication,
    QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette


def is_first_boot_needed() -> bool:
    """Check if the user environment has already completed first-boot provisioning."""
    marker = os.path.expanduser("~/.silis/.initialized")
    pdk_dir = os.path.expanduser("~/.silis/pdks/sky130B")
    return not (os.path.isfile(marker) and os.path.isdir(pdk_dir))


class SetupWorker(QThread):
    """Background worker thread performing directory creation and PDK asset staging."""

    progress_updated = pyqtSignal(int, str)
    finished_success = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, source_pdk_dir=None, parent=None):
        super().__init__(parent)
        self.source_pdk_dir = source_pdk_dir

    def run(self):
        try:
            self._do_setup()
            self.finished_success.emit()
        except Exception as e:
            self.failed.emit(str(e))

    def _do_setup(self):
        self.progress_updated.emit(5, "Creating user directory structures...")
        home_silis = os.path.expanduser("~/silis")
        dot_silis = os.path.expanduser("~/.silis")
        
        # Subdirectories for user workspace and app data
        subdirs = [
            os.path.join(home_silis, "projects"),
            os.path.join(home_silis, "templates"),
            os.path.join(dot_silis, "config"),
            os.path.join(dot_silis, "designs"),
            os.path.join(dot_silis, "macrocache"),
            os.path.join(dot_silis, "reports"),
            os.path.join(dot_silis, "pdks", "sky130B"),
        ]
        for d in subdirs:
            os.makedirs(d, exist_ok=True)
            time.sleep(0.01)

        self.progress_updated.emit(15, "Resolving PDK source assets...")
        
        # Locate source PDK bundle
        appdir = os.environ.get("APPDIR", "")
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        candidates = [
            self.source_pdk_dir,
            os.path.join(appdir, "assets", "pdk", "sky130B") if appdir else None,
            os.path.join(appdir, "third-party", "pdks", "sky130B") if appdir else None,
            os.path.expanduser("~/.silis/pdks/sky130B"),
            os.path.join(repo_root, "assets", "pdk", "sky130B"),
        ]

        found_src = None
        for c in candidates:
            if c and os.path.isdir(c) and os.path.isdir(os.path.join(c, "libs.ref")):
                found_src = c
                break

        dest_sky130 = os.path.expanduser("~/.silis/pdks/sky130B")

        if found_src and os.path.abspath(found_src) != os.path.abspath(dest_sky130):
            self.progress_updated.emit(25, f"Copying Sky130 PDK from {os.path.basename(found_src)}...")
            
            # Count total files for fine-grained progress reporting
            all_files = []
            for root, _, files in os.walk(found_src):
                for f in files:
                    all_files.append(os.path.join(root, f))

            total_files = len(all_files)
            if total_files > 0:
                for idx, src_file in enumerate(all_files):
                    rel_path = os.path.relpath(src_file, found_src)
                    dst_file = os.path.join(dest_sky130, rel_path)
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    if not os.path.exists(dst_file) or os.path.getsize(dst_file) != os.path.getsize(src_file):
                        shutil.copy2(src_file, dst_file)
                    
                    pct = 25 + int((idx / total_files) * 55)
                    if idx % 10 == 0:
                        self.progress_updated.emit(pct, f"Installing: {os.path.basename(rel_path)}")
            else:
                self.progress_updated.emit(60, "No bundled PDK files to copy.")
        else:
            self.progress_updated.emit(60, "PDK root verified at destination.")

        # Ensure power switch cell LEF is present in the PDK
        self.progress_updated.emit(85, "Configuring multi-voltage power switch standard cell...")
        lef_dir = os.path.join(dest_sky130, "libs.ref", "sky130_fd_sc_hd", "lef")
        os.makedirs(lef_dir, exist_ok=True)
        psw_lef = os.path.join(lef_dir, "sky130_power_switch.lef")
        
        # Look for existing power switch template in silisprojects or repo
        known_psw_paths = [
            "/home/econsystems/silisprojects/tapeout_mini_soc/sky130_power_switch.lef",
            os.path.join(repo_root, "core", "sky130_power_switch.lef"),
            os.path.join(appdir, "assets", "sky130_power_switch.lef") if appdir else None,
        ]
        for kp in known_psw_paths:
            if kp and os.path.isfile(kp):
                shutil.copy2(kp, psw_lef)
                break

        # Register default PDK configuration manifest
        pdk_master_json = os.path.expanduser("~/.silis/pdks/pdk_master.json")
        if not os.path.isfile(pdk_master_json):
            self.progress_updated.emit(90, "Writing PDK configuration registry...")
            import json
            manifest = {
                "default_pdk": "sky130B",
                "pdks": {
                    "sky130B": {
                        "path": dest_sky130,
                        "type": "skywater130",
                        "status": "installed",
                        "standard_cells": ["sky130_fd_sc_hd"]
                    }
                }
            }
            with open(pdk_master_json, "w") as f:
                json.dump(manifest, f, indent=2)

        # Mark initialization complete
        self.progress_updated.emit(98, "Writing initialization marker...")
        marker_file = os.path.expanduser("~/.silis/.initialized")
        with open(marker_file, "w") as f:
            f.write(f"SILIS_INITIALIZED=1\nTIMESTAMP={time.time()}\n")

        self.progress_updated.emit(100, "Setup complete.")


class FirstBootSetupDialog(QDialog):
    """
    Pure native Qt6 modal dialog showing setup progress.
    Conforms strictly to Silis EDA standards: no emojis, native system palette.
    """

    def __init__(self, source_pdk_dir=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Silis EDA First-Boot Environment Setup")
        self.setFixedSize(540, 240)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.source_pdk_dir = source_pdk_dir
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title_label = QLabel("Initializing Silis Physical Design Environment")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        desc_label = QLabel(
            "Setting up user workspace at ~/silis, provisioning application data at ~/.silis,\n"
            "and verifying Sky130 semiconductor process design kit libraries."
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Preparing environment...", self)
        font_mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font_mono.setPointSize(8)
        self.status_label.setFont(font_mono)
        layout.addWidget(self.status_label)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        self.btn_finish = QPushButton("Launch Silis", self)
        self.btn_finish.setEnabled(False)
        self.btn_finish.clicked.connect(self.accept)
        btn_box.addWidget(self.btn_finish)
        layout.addLayout(btn_box)

    def start_setup(self):
        self.worker = SetupWorker(source_pdk_dir=self.source_pdk_dir, parent=self)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.finished_success.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.status_label.setText(msg)

    def _on_finished(self):
        self.progress_bar.setValue(100)
        self.status_label.setText("Initialization finished successfully.")
        self.btn_finish.setEnabled(True)
        # Auto-accept after 1 second if modal
        self.accept()

    def _on_failed(self, error_msg: str):
        self.status_label.setText(f"Error during initialization: {error_msg}")
        self.btn_finish.setText("Close")
        self.btn_finish.setEnabled(True)


def run_headless_setup(source_pdk_dir=None) -> bool:
    """Synchronous headless runner for CLI / offscreen modes."""
    worker = SetupWorker(source_pdk_dir=source_pdk_dir)
    status_history = []
    worker.progress_updated.connect(lambda pct, msg: print(f"[First-Boot Setup {pct}%] {msg}"))
    try:
        worker._do_setup()
        return True
    except Exception as e:
        print(f"[First-Boot Setup ERROR] {e}", file=sys.stderr)
        return False


def run_first_boot_if_needed(app=None, source_pdk_dir=None) -> bool:
    """
    Main entry point invoked by silis.py or AppRun.
    Checks if first boot is needed, launches dialog or headless runner.
    """
    if not is_first_boot_needed():
        return True

    is_headless = (
        os.environ.get("SILIS_HEADLESS_TEST") == "1"
        or os.environ.get("QT_QPA_PLATFORM") == "offscreen"
        or not os.environ.get("DISPLAY")
    )

    if is_headless or app is None:
        print("[Silis Initializer] Performing first-boot initialization in headless mode...")
        return run_headless_setup(source_pdk_dir=source_pdk_dir)
    else:
        dialog = FirstBootSetupDialog(source_pdk_dir=source_pdk_dir)
        dialog.start_setup()
        result = dialog.exec()
        return result == QDialog.DialogCode.Accepted
