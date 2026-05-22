from typing import List, Dict
from .base import BaseChecker, ReviewResult
from src.core.logger import get_logger

logger = get_logger(__name__)


class CoherenceChecker(BaseChecker):
    """Checks cross-chapter coherence and logical flow."""

    def __init__(self):
        super().__init__("coherence")

    def check(self, sections: List[Dict], **kwargs) -> ReviewResult:
        result = ReviewResult(self.name)
        if len(sections) < 2:
            result.add_issue("warning", "Too few sections to check coherence", "document")
            return result

        for i in range(len(sections) - 1):
            current = sections[i].get("heading", "")
            next_sec = sections[i + 1].get("heading", "")
            self._check_transition(result, current, next_sec, i)

        terms_by_section = []
        for sec in sections:
            content = sec.get("content", "")
            terms = set(w.lower() for w in content.split() if len(w) > 5)
            terms_by_section.append(terms)

        for i in range(1, len(terms_by_section)):
            overlap = terms_by_section[i] & terms_by_section[i - 1]
            if len(overlap) < 3 and len(terms_by_section[i]) > 20:
                result.add_issue(
                    "warning",
                    f"Section '{sections[i].get('heading', '')}' has low term overlap with previous section",
                    sections[i].get("heading", ""),
                )

        return result

    def _check_transition(self, result: ReviewResult, current: str, next_sec: str, index: int):
        expected_orders = [
            ("introduction", "literature"),
            ("literature", "methodology"),
            ("methodology", "result"),
            ("result", "discussion"),
            ("discussion", "conclusion"),
        ]
        cur_lower = current.lower()
        next_lower = next_sec.lower()
        for expected_cur, expected_next in expected_orders:
            if expected_cur in cur_lower and expected_next not in next_lower:
                if any(alt in next_lower for alt in ("introduction", "background", "overview")):
                    continue
                result.add_issue(
                    "info",
                    f"Section '{current}' is followed by '{next_sec}' instead of expected '{expected_next.title()}'",
                    current,
                )
