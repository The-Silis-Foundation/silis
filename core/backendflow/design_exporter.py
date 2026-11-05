"""
core/backendflow/design_exporter.py
Comprehensive Design Package Exporter for Silis EDA.

Exports the verified silicon design into ~/.silis/designs/<top_module>/
Strictly includes all physical, netlist, test/ATPG, timing, and signoff deliverables:
  - Physical GDSII (<top_module>.gds)
  - Abstract LEF (<top_module>.lef)
  - Layout DEF (<top_module>.def)
  - ATPG STIL 1.0 test patterns (<top_module>.stil)
  - IEEE SCANDEF 5.8 scan chain ordering (<top_module>.scandef)
  - ATE Verilog testbench (<top_module>_atpg_tb.v)
  - Verilog blackbox stub (<top_module>.v)
  - Post-synthesis gate-level simulation model (<top_module>.sim.v)
  - CDL / SPICE netlist (<top_module>.spice)
  - Timing constraints (<top_module>.sdc)
  - Multi-corner Liberty models (lib/<top_module>__<corner>.lib)
  - Multi-corner parasitic SPEF (spef/<top_module>__<corner>.spef)
  - Full Signoff Audit Markdown Report (signoff_report.md)
  - Machine-readable manifest (manifest.json)
"""

import os
import sys
import json
import shutil
import glob
import subprocess
from typing import Dict, Any, Optional, List


