from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResourceRelationship:
    source_id: str
    target_id: str
    relationship_type: str
    strength: float
    evidence: str = ""
    bidirectional: bool = False

    def to_dict(self) -> Dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.relationship_type,
            "strength": self.strength,
            "evidence": self.evidence[:100],
        }


RELATION_TYPE_WEIGHTS = {
    "uses": 0.9,
    "implements": 0.85,
    "extends": 0.8,
    "evaluates": 0.75,
    "references": 0.7,
    "complements": 0.6,
    "contrasts": 0.5,
    "related_to": 0.4,
}


class ResourceRelationshipBuilder:
    def __init__(self, metadata_store=None):
        from .resource_metadata_store import ResourceMetadataStore
        self._store = metadata_store or ResourceMetadataStore()
        self._relationships: List[ResourceRelationship] = []

    def build_from_analyses(self, analyses: Dict[str, object]) -> List[ResourceRelationship]:
        rels = []
        paths = list(analyses.keys())
        for i, path_a in enumerate(paths):
            for path_b in paths[i + 1:]:
                meta_a = self._store.get_by_path(path_a)
                meta_b = self._store.get_by_path(path_b)
                if not meta_a or not meta_b:
                    continue
                domain_rel = self._check_domain_relationship(meta_a, meta_b)
                if domain_rel:
                    rels.append(domain_rel)
                tech_rel = self._check_technology_relationship(meta_a, meta_b)
                if tech_rel:
                    rels.append(tech_rel)
                ref_rel = self._check_reference_relationship(meta_a, meta_b)
                if ref_rel:
                    rels.append(ref_rel)
                type_rel = self._check_type_complement(meta_a, meta_b)
                if type_rel:
                    rels.append(type_rel)
                algorithm_overlap = self._check_algorithm_overlap(meta_a, meta_b)
                if algorithm_overlap:
                    rels.append(algorithm_overlap)
        self._relationships.extend(rels)
        logger.info(f"Built {len(rels)} resource relationships from {len(analyses)} analyses")
        return rels

    def _check_domain_relationship(self, a, b) -> Optional[ResourceRelationship]:
        if a.domain == b.domain:
            return ResourceRelationship(
                source_id=a.resource_id,
                target_id=b.resource_id,
                relationship_type="related_to",
                strength=0.6,
                evidence=f"Same domain: {a.domain}",
            )
        return None

    def _check_technology_relationship(self, a, b) -> Optional[ResourceRelationship]:
        a_techs = set(t.lower() for t in a.technologies)
        b_techs = set(t.lower() for t in b.technologies)
        common = a_techs & b_techs
        if common:
            return ResourceRelationship(
                source_id=a.resource_id,
                target_id=b.resource_id,
                relationship_type="uses",
                strength=0.8,
                evidence=f"Shared technologies: {', '.join(list(common)[:3])}",
            )
        return None

    def _check_reference_relationship(self, a, b) -> Optional[ResourceRelationship]:
        name_a = a.file_name.lower().replace(".", " ").replace("_", " ").replace("-", " ")[:30]
        name_b = b.file_name.lower().replace(".", " ").replace("_", " ").replace("-", " ")[:30]
        words_a = set(name_a.split())
        words_b = set(name_b.split())
        common = words_a & words_b
        if len(common) >= 2:
            return ResourceRelationship(
                source_id=a.resource_id,
                target_id=b.resource_id,
                relationship_type="references",
                strength=0.7,
                evidence=f"Name overlap: {', '.join(common)}",
            )
        return None

    def _check_type_complement(self, a, b) -> Optional[ResourceRelationship]:
        type_pairs = {
            ("source_code", "pdf"): "implements",
            ("source_code", "docx"): "implements",
            ("pdf", "xlsx"): "evaluates",
            ("docx", "xlsx"): "evaluates",
            ("pdf", "csv"): "evaluates",
            ("docx", "csv"): "evaluates",
            ("source_code", "csv"): "uses",
            ("source_code", "xlsx"): "uses",
            ("markdown", "source_code"): "extends",
        }
        pair = (a.resource_type, b.resource_type)
        reverse_pair = (b.resource_type, a.resource_type)
        if pair in type_pairs:
            return ResourceRelationship(
                source_id=a.resource_id,
                target_id=b.resource_id,
                relationship_type=type_pairs[pair],
                strength=0.75,
                evidence=f"{a.resource_type} -> {b.resource_type} ({type_pairs[pair]})",
            )
        if reverse_pair in type_pairs:
            return ResourceRelationship(
                source_id=b.resource_id,
                target_id=a.resource_id,
                relationship_type=type_pairs[reverse_pair],
                strength=0.75,
                evidence=f"{b.resource_type} -> {a.resource_type} ({type_pairs[reverse_pair]})",
            )
        return None

    def _check_algorithm_overlap(self, a, b) -> Optional[ResourceRelationship]:
        a_algs = set(al.lower() for al in a.algorithms)
        b_algs = set(al.lower() for al in b.algorithms)
        common = a_algs & b_algs
        if common:
            return ResourceRelationship(
                source_id=a.resource_id,
                target_id=b.resource_id,
                relationship_type="related_to",
                strength=0.85,
                evidence=f"Shared algorithms: {', '.join(list(common)[:3])}",
            )
        return None

    def get_all_relationships(self) -> List[ResourceRelationship]:
        return list(self._relationships)

    def get_relationships_for(self, resource_id: str) -> List[ResourceRelationship]:
        return [
            r for r in self._relationships
            if r.source_id == resource_id or r.target_id == resource_id
        ]

    def get_relationship_graph(self) -> Dict:
        nodes = set()
        edges = []
        for r in self._relationships:
            nodes.add(r.source_id)
            nodes.add(r.target_id)
            edges.append({
                "source": r.source_id,
                "target": r.target_id,
                "type": r.relationship_type,
                "strength": r.strength,
            })
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": list(nodes),
            "edges": edges,
        }

    def reset(self):
        self._relationships.clear()
