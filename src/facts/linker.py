from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from src.core.logger import get_logger
from .models import Fact, FactType

logger = get_logger(__name__)


class LinkType(Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    RELATED_TO = "related_to"
    PART_OF = "part_of"
    EVALUATES = "evaluates"
    IMPLEMENTS = "implements"
    SAME_AS = "same_as"


@dataclass
class FactLink:
    source_id: str
    target_id: str
    link_type: LinkType
    strength: float
    evidence: str = ""

    def to_dict(self) -> Dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.link_type.value,
            "strength": self.strength,
        }


LINK_RULES: Dict[Tuple[FactType, FactType], List[LinkType]] = {
    (FactType.ALGORITHM, FactType.TECHNOLOGY): [LinkType.IMPLEMENTS],
    (FactType.ALGORITHM, FactType.DATASET): [LinkType.EVALUATES],
    (FactType.METRIC, FactType.RESULT): [LinkType.SUPPORTS],
    (FactType.DATASET, FactType.METRIC): [LinkType.EVALUATES],
    (FactType.OBJECTIVE, FactType.RESULT): [LinkType.EXTENDS],
    (FactType.ARCHITECTURE, FactType.ALGORITHM): [LinkType.PART_OF],
    (FactType.ARCHITECTURE, FactType.TECHNOLOGY): [LinkType.IMPLEMENTS],
    (FactType.REQUIREMENT, FactType.ARCHITECTURE): [LinkType.DEPENDS_ON],
    (FactType.REQUIREMENT, FactType.TECHNOLOGY): [LinkType.DEPENDS_ON],
    (FactType.CITATION, FactType.ALGORITHM): [LinkType.REFERENCES],
    (FactType.CITATION, FactType.DATASET): [LinkType.REFERENCES],
    (FactType.CITATION, FactType.METHODOLOGY): [LinkType.REFERENCES],
}


