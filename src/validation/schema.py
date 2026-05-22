"""
Schema Validator Module
=======================
Validates JSON schemas.
"""

from typing import Dict, Any
from .base import Validator, ValidationResult


class SchemaValidator(Validator):
    """Validates data against a schema."""

    def __init__(self, schema: Dict[str, Any] = None):
        super().__init__()
        self.schema = schema or {}

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate data against schema."""
        self._reset()

        if not self.schema:
            return self._create_result()

        required = self.schema.get('required', [])
        for field in required:
            if field not in data or data[field] is None or data[field] == "":
                self.add_error(field, f"Required field is missing or empty")

        properties = self.schema.get('properties', {})
        for field, rules in properties.items():
            if field in data:
                self._validate_field(field, data[field], rules)

        return self._create_result()

    def _validate_field(self, field: str, value: Any, rules: Dict):
        """Validate a single field."""
        field_type = rules.get('type')
        min_length = rules.get('min_length')
        max_length = rules.get('max_length')
        min_items = rules.get('min_items')
        enum_values = rules.get('enum')

        if field_type == 'string':
            if not isinstance(value, str):
                self.add_error(field, f"Expected string, got {type(value).__name__}")
                return

            if min_length and len(value) < min_length:
                self.add_error(field, f"Value too short (min: {min_length})")

            if max_length and len(value) > max_length:
                self.add_error(field, f"Value too long (max: {max_length})")

        elif field_type == 'array':
            if not isinstance(value, list):
                self.add_error(field, f"Expected array, got {type(value).__name__}")
                return

            if min_items and len(value) < min_items:
                self.add_error(field, f"Array has too few items (min: {min_items})")

        elif field_type == 'number':
            if not isinstance(value, (int, float)):
                self.add_error(field, f"Expected number, got {type(value).__name__}")

        if enum_values and value not in enum_values:
            self.add_error(field, f"Value must be one of: {', '.join(enum_values)}")

    def validate_content(self, content: Dict[str, Any]) -> ValidationResult:
        """Validate report content specifically."""
        original_schema = self.schema
        self.schema = {
            "required": ["title"],
            "properties": {
                "title": {"type": "string", "min_length": 1, "max_length": 200},
                "subtitle": {"type": "string", "max_length": 200},
                "author": {"type": "string", "max_length": 100},
                "date": {"type": "string", "max_length": 50},
                "toc_entries": {"type": "array"},
                "sections": {"type": "array", "min_items": 1},
                "executive_summary": {"type": "string", "max_length": 1000},
                "introduction": {"type": "string"},
                "conclusion": {"type": "string"}
            }
        }
        result = self.validate(content)
        self.schema = original_schema
        return result


CONTENT_SCHEMA = {
    "required": ["title"],
    "properties": {
        "title": {"type": "string", "min_length": 1, "max_length": 200},
        "subtitle": {"type": "string", "max_length": 200},
        "author": {"type": "string", "max_length": 100},
        "date": {"type": "string", "max_length": 50},
        "toc_entries": {"type": "array"},
        "sections": {"type": "array"},
    }
}