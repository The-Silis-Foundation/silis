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
import stat
import subprocess
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
from PyQt6.QtGui import QFont, QPalette, QFontDatabase


def _find_pdk_source_candidates(variant: str, source_pdk_dir=None) -> list:
    """Returns prioritized candidate directories for a PDK variant, preferring full GDS/Verilog installs."""
    appdir = os.environ.get("APPDIR", "")
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ext_pdk = os.environ.get("SILIS_EXTERNAL_PDK_ROOT", "")
    env_pdk = os.environ.get("PDK_ROOT", "")
    raw = [
        os.path.join(source_pdk_dir, variant) if source_pdk_dir else None,
        os.path.join(appdir, "assets", "pdk", variant) if appdir else None,
        os.path.join(appdir, "third-party", "pdks", variant) if appdir else None,
        os.path.join(repo_root, "assets", "pdk", variant),
        os.path.join(repo_root, "third-party", "pdks", variant),
        os.path.join(ext_pdk, variant) if ext_pdk else None,
        os.path.join(env_pdk, variant) if env_pdk else None,
        os.path.expanduser(f"~/.silis_backup_audit/pdks/{variant}"),
    ]
    # Include Volare versioned installs if present
    volare_glob = sorted(Path(os.path.expanduser("~/.volare")).glob(f"volare/*/versions/*/{variant}")) if os.path.isdir(os.path.expanduser("~/.volare")) else []
    for vg in volare_glob:
        raw.append(str(vg))
    bundled_volare = os.path.join(repo_root, "third-party", "pdks", "volare")
    if os.path.isdir(bundled_volare):
        for vg in sorted(Path(bundled_volare).glob(f"*/versions/*/{variant}")):
            raw.append(str(vg))
    return [c for c in raw if c and os.path.isdir(c)]


def _score_pdk_source(path_str: str) -> int:
    """Scores a PDK source tree by completeness (LEF/lib + GDS + Verilog + Magic/Netgen tech)."""
    score = 0
    if os.path.isdir(os.path.join(path_str, "libs.ref")):
        score += 10
    if os.path.isfile(os.path.join(path_str, "gf180mcu_5LM_1TM_9K_9t_sc.lef")):
        score += 10
    if os.path.isdir(os.path.join(path_str, "libs.tech", "magic")):
        score += 20
    if os.path.isdir(os.path.join(path_str, "libs.tech", "netgen")):
        score += 20
    if os.path.isdir(os.path.join(path_str, "libs.ref", "sky130_fd_io", "gds")):
        score += 40
    if os.path.isdir(os.path.join(path_str, "libs.ref", "sky130_sram_macros", "gds")):
        score += 30
    if os.path.isdir(os.path.join(path_str, "libs.ref", "sky130_fd_sc_hd", "verilog")):
        score += 30
    lib_dir = os.path.join(path_str, "libs.ref", "sky130_fd_sc_hd", "lib")
    if os.path.isdir(lib_dir) and len(os.listdir(lib_dir)) > 1:
        score += 20
    return score


