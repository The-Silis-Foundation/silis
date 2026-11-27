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
if [ ! -d "${APPDIR}/opt/python/lib/python3.12/site-packages/PyQt6" ]; then
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
else
    echo "=== Standalone Python wheels already staged in AppDir/opt/python ==="
fi

# 4. Copy application core files into AppDir
echo "=== Staging application codebase into AppDir ==="
cp -a "${REPO_DIR}/silis.py" "${APPDIR}/silis.py"
cp -a "${REPO_DIR}/__init__.py" "${APPDIR}/__init__.py"
rsync -a --delete --delete-excluded --exclude='.git' --exclude='CMakeFiles' --exclude='__pycache__' "${REPO_DIR}/core/" "${APPDIR}/core/"
rm -rf "${APPDIR}/core/core"
cp -a "${REPO_DIR}/packaging/AppRun" "${APPDIR}/AppRun"
cp -a "${REPO_DIR}/packaging/silis.desktop" "${APPDIR}/silis.desktop"
cp -a "${REPO_DIR}/packaging/silisicon.png" "${APPDIR}/silisicon.png"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
cp -a "${REPO_DIR}/packaging/silisicon.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/silisicon.png"
if [ -d "${REPO_DIR}/examples" ]; then
    cp -a "${REPO_DIR}/examples" "${APPDIR}/examples"
fi

# 5. Stage 100% Complete PDK & SSA Assets (Zero Truncation Law)
echo "=== Staging 100% COMPLETE PDKs into AppDir (SkyWater 130A, 130B, GF180MCU) ==="
mkdir -p "${APPDIR}/assets/pdk"
mkdir -p "${APPDIR}/assets/ssa"

for VARIANT in sky130A sky130B gf180mcu; do
    SRC_PDK=""
    if [ -d "${REPO_DIR}/assets/pdk/${VARIANT}" ]; then
        SRC_PDK="${REPO_DIR}/assets/pdk/${VARIANT}"
    elif [ -d "${HOME}/.silis/pdks/${VARIANT}" ]; then
        SRC_PDK="${HOME}/.silis/pdks/${VARIANT}"
    elif [ -d "/home/econsystems/.silis_backup_audit/pdks/${VARIANT}" ]; then
        SRC_PDK="/home/econsystems/.silis_backup_audit/pdks/${VARIANT}"
    fi

    if [ -n "${SRC_PDK}" ] && [ -d "${SRC_PDK}" ]; then
        echo "=== Staging 100% complete ${VARIANT} from ${SRC_PDK} ==="
        mkdir -p "${APPDIR}/assets/pdk/${VARIANT}"
        rsync -a --delete "${SRC_PDK}/" "${APPDIR}/assets/pdk/${VARIANT}/"
    else
        echo "WARNING: Could not find source PDK for ${VARIANT}!"
    fi
done

# Stage master PDK configuration manifest into AppDir (prefer repo assets/pdk or active ~/.silis/pdks first)
if [ -f "${REPO_DIR}/assets/pdk/pdk_master.json" ]; then
    cp -a "${REPO_DIR}/assets/pdk/pdk_master.json" "${APPDIR}/assets/pdk/pdk_master.json"
elif [ -f "${HOME}/.silis/pdks/pdk_master.json" ]; then
    cp -a "${HOME}/.silis/pdks/pdk_master.json" "${APPDIR}/assets/pdk/pdk_master.json"
elif [ -f "/home/econsystems/.silis_backup_audit/pdks/pdk_master.json" ]; then
    cp -a "/home/econsystems/.silis_backup_audit/pdks/pdk_master.json" "${APPDIR}/assets/pdk/pdk_master.json"
fi

# Stage all SSA drop-in configurations into AppDir (prefer current repo assets/ssa first)
if [ -d "${REPO_DIR}/assets/ssa" ]; then
    rsync -a --delete "${REPO_DIR}/assets/ssa/" "${APPDIR}/assets/ssa/"
elif [ -d "${HOME}/.silis/ssa" ]; then
    rsync -a --delete "${HOME}/.silis/ssa/" "${APPDIR}/assets/ssa/"
