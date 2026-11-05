sta::set_thread_count [exec nproc]
        read_liberty /home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
        read_verilog /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/netlist/chip_top_netlist.v
        link_design chip_top
        read_sdc /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/source/chip_top.sdc
        report_checks -path_delay max -fields {slew cap input_pins nets fanout} -format full_clock_expanded -group_count 100 > /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/reports/timing.rpt
        report_power > /home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/reports/power.rpt
        exit
        