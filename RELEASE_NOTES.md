# Silis v0.1.1-pre (Pre-Release)

<p align="center">
  <img src="https://raw.githubusercontent.com/The-Silis-Foundation/silis/main/packaging/silisicon.png" alt="Silis ASIC EDA Logo" width="128" height="128">
</p>

<h3 align="center">Silis ASIC Design Studio</h3>

<p align="center">
  <a href="https://github.com/The-Silis-Foundation/silis/releases/tag/v0.1.1-pre"><img src="https://img.shields.io/badge/Release-v0.1.1--pre-blue.svg" alt="Release Badge"></a>
  <a href="https://github.com/The-Silis-Foundation/silis/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-green.svg" alt="License"></a>
  <a href="https://codespaces.new/The-Silis-Foundation/silis-cs-edition" target="_blank" rel="noopener noreferrer"><img src="https://img.shields.io/badge/Codespaces-Launch%20Web%20Studio-violet.svg" alt="Launch Codespace"></a>
</p>

---

## Downloads

<table>
<thead>
<tr>
<th>Platform / Architecture</th>
<th>Standalone Deliverable</th>
<th>Delta Updater</th>
<th>Web / Cloud Edition</th>
<th>Source Code</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>Linux x86-64 (64-bit)</strong></td>
<td><a href="https://github.com/The-Silis-Foundation/silis/releases/download/v0.1.1-pre/Silis-x86_64.AppImage">Download AppImage (1.4 GB)</a></td>
<td><a href="https://github.com/The-Silis-Foundation/silis/releases/download/v0.1.1-pre/Silis-x86_64.AppImage.zsync">Zsync Manifest</a></td>
<td><a href="https://codespaces.new/The-Silis-Foundation/silis-cs-edition" target="_blank" rel="noopener noreferrer">Launch in Codespaces</a></td>
<td><a href="https://github.com/The-Silis-Foundation/silis/archive/refs/tags/v0.1.1-pre.tar.gz">tar.gz</a> &nbsp;|&nbsp; <a href="https://github.com/The-Silis-Foundation/silis/archive/refs/tags/v0.1.1-pre.zip">zip</a></td>
</tr>
</tbody>
</table>

---

## Quickstart

```bash
# 1. Make executable
chmod +x Silis-x86_64.AppImage

# 2. Launch Silis Studio (GUI mode)
./Silis-x86_64.AppImage

# Alternatively, invoke headless CLI flow directly
./Silis-x86_64.AppImage --projects
```

---

## System Requirements & FUSE Prerequisite Notice

Silis AppImage runs on Linux distributions with kernel >= 4.18 and GLIBC >= 2.38.

> [!NOTE]
> **Ubuntu 24.04 and RHEL 9 Users**: Newer Linux distributions omit `libfuse2` by default. If the AppImage fails to mount, install the FUSE library or use the extract flag:
> ```bash
> # Ubuntu / Debian
> sudo apt install libfuse2t64
>
> # RHEL / Fedora
> sudo dnf install fuse-libs
>
> # Or run directly without FUSE
> ./Silis-x86_64.AppImage --appimage-extract-and-run
> ```

---

## Verification & Checksums

| File | Size | MD5 Hash | SHA-256 Checksum |
| :--- | :--- | :--- | :--- |
| `Silis-x86_64.AppImage` | 1.4 GB | `70bd6bb25df2f52c7c06fa1d36a8848e` | `169ea3955fc7759ca75e521905ab0cc83ad75f212103c1a89f56bacdf46ba6bd` |
| `Silis-x86_64.AppImage.zsync` | 2.8 MB | `e4b1fdf907a31ac2a3f44e8147ad4304` | `87a5ae1aedd29e95e66ad75bc2cd9be6efab2136a01b584614a6475cd0951e88` |

Verification command:
```bash
sha256sum -c <<< "169ea3955fc7759ca75e521905ab0cc83ad75f212103c1a89f56bacdf46ba6bd  Silis-x86_64.AppImage"
```

