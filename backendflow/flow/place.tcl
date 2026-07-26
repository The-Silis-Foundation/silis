global_placement -density 0.6
#global_placement -density 0.7 -routability_driven
#global_placement -skip_io
detailed_placement
#optimize_mirroring
{write_cmd}

# --- PLACEMENT FLAGS ---
# global_placement:
#   -density <0.0 to 1.0> : Target placement density. Lower means more spread out (helps fix routing congestion).
#   -routability_driven : Prioritize routing congestion relief over wirelength during placement.
#   -skip_io : Do not place IO pins (if already placed manually).
# detailed_placement: Legalizes cell positions to snap cleanly into standard cell rows.
# optimize_mirroring: Flips cells horizontally to reduce wirelength and congestion.
