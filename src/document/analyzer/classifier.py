import re
from typing import List, Optional
from .models import HeadingInfo, SectionInfo


SECTION_PATTERNS = {
    "certificate": [
        re.compile(r'^(certificate|declaration|certificate\s+of\s+.*)$', re.IGNORECASE),
    ],
    "acknowledgement": [
        re.compile(r'^(acknowledg(e)?ment(s)?)$', re.IGNORECASE),
    ],
    "abstract": [
        re.compile(r'^abstract$', re.IGNORECASE),
    ],
    "introduction": [
        re.compile(r'^(1\.?\s*)?introduction$', re.IGNORECASE),
        re.compile(r'^introduction', re.IGNORECASE),
    ],
    "literature_survey": [
        re.compile(r'^(2\.?\s*)?(literature\s+(survey|review)|related\s+work|background)$', re.IGNORECASE),
        re.compile(r'^(literature\s+(survey|review)|related\s+work)', re.IGNORECASE),
    ],
    "methodology": [
        re.compile(r'^(3\.?\s*)?methodology$', re.IGNORECASE),
        re.compile(r'^methodology', re.IGNORECASE),
        re.compile(r'^(proposed\s+)?(method|approach|system\s+design|implementation)$', re.IGNORECASE),
    ],
    "results": [
        re.compile(r'^(4\.?\s*)?(results?|experiment|evaluation|findings)$', re.IGNORECASE),
        re.compile(r'^(results?|experiment)', re.IGNORECASE),
    ],
    "discussion": [
        re.compile(r'^(5\.?\s*)?discussion$', re.IGNORECASE),
        re.compile(r'^discussion', re.IGNORECASE),
    ],
    "conclusion": [
        re.compile(r'^(6\.?\s*)?conclusion$', re.IGNORECASE),
        re.compile(r'^conclusion', re.IGNORECASE),
        re.compile(r'^(conclusion|summary|future\s+work)', re.IGNORECASE),
    ],
    "references": [
        re.compile(r'^references$', re.IGNORECASE),
        re.compile(r'^(bibliography|works\s+cited|references)', re.IGNORECASE),
    ],
    "appendix": [
        re.compile(r'^appendix(\s+[A-Z])?$', re.IGNORECASE),
    ],
}


SECTION_KEYWORDS = {
    "abstract": ["abstract", "summary"],
    "introduction": ["introduction", "background", "motivation", "overview"],
    "literature_survey": ["literature", "survey", "review", "related work", "previous work", "state of the art"],
    "methodology": ["method", "methodology", "proposed", "approach", "implementation", "system design", "algorithm"],
    "results": ["result", "experiment", "evaluation", "finding", "analysis", "performance"],
    "discussion": ["discussion", "analysis of", "interpretation"],
    "conclusion": ["conclusion", "summary", "future work", "concluding"],
    "certificate": ["certificate", "declaration", "undertaking"],
    "acknowledgement": ["acknowledge", "thanks"],
    "references": ["reference", "bibliography", "works cited", "citations"],
    "appendix": ["appendix"],
}


class SectionClassifier:
    """Classifies document sections into academic categories."""

    def __init__(self):
        self._section_type_order = [
            "certificate", "acknowledgement", "abstract",
            "introduction", "literature_survey", "methodology",
            "results", "discussion", "conclusion", "references", "appendix",
        ]

    def classify(self, heading: HeadingInfo) -> str:
        if not heading or not heading.text:
            return "unknown"

        text = heading.text.strip()
        best_type = "unknown"
        best_score = 0.0

        for section_type, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                m = pattern.match(text)
                if m:
                    score = 1.0 - (len(m.group(0)) - len(m.group(0).rstrip('.'))) * 0.1
                    if score > best_score:
                        best_score = score
                        best_type = section_type

        if best_type == "unknown":
            score = self._keyword_score(text)
            if score > 0.5:
                best_type = self._best_keyword_match(text)
                best_score = score

        return best_type

    def classify_headings(self, headings: List[HeadingInfo]) -> List[SectionInfo]:
        sections: List[SectionInfo] = []
        stack: List[SectionInfo] = []

        for h in headings:
            section_type = self.classify(h)
            confidence = 0.9 if section_type != "unknown" else 0.3

            sec = SectionInfo(
                heading=h,
                section_type=section_type,
                confidence=confidence,
                level=h.level,
            )

            while stack and stack[-1].level >= h.level:
                stack.pop()

            if stack:
                stack[-1].children.append(sec)
            else:
                sections.append(sec)
            stack.append(sec)

        return sections

    def _keyword_score(self, text: str) -> float:
        lower = text.lower()
        max_score = 0.0
        for section_type, keywords in SECTION_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    score = len(kw) / max(len(text), 1)
                    max_score = max(max_score, score)
        return max_score

    def _best_keyword_match(self, text: str) -> str:
        lower = text.lower()
        best_type = "unknown"
        best_score = 0.0
        for section_type, keywords in SECTION_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    score = len(kw) / max(len(text), 1)
                    if score > best_score:
                        best_score = score
                        best_type = section_type
        return best_type

    def get_section_order(self) -> List[str]:
        return list(self._section_type_order)
