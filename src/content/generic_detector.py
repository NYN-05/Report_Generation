"""GenericContentDetector — detects and rejects low-information filler text."""

import re
from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger

logger = get_logger(__name__)


GENERIC_PHRASES = [
    r"this[^.]*has gained significant attention",
    r"this[^.]*growing (area|field|topic)",
    r"several (important|key|various) aspects",
    r"numerous (studies|works|papers|researchers)",
    r"research indicates (many|several|various)",
    r"various studies (suggest|indicate|show|demonstrate)",
    r"many researchers have focused",
    r"this field is rapidly (growing|evolving|expanding)",
    r"current trends demonstrate",
    r"it is (widely|generally) (accepted|known|believed)",
    r"it is important to (note|consider|understand)",
    r"there are (many|several|various) (ways|approaches|methods)",
    r"a lot of research",
    r"a wide range of",
    r"in recent (years|decades|times)",
    r"over the past (few|several|many) (years|decades)",
    r"recent (advances|developments|progress) in",
    r"has been extensively (studied|researched|investigated)",
    r"plays a (crucial|vital|significant|important) role",
    r"one of the (most|key|important|critical)",
    r"due to its (importance|significance|potential)",
    r"it is worth (noting|mentioning)",
    r"as we (know|understand|can see)",
    r"the future of (this|the)",
    r"the potential for",
    r"there is a need for",
    r"it has been shown that",
    r"studies have shown that",
    r"research has shown that",
]

# Generic topic insertion patterns — evidence the model is doing find-and-replace
TOPIC_INSERTION_PATTERNS = [
    r"the (topic|field|area|domain) of \w+",
    r"application of \w+ in",
    r"use of \w+ for",
    r"in the context of \w+",
    r"when (it comes to|considering|discussing) \w+",
    r"with respect to \w+",
]

# Low-info hedging that adds no content
HEDGING = [
    r"\bquite\b", r"\brather\b", r"\bsomewhat\b", r"\barguably\b",
    r"\bessentially\b", r"\bbasically\b", r"\bgenerally\b",
    r"\boverall\b", r"\bin general\b", r"\bto some extent\b",
]


class GenericContentDetector:
    FILLER_THRESHOLD = 0.15

    def detect(self, text: str, topic: str = "") -> Dict[str, any]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return {"passed": True, "filler_density": 0.0, "issues": []}

        total_paragraphs = len(paragraphs)
        filler_paragraphs = 0
        issues = []

        for i, para in enumerate(paragraphs):
            para_result = self._analyze_paragraph(para, topic)
            if para_result["has_filler"]:
                filler_paragraphs += 1
            if para_result["issues"]:
                issues.append({
                    "paragraph_index": i,
                    "paragraph_start": para[:80],
                    "issues": para_result["issues"],
                })

        density = filler_paragraphs / total_paragraphs
        return {
            "passed": density < self.FILLER_THRESHOLD,
            "filler_density": round(density, 3),
            "threshold": self.FILLER_THRESHOLD,
            "filler_paragraphs": filler_paragraphs,
            "total_paragraphs": total_paragraphs,
            "issues": issues,
        }

    def _analyze_paragraph(self, text: str, topic: str) -> Dict:
        issues = []
        has_filler = False

        for pattern in GENERIC_PHRASES:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"generic_phrase: {pattern}")
                has_filler = True

        for pattern in TOPIC_INSERTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"topic_insertion: {pattern}")

        hedging_count = 0
        for pattern in HEDGING:
            hedging_count += len(re.findall(pattern, text, re.IGNORECASE))
        if hedging_count > 3:
            issues.append(f"excessive_hedging: {hedging_count} instances")
            has_filler = True

        sentences = [s.strip() for s in text.replace(". ", ".|").split("|") if s.strip()]
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)

        word_count = len(text.split())
        unique_words = len(set(text.lower().split()))
        lexical_diversity = unique_words / max(word_count, 1)
        if lexical_diversity < 0.45:
            issues.append(f"low_lexical_diversity: {lexical_diversity:.2f}")
            has_filler = True

        return {
            "has_filler": has_filler,
            "issues": issues,
            "hedging_count": hedging_count,
            "avg_sentence_length": round(avg_sentence_length, 1),
            "lexical_diversity": round(lexical_diversity, 2),
        }
