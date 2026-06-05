from typing import Dict, List, Optional, Any
from src.core.logger import get_logger
from src.facts.models import Fact, FactType
from src.facts.store import FactStore

logger = get_logger(__name__)


class EvidenceFidelityScore:
    def __init__(self, fact_store: Optional[FactStore] = None):
        self._fact_store = fact_store

    def score_section(self, section_text: str, facts: List[Fact]) -> Dict:
        if not section_text or not facts:
            return {"evidence_fidelity": 0.0, "fact_types_used": 0, "fact_types_available": 0}

        text_lower = section_text.lower()
        used_fact_ids = set()
        fact_type_usage: Dict[str, bool] = {}

        for fact in facts:
            fact_type_usage[fact.fact_type.value] = False
            if fact.normalized_value[:40] in text_lower:
                used_fact_ids.add(fact.fact_id)
                fact_type_usage[fact.fact_type.value] = True
            else:
                for phrase in self._extract_phrases(fact.value):
                    if phrase in text_lower:
                        used_fact_ids.add(fact.fact_id)
                        fact_type_usage[fact.fact_type.value] = True
                        break

        usage_ratio = len(used_fact_ids) / max(len(facts), 1)
        type_ratio = sum(1 for v in fact_type_usage.values() if v) / max(len(fact_type_usage), 1)

        if len(facts) >= len(used_fact_ids) and len(facts) > 0:
            fidelity = usage_ratio * 0.6 + type_ratio * 0.4
        else:
            fidelity = 0.0

        return {
            "evidence_fidelity": round(fidelity, 3),
            "facts_used": len(used_fact_ids),
            "facts_available": len(facts),
            "fact_types_used": sum(1 for v in fact_type_usage.values() if v),
            "fact_types_available": len(fact_type_usage),
            "usage_ratio": round(usage_ratio, 3),
            "type_diversity": round(type_ratio, 3),
        }

    def _extract_phrases(self, text: str, min_words: int = 4) -> List[str]:
        words = text.split()
        phrases = []
        if len(words) >= min_words:
            for i in range(len(words) - min_words + 1):
                phrase = " ".join(words[i:i + min_words]).lower()
                if len(phrase) > 15:
                    phrases.append(phrase)
        return phrases[:5]

    def score_paragraph(self, paragraph_text: str, facts: List[Fact]) -> float:
        text_lower = paragraph_text.lower()
        used = 0
        for fact in facts:
            if fact.normalized_value[:30] in text_lower:
                used += 1
            elif any(c.lower() in text_lower for c in fact.concepts):
                used += 1
        return round(used / max(len(facts), 1), 3)

    def score_global(self, sections: Dict[str, str],
                      facts_by_section: Dict[str, List[Fact]]) -> Dict:
        scores = {}
        total_fidelity = 0.0
        for section_type, section_text in sections.items():
            facts = facts_by_section.get(section_type, [])
            score = self.score_section(section_text, facts)
            scores[section_type] = score
            total_fidelity += score["evidence_fidelity"]

        overall = total_fidelity / max(len(scores), 1)
        return {
            "evidence_fidelity_score": round(overall, 3),
            "by_section": scores,
            "section_count": len(scores),
        }
