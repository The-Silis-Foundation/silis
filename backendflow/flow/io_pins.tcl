place_pins -hor_layers met3 -ver_layers met4
#place_pins -random
#place_pins -exclude "left"
{write_cmd}

# --- IO PINS FLAGS ---
# place_pins:
#   -hor_layers / -ver_layers : Restrict pin placement to specific metal routing layers.
#   -random : Place pins randomly rather than uniformly distributed.
#   -exclude <sides> : Prevent pins on specific edges (e.g., left, right, top, bottom).
