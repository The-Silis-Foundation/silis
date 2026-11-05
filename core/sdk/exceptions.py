"""
silis/core/sdk/exceptions.py
Structured EDA Domain Exceptions for the Silis Platform.
Replaces silent error swallowing and vague runtime errors with fail-fast,
actionable design and verification exceptions.
"""

class SilisEDAError(Exception):
    """Base exception for all Silis EDA runtime and pipeline errors."""
    pass


class DRCViolationError(SilisEDAError):
    """Raised when detailed routing or geometric DRC checks find violations."""
    def __init__(self, violation_count: int, report_path: str = ""):
        self.violation_count = violation_count
        self.report_path = report_path
        super().__init__(
            f"DRC violation threshold exceeded: {violation_count} violations detected. Report: {report_path}"
        )


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
