"""
Citation Agent
==============
Validates citations and generates bibliography.
"""

import re
from typing import Any, Dict, Optional, List
from .base import BaseAgent, AgentResponse
from src.core.logger import get_logger

logger = get_logger(__name__)


class CitationAgent(BaseAgent):
    """Agent responsible for citation validation and bibliography generation.

    Responsibilities:
    - Validate numeric citations [N] throughout the document
    - Generate properly formatted bibliography
    - Detect missing or orphaned citations
    - Check citation distribution across sections
    """

    def __init__(self, provider=None):
        super().__init__("citation", provider)
        self._cite_pattern = re.compile(r'\[(\d+(?:[-,]\s*\d+)*)\]')

    def execute(self, input_data: Any, **kwargs) -> AgentResponse:
        if not isinstance(input_data, dict):
            return self._create_response(False, error="Input must be a dict")

        content = input_data.get("content", "")
        references = input_data.get("references", [])

        if not content:
            return self._create_response(False, error="No content provided")

        issues = self.validate_citations(content, len(references))
        bib = self.format_bibliography(references) if references else ""

        return self._create_response(True, data={
            "issues": issues,
            "has_issues": len(issues) > 0,
            "bibliography": bib,
            "citation_count": len(self._extract_citations(content)),
        })

    def validate_citations(self, content: str, ref_count: int) -> List[str]:
        issues = []
        citations = self._extract_citations(content)
        for cite in citations:
            if cite > ref_count:
                issues.append(f"Citation [{cite}] exceeds reference list ({ref_count} refs)")
        return issues

    def _extract_citations(self, text: str) -> List[int]:
        citations = set()
        for match in self._cite_pattern.finditer(text):
            for part in match.group(1).split(","):
                part = part.strip()
                if "-" in part:
                    try:
                        start, end = part.split("-")
                        citations.update(range(int(start.strip()), int(end.strip()) + 1))
                    except ValueError:
                        pass
                else:
                    try:
                        citations.add(int(part))
                    except ValueError:
                        pass
        return sorted(citations)

    def validate_distribution(self, sections: List[Dict]) -> List[str]:
        issues = []
        cited_sections = [s for s in sections if self._extract_citations(s.get("content", ""))]
        if len(cited_sections) <= 1 and len(sections) > 3:
            issues.append("Citations are concentrated in only 1 section; distribute across the document")
        return issues

    def format_bibliography(self, references: List[str], style: str = "ieee") -> str:
        if style == "ieee":
            return "\n".join(f"[{i+1}] {ref}" for i, ref in enumerate(references))
        return "\n".join(references)

    def check_orphaned_references(self, content: str, references: List[str]) -> List[str]:
        issues = []
        for i, ref in enumerate(references):
            if f"[{i+1}]" not in content and f" [{i+1}]" not in content:
                issues.append(f"Reference [{i+1}] defined but never cited in text")
        return issues
