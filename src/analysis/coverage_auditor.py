"""KnowledgeCoverageAuditor — audits fact utilization and drives expansion."""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import Counter
import math
from src.core.logger import get_logger
from src.facts.models import Fact
from src.facts.store import FactStore
from src.analysis.knowledge_model import KnowledgeModel, ConceptCluster

logger = get_logger(__name__)


@dataclass
class CoverageReport:
    total_facts: int = 0
    assigned_facts: int = 0
    generated_facts: int = 0
    utilization_rate: float = 0.0
    total_sources: int = 0
    covered_sources: int = 0
    source_coverage_rate: float = 0.0
    total_clusters: int = 0
    covered_clusters: int = 0
    unused_by_category: Dict[str, int] = field(default_factory=dict)
    unused_facts_sample: List[str] = field(default_factory=list)
    expansion_recommendations: List[str] = field(default_factory=list)
    knowledge_areas: List[str] = field(default_factory=list)
    needs_expansion: bool = False

    def to_dict(self) -> Dict:
        return {
            "total_facts": self.total_facts,
            "assigned_facts": self.assigned_facts,
            "generated_facts": self.generated_facts,
            "utilization_rate": self.utilization_rate,
            "total_sources": self.total_sources,
            "covered_sources": self.covered_sources,
            "source_coverage_rate": self.source_coverage_rate,
            "total_clusters": self.total_clusters,
            "covered_clusters": self.covered_clusters,
            "unused_by_category": self.unused_by_category,
            "needs_expansion": self.needs_expansion,
        }


class KnowledgeCoverageAuditor:
    def __init__(self, fact_store: FactStore, provider=None):
        self._store = fact_store
        self._provider = provider

    def audit(self, model: KnowledgeModel,
              generated_section_facts: List[List[Fact]],
              threshold: float = 0.60) -> CoverageReport:
        all_facts = self._store.get_verified_facts()
        if not all_facts:
            all_facts = self._store.get_all_facts()

        total = len(all_facts)
        if total == 0:
            return CoverageReport()

        generated_ids: Set[str] = set()
        for flist in generated_section_facts:
            generated_ids.update(f.fact_id for f in flist)

        assigned_ids = {f.fact_id for c in model.clusters for f in c.facts}

        assigned_count = len(assigned_ids)
        generated_count = len(generated_ids)
        utilization_rate = round(generated_count / max(total, 1), 4)

        all_sources = {f.source.file_name for f in all_facts if f.source.file_name}
        used_sources = {
            f.source.file_name for f in all_facts
            if f.fact_id in generated_ids and f.source.file_name
        }
        total_sources = len(all_sources)
        covered_sources = len(used_sources)
        source_coverage = round(covered_sources / max(total_sources, 1), 4)

        unused = [f for f in all_facts if f.fact_id not in generated_ids]
        unused_by_category = self._categorize_unused(unused, model)
        unused_sample = [f.value[:120] for f in unused[:10]]

        generated_map: Dict[str, Set[str]] = {}
        for c in model.clusters:
            gids = {f.fact_id for f in c.facts if f.fact_id in generated_ids}
            if gids:
                generated_map[c.name] = gids

        recs = self._generate_recommendations(
            model, unused_by_category, unused, generated_map
        )
        needs_exp = utilization_rate < threshold

        knowledge_areas = [c.name for c in model.clusters if c.fact_count > 0]

        return CoverageReport(
            total_facts=total,
            assigned_facts=assigned_count,
            generated_facts=generated_count,
            utilization_rate=utilization_rate,
            total_sources=total_sources,
            covered_sources=covered_sources,
            source_coverage_rate=source_coverage,
            total_clusters=len(model.clusters),
            covered_clusters=len(model.clusters),
            unused_by_category=unused_by_category,
            unused_facts_sample=unused_sample,
            expansion_recommendations=recs,
            knowledge_areas=knowledge_areas,
            needs_expansion=needs_exp,
        )

    def _categorize_unused(self, unused: List[Fact],
                           model: KnowledgeModel) -> Dict[str, int]:
        categories: Dict[str, int] = {
            "low_confidence": 0,
            "duplicate": 0,
            "low_information": 0,
            "high_coverage_gap": 0,
        }

        for f in unused:
            if f.confidence < 0.3:
                categories["low_confidence"] += 1
            elif len(f.value.split()) < 5:
                categories["low_information"] += 1
            else:
                dup = False
                for c in model.clusters:
                    for cf in c.facts:
                        if (cf.fact_id != f.fact_id and
                                self._text_overlap(f.value, cf.value) > 0.85):
                            dup = True
                            break
                    if dup:
                        break
                if dup:
                    categories["duplicate"] += 1
                else:
                    categories["high_coverage_gap"] += 1

        return categories

    def _text_overlap(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        overlap = len(words_a & words_b)
        return overlap / max(len(words_a | words_b), 1)

    def _generate_recommendations(
        self,
        model: KnowledgeModel,
        unused_by_category: Dict[str, int],
        unused: List[Fact],
        generated_map: Dict[str, Set[str]],
    ) -> List[str]:
        recs = []
        gap_count = unused_by_category.get("high_coverage_gap", 0)
        if gap_count > 0:
            recs.append(
                f"{gap_count} high-confidence facts unused — consider generating "
                f"additional sections or expanding existing ones"
            )
            if gap_count >= 30:
                sample_texts = [f.value[:80] for f in unused
                                if f.confidence >= 0.5][:5]
                if sample_texts:
                    recs.append(
                        f"Unused fact themes: {'; '.join(sample_texts)}"
                    )
        low_conf = unused_by_category.get("low_confidence", 0)
        if low_conf > 10:
            recs.append(
                f"{low_conf} low-confidence facts excluded (confidence < 0.3)"
            )

        largest_generated = max(
            (len(v) for v in generated_map.values()),
            default=0,
        )
        if largest_generated < 100:
            recs.append(
                "All generated sections are small — increase per-section "
                "capacity to cover more facts"
            )

        return recs

    def get_expansion_facts(self, model: KnowledgeModel,
                            unused: List[Fact],
                            min_confidence: float = 0.5,
                            max_facts: int = 300) -> List[Fact]:
        candidates = [
            f for f in unused
            if f.confidence >= min_confidence and len(f.value.split()) >= 5
        ]
        candidates.sort(key=lambda f: f.confidence, reverse=True)
        return candidates[:max_facts]

    def suggest_new_clusters(self, unused: List[Fact],
                             max_suggestions: int = 3) -> List[Dict]:
        if not unused or not self._provider:
            return []

        high_conf = [f for f in unused if f.confidence >= 0.5][:30]
        if len(high_conf) < 5:
            return []

        from src.providers.base import CompletionOptions, Message
        samples = "\n".join(
            f"  [{f.fact_type.value}] {f.value[:150]}"
            for f in high_conf[:20]
        )
        prompt = (
            f"These unused facts might form new report sections.\n"
            f"Suggest up to {max_suggestions} new section headings.\n\n"
            f"UNUSED FACTS:\n{samples}\n\n"
            f"Return ONLY valid JSON array of objects with 'heading', "
            f"'description', and 'reason' fields:\n"
            f'[{{"heading": "...", "description": "...", "reason": "..."}}]'
        )
        try:
            messages = [
                Message(role="system",
                        content="You are a knowledge organization expert."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.3, max_tokens=1024, timeout=60)
            response = self._provider.chat(messages, options=opts)
            import json, re
            raw = response.content.strip()
            json_match = re.search(r"\[.*\]", raw, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return []
        except Exception as e:
            logger.warning(f"New cluster suggestion failed: {e}")
            return []
