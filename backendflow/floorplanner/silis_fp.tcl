# ==============================================================================
# silis_fp.tcl - Silis ASIC High-Level Floorplanning Commands for OpenROAD
# Hides low-level ODB database plumbing from users.
# ==============================================================================

proc _silis_snap {val} {
    set snapped [expr {round($val / 0.005) * 0.005}]
    return [format "%.3f" $snapped]
}

# ------------------------------------------------------------------------------
# create_fence: Creates an exclusive physical fence for a hierarchical module
# Syntax: create_fence -module <name> -box {x1 y1 x2 y2} [-density <0.0-1.0>] [-halo {l r b t}]
# ------------------------------------------------------------------------------
proc create_fence {args} {
    set mod ""
    set box {}
    set boxes {}
    set density 0.60
    set halo {}

    set i 0
    while {$i < [llength $args]} {
        set opt [lindex $args $i]
        if {$opt eq "-module"} {
            incr i; set mod [lindex $args $i]
        } elseif {$opt eq "-box"} {
            incr i; set box [lindex $args $i]
        } elseif {$opt eq "-boxes"} {
            incr i; set boxes [lindex $args $i]
        } elseif {$opt eq "-density"} {
            incr i; set density [lindex $args $i]
        } elseif {$opt eq "-halo"} {
            incr i; set halo [lindex $args $i]
        }
        incr i
    }

    if {$boxes ne ""} {
        create_region -module $mod -boxes $boxes -type exclusive -density $density -halo $halo
        return
    }

    if {$mod eq "" || [llength $box] != 4} {
        puts "\[ERR\] create_fence usage: create_fence -module <name> -box {x1 y1 x2 y2} \[-density <0.0-1.0>\] \[-halo {l r b t}\]"
        return
    }

    create_region -module $mod -box $box -type exclusive -density $density -halo $halo
}

# ------------------------------------------------------------------------------
# create_region: Creates an inclusive or exclusive region for a hierarchical module
# Syntax: create_region -module <name> -box {x1 y1 x2 y2} [-type inclusive|exclusive] [-density <0.0-1.0>] [-halo {l r b t}]
# ------------------------------------------------------------------------------
proc create_region {args} {
    set mod ""
    set box {}
    set boxes {}
    set rtype "inclusive"
    set density 0.60
    set halo {}

    set i 0
    while {$i < [llength $args]} {
        set opt [lindex $args $i]
        if {$opt eq "-module"} {
            incr i; set mod [lindex $args $i]
        } elseif {$opt eq "-box"} {
            incr i; set box [lindex $args $i]
        } elseif {$opt eq "-boxes"} {
            incr i; set boxes [lindex $args $i]
        } elseif {$opt eq "-type"} {
            incr i; set rtype [string tolower [lindex $args $i]]
        } elseif {$opt eq "-density"} {
            incr i; set density [lindex $args $i]
        } elseif {$opt eq "-halo"} {
            incr i; set halo [lindex $args $i]
        }
        incr i
    }

    if {$boxes ne ""} {
        foreach b $boxes {
            create_region -module $mod -box $b -type $rtype -density $density -halo $halo
        }
        return
    }

    if {$mod eq "" || [llength $box] != 4} {
        puts "\[ERR\] create_region usage: create_region -module <name> -box {x1 y1 x2 y2} \[-type inclusive|exclusive\] \[-density <float>\] \[-halo {l r b t}\]"
        return
    }

    set block [::ord::get_db_block]
    set tech [::ord::get_db_tech]
    set dbu [$tech getDbUnitsPerMicron]

    set clean_mod [string map {"/" "_"} $mod]
    set reg_name "region_${clean_mod}"
    set grp_name "group_${clean_mod}"

    set odb_rtype [expr {$rtype eq "exclusive" ? "EXCLUSIVE" : "INCLUSIVE"}]

    set r [$block findRegion $reg_name]
    set is_new 0
    if {$r eq "NULL" || $r eq ""} {
        set r [odb::dbRegion_create $block $reg_name]
        $r setRegionType $odb_rtype
        set is_new 1
    }

    set x1 [_silis_snap [lindex $box 0]]
    set y1 [_silis_snap [lindex $box 1]]
    set x2 [_silis_snap [lindex $box 2]]
    set y2 [_silis_snap [lindex $box 3]]

    set x1_dbu [expr {int($x1 * $dbu)}]
    set y1_dbu [expr {int($y1 * $dbu)}]
    set x2_dbu [expr {int($x2 * $dbu)}]
    set y2_dbu [expr {int($y2 * $dbu)}]

    catch { odb::dbBox_create $r $x1_dbu $y1_dbu $x2_dbu $y2_dbu }

    set g [$block findGroup $grp_name]
    if {$g eq "NULL" || $g eq ""} {
        set g [odb::dbGroup_create $block $grp_name]
        $r addGroup $g
    }

    if {$is_new} {
        set inst_count 0
        foreach inst [$block getInsts] {
            set iname [$inst getName]
            if {[string match "${mod}/*" $iname] || $iname eq $mod} {
                $g addInst $inst
                incr inst_count
            }
        }
        puts "\[SILIS\] Created $rtype region '$reg_name' ($x1, $y1) to ($x2, $y2) with $inst_count instances."
    } else {
        puts "\[SILIS\] Appended rectilinear box ($x1, $y1) to ($x2, $y2) to region '$reg_name'."
    }

    # 4-strip perimeter blockage for halo keepout around region (preserving interior)
    if {[llength $halo] == 4} {
        set hl [lindex $halo 0]; set hr [lindex $halo 1]
        set hb [lindex $halo 2]; set ht [lindex $halo 3]

        if {$hl > 0 || $hr > 0 || $hb > 0 || $ht > 0} {
            set bx1 [_silis_snap [expr {$x1 - $hl}]]
            set by1 [_silis_snap [expr {$y1 - $hb}]]
            set bx2 [_silis_snap [expr {$x2 + $hr}]]
            set by2 [_silis_snap [expr {$y2 + $ht}]]

            # Left strip
            if {$hl > 0 && $bx1 < $x1} {
                catch { ::create_blockage -soft -region [list $bx1 $by1 $x1 $by2] }
            }
            # Right strip
            if {$hr > 0 && $x2 < $bx2} {
                catch { ::create_blockage -soft -region [list $x2 $by1 $bx2 $by2] }
            }
            # Bottom strip
            if {$hb > 0 && $by1 < $y1} {
                catch { ::create_blockage -soft -region [list $x1 $by1 $x2 $y1] }
            }
            # Top strip
            if {$ht > 0 && $y2 < $by2} {
                catch { ::create_blockage -soft -region [list $x1 $y2 $x2 $by2] }
            }
            puts "\[SILIS\] Added 4-strip soft halo keepout around region '$reg_name' (L:$hl R:$hr B:$hb T:$ht)."
        }
    }
}

