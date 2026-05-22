"""Error types for pipeline phase execution.

RecoverableError — phase can be skipped; pipeline continues.
PhaseError       — phase failed; pipeline should stop.
"""


class PhaseError(Exception):
    """Fatal phase error — pipeline should halt."""

    def __init__(self, phase: str, message: str, details: dict = None):
        super().__init__(f"[{phase}] {message}")
        self.phase = phase
        self.details = details or {}


class RecoverableError(Exception):
    """Non-fatal phase error — pipeline may continue."""

    def __init__(self, phase: str, message: str, details: dict = None):
        super().__init__(f"[{phase}] {message}")
        self.phase = phase
        self.details = details or {}
