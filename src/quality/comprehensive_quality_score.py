from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from src.core.logger import get_logger
from src.facts.models import Fact
from src.facts.store import FactStore
from src.evidence.traceability import TraceabilityBuilder
from .evidence_fidelity_score import EvidenceFidelityScore
from .fact_utilization_score import FactUtilizationScore
from .source_coverage_score import SourceCoverageScore
from .traceability_score import TraceabilityScore
from .hallucination_risk_score import HallucinationRiskScore

logger = get_logger(__name__)


@dataclass
class EvidenceQualityReport:
    evidence_fidelity: float = 0.0
    fact_utilization: float = 0.0
    source_coverage: float = 0.0
    traceability: float = 0.0
    hallucination_risk: float = 0.0
    overall_quality: float = 0.0
    passed: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "evidence_fidelity": self.evidence_fidelity,
            "fact_utilization": self.fact_utilization,
            "source_coverage": self.source_coverage,
            "traceability": self.traceability,
            "hallucination_risk": self.hallucination_risk,
            "overall_quality": self.overall_quality,
            "passed": self.passed,
            "details": self.details,
        }


class ComprehensiveQualityScore:
    FIDELITY_WEIGHT = 0.25
    UTILIZATION_WEIGHT = 0.2
    COVERAGE_WEIGHT = 0.2
    TRACEABILITY_WEIGHT = 0.2
    HALLUCINATION_WEIGHT = 0.15
    MIN_QUALITY = 0.6

    def __init__(self, fact_store: FactStore,
                 traceability_builder: TraceabilityBuilder):
        self._fidelity_score = EvidenceFidelityScore(fact_store)
        self._utilization_score = FactUtilizationScore(fact_store)
        self._source_coverage = SourceCoverageScore(fact_store)
        self._traceability = TraceabilityScore(traceability_builder)
        self._hallucination = HallucinationRiskScore(fact_store)

    def evaluate_section(self, section_type: str, section_text: str,
                          facts: List[Fact], paragraphs: Optional[List[Dict]] = None) -> Dict:
        fidelity = self._fidelity_score.score_section(section_text, facts)
        utilization = self._utilization_score.score(section_text, facts)
        source = self._source_coverage.score_section(section_text, facts)
        trace = self._traceability.score_section(
            section_type, paragraphs or [{"text": section_text}], facts
        )
        hallucination = self._hallucination.score_section(section_text, facts, section_type)

        quality = (
            fidelity["evidence_fidelity"] * self.FIDELITY_WEIGHT +
            utilization["fact_utilization"] * self.UTILIZATION_WEIGHT +
            source["source_coverage"] * self.COVERAGE_WEIGHT +
            trace["traceability"] * self.TRACEABILITY_WEIGHT +
            (1 - hallucination["hallucination_risk"]) * self.HALLUCINATION_WEIGHT
        )

        return {
            "quality_score": round(quality, 3),
            "evidence_fidelity": fidelity["evidence_fidelity"],
            "fact_utilization": utilization["fact_utilization"],
            "source_coverage": source["source_coverage"],
            "traceability": trace["traceability"],
            "hallucination_risk": hallucination["hallucination_risk"],
            "hallucination_free": hallucination["hallucination_free"],
            "passed": quality >= self.MIN_QUALITY,
        }

    def evaluate_report(self, sections: Dict[str, str],
                         facts_by_section: Dict[str, List[Fact]],
                         paragraphs_by_section: Optional[Dict[str, List[Dict]]] = None) -> EvidenceQualityReport:
        section_results = {}
        total_quality = 0.0
        total_fidelity = 0.0
        total_utilization = 0.0
        total_coverage = 0.0
        total_traceability = 0.0
        total_hallucination = 0.0

        for section_type, section_text in sections.items():
            facts = facts_by_section.get(section_type, [])
            paras = (paragraphs_by_section or {}).get(section_type)
            result = self.evaluate_section(section_type, section_text, facts, paras)
            section_results[section_type] = result
            total_quality += result["quality_score"]
            total_fidelity += result["evidence_fidelity"]
            total_utilization += result["fact_utilization"]
            total_coverage += result["source_coverage"]
            total_traceability += result["traceability"]
            total_hallucination += result["hallucination_risk"]

        count = max(len(section_results), 1)
        report = EvidenceQualityReport(
            evidence_fidelity=round(total_fidelity / count, 3),
            fact_utilization=round(total_utilization / count, 3),
            source_coverage=round(total_coverage / count, 3),
            traceability=round(total_traceability / count, 3),
            hallucination_risk=round(total_hallucination / count, 3),
            overall_quality=round(total_quality / count, 3),
            passed=(total_quality / count) >= self.MIN_QUALITY,
            details={
                "section_results": section_results,
                "section_count": len(section_results),
            },
        )

        logger.info(
            f"Evidence quality report: overall={report.overall_quality:.2%}, "
            f"fidelity={report.evidence_fidelity:.2%}, "
            f"utilization={report.fact_utilization:.2%}, "
            f"traceability={report.traceability:.2%}, "
            f"hallucination_risk={report.hallucination_risk:.2%}, "
            f"passed={report.passed}"
        )
        return report
