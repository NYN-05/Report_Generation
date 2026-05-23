from typing import Dict, List, Optional, Set, Tuple
from src.core.logger import get_logger
from .knowledge_graph import KnowledgeGraph

logger = get_logger(__name__)


SECTION_CONCEPT_MAP = {
    "introduction": ["background", "problem", "motivation", "scope", "objective", "challenge"],
    "literature_review": ["existing approach", "related work", "state of art", "limitation", "gap"],
    "methodology": ["architecture", "algorithm", "design", "method", "framework", "technique"],
    "implementation": ["tool", "configuration", "setup", "environment", "parameter"],
    "results": ["experiment", "result", "performance", "evaluation", "metric", "finding"],
    "discussion": ["analysis", "interpretation", "comparison", "implication", "limitation"],
    "conclusion": ["summary", "contribution", "future work", "significance"],
}


class ConceptMapper:
    def __init__(self):
        self._section_concepts: Dict[str, List[str]] = {}

    def map_concepts_to_sections(self, graph: KnowledgeGraph) -> Dict[str, List[str]]:
        mapping: Dict[str, List[str]] = {}
        all_concepts = list(graph.nodes.keys())
        for section_type, target_concepts in SECTION_CONCEPT_MAP.items():
            matched = self._match_concepts(all_concepts, target_concepts)
            mapping[section_type] = matched
        self._section_concepts = mapping
        total = sum(len(v) for v in mapping.values())
        logger.info(f"Mapped {total} concept assignments across {len(mapping)} sections")
        return mapping

    def _match_concepts(self, available: List[str], targets: List[str]) -> List[str]:
        matched = []
        for target in targets:
            target_lower = target.lower()
            best_match = None
            best_score = 0.0
            for avail in available:
                avail_lower = avail.lower()
                score = self._compute_semantic_overlap(avail_lower, target_lower)
                if score > best_score:
                    best_score = score
                    best_match = avail
            if best_match and best_score > 0.2:
                matched.append(best_match)
        return matched

    def _compute_semantic_overlap(self, a: str, b: str) -> float:
        a_words = set(a.split())
        b_words = set(b.split())
        if not a_words or not b_words:
            return 0.0
        intersection = a_words & b_words
        return len(intersection) / max(len(a_words | b_words), 1)

    def get_concepts_for_section(self, section_type: str) -> List[str]:
        return self._section_concepts.get(section_type, [])

    def get_all_mapped(self) -> Dict[str, List[str]]:
        return dict(self._section_concepts)

    def reset(self):
        self._section_concepts.clear()
