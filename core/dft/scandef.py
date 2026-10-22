"""
silis/dft/scandef.py
Standard IEEE / OpenROAD SCANDEF 5.8 Generator and Parser.

Generates standard SCANDEF format consumable by OpenROAD's `reorder_scan_chain` command:
    reorder_scan_chain -scandef "results/design.scandef"

SCANDEF Syntax:
    VERSION 5.8 ;
    DIVIDERCHAR "/" ;
    BUSBITCHARS "[]" ;
    DESIGN <design_name> ;

    SCANCHAINS <num_chains> ;
      - <chain_name>
        + START <pin_or_port>
        + FLOATING
            <inst_name> ( IN <in_pin> OUT <out_pin> )
            ...
        + STOP <pin_or_port> ;
    END SCANCHAINS

    END DESIGN
"""

import os
import re
from typing import List, Dict, Optional, Tuple, Any


class ScanCellInfo:
    """Represents a single scan flip-flop in a scan chain."""
    def __init__(
        self,
        instance_name: str,
        cell_type: str,
        scan_in_pin: str = "SCD",
        scan_out_pin: str = "Q",
        clock_pin: str = "CLK",
        scan_enable_pin: str = "SCE",
        data_in_pin: str = "D",
        bits: int = 1,
    ):
        self.instance_name = instance_name
        self.cell_type = cell_type
        self.scan_in_pin = scan_in_pin
        self.scan_out_pin = scan_out_pin
        self.clock_pin = clock_pin
        self.scan_enable_pin = scan_enable_pin
        self.data_in_pin = data_in_pin
        self.bits = bits

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance": self.instance_name,
            "cell_type": self.cell_type,
            "scan_in": self.scan_in_pin,
            "scan_out": self.scan_out_pin,
            "clock": self.clock_pin,
            "scan_enable": self.scan_enable_pin,
            "data_in": self.data_in_pin,
        }


class ScanChain:
    """Represents an ordered or floating scan chain."""
    def __init__(
        self,
        name: str = "chain_0",
        scan_in_port: str = "scan_in",
        scan_out_port: str = "scan_out",
        scan_enable_port: str = "scan_en",
        clock_port: str = "clk",
    ):
        self.name = name
        self.scan_in_port = scan_in_port
        self.scan_out_port = scan_out_port
        self.scan_enable_port = scan_enable_port
        self.clock_port = clock_port
        self.cells: List[ScanCellInfo] = []

    def add_cell(self, cell: ScanCellInfo):
        self.cells.append(cell)

    @property
    def length(self) -> int:
        return len(self.cells)


class SCANDEFGenerator:
    """
    Generates and parses OpenROAD-compatible SCANDEF 5.8 files.
    """

    def __init__(self, design_name: str = "design"):
        self.design_name = design_name
        self.chains: List[ScanChain] = []

    def add_chain(self, chain: ScanChain):
        self.chains.append(chain)

    def generate(self) -> str:
        """Emits standard SCANDEF 5.8 formatted text."""
        lines = [
            "VERSION 5.8 ;",
            'DIVIDERCHAR "/" ;',
            'BUSBITCHARS "[]" ;',
            f"DESIGN {self.design_name} ;\n",
            f"SCANCHAINS {len(self.chains)} ;",
        ]

        for chain in self.chains:
            lines.append(f"  - {chain.name}")
            lines.append(f"    + START {chain.scan_in_port}")
            if chain.cells:
                lines.append("    + FLOATING")
                for cell in chain.cells:
                    lines.append(
                        f"        {cell.instance_name} ( IN {cell.scan_in_pin} OUT {cell.scan_out_pin} )"
                    )
            lines.append(f"    + STOP {chain.scan_out_port} ;")

        lines.append("END SCANCHAINS\n")
        lines.append("END DESIGN")
        return "\n".join(lines) + "\n"

    def write_file(self, file_path: str):
        """Writes the generated SCANDEF to a target path."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(self.generate())

    @classmethod
    def parse_file(cls, file_path: str) -> "SCANDEFGenerator":
        """Parses an existing SCANDEF file into a SCANDEFGenerator object."""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"SCANDEF file not found: {file_path}")

        with open(file_path, "r") as f:
            content = f.read()

        m_des = re.search(r"DESIGN\s+(\S+)\s*;", content)
        design_name = m_des.group(1) if m_des else "design"
        generator = cls(design_name=design_name)

        # Extract chain blocks
        chain_blocks = re.findall(
            r"-\s*(\S+)\s*\+ START\s+(\S+)(.*?)\+ STOP\s+(\S+)\s*;",
            content,
            re.DOTALL,
        )

        for chain_name, start_port, body, stop_port in chain_blocks:
            chain = ScanChain(
                name=chain_name,
                scan_in_port=start_port,
                scan_out_port=stop_port,
            )

            # Find all floating or ordered cells
            cell_matches = re.findall(
                r"(\S+)\s*\(\s*IN\s+(\S+)\s+OUT\s+(\S+)\s*\)",
                body,
            )
            for inst, in_pin, out_pin in cell_matches:
                chain.add_cell(
                    ScanCellInfo(
                        instance_name=inst,
                        cell_type="unknown",
                        scan_in_pin=in_pin,
                        scan_out_pin=out_pin,
                    )
                )

            generator.add_chain(chain)

        return generator
