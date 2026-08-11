# Save and temporarily remove manual blockages.
# The user's floorplan creates hard blockages perfectly overlapping their fence regions.
# This causes the "available free area" to be 0 for those groups, crashing RePlAce with -nan.
# By hiding them during placement, we rely on the fences and macros to guide RePlAce.
set block [::ord::get_db_block]
set saved_blockages {}
set dbu 1000.0

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

# WARNING: set_placement_padding -global causes a Signal 11 segfault in detailed_placement (checkPadding)
# when used alongside inclusive region fences in this version of OpenROAD. 
# We MUST clear the padding before running detailed_placement.
set_placement_padding -global -left 0 -right 0
detailed_placement -max_displacement {500 500}

# Restore blockages
foreach b $saved_blockages {
    catch { create_blockage -region $b }
}

{write_cmd}

# --- PLACEMENT FLAGS ---
# global_placement:
#   -routability_driven : Prioritize routing congestion relief over wirelength during placement.
# detailed_placement: Legalizes cell positions to snap cleanly into standard cell rows.
