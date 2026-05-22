import re
from typing import List, Dict
from .base import BaseChecker, ReviewResult
from src.core.logger import get_logger

logger = get_logger(__name__)


class FormattingChecker(BaseChecker):
    """Checks document formatting consistency."""

    MIN_WORDS_PER_SECTION = 100
    MAX_WORDS_PER_PARAGRAPH = 300

    def __init__(self):
        super().__init__("formatting")

    def check(self, sections: List[Dict], **kwargs) -> ReviewResult:
        result = ReviewResult(self.name)
        for sec in sections:
            heading = sec.get("heading", "")
            content = sec.get("content", "")
            self._check_section_length(result, content, heading)
            self._check_paragraph_structure(result, content, heading)
            self._check_heading_format(result, heading)
        return result

    def _check_section_length(self, result: ReviewResult, content: str, heading: str):
        words = len(content.split())
        if words < self.MIN_WORDS_PER_SECTION and heading.lower() not in ("references", "appendices", "acknowledgement", "certificate", "declaration"):
            result.add_issue("warning", f"Section too short: {words} words (min {self.MIN_WORDS_PER_SECTION})", heading)

    def _check_paragraph_structure(self, result: ReviewResult, content: str, heading: str):
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for pi, para in enumerate(paragraphs):
            words = len(para.split())
            if words > self.MAX_WORDS_PER_PARAGRAPH:
                result.add_issue("info", f"Long paragraph: {words} words (max {self.MAX_WORDS_PER_PARAGRAPH})", f"{heading} para {pi+1}")

    def _check_heading_format(self, result: ReviewResult, heading: str):
        if heading and heading[0].islower():
            result.add_issue("info", f"Heading should start with uppercase: '{heading}'", heading)
        if heading and heading[-1] == '.':
            result.add_issue("info", f"Heading should not end with period: '{heading}'", heading)
