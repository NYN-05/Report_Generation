from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger
from .fact_extractor import AtomicFact

logger = get_logger(__name__)


class EvidenceGroup:
    def __init__(self, claim: str, facts: List[AtomicFact],
                 section_type: str = "", strength: float = 0.0):
        self.claim = claim
        self.facts = facts
        self.section_type = section_type
        self.strength = strength
        self.sources = list(set(
            f.source_meta.get("source", "unknown") for f in facts
        ))

    def to_dict(self) -> Dict:
        return {
            "claim": self.claim,
            "fact_count": len(self.facts),
            "strength": self.strength,
            "sources": self.sources,
            "section_type": self.section_type,
            "facts": [f.to_dict() for f in self.facts],
        }


class EvidenceBuilder:
    def __init__(self):
        self._groups: List[EvidenceGroup] = []

    def build_from_facts(self, facts: List[AtomicFact],
                         section_type: str) -> List[EvidenceGroup]:
        if not facts:
            return []
        grouped = self._group_by_claim(facts)
        groups = []
        for claim, claim_facts in grouped:
            strength = self._compute_group_strength(claim_facts)
            group = EvidenceGroup(
                claim=claim,
                facts=claim_facts,
                section_type=section_type,
                strength=strength,
            )
            groups.append(group)
        self._groups.extend(groups)
        logger.info(
            f"Built {len(groups)} evidence groups from {len(facts)} facts "
            f"for section '{section_type}'"
        )
        return groups

    def build_claim_evidence_map(self, facts: List[AtomicFact],
                                  section_type: str) -> Dict[str, List[AtomicFact]]:
        grouped = self._group_by_claim(facts)
        return {claim: claim_facts for claim, claim_facts in grouped}

    def _group_by_claim(self, facts: List[AtomicFact]) -> List[Tuple[str, List[AtomicFact]]]:
        from collections import defaultdict
        category_map: Dict[str, List[AtomicFact]] = defaultdict(list)
        for fact in facts:
            category_map[fact.category].append(fact)
        result = []
        for cat, cat_facts in category_map.items():
            result.append((cat, cat_facts))
        return result

    def _compute_group_strength(self, facts: List[AtomicFact]) -> float:
        if not facts:
            return 0.0
        avg_conf = sum(f.confidence for f in facts) / len(facts)
        coverage = min(len(facts) / 5.0, 1.0)
        source_diversity = min(len(set(f.source_meta.get("source", "") for f in facts)) / 3.0, 1.0)
        return round(avg_conf * 0.5 + coverage * 0.25 + source_diversity * 0.25, 2)

    def get_strongest_evidence(self, top_n: int = 3) -> List[EvidenceGroup]:
        sorted_groups = sorted(self._groups, key=lambda g: -g.strength)
        return sorted_groups[:top_n]

    def get_groups_for_section(self, section_type: str) -> List[EvidenceGroup]:
        return [g for g in self._groups if g.section_type == section_type]

    def reset(self):
        self._groups.clear()
