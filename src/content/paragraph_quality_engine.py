"""ParagraphQualityEngine — enforces structural rules per paragraph.

Each paragraph must contain:
1. Topic sentence
2. Supporting explanation
3. Technical detail
4. Evidence reference
5. Analysis
6. Transition

Minimum 150 words, maximum 300 words.
"""

from typing import Dict, List, Optional
import re
from src.core.logger import get_logger

logger = get_logger(__name__)


ELEMENTS = {
    "topic_sentence": {
        "triggers": [r"^[A-Z][^.]{10,}\.(?:\s|$)"],
        "weight": 0.20,
    },
    "supporting_explanation": {
        "triggers": [r"(specifically|in particular|more precisely|that is|namely|"
                     r"furthermore|moreover|in addition|additionally|"
                     r"this (means|implies|indicates|suggests))",
                     r"for (instance|example)"],
        "weight": 0.20,
    },
    "technical_detail": {
        "triggers": [r"\b(?:specific|parameter|variable|function|component|module|"
                     r"algorithm|architecture|framework|protocol|interface|"
                     r"implementation|configuration|threshold|coefficient)\b",
                     r"\d+\.?\d*\s*(?:%|[A-Z]{2,}|accuracy|precision|rate|score|"
                     r"latency|throughput|bandwidth)"],
        "weight": 0.20,
    },
    "evidence_reference": {
        "triggers": [r"(?:according to|reported by|based on|as shown (?:in|by)|"
                     r"as demonstrated|per the|using data from|"
                     r"the (?:study|work|paper|research|analysis) (?:by|of)|"
                     r"as observed (?:in|by)|found that)",
                     r"\[\d+\]"],
        "weight": 0.15,
    },
    "analysis": {
        "triggers": [r"(?:this (?:suggests|indicates|implies|demonstrates|shows|"
                     r"reveals|highlights|underscores|confirms)|"
                     r"therefore|thus|hence|consequently|"
                     r"this is (?:because|attributed to|due to)|"
                     r"the (?:implication|significance|importance) is)"],
        "weight": 0.15,
    },
    "transition": {
        "triggers": [r"^[A-Z][a-z]+ly,?\s", r"(?:however|furthermore|moreover|"
                     r"in (?:addition|contrast|comparison)|"
                     r"on the (?:other hand|contrary)|"
                     r"nevertheless|nonetheless|conversely|"
                     r"additionally|alternatively)"],
        "weight": 0.10,
    },
}

MIN_WORDS = 150
MAX_WORDS = 300


class ParagraphQualityEngine:

    def score_paragraph(self, text: str) -> Dict[str, any]:
        text = text.strip()
        word_count = len(text.split())
        issues = []

        # Word count check
        if word_count < MIN_WORDS:
            issues.append(f"too_short: {word_count} words (min {MIN_WORDS})")
        if word_count > MAX_WORDS:
            issues.append(f"too_long: {word_count} words (max {MAX_WORDS})")

        # Element check
        text_lower = text.lower()
        elements_found = {}
        elements_missing = []
        for elem_name, elem_info in ELEMENTS.items():
            found = False
            for pat in elem_info["triggers"]:
                if re.search(pat, text, re.IGNORECASE):
                    found = True
                    break
            elements_found[elem_name] = found
            if not found:
                elements_missing.append(elem_name)

        covered = sum(1 for v in elements_found.values() if v)
        element_score = covered / len(ELEMENTS)

        # Check for forbidden bullet-in-paragraph
        has_inline_bullets = bool(re.search(r"(?:^|\n)\s*[•\-\*]\s", text))
        if has_inline_bullets:
            issues.append("inline_bullets_present")

        # Check for topic insertion patterns
        has_generic_opening = bool(re.search(
            r"(This (section|chapter|part|report) (discusses|presents|covers|focuses on|explores|examines|addresses|describes))",
            text, re.IGNORECASE
        ))
        if has_generic_opening:
            issues.append("generic_opening")

        overall = (element_score * 0.6 +
                   (1.0 if MIN_WORDS <= word_count <= MAX_WORDS else 0.3) * 0.2 +
                   (0.0 if has_inline_bullets else 1.0) * 0.1 +
                   (0.0 if has_generic_opening else 1.0) * 0.1)

        return {
            "overall": round(overall, 3),
            "word_count": word_count,
            "word_count_ok": MIN_WORDS <= word_count <= MAX_WORDS,
            "elements": elements_found,
            "elements_covered": covered,
            "elements_total": len(ELEMENTS),
            "elements_missing": elements_missing,
            "has_inline_bullets": has_inline_bullets,
            "has_generic_opening": has_generic_opening,
            "issues": issues,
            "passed": overall >= 0.6 and not has_inline_bullets,
        }

    def score_section(self, text: str) -> Dict[str, any]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return {"overall": 0.0, "passed": False, "total": 0}

        results = []
        below = 0
        for p in paragraphs:
            r = self.score_paragraph(p)
            results.append(r)
            if not r["passed"]:
                below += 1

        avg = sum(r["overall"] for r in results) / len(results)
        return {
            "overall": round(avg, 3),
            "passed": avg >= 0.6 and below == 0,
            "total": len(results),
            "below_threshold": below,
            "paragraphs": results,
        }