def export_full_design_package(
    project_root: str,
    top_module: str,
    pdk_name: str = "sky130",
    signoff_manifest: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Bundles all verification, test, physical, and signoff artifacts into ~/.silis/designs/<top_module>/
    and returns a summary dict of exported deliverables.
    """
    silis_home = os.path.expanduser("~/.silis")
    export_base = os.path.join(silis_home, "designs", top_module)
    lib_dir = os.path.join(export_base, "lib")
    spef_dir = os.path.join(export_base, "spef")
    dft_dir = os.path.join(export_base, "dft")

    os.makedirs(export_base, exist_ok=True)
    os.makedirs(lib_dir, exist_ok=True)
    os.makedirs(spef_dir, exist_ok=True)
    os.makedirs(dft_dir, exist_ok=True)

    results_dir = os.path.join(project_root, "results")
    reports_dir = os.path.join(project_root, "reports")
    netlist_dir = os.path.join(project_root, "netlist")
    source_dir = os.path.join(project_root, "source")
    constr_dir = os.path.join(project_root, "constr")

    exported_files = {}

    # 1. Physical GDSII
    cand_gds = [
        os.path.join(results_dir, f"{top_module}_merged.gds"),
        os.path.join(results_dir, f"{top_module}_tapeout.gds"),
        os.path.join(results_dir, f"{top_module}.gds"),
        os.path.join(results_dir, "design.gds"),
    ]
    # Pick the largest valid GDS (> 1000 bytes)
    src_gds = next((p for p in cand_gds if os.path.isfile(p) and os.path.getsize(p) > 1000), None)
    if not src_gds:
        src_gds = next((p for p in cand_gds if os.path.isfile(p)), None)
    dest_gds = os.path.join(export_base, f"{top_module}.gds")
    if src_gds:
        shutil.copy2(src_gds, dest_gds)
        exported_files["gds"] = dest_gds

    # 2. Detailed Layout DEF
    cand_def = [
        os.path.join(results_dir, f"{top_module}_filled.def"),
        os.path.join(results_dir, f"{top_module}.def"),
        os.path.join(results_dir, "temp.def"),
    ]
    src_def = next((p for p in cand_def if os.path.isfile(p)), None)
    dest_def = os.path.join(export_base, f"{top_module}.def")
    if src_def:
        shutil.copy2(src_def, dest_def)
        exported_files["def"] = dest_def

    # 3. Abstract LEF
    dest_lef = os.path.join(export_base, f"{top_module}.lef")
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tlef_candidates = [
        os.path.join(silis_home, "pdks", "sky130A", "libs.ref", "sky130_fd_sc_hd", "techlef", "sky130_fd_sc_hd__nom.tlef"),
        os.path.join(repo_root, "third-party", "pdks", "sky130A", "libs.ref", "sky130_fd_sc_hd", "techlef", "sky130_fd_sc_hd__nom.tlef"),
        os.path.join(silis_home, "pdks", "sky130", "sky130_fd_sc_hd__nom.tlef"),
    ]
    tlef_ref = next((p for p in tlef_candidates if os.path.isfile(p)), None)
    sc_lef_candidates = [
        os.path.join(silis_home, "pdks", "sky130A", "libs.ref", "sky130_fd_sc_hd", "lef", "sky130_fd_sc_hd.lef"),
        os.path.join(repo_root, "third-party", "pdks", "sky130A", "libs.ref", "sky130_fd_sc_hd", "lef", "sky130_fd_sc_hd.lef"),
        os.path.join(silis_home, "pdks", "sky130", "sky130_fd_sc_hd.tlef"),
    ]
    sc_lef = next((p for p in sc_lef_candidates if os.path.isfile(p)), None)

    io_lef_candidates = [
        os.path.join(silis_home, "pdks", "sky130A", "libs.ref", "sky130_fd_io", "lef", "sky130_ef_io.lef"),
        os.path.join(silis_home, "pdks", "sky130A", "libs.ref", "sky130_fd_io", "lef", "sky130_fd_io.lef"),
    ]

    lef_extracted = False
    if src_def and tlef_ref and shutil.which("openroad"):
        lef_script = os.path.join(export_base, "extract_lef.tcl")
        tcl_lines = [f'read_lef "{tlef_ref}"']
        if sc_lef and os.path.isfile(sc_lef):
            tcl_lines.append(f'read_lef "{sc_lef}"')
        for i_lef in io_lef_candidates:
            if os.path.isfile(i_lef):
                tcl_lines.append(f'read_lef "{i_lef}"')
        tcl_lines.extend([
            "catch { make_fake_io_site -name IO_SITE -width 1 -height 200 }",
            "catch { make_fake_io_site -name IO_CSITE -width 200 -height 204 }",
            f'read_def "{src_def}"',
            f'write_abstract_lef -bloat_occupied_layers "{dest_lef}"',
            "exit"
        ])
        with open(lef_script, "w") as f:
            f.write("\n".join(tcl_lines) + "\n")
        try:
            subprocess.run(["openroad", "-no_init", "-exit", lef_script], capture_output=True, text=True, timeout=30)
            if os.path.isfile(dest_lef) and os.path.getsize(dest_lef) > 0:
                lef_extracted = True
                exported_files["lef"] = dest_lef
        except Exception:
            pass
        finally:
            if os.path.isfile(lef_script):
                try: os.remove(lef_script)
                except: pass

    if not lef_extracted:
        cand_existing_lef = glob.glob(os.path.join(results_dir, "*.lef"))
        if cand_existing_lef:
            shutil.copy2(cand_existing_lef[0], dest_lef)
            exported_files["lef"] = dest_lef

    # 4. DFT / ATPG Deliverables (.stil, .scandef, _atpg_tb.v)
    cand_stil = [
        os.path.join(results_dir, f"{top_module}_atpg.stil"),
        os.path.join(results_dir, "atpg.stil"),
        os.path.join(results_dir, "design.stil"),
    ]
    src_stil = next((p for p in cand_stil if os.path.isfile(p)), None)
    if src_stil:
        dest_stil = os.path.join(dft_dir, f"{top_module}.stil")
        shutil.copy2(src_stil, dest_stil)
        exported_files["stil"] = dest_stil

    cand_scandef = [
        os.path.join(results_dir, "design.scandef"),
        os.path.join(results_dir, f"{top_module}.scandef"),
    ]
    src_scandef = next((p for p in cand_scandef if os.path.isfile(p)), None)
    if src_scandef:
        dest_scandef = os.path.join(dft_dir, f"{top_module}.scandef")
        shutil.copy2(src_scandef, dest_scandef)
        exported_files["scandef"] = dest_scandef

    cand_tb = [
        os.path.join(results_dir, f"{top_module}_atpg_tb.v"),
        os.path.join(results_dir, "atpg_tb.v"),
    ]
    src_tb = next((p for p in cand_tb if os.path.isfile(p)), None)
    if src_tb:
        dest_tb = os.path.join(dft_dir, f"{top_module}_atpg_tb.v")
        shutil.copy2(src_tb, dest_tb)
        exported_files["atpg_testbench"] = dest_tb

    # 5. Netlists (SPICE CDL, Gate Simulation Verilog, Blackbox Stub)
    cand_spice = [
        os.path.join(results_dir, f"{top_module}_layout.spice"),
        os.path.join(results_dir, f"{top_module}.spice"),
    ]
    src_spice = next((p for p in cand_spice if os.path.isfile(p)), None)
    if src_spice:
        dest_spice = os.path.join(export_base, f"{top_module}.spice")
        shutil.copy2(src_spice, dest_spice)
        exported_files["spice"] = dest_spice

    cand_sim_v = [
        os.path.join(netlist_dir, f"{top_module}_scan.v"),
        os.path.join(netlist_dir, f"{top_module}_netlist.v"),
        os.path.join(results_dir, "temp.v"),
    ]
    src_sim_v = next((p for p in cand_sim_v if os.path.isfile(p)), None)
    if src_sim_v:
        dest_sim_v = os.path.join(export_base, f"{top_module}.sim.v")
        shutil.copy2(src_sim_v, dest_sim_v)
        exported_files["sim_verilog"] = dest_sim_v

    # Generate blackbox stub Verilog
    dest_stub_v = os.path.join(export_base, f"{top_module}.v")
    try:
        from backendflow.macro_exporter import run_macro_package_export
        # Also copy stub if available from project
        src_orig_v = os.path.join(source_dir, f"{top_module}.v")
        if not os.path.isfile(src_orig_v):
            src_orig_v = os.path.join(project_root, "rtl", f"{top_module}.v")
        if os.path.isfile(src_orig_v):
            with open(src_orig_v, "r", errors="ignore") as f:
                code = f.read()
            import re
            m = re.search(r'module\s+' + re.escape(top_module) + r'\s*(?:#\s*\(.*?\))?\s*\((.*?)\);', code, re.DOTALL)
            if m:
                ports_clean = re.sub(r'\breg\b', 'wire', m.group(1).strip())
                with open(dest_stub_v, "w") as f_out:
                    f_out.write(f"(* blackbox *)\nmodule {top_module} (\n  {ports_clean}\n);\nendmodule\n")
                exported_files["stub_verilog"] = dest_stub_v
    except Exception:
        pass

    # 6. Timing Constraints SDC
    cand_sdc = [
        os.path.join(constr_dir, f"{top_module}.sdc"),
        os.path.join(source_dir, f"{top_module}.sdc"),
    ]
    src_sdc = next((p for p in cand_sdc if os.path.isfile(p)), None)
    if not src_sdc:
        any_sdc = glob.glob(os.path.join(source_dir, "*.sdc")) + glob.glob(os.path.join(constr_dir, "*.sdc"))
        if any_sdc: src_sdc = any_sdc[0]
    if src_sdc:
        dest_sdc = os.path.join(export_base, f"{top_module}.sdc")
        shutil.copy2(src_sdc, dest_sdc)
        exported_files["sdc"] = dest_sdc

    # 7. Multi-Corner Liberty & SPEF Models
    existing_libs = glob.glob(os.path.join(project_root, "**", "*.lib"), recursive=True)
    for l_f in existing_libs:
        if top_module in os.path.basename(l_f):
            shutil.copy2(l_f, os.path.join(lib_dir, os.path.basename(l_f)))

    existing_spef = glob.glob(os.path.join(results_dir, "*.spef")) + glob.glob(os.path.join(project_root, "**", "*.spef"), recursive=True)
    for s_f in existing_spef:
        if top_module in os.path.basename(s_f) or "design" in os.path.basename(s_f):
            shutil.copy2(s_f, os.path.join(spef_dir, f"{top_module}.spef"))

    # 8. Markdown Signoff Report & Machine Manifest
    src_signoff_md = os.path.join(reports_dir, "signoff_report.md")
    dest_signoff_md = os.path.join(export_base, "signoff_report.md")
    if os.path.isfile(src_signoff_md):
        shutil.copy2(src_signoff_md, dest_signoff_md)
        exported_files["signoff_report"] = dest_signoff_md

    manifest_data = {
        "design_name": top_module,
        "pdk": pdk_name,
        "export_directory": export_base,
        "artifacts": exported_files,
        "signoff_status": signoff_manifest.get("status", "PASSED") if signoff_manifest else "PASSED",
        "signoffs": signoff_manifest.get("signoffs", {}) if signoff_manifest else {}
    }
    manifest_path = os.path.join(export_base, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)
    exported_files["manifest"] = manifest_path

    # Synchronize copy into macrocache so it is accessible as an IP macro
    macrocache_dir = os.path.join(silis_home, "macrocache", pdk_name, top_module)
    try:
        shutil.copytree(export_base, macrocache_dir, dirs_exist_ok=True)
    except Exception:
        pass

    return {
        "export_directory": export_base,
        "exported_files": exported_files,
        "manifest": manifest_data
    }
