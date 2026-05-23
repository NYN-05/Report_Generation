"""TechnicalDepthEvaluator — scores content for technical quality and regenerates if below threshold.

For each section, score:
- specificity (0-1): how specific vs generic the content is
- technical_detail (0-1): depth of technical information
- evidence_usage (0-1): how well evidence is integrated
- terminology_quality (0-1): quality of domain terminology
- academic_tone (0-1): formality and academic style

If overall score < threshold (0.6), signal for regeneration.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DepthScore:
    specificity: float = 0.0
    technical_detail: float = 0.0
    evidence_usage: float = 0.0
    terminology_quality: float = 0.0
    academic_tone: float = 0.0
    overall: float = 0.0
    issues: List[str] = field(default_factory=list)

    def passed(self, threshold: float = 0.6) -> bool:
        return self.overall >= threshold


class TechnicalDepthEvaluator:

    GENERIC_TERMS = {
        "thing", "stuff", "nice", "good", "bad", "great", "important",
        "interesting", "various", "different", "multiple", "many",
        "some", "certain", "specific", "particular", "significant",
        "substantial", "considerable", "extensive", "broad", "wide",
        "diverse", "numerous", "countless", "myriad",
    }

    TECHNICAL_INDICATORS = [
        r'\b(system|architecture|module|component|interface|protocol)\b',
        r'\b(algorithm|function|method|procedure|process|pipeline)\b',
        r'\b(database|cache|buffer|queue|stack|heap|index)\b',
        r'\b(parameter|variable|constant|configuration|threshold)\b',
        r'\b(implementation|deployment|integration|migration)\b',
        r'\b(framework|library|toolkit|platform|environment)\b',
        r'\b(performance|latency|throughput|bandwidth|overhead)\b',
        r'\b(optimization|scalability|reliability|availability|concurrency)\b',
        r'\b(encryption|authentication|authorization|validation|parsing)\b',
        r'\b(API|REST|HTTP|TCP|UDP|JSON|XML|SQL|NoSQL)\b',
        r'\b(neural|network|learning|training|inference|regression)\b',
        r'\b(accuracy|precision|recall|F1|ROC|AUC|loss|error)\b',
    ]

    WEAK_PATTERNS = [
        r"it is important to note",
        r"it should be noted",
        r"it is worth mentioning",
        r"it is essential to",
        r"it is crucial to",
        r"plays a (crucial|vital|significant) role",
        r"in conclusion",
        r"to summarize",
        r"as mentioned (above|earlier|previously)",
    ]

    def evaluate(self, text: str, evidence_count: int = 0) -> DepthScore:
        score = DepthScore()

        score.specificity = self._score_specificity(text)
        score.technical_detail = self._score_technical_detail(text)
        score.evidence_usage = self._score_evidence_usage(text, evidence_count)
        score.terminology_quality = self._score_terminology(text)
        score.academic_tone = self._score_academic_tone(text)

        score.overall = (
            score.specificity * 0.20
            + score.technical_detail * 0.25
            + score.evidence_usage * 0.25
            + score.terminology_quality * 0.15
            + score.academic_tone * 0.15
        )

        score.issues = self._find_issues(text)

        logger.debug(
            f"Depth score: spec={score.specificity:.2f} tech={score.technical_detail:.2f} "
            f"evid={score.evidence_usage:.2f} term={score.terminology_quality:.2f} "
            f"tone={score.academic_tone:.2f} overall={score.overall:.2f}"
        )

        return score

    def _score_specificity(self, text: str) -> float:
        words = text.lower().split()
        if not words:
            return 0.0
        generic = sum(1 for w in words if w in self.GENERIC_TERMS)
        generic_ratio = generic / len(words)
        specificity = 1.0 - (generic_ratio * 5)
        return max(0.0, min(1.0, specificity))

    def _score_technical_detail(self, text: str) -> float:
        matches = 0
        for pattern in self.TECHNICAL_INDICATORS:
            matches += len(re.findall(pattern, text, re.IGNORECASE))
        words = len(text.split())
        if words == 0:
            return 0.0
        density = matches / max(words, 1) * 100
        score = min(1.0, density / 5.0)
        return score

    def _score_evidence_usage(self, text: str, evidence_count: int) -> float:
        has_refs = bool(re.search(r'\[.*?\]', text))
        has_citations = bool(re.search(r'According to', text))
        has_source = bool(re.search(r'source', text, re.IGNORECASE))
        has_placeholder = "[Source Material Required]" in text

        if has_placeholder:
            return 0.0
        if has_refs and evidence_count > 0:
            return 0.9
        if has_citations:
            return 0.7
        if has_source:
            return 0.5
        if evidence_count > 0:
            return 0.3
        return 0.1

    def _score_terminology(self, text: str) -> float:
        weak = len(re.findall(r'\b(very|really|quite|somewhat|rather|fairly)\b', text, re.IGNORECASE))
        weak += len(re.findall(r'\b(this|these|those) (thing|stuff|area|field|aspect)\b', text, re.IGNORECASE))
        weak_penalty = weak * 0.15
        return max(0.0, 1.0 - weak_penalty)

    def _score_academic_tone(self, text: str) -> float:
        conversational = [
            r"\blet['\u2019]s\b", r"\byou\b", r"\bwe'll\b", r"\bI'll\b",
            r"\bwell,?\b", r"\bso,?\b",
        ]
        hits = sum(1 for p in conversational if re.search(p, text, re.IGNORECASE))
        academic_markers = [
            r"\btherefore\b", r"\bhowever\b", r"\bfurthermore\b",
            r"\bconsequently\b", r"\bnevertheless\b", r"\bmoreover\b",
        ]
        academic = sum(1 for p in academic_markers if re.search(p, text, re.IGNORECASE))
        score = 0.5 + academic * 0.1 - hits * 0.2
        return max(0.0, min(1.0, score))

    def _find_issues(self, text: str) -> List[str]:
        issues = []
        for p in self.WEAK_PATTERNS:
            if re.search(p, text, re.IGNORECASE):
                issues.append(f"Weak phrase detected: {p}")
        if re.search(r'\b(in conclusion|to summarize|in summary)\b', text, re.IGNORECASE):
            issues.append("Uses redundant concluding marker")
        return issues

    def evaluate_section(self, content: str, evidence_count: int = 0) -> Tuple[DepthScore, bool]:
        score = self.evaluate(content, evidence_count)
        passed = score.passed()
        if not passed:
            logger.info(f"Technical depth check FAILED (score={score.overall:.2f})")
        return score, passed
