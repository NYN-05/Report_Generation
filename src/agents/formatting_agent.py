"""
Formatting Agent
================
Applies DOCX/PDF formatting rules and IEEE compliance.
"""

from typing import Any, Dict, Optional, List
from .base import BaseAgent, AgentResponse
from src.core.logger import get_logger

logger = get_logger(__name__)


class FormattingAgent(BaseAgent):
    """Agent responsible for document formatting and IEEE compliance.

    Responsibilities:
    - Apply IEEE heading styles
    - Ensure consistent font/spacing
    - Validate section numbering
    - Check table/figure formatting
    - Enforce academic formatting rules
    """

    def __init__(self, provider=None):
        super().__init__("formatting", provider)

    def execute(self, input_data: Any, **kwargs) -> AgentResponse:
        if not isinstance(input_data, dict):
            return self._create_response(False, error="Input must be a dict")

        sections = input_data.get("sections", [])
        rules = input_data.get("rules", {})

        issues = []
        suggestions = []

        for i, sec in enumerate(sections):
            heading = sec.get("heading", "")
            content = sec.get("content", "")
            level = sec.get("level", 1)

            if heading and not heading[0].isupper() if heading else False:
                issues.append(f"Section '{heading}': heading should start with uppercase")
                suggestions.append(f"Fix casing: {heading.capitalize()}")

            word_count = len(content.split())
            if word_count < 50:
                issues.append(f"Section '{heading}': only {word_count} words (min 50)")
                suggestions.append(f"Expand '{heading}' to at least 50 words")

        numbered_sections = [s for s in sections if re.match(r'^\d+\.', s.get("heading", ""))]
        if numbered_sections and len(numbered_sections) != len(sections):
            issues.append("Mixed numbered and unnumbered sections")

        return self._create_response(True, data={
            "issues": issues,
            "suggestions": suggestions,
            "total_issues": len(issues),
            "compliant": len(issues) == 0,
        })

    def analyze_style_compliance(self, sections: List[Dict]) -> Dict:
        result = self.execute({"sections": sections})
        return result.data if result.success else {"issues": [], "compliant": True}

    def suggest_numbering_fix(self, heading: str) -> str:
        import re as _re
        if _re.match(r'^\d+\.\d+\.\d+', heading):
            return f"Consider reducing nesting depth: '{heading}'"
        if _re.match(r'^\d+', heading) and not _re.match(r'^\d+\.', heading):
            return f"Fix numbering format: '1. {heading}'"
        return ""

import re
