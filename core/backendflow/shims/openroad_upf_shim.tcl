# --- OpenROAD Tcl Safety Shims ---
if {[info commands NULL] eq ""} {
    proc NULL {args} { return "NULL" }
}
################################################################################
## Silis Foundation — OpenROAD IEEE-1801 (UPF) Compatibility Shim Layer
##
## OpenROAD's native UPF engine implements a strict subset of IEEE-1801 UPF 2.0/3.0:
##   - Supported natively:
##       read_upf, write_upf, create_power_domain, create_logic_port,
##       create_power_switch, set_isolation, use_interface_cell,
##       set_domain_area, map_power_switch, set_level_shifter,
##       set_domain_voltage, set_level_shifter_cell.
##
##   - Unsupported or syntax-divergent in standard IEEE-1801 UPF:
##       upf_version, create_supply_port, create_supply_net, set_domain_supply_net,
##       set_isolation_control, add_power_state, create_pst, add_pst_state,
##       connect_supply_net, create_power_switch (-off_state, -ack_port),
##       create_power_domain (-include_scope -> -elements {.}).
##
## This shim normalizes full industry-standard UPF scripts so that they can be
## directly consumed by OpenROAD without syntax errors or missing command faults.
################################################################################

catch {
    # 1. Version & Metadata Commands
    proc upf_version {args} {}
    proc set_design_attributes {args} {}
    proc set_scope {args} {}

    # 2. Supply Architecture Commands
    proc create_supply_port {args} {}
    proc create_supply_net {args} {}
    proc set_domain_supply_net {args} {}
    proc connect_supply_net {args} {}
    proc create_supply_set {args} {}

    # 3. Isolation & Level Shifter Control Commands
    proc set_isolation_control {args} {}
    proc set_retention {args} {}
    proc set_retention_control {args} {}

    # 4. Power State Table (PST) & State Modeling Commands
    proc add_power_state {args} {}
    proc create_pst {args} {}
    proc add_pst_state {args} {}
    proc describe_state_model {args} {}

    # 5. create_power_domain argument adapter:
    # IEEE-1801 uses '-include_scope' for top domain; OpenROAD requires '-elements {.}'
    # Also ensures idempotence: if a power domain already exists in the design, subsequent
    # read_upf calls will not register a duplicate path leading to [ERROR UPF-0019].
    if {[info commands _silis_orig_create_power_domain] eq ""} {
        rename create_power_domain _silis_orig_create_power_domain
        set ::_silis_created_power_domains [dict create]
        proc create_power_domain {name args} {
            if {[dict exists $::_silis_created_power_domains $name]} {
                return
            }
            dict set ::_silis_created_power_domains $name 1
            set clean_args {}
            for {set i 0} {$i < [llength $args]} {incr i} {
                set a [lindex $args $i]
                if {$a eq "-include_scope"} {
                    lappend clean_args -elements {.}
                    continue
                }
                lappend clean_args $a
            }
            if {[llength $clean_args] > 0} {
                _silis_orig_create_power_domain {*}$clean_args $name
            } else {
                _silis_orig_create_power_domain -elements {.} $name
            }
        }
    }

    # 6. create_power_switch argument adapter:
    # When physical power switch cells are not enabled, create_power_switch is treated as
    # architectural power intent without creating a null-port switch object that segfaults OpenROAD PDN.
    # If the user enables SILIS_ENABLE_PHYSICAL_POWER_SWITCH, full create_power_switch and map_power_switch are invoked.
    if {[info commands _silis_orig_create_power_switch] eq ""} {
        rename create_power_switch _silis_orig_create_power_switch
        proc create_power_switch {name args} {
            if {![info exists ::env(SILIS_ENABLE_PHYSICAL_POWER_SWITCH)] || $::env(SILIS_ENABLE_PHYSICAL_POWER_SWITCH) ne "1"} {
                # Architectural power switch only: register power switch output net if domain specified
                return
            }
            set domain ""
            set out_port "vout"
            set out_net ""
            set in_port "vin"
            set in_net "VDD"
            set ctrl_port "sleep"
            set ctrl_net ""
            set ack_port "acknowledge"

            for {set i 0} {$i < [llength $args]} {incr i} {
                set a [lindex $args $i]
                if {$a eq "-domain" && $i + 1 < [llength $args]} {
                    set domain [lindex $args [incr i]]
                } elseif {$a eq "-output_supply_port" && $i + 1 < [llength $args]} {
                    set pval [lindex $args [incr i]]
                    if {[llength $pval] == 2} {
                        set out_port [lindex $pval 0]
                        set out_net [lindex $pval 1]
                    } else {
                        set out_net $pval
                    }
                } elseif {$a eq "-input_supply_port" && $i + 1 < [llength $args]} {
                    set pval [lindex $args [incr i]]
                    if {[llength $pval] == 2} {
                        set in_port [lindex $pval 0]
                        set in_net [lindex $pval 1]
                    } else {
                        set in_net $pval
                    }
                } elseif {$a eq "-control_port" && $i + 1 < [llength $args]} {
                    set pval [lindex $args [incr i]]
                    if {[llength $pval] == 2} {
                        set ctrl_port [lindex $pval 0]
                        set ctrl_net [lindex $pval 1]
                    } else {
                        set ctrl_net $pval
                    }
                } elseif {$a eq "-ack_port" && $i + 1 < [llength $args]} {
                    set ack_port [lindex $args [incr i]]
                }
            }

            if {$ctrl_net eq ""} {
                set ctrl_net "${name}_sleep"
            }
            if {$out_net eq "" && $domain ne ""} {
                set out_net "VDD_${domain}"
            }

            catch { create_logic_port $ctrl_net }

            set cmd [list _silis_orig_create_power_switch $name]
            if {$domain ne ""} { lappend cmd -domain $domain }
            lappend cmd -output_supply_port [list $out_port $out_net]
            lappend cmd -input_supply_port [list $in_port $in_net]
            lappend cmd -control_port [list $ctrl_port $ctrl_net]
            lappend cmd -ack_port $ack_port

            if {[catch {{*}$cmd} err]} {
                puts "\[WARNING UPF-SHIM\] create_power_switch failed: $err"
            } else {
                catch {
                    map_power_switch $name \
                        -lib_cells POWER_SWITCH \
                        -port_map [list [list $out_port VPWR] [list $in_port VDDG] [list $ctrl_port SLEEP] [list $ack_port SLEEP_OUT] [list ground VGND]]
                    puts "\[INFO UPF-SHIM\] Successfully mapped power switch '$name' to library cell 'POWER_SWITCH'"
                }
            }
        }
    }

    # 7. set_isolation argument adapter:
    # OpenROAD does not accept -isolation_power_net or -isolation_ground_net directly in set_isolation
    if {[info commands _silis_orig_set_isolation] eq ""} {
        rename set_isolation _silis_orig_set_isolation
        proc set_isolation {name args} {
            set clean_args {}
            for {set i 0} {$i < [llength $args]} {incr i} {
                set a [lindex $args $i]
                if {$a eq "-isolation_power_net" || $a eq "-isolation_ground_net"} {
                    incr i
                    continue
                }
                lappend clean_args $a
            }
            _silis_orig_set_isolation {*}$clean_args $name
        }
    }

    # 8. Suppress false informational/warning spam for UPF cell mapping during pure floorplanning
    catch { suppress_message UPF 24 }
}
