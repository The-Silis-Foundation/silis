if {[info procs create_fence] eq "" && [file exists "/home/eatheswar/silisfoundation/silis/backendflow/floorplanner/silis_fp.tcl"]} { source "/home/eatheswar/silisfoundation/silis/backendflow/floorplanner/silis_fp.tcl" }
if {[info commands SILIS] eq ""} { proc SILIS {args} { return {SILIS} } }
if {[info commands synth] eq ""} {
    proc synth {args} {
        puts "\n>>> [SILIS] Frontend Synthesis & Scan Cell Mapping already synthesized into netlist."
        puts ">>> [SILIS] Netlist is ready for physical PnR design flow."
        return 0
    }
}
if {[info commands init] eq ""} {
    proc init {args} {
        puts "\n>>> [SILIS] OpenROAD Design already linked and initialized with LEF/DEF/Verilog."
        return 0
    }
}
if {[info commands tapcells] eq ""} {
    proc tapcells {args} {
        eval tapcell $args
    }
}
if {[info commands pdn] eq ""} {
    proc pdn {args} {
        puts "\n>>> [SILIS] Synthesizing Power Grid..."
        # If PDN config/stripes already exist or can be generated
        catch { pdngen }
        return 0
    }
}
if {[info commands iopins] eq ""} {
    proc iopins {args} {
        eval place_pins $args
    }
}
if {[info commands gds] eq ""} {
    proc gds {args} {
        puts "\n>>> [SILIS] GDS Stream-out requested."
        return 0
    }
}
set_thread_count [exec nproc]
read_lef "/home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef"
read_lef "/home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef"
read_liberty "/home/eatheswar/silisfoundation/silis/third-party/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
read_verilog "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/netlist/simple_alu_netlist.v"
link_design simple_alu
read_sdc "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/source/simple_alu.sdc"

set block [::ord::get_db_block]
set tech [::ord::get_db_tech]
set dbu [$tech getDbUnitsPerMicron]

set macros_json "\{\n  \"macros\": \{\n"
set first_macro 1
set total_std_cell_area 0.0
array set module_areas {}

foreach inst [$block getInsts] {
    set master [$inst getMaster]
    set m_width [$master getWidth]
    set m_height [$master getHeight]
    set m_area [expr {($m_width * 1.0 / $dbu) * ($m_height * 1.0 / $dbu)}]

    if { [$master isBlock] } {
        if { !$first_macro } { append macros_json ",\n" }
        set inst_name [$inst getName]
        set inst_name [string map [list \\ \\\\ \" \\"] $inst_name]
        append macros_json "    \"$inst_name\": \"[$master getName]\""
        set first_macro 0
    } else {
        set total_std_cell_area [expr {$total_std_cell_area + $m_area}]
        set inst_name [$inst getName]
        set parts [split $inst_name "/"]
        if { [llength $parts] > 1 } {
            set mod_name [join [lrange $parts 0 end-1] "/"]
            if { ![info exists module_areas($mod_name)] } {
                set module_areas($mod_name) 0.0
            }
            set module_areas($mod_name) [expr {$module_areas($mod_name) + $m_area}]
        }
    }
}
append macros_json "\n  \},\n  \"total_std_cell_area\": $total_std_cell_area,\n  \"modules\": \{\n"
set first_mod 1
foreach mod_name [array names module_areas] {
    if { !$first_mod } { append macros_json ",\n" }
    set clean_mod [string map [list \\ \\\\ \" \\"] $mod_name]
    append macros_json "    \"$clean_mod\": $module_areas($mod_name)"
    set first_mod 0
}
append macros_json "\n  \}\n\}"

file mkdir "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/reports"
set fp [open "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/simple_alu_macro_proj/reports/simple_alu_sizes.json" w]
puts $fp $macros_json
close $fp

puts "SILIS_INIT_DONE"
