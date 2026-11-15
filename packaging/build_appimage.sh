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

# 3. Install self-contained wheels (PyQt6, WebEngine, QScintilla, gdstk, numpy, Pillow, packaging)
echo "=== Installing fully self-contained wheels into AppDir Python ==="
PYTHONNOUSERSITE=1 "${APPDIR}/opt/python/bin/pip3" install --no-cache-dir \
    PyQt6 \
    PyQt6-WebEngine \
    PyQt6-QScintilla \
    gdstk \
    numpy \
    websockify \
    Pillow \
    packaging

# 4. Copy application core files into AppDir
echo "=== Staging application codebase into AppDir ==="
cp -a "${REPO_DIR}/silis.py" "${APPDIR}/silis.py"
cp -a "${REPO_DIR}/__init__.py" "${APPDIR}/__init__.py"
rsync -a --delete --exclude='.git' "${REPO_DIR}/core/" "${APPDIR}/core/"
rm -rf "${APPDIR}/core/core"
cp -a "${REPO_DIR}/packaging/AppRun" "${APPDIR}/AppRun"
cp -a "${REPO_DIR}/packaging/silis.desktop" "${APPDIR}/silis.desktop"
cp -a "${REPO_DIR}/packaging/silisicon.png" "${APPDIR}/silisicon.png"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
cp -a "${REPO_DIR}/packaging/silisicon.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/silisicon.png"
if [ -d "${REPO_DIR}/examples" ]; then
    cp -a "${REPO_DIR}/examples" "${APPDIR}/examples"
fi

# 5. Stage lean Sky130 PDK assets for first-boot provisioning (SkyWater 130A & 130B with macros)
for VARIANT in sky130A sky130B; do
    HOST_PDK="${HOME}/.silis/pdks/${VARIANT}"
    if [ ! -d "${HOST_PDK}" ] && [ -d "/home/econsystems/.silis_backup_audit/pdks/${VARIANT}" ]; then
        HOST_PDK="/home/econsystems/.silis_backup_audit/pdks/${VARIANT}"
    fi

    if [ -d "${HOST_PDK}" ]; then
        echo "=== Staging lean ${VARIANT} PDK assets (standard cells, SRAM macros, IO pads, power switch) ==="
        mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_sc_hd/techlef"
        mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_sc_hd/lef"
        mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_sc_hd/lib"
        
        # Tech LEF
        if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef" ]; then
            cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef" \
                  "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_sc_hd/techlef/"
        fi
        # Standard cell LEF
        if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef" ]; then
            cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef" \
                  "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_sc_hd/lef/"
        fi
        if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd_merged.lef" ]; then
            cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd_merged.lef" \
                  "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_sc_hd/lef/"
        fi
        if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_power_switch.lef" ]; then
            cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lef/sky130_power_switch.lef" \
                  "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_sc_hd/lef/"
        fi
        # Standard cell LIB (nominal TT corner)
        if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" ]; then
            cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" \
                  "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_sc_hd/lib/"
        fi
        # Standard cell GDS
        if [ -f "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds" ]; then
            mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_sc_hd/gds"
            cp -a "${HOST_PDK}/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds" \
                  "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_sc_hd/gds/"
        fi

        # Power switch cell
        mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_power_switch/lef"
        if [ -f "${HOST_PDK}/libs.ref/sky130_power_switch/lef/power_switch.lef" ]; then
            cp -a "${HOST_PDK}/libs.ref/sky130_power_switch/lef/power_switch.lef" \
                  "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_power_switch/lef/"
        fi

        # SRAM memory macros
        if [ -d "${HOST_PDK}/libs.ref/sky130_sram_macros" ]; then
            mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_sram_macros/lef"
            mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_sram_macros/lib"
            mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_sram_macros/verilog"
            cp -a "${HOST_PDK}/libs.ref/sky130_sram_macros/lef/"*.lef "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_sram_macros/lef/" 2>/dev/null || true
            cp -a "${HOST_PDK}/libs.ref/sky130_sram_macros/lib/"*.lib "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_sram_macros/lib/" 2>/dev/null || true
            cp -a "${HOST_PDK}/libs.ref/sky130_sram_macros/verilog/"*.v "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_sram_macros/verilog/" 2>/dev/null || true
        fi

        # IO pad cells
        if [ -d "${HOST_PDK}/libs.ref/sky130_fd_io" ]; then
            mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_io/lef"
            mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_io/lib"
            cp -a "${HOST_PDK}/libs.ref/sky130_fd_io/lef/"*.lef "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_io/lef/" 2>/dev/null || true
            cp -a "${HOST_PDK}/libs.ref/sky130_fd_io/lib/"*tt*.lib "${APPDIR}/assets/pdk/${VARIANT}/libs.ref/sky130_fd_io/lib/" 2>/dev/null || true
        fi

        # Tech files (OpenLane, KLayout, Magic)
        if [ -d "${HOST_PDK}/libs.tech" ]; then
            mkdir -p "${APPDIR}/assets/pdk/${VARIANT}/libs.tech"
            for TDIR in openlane klayout magic; do
                if [ -d "${HOST_PDK}/libs.tech/${TDIR}" ]; then
                    cp -a "${HOST_PDK}/libs.tech/${TDIR}" "${APPDIR}/assets/pdk/${VARIANT}/libs.tech/"
                fi
            done
        fi
    fi
