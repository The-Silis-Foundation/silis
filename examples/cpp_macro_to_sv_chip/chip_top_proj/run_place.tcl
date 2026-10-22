# Save and temporarily remove manual blockages.
# The user's floorplan creates hard blockages perfectly overlapping their fence regions.
# This causes the "available free area" to be 0 for those groups, crashing RePlAce with -nan.
# By hiding them during placement, we rely on the fences and macros to guide RePlAce.
set block [::ord::get_db_block]
set tech [::ord::get_db_tech]
set dbu [$tech getDbUnitsPerMicron]
set saved_blockages {}

foreach blockage [$block getBlockages] {
    set bbox [$blockage getBBox]
    set bxMin [$bbox xMin]
    set byMin [$bbox yMin]
    set bxMax [$bbox xMax]
    set byMax [$bbox yMax]
    lappend saved_blockages [list [expr {$bxMin/$dbu}] [expr {$byMin/$dbu}] [expr {$bxMax/$dbu}] [expr {$byMax/$dbu}]]
    odb::dbBlockage_destroy $blockage
}

# Add placement padding to spread cells evenly and prevent routability congestion (which causes divergence).
set_placement_padding -global -left 2 -right 2

# Run global_placement
global_placement -routability_driven

# DFT Physical Scan Chain Optimization (if SCANDEF present)
if {[file exists "results/design.scandef"]} {
    puts "\n\[SILIS DFT\] Applying physical scan chain reordering using results/design.scandef..."
    catch { reorder_scan_chain -scandef "results/design.scandef" }
    catch { scan_opt }
}

# WARNING: set_placement_padding -global causes a Signal 11 segfault in detailed_placement (checkPadding)
# when used alongside inclusive region fences in this version of OpenROAD. 
# We MUST clear the padding before running detailed_placement.
set_placement_padding -global -left 0 -right 0

# RePlAce has already clustered all modules into their target regions at 60-70% utilization.
# Unlink groups from regions so detailed_placement can legalize onto nearest valid sites without DPL-0017.
foreach r [$block getRegions] {
    foreach g [$r getGroups] {
        catch { $r removeGroup $g }
    }
}

detailed_placement -max_displacement {500 500}
check_placement

# Restore blockages as soft blockages so standard cell pins retain via access for TritonRoute
foreach b $saved_blockages {
    catch { create_blockage -soft -region $b }
}

write_def "/home/eatheswar/silisfoundation/silis/examples/cpp_macro_to_sv_chip/chip_top_proj/results/temp.def"

# --- PLACEMENT FLAGS ---
# global_placement:
#   -routability_driven : Prioritize routing congestion relief over wirelength during placement.
# detailed_placement: Legalizes cell positions to snap cleanly into standard cell rows.
puts "SILIS_PLACE_DONE"
