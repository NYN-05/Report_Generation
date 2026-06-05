from typing import Dict, List, Optional, Any, Set
from collections import defaultdict
from src.core.logger import get_logger
from src.facts.models import Fact, SourceReference
from src.facts.store import FactStore

logger = get_logger(__name__)


class SourceCoverageScore:
    def __init__(self, fact_store: Optional[FactStore] = None):
        self._fact_store = fact_store

    def score_section(self, section_text: str, facts: List[Fact]) -> Dict:
        if not section_text or not facts:
            return {"source_coverage": 0.0}

        text_lower = section_text.lower()
        source_usage: Dict[str, Set[str]] = defaultdict(set)

        for fact in facts:
            if fact.normalized_value[:40] in text_lower:
                source_key = fact.source.file_path or fact.source.resource_id
                source_usage[source_key].add(fact.fact_id)

        unique_sources = len(source_usage)
        all_sources = len(set(
            f.source.file_path or f.source.resource_id for f in facts
        ))

        coverage = round(unique_sources / max(all_sources, 1), 3)
        source_diversity = round(
            sum(len(v) for v in source_usage.values()) / max(unique_sources, 1),
            3
        )

        return {
            "source_coverage": coverage,
            "unique_sources_used": unique_sources,
            "total_sources_available": all_sources,
            "source_diversity": source_diversity,
            "sources": {
                src: len(fids) for src, fids in source_usage.items()
            },
        }

    def score_paragraph(self, paragraph_text: str, facts: List[Fact]) -> float:
        text_lower = paragraph_text.lower()
        used_sources = set()
        for fact in facts:
            if fact.normalized_value[:30] in text_lower:
                source_key = fact.source.file_path or fact.source.resource_id
                used_sources.add(source_key)
        all_sources = set(f.source.file_path or f.source.resource_id for f in facts)
        return round(len(used_sources) / max(len(all_sources), 1), 3)

    def score_global(self, sections: Dict[str, str],
                      facts_by_section: Dict[str, List[Fact]]) -> Dict:
        scores = {}
        total_coverage = 0.0
        for section_type, section_text in sections.items():
            facts = facts_by_section.get(section_type, [])
            result = self.score_section(section_text, facts)
            scores[section_type] = result
            total_coverage += result["source_coverage"]

        return {
            "source_coverage_score": round(total_coverage / max(len(scores), 1), 3),
            "by_section": scores,
        }
