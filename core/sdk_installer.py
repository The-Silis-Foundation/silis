"""
sdk_installer.py
Automated first-time setup and host bridge injector for Silis AppImage & Python SDK.
Deploys a lightweight bridge package into host Python user site-packages:
(~/.local/lib/python3.*/site-packages/silis/)
Allows `import silis; from silis import Project, Floorplan, Pipeline` to work
directly from any host script, terminal, Jupyter notebook, or IDE.
When running on host, it can either link directly to the Silis installation
or dynamically mount and invoke the Silis AppImage headlessly.
"""

import os
import sys
import site
import time
import shutil
import stat
import subprocess
from pathlib import Path


def get_user_site_packages():
    """Returns the primary user site-packages directory for the current host Python."""
    try:
        user_site = site.getusersitepackages()
        return user_site
    except Exception:
        return os.path.expanduser(f"~/.local/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")


def install_host_sdk_bridge(appimage_path=None, force=False):
    """
    Installs the starter `silis.pth`, `silis/` package directory, and CLI symlink.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    silis_root = os.path.abspath(os.path.join(current_dir, ".."))
    appimage_bin = appimage_path or os.environ.get("APPIMAGE", "")

    target_site = get_user_site_packages()
    os.makedirs(target_site, exist_ok=True)

    # If executing from inside an AppImage mount, deploy a persistent copy to ~/.silis/sdk
    is_appimage_mount = bool(os.environ.get("APPIMAGE")) or bool(os.environ.get("APPDIR")) or "/tmp/.mount_" in silis_root
    if is_appimage_mount:
        permanent_sdk = os.path.expanduser("~/.silis/sdk")
        os.makedirs(permanent_sdk, exist_ok=True)
        for item in ["silis.py", "__init__.py"]:
            src = os.path.join(silis_root, item)
            dst = os.path.join(permanent_sdk, item)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass
        core_src = os.path.join(silis_root, "core")
        core_dst = os.path.join(permanent_sdk, "core")
        if os.path.isdir(core_src):
            try:
                if os.path.exists(core_dst):
                    shutil.rmtree(core_dst)
                shutil.copytree(core_src, core_dst)
            except Exception:
                pass
        effective_root = permanent_sdk
    else:
        effective_root = silis_root

    # 1. Install silis.pth pointing to silis parent and silis itself
    silis_parent = os.path.abspath(os.path.join(effective_root, ".."))
    pth_file = os.path.join(target_site, "silis.pth")
    try:
        with open(pth_file, "w") as f:
            f.write(f"{silis_parent}\n")
            f.write(f"{effective_root}\n")
            f.write(f"{os.path.join(effective_root, 'core')}\n")
    except Exception as e:
        print(f"[WARN] Could not write silis.pth: {e}")

    # 2. Ensure site-packages/silis doesn't overshadow the repository
    silis_pkg_dir = os.path.join(target_site, "silis")
    if os.path.isdir(silis_pkg_dir) or os.path.islink(silis_pkg_dir):
        try:
            if os.path.islink(silis_pkg_dir):
                os.unlink(silis_pkg_dir)
            else:
                shutil.rmtree(silis_pkg_dir)
            os.symlink(effective_root, silis_pkg_dir)
            print(f"[SUCCESS] Linked {silis_pkg_dir} -> {effective_root}")
        except Exception:
            pass
    elif not os.path.exists(silis_pkg_dir):
        try:
            os.symlink(effective_root, silis_pkg_dir)
            print(f"[SUCCESS] Linked {silis_pkg_dir} -> {effective_root}")
        except Exception:
            pass

    # 3. Create host CLI executable symlink in ~/.local/bin
    local_bin = os.path.expanduser("~/.local/bin")
    os.makedirs(local_bin, exist_ok=True)
    cli_symlink = os.path.join(local_bin, "silis")

    cli_script = os.path.join(effective_root, "core", "cli", "cli.py")
    if appimage_bin and os.path.isfile(appimage_bin):
        cli_target = appimage_bin
    else:
        cli_target = cli_script

    try:
        if os.path.lexists(cli_symlink):
            os.remove(cli_symlink)
        if cli_target == appimage_bin:
            os.symlink(cli_target, cli_symlink)
        else:
            with open(cli_symlink, "w") as f:
                f.write(f"#!/usr/bin/env bash\nexec python3 \"{cli_target}\" \"$@\"\n")
            st = os.stat(cli_symlink)
            os.chmod(cli_symlink, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except Exception as e:
        print(f"[WARN] Could not register CLI symlink: {e}")

    print(f"[SUCCESS] Silis Python SDK package registered at: {silis_pkg_dir}")
    print("You can now run 'python3 -c \"import silis; print(silis.Pipeline)\"' from any host terminal.")
    return True


def check_and_auto_bootstrap(appimage_path=None):
    """
    Checks if host SDK bridge is already installed. If not, installs it.
    """
    marker = os.path.expanduser("~/.silis/.sdk_bootstrap_done")
    if os.path.isfile(marker):
        return True
    try:
        success = install_host_sdk_bridge(appimage_path=appimage_path)
        if success:
            os.makedirs(os.path.dirname(marker), exist_ok=True)
            with open(marker, "w") as f:
                f.write(f"SDK_BOOTSTRAP_DONE=1\nTIMESTAMP={time.time()}\n")
        return success
    except Exception as e:
        print(f"[WARN] Auto-bootstrap error: {e}")
        return False


if __name__ == "__main__":
    install_host_sdk_bridge()