elif [ -d "/home/econsystems/.silis_backup_audit/ssa" ]; then
    rsync -a --delete "/home/econsystems/.silis_backup_audit/ssa/" "${APPDIR}/assets/ssa/"
fi

# Stage pdk_aliases.json
if [ -f "${REPO_DIR}/assets/pdk/pdk_aliases.json" ]; then
    cp -a "${REPO_DIR}/assets/pdk/pdk_aliases.json" "${APPDIR}/assets/pdk/pdk_aliases.json"
    cp -a "${REPO_DIR}/assets/pdk/pdk_aliases.json" "${APPDIR}/assets/ssa/pdk_aliases.json"
elif [ -f "${REPO_DIR}/assets/ssa/pdk_aliases.json" ]; then
    cp -a "${REPO_DIR}/assets/ssa/pdk_aliases.json" "${APPDIR}/assets/ssa/pdk_aliases.json"
    cp -a "${REPO_DIR}/assets/ssa/pdk_aliases.json" "${APPDIR}/assets/pdk/pdk_aliases.json"
fi

if [ -d "${REPO_DIR}/third-party/pdks/volare" ] && [ ! -d "${APPDIR}/assets/pdk/volare" ]; then
    cp -a "${REPO_DIR}/third-party/pdks/volare" "${APPDIR}/assets/pdk/volare"
elif [ -d "${HOME}/.silis/pdks/volare" ] && [ ! -d "${APPDIR}/assets/pdk/volare" ]; then
    cp -a "${HOME}/.silis/pdks/volare" "${APPDIR}/assets/pdk/volare"
fi

# 6. Copy third-party tools & extensions BEFORE creating third-party/pdks symlinks
if [ -d "${REPO_DIR}/third-party" ]; then
    echo "=== Copying third-party tool binaries and plugins ==="
    mkdir -p "${APPDIR}/third-party"
    rsync -a --delete --exclude='.git' --exclude='pdks/sky130A' --exclude='pdks/sky130B' --exclude='pdks/gf180mcu' "${REPO_DIR}/third-party/" "${APPDIR}/third-party/"
fi

# Ensure cross-compatibility symlinks between assets/pdk and third-party/pdks
mkdir -p "${APPDIR}/assets/pdk/third-party"
(cd "${APPDIR}/assets/pdk/third-party" && ln -sfn .. pdks)
mkdir -p "${APPDIR}/third-party/pdks"
(cd "${APPDIR}/third-party/pdks" && ln -sfn ../../assets/pdk/sky130A sky130A && ln -sfn ../../assets/pdk/sky130B sky130B && ln -sfn ../../assets/pdk/gf180mcu gf180mcu)
(cd "${APPDIR}/third-party/pdks" && ln -sfn ../../assets/pdk/pdk_master.json pdk_master.json && ln -sfn ../../assets/pdk/pdk_aliases.json pdk_aliases.json)

# Bundle Tcl 8.6 runtime scripts so sta/yosys/magic run on minimal Linux systems lacking tcl8.6 apt package
if [ -d "/usr/share/tcltk/tcl8.6" ]; then
    mkdir -p "${APPDIR}/usr/share/tcltk"
    rsync -a "/usr/share/tcltk/tcl8.6/" "${APPDIR}/usr/share/tcltk/tcl8.6/"
fi
rm -rf "${APPDIR}/usr/share/perl5"

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

APPIMAGE_EXTRACT_AND_RUN=1 "${TOOL_CMD}" -n "${RUNTIME_OPT[@]}" -u "${UPDATE_INFO}" "${APPDIR}" "${OUTPUT_DIR}/Silis-x86_64.AppImage" || APPIMAGE_EXTRACT_AND_RUN=1 "${TOOL_CMD}" -n "${RUNTIME_OPT[@]}" "${APPDIR}" "${OUTPUT_DIR}/Silis-x86_64.AppImage"

if command -v zsyncmake &>/dev/null; then
    echo "=== Generating zsync update metadata ==="
    (cd "${OUTPUT_DIR}" && zsyncmake -u "Silis-x86_64.AppImage" "Silis-x86_64.AppImage")
fi

echo "=== Standalone AppImage build complete! Deliverable: ${OUTPUT_DIR}/Silis-x86_64.AppImage ==="
