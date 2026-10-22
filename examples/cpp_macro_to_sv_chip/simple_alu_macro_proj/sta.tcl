sta::set_thread_count [exec nproc]
        read_liberty /home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
        read_verilog /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/netlist/simple_alu_netlist.v
        link_design simple_alu
        read_sdc /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/source/simple_alu.sdc
        report_checks -path_delay max -fields {slew cap input_pins nets fanout} -format full_clock_expanded -group_count 100 > /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/reports/timing.rpt
        report_power > /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/reports/power.rpt
        exit
        