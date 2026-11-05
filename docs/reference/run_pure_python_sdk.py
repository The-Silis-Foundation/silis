import os
import sys
import subprocess
import time

# 1. Setup Silis Path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "silis"))
sys.path.insert(0, REPO_ROOT)
import silis

print("==================================================================")
print("  🚀 SILIS PYTHON SDK: 100% NATIVE ASIC PROJECT & FLOW RUNNER")
print("==================================================================")

# 2. CREATE FRESH PROJECT USING PYTHON SDK
proj_loc = os.path.join(REPO_ROOT, "projects", "sram_soc_quad_pure_sdk")
if os.path.isdir(proj_loc):
    import shutil
    shutil.rmtree(proj_loc)

proj = silis.Project.create(
    name="sram_soc_quad_pure_sdk",
    top="sram_soc_quad_top",
    pdk="sky130",
    loc=proj_loc,
    macros=[
        "sky130_sram_1kbyte_1rw1r_32x256_8",
        "sky130_sram_2kbyte_1rw1r_32x512_8"
    ]
)
print(f"[SDK] Created Fresh Project at: {proj.proj_file}")

# Copy RTL, stubs, and SDC from sram_soc_quad_core
source_src = os.path.join(REPO_ROOT, "projects", "sram_soc_quad_core", "source")
for f in os.listdir(source_src):
    src_f = os.path.join(source_src, f)
    dst_f = os.path.join(proj.source_dir, f)
    if os.path.isfile(src_f):
        import shutil
        shutil.copy2(src_f, dst_f)

# Copy testbench to tb/
os.makedirs(os.path.join(proj.root_dir, "tb"), exist_ok=True)
tb_src = os.path.join(REPO_ROOT, "projects", "sram_soc_quad_core", "tb", "sram_soc_quad_top_tb.v")
if os.path.isfile(tb_src):
    import shutil
    shutil.copy2(tb_src, os.path.join(proj.root_dir, "tb", "sram_soc_quad_top_tb.v"))

proj.rtl_files = [os.path.join(proj.source_dir, "sram_soc_quad_top.v")]
proj.sdc_files = [os.path.join(proj.source_dir, "sram_soc_quad_top.sdc")]
proj.tb_files = [os.path.join(proj.root_dir, "tb", "sram_soc_quad_top_tb.v")]
proj.save()

