from typing import Dict, List, Optional, Any, Set
from src.core.logger import get_logger
from src.facts.models import Fact, FactType
from src.facts.store import FactStore

logger = get_logger(__name__)


class FactUtilizationScore:
    def __init__(self, fact_store: Optional[FactStore] = None):
        self._fact_store = fact_store

    def score(self, section_text: str, facts: List[Fact]) -> Dict:
        if not section_text or not facts:
            return {"fact_utilization": 0.0}

        text_lower = section_text.lower()
        total_weight = 0.0
        utilized_weight = 0.0
        utilization_details = []

        for fact in facts:
            weight = fact.confidence
            total_weight += weight

            if fact.normalized_value[:40] in text_lower:
                utilized_weight += weight
                utilization_details.append({
                    "fact_id": fact.fact_id,
                    "fact_type": fact.fact_type.value,
                    "confidence": fact.confidence,
                    "weight": weight,
                    "utilized": True,
                })
            else:
                utilization_details.append({
                    "fact_id": fact.fact_id,
                    "fact_type": fact.fact_type.value,
                    "confidence": fact.confidence,
                    "weight": weight,
                    "utilized": False,
                })

        utilization = round(utilized_weight / max(total_weight, 1), 3)

        high_value_used = sum(
            1 for f in facts if f.confidence >= 0.8
            and f.normalized_value[:40] in text_lower
        )
        high_value_total = sum(1 for f in facts if f.confidence >= 0.8)

        return {
            "fact_utilization": utilization,
            "utilized_weight": round(utilized_weight, 3),
            "total_weight": round(total_weight, 3),
            "high_value_used": high_value_used,
            "high_value_total": high_value_total,
            "high_value_utilization": round(
                high_value_used / max(high_value_total, 1), 3
            ),
            "total_facts": len(facts),
            "utilized_facts": sum(1 for d in utilization_details if d["utilized"]),
        }

    def score_by_type(self, section_text: str, facts: List[Fact]) -> Dict:
        text_lower = section_text.lower()
        type_usage: Dict[str, Dict] = {}

        for fact in facts:
            ft = fact.fact_type.value
            if ft not in type_usage:
                type_usage[ft] = {"total": 0, "used": 0, "total_weight": 0.0, "used_weight": 0.0}

            type_usage[ft]["total"] += 1
            type_usage[ft]["total_weight"] += fact.confidence

            if fact.normalized_value[:40] in text_lower:
                type_usage[ft]["used"] += 1
                type_usage[ft]["used_weight"] += fact.confidence

        results = {}
        for ft, stats in type_usage.items():
            results[ft] = {
                "utilization": round(stats["used"] / max(stats["total"], 1), 3),
                "weighted_utilization": round(
                    stats["used_weight"] / max(stats["total_weight"], 1), 3
                ),
                "used": stats["used"],
                "total": stats["total"],
            }

        return results

    def score_global(self, sections: Dict[str, str],
                      facts_by_section: Dict[str, List[Fact]]) -> Dict:
        scores = {}
        total_util = 0.0
        for section_type, section_text in sections.items():
            facts = facts_by_section.get(section_type, [])
            result = self.score(section_text, facts)
            scores[section_type] = result
            total_util += result["fact_utilization"]

        return {
            "fact_utilization_score": round(total_util / max(len(scores), 1), 3),
            "by_section": scores,
        }
