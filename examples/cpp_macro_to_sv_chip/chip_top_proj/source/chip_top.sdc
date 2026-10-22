# chip_top SDC Timing Constraints
# Clock: 50 MHz (20.0 ns)
create_clock -name clk_pad -period 20.000 [get_ports clk_pad]
set_clock_uncertainty 0.25 [get_clocks clk_pad]
set_clock_transition 0.15 [get_clocks clk_pad]

set_input_delay 2.0 -clock clk_pad [all_inputs]
set_output_delay 2.0 -clock clk_pad [all_outputs]
