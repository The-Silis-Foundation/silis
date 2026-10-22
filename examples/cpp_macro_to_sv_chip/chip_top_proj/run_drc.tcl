drc off
gds read /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/results/design.gds
drc style drc(fast)
drc on
drc check
drc catchup
set count [drc list count]
puts "SILIS_DRC_VIOLATIONS: $count"
if {$count > 0} { drc list all }
quit