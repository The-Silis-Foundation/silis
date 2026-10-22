"""
cli_project.py
Headless ASIC Project Setup Engine for Silis.
Provides both an interactive terminal wizard and scriptable one-liner project setup.
Targeted specifically for SkyWater 130nm (sky130) and GlobalFoundries 180nm (gf180mcu).
Produces 100% identical project structure and silis.silisproj to the GUI wizard.
"""

import os
import sys
import glob
import json
import shutil
import re

# Pre-parsed Macro definitions for Sky130 and GF180
KNOWN_MACROS = {
    "sky130": [
        {
            "name": "sky130_sram_1kbyte_1rw1r_32x256_8",
            "desc": "Sky130 1KB SRAM (32-bit x 256 words, 1RW1R)",
            "stub": """// SkyWater 130 1KB SRAM Stub
module sky130_sram_1kbyte_1rw1r_32x256_8 (
    input clk0, input csb0, input web0, input [3:0] wmask0, input [7:0] addr0, input [31:0] din0, output [31:0] dout0,
    input clk1, input csb1, input [7:0] addr1, output [31:0] dout1
);
endmodule
"""
        },
        {
            "name": "sky130_sram_2kbyte_1rw1r_32x512_8",
            "desc": "Sky130 2KB SRAM (32-bit x 512 words, 1RW1R)",
            "stub": """// SkyWater 130 2KB SRAM Stub
module sky130_sram_2kbyte_1rw1r_32x512_8 (
    input clk0, input csb0, input web0, input [3:0] wmask0, input [8:0] addr0, input [31:0] din0, output [31:0] dout0,
    input clk1, input csb1, input [8:0] addr1, output [31:0] dout1
);
endmodule
"""
        }
    ],
    "gf180mcu": [
        {
            "name": "gf180mcu_fd_ip_sram__sram512x8m8wm1",
            "desc": "GF180 512B SRAM (8-bit x 512 words)",
            "stub": """// GlobalFoundries 180 512B SRAM Stub
module gf180mcu_fd_ip_sram__sram512x8m8wm1 (
    input CLK, input CEN, input WEN, input [8:0] A, input [7:0] D, output [7:0] Q
);
endmodule
"""
        }
    ]
}


