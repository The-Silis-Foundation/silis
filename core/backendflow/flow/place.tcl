# =============================================================================
# SILIS ASIC EDA — Standard Cell Global & Detailed Placement
# =============================================================================
# RePlAce Divergence Prevention Architecture:
#
# FENCE regions (TYPE FENCE in DEF) create isolated Nesterov gradient sub-problems
# in OpenROAD's RePlAce engine. When a FENCE region contains mostly FIXED instances
# (POWER_SWITCH cells, tapcells, SRAM macros) with a tiny number of movable cells,
# the gradient field becomes numerically degenerate, and the step length explodes to
# Inf/NaN after ~2600-3150 iterations, causing GPL-0305.
#
# The correct architectural fix is:
#   1. Remove ALL groups from FENCE-type PD regions (PD_NPU, PD_CRYPTO, PD_LOWPWR)
#      These FENCE regions serve ONLY as physical keepout/power-domain boundaries.
#   2. Reattach functional instance groups to the co-located INCLUSIVE regions
#      (reg_npu, reg_crypto, reg_sensor) by scanning block-level group names.
#   3. Attach any orphaned groups (group_reg_sensor, group_reg_cpu, group_reg_bus)
#      to their matching INCLUSIVE regions so all instances are region-constrained.
#   4. Destroy any STILL-empty groups to prevent GPL-0306 zero-area divergence.
#
# This preserves voltage island containment (instances are still inside the correct
# physical boundary) while eliminating the RePlAce gradient instability.
# =============================================================================

set block [::ord::get_db_block]
set tech  [::ord::get_db_tech]
set dbu   [$tech getDbUnitsPerMicron]

# --- Step 1: Save and remove hard blockages ---
set saved_blockages {}
foreach blockage [$block getBlockages] {
    set bbox  [$blockage getBBox]
    lappend saved_blockages [list \
        [expr {[$bbox xMin] / $dbu}] \
        [expr {[$bbox yMin] / $dbu}] \
        [expr {[$bbox xMax] / $dbu}] \
        [expr {[$bbox yMax] / $dbu}]]
    odb::dbBlockage_destroy $blockage
}
puts "\[SILIS\] Removed [llength $saved_blockages] hard blockage(s) for placement."

# --- Step 2: Build inclusive-region name map ---
# Maps logical suffix -> inclusive dbRegion object.
array set inclusive_map {}
foreach r [$block getRegions] {
    set rname [$r getName]
    if {![string match "*PD_*" $rname] && ![string match "*pd_*" $rname]} {
        # reg_npu -> "npu", reg_crypto -> "crypto", reg_sensor -> "sensor", etc.
        set suffix [string map {"reg_" ""} $rname]
        set inclusive_map($suffix) $r
        if {$suffix eq "sensor"} { set inclusive_map(lowpwr) $r }
    }
}
puts "\[SILIS\] Inclusive regions: [array names inclusive_map]"

# --- Step 3: Detach ALL groups from FENCE PD regions ---
# Reattach to matching INCLUSIVE region so RePlAce creates a unified sub-problem.
foreach r [$block getRegions] {
    set rname [$r getName]
    if {[string match "*PD_*" $rname] || [string match "*pd_*" $rname]} {
        set suffix [string tolower [string map {"PD_" "" "pd_" ""} $rname]]
        foreach g [$r getGroups] {
            set gname [$g getName]
            catch { $r removeGroup $g }
            if {[info exists inclusive_map($suffix)]} {
                set inc_r $inclusive_map($suffix)
                catch { $inc_r addGroup $g }
                puts "\[SILIS\] Reattached '$gname': FENCE '$rname' -> INCLUSIVE '[$inc_r getName]'."
            } else {
                puts "\[SILIS\] WARNING: No inclusive region for suffix '$suffix'. '$gname' left unattached."
            }
        }
    }
}