# ------------------------------------------------------------------------------
# place_macro: Places a hard macro with orientation, snapping, FIRM status & halo
# Syntax: place_macro -inst <name> [-cell <name>] -origin {x y} [-orient <R0..MY90>] [-halo {l r b t}]
# ------------------------------------------------------------------------------
proc place_macro {args} {
    set inst ""
    set cell ""
    set origin {}
    set orient "R0"
    set halo {}

    set i 0
    while {$i < [llength $args]} {
        set opt [lindex $args $i]
        if {$opt eq "-inst" || $opt eq "-name" || $opt eq "-macro_name"} {
            incr i; set inst [lindex $args $i]
        } elseif {$opt eq "-cell"} {
            incr i; set cell [lindex $args $i]
        } elseif {$opt eq "-origin" || $opt eq "-location"} {
            incr i; set origin [lindex $args $i]
        } elseif {$opt eq "-orient" || $opt eq "-orientation"} {
            incr i; set orient [lindex $args $i]
        } elseif {$opt eq "-halo"} {
            incr i; set halo [lindex $args $i]
        }
        incr i
    }

    if {$inst eq "" || [llength $origin] != 2} {
        puts "\[ERR\] place_macro usage: place_macro -inst <name> \[-cell <cell>\] -origin {x y} \[-orient R0..MY90\] \[-halo {l r b t}\]"
        return
    }

    set ox [_silis_snap [lindex $origin 0]]
    set oy [_silis_snap [lindex $origin 1]]

    # Map MX90/MY90 aliases to OpenROAD's internal MXR90/MYR90
    if {$orient eq "MX90"} { set orient "MXR90" }
    if {$orient eq "MY90"} { set orient "MYR90" }

    # Execute firm placement in OpenROAD using -location so (ox, oy) is the exact lower-left of the box
    if {$cell ne ""} {
        catch { place_inst -name $inst -cell $cell -location "$ox $oy" -status FIRM -orientation $orient }
    } else {
        catch { place_inst -name $inst -location "$ox $oy" -status FIRM -orientation $orient }
    }
    puts "\[SILIS\] Placed macro '$inst' at ($ox, $oy) orientation $orient."

    # Halo blockage around macro
    if {[llength $halo] == 4} {
        set hl [lindex $halo 0]; set hr [lindex $halo 1]
        set hb [lindex $halo 2]; set ht [lindex $halo 3]
        if {$hl > 0 || $hr > 0 || $hb > 0 || $ht > 0} {
            set block [::ord::get_db_block]
            set inst_obj [$block findInst $inst]
            if {$inst_obj ne "NULL" && $inst_obj ne ""} {
                set bbox [$inst_obj getBBox]
                set dbu [[::ord::get_db_tech] getDbUnitsPerMicron]
                set x1 [expr {[$bbox xMin] * 1.0 / $dbu}]
                set y1 [expr {[$bbox yMin] * 1.0 / $dbu}]
                set x2 [expr {[$bbox xMax] * 1.0 / $dbu}]
                set y2 [expr {[$bbox yMax] * 1.0 / $dbu}]
                set bx1 [_silis_snap [expr {$x1 - $hl}]]
                set by1 [_silis_snap [expr {$y1 - $hb}]]
                set bx2 [_silis_snap [expr {$x2 + $hr}]]
                set by2 [_silis_snap [expr {$y2 + $ht}]]
                
                set die_bbox [$block getDieArea]
                set die_x1 [expr {[$die_bbox xMin] * 1.0 / $dbu}]
                set die_y1 [expr {[$die_bbox yMin] * 1.0 / $dbu}]
                set die_x2 [expr {[$die_bbox xMax] * 1.0 / $dbu}]
                set die_y2 [expr {[$die_bbox yMax] * 1.0 / $dbu}]
                if {$bx1 < $die_x1} { set bx1 $die_x1 }
                if {$by1 < $die_y1} { set by1 $die_y1 }
                if {$bx2 > $die_x2} { set bx2 $die_x2 }
                if {$by2 > $die_y2} { set by2 $die_y2 }

                if {$bx1 < $bx2 && $by1 < $by2} {
                    catch { ::create_blockage -region [list $bx1 $by1 $bx2 $by2] }
                    puts "\[SILIS\] Created halo blockage for macro '$inst' ($bx1, $by1) to ($bx2, $by2)."
                }
            }
        }
    }
}