class FactLinker:
    def __init__(self):
        self._links: List[FactLink] = []

    def link_facts(self, facts: List[Fact]) -> List[FactLink]:
        links = []

        links.extend(self._link_by_type_rules(facts))
        links.extend(self._link_by_concept_overlap(facts))
        links.extend(self._link_by_value_similarity(facts))
        links.extend(self._link_by_resource_proximity(facts))

        deduplicated = self._deduplicate_links(links)
        self._links.extend(deduplicated)

        for link in deduplicated:
            self._update_fact_relations(facts, link)

        logger.info(f"Created {len(deduplicated)} fact links from {len(facts)} facts")
        return deduplicated

    def _link_by_type_rules(self, facts: List[Fact]) -> List[FactLink]:
        links = []
        type_groups: Dict[FactType, List[Fact]] = {}
        for fact in facts:
            type_groups.setdefault(fact.fact_type, []).append(fact)

        for (src_type, tgt_type), link_types in LINK_RULES.items():
            src_facts = type_groups.get(src_type, [])
            tgt_facts = type_groups.get(tgt_type, [])
            for sf in src_facts:
                for tf in tgt_facts:
                    if sf.fact_id == tf.fact_id:
                        continue
                    for lt in link_types:
                        link = FactLink(
                            source_id=sf.fact_id,
                            target_id=tf.fact_id,
                            link_type=lt,
                            strength=0.7,
                            evidence=f"{sf.fact_type.value} -> {tf.fact_type.value} ({lt.value})",
                        )
                        links.append(link)
        return links

    def _link_by_concept_overlap(self, facts: List[Fact]) -> List[FactLink]:
        links = []
        for i, fa in enumerate(facts):
            for fb in facts[i + 1:]:
                if fa.fact_id == fb.fact_id:
                    continue
                common = set(c.lower() for c in fa.concepts) & set(c.lower() for c in fb.concepts)
                if len(common) >= 2:
                    links.append(FactLink(
                        source_id=fa.fact_id,
                        target_id=fb.fact_id,
                        link_type=LinkType.RELATED_TO,
                        strength=0.5 + 0.1 * len(common),
                        evidence=f"Shared concepts: {', '.join(list(common)[:3])}",
                    ))
        return links

    def _link_by_value_similarity(self, facts: List[Fact]) -> List[FactLink]:
        links = []
        for i, fa in enumerate(facts):
            for fb in facts[i + 1:]:
                if fa.fact_id == fb.fact_id:
                    continue
                if fa.fact_type != fb.fact_type:
                    continue
                a_words = set(fa.normalized_value.split())
                b_words = set(fb.normalized_value.split())
                if not a_words or not b_words:
                    continue
                intersection = a_words & b_words
                union = a_words | b_words
                jaccard = len(intersection) / len(union)
                if jaccard > 0.6:
                    links.append(FactLink(
                        source_id=fa.fact_id,
                        target_id=fb.fact_id,
                        link_type=LinkType.SAME_AS,
                        strength=round(jaccard, 2),
                        evidence=f"Value similarity: {jaccard:.2f}",
                    ))
        return links

    def _link_by_resource_proximity(self, facts: List[Fact]) -> List[FactLink]:
        links = []
        resource_groups: Dict[str, List[Fact]] = {}
        for fact in facts:
            rid = fact.source.resource_id
            if rid:
                resource_groups.setdefault(rid, []).append(fact)

        for rid, group in resource_groups.items():
            for i, fa in enumerate(group):
                for fb in group[i + 1:]:
                    if fa.fact_id == fb.fact_id:
                        continue
                    if fa.fact_type != fb.fact_type:
                        link = FactLink(
                            source_id=fa.fact_id,
                            target_id=fb.fact_id,
                            link_type=LinkType.RELATED_TO,
                            strength=0.4,
                            evidence=f"Same resource: {rid}",
                        )
                        links.append(link)
        return links

    def _deduplicate_links(self, links: List[FactLink]) -> List[FactLink]:
        seen: Set[Tuple[str, str, str]] = set()
        unique = []
        for link in sorted(links, key=lambda l: -l.strength):
            key = (link.source_id, link.target_id, link.link_type.value)
            reverse_key = (link.target_id, link.source_id, link.link_type.value)
            if key not in seen and reverse_key not in seen:
                seen.add(key)
                unique.append(link)
        return unique

    def _update_fact_relations(self, facts: List[Fact], link: FactLink):
        fact_map = {f.fact_id: f for f in facts}
        src = fact_map.get(link.source_id)
        tgt = fact_map.get(link.target_id)
        if src and tgt:
            if tgt.fact_id not in src.related_fact_ids:
                src.related_fact_ids.append(tgt.fact_id)
            if link.link_type in (LinkType.SUPPORTS, LinkType.EXTENDS, LinkType.PART_OF):
                if src.fact_id not in tgt.related_fact_ids:
                    tgt.related_fact_ids.append(src.fact_id)

    def get_links_for(self, fact_id: str) -> List[FactLink]:
        return [
            l for l in self._links
            if l.source_id == fact_id or l.target_id == fact_id
        ]

    def get_links_by_type(self, link_type: LinkType) -> List[FactLink]:
        return [l for l in self._links if l.link_type == link_type]

    def get_all_links(self) -> List[FactLink]:
        return list(self._links)

    def get_link_graph(self) -> Dict:
        nodes = set()
        edges = []
        for link in self._links:
            nodes.add(link.source_id)
            nodes.add(link.target_id)
            edges.append({
                "source": link.source_id,
                "target": link.target_id,
                "type": link.link_type.value,
                "strength": link.strength,
            })
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "edges": edges,
        }

    def get_statistics(self) -> Dict:
        type_counts: Dict[str, int] = {}
        for link in self._links:
            type_counts[link.link_type.value] = type_counts.get(link.link_type.value, 0) + 1
        return {
            "total_links": len(self._links),
            "by_type": type_counts,
        }

    def reset(self):
        self._links.clear()
