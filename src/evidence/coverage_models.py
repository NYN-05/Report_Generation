from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class CoverageLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

    @classmethod
    def from_score(cls, score: float) -> "CoverageLevel":
        if score >= 0.8:
            return cls.HIGH
        elif score >= 0.5:
            return cls.MEDIUM
        elif score >= 0.1:
            return cls.LOW
        return cls.NONE


class GenerationMode(Enum):
    NORMAL = "normal"
    CAUTIOUS = "cautious"
    INSUFFICIENT = "insufficient_evidence"
    NOT_POSSIBLE = "not_possible"

    @classmethod
    def from_coverage(cls, coverage: float) -> "GenerationMode":
        if coverage >= 0.8:
            return cls.NORMAL
        elif coverage >= 0.5:
            return cls.CAUTIOUS
        elif coverage >= 0.1:
            return cls.INSUFFICIENT
        return cls.NOT_POSSIBLE


@dataclass
class ParagraphCoverage:
    paragraph_id: str
    paragraph_text: str
    coverage_score: float
    fact_ids: List[str] = field(default_factory=list)
    source_documents: List[str] = field(default_factory=list)
    source_pages: List[int] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    coverage_level: CoverageLevel = CoverageLevel.NONE

    def __post_init__(self):
        self.coverage_level = CoverageLevel.from_score(self.coverage_score)

    def to_dict(self) -> Dict:
        return {
            "paragraph_id": self.paragraph_id,
            "coverage_score": self.coverage_score,
            "coverage_level": self.coverage_level.value,
            "fact_count": len(self.fact_ids),
            "source_count": len(self.source_documents),
            "source_pages": self.source_pages,
            "missing_requirements": self.missing_requirements[:5],
            "text_preview": self.paragraph_text[:100],
        }


@dataclass
class SectionCoverage:
    section_type: str
    heading: str
    coverage_score: float
    confidence_score: float
    paragraph_coverages: List[ParagraphCoverage] = field(default_factory=list)
    supporting_fact_ids: List[str] = field(default_factory=list)
    fact_count: int = 0
    missing_fact_types: List[str] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    coverage_level: CoverageLevel = CoverageLevel.NONE
    generation_mode: GenerationMode = GenerationMode.NOT_POSSIBLE

    def __post_init__(self):
        self.coverage_level = CoverageLevel.from_score(self.coverage_score)
        self.generation_mode = GenerationMode.from_coverage(self.coverage_score)

    @property
    def paragraphs_below_threshold(self) -> int:
        return sum(1 for p in self.paragraph_coverages if p.coverage_score < 0.8)

    def to_dict(self) -> Dict:
        return {
            "section_type": self.section_type,
            "heading": self.heading,
            "coverage_score": round(self.coverage_score, 3),
            "confidence_score": round(self.confidence_score, 3),
            "coverage_level": self.coverage_level.value,
            "generation_mode": self.generation_mode.value,
            "paragraph_count": len(self.paragraph_coverages),
            "paragraphs_below_threshold": self.paragraphs_below_threshold,
            "fact_count": self.fact_count,
            "supporting_fact_ids": self.supporting_fact_ids[:10],
            "missing_fact_types": self.missing_fact_types,
            "missing_requirements": self.missing_requirements[:5],
        }


@dataclass
class EvidenceCoverageReport:
    sections: Dict[str, SectionCoverage] = field(default_factory=dict)
    overall_coverage: float = 0.0
    overall_confidence: float = 0.0
    total_facts: int = 0
    total_paragraphs: int = 0
    sections_below_threshold: int = 0
    generation_mode: GenerationMode = GenerationMode.NOT_POSSIBLE

    def __post_init__(self):
        if self.sections:
            scores = [s.coverage_score for s in self.sections.values()]
            self.overall_coverage = round(sum(scores) / len(scores), 3) if scores else 0.0
            confidences = [s.confidence_score for s in self.sections.values()]
            self.overall_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0
            self.total_paragraphs = sum(len(s.paragraph_coverages) for s in self.sections.values())
            self.sections_below_threshold = sum(1 for s in self.sections.values() if s.coverage_score < 0.8)
            self.generation_mode = GenerationMode.from_coverage(self.overall_coverage)

    def to_dict(self) -> Dict:
        return {
            "sections": {k: v.to_dict() for k, v in self.sections.items()},
            "overall_coverage": self.overall_coverage,
            "overall_confidence": self.overall_confidence,
            "total_facts": self.total_facts,
            "total_paragraphs": self.total_paragraphs,
            "sections_below_threshold": self.sections_below_threshold,
            "generation_mode": self.generation_mode.value,
            "section_count": len(self.sections),
        }