# 3. PIPELINE EXECUTION WITH RICH PYTHON ARGUMENTS & VISIBLE DESKTOP WINDOW
with silis.Pipeline(proj) as pipe:
    # A. Frontend Synthesis
    print("\n>>> Step 1: RTL Synthesis via Python SDK...")
    pipe.synthesis()
    rep = proj.get_synthesis_report()
    print(f"[SDK SYNTH REPORT] Cells: {rep.cells}, Area: {rep.area} um^2, WNS: {rep.wns} ns, Status: {rep.status}")

    # B. Open Standalone Schematic Viewer Window
    print("\n>>> Step 2: Standalone Schematic Viewer Window...")
    netlist = proj.get_netlist()
    schem_win = silis.view_schematic(netlist, show=False)
    print(f"[SDK] Created Standalone Schematic Window: '{schem_win.windowTitle()}'")

    # C. OpenROAD Init
    print("\n>>> Step 3: Backend Design Init...")
    pipe.init()

    # D. Floorplan Completely in Python (NO manual script reading!)
    print("\n>>> Step 4: Floorplanning 100% via Python dict arguments...")
    pipe.floorplan(
        die_area=(0, 0, 2400, 2400),
        core_margin=(20, 20, 20, 20),
        macros=[
            # 4x 1KB SRAM (Orientation R90, non-locked distinct halos)
            {"inst": "u_sram_bank0", "pos": (120, 1850), "orient": "R90", "halo": [12, 10, 15, 10]},
            {"inst": "u_sram_bank1", "pos": (1850, 1850), "orient": "R90", "halo": [10, 14, 10, 16]},
            {"inst": "u_sram_bank2", "pos": (120, 120), "orient": "R90", "halo": [14, 12, 18, 10]},
            {"inst": "u_sram_bank3", "pos": (1850, 120), "orient": "R90", "halo": [10, 16, 12, 14]},
            # 1x 2KB Cache SRAM (Orientation R0, distinct halo)
            {"inst": "u_sram_cache2k", "pos": (850, 150), "orient": "R0", "halo": [15, 15, 12, 12]},
        ],
        regions=[
            # Fences and regions with 30% utilization
            {"module": "u_execution_core", "box": [600, 1300, 1000, 1700], "type": "exclusive", "density": 0.30, "halo": [5, 5, 5, 5]},
            {"module": "u_crypto_accel", "box": [1400, 1300, 1800, 1700], "type": "inclusive", "density": 0.30, "halo": [5, 5, 5, 5]},
            {"module": "u_dma_ctrl", "box": [1000, 700, 1400, 1100], "type": "exclusive", "density": 0.30, "halo": [4, 4, 4, 4]},
        ],
        blockages=[
            # Hard blockage
            {"box": [1100, 1100, 1300, 1300], "soft": False},
            # Soft blockage
            {"box": [700, 150, 800, 600], "soft": True},
        ]
    )

    # E. Spawn Standalone SiliconPeeker Layout Window onto Desktop
    print("\n>>> Step 5: Launching Standalone SiliconPeeker Window on Desktop Screen...")
    def_path = os.path.join(proj.results_dir, "temp.def")
    layout_proc = silis.view_layout(def_path, title="SILIS Live Layout — SRAM Quad Core")

    # F. Welltap & Endcap insertion with Python flags
    print("\n>>> Step 6: Well-Tap & Endcap Insertion (distance=14, endcap_cpp=1)...")
    pipe.tapcells(distance=14, endcap_cpp=1)

    # G. PDN Synthesis
    print("\n>>> Step 7: Power Distribution Network (PDN) Synthesis...")
    pipe.pdn()

    # H. IO Pin Placement with Python flags (met3 hor, met2 ver)
    print("\n>>> Step 8: IO Pin Placement (hor_layers='met3', ver_layers='met2')...")
    pipe.iopins(hor_layers="met3", ver_layers="met2")

    # I. Placement with Python density and padding flags
    print("\n>>> Step 9: Standard Cell Placement (density=0.40, pad_left=2, pad_right=2)...")
    pipe.place(density=0.40, pad_left=2, pad_right=2)

    # J. Clock Tree Synthesis with Python buffer flags
    print("\n>>> Step 10: Clock Tree Synthesis (TritonCTS)...")
    pipe.cts(root_buf="sky130_fd_sc_hd__clkbuf_8")

    # K. TritonRoute with Python iteration and layer flags
    print("\n>>> Step 11: TritonRoute Detailed Routing (iterations=30, met1 to met5)...")
    pipe.route(congestion_iterations=30, bottom_layer="met1", top_layer="met5")

    # L. GDS Stream-out
    print("\n>>> Step 12: Streaming out GDS Layout...")
    pipe.gds()

    # M. Post-Layout Signoff
    print("\n>>> Step 13: Multi-Corner PAT Signoff...")
    pat_rep = pipe.signoff("PAT")

    print("\n==================================================================")
    print("  🏆 FINAL PAT SIGNOFF REPORT SUMMARY")
    print("==================================================================")
    if pat_rep:
        print(f"  • Timing Closure Status: {'MET' if pat_rep.is_clean else 'VIOLATED'}")
        print(f"  • Worst Negative Slack : {pat_rep.wns} ns")
        print(f"  • Total Standard Cells : {pat_rep.cells}")
        print(f"  • Total Die Area       : {pat_rep.area} um^2")
        print(f"  • Total Chip Power     : {pat_rep.total_power_mw} mW")
        print(f"  • Critical Endpoint    : {pat_rep.critical_endpoint}")
    print("==================================================================\n")

    # N. Third-Party EDA Tools integration
    print(">>> Step 14: Third-Party EDA GUI Integration Available:")
    print("  • Magic VLSI Layout Viewer  : silis.view_magic(proj.get_gds())")
    vcds = proj.get_vcd_files()
    if vcds:
        print(f"  • GTKWave Waveform Viewer    : silis.view_gtkwave('{vcds[0]}')")
    print(f"  • OpenROAD Native GUI        : silis.view_openroad_gui(proj.get_def())")

print("\nAll Python SDK flow steps, layout viewing, and signoff completed successfully!")
