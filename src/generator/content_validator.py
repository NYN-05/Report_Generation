"""ContentValidator — validates content quality before DOCX export.

Checks:
- evidence coverage
- paragraph quality
- citation quality
- technical depth
- structure quality
- bullet formatting

If validation fails for any section, that section must be regenerated.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from src.core.logger import get_logger
from .content_blocks import (
    SectionContent, ParagraphBlock, BulletListBlock,
    SourceRequiredBlock, TableBlock, FigureBlock,
)
from .paragraph_quality import ParagraphQualityControl
from .technical_depth import TechnicalDepthEvaluator

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    passed: bool = True
    section: str = ""
    evidence_coverage: float = 0.0
    paragraph_quality: float = 0.0
    citation_quality: float = 0.0
    technical_depth: float = 0.0
    structure_quality: float = 0.0
    bullet_formatting: float = 1.0
    issues: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def overall_score(self) -> float:
        return (
            self.evidence_coverage * 0.25
            + self.paragraph_quality * 0.20
            + self.citation_quality * 0.15
            + self.technical_depth * 0.20
            + self.structure_quality * 0.10
            + self.bullet_formatting * 0.10
        )

    def should_regenerate(self, threshold: float = 0.6) -> bool:
        return self.overall_score() < threshold or not self.passed


class ContentValidator:

    def __init__(self):
        self._quality = ParagraphQualityControl()
        self._depth = TechnicalDepthEvaluator()

    def validate_section(self, section: SectionContent, section_type: str, topic: str) -> ValidationResult:
        result = ValidationResult(section=section.heading)

        result.evidence_coverage = self._check_evidence_coverage(section)
        if result.evidence_coverage < 0.3:
            result.issues.append(f"Low evidence coverage: {result.evidence_coverage:.2f}")

        result.paragraph_quality = self._check_paragraph_quality(section)
        if result.paragraph_quality < 0.5:
            result.issues.append(f"Low paragraph quality: {result.paragraph_quality:.2f}")

        result.citation_quality = self._check_citation_quality(section)
        if result.citation_quality < 0.3:
            result.issues.append(f"Low citation quality: {result.citation_quality:.2f}")

        result.technical_depth = self._check_technical_depth(section)
        if result.technical_depth < 0.4:
            result.issues.append(f"Low technical depth: {result.technical_depth:.2f}")

        result.structure_quality = self._check_structure(section)
        if result.structure_quality < 0.5:
            result.issues.append(f"Poor structure: {result.structure_quality:.2f}")

        result.bullet_formatting = self._check_bullet_formatting(section)
        if result.bullet_formatting < 0.8:
            result.issues.append(f"Bullet formatting issues: {result.bullet_formatting:.2f}")

        if len(result.issues) > 2:
            result.passed = False

        result.details = {
            "block_count": len(section.blocks),
            "paragraph_count": sum(1 for b in section.blocks if isinstance(b, ParagraphBlock)),
            "source_required_count": sum(1 for b in section.blocks if isinstance(b, SourceRequiredBlock)),
            "bullet_list_count": sum(1 for b in section.blocks if isinstance(b, BulletListBlock)),
            "table_count": sum(1 for b in section.blocks if isinstance(b, TableBlock)),
            "figure_count": sum(1 for b in section.blocks if isinstance(b, FigureBlock)),
            "total_words": section.total_words,
            "evidence_sources": len(section.evidence_sources),
        }

        logger.info(
            f"Validation [{section.heading}]: overall={result.overall_score():.2f} "
            f"evid={result.evidence_coverage:.2f} para={result.paragraph_quality:.2f} "
            f"cite={result.citation_quality:.2f} depth={result.technical_depth:.2f} "
            f"struct={result.structure_quality:.2f} bullet={result.bullet_formatting:.2f} "
            f"passed={result.passed} issues={len(result.issues)}"
        )

        return result

    def _check_evidence_coverage(self, section: SectionContent) -> float:
        if not section.blocks:
            return 0.0

        paras = [b for b in section.blocks if isinstance(b, ParagraphBlock)]
        if not paras:
            return 0.5

        with_evidence = sum(1 for p in paras if p.evidence_source or "[Source Material Required]" in p.text)
        return with_evidence / len(paras)

    def _check_paragraph_quality(self, section: SectionContent) -> float:
        paras = [b for b in section.blocks if isinstance(b, ParagraphBlock)]
        if not paras:
            return 0.5

        scores = []
        for p in paras:
            if "Insufficient source material" in p.text:
                scores.append(0.0)
                continue
            scores_tuple = self._quality.score(p.text)
            avg = sum(scores_tuple) / len(scores_tuple)
            scores.append(avg)

        return sum(scores) / len(scores) if scores else 0.0

    def _check_citation_quality(self, section: SectionContent) -> float:
        all_text = " ".join(
            b.text if isinstance(b, ParagraphBlock) else ""
            for b in section.blocks
        )

        has_square_brackets = bool(re.search(r'\[\d+\]', all_text))
        has_according = bool(re.search(r'According to', all_text))
        has_source_ref = bool(re.search(r'(source|reference|document|study|work)', all_text, re.IGNORECASE))
        has_numbers = bool(re.search(r'\d+\.?\d*%|\d+\.?\d*\s*(accuracy|precision|recall|F1|score)', all_text, re.IGNORECASE))
        has_fake = bool(re.search(r'(fake|hallucinated|fabricated|invented)', all_text, re.IGNORECASE))

        score = 0.0
        if has_square_brackets: score += 0.4
        if has_according: score += 0.2
        if has_source_ref: score += 0.1
        if has_numbers: score += 0.2
        if len(section.evidence_sources) > 0: score += 0.1
        if has_fake: score -= 0.5

        return max(0.0, min(1.0, score))

    def _check_technical_depth(self, section: SectionContent) -> float:
        all_text = " ".join(
            b.text if isinstance(b, ParagraphBlock) else ""
            for b in section.blocks
        )
        if not all_text:
            return 0.0
        score, _ = self._depth.evaluate_section(all_text, len(section.evidence_sources))
        return score.relevance * 0.2 + score.technical_detail * 0.3 + score.evidence_usage * 0.2 + score.uniqueness * 0.15 + score.academic_tone * 0.15

    def _check_structure(self, section: SectionContent) -> float:
        has_heading = any(b.__class__.__name__ == "HeadingBlock" for b in section.blocks)
        has_paragraph = any(isinstance(b, ParagraphBlock) for b in section.blocks)
        block_count = len(section.blocks)

        score = 0.0
        if has_heading: score += 0.3
        if has_paragraph: score += 0.3
        if block_count >= 3: score += 0.2
        if block_count >= 5: score += 0.2

        return score

    def _check_bullet_formatting(self, section: SectionContent) -> float:
        penalties = 0.0
        for block in section.blocks:
            if isinstance(block, ParagraphBlock):
                if re.search(r'(?:^|\n)\s*[•\-\*]\s', block.text):
                    penalties += 0.3
                if re.search(r'(?:such as|including|for example|e\.g\.)[^.]*(?:•|\-|\*)', block.text, re.IGNORECASE):
                    penalties += 0.4
        return max(0.0, 1.0 - penalties)
