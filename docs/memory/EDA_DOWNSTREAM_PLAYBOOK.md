# OpenROAD Downstream Engine Error Playbook & Rules Reference

*Mission-critical error codes, symptoms, physical semiconductor mechanisms, and verified fixes for Silis EDA.*

---

## 1. Power Distribution Network (`PDN-*`)

### `[WARNING PDN-0178] Remaining channel (x1, y1) - (x2, y2) on met1 for nets: <NET>`
- **Stage**: `pdngen` / followpin strap generation
- **Physical Root Cause**:
  - OpenROAD generates followpin rails on `met1` along standard cell site rows.
  - When site rows are fragmented, sliced, or duplicated across power domains, OpenROAD detects a gap or short between row segments that cannot be legally bridged without violating pitch or minimum width rules.
  - A primary trigger in Silis: duplicate standard cell rows generated during multi-voltage domain slicing where duplicate tapcells are placed at identical $(x, y)$ coordinates.
- **Immediate Remedy**:
  1. Deduplicate standard cell rows in the block immediately after `initialize_floorplan` using integer-quantized origin keys:
     ```tcl
     set _key "${_site},[lindex $_orig 0],[lindex $_orig 1],${_scnt}"
     ```
  2. Avoid manual row destruction inside defined voltage regions.
  3. Ensure all macro halos and region boundaries align to integer multiples of the standard cell row height ($2.72\,\mu\text{m}$ in Sky130).

### `[ERROR PDN-0179] Unable to repair all channels.`
- **Stage**: `pdngen` completion abort
- **Physical Root Cause**:
  - Direct fatal escalation of `PDN-0178`.
  - OpenROAD attempted channel repair algorithms to connect unrouted followpin segments to the higher metal mesh (`met4`/`met5`), but the remaining unrouted channel violates DRC minimum enclosure or intersects an illegal blockage.
- **Immediate Remedy**:
  - Fix the underlying row discontinuity in floorplan setup before invoking `pdngen`.

### `[WARNING PDN-0209] Power switch for <pwr_sw_name> already exists`
- **Stage**: Multi-voltage power switch definition
- **Physical Root Cause**:
  - `define_power_switch_cell` or `create_power_switch` was invoked multiple times for the same power switch.
- **Immediate Remedy**:
  - Add idempotency guards in UPF shims to check if power switches are already defined.

---

## 2. Power Intent & Voltage Domains (`UPF-*`)

### `[ERROR UPF-0019] Power domain already exists`
- **Stage**: `read_upf`
- **Root Cause**: Redundant `create_power_domain` call on an existing domain.
- **Remedy**: Handled via `openroad_upf_shim.tcl`: tracking `dict exists $::_silis_created_power_domains $name`.

### `[WARNING UPF-0021] No area specified for <domain> power domain`
- **Stage**: Floorplan initialization with multi-voltage intent
- **Root Cause**: `set_domain_area` was not called before `initialize_floorplan`.
- **Rule**: In OpenROAD IEEE-1801, `set_domain_area` **must precede** `initialize_floorplan`.

---

## 3. Placement & Density Legalization (`GPL-*` & `DPL-*`)

### `[ERROR GPL-0301] Utilization overflow in fence region`
- **Stage**: RePlAce global placement
- **Root Cause**: Fixed instances (tapcells, decaps, power switches) plus movable standard cells exceed 100% of the assigned fence boundary area.
- **Remedy**: Expand region bounding box or lower target density using `pipe.suggest_box(target_density=0.65)`.

### `[ERROR DPL-0036] Detailed placement legalization failure`
- **Stage**: OpenDP detailed placement
- **Root Cause**: Cell overlap in narrow channels between macros (<15–20 routing tracks).
- **Remedy**: Increase macro spacing $W_{\text{channel}} \ge 2 \times \text{Halo} + W_{\text{routing\_tracks}}$.

---

## 4. Clock Tree Synthesis & Routing (`CTS-*` & `DRT-*`)

### `[ERROR CTS-0043] Macro clock pin obstructed by blockage`
- **Stage**: TritonCTS
- **Root Cause**: Macro placement halo overlaps hard routing blockage or sits outside core cavity.
- **Remedy**: Maintain clean routing corridors directly to macro register clock pins.
