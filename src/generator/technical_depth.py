"""TechnicalDepthEvaluator — scores content for technical quality on 7 dimensions.

Evaluate every generated section on:
1. Relevance     — how well content matches the chapter purpose
2. Technical depth   — depth of technical information
3. Evidence support  — how well evidence is integrated
4. Uniqueness    — how distinct from generic/template content
5. Readability   — sentence structure and clarity
6. Chapter alignment — how well it fits the chapter type
7. Academic quality  — formality and academic tone

If overall score < threshold (0.6), signal for regeneration.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DepthScore:
    relevance: float = 0.0
    technical_detail: float = 0.0
    evidence_usage: float = 0.0
    uniqueness: float = 0.0
    readability: float = 0.0
    chapter_alignment: float = 0.0
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
        r'\b(neural|network|learning|training|inference|regression|classification)\b',
        r'\b(accuracy|precision|recall|F1|ROC|AUC|loss|error)\b',
    ]

    WHAT_WHY_HOW_PATTERNS = [
        r'\b(because|since|due to|as a result of)\b',
        r'\b(in order to|so that|for the purpose of)\b',
        r'\b(this (is|was|has been) (achieved|accomplished|implemented) (by|through|using))\b',
        r'\b(the (impact|effect|implication) of)\b',
        r'\b(limitation|drawback|constraint|challenge|trade-off)\b',
        r'\b(application|use case|scenario|domain) (of|for|in)\b',
        r'\b(future|next step|further|ongoing|potential) (work|research|direction|improvement)\b',
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

    FORBIDDEN_PATTERNS = [
        r"Several (important|key|significant) aspects can be observed",
        r"This (topic|area|field) has gained (significant|considerable|substantial) attention",
        r"Research indicates (many|numerous|several) benefits",
        r"Various studies have shown (improvements|enhancements|benefits)",
    ]

    def evaluate(self, text: str, evidence_count: int = 0, section_type: str = "") -> DepthScore:
        score = DepthScore()

        score.relevance = self._score_relevance(text, section_type)
        score.technical_detail = self._score_technical_detail(text)
        score.evidence_usage = self._score_evidence_usage(text, evidence_count)
        score.uniqueness = self._score_uniqueness(text)
        score.readability = self._score_readability(text)
        score.chapter_alignment = self._score_chapter_alignment(text, section_type)
        score.academic_tone = self._score_academic_tone(text)

        score.overall = (
            score.relevance * 0.15
            + score.technical_detail * 0.20
            + score.evidence_usage * 0.20
            + score.uniqueness * 0.10
            + score.readability * 0.10
            + score.chapter_alignment * 0.10
            + score.academic_tone * 0.15
        )

        score.issues = self._find_issues(text, section_type)

        logger.debug(
            f"Depth score: rel={score.relevance:.2f} tech={score.technical_detail:.2f} "
            f"evid={score.evidence_usage:.2f} uniq={score.uniqueness:.2f} "
            f"read={score.readability:.2f} align={score.chapter_alignment:.2f} "
            f"tone={score.academic_tone:.2f} overall={score.overall:.2f}"
        )

        return score

    def _score_relevance(self, text: str, section_type: str) -> float:
        if not text:
            return 0.0
        has_placeholder = "Insufficient source material available for this claim." in text
        if has_placeholder:
            return 0.0

        if not section_type:
            return 0.5

        section_type_lower = section_type.lower()
        chapter_terms = {
            "introduction": ["background", "problem", "motivation", "objective", "scope"],
            "literature_review": ["existing", "prior", "related", "research", "literature", "gap"],
            "methodology": ["architecture", "workflow", "algorithm", "model", "implementation", "method"],
            "implementation": ["development", "component", "integration", "testing", "environment"],
            "results": ["result", "finding", "observation", "metric", "experiment", "measure"],
            "discussion": ["interpret", "implication", "limitation", "comparison", "discuss"],
            "conclusion": ["summary", "conclusion", "contribution", "future", "achievement"],
        }
        expected = chapter_terms.get(section_type_lower, [])
        if not expected:
            return 0.5

        text_lower = text.lower()
        found = sum(1 for term in expected if term in text_lower)
        relevance = found / max(len(expected), 1)
        return min(1.0, relevance * 1.5)

    def _score_technical_detail(self, text: str) -> float:
        matches = 0
        for pattern in self.TECHNICAL_INDICATORS:
            matches += len(re.findall(pattern, text, re.IGNORECASE))

        what_why = 0
        for pattern in self.WHAT_WHY_HOW_PATTERNS:
            what_why += len(re.findall(pattern, text, re.IGNORECASE))

        words = len(text.split())
        if words == 0:
            return 0.0

        tech_density = matches / max(words, 1) * 100
        tech_score = min(1.0, tech_density / 5.0)

        analysis_score = min(1.0, what_why / max(words, 1) * 50)

        return (tech_score * 0.6 + analysis_score * 0.4)

    def _score_evidence_usage(self, text: str, evidence_count: int) -> float:
        has_placeholder = "Insufficient source material available for this claim." in text
        has_refs = bool(re.search(r'\[.*?\]', text))
        has_according = bool(re.search(r'According to', text))
        has_source = bool(re.search(r'source', text, re.IGNORECASE))
        has_numbers = bool(re.search(r'\d+\.?\d*%|\d+\.?\d*\s*(accuracy|precision|recall|F1|score)', text, re.IGNORECASE))

        if has_placeholder:
            return 0.0
        score = 0.0
        if has_refs and evidence_count > 0: score += 0.35
        if has_numbers and evidence_count > 0: score += 0.35
        if has_according: score += 0.20
        if has_source: score += 0.10
        if evidence_count > 0 and not has_refs: score += 0.15
        return min(score, 1.0)

    def _score_uniqueness(self, text: str) -> float:
        forbidden = 0
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                forbidden += 1

        template_words = ["this topic", "this field", "this area", "the subject of"]
        template = sum(1 for w in template_words if w in text.lower())
        return max(0.0, 1.0 - (forbidden * 0.3 + template * 0.15))

    def _score_readability(self, text: str) -> float:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        words = text.split()
        if not sentences or not words:
            return 0.0

        avg_sentence_len = len(words) / len(sentences)
        if avg_sentence_len < 8: return 0.4
        if avg_sentence_len > 40: return 0.5
        if 12 <= avg_sentence_len <= 25: return 1.0
        return 0.8

    def _score_chapter_alignment(self, text: str, section_type: str) -> float:
        if not section_type:
            return 0.5

        section_type_lower = section_type.lower()

        intro_penalties = [
            r'\b(methodology|implementation|algorithm|model training|experimental setup)\b',
            r'\b(results show|the findings|our approach achieves)\b',
        ]
        lit_review_penalties = [
            r'\b(architecture|implementation details|system design|workflow)\b',
            r'\b(experimental setup|evaluation metrics)\b',
        ]
        methodology_penalties = [
            r'\b(literature review|existing research|prior work|related studies)\b',
            r'\b(results indicate|the findings suggest)\b',
        ]
        results_penalties = [
            r'\b(background|literature review|related work|motivation)\b',
            r'\b(methodology|implementation details|system architecture)\b',
        ]
        discussion_penalties = [
            r'\b(experimental setup|implementation environment)\b',
        ]
        conclusion_penalties = [
            r'\b(methodology|implementation details|system architecture)\b',
            r'\b(literature review|related work)\b',
        ]

        penalties = {
            "introduction": intro_penalties,
            "literature_review": lit_review_penalties,
            "methodology": methodology_penalties,
            "implementation": methodology_penalties,
            "results": results_penalties,
            "discussion": discussion_penalties,
            "conclusion": conclusion_penalties,
        }

        penalty_patterns = penalties.get(section_type_lower, [])
        violations = 0
        for p in penalty_patterns:
            violations += len(re.findall(p, text, re.IGNORECASE))

        return max(0.0, 1.0 - violations * 0.25)

    def _score_academic_tone(self, text: str) -> float:
        conversational = [
            r"\blet['\u2019]s\b", r"\byou\b", r"\bwe'll\b", r"\bI'll\b",
            r"\bwell,?\b", r"\bso,?\b",
        ]
        hits = sum(1 for p in conversational if re.search(p, text, re.IGNORECASE))
        academic_markers = [
            r"\btherefore\b", r"\bhowever\b", r"\bfurthermore\b",
            r"\bconsequently\b", r"\bnevertheless\b", r"\bmoreover\b",
            r"\bwhereas\b", r"\balthough\b", r"\bdespite\b", r"\bhence\b",
            r"\bthus\b", r"\bspecifically\b", r"\bnotably\b",
        ]
        academic = sum(1 for p in academic_markers if re.search(p, text, re.IGNORECASE))
        score = 0.5 + academic * 0.08 - hits * 0.25
        return max(0.0, min(1.0, score))

    def _find_issues(self, text: str, section_type: str) -> List[str]:
        issues = []
        for p in self.WEAK_PATTERNS:
            if re.search(p, text, re.IGNORECASE):
                issues.append(f"Weak phrase: {p}")

        for p in self.FORBIDDEN_PATTERNS:
            if re.search(p, text, re.IGNORECASE):
                issues.append(f"Forbidden phrase: {p[:50]}")

        if re.search(r'\b(in conclusion|to summarize|in summary)\b', text, re.IGNORECASE):
            issues.append("Uses redundant concluding marker")

        if "Insufficient source material" in text:
            issues.append("Missing evidence for claims")
        return issues

    def evaluate_section(self, content: str, evidence_count: int = 0, section_type: str = "") -> Tuple[DepthScore, bool]:
        score = self.evaluate(content, evidence_count, section_type)
        passed = score.passed()
        if not passed:
            logger.info(f"Technical depth check FAILED (score={score.overall:.2f}) for {section_type}")
        return score, passed
