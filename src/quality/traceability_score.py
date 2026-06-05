from typing import Dict, List, Optional, Any
from src.core.logger import get_logger
from src.facts.models import Fact
from src.facts.store import FactStore
from src.evidence.traceability import TraceabilityBuilder

logger = get_logger(__name__)


class TraceabilityScore:
    def __init__(self, traceability_builder: TraceabilityBuilder):
        self._traceability = traceability_builder

    def score_section(self, section_type: str, paragraphs: List[Dict],
                       facts: List[Fact]) -> Dict:
        if not paragraphs:
            return {"traceability": 0.0}

        traceable = 0
        total = len(paragraphs)
        scores = []

        for para in paragraphs:
            para_id = para.get("paragraph_id", "unknown")
            para_text = para.get("text", "")
            para_fact_ids = para.get("fact_ids", [])

            pm = self._traceability.build_paragraph_map(
                paragraph_id=para_id,
                section_type=section_type,
                paragraph_text=para_text,
                paragraph_fact_ids=para_fact_ids,
            )
            scores.append(pm.traceability_score)
            if pm.has_traceability:
                traceable += 1

        avg_score = sum(scores) / max(len(scores), 1)
        return {
            "traceability": round(avg_score, 3),
            "traceable_paragraphs": traceable,
            "total_paragraphs": total,
            "traceability_ratio": round(traceable / max(total, 1), 3),
            "paragraph_scores": [
                round(s, 3) for s in scores[:10]
            ],
        }

    def score_global(self, sections: Dict[str, List[Dict]],
                      facts_by_section: Dict[str, List[Fact]]) -> Dict:
        scores = {}
        total_traceability = 0.0
        for section_type, paragraphs in sections.items():
            facts = facts_by_section.get(section_type, [])
            result = self.score_section(section_type, paragraphs, facts)
            scores[section_type] = result
            total_traceability += result["traceability"]

        return {
            "traceability_score": round(total_traceability / max(len(scores), 1), 3),
            "by_section": scores,
        }
