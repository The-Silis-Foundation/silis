
        read_liberty /home/ubuju/pdk/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
        read_verilog netlist/riscv_core_netlist.v
        link_design riscv_core
        read_sdc netlist/riscv_core.sdc
        report_checks -path_delay max -fields {slew cap input_pins nets fanout} -format full_clock_expanded -group_count 100 > reports/timing.rpt
        report_power > reports/power.rpt
        exit
        