---

## Changelog

### Added
- **Zero PDK Truncation Law (ADR-012)**: Bundled 100% full, uncompressed silicon technology assets:
  - Complete SkyWater 130nm `sky130A` and `sky130B` PDKs (1.1 GB uncompressed each) including all standard cell variants (`hd`, `hvl`, `hs`, `ms`, `ls`, `lp`, `hdll`), all PVT corners (SS, FF, TT), primitive device models (`sky130_fd_pr`), OpenRAM memory macros, and IO pad cells.
  - Complete GlobalFoundries 180nm MCU `gf180mcu` PDK (21 MB uncompressed) with 7T and 9T libraries.
  - Complete master configuration catalog `pdk_master.json` containing multi-corner timing definitions.
- **SSA Configuration Completeness**: Packaged all SSA family configuration drop-in profiles (`sky130a`, `gf180mcu`, `asap7`) and `pdk_aliases.json` with deterministic search paths across AppDir and user workspace.
- **First-Boot Setup Orchestrator**: Implemented native Qt6 onboarding progress dialog (`FirstBootSetupDialog`) and headless runner (`run_headless_setup`) in `core/setup_wizard.py` to auto-provision workspace, PDKs, and application data.
- **Desktop Database Integration**: Added automatic registration of `silis.desktop` launcher and application icons in `~/.local/share/applications/` and `~/.local/share/icons/hicolor/256x256/apps/`.
- **Global Terminal Symlink**: Automated deployment of `~/.local/bin/silis` symlink pointing to the active AppImage.
- **Python SDK Host Bridge**: Implemented `check_and_auto_bootstrap()` in `core/sdk_installer.py` to auto-inject `silis.pth` into user site-packages.
- **Starter SoC Demonstration**: Bundled and staged `demo_chip_top` project in `~/silis/projects` on first execution.
- **Multi-Voltage Power Switch Cells**: Bundled `power_switch.lef` and `sky130_power_switch.lef` in `libs.ref/sky130_fd_sc_hd/lef` and `libs.ref/sky130_power_switch/lef`.

### Changes
- **Offline Static-PIE Runtime**: Bundled static-PIE type-2 AppImage runtime (`runtime-x86_64`) into build cache to guarantee 100% offline and air-gapped AppImage generation.
- **Standalone Wheel Caching**: Bundled `Pillow 13.0` and `packaging 26.3` directly into embedded CPython 3.12 environment in `Silis.AppDir`.
- **Packaging Pipeline Hardening**: Switched directory staging to `rsync -a --delete --exclude='.git'` to guarantee zero residual build artifacts.

### Fixes
- **Chromium Display Diagnostics**: Configured `QTWEBENGINE_CHROMIUM_FLAGS="--disable-logging --log-level=3 --disable-gpu-compositing"` in `AppRun` and `qt_setup.py` to eliminate GBM DRI fallback warnings on Linux desktops.
- **SSA Alias Discovery**: Resolved `[SSA] No external JSON found.` warning by embedding `pdk_aliases.json` and multi-path fallback lookup in `SSAForge.load_aliases()`.
- **CLI Argument Collision**: Resolved fatal unhandled `argparse.ArgumentError: conflicting option strings: --bend, --backend` in `core/cli/main.py`.
- **REPL Package Relative Imports**: Fixed fatal module lookup failures on `cli_flow` and `cli_main` in `core/cli/tui_repl.py`.
- **Current Working Directory Security Leak**: Patched trailing-colon in `LD_LIBRARY_PATH` and `PYTHONPATH` in `packaging/AppRun` preventing untrusted `.so` searches in `.` under clean environments.
- **Developer Host Path Leak**: Purged stale duplicate directory `Silis.AppDir/core/core` containing absolute developer paths.
- **Symlink Normalization**: Rebased all absolute GHDL plugin and Monaco editor symlinks to valid relative targets inside the AppDir.
