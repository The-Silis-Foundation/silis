# riscv_core.sdc - Synopsys Design Constraints for RISC-V Core
# Optimized for OpenRoad and OpenSTA

# ========================================
# 1. Units Definition
# ========================================
set_units -time ns -resistance kOhm -capacitance pF -voltage V -current mA

# ========================================
# 2. Clock Definition
# ========================================
# Main system clock (100MHz - 10ns period)
create_clock -name clk -period 10.0 [get_ports clk]

# Clock uncertainty accounts for jitter and skew
# Setup: 2.5% of clock period
# Hold: 1.5% of clock period
set_clock_uncertainty -setup 0.25 [get_clocks clk]
set_clock_uncertainty -hold 0.15 [get_clocks clk]

# Clock transition time (rise/fall time)
set_clock_transition 0.15 [get_clocks clk]

# Clock latency (network delay)
# Source latency: from clock source to clock tree
# Network latency: through clock tree to registers
set_clock_latency -source 0.5 [get_clocks clk]
set_clock_latency 0.3 [get_clocks clk]

# ========================================
# 3. Input Constraints
# ========================================
# Input delays for instruction memory interface
set_input_delay -clock clk -max 3.0 [get_ports {imem_data[*]}]
set_input_delay -clock clk -min 0.5 [get_ports {imem_data[*]}]

# Input delays for data memory interface
set_input_delay -clock clk -max 3.0 [get_ports {dmem_rdata[*]}]
set_input_delay -clock clk -min 0.5 [get_ports {dmem_rdata[*]}]

# Reset is typically asynchronous but we constrain it anyway
set_input_delay -clock clk -max 2.0 [get_ports rst]
set_input_delay -clock clk -min 0.3 [get_ports rst]

# ========================================
# 4. Output Constraints
# ========================================
# Instruction memory interface outputs
set_output_delay -clock clk -max 3.0 [get_ports {imem_addr[*]}]
set_output_delay -clock clk -min 0.5 [get_ports {imem_addr[*]}]
set_output_delay -clock clk -max 2.5 [get_ports imem_valid]
set_output_delay -clock clk -min 0.4 [get_ports imem_valid]

# Data memory interface outputs
set_output_delay -clock clk -max 3.0 [get_ports {dmem_addr[*]}]
set_output_delay -clock clk -min 0.5 [get_ports {dmem_addr[*]}]
set_output_delay -clock clk -max 3.0 [get_ports {dmem_wdata[*]}]
set_output_delay -clock clk -min 0.5 [get_ports {dmem_wdata[*]}]
set_output_delay -clock clk -max 2.5 [get_ports {dmem_we[*]}]
set_output_delay -clock clk -min 0.4 [get_ports {dmem_we[*]}]
set_output_delay -clock clk -max 2.5 [get_ports dmem_valid]
set_output_delay -clock clk -min 0.4 [get_ports dmem_valid]

# Debug outputs
set_output_delay -clock clk -max 3.0 [get_ports {pc_out[*]}]
set_output_delay -clock clk -min 0.5 [get_ports {pc_out[*]}]
set_output_delay -clock clk -max 3.0 [get_ports {rd_addr[*]}]
set_output_delay -clock clk -min 0.5 [get_ports {rd_addr[*]}]
set_output_delay -clock clk -max 3.0 [get_ports {rd_data[*]}]
set_output_delay -clock clk -min 0.5 [get_ports {rd_data[*]}]
set_output_delay -clock clk -max 2.5 [get_ports reg_write]
set_output_delay -clock clk -min 0.4 [get_ports reg_write]

# ========================================
# 5. Load Capacitance
# ========================================
# External load on outputs (in pF)
# Assuming typical ASIC loads
set_load 0.05 [get_ports {imem_addr[*]}]
set_load 0.03 [get_ports imem_valid]
set_load 0.05 [get_ports {dmem_addr[*]}]
set_load 0.05 [get_ports {dmem_wdata[*]}]
set_load 0.03 [get_ports {dmem_we[*]}]
set_load 0.03 [get_ports dmem_valid]
set_load 0.05 [get_ports {pc_out[*]}]
set_load 0.05 [get_ports {rd_addr[*]}]
set_load 0.05 [get_ports {rd_data[*]}]
set_load 0.03 [get_ports reg_write]