def find_top_module_in_files(v_files):
    """Parses Verilog files to find declared modules and detects the top module."""
    declared = []
    instantiated = set()
    mod_pat = re.compile(r'\bmodule\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[#(;]')
    inst_pat = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s+(?:#\s*\(.*?\)\s*)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')

    for f in v_files:
        try:
            with open(f, 'r', errors='ignore') as fp:
                content = fp.read()
                # strip comments
                content = re.sub(r'//.*', '', content)
                content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
                for m in mod_pat.finditer(content):
                    m_name = m.group(1)
                    if m_name not in declared:
                        declared.append(m_name)
                for inst in inst_pat.finditer(content):
                    target_mod = inst.group(1)
                    instantiated.add(target_mod)
        except:
            pass

    candidates = [m for m in declared if m not in instantiated]
    if candidates:
        return candidates[0]
    return declared[0] if declared else "top"


def resolve_pdk_name(pdk_input):
    p = pdk_input.lower().strip()
    if "gf" in p or "180" in p:
        return "gf180mcu"
    return "sky130"


def create_project_structure(loc, name, top, pdk, rtl_paths=None, tb_paths=None, sdc_paths=None, macros=None):
    """Creates the standard Silis workspace layout matching SilisProjectWizard."""
    loc = os.path.abspath(loc)
    src_dir = os.path.join(loc, "source")
    net_dir = os.path.join(loc, "netlist")
    rep_dir = os.path.join(loc, "reports")
    res_dir = os.path.join(loc, "results")

    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(net_dir, exist_ok=True)
    os.makedirs(rep_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)

    final_rtl = []
    final_tb = []
    final_sdc = []

    # 1. RTL Files
    if rtl_paths:
        for p in rtl_paths:
            if os.path.isdir(p):
                for f in glob.glob(os.path.join(p, "*.v")) + glob.glob(os.path.join(p, "*.sv")) + glob.glob(os.path.join(p, "*.vhd")):
                    dest = os.path.join(src_dir, os.path.basename(f))
                    if os.path.abspath(f) != dest:
                        shutil.copy2(f, dest)
                    final_rtl.append(dest)
            elif os.path.isfile(p):
                dest = os.path.join(src_dir, os.path.basename(p))
                if os.path.abspath(p) != dest:
                    shutil.copy2(p, dest)
                final_rtl.append(dest)
    else:
        # Create template top module
        top_v = os.path.join(src_dir, f"{top}.v")
        if not os.path.exists(top_v):
            with open(top_v, 'w') as f:
                f.write(f"""// ==============================================================================
// Module: {top}
// Project: {name}
// Silicon Target: {pdk}
// ==============================================================================

module {top} (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  data_in,
    output reg  [7:0]  data_out
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= 8'h00;
        end else begin
            data_out <= data_in + 8'h01;
        end
    end

endmodule
""")
        final_rtl.append(top_v)

    # 2. Testbenches
    if tb_paths:
        for p in tb_paths:
            if os.path.isfile(p):
                dest = os.path.join(src_dir, os.path.basename(p))
                if os.path.abspath(p) != dest:
                    shutil.copy2(p, dest)
                final_tb.append(dest)
    else:
        tb_v = os.path.join(src_dir, f"tb_{top}.v")
        if not os.path.exists(tb_v):
            with open(tb_v, 'w') as f:
                f.write(f"""`timescale 1ns/1ps
module tb_{top};
    reg clk = 0;
    reg rst_n = 0;
    reg [7:0] data_in = 8'hAA;
    wire [7:0] data_out;

    {top} dut (
        .clk(clk),
        .rst_n(rst_n),
        .data_in(data_in),
        .data_out(data_out)
    );

    always #5 clk = ~clk;

    initial begin
        #20 rst_n = 1;
        #100 $finish;
    end
endmodule
""")
        final_tb.append(tb_v)

    # 3. SDC Constraints
    auto_sdc = False
    if sdc_paths:
        for p in sdc_paths:
            if os.path.isfile(p):
                dest = os.path.join(src_dir, os.path.basename(p))
                if os.path.abspath(p) != dest:
                    shutil.copy2(p, dest)
                final_sdc.append(dest)
    else:
        auto_sdc = True
        top_sdc = os.path.join(src_dir, f"{top}.sdc")
        if not os.path.exists(top_sdc):
            with open(top_sdc, 'w') as f:
                f.write(f"""# ==============================================================================
# SDC Constraints for {top}
# Target: 100 MHz (10.0 ns)
# ==============================================================================

create_clock -name clk -period 10.000 [get_ports clk]
set_clock_uncertainty 0.25 [get_clocks clk]
set_clock_transition 0.15 [get_clocks clk]

set_input_delay 2.0 -clock clk [all_inputs]
set_output_delay 2.0 -clock clk [all_outputs]
""")
        final_sdc.append(top_sdc)

    # 4. Macros
    macros_list = []
    if macros:
        pdk_key = resolve_pdk_name(pdk)
        known = {m["name"]: m for m in KNOWN_MACROS.get(pdk_key, [])}
        for m_name in macros:
            macros_list.append(m_name)
            if m_name in known:
                stub_file = os.path.join(src_dir, f"{m_name}_stub.v")
                with open(stub_file, 'w') as f:
                    f.write(known[m_name]["stub"])
                final_rtl.append(stub_file)

    # 5. Config File
    config = {
        "project_name": name,
        "top_module": top,
        "pdk": pdk,
        "macros": macros_list,
        "auto_sdc": auto_sdc,
        "rtl_files": final_rtl,
        "sdc_files": final_sdc,
        "tb_files": final_tb
    }

    proj_file = os.path.join(loc, "silis.silisproj")
    with open(proj_file, 'w') as f:
        json.dump(config, f, indent=4)

    import project_registry
    project_registry.register_project(loc)

    return proj_file, config


def run_interactive_init(default_name=None):
    """Guided terminal setup wizard matching the user's workflow."""
    print("\n" + "=" * 65)
    print("  ✨ SILIS ASIC PROJECT SETUP WIZARD")
    print("=" * 65 + "\n")

    # 1. Project Name & Location
    def_name = default_name or os.path.basename(os.getcwd())
    name_input = input(f"? Project Name [{def_name}]: ").strip()
    name = name_input if name_input else def_name

    loc_input = input(f"? Project Location [{os.getcwd()}]: ").strip()
    loc = os.path.abspath(loc_input) if loc_input else os.getcwd()

    # 2. Target PDK
    print("\n? Select Silicon PDK Target:")
    print("  [1] SkyWater 130nm (sky130)  [Recommended for OpenROAD]")
    print("  [2] GlobalFoundries 180nm (gf180mcu)")
    pdk_choice = input("Enter choice [1]: ").strip()
    pdk = "gf180mcu" if pdk_choice == "2" else "sky130"

    # 3. RTL Files
    print(f"\n? Import RTL files/directory? (y/N): ", end="")
    imp_rtl = input().strip().lower() == "y"
    rtl_files = []
    top_mod = name
    if imp_rtl:
        rtl_input = input("  Path to RTL file or directory: ").strip()
        if os.path.exists(rtl_input):
            rtl_files.append(rtl_input)
            if os.path.isdir(rtl_input):
                scanned = glob.glob(os.path.join(rtl_input, "*.v")) + glob.glob(os.path.join(rtl_input, "*.sv"))
                top_mod = find_top_module_in_files(scanned)
            elif os.path.isfile(rtl_input):
                top_mod = find_top_module_in_files([rtl_input])
    else:
        print(f"  -> Skipping. Will create template module '{name}'.")

    # Top module confirmation
    top_input = input(f"\n? Top Module Name [{top_mod}]: ").strip()
    top = top_input if top_input else top_mod

    # 4. Testbenches
    print(f"\n? Import Testbench files/directory? (y/N): ", end="")
    imp_tb = input().strip().lower() == "y"
    tb_files = []
    if imp_tb:
        tb_input = input("  Path to Testbench file or directory: ").strip()
        if os.path.exists(tb_input):
            tb_files.append(tb_input)

    # 5. SDC Constraints
    print(f"\n? Import SDC timing constraints? (y/N): ", end="")
    imp_sdc = input().strip().lower() == "y"
    sdc_files = []
    if imp_sdc:
        sdc_input = input("  Path to SDC file: ").strip()
        if os.path.exists(sdc_input):
            sdc_files.append(sdc_input)
    else:
        print("  -> Skipping. Will auto-generate standard 100 MHz clock constraint.")

    # 6. Hard Macros
    macros_selected = []
    avail_macros = KNOWN_MACROS.get(pdk, [])
    if avail_macros:
        print(f"\n? Available hard macros for {pdk}:")
        for i, m in enumerate(avail_macros):
            print(f"  [{i+1}] {m['name']} — {m['desc']}")
        m_choice = input("Select macros by number (comma-separated, or Enter to skip): ").strip()
        if m_choice:
            for part in m_choice.split(","):
                try:
                    idx = int(part.strip()) - 1
                    if 0 <= idx < len(avail_macros):
                        macros_selected.append(avail_macros[idx]["name"])
                except:
                    pass

    # Build Project
    proj_file, config = create_project_structure(
        loc=loc, name=name, top=top, pdk=pdk,
        rtl_paths=rtl_files, tb_paths=tb_files, sdc_paths=sdc_files, macros=macros_selected
    )

    print("\n" + "─" * 65)
    print(f"✔ Created project configuration: {os.path.relpath(proj_file, os.getcwd())}")
    print("✔ Created workspace layout:")
    print("  ├── source/")
    print(f"  │   ├── {top}.sdc (10.0 ns target clock)")
    if rtl_files:
        print(f"  │   └── [Imported RTL sources]")
    else:
        print(f"  │   ├── {top}.v")
        print(f"  │   └── tb_{top}.v")
    print("  ├── netlist/")
    print("  ├── reports/")
    print("  └── results/")
    print("─" * 65)
    print(f"🚀 Project '{name}' initialized successfully!")
    print(f"Next step: silis --run-synth {name} --tcl\n")
    return proj_file


def run_cli_init(name, rtl=None, tb=None, sdc=None, pdk="sky130", macros=None, top=None, loc=None):
    """One-liner flag-based setup."""
    if loc:
        target_loc = os.path.abspath(loc)
        proj_name = name
    elif os.path.isabs(name) or os.path.dirname(name):
        target_loc = os.path.abspath(name)
        proj_name = os.path.basename(name)
    else:
        target_loc = os.path.abspath(os.path.join(os.getcwd(), name))
        proj_name = name

    target_top = top or proj_name
    pdk_clean = resolve_pdk_name(pdk)

    if not top and rtl:
        all_v = []
        for r in rtl:
            if os.path.isdir(r):
                all_v += glob.glob(os.path.join(r, "*.v")) + glob.glob(os.path.join(r, "*.sv"))
            elif os.path.isfile(r):
                all_v.append(r)
        detected = find_top_module_in_files(all_v)
        if detected:
            target_top = detected

    proj_file, config = create_project_structure(
        loc=target_loc, name=proj_name, top=target_top, pdk=pdk_clean,
        rtl_paths=rtl, tb_paths=tb, sdc_paths=sdc, macros=macros
    )
    print(f"[SUCCESS] Initialized Silis ASIC project '{proj_name}' at {proj_file}")
    return proj_file
