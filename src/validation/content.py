"""
Content Validator Module
========================
Validates content quality and completeness.
"""

from typing import Dict, Any
from .base import Validator, ValidationResult


class ContentValidator(Validator):
    """Validates content quality."""

    def validate(self, content: Dict[str, Any]) -> ValidationResult:
        """Validate content quality."""
        self._reset()

        self._validate_required_fields(content)
        self._validate_section_lengths(content)
        self._validate_toc(content)
        self._validate_sections(content)

        return self._create_result()

    def _validate_required_fields(self, content: Dict):
        """Validate required fields are present."""
        if not content.get('title'):
            self.add_error("title", "Report title is required")

        if not content.get('introduction'):
            self.add_warning("introduction", "No introduction section")

    def _validate_section_lengths(self, content: Dict):
        """Validate section content lengths."""
        for field in ['executive_summary', 'introduction', 'conclusion']:
            value = content.get(field, '')
            if value and len(value) < 20:
                self.add_warning(field, f"{field} seems too short")
            if value and len(value) > 5000:
                self.add_warning(field, f"{field} is very long")

    def _validate_toc(self, content: Dict):
        """Validate table of contents."""
        toc = content.get('toc_entries', [])
        if not toc:
            self.add_warning("toc", "No table of contents entries")
        elif not isinstance(toc, list):
            self.add_error("toc", "Table of contents must be a list")

    def _validate_sections(self, content: Dict):
        """Validate content sections."""
        sections = content.get('sections', [])
        if not sections:
            self.add_warning("sections", "No content sections")
            return

        if not isinstance(sections, list):
            self.add_error("sections", "Sections must be a list")
            return

        for idx, section in enumerate(sections):
            if not isinstance(section, dict):
                self.add_error(f"section_{idx}", "Section must be an object")
                continue

            if 'heading' not in section:
                self.add_error(f"section_{idx}", "Section missing heading")

            if 'content' not in section:
                self.add_warning(f"section_{idx}", "Section missing content")

    def validate_completeness(self, content: Dict[str, Any]) -> float:
        """Calculate content completeness score (0-100)."""
        score = 0
        max_score = 100

        fields = [
            ('title', 10),
            ('subtitle', 5),
            ('author', 5),
            ('date', 5),
            ('executive_summary', 10),
            ('introduction', 15),
            ('sections', 30),
            ('conclusion', 10),
            ('toc_entries', 10)
        ]

        for field, weight in fields:
            if field in content and content[field]:
                if isinstance(content[field], list):
                    if len(content[field]) > 0:
                        score += weight
                elif isinstance(content[field], str):
                    if len(content[field].strip()) > 0:
                        score += weight

        return min(score, max_score)


def validate_content(content: Dict[str, Any]) -> ValidationResult:
    """Convenience function to validate content."""
    validator = ContentValidator()
    return validator.validate(content)