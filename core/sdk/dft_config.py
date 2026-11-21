"""
silis/core/sdk/dft_config.py
Canonical Design-for-Testability (DFT) Configuration Specification.
Defines strongly typed DFTConfig dataclass ensuring 100% GUI-SDK parity.
Zero emojis.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List


@dataclass
class DFTConfig:
    """
    Complete configuration for Silis Tier-1 DFT & Testability Suite.
    Shared identically across headless Python SDK and GUI interactive dialogs.
    """
    # Core Scan Chain Insertion
    enabled: bool = True
    scan_in: str = "scan_in"
    scan_out: str = "scan_out"
    scan_en: str = "scan_en"
    scan_clk: str = "clk"
    lockup_latches: bool = True
    icg_bypass: bool = True

    # On-Chip Continuous Flow Decompressor (EDT) & Spatial Compactor
    compression: bool = False
    compression_ratio: int = 50
    external_channels: int = 4
    internal_chains: int = 128
    x_masking: bool = True

    # Memory BIST & BIRA Self-Repair
    mbist: bool = False
    march_algorithm: str = "MARCH_C_PLUS"
    enable_bira: bool = True
    clamp_macros: bool = True

    # IEEE 1149.1 JTAG TAP & Boundary Scan
    jtag: bool = False
    device_id: str = "0x00010001"
    ir_length: int = 4
    export_bsdl: bool = True

    # At-Speed Delay Testing (LOC / LOS)
    at_speed: bool = False
    launch_mode: str = "LOC"
    slack_cutoff_ns: float = 0.500

    def validate(self) -> None:
        """Validates all parameter invariants before synthesis or execution."""
        if self.compression_ratio < 1 or self.compression_ratio > 500:
            raise ValueError(f"Compression ratio must be in range [1, 500], got {self.compression_ratio}")
        if self.external_channels < 1 or self.external_channels > 64:
            raise ValueError(f"External ATE channels must be in range [1, 64], got {self.external_channels}")
        if self.internal_chains < self.external_channels:
            raise ValueError(
                f"Internal chains ({self.internal_chains}) must be >= external channels ({self.external_channels})"
            )
        if self.march_algorithm not in ("MARCH_C_PLUS", "MARCH_SS", "MARCH_C", "MATS_PLUS"):
            raise ValueError(f"Unsupported MARCH algorithm: {self.march_algorithm}")
        if self.ir_length not in (4, 5, 8, 16):
            raise ValueError(f"JTAG Instruction Register length must be 4, 5, 8, or 16 bits, got {self.ir_length}")
        if self.launch_mode not in ("LOC", "LOS"):
            raise ValueError(f"At-speed launch mode must be 'LOC' or 'LOS', got '{self.launch_mode}'")
        if self.slack_cutoff_ns < 0.0:
            raise ValueError(f"OpenSTA slack cutoff must be non-negative, got {self.slack_cutoff_ns}")

    def to_dict(self) -> Dict[str, Any]:
        """Converts configuration to primitive dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DFTConfig":
        """Instantiates configuration from dictionary with safe default fallbacks."""
        if not data:
            return cls()
        filtered = {}
        for k in cls.__dataclass_fields__.keys():
            if k in data:
                filtered[k] = data[k]
        cfg = cls(**filtered)
        cfg.validate()
        return cfg
