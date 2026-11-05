drc off
locking off
gds readonly true
gds rescale false
lef read /home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef
lef read /home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef
gds read /home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds
def read /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/results/temp.def
load simple_alu
gds write /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/results/simple_alu.gds
quit -noprompt