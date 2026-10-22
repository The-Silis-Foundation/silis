source "{fix_script}"

# Fix DRT-0305: TritonRoute crashes if regular nets are marked as POWER/GROUND.
foreach net [[::ord::get_db_block] getNets] {
    set type [$net getSigType]
    set name [$net getName]
    if {($type == "POWER" || $type == "GROUND") && $name != "VDD" && $name != "VSS"} {
        $net setSigType "SIGNAL"
        puts "Fixed sigType of regular net $name from $type to SIGNAL"
    }
}

global_route -guide_file "{guide_path}" -congestion_iterations 50 -allow_congestion -verbose
#global_route -congestion_iterations 100
detailed_route -output_drc "{drc_path}"
#detailed_route -bottom_routing_layer met1 -top_routing_layer met5
#repair_antennas -iterations 5 sky130_fd_sc_hd__diode_2/DIODE
{write_cmd}

# --- ROUTING FLAGS ---
# global_route:
#   -congestion_iterations <N> : How aggressively the router tries to fix congestion (higher = slower but better).
# detailed_route:
#   -bottom_routing_layer / -top_routing_layer : Restrict routing to specific layers.
# repair_antennas:
#   repair_antennas -iterations 5 sky130_fd_sc_hd__diode_2/DIODE : Automatically insert antenna diodes on long nets.

