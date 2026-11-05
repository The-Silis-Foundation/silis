# ==============================================================================
# SDC Constraints for simple_alu
# Target: 100 MHz (10.0 ns)
# ==============================================================================

create_clock -name clk -period 10.000 [get_ports clk]
set_clock_uncertainty 0.25 [get_clocks clk]
set_clock_transition 0.15 [get_clocks clk]

set_input_delay 2.0 -clock clk [all_inputs]
set_output_delay 2.0 -clock clk [all_outputs]
