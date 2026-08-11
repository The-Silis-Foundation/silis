source "{fix_script}"

# Fix DRT-0305: TritonRoute crashes if regular nets are marked as POWER/GROUND.
foreach net [[::ord::get_db_block] getNets] {
    set type [$net getSigType]
    if {$type == "POWER" || $type == "GROUND"} {
        $net setSigType "SIGNAL"
        puts "Fixed sigType of regular net [$net getName] from $type to SIGNAL"
    }
}

global_route -guide_file "{guide_path}" -congestion_iterations 50 -verbose
#global_route -congestion_iterations 100
detailed_route -output_drc "{drc_path}"
#detailed_route -bottom_routing_layer met1 -top_routing_layer met5
{write_cmd}

# --- ROUTING FLAGS ---
# global_route:
#   -congestion_iterations <N> : How aggressively the router tries to fix congestion (higher = slower but better).
# detailed_route:
#   -bottom_routing_layer / -top_routing_layer : Restrict routing to specific layers.
