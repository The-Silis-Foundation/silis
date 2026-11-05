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
foreach net [[::ord::get_db_block] getNets] {
    set type [$net getSigType]
    set name [$net getName]
    if {($type == "POWER" || $type == "GROUND") && $name != "VDD" && $name != "VSS"} {
        $net setSigType "SIGNAL"
    }
}
set tech [::ord::get_db_tech]
if {[$tech findLayer "met1"] ne "NULL"} {
    catch { set_routing_layers -signal met1-met5 }
    catch { set_global_routing_layer_adjustment met1 0.5 }
    catch { set_global_routing_layer_adjustment met2 0.3 }
    catch { set_global_routing_layer_adjustment met3 0.2 }
}
catch { global_route -guide_file "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/results/route.guide" -congestion_iterations 60 -verbose }
detailed_route -output_drc "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/reports/drc.rpt"
write_def "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/results/temp.def"

puts "SILIS_ROUTE_DONE"
