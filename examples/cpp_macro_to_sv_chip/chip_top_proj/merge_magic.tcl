drc off
locking off
gds readonly true
gds rescale false
lef read /home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef
lef read /home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef
lef read /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/source/simple_alu.lef
gds read /home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds
gds read /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/source/simple_alu.gds
def read /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/results/temp.def
load chip_top
gds write /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/results/chip_top.gds
quit -noprompt