# ========================================
# 6. Driving Cell
# ========================================
# Define what drives the inputs (affects input transition time)
set_driving_cell -lib_cell sky130_fd_sc_hd__inv_2 [get_ports {imem_data[*]}]
set_driving_cell -lib_cell sky130_fd_sc_hd__inv_2 [get_ports {dmem_rdata[*]}]
set_driving_cell -lib_cell sky130_fd_sc_hd__inv_2 [get_ports rst]

# ========================================
# 7. Design Rule Constraints
# ========================================
# Maximum transition time on any net (in ns)
set_max_transition 0.75 [current_design]

# Maximum fanout for any net
set_max_fanout 10 [current_design]

# Maximum capacitance on any net (in pF)
set_max_capacitance 0.5 [current_design]

# ========================================
# 8. Area Constraint
# ========================================
# Minimize area (set to 0 for minimum)
set_max_area 0

# ========================================
# 9. Multi-Cycle Paths
# ========================================
# Some paths in the pipeline may take multiple cycles
# Uncomment if you have specific multi-cycle paths

# Example: Memory access might take 2 cycles
# set_multicycle_path -setup 2 -from [get_pins *ex_mem*] -to [get_pins *mem_wb*]
# set_multicycle_path -hold 1 -from [get_pins *ex_mem*] -to [get_pins *mem_wb*]

# ========================================
# 10. False Paths
# ========================================
# Asynchronous reset path
set_false_path -from [get_ports rst]

# False paths between independent clock domains (if any)
# set_false_path -from [get_clocks clk1] -to [get_clocks clk2]

# ========================================
# 11. Case Analysis
# ========================================
# If certain signals are known to be constant during operation
# Uncomment and adjust as needed

# Example: Reset is inactive during normal operation
# set_case_analysis 0 [get_ports rst]

# ========================================
# 12. Path Groups
# ========================================
# Group paths for better reporting and optimization
group_path -name INPUTS -from [all_inputs]
group_path -name OUTPUTS -to [all_outputs]
group_path -name COMBO -from [all_inputs] -to [all_outputs]
group_path -name REG2REG -from [all_registers] -to [all_registers]

# Note: Specific pipeline stage grouping requires exact register names after synthesis
# Uncomment and adjust after synthesis if needed:
# group_path -name FETCH -from [get_pins if_id_*_reg*/Q] -to [get_pins id_ex_*_reg*/D]
# group_path -name DECODE -from [get_pins id_ex_*_reg*/Q] -to [get_pins ex_mem_*_reg*/D]
# group_path -name EXECUTE -from [get_pins ex_mem_*_reg*/Q] -to [get_pins mem_wb_*_reg*/D]

# ========================================
# 13. Timing Exceptions for Critical Paths
# ========================================
# Note: Specific path constraints require exact pin names after synthesis
# Uncomment and adjust after synthesis if needed:
# set_max_delay 7.0 -from [get_pins id_ex_*_reg*/Q] -to [get_pins ex_mem_*_reg*/D]
# set_max_delay 6.0 -from [get_pins registers_reg*/Q] -to [get_pins id_ex_*_reg*/D]

# ========================================
# 14. Clock Network (OpenSTA Compatible)
# ========================================
# Mark clock as ideal network before clock tree synthesis
# Note: set_dont_touch_network is not supported in OpenSTA
set_ideal_network [get_ports clk]

# Propagate clock (use this after clock tree synthesis)
# set_propagated_clock [get_clocks clk]

# ========================================
# 15. Environmental Attributes
# ========================================
# Operating voltage
set_voltage 1.8 -object_list {VDD}
set_voltage 0.0 -object_list {VSS}

# Temperature and process corner
# These will be set by library operating conditions

# ========================================
# 16. Power Optimization Hints
# ========================================
# Uncomment for power-aware synthesis

# Maximum dynamic power budget (in mW)
# set_max_dynamic_power 100

# Maximum leakage power budget (in mW)
# set_max_leakage_power 5

# Clock gating for power saving
# set_clock_gating_style -sequential_cell latch -positive_edge_logic {integrated} -control_point before -control_signal scan_enable

# ========================================
# 17. Additional Constraints for OpenRoad
# ========================================
# These help OpenRoad's placer and router

# Utilization target (70% is typical)
# set_max_utilization 0.7

# Aspect ratio (1.0 = square)
# set_aspect_ratio 1.0

# Core margin (in microns)
# set_core_margin 2.0