#!/usr/bin/env python3
"""
Collect all system shared libraries required by PyQt6, WebEngine, and Python
into the AppDir usr/lib/x86_64-linux-gnu directory for true self-contained execution.
"""
import os
import shutil
import subprocess
import sys

def collect_libs(appdir: str):
    target_lib_dir = os.path.join(appdir, "usr", "lib", "x86_64-linux-gnu")
    os.makedirs(target_lib_dir, exist_ok=True)
    
    python_site = os.path.join(appdir, "opt", "python", "lib", "python3.12", "site-packages")
    if not os.path.exists(python_site):
        print(f"Error: site-packages not found at {python_site}")
        sys.exit(1)
        
    # Find all binary ELF and .so files across opt/python, third-party/bin, core, and GDS3D
    scan_dirs = [
        os.path.join(appdir, "opt", "python"),
        os.path.join(appdir, "third-party", "bin"),
        os.path.join(appdir, "core"),
        os.path.join(appdir, "third-party", "GDS3D"),
    ]
    so_binaries = []
    for s_dir in scan_dirs:
        if not os.path.exists(s_dir):
            continue
        for root, _, files in os.walk(s_dir):
            if "build/_deps" in root:
                continue
            for f in files:
                fp = os.path.join(root, f)
                if os.path.islink(fp):
                    continue
                if f.endswith(".so") or ".so." in f or f.startswith("python3"):
                    so_binaries.append(fp)
                else:
                    try:
                        with open(fp, "rb") as bf:
                            if bf.read(4) == b"\x7fELF":
                                so_binaries.append(fp)
                    except Exception:
                        pass
                
    print(f"Found {len(so_binaries)} binary objects inside AppDir to analyze.")
    
    # Exclude core glibc / kernel interface libraries that must come from host
    GLIBC_EXCLUDE = {
        "libc.so", "libm.so", "libdl.so", "libpthread.so", "librt.so", 
        "ld-linux-x86-64.so", "libresolv.so", "libutil.so", "libnss_compat.so",
        "libnss_files.so", "libnss_dns.so"
    }
    
    # Compute transitive closure of all external library dependencies
    needed_libs = set()
    to_scan = list(so_binaries)
    scanned = set()
    while to_scan:
        binary = to_scan.pop()
        if binary in scanned:
            continue
        scanned.add(binary)
        try:
            out = subprocess.check_output(["ldd", binary], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if "=>" in line and "/" in line:
                    parts = line.split("=>")
                    lib_path = parts[1].split("(")[0].strip()
                    lib_name = os.path.basename(lib_path)
                    
                    # Check if glibc
                    if any(lib_name.startswith(excl) for excl in GLIBC_EXCLUDE):
                        continue
                    if os.path.exists(lib_path) and not lib_path.startswith(appdir):
                        if lib_path not in needed_libs:
                            needed_libs.add(lib_path)
                            to_scan.append(lib_path)
        except Exception:
            pass

    print(f"Discovered {len(needed_libs)} external host shared libraries to bundle.")
    
    copied = 0
    for lib in sorted(needed_libs):
        base = os.path.basename(lib)
        dest = os.path.join(target_lib_dir, base)
        if not os.path.exists(dest):
            try:
                # Follow symlink or copy real file + symlink
                real = os.path.realpath(lib)
                real_base = os.path.basename(real)
                real_dest = os.path.join(target_lib_dir, real_base)
                shutil.copy2(real, real_dest)
                if real_base != base:
                    link_name = os.path.join(target_lib_dir, base)
                    if not os.path.exists(link_name):
                        os.symlink(real_base, link_name)
                copied += 1
            except Exception as e:
                print(f"Warning: could not copy {lib}: {e}")
                
    print(f"Successfully bundled {copied} shared libraries into {target_lib_dir}.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: bundle_shared_libs.py <APPDIR_PATH>")
        sys.exit(1)
    collect_libs(sys.argv[1])
