from typing import Dict, List, Optional, Set, Any, Tuple
from collections import defaultdict
from src.core.logger import get_logger
from src.facts.models import Fact, FactType, SourceReference
from src.facts.store import FactStore
from src.resource_intelligence.resource_metadata_store import ResourceMetadataStore

logger = get_logger(__name__)


class FusionResult:
    def __init__(self, fact: Fact, source_resources: List[str],
                 confidence: float, fusion_type: str = "cross_reference"):
        self.fact = fact
        self.source_resources = source_resources
        self.confidence = confidence
        self.fusion_type = fusion_type

    def to_dict(self) -> Dict:
        return {
            "fact_id": self.fact.fact_id,
            "value_preview": self.fact.value[:150],
            "fact_type": self.fact.fact_type.value,
            "source_resources": self.source_resources,
            "confidence": self.confidence,
            "fusion_type": self.fusion_type,
        }


class EvidenceFusionEngine:
    def __init__(self, fact_store: FactStore,
                 resource_store: Optional[ResourceMetadataStore] = None):
        self._fact_store = fact_store
        self._resource_store = resource_store or ResourceMetadataStore()
        self._fusion_results: List[FusionResult] = []

    def fuse_by_concept(self, facts: List[Fact]) -> List[FusionResult]:
        concept_groups: Dict[str, List[Fact]] = defaultdict(list)
        for fact in facts:
            for concept in fact.concepts:
                concept_groups[concept.lower()].append(fact)

        results = []
        for concept, group in concept_groups.items():
            if len(group) < 2:
                continue
            resource_ids = list(set(
                f.source.resource_id for f in group if f.source.resource_id
            ))
            if len(resource_ids) < 2:
                continue
            avg_confidence = sum(f.confidence for f in group) / len(group)
            boosted = min(1.0, avg_confidence * 1.15)
            primary_fact = max(group, key=lambda f: f.confidence)
            result = FusionResult(
                fact=primary_fact,
                source_resources=resource_ids,
                confidence=round(boosted, 2),
                fusion_type="concept_cross_reference",
            )
            results.append(result)
            primary_fact.confidence = boosted

        logger.info(f"Fused {len(results)} facts by concept overlap")
        self._fusion_results.extend(results)
        return results

    def fuse_by_type_complement(self, code_facts: List[Fact],
                                  doc_facts: List[Fact]) -> List[FusionResult]:
        results = []
        for cf in code_facts:
            if cf.fact_type != FactType.ALGORITHM and cf.fact_type != FactType.TECHNOLOGY:
                continue
            for df in doc_facts:
                match_score = self._compute_algorithm_match(cf, df)
                if match_score > 0.6:
                    combined = FusionResult(
                        fact=cf,
                        source_resources=list(set([
                            cf.source.resource_id, df.source.resource_id
                        ])),
                        confidence=round(match_score, 2),
                        fusion_type="code_document_cross_validation",
                    )
                    results.append(combined)
                    cf.confidence = max(cf.confidence, match_score)

        logger.info(f"Fused {len(results)} facts by code-document complement")
        self._fusion_results.extend(results)
        return results

    def _compute_algorithm_match(self, code_fact: Fact, doc_fact: Fact) -> float:
        code_name = code_fact.value.lower()
        doc_name = doc_fact.value.lower()
        code_words = set(code_name.split())
        doc_words = set(doc_name.split())
        if not code_words or not doc_words:
            return 0.0
        intersection = code_words & doc_words
        union = code_words | doc_words
        jaccard = len(intersection) / len(union) if union else 0
        return jaccard

    def fuse_by_metric_result(self, metric_facts: List[Fact],
                               result_facts: List[Fact]) -> List[FusionResult]:
        results = []
        for mf in metric_facts:
            for rf in result_facts:
                if self._metric_matches_result(mf, rf):
                    combined = FusionResult(
                        fact=rf,
                        source_resources=list(set([
                            mf.source.resource_id, rf.source.resource_id
                        ])),
                        confidence=round((mf.confidence + rf.confidence) / 2 * 1.1, 2),
                        fusion_type="metric_result_correlation",
                    )
                    results.append(combined)

        self._fusion_results.extend(results)
        return results

    def _metric_matches_result(self, metric_fact: Fact, result_fact: Fact) -> bool:
        if hasattr(metric_fact, 'metric_name') and hasattr(result_fact, 'metric_name'):
            if metric_fact.metric_name and result_fact.metric_name:
                return metric_fact.metric_name.lower() == result_fact.metric_name.lower()
        m_words = set(metric_fact.normalized_value.split())
        r_words = set(result_fact.normalized_value.split())
        common = m_words & r_words
        return len(common) >= 3

    def fuse_all(self, facts: List[Fact]) -> List[FusionResult]:
        all_results = []
        all_results.extend(self.fuse_by_concept(facts))
        doc_facts = [f for f in facts if f.source.file_name.lower().endswith(('.pdf', '.docx', '.md'))]
        code_facts = [f for f in facts if f.source.file_name.lower().endswith(('.py', '.js', '.java', '.cpp', '.rs'))]
        if doc_facts and code_facts:
            all_results.extend(self.fuse_by_type_complement(code_facts, doc_facts))
        metric_facts = self._fact_store.get_by_type(FactType.METRIC)
        result_facts = self._fact_store.get_by_type(FactType.RESULT)
        if metric_facts and result_facts:
            all_results.extend(self.fuse_by_metric_result(metric_facts, result_facts))

        logger.info(
            f"Total fusion results: {len(all_results)} from {len(facts)} facts "
            f"({len(doc_facts)} doc, {len(code_facts)} code)"
        )
        return all_results

    def get_merged_evidence(self, facts: List[Fact]) -> Dict[str, List[Fact]]:
        merged: Dict[str, List[Fact]] = defaultdict(list)
        for fact in facts:
            key = fact.fact_type.value
            merged[key].append(fact)
        return dict(merged)

    def get_cross_resource_context(self) -> Dict:
        if not self._fusion_results:
            return {"fusion_count": 0, "context": "No cross-resource fusion available"}

        validated_claims = []
        for fr in self._fusion_results[:20]:
            validated_claims.append({
                "claim": fr.fact.value[:150],
                "sources": fr.source_resources,
                "confidence": fr.confidence,
                "fusion_type": fr.fusion_type,
            })

        return {
            "fusion_count": len(self._fusion_results),
            "validated_claims": validated_claims,
            "average_confidence": round(
                sum(fr.confidence for fr in self._fusion_results) / max(len(self._fusion_results), 1),
                3
            ),
        }

    def get_all_results(self) -> List[FusionResult]:
        return list(self._fusion_results)

    def reset(self):
        self._fusion_results.clear()
