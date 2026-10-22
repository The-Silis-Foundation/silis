set tech [::ord::get_db_tech]
if {[$tech findLayer "met1"] ne "NULL"} {
    set pdn_layer_bot "met1"
    set pdn_layer_top "met4"
} else {
    set pdn_layer_bot "Metal1"
    set pdn_layer_top "Metal4"
}
add_global_connection -net {VDD} -pin_pattern {^VPWR$|^VDD$|^vccd1$} -power
add_global_connection -net {VSS} -pin_pattern {^VGND$|^VSS$|^vssd1$} -ground
set_voltage_domain -name {Core} -power {VDD} -ground {VSS}
define_pdn_grid -name {grid} -voltage_domains {Core}
add_pdn_stripe -grid {grid} -layer $pdn_layer_bot -width {0.48} -followpins
add_pdn_stripe -grid {grid} -layer $pdn_layer_top -width {1.6} -pitch {27.2} -offset {13.6} -extend_to_core_ring
add_pdn_connect -grid {grid} -layers "$pdn_layer_bot $pdn_layer_top"
#add_pdn_stripe -grid {grid} -layer {met5} -width {3.0} -pitch {40.0} -offset {20.0}
#add_pdn_connect -grid {grid} -layers {met4 met5}
pdngen
write_def "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/results/temp.def"

# --- PDN FLAGS ---
# add_global_connection:
#   -net / -pin_pattern / -power / -ground : Bind logical nets to physical supply nets (VDD/VSS).
# add_pdn_stripe:
#   -layer <> : Metal layer for stripes (e.g., met1, met4).
#   -width <> : Width of the power stripe.
#   -pitch <> : Distance between adjacent stripes of the same net.
#   -offset <> : Starting coordinate offset for the first stripe.
puts "SILIS_PDN_DONE"
