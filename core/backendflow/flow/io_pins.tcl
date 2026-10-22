set tech [::ord::get_db_tech]
if {[$tech findLayer "met3"] ne "NULL"} {
    set io_hor "met3"
    set io_ver "met4"
} else {
    set io_hor "Metal3"
    set io_ver "Metal4"
}
place_pins -hor_layers $io_hor -ver_layers $io_ver -corner_avoidance 5.0 -min_distance 1.0
#place_pins -random
#place_pins -exclude "left"
{write_cmd}

# --- IO PINS FLAGS ---
# place_pins:
#   -hor_layers / -ver_layers : Restrict pin placement to specific metal routing layers.
#   -random : Place pins randomly rather than uniformly distributed.
#   -exclude <sides> : Prevent pins on specific edges (e.g., left, right, top, bottom).
