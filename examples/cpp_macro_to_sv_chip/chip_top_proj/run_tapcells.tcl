tapcell -distance 14 -tapcell_master sky130_fd_sc_hd__tapvpwrvgnd_1; make_tracks
#tapcell -distance 14
write_def "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/results/temp.def"

# --- TAPCELL FLAGS ---
# tapcell:
#   -distance <microns> : Max distance between tap cells to prevent latch-up.
#   -tapcell_master <name> : Explicitly specify the tap cell name to use.
puts "SILIS_TAPCELLS_DONE"