# --- Step 4: Attach orphaned block-level groups to their INCLUSIVE regions ---
# Groups like group_reg_sensor, group_reg_cpu, group_reg_bus may exist at block level
# with no region assignment. Attach them to their inclusive counterparts.
foreach g [$block getGroups] {
    # Skip groups already attached to an inclusive region
    set already_attached 0
    foreach r [$block getRegions] {
        if {![string match "*PD_*" [$r getName]] && ![string match "*pd_*" [$r getName]]} {
            foreach rg [$r getGroups] {
                if {$rg eq $g} { set already_attached 1; break }
            }
        }
        if {$already_attached} { break }
    }
    if {$already_attached} { continue }

    set gname [$g getName]
    # Derive suffix from group name: group_reg_sensor -> "sensor", group_reg_npu -> "npu"
    set suffix [string map {"group_reg_" "" "group_" ""} $gname]
    if {[info exists inclusive_map($suffix)]} {
        set inc_r $inclusive_map($suffix)
        # Only attach if this group has instances
        if {[llength [$g getInsts]] > 0} {
            catch { $inc_r addGroup $g }
            puts "\[SILIS\] Attached orphaned group '$gname' -> inclusive region '[$inc_r getName]'."
        }
    }
}

# --- Step 4.5: Attach top-level unassigned movable cells to system bus group ---
# Top-level glue logic and UPF isolation cells not belonging to any hierarchy
# should be placed within the inclusive system bus region rather than creating
# a congested/divergent top-level Nesterov sub-problem.
set g_bus [$block findGroup "group_reg_bus"]
if {$g_bus ne "NULL" && $g_bus ne ""} {
    set top_cell_count 0
    foreach inst [$block getInsts] {
        if {![$inst isFixed] && ([$inst getGroup] eq "NULL" || [$inst getGroup] eq "")} {
            $g_bus addInst $inst
            incr top_cell_count
        }
    }
    if {$top_cell_count > 0} {
        puts "\[SILIS\] Bound $top_cell_count top-level unassigned movable cell(s) to group_reg_bus."
    }
}

# --- Step 5: Destroy empty groups across ALL regions and block ---
# An empty group in ANY region causes GPL-0306 (divide-by-zero in RePlAce).
set destroyed_count 0
foreach r [$block getRegions] {
    set dead {}
    foreach g [$r getGroups] {
        if {[llength [$g getInsts]] == 0} { lappend dead $g }
    }
    foreach dg $dead {
        catch { $r removeGroup $dg }
        catch { odb::dbGroup_destroy $dg }
        incr destroyed_count
    }
}
# Orphaned block-level groups with 0 instances
foreach g [$block getGroups] {
    if {[llength [$g getInsts]] == 0} {
        catch { odb::dbGroup_destroy $g }
        incr destroyed_count
    }
}
puts "\[SILIS\] Destroyed $destroyed_count empty group(s)."

# --- Step 6: Set wire RC for timing-driven placement ---
catch { set_wire_rc -layer met2 }

# --- Step 7: Global placement ---
# -density 0.50              : Conservative target density for macro-dense regions.
# -init_density_penalty 0.00002 : Lowers initial Nesterov gradient penalty to prevent
#                                  step length explosion in heterogeneous fixed/movable regions.
# -routability_driven        : Congestion-aware bin inflation.
set_placement_padding -global -left 2 -right 2
puts "\[SILIS\] Starting global_placement density=0.50 init_density_penalty=0.00002..."
global_placement -density 0.50 -init_density_penalty 0.00002 -routability_driven

# --- Step 8: DFT scan chain reordering (if SCANDEF present) ---
if {[file exists "results/design.scandef"]} {
    puts "\[SILIS DFT\] Applying physical scan chain reordering..."
    catch { reorder_scan_chain -scandef "results/design.scandef" }
    catch { scan_opt }
}

# --- Step 9: Detailed placement ---
# IMPORTANT: set_placement_padding -global causes Signal 11 in detailed_placement
# when inclusive region fences are active. Clear before detailed_placement.
set_placement_padding -global -left 0 -right 0
detailed_placement -max_displacement {500 500}
check_placement

# --- Step 10: Restore blockages as soft (routing retains via access) ---
foreach b $saved_blockages {
    catch { create_blockage -soft -region $b }
}
puts "\[SILIS\] Restored [llength $saved_blockages] blockage(s) as soft blockages."

{write_cmd}

# =============================================================================
# Placement Flags Reference:
#   global_placement:
#     -density <f>              : Target bin utilization [0.0, 1.0].
#     -init_density_penalty <f> : Initial Nesterov gradient penalty (lower = more stable).
#     -routability_driven       : Congestion-aware bin inflation.
#   detailed_placement:
#     -max_displacement {dx dy} : Maximum cell displacement in site units.
# =============================================================================
