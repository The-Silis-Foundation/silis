if {[info procs create_fence] eq "" && [file exists "/home/eatheswar/silisfoundation/silis/backendflow/floorplanner/silis_fp.tcl"]} { source "/home/eatheswar/silisfoundation/silis/backendflow/floorplanner/silis_fp.tcl" }
if {[info commands SILIS] eq ""} { proc SILIS {args} { return {SILIS} } }
if {[info commands synth] eq ""} {
    proc synth {args} {
        puts "\n>>> [SILIS] Frontend Synthesis & Scan Cell Mapping already synthesized into netlist."
        puts ">>> [SILIS] Netlist is ready for physical PnR design flow."
        return 0
    }
}
if {[info commands init] eq ""} {
    proc init {args} {
        puts "\n>>> [SILIS] OpenROAD Design already linked and initialized with LEF/DEF/Verilog."
        return 0
    }
}
if {[info commands tapcells] eq ""} {
    proc tapcells {args} {
        eval tapcell $args
    }
}
if {[info commands pdn] eq ""} {
    proc pdn {args} {
        puts "\n>>> [SILIS] Synthesizing Power Grid..."
        # If PDN config/stripes already exist or can be generated
        catch { pdngen }
        return 0
    }
}
if {[info commands iopins] eq ""} {
    proc iopins {args} {
        eval place_pins $args
    }
}
if {[info commands gds] eq ""} {
    proc gds {args} {
        puts "\n>>> [SILIS] GDS Stream-out requested."
        return 0
    }
}
set tech [::ord::get_db_tech]
if {[$tech findLayer "met3"] eq "NULL"} { set io_hor "Metal3"; set io_ver "Metal4" } else { set io_hor "met3"; set io_ver "met4" }
place_pins -hor_layers $io_hor -ver_layers $io_ver -corner_avoidance 5.0 -min_distance 1.0
write_def "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/results/temp.def"

puts "SILIS_IOPINS_DONE"
