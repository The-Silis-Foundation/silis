# ADR-0001: Zero GUI-SDK Deviance and Strict Downstream Data Integrity

## Status
Accepted

## Context & Physical Problem
In digital ASIC physical design EDA software, visual presentation tools frequently diverge from headless automation scripts. When a graphic interface performs ad-hoc geometric bounding box calculations, rounding, or macro snapping independently of the core algorithmic engine, the emitted design exchange formats (DEF, TCL, UPF, SDC) deviate from what the physical designer observed on canvas.

Downstream engines—including **OpenROAD**, **Yosys**, and foundry DRC/LVS decks (Calibre, Pegasus)—execute emitted instructions verbatim. At deep submicron and nanometer nodes (such as SkyWater 130nm), off-grid coordinates ($x \pmod{0.005} \ne 0$), illegal macro halos, overlapping standard cell rows, or truncated UPF voltage specifications cause catastrophic downstream routing explosions, design rule check (DRC) violations, and silicon fabrication failures.

## Decision & Invariant
1. **The Parity Law**:
   The GUI is strictly a presentation shell over the Python SDK (`silis.core.sdk`). Interactive user gestures (moving a macro, adjusting die dimensions, synthesizing a power mesh) must invoke the exact same underlying SDK class methods that CLI runners or headless scripts call:
   $$\text{User Interaction / Qt Event} \longrightarrow \text{Silis SDK Object Method} \longrightarrow \text{State & Physics Mutation} \longrightarrow \text{Canvas View Update}$$

2. **Geometric Legalization Contract**:
   All coordinates and physical dimensions must be quantized to the manufacturing grid:
   $$\text{legalize\_coord}(v, g) = \left\lfloor \frac{v}{g} + 0.5 \right\rfloor \times g, \quad g = 0.005\ \mu\text{m}$$
   Macro $y$-origins must snap strictly to unit site row heights ($y = k \times 2.72\ \mu\text{m}$).

3. **Multi-Voltage Power Integrity (IEEE 1801 UPF 3.0)**:
   Every declared power domain must possess an explicit numeric voltage potential. Level shifters must resolve any domain transition where $|\Delta V| > 0.05\text{V}$, and gated power domains must declare clamp isolation rules.

4. **Atomic File Persistence**:
   Downstream scripts and session configurations are committed via transactional write-and-replace routines to prevent partial script emission.

## Consequences
- **Positive**:
  - Eliminates downstream OpenROAD DPL/PDN failures stemming from GUI-script discrepancies.
  - Guarantees 100% testability: any visual design operation can be tested and reproduced headlessly via SDK test scripts.
- **Trade-offs / Negative**:
  - User gestures that violate physical DRC rules (such as macro overlaps or off-grid placements) are rejected or quantized at interaction time rather than deferred to later flow stages.