def is_first_boot_needed() -> bool:
    """Check if the user environment has completed full SSAForge-compliant first-boot provisioning."""
    marker = os.path.expanduser("~/.silis/.initialized")
    pdk_a = os.path.expanduser("~/.silis/pdks/sky130A")
    pdk_b = os.path.expanduser("~/.silis/pdks/sky130B")
    ssa_dir = os.path.expanduser("~/.silis/ssa")
    ssa_sky = os.path.join(ssa_dir, "sky130a", "config.json")
    tlef_a = os.path.join(pdk_a, "libs.ref", "sky130_fd_sc_hd", "techlef", "sky130_fd_sc_hd__nom.tlef")
    tlef_b = os.path.join(pdk_b, "libs.ref", "sky130_fd_sc_hd", "techlef", "sky130_fd_sc_hd__nom.tlef")
    sram_a = os.path.join(pdk_a, "libs.ref", "sky130_sram_macros", "lef")
    sram_b = os.path.join(pdk_b, "libs.ref", "sky130_sram_macros", "lef")
    desktop_file = os.path.expanduser("~/.local/share/applications/silis.desktop")
    cli_bin = os.path.expanduser("~/.local/bin/silis")

    has_pdk = (
        os.path.isdir(pdk_a) and (os.path.isfile(tlef_a) or os.path.isdir(os.path.join(pdk_a, "libs.tech")))
        and os.path.isdir(pdk_b) and (os.path.isfile(tlef_b) or os.path.isdir(os.path.join(pdk_b, "libs.tech")))
        and os.path.isdir(sram_a) and os.path.isdir(sram_b)
    )
    has_ssa = os.path.isdir(ssa_dir) and os.path.isfile(ssa_sky)
    if has_ssa:
        try:
            with open(ssa_sky, "r") as f:
                has_ssa = "gds_dirs" in f.read()
        except Exception:
            has_ssa = False

    # If installed PDK lacks full GDS/Verilog/Netgen while a richer host/bundle source exists, trigger hydration
    dest_score = _score_pdk_source(pdk_a) if os.path.isdir(pdk_a) else 0
    best_src_score = max([_score_pdk_source(c) for c in _find_pdk_source_candidates("sky130A")], default=0)
    needs_pdk_hydration = best_src_score > dest_score and dest_score < 120

    has_desktop = os.path.isfile(desktop_file) and (os.path.isfile(cli_bin) or os.path.islink(cli_bin))
    return not (os.path.isfile(marker) and has_pdk and has_ssa and has_desktop and not needs_pdk_hydration)


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
            os.path.join(dot_silis, "ssa"),
            os.path.join(dot_silis, "pdks", "sky130A"),
            os.path.join(dot_silis, "pdks", "sky130B"),
            os.path.join(dot_silis, "pdks", "gf180mcu"),
        ]
        for d in subdirs:
            os.makedirs(d, exist_ok=True)
            time.sleep(0.01)

        self.progress_updated.emit(15, "Resolving PDK source assets...")
        
        # Locate source PDK bundle
        appdir = os.environ.get("APPDIR", "")
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        variants = ["sky130A", "sky130B", "gf180mcu"]
        dest_dirs = {}

        for v_idx, variant in enumerate(variants):
            pct_base = 20 + v_idx * 18  # 20..38 for sky130A, 38..56 for sky130B, 56..74 for gf180mcu
            dest_var = os.path.expanduser(f"~/.silis/pdks/{variant}")
            dest_dirs[variant] = dest_var

            candidates = _find_pdk_source_candidates(variant, source_pdk_dir=self.source_pdk_dir)
            candidates = sorted(candidates, key=_score_pdk_source, reverse=True)

            found_src = None
            for c in candidates:
                if c and os.path.isdir(c) and (
                    os.path.isdir(os.path.join(c, "libs.ref"))
                    or os.path.isfile(os.path.join(c, "gf180mcu_5LM_1TM_9K_9t_sc.lef"))
                ):
                    found_src = c
                    break

            if found_src and os.path.abspath(found_src) != os.path.abspath(dest_var):
                self.progress_updated.emit(pct_base, f"Installing {variant} from {found_src}...")
                all_files = []
                for root, _, files in os.walk(found_src):
                    for f in files:
                        all_files.append(os.path.join(root, f))

                total_files = len(all_files)
                if total_files > 0:
                    for idx, src_file in enumerate(all_files):
                        rel_path = os.path.relpath(src_file, found_src)
                        dst_file = os.path.join(dest_var, rel_path)
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        if not os.path.exists(dst_file) or os.path.getsize(dst_file) != os.path.getsize(src_file):
                            shutil.copy2(src_file, dst_file)
                        if idx % 25 == 0:
                            pct = pct_base + int((idx / total_files) * 16)
                            self.progress_updated.emit(pct, f"Installing {variant}: {os.path.basename(rel_path)}")

            # Ensure power switch cell LEF is present in each PDK variant
            lef_dir = os.path.join(dest_var, "libs.ref", "sky130_fd_sc_hd", "lef")
            psw_dir = os.path.join(dest_var, "libs.ref", "sky130_power_switch", "lef")
            os.makedirs(lef_dir, exist_ok=True)
            os.makedirs(psw_dir, exist_ok=True)
            psw_lef = os.path.join(lef_dir, "sky130_power_switch.lef")

            known_psw_paths = [
                os.path.join(dest_var, "libs.ref", "sky130_power_switch", "lef", "power_switch.lef"),
                os.path.join(appdir, "assets", "pdk", variant, "libs.ref", "sky130_power_switch", "lef", "power_switch.lef") if appdir else None,
                os.path.join(appdir, "third-party", "OpenROAD", "src", "pdn", "test", "sky130_power_switch", "power_switch.lef") if appdir else None,
                os.path.join(repo_root, "third-party", "OpenROAD", "src", "pdn", "test", "sky130_power_switch", "power_switch.lef"),
                os.path.join(repo_root, "core", "sky130_power_switch.lef"),
                os.path.join(appdir, "assets", "sky130_power_switch.lef") if appdir else None,
            ]
            for kp in known_psw_paths:
                if kp and os.path.isfile(kp):
                    try:
                        shutil.copy2(kp, psw_lef)
                        shutil.copy2(kp, os.path.join(psw_dir, "power_switch.lef"))
                        break
                    except Exception:
                        pass

            # Ensure SRAM memory macros are copied if available in backup/appdir/source
            dst_sram_lef = os.path.join(dest_var, "libs.ref", "sky130_sram_macros", "lef")
            if not os.path.isdir(dst_sram_lef) or not os.listdir(dst_sram_lef):
                sram_candidates = [
                    os.path.join(appdir, "assets", "pdk", variant, "libs.ref", "sky130_sram_macros") if appdir else None,
                    os.path.join(repo_root, "assets", "pdk", variant, "libs.ref", "sky130_sram_macros"),
                ]
                for sc in sram_candidates:
                    if sc and os.path.isdir(sc):
                        try:
                            shutil.copytree(sc, os.path.join(dest_var, "libs.ref", "sky130_sram_macros"), dirs_exist_ok=True)
                            break
                        except Exception:
                            pass

        # Stage complete SSA configs into ~/.silis/ssa
        self.progress_updated.emit(75, "Provisioning SSA family configuration profiles...")
        ssa_dst = os.path.join(dot_silis, "ssa")
        os.makedirs(ssa_dst, exist_ok=True)
        ssa_candidates = [
            os.path.join(appdir, "assets", "ssa") if appdir else None,
            os.path.join(repo_root, "assets", "ssa"),
        ]
        for s_cand in ssa_candidates:
            if s_cand and os.path.isdir(s_cand):
                try:
                    shutil.copytree(s_cand, ssa_dst, dirs_exist_ok=True)
                    break
                except Exception:
                    pass

        # Provision pdk_aliases.json
        alias_candidates = [
            os.path.join(appdir, "assets", "ssa", "pdk_aliases.json") if appdir else None,
            os.path.join(appdir, "assets", "pdk", "pdk_aliases.json") if appdir else None,
            os.path.join(repo_root, "assets", "ssa", "pdk_aliases.json"),
            os.path.join(repo_root, "core", "pdkmanagers", "pdk", "pdk_aliases.json"),
        ]
        for ac in alias_candidates:
            if ac and os.path.isfile(ac):
                try:
                    shutil.copy2(ac, os.path.join(dot_silis, "ssa", "pdk_aliases.json"))
                    shutil.copy2(ac, os.path.join(dot_silis, "pdks", "pdk_aliases.json"))
                    break
                except Exception:
                    pass

        # Register master PDK configuration manifest
        self.progress_updated.emit(78, "Writing multi-variant PDK configuration registry...")
        pdk_master_json = os.path.expanduser("~/.silis/pdks/pdk_master.json")
        master_candidates = [
            os.path.join(appdir, "assets", "pdk", "pdk_master.json") if appdir else None,
            os.path.join(repo_root, "assets", "pdk", "pdk_master.json"),
        ]
        master_copied = False
        for mc in master_candidates:
            if mc and os.path.isfile(mc):
                try:
                    shutil.copy2(mc, pdk_master_json)
                    master_copied = True
                    break
                except Exception:
                    pass

        if not master_copied:
            import json
            manifest = {
                "version": "1.0",
                "default_pdk": "sky130A",
                "pdks": {
                    "sky130A": {
                        "path": dest_dirs.get("sky130A", os.path.expanduser("~/.silis/pdks/sky130A")),
                        "type": "skywater130",
                        "status": "installed",
                        "standard_cells": ["sky130_fd_sc_hd", "sky130_fd_sc_hvl"],
                        "sram_macros": ["sky130_sram_macros"],
                        "io_cells": ["sky130_fd_io"],
                        "power_switches": ["sky130_power_switch"]
                    },
                    "sky130B": {
                        "path": dest_dirs.get("sky130B", os.path.expanduser("~/.silis/pdks/sky130B")),
                        "type": "skywater130",
                        "status": "installed",
                        "standard_cells": ["sky130_fd_sc_hd", "sky130_fd_sc_hvl"],
                        "sram_macros": ["sky130_sram_macros"],
                        "io_cells": ["sky130_fd_io"],
                        "power_switches": ["sky130_power_switch"]
                    },
                    "gf180mcu": {
                        "path": dest_dirs.get("gf180mcu", os.path.expanduser("~/.silis/pdks/gf180mcu")),
                        "type": "gf180mcu",
                        "status": "installed",
                        "standard_cells": ["gf180mcu_fd_sc_mcu9t5v0", "gf180mcu_fd_sc_mcu7t5v0"]
                    }
                },
                "families": {
                    "sky130": {
                        "display_name": "SkyWater 130nm",
                        "variants": {
                            "sky130A": {
                                "name": "Sky130A (High Density)",
                                "tech_lef": "sky130A/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef",
                                "std_cell_lef": "sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef",
                                "gds": "sky130A/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds",
                                "magic_tech": "sky130A/libs.tech/magic/sky130A.tech",
                                "default_corner": "tt_025C_1v80",
                                "corners": {
                                    "tt": {
                                        "tt_025C_1v80": {
                                            "lib": "sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib",
                                            "temp": 25,
                                            "volt": 1.8
                                        }
                                    }
                                }
                            },
                            "sky130B": {
                                "name": "Sky130B (High Density)",
                                "tech_lef": "sky130B/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef",
                                "std_cell_lef": "sky130B/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef",
                                "gds": "sky130B/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds",
                                "magic_tech": "sky130B/libs.tech/magic/sky130B.tech",
                                "default_corner": "tt_025C_1v80",
                                "corners": {
                                    "tt": {
                                        "tt_025C_1v80": {
                                            "lib": "sky130B/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib",
                                            "temp": 25,
                                            "volt": 1.8
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            with open(pdk_master_json, "w") as f:
                json.dump(manifest, f, indent=2)

        # 85%: Desktop integration & System Icons
        self.progress_updated.emit(85, "Installing desktop menu shortcuts and application icons...")
        apps_dir = os.path.expanduser("~/.local/share/applications")
        icons_dir = os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps")
        pixmaps_dir = os.path.expanduser("~/.local/share/pixmaps")
        os.makedirs(apps_dir, exist_ok=True)
        os.makedirs(icons_dir, exist_ok=True)
        os.makedirs(pixmaps_dir, exist_ok=True)

        icon_src = (
            os.path.join(appdir, "silisicon.png") if appdir and os.path.isfile(os.path.join(appdir, "silisicon.png"))
            else os.path.join(repo_root, "packaging", "silisicon.png") if os.path.isfile(os.path.join(repo_root, "packaging", "silisicon.png"))
            else os.path.join(repo_root, "silisicon.png")
        )
        if os.path.isfile(icon_src):
            try:
                shutil.copy2(icon_src, os.path.join(icons_dir, "silisicon.png"))
                shutil.copy2(icon_src, os.path.join(pixmaps_dir, "silisicon.png"))
            except Exception:
                pass

        appimage_bin = os.environ.get("APPIMAGE") or os.path.expanduser("~/.local/bin/silis")
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=Silis ASIC EDA Studio
GenericName=ASIC Physical Design Studio
Comment=Real-Time ASIC Physical Design, Floorplanning, and Signoff Studio
Exec={appimage_bin} %F
Icon=silisicon
Terminal=false
Categories=Development;Engineering;Electronics;
Keywords=ASIC;EDA;VLSI;Floorplan;OpenROAD;Yosys;Verilog;Silicon;
MimeType=application/x-silis-project;application/x-silisproj;
StartupWMClass=silis
"""
        desktop_file = os.path.join(apps_dir, "silis.desktop")
        try:
            with open(desktop_file, "w") as f:
                f.write(desktop_content)
            try:
                subprocess.run(["update-desktop-database", apps_dir], capture_output=True, timeout=2)
            except Exception:
                pass
        except Exception as e:
            print(f"[First-Boot Setup WARN] Could not write desktop entry: {e}")

        # 90%: Host CLI executable in ~/.local/bin/silis
        self.progress_updated.emit(90, "Registering host CLI executable in ~/.local/bin/silis...")
        local_bin = os.path.expanduser("~/.local/bin")
        os.makedirs(local_bin, exist_ok=True)
        cli_symlink = os.path.join(local_bin, "silis")
        try:
            if os.path.lexists(cli_symlink):
                try:
                    os.remove(cli_symlink)
                except Exception:
                    pass
            if os.environ.get("APPIMAGE"):
                os.symlink(os.environ["APPIMAGE"], cli_symlink)
            else:
                launcher_script = f"#!/bin/bash\nexec python3 \"{os.path.join(repo_root, 'silis.py')}\" \"$@\"\n"
                with open(cli_symlink, "w") as f:
                    f.write(launcher_script)
                st = os.stat(cli_symlink)
                os.chmod(cli_symlink, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        except Exception as e:
            print(f"[First-Boot Setup WARN] Could not register CLI symlink: {e}")

        # 94%: Register Python SDK host bridge
        self.progress_updated.emit(94, "Registering Python SDK host bridge...")
        try:
            from core.sdk_installer import install_host_sdk_bridge
            install_host_sdk_bridge(appimage_path=os.environ.get("APPIMAGE"))
        except Exception as e:
            print(f"[First-Boot Setup WARN] Could not install SDK host bridge: {e}")

        # 97%: Stage starter project and templates
        self.progress_updated.emit(97, "Staging starter project and templates...")
        demo_dest = os.path.join(home_silis, "projects", "demo_chip_top")
        if not os.path.exists(demo_dest):
            demo_src = os.path.join(repo_root, "examples", "cpp_macro_to_sv_chip", "chip_top_proj")
            if not os.path.isdir(demo_src) and appdir:
                demo_src = os.path.join(appdir, "examples", "cpp_macro_to_sv_chip", "chip_top_proj")
            if os.path.isdir(demo_src):
                try:
                    shutil.copytree(demo_src, demo_dest)
                except Exception:
                    pass

        # Mark initialization complete
        self.progress_updated.emit(99, "Writing initialization marker...")
        marker_file = os.path.expanduser("~/.silis/.initialized")
        with open(marker_file, "w") as f:
            f.write(f"SILIS_INITIALIZED=1\nTIMESTAMP={time.time()}\nVERSION=1.0.0\n")

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
