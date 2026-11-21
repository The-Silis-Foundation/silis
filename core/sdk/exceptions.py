"""
silis/core/sdk/exceptions.py
Structured EDA Domain Exceptions for the Silis Platform.
Replaces silent error swallowing and vague runtime errors with fail-fast,
actionable design and verification exceptions.
"""

import sys
from typing import Tuple, Union, Optional, List, Dict

# Ensure module alias parity across both 'sdk.exceptions' and 'silis.core.sdk.exceptions'
if __name__ == "sdk.exceptions":
    sys.modules.setdefault("silis.core.sdk.exceptions", sys.modules[__name__])
elif __name__ == "silis.core.sdk.exceptions":
    sys.modules.setdefault("sdk.exceptions", sys.modules[__name__])

class SilisEDAError(Exception):
    """Base exception for all Silis EDA runtime and pipeline errors."""
    pass


class DRCViolationError(SilisEDAError):
    """Raised when detailed routing, placement, or geometric DRC checks find violations."""
    def __init__(self, violation_count_or_msg=1, report_path: str = ""):
        from typing import Union
        if isinstance(violation_count_or_msg, str):
            self.violation_count = 1
            self.message = violation_count_or_msg
            self.report_path = report_path
            super().__init__(self.message)
        else:
            self.violation_count = int(violation_count_or_msg)
            self.report_path = report_path
            self.message = report_path or f"{self.violation_count} DRC violations detected."
            super().__init__(
                f"DRC violation threshold exceeded: {self.violation_count} violations detected. Details: {self.report_path}"
            )


class PlacementContainmentError(DRCViolationError):
    """Raised when an instance, macro, halo, or voltage fence exceeds the legal core boundary or die area."""
    def __init__(self, element: str, bbox, boundary, boundary_name: str = "core"):
        self.element = element
        self.bbox = tuple(bbox)
        self.boundary = tuple(boundary)
        self.boundary_name = boundary_name
        overshoots = []
        if self.bbox[0] < (self.boundary[0] - 0.001):
            overshoots.append(f"left overshoot: {self.boundary[0] - self.bbox[0]:.3f} um below {boundary_name}.x1 ({self.boundary[0]:.3f} um)")
        if self.bbox[1] < (self.boundary[1] - 0.001):
            overshoots.append(f"bottom overshoot: {self.boundary[1] - self.bbox[1]:.3f} um below {boundary_name}.y1 ({self.boundary[1]:.3f} um)")
        if self.bbox[2] > (self.boundary[2] + 0.001):
            overshoots.append(f"right overshoot: {self.bbox[2] - self.boundary[2]:.3f} um beyond {boundary_name}.x2 ({self.boundary[2]:.3f} um)")
        if self.bbox[3] > (self.boundary[3] + 0.001):
            overshoots.append(f"top overshoot: {self.bbox[3] - self.boundary[3]:.3f} um beyond {boundary_name}.y2 ({self.boundary[3]:.3f} um)")
        details = "; ".join(overshoots) or "out of bounds"
        msg = (
            f"Placement Containment Violation: '{element}' with bounding box "
            f"[{self.bbox[0]:.3f}, {self.bbox[1]:.3f}, {self.bbox[2]:.3f}, {self.bbox[3]:.3f}] um "
            f"exceeds {boundary_name} boundary [{self.boundary[0]:.3f}, {self.boundary[1]:.3f}, {self.boundary[2]:.3f}, {self.boundary[3]:.3f}] um. "
            f"Encroachments: {details}."
        )
        super().__init__(1, msg)


class LVSViolationError(SilisEDAError):
    """Raised when Layout-Versus-Schematic (LVS) verification detects mismatches."""
    def __init__(self, mismatch_count: int, report_path: str = ""):
        self.mismatch_count = mismatch_count
        self.report_path = report_path
        super().__init__(
            f"LVS verification failed: {mismatch_count} device/net mismatches found. Report: {report_path}"
        )


class TimingSlackViolationError(SilisEDAError):
    """Raised when setup or hold timing slack fails signoff requirements."""
    def __init__(self, wns: float, tns: float, corner: str = "nom"):
        self.wns = wns
        self.tns = tns
        self.corner = corner
        super().__init__(
            f"Timing signoff violation [{corner}]: WNS = {wns:.3f} ns, TNS = {tns:.3f} ns (slack < 0.0)"
        )


class AntennaViolationError(SilisEDAError):
    """Raised when antenna checker identifies gate damage ratio violations."""
    def __init__(self, pin_count: int, report_path: str = ""):
        self.pin_count = pin_count
        self.report_path = report_path
        super().__init__(
            f"Antenna rule violations detected: {pin_count} damaged pins found. Report: {report_path}"
        )


class PowerGridSynthesisError(SilisEDAError):
    """Raised when PDN generation fails or creates disconnected power islands."""
    pass


class RoutingOverflowError(SilisEDAError):
    """Raised when global router suffers unresolvable routing overflow."""
    pass


class OverlappingHaloError(SilisEDAError):
    """Raised when macro keepouts or routing corridors violate channel spacing."""
    pass


class MacroCollisionError(SilisEDAError):
    """Raised when two placed macros physically overlap in the floorplan."""
    def __init__(
        self,
        inst_a: str,
        box_a: Tuple[float, float, float, float],
        inst_b: str,
        box_b: Tuple[float, float, float, float],
        overlap_box: Tuple[float, float, float, float]
    ):
        self.inst_a = inst_a
        self.box_a = box_a
        self.inst_b = inst_b
        self.box_b = box_b
        self.overlap_box = overlap_box
        super().__init__(
            f"Physical collision detected between macro '{inst_a}' at {box_a} and '{inst_b}' at {box_b}. "
            f"Intersection overlap: {overlap_box}."
        )


class IllegalVoltageError(SilisEDAError):
    """Raised when power domain voltage violates technology library limits."""
    pass


class PipelineStateError(SilisEDAError):
    """Raised when pipeline step pre-conditions or atomic post-conditions are violated."""
    pass


class PipelineExecutionError(SilisEDAError):
    """Raised when a physical design pipeline step fails execution."""
    def __init__(self, step_name: str, exit_code: int = 1, message: str = ""):
        self.step_name = step_name
        self.exit_code = exit_code
        self.message = message
        err_msg = f"ASIC Pipeline Step '{step_name}' failed with error code {exit_code}."
        if message:
            err_msg += f" Details: {message}"
        super().__init__(err_msg)


class GridLegalizationError(SilisEDAError):
    """Raised when coordinates violate manufacturing grid quantization rules."""
    def __init__(self, element: str, x: float, y: float, grid: float = 0.005):
        self.element = element
        self.x = x
        self.y = y
        self.grid = grid
        super().__init__(
            f"Manufacturing grid quantization violation: '{element}' at ({x:.4f}, {y:.4f}) does not snap to grid {grid:.4f} um."
        )


class SignoffHandoffIntegrityError(SilisEDAError):
    """Raised when exported tapeout package violates structural completeness or artifact integrity."""
    pass

