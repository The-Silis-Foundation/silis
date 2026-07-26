source "{fix_script}"
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
