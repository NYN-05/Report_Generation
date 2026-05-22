import re
from typing import List, Dict
from .base import BaseChecker, ReviewResult
from src.core.logger import get_logger

logger = get_logger(__name__)


class CitationChecker(BaseChecker):
    """Validates citation usage and reference coverage."""

    def __init__(self):
        super().__init__("citation")
        self._cite_pattern = re.compile(r'\[(\d+(?:[-,]\s*\d+)*)\]')
        self._year_pattern = re.compile(r'\(?\d{4}\)?')

    def check(self, sections: List[Dict], **kwargs) -> ReviewResult:
        result = ReviewResult(self.name)
        all_citations = set()
        citation_sections = []

        for sec in sections:
            heading = sec.get("heading", "")
            content = sec.get("content", "")
            cites = self._extract_citations(content)
            all_citations.update(cites)
            if cites:
                citation_sections.append((heading, len(cites)))

            if not cites and heading.lower() not in ("abstract", "references", "acknowledgement", "certificate", "declaration"):
                result.add_issue("info", "Section lacks citations", heading)

        if len(citation_sections) <= 1 and len(sections) > 3:
            result.add_issue("warning", "Only 1 section contains citations; spread citations across chapters", "document")

        return result

    def _extract_citations(self, text: str) -> set:
        matches = self._cite_pattern.findall(text)
        refs = set()
        for m in matches:
            for part in m.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-")
                    try:
                        refs.update(str(i) for i in range(int(start), int(end) + 1))
                    except ValueError:
                        refs.add(part)
                else:
                    refs.add(part)
        return refs
