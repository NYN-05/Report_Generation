import re
from typing import List, Dict, Set
from .base import BaseChecker, ReviewResult
from src.core.logger import get_logger

logger = get_logger(__name__)


class RedundancyChecker(BaseChecker):
    """Detects repeated content and redundant phrases across sections."""

    def __init__(self, ngram_size: int = 8):
        super().__init__("redundancy")
        self.ngram_size = ngram_size

    def check(self, sections: List[Dict], **kwargs) -> ReviewResult:
        result = ReviewResult(self.name)
        ngram_map: Dict[str, List[str]] = {}

        for sec in sections:
            heading = sec.get("heading", "")
            content = sec.get("content", "")
            ngrams = self._extract_ngrams(content)
            for ng in ngrams:
                if ng not in ngram_map:
                    ngram_map[ng] = []
                ngram_map[ng].append(heading)

        for ng, headings in ngram_map.items():
            if len(headings) > 1:
                unique = list(set(headings))
                if len(unique) > 1:
                    result.add_issue(
                        "info",
                        f"Repeated phrase '{ng}' in {len(unique)} sections: {', '.join(unique)}",
                        ", ".join(unique),
                    )

        for i in range(len(sections) - 1):
            for j in range(i + 1, len(sections)):
                overlap = self._sentence_overlap(
                    sections[i].get("content", ""),
                    sections[j].get("content", ""),
                )
                if overlap > 30:
                    result.add_issue(
                        "warning",
                        f"{overlap:.0f}% sentence overlap between '{sections[i].get('heading', '')}' and '{sections[j].get('heading', '')}'",
                        f"{sections[i].get('heading', '')}, {sections[j].get('heading', '')}",
                    )

        return result

    def _extract_ngrams(self, text: str) -> Set[str]:
        words = text.lower().split()
        ngrams = set()
        for i in range(len(words) - self.ngram_size + 1):
            ng = " ".join(words[i:i + self.ngram_size])
            if len(ng) > 30:
                ngrams.add(ng)
        return ngrams

    def _sentence_overlap(self, text_a: str, text_b: str) -> float:
        sentences_a = set(re.findall(r'[^.!?]+[.!?]', text_a))
        sentences_b = set(re.findall(r'[^.!?]+[.!?]', text_b))
        if not sentences_a or not sentences_b:
            return 0.0
        overlap = len(sentences_a & sentences_b)
        total = len(sentences_a | sentences_b)
        return (overlap / total * 100) if total > 0 else 0.0
