"""
Base Validator Module
=====================
Validator interface and result.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ValidationError:
    """Single validation error."""
    field: str
    message: str
    severity: str = "error"
    code: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validation."""
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    def add_error(self, field: str, message: str, code: str = None):
        """Add an error."""
        self.errors.append(ValidationError(field=field, message=message, code=code))
        self.valid = False

    def add_warning(self, field: str, message: str, code: str = None):
        """Add a warning."""
        self.warnings.append(ValidationError(field=field, message=message, code=code))

    def to_dict(self) -> Dict:
        return {
            "valid": self.valid,
            "errors": [
                {"field": e.field, "message": e.message, "severity": e.severity}
                for e in self.errors
            ],
            "warnings": [
                {"field": w.field, "message": w.message, "severity": w.severity}
                for w in self.warnings
            ]
        }


class Validator(ABC):
    """Abstract base class for validators."""

    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    @abstractmethod
    def validate(self, data: Any) -> ValidationResult:
        """Validate data and return result."""
        pass

    def _create_result(self) -> ValidationResult:
        """Create a validation result."""
        return ValidationResult(
            valid=len(self.errors) == 0,
            errors=self.errors.copy(),
            warnings=self.warnings.copy()
        )

    def _reset(self):
        """Reset errors and warnings."""
        self.errors = []
        self.warnings = []