"""
silis/core/dft/jtag.py
IEEE 1149.1 Standard Test Access Port (TAP) and IEEE 1149.1b BSDL Specification Generator.
Exports formal Boundary Scan Description Language (BSDL) for ATE tester automation.
Zero emojis.
"""

import os
import re
from typing import Dict, List, Optional, Any, Tuple


def generate_bsdl_spec(
    top_module: str,
    pdk_name: str = "sky130",
    output_path: Optional[str] = None,
    device_id: str = "0x00010001",
    ir_length: int = 4,
    ports: Optional[List[Tuple[str, str, int]]] = None,  # (name, direction: in/out/inout, width)
    package_pin_map: str = "QFN_64",
) -> str:
    """
    Synthesizes a compliant IEEE 1149.1b BSDL file for top_module.
    Documents the TAP controller state machine, instruction register opcodes,
    and boundary scan register (BSR) cells.
    """
    # Parse 32-bit device ID
    try:
        val = int(device_id, 16) if device_id.startswith("0x") else int(device_id)
    except ValueError:
        val = 0x00010001
    idcode_bin = f"{val:032b}"
    ver_bits = idcode_bin[0:4]
    part_bits = idcode_bin[4:20]
    mfg_bits = idcode_bin[20:31]
    fixed_bit = "1"

    # Default ports if not supplied
    if not ports:
        ports = [
            ("clk", "in", 1),
            ("rst_n", "in", 1),
            ("gpio_io", "inout", 16),
            ("tck", "in", 1),
            ("tms", "in", 1),
            ("tdi", "in", 1),
            ("tdo", "out", 1),
            ("trst_n", "in", 1),
        ]

    # Logical port declarations
    port_decls = []
    for name, direction, width in ports:
        vhdl_dir = "in" if direction == "in" else ("out" if direction == "out" else "inout")
        if width > 1:
            port_decls.append(f"    {name} : {vhdl_dir} bit_vector({width - 1} downto 0);")
        else:
            port_decls.append(f"    {name} : {vhdl_dir} bit;")

    port_str = "\n".join(port_decls)

    # Pin Map Constants
    pin_mappings = []
    pin_num = 1
    for name, direction, width in ports:
        if width > 1:
            pin_mappings.append(f"{name}:({pin_num}..{pin_num + width - 1})")
            pin_num += width
        else:
            pin_mappings.append(f"{name}:{pin_num}")
            pin_num += 1

    pin_map_str = ", ".join(pin_mappings)

    # Instruction opcodes
    opcodes = [
        ('BYPASS', '1' * ir_length),
        ('IDCODE', f'0{"0" * (ir_length - 2)}1'),
        ('SAMPLE', f'0{"0" * (ir_length - 3)}10'),
        ('PRELOAD', f'0{"0" * (ir_length - 3)}10'),
        ('EXTEST', '0' * ir_length),
        ('CLAMP', f'0{"0" * (ir_length - 3)}100'[-ir_length:]),
        ('HIGHZ', f'0{"0" * (ir_length - 3)}101'[-ir_length:]),
        ('RUNBIST', f'0{"0" * (ir_length - 3)}110'[-ir_length:]),
    ]
    opcode_lines = []
    for op_name, op_code in opcodes:
        opcode_lines.append(f'    "{op_name:<14} ({op_code})," &')
    opcode_str = "\n".join(opcode_lines)[:-2]  # Remove trailing &

    # Boundary scan register mapping
    bsr_lines = []
    cell_idx = 0
    for name, direction, width in ports:
        if name in ("tck", "tms", "tdi", "tdo", "trst_n"):
            continue
        if width > 1:
            for b in range(width):
                sig_name = f"{name}({b})"
                if direction == "in":
                    bsr_lines.append(f'    "   {cell_idx:<3} (BC_1,  {sig_name:<12}, input,   X)," &')
                    cell_idx += 1
                elif direction == "out":
                    bsr_lines.append(f'    "   {cell_idx:<3} (BC_1,  {sig_name:<12}, output3, X, {cell_idx + 1}, 0, Z)," &')
                    cell_idx += 1
                    bsr_lines.append(f'    "   {cell_idx:<3} (BC_2,  *,            control, 1)," &')
                    cell_idx += 1
                else:  # inout
                    bsr_lines.append(f'    "   {cell_idx:<3} (BC_1,  {sig_name:<12}, input,   X)," &')
                    cell_idx += 1
                    bsr_lines.append(f'    "   {cell_idx:<3} (BC_1,  {sig_name:<12}, output3, X, {cell_idx + 1}, 0, Z)," &')
                    cell_idx += 1
                    bsr_lines.append(f'    "   {cell_idx:<3} (BC_2,  *,            control, 1)," &')
                    cell_idx += 1
        else:
            if direction == "in":
                bsr_lines.append(f'    "   {cell_idx:<3} (BC_1,  {name:<12}, input,   X)," &')
                cell_idx += 1
            elif direction == "out":
                bsr_lines.append(f'    "   {cell_idx:<3} (BC_1,  {name:<12}, output3, X, {cell_idx + 1}, 0, Z)," &')
                cell_idx += 1
                bsr_lines.append(f'    "   {cell_idx:<3} (BC_2,  *,            control, 1)," &')
                cell_idx += 1
            else:
                bsr_lines.append(f'    "   {cell_idx:<3} (BC_1,  {name:<12}, input,   X)," &')
                cell_idx += 1
                bsr_lines.append(f'    "   {cell_idx:<3} (BC_1,  {name:<12}, output3, X, {cell_idx + 1}, 0, Z)," &')
                cell_idx += 1
                bsr_lines.append(f'    "   {cell_idx:<3} (BC_2,  *,            control, 1)," &')
                cell_idx += 1

    bsr_str = "\n".join(bsr_lines)
    if bsr_str.endswith(' &'):
        bsr_str = bsr_str[:-2] + ';'
    else:
        bsr_str = bsr_str + ';'

    bsdl = f"""-- IEEE 1149.1b BSDL Specification for {top_module}
-- Process Design Kit: {pdk_name}
-- Generated by Silis ASIC Physical Design & Signoff Studio
-- Zero Emojis.

entity {top_module} is
  generic (PHYSICAL_PIN_MAP : string := "{package_pin_map}");

  port (
{port_str}
  );

  use STD_1149_1_2001.all;

  attribute COMPONENT_CONFORMANCE of {top_module} : entity is "STD_1149_1_2001";

  attribute PIN_MAP of {top_module} : entity is PHYSICAL_PIN_MAP;
  constant {package_pin_map} : PIN_MAP_STRING :=
    "{pin_map_str}";

  attribute TAP_SCAN_IN    of tdi    : signal is true;
  attribute TAP_SCAN_OUT   of tdo    : signal is true;
  attribute TAP_SCAN_MODE  of tms    : signal is true;
  attribute TAP_SCAN_CLOCK of tck    : signal is (25.0e6, BOTH);
  attribute TAP_SCAN_RESET of trst_n : signal is true;

  attribute INSTRUCTION_LENGTH of {top_module} : entity is {ir_length};
  attribute INSTRUCTION_OPCODE of {top_module} : entity is
{opcode_str};

  attribute IDCODE_REGISTER of {top_module} : entity is
    "{ver_bits}" &             -- 4-bit version
    "{part_bits}" & -- 16-bit part number
    "{mfg_bits}" &      -- 11-bit manufacturer ID
    "{fixed_bit}";                     -- mandatory fixed bit

  attribute BOUNDARY_LENGTH of {top_module} : entity is {cell_idx};
  attribute BOUNDARY_REGISTER of {top_module} : entity is
{bsr_str}
end {top_module};
"""

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(bsdl)

    return bsdl
