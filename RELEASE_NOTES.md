# Silis v0.1.1-pre (Pre-Release)

<p align="center">
  <img src="https://raw.githubusercontent.com/The-Silis-Foundation/silis/main/packaging/silisicon.png" alt="Silis ASIC EDA Logo" width="128" height="128">
</p>

<h3 align="center">Silis ASIC EDA Studio & Real-Time Physical Design Orchestrator</h3>

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
<td><a href="https://github.com/The-Silis-Foundation/silis/releases/download/v0.1.1-pre/Silis-x86_64.AppImage">Download AppImage (1.2 GB)</a></td>
<td><a href="https://github.com/The-Silis-Foundation/silis/releases/download/v0.1.1-pre/Silis-x86_64.AppImage.zsync">Zsync Manifest</a></td>
<td><a href="https://codespaces.new/The-Silis-Foundation/silis-cs-edition" target="_blank" rel="noopener noreferrer">Launch in Codespaces</a></td>
<td><a href="https://github.com/The-Silis-Foundation/silis/archive/refs/tags/v0.1.1-pre.tar.gz">tar.gz</a> &nbsp;|&nbsp; <a href="https://github.com/The-Silis-Foundation/silis/archive/refs/tags/v0.1.1-pre.zip">zip</a></td>
</tr>
</tbody>
</table>

---

## Quickstart & Zero-Configuration First Run

Silis v0.1.1-pre is fully self-contained. Running the AppImage for the first time automatically provisions your physical design environment without requiring root privileges or external setup scripts:

```bash
# 1. Make executable
chmod +x Silis-x86_64.AppImage

# 2. Launch Silis Studio (GUI mode)
./Silis-x86_64.AppImage

# Alternatively, invoke headless CLI flow directly
./Silis-x86_64.AppImage --projects
```

### Automated First-Run Setup Highlights
- **System Application Menu Integration**: Automatically registers `~/.local/share/applications/silis.desktop` and application icons so Silis appears directly in your system launcher, dock, and file manager.
- **Global Terminal Command**: Installs `~/.local/bin/silis` linking to the AppImage. You can run `silis` anywhere in your terminal.
- **Python SDK Host Bridge**: Configures `~/.local/lib/python3.*/site-packages/silis.pth`, enabling `import silis; from silis import Project, Floorplan, Pipeline` across your host Python environment.
- **Bundled SkyWater 130nm PDK**: Auto-provisions `~/.silis/pdks/sky130B` with standard cell libraries, technology LEFs, and power switches (`power_switch.lef`).
- **Starter Workspace**: Stages a complete demonstration design at `~/silis/projects/demo_chip_top`.

---

## Verification & Checksums

Verify your downloaded AppImage using the official SHA-256 or MD5 cryptographic hashes:

| File | Size | MD5 Hash | SHA-256 Checksum |
| :--- | :--- | :--- | :--- |
| `Silis-x86_64.AppImage` | 1.2 GB | `91174e689c7e27e1d536295ab9f41bf9` | `7635c501302f2f56a90f3f1c20471affabc6a096267edd6e2af4d78a863b19b9` |
| `Silis-x86_64.AppImage.zsync` | 2.4 MB | `d7eeab4540d9b01e549c03e3fe2adce7` | `19ede62afaa0739141d24462089e06d26365e14e156efe3c284e4ae372bbe623` |

Verification command:
```bash
sha256sum -c <<< "7635c501302f2f56a90f3f1c20471affabc6a096267edd6e2af4d78a863b19b9  Silis-x86_64.AppImage"
```

---

# Changelog

<details>
<summary>Detailed Changelog for v0.1.1-pre</summary>

### Added
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
- **CLI Argument Collision**: Resolved fatal unhandled `argparse.ArgumentError: conflicting option strings: --bend, --backend` in `core/cli/main.py`.
- **REPL Package Relative Imports**: Fixed fatal module lookup failures on `cli_flow` and `cli_main` in `core/cli/tui_repl.py`.
- **Current Working Directory Security Leak**: Patched trailing-colon in `LD_LIBRARY_PATH` and `PYTHONPATH` in `packaging/AppRun` preventing untrusted `.so` searches in `.` under clean environments.
- **Developer Host Path Leak**: Purged stale duplicate directory `Silis.AppDir/core/core` containing absolute developer paths.
- **Symlink Normalization**: Rebased all absolute GHDL plugin and Monaco editor symlinks to valid relative targets inside the AppDir.

</details>
