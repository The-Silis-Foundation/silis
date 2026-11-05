#!/bin/bash
set -euo pipefail

# ==============================================================================
# Silis ASIC EDA AppImage Builder with Lean PDK Bundling & Zsync Support
# ==============================================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${REPO_DIR}/build_appimage"
APPDIR="${BUILD_DIR}/Silis.AppDir"
OUTPUT_DIR="${REPO_DIR}/dist"

echo "=== Preparing Silis AppDir at: ${APPDIR} ==="
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/lef"
mkdir -p "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/techlef"
mkdir -p "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/lib"
mkdir -p "${OUTPUT_DIR}"

# 1. Copy application core files into AppDir
cp -a "${REPO_DIR}/silis.py" "${APPDIR}/silis.py"
cp -a "${REPO_DIR}/__init__.py" "${APPDIR}/__init__.py"
cp -a "${REPO_DIR}/core" "${APPDIR}/core"
cp -a "${REPO_DIR}/packaging/AppRun" "${APPDIR}/AppRun"
cp -a "${REPO_DIR}/packaging/silis.desktop" "${APPDIR}/silis.desktop"
cp -a "${REPO_DIR}/packaging/silisicon.png" "${APPDIR}/silisicon.png"
cp -a "${REPO_DIR}/packaging/silisicon.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/silisicon.png"

# 2. Stage lean Sky130 PDK assets for first-boot provisioning
HOST_PDK="${HOME}/.silis/pdks/sky130B"
if [ -d "${HOST_PDK}" ]; then
    echo "=== Staging lean Sky130 standard cell assets ==="
    # Tech LEF
    if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef" ]; then
        cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef" \
              "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/techlef/"
    fi
    # Merged LEF
    if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd_merged.lef" ]; then
        cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd_merged.lef" \
              "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/lef/"
    fi
    # Power Switch LEF
    if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_power_switch.lef" ]; then
        cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_power_switch.lef" \
              "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/lef/"
    fi
    # Standard cell timing model
    if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" ]; then
        cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" \
              "${APPDIR}/assets/pdk/sky130B/libs.ref/sky130_fd_sc_hd/lib/"
    fi
    # OpenLane / tech configs
    if [ -d "${HOST_PDK}/libs.tech" ]; then
        cp -a "${HOST_PDK}/libs.tech" "${APPDIR}/assets/pdk/sky130B/"
    fi
fi

# Copy third-party tools & extensions if present
if [ -d "${REPO_DIR}/third-party" ]; then
    echo "=== Copying third-party tool binaries and plugins ==="
    cp -a "${REPO_DIR}/third-party" "${APPDIR}/third-party"
fi

chmod +x "${APPDIR}/AppRun"

# 3. Download appimagetool if not found on system
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

# 4. Build AppImage with embedded update information (zsync)
echo "=== Generating Silis-x86_64.AppImage with Zsync metadata ==="
export ARCH=x86_64
UPDATE_INFO="zsync|https://github.com/The-Silis-Foundation/silis/releases/latest/download/Silis-x86_64.AppImage.zsync"

"${TOOL_CMD}" -u "${UPDATE_INFO}" "${APPDIR}" "${OUTPUT_DIR}/Silis-x86_64.AppImage" || "${TOOL_CMD}" "${APPDIR}" "${OUTPUT_DIR}/Silis-x86_64.AppImage"

echo "=== AppImage build complete! Deliverable: ${OUTPUT_DIR}/Silis-x86_64.AppImage ==="
