from typing import List, Dict
from .base import BaseChecker, ReviewResult
from src.core.logger import get_logger

logger = get_logger(__name__)


class StyleChecker(BaseChecker):
    """Checks writing style consistency across sections."""

    def __init__(self):
        super().__init__("style")
        self._informal_patterns = [
            "you'll", "we're", "they're", "it's", "don't", "can't", "won't",
            "gonna", "wanna", "kinda", "sorta", "lots of", "a lot",
        ]
        self._first_person_patterns = [
            "i think", "i believe", "i feel", "in my opinion",
            "as i said", "we think", "we believe",
        ]
        self._weak_words = [
            "very", "really", "quite", "somewhat", "fairly",
            "pretty", "rather", "kind of", "sort of",
        ]

    def check(self, sections: List[Dict], **kwargs) -> ReviewResult:
        result = ReviewResult(self.name)
        for sec in sections:
            heading = sec.get("heading", "")
            content = sec.get("content", "")
            self._check_informal_language(result, content, heading)
            self._check_first_person(result, content, heading)
            self._check_weak_words(result, content, heading)
            self._check_paragraph_length(result, content, heading)

        return result

    def _check_informal_language(self, result: ReviewResult, content: str, heading: str):
        for pat in self._informal_patterns:
            if pat in content.lower():
                result.add_issue("warning", f"Informal language detected: '{pat}'", heading)

    def _check_first_person(self, result: ReviewResult, content: str, heading: str):
        for pat in self._first_person_patterns:
            if pat in content.lower():
                result.add_issue("warning", f"First-person expression: '{pat}'", heading)

    def _check_weak_words(self, result: ReviewResult, content: str, heading: str):
        for w in self._weak_words:
            if f" {w} " in content.lower():
                result.add_issue("info", f"Weak word detected: '{w}'", heading)

    def _check_paragraph_length(self, result: ReviewResult, content: str, heading: str):
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for pi, para in enumerate(paragraphs):
            words = len(para.split())
            if words < 20 and len(paragraphs) > 1:
                result.add_issue("info", f"Very short paragraph ({words} words)", f"{heading} para {pi+1}")
