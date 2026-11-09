#!/bin/bash
set -euo pipefail

# ==============================================================================
# Silis ASIC EDA AppImage Builder with Embedded Python, Qt6, PDK & Zsync
# ==============================================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${REPO_DIR}/build_appimage"
APPDIR="${BUILD_DIR}/Silis.AppDir"
OUTPUT_DIR="${REPO_DIR}/dist"
CACHE_DIR="${BUILD_DIR}/cache"

echo "=== Preparing Silis AppDir at: ${APPDIR} ==="
mkdir -p "${CACHE_DIR}"
mkdir -p "${OUTPUT_DIR}"

# 1. Fetch and stage standalone CPython 3.12 if not already in cache
PYTHON_TAR="${CACHE_DIR}/python-standalone.tar.gz"
if [ ! -f "${PYTHON_TAR}" ]; then
    echo "=== Downloading python-build-standalone (Python 3.12.3) ==="
    wget -c "https://github.com/astral-sh/python-build-standalone/releases/download/20240415/cpython-3.12.3+20240415-x86_64-unknown-linux-gnu-install_only.tar.gz" \
         -O "${PYTHON_TAR}"
fi

# 2. Prepare opt/python inside AppDir
mkdir -p "${APPDIR}/opt"
if [ ! -d "${APPDIR}/opt/python" ]; then
    echo "=== Extracting standalone Python runtime into AppDir/opt/python ==="
    tar -xzf "${PYTHON_TAR}" -C "${APPDIR}/opt"
fi

# 3. Install self-contained wheels (PyQt6, WebEngine, QScintilla, gdstk, numpy)
echo "=== Installing fully self-contained wheels into AppDir Python ==="
PYTHONNOUSERSITE=1 "${APPDIR}/opt/python/bin/pip3" install --no-cache-dir \
    PyQt6 \
    PyQt6-WebEngine \
    PyQt6-QScintilla \
    gdstk \
    numpy \
    websockify

# 4. Copy application core files into AppDir
echo "=== Staging application codebase into AppDir ==="
cp -a "${REPO_DIR}/silis.py" "${APPDIR}/silis.py"
cp -a "${REPO_DIR}/__init__.py" "${APPDIR}/__init__.py"
cp -a "${REPO_DIR}/core" "${APPDIR}/core"
cp -a "${REPO_DIR}/packaging/AppRun" "${APPDIR}/AppRun"
cp -a "${REPO_DIR}/packaging/silis.desktop" "${APPDIR}/silis.desktop"
cp -a "${REPO_DIR}/packaging/silisicon.png" "${APPDIR}/silisicon.png"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
cp -a "${REPO_DIR}/packaging/silisicon.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/silisicon.png"

# 5. Stage lean Sky130 PDK assets for first-boot provisioning
HOST_PDK="${HOME}/.silis/pdks/sky130B"
if [ -d "${HOST_PDK}" ]; then
    echo "=== Staging lean Sky130 standard cell assets ==="
    mkdir -p "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/techlef"
    mkdir -p "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/lef"
    mkdir -p "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/lib"
    if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef" ]; then
        cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef" \
              "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/techlef/"
    fi
    if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd_merged.lef" ]; then
        cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd_merged.lef" \
              "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/lef/"
    fi
    if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_power_switch.lef" ]; then
        cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_power_switch.lef" \
              "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/lef/"
    fi
    if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" ]; then
        cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" \
              "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/lib/"
    fi
    if [ -d "${HOST_PDK}/libs.tech" ]; then
        cp -a "${HOST_PDK}/libs.tech" "${APPDIR}/assets/pdk/sky130B/"
    fi
fi

# 6. Copy third-party tools & extensions if present
if [ -d "${REPO_DIR}/third-party" ] && [ ! -d "${APPDIR}/third-party" ]; then
    echo "=== Copying third-party tool binaries and plugins ==="
    cp -a "${REPO_DIR}/third-party" "${APPDIR}/third-party"
fi

chmod +x "${APPDIR}/AppRun"

# 7. Locate appimagetool
APPIMAGETOOL="${BUILD_DIR}/appimagetool-x86_64.AppImage"
if ! command -v appimagetool &>/dev/null; then
    if [ ! -f "${APPIMAGETOOL}" ]; then
        echo "=== Fetching appimagetool ==="
        wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O "${APPIMAGETOOL}"
        chmod +x "${APPIMAGETOOL}"
    fi
    TOOL_CMD="${APPIMAGETOOL}"
else
    TOOL_CMD="appimagetool"
fi

# 8. Build AppImage with embedded update information (zsync)
echo "=== Generating 100% Standalone Silis-x86_64.AppImage ==="
export ARCH=x86_64
UPDATE_INFO="zsync|https://github.com/The-Silis-Foundation/silis/releases/latest/download/Silis-x86_64.AppImage.zsync"

"${TOOL_CMD}" -u "${UPDATE_INFO}" "${APPDIR}" "${OUTPUT_DIR}/Silis-x86_64.AppImage" || "${TOOL_CMD}" "${APPDIR}" "${OUTPUT_DIR}/Silis-x86_64.AppImage"

echo "=== Standalone AppImage build complete! Deliverable: ${OUTPUT_DIR}/Silis-x86_64.AppImage ==="