done

# Stage master PDK configuration manifest into AppDir
if [ -f "${HOME}/.silis/pdks/pdk_master.json" ]; then
    mkdir -p "${APPDIR}/assets/pdk"
    cp -a "${HOME}/.silis/pdks/pdk_master.json" "${APPDIR}/assets/pdk/pdk_master.json"
fi

# 6. Copy third-party tools & extensions if present
if [ -d "${REPO_DIR}/third-party" ] && [ ! -d "${APPDIR}/third-party" ]; then
    echo "=== Copying third-party tool binaries and plugins ==="
    cp -a "${REPO_DIR}/third-party" "${APPDIR}/third-party"
fi

# Normalize symlinks to relative targets inside AppDir for zero host path leaks
if [ -d "${APPDIR}/core/editor" ]; then
    (cd "${APPDIR}/core/editor" && ln -sfn ../../third-party/monaco/node_modules/monaco-editor/min/vs vs)
fi
if [ -d "${APPDIR}/third-party/monaco/min" ]; then
    (cd "${APPDIR}/third-party/monaco/min" && ln -sfn ../node_modules/monaco-editor/min/vs vs)
fi
if [ -d "${APPDIR}/third-party/bin" ]; then
    (cd "${APPDIR}/third-party/bin" && ln -sfn ../OpenSTA/build/sta sta)
fi
if [ -d "${APPDIR}/third-party/plugins/ghdl" ]; then
    (cd "${APPDIR}/third-party/plugins/ghdl" && ln -sfn vhdl/ieee ieee && ln -sfn vhdl/std std)
    if [ -d "${APPDIR}/third-party/plugins/ghdl/gcc" ]; then
        (cd "${APPDIR}/third-party/plugins/ghdl/gcc" && ln -sfn ../vhdl vhdl)
    fi
    rm -f "${APPDIR}/third-party/plugins/ghdl/vhdl/src"
fi
find "${APPDIR}/third-party" -name "node_gyp_bins" -type d -exec rm -rf {} + 2>/dev/null || true

# 6b. Collect all external shared libraries (libxcb*, libxkbcommon*, libEGL*, libtcl*, libreadline*, etc.)
echo "=== Bundling system shared libraries into AppDir/usr/lib/x86_64-linux-gnu ==="
python3 "${REPO_DIR}/packaging/bundle_shared_libs.py" "${APPDIR}"

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
RUNTIME_OPT=()
if [ -f "${CACHE_DIR}/runtime-x86_64" ]; then
    RUNTIME_OPT=(--runtime-file "${CACHE_DIR}/runtime-x86_64")
fi

"${TOOL_CMD}" -n "${RUNTIME_OPT[@]}" -u "${UPDATE_INFO}" "${APPDIR}" "${OUTPUT_DIR}/Silis-x86_64.AppImage" || "${TOOL_CMD}" -n "${RUNTIME_OPT[@]}" "${APPDIR}" "${OUTPUT_DIR}/Silis-x86_64.AppImage"

echo "=== Standalone AppImage build complete! Deliverable: ${OUTPUT_DIR}/Silis-x86_64.AppImage ==="
