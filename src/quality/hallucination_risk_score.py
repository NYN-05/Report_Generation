from typing import Dict, List, Optional, Any
from src.core.logger import get_logger
from src.facts.models import Fact, FactType
from src.facts.store import FactStore
from src.validation.hallucination_detector import HallucinationDetector

logger = get_logger(__name__)


class HallucinationRiskScore:
    def __init__(self, fact_store: FactStore):
        self._detector = HallucinationDetector(fact_store)
        self._fact_store = fact_store

    def score_section(self, section_text: str, facts: List[Fact],
                       section_type: str = "") -> Dict:
        if not section_text:
            return {"hallucination_risk": 0.0, "hallucination_free": True}

        result = self._detector.check_section(
            self._fact_store, section_text, section_type
        )

        total_issues = result["total_issues"]
        unsupported = result["unsupported_claims"]

        paragraph_count = max(len([p for p in section_text.split("\n\n") if p.strip()]), 1)

        risk = min(1.0, unsupported / max(paragraph_count, 1))
        weighted_risk = min(1.0, risk * 1.5)

        return {
            "hallucination_risk": round(weighted_risk, 3),
            "total_issues": total_issues,
            "unsupported_claims": unsupported,
            "warnings": result["warnings"],
            "hallucination_free": total_issues == 0,
            "paragraph_count": paragraph_count,
            "issues_per_paragraph": round(total_issues / paragraph_count, 3),
        }

    def score_global(self, sections: Dict[str, str],
                      facts_by_section: Dict[str, List[Fact]]) -> Dict:
        scores = {}
        total_risk = 0.0
        total_issues = 0

        for section_type, section_text in sections.items():
            facts = facts_by_section.get(section_type, [])
            result = self.score_section(section_text, facts, section_type)
            scores[section_type] = result
            total_risk += result["hallucination_risk"]
            total_issues += result["total_issues"]

        return {
            "hallucination_risk_score": round(total_risk / max(len(scores), 1), 3),
            "total_hallucination_issues": total_issues,
            "hallucination_free": total_issues == 0,
            "by_section": scores,
        }
