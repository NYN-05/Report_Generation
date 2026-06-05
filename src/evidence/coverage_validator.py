from typing import Dict, List, Optional, Any
from src.core.logger import get_logger
from .coverage_models import (
    EvidenceCoverageReport, SectionCoverage, CoverageLevel, GenerationMode,
)

logger = get_logger(__name__)


class CoverageValidationIssue:
    def __init__(self, section_type: str, message: str,
                 severity: str = "warning", coverage_score: float = 0.0):
        self.section_type = section_type
        self.message = message
        self.severity = severity
        self.coverage_score = coverage_score

    def to_dict(self) -> Dict:
        return {
            "section_type": self.section_type,
            "message": self.message,
            "severity": self.severity,
            "coverage_score": self.coverage_score,
        }


class CoverageValidator:
    MIN_SECTION_COVERAGE = 0.5
    MIN_PARAGRAPH_COVERAGE = 0.3
    MIN_CONFIDENCE = 0.4

    def __init__(self):
        self._issues: List[CoverageValidationIssue] = []

    def validate(self, report: EvidenceCoverageReport) -> List[CoverageValidationIssue]:
        self._issues = []

        if not report.sections:
            self._issues.append(CoverageValidationIssue(
                "all", "No sections in coverage report", "error", 0.0
            ))
            return self._issues

        for section_type, coverage in report.sections.items():
            self._validate_section(section_type, coverage)

        self._validate_overall(report)
        return self._issues

    def _validate_section(self, section_type: str, coverage: SectionCoverage):
        if coverage.coverage_score < self.MIN_SECTION_COVERAGE:
            self._issues.append(CoverageValidationIssue(
                section_type,
                f"Section coverage {coverage.coverage_score:.1%} below minimum {self.MIN_SECTION_COVERAGE:.0%}",
                "error" if coverage.coverage_score < 0.3 else "warning",
                coverage.coverage_score,
            ))

        if coverage.confidence_score < self.MIN_CONFIDENCE:
            self._issues.append(CoverageValidationIssue(
                section_type,
                f"Section confidence {coverage.confidence_score:.1%} below minimum {self.MIN_CONFIDENCE:.0%}",
                "warning",
                coverage.coverage_score,
            ))

        if coverage.fact_count == 0:
            self._issues.append(CoverageValidationIssue(
                section_type,
                "No supporting facts for section",
                "warning",
                coverage.coverage_score,
            ))

        paragraphs_below = coverage.paragraphs_below_threshold
        if paragraphs_below > 0:
            ratio = paragraphs_below / max(len(coverage.paragraph_coverages), 1)
            if ratio > 0.5:
                self._issues.append(CoverageValidationIssue(
                    section_type,
                    f"{paragraphs_below}/{len(coverage.paragraph_coverages)} paragraphs below coverage threshold",
                    "warning",
                    coverage.coverage_score,
                ))

        if coverage.missing_fact_types:
            self._issues.append(CoverageValidationIssue(
                section_type,
                f"Missing fact types: {', '.join(coverage.missing_fact_types[:3])}",
                "info",
                coverage.coverage_score,
            ))

    def _validate_overall(self, report: EvidenceCoverageReport):
        if report.generation_mode in (GenerationMode.INSUFFICIENT, GenerationMode.NOT_POSSIBLE):
            self._issues.append(CoverageValidationIssue(
                "overall",
                f"Overall coverage {report.overall_coverage:.1%} - generation mode: {report.generation_mode.value}",
                "error",
                report.overall_coverage,
            ))

        if report.sections_below_threshold > len(report.sections) / 2:
            self._issues.append(CoverageValidationIssue(
                "overall",
                f"{report.sections_below_threshold}/{len(report.sections)} sections below coverage threshold",
                "warning",
                report.overall_coverage,
            ))

    def get_generation_decision(self, section_type: str,
                                 coverage: SectionCoverage) -> Dict:
        if coverage.generation_mode == GenerationMode.NORMAL:
            return {
                "can_generate": True,
                "mode": "normal",
                "message": "Sufficient evidence for full generation",
                "restrictions": [],
            }
        elif coverage.generation_mode == GenerationMode.CAUTIOUS:
            return {
                "can_generate": True,
                "mode": "cautious",
                "message": "Generate with evidence gap warnings",
                "restrictions": [
                    "Flag unsupported claims",
                    "Use hedging language for uncertain assertions",
                    "Mark evidence gaps explicitly",
                ],
            }
        elif coverage.generation_mode == GenerationMode.INSUFFICIENT:
            return {
                "can_generate": True,
                "mode": "insufficient_evidence",
                "message": "Insufficient evidence - generate with explicit gap markers",
                "restrictions": [
                    "Do not fabricate missing information",
                    "Insert [Insufficient source material] for unsupported claims",
                    "Flag every claim not backed by facts",
                ],
            }
        else:
            return {
                "can_generate": False,
                "mode": "not_possible",
                "message": "Cannot generate - no evidence available",
                "restrictions": [
                    "Do not generate this section",
                    "Report missing evidence to user",
                ],
            }

    def get_all_issues(self) -> List[CoverageValidationIssue]:
        return list(self._issues)

    def get_summary(self) -> Dict:
        if not self._issues:
            return {"total_issues": 0, "valid": True}
        errors = sum(1 for i in self._issues if i.severity == "error")
        warnings = sum(1 for i in self._issues if i.severity == "warning")
        info = sum(1 for i in self._issues if i.severity == "info")
        return {
            "total_issues": len(self._issues),
            "errors": errors,
            "warnings": warnings,
            "info": info,
            "valid": errors == 0,
        }

    def reset(self):
        self._issues.clear()
