
            read_lef "/home/ubuju/pdk/techlef/sky130_fd_sc_hd__nom.tlef"
            read_lef "/home/ubuju/pdk/lef/sky130_fd_sc_hd.lef"
            read_liberty "/home/ubuju/pdk/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
            read_verilog "/home/ubuju/testprojects/riscv_core_project/netlist/riscv_core_netlist.v"
            link_design riscv_core
            read_sdc "/home/ubuju/testprojects/riscv_core_project/netlist/riscv_core.sdc"
            