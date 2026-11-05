set tech [::ord::get_db_tech]
if {[$tech findLayer "met1"] ne "NULL"} {
    set _pdn_bot "met1"
    set _pdn_top "met4"
} else {
    set _pdn_bot "Metal1"
    set _pdn_top "Metal4"
}

set _blk [ord::get_db_block]
if {[$_blk findNet "VDD"] eq "NULL"} { odb::dbNet_create $_blk "VDD" }
if {[$_blk findNet "VSS"] eq "NULL"} { odb::dbNet_create $_blk "VSS" }

# 1. Global connections for standard cells and pads
add_global_connection -net {VDD} -pin_pattern {^VPWR$|^VDD$|^vccd1$} -power
add_global_connection -net {VSS} -pin_pattern {^VGND$|^VSS$|^vssd1$} -ground
add_global_connection -net {VDD} -inst_pattern {.*pad_v.*|.*IO_CORNER.*} -pin_pattern {^P_CORE$|^VCCD$|^DRN_LVC[12]$|^OGC_LVC$|^VCCHIB$|^VDDA$} -power
add_global_connection -net {VSS} -inst_pattern {.*pad_v.*|.*IO_CORNER.*} -pin_pattern {^G_CORE$|^VSSD$|^SRC_BDY_LVC[12]$|^BDY2_B2B$|^VSSA$} -ground
add_global_connection -net {VDDIO} -inst_pattern {.*} -pin_pattern {^VDDIO$|^VDDIO_Q$|^VSWITCH$} -power
add_global_connection -net {VSSIO} -inst_pattern {.*} -pin_pattern {^VSSIO$|^VSSIO_Q$} -ground
global_connect

# 2. Prune orphan row fragments between domain boundaries and macro keepouts
set _dead_rows [list]
foreach _r [$_blk getRows] {
    set _orig [$_r getOrigin]
    set _y [expr {[lindex $_orig 1] / 1000.0}]
    if {$_y >= 750.700 && $_y <= 766.000} {
        lappend _dead_rows $_r
    }
}
foreach _dr $_dead_rows { odb::dbRow_destroy $_dr }

# 3. Core Power Grid and Peripheral Ring
set_voltage_domain -name {Core} -power {VDD} -ground {VSS}
define_pdn_grid -name {grid_top} -voltage_domains {Core}
add_pdn_ring -grid {grid_top} -layers "met4 met5" -widths {5.0 5.0} -spacings {2.0 2.0} -core_offsets {5.0 5.0}
add_pdn_stripe -grid {grid_top} -layer $_pdn_bot -width {0.48} -followpins
add_pdn_stripe -grid {grid_top} -layer $_pdn_top -width {1.6} -pitch {27.2} -offset {13.6} -extend_to_core_ring
add_pdn_connect -grid {grid_top} -layers "$_pdn_bot $_pdn_top"
add_pdn_connect -grid {grid_top} -layers "met4 met5"

# 4. Switched Power Domains (FPS Multi-Voltage Architecture)
{power_domains_pdn}

# 5. Synthesize Power Distribution Network
pdngen
{write_cmd}
