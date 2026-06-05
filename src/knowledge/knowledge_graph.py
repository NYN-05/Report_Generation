from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
from src.core.logger import get_logger


logger = get_logger(__name__)


class NodeType(Enum):
    PROJECT = "Project"
    OBJECTIVE = "Objective"
    DATASET = "Dataset"
    TECHNOLOGY = "Technology"
    ALGORITHM = "Algorithm"
    ARCHITECTURE = "Architecture"
    MODULE = "Module"
    METRIC = "Metric"
    RESULT = "Result"
    REFERENCE = "Reference"
    REQUIREMENT = "Requirement"
    GENERAL = "General"


class RelationType(Enum):
    USES = "uses"
    IMPLEMENTS = "implements"
    EVALUATES = "evaluates"
    DEPENDS_ON = "depends_on"
    PRODUCES = "produces"
    REFERENCES = "references"
    ACHIEVES = "achieves"
    MEASURES = "measures"
    EXTENDS = "extends"
    COMPOSES = "composes"
    RELATED_TO = "related_to"


@dataclass
class ProjectNode:
    node_id: str
    name: str
    node_type: NodeType
    fact_ids: List[str] = field(default_factory=list)
    properties: Dict[str, any] = field(default_factory=dict)
    evidence_source: str = ""

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type.value,
            "fact_count": len(self.fact_ids),
            "properties": {
                k: v for k, v in self.properties.items()
                if not isinstance(v, (list, dict)) or len(str(v)) < 100
            },
        }


@dataclass
class ProjectEdge:
    source_id: str
    target_id: str
    relation_type: RelationType
    strength: float = 1.0
    evidence: str = ""

    def to_dict(self) -> Dict:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.relation_type.value,
            "strength": self.strength,
        }


class ProjectKnowledgeGraph:
    def __init__(self):
        self.nodes: Dict[str, ProjectNode] = {}
        self.edges: List[ProjectEdge] = []
        self._type_index: Dict[NodeType, Set[str]] = defaultdict(set)

    def add_node(self, name: str, node_type: NodeType,
                 fact_id: str = "", properties: Optional[Dict] = None) -> ProjectNode:
        node_id = self._make_node_id(name, node_type)
        if node_id in self.nodes:
            existing = self.nodes[node_id]
            if fact_id and fact_id not in existing.fact_ids:
                existing.fact_ids.append(fact_id)
            for k, v in (properties or {}).items():
                if k not in existing.properties:
                    existing.properties[k] = v
            return existing

        node = ProjectNode(
            node_id=node_id,
            name=name,
            node_type=node_type,
            fact_ids=[fact_id] if fact_id else [],
            properties=properties or {},
        )
        self.nodes[node_id] = node
        self._type_index[node_type].add(node_id)
        return node

    def add_fact(self, fact) -> ProjectNode:
        from src.facts.models import FactType as FT
        type_map = {
            FT.OBJECTIVE: NodeType.OBJECTIVE,
            FT.DATASET: NodeType.DATASET,
            FT.ALGORITHM: NodeType.ALGORITHM,
            FT.TECHNOLOGY: NodeType.TECHNOLOGY,
            FT.ARCHITECTURE: NodeType.ARCHITECTURE,
            FT.METRIC: NodeType.METRIC,
            FT.RESULT: NodeType.RESULT,
            FT.CITATION: NodeType.REFERENCE,
            FT.REQUIREMENT: NodeType.REQUIREMENT,
        }
        node_type = type_map.get(fact.fact_type, NodeType.GENERAL)
        value_key = fact.normalized_value[:50] or fact.value[:50]
        return self.add_node(
            name=value_key,
            node_type=node_type,
            fact_id=fact.fact_id,
            properties={
                "confidence": fact.confidence,
                "source": fact.source.file_name,
                "type": fact.fact_type.value,
            },
        )

    def add_relationship(self, source_id: str, target_id: str,
                         relation_type: RelationType, strength: float = 1.0,
                         evidence: str = "") -> Optional[ProjectEdge]:
        if source_id not in self.nodes or target_id not in self.nodes:
            return None
        for existing in self.edges:
            if (existing.source_id == source_id and
                existing.target_id == target_id and
                existing.relation_type == relation_type):
                existing.strength = max(existing.strength, strength)
                return existing
        edge = ProjectEdge(source_id, target_id, relation_type, strength, evidence)
        self.edges.append(edge)
        return edge

    def add_fact_relationship(self, source_fact, target_fact,
                               relation_type: RelationType) -> Optional[ProjectEdge]:
        source_node = self.add_fact(source_fact)
        target_node = self.add_fact(target_fact)
        return self.add_relationship(
            source_id=source_node.node_id,
            target_id=target_node.node_id,
            relation_type=relation_type,
            strength=(source_fact.confidence + target_fact.confidence) / 2,
            evidence=f"{source_fact.fact_type.value} -> {target_fact.fact_type.value}",
        )

    def build_from_facts(self, facts) -> int:
        for fact in facts:
            self.add_fact(fact)

        for i, fa in enumerate(facts):
            for fb in facts[i + 1:]:
                relation = self._infer_relation(fa, fb)
                if relation:
                    self.add_fact_relationship(fa, fb, relation)

        logger.info(
            f"Graph built: {len(self.nodes)} nodes, {len(self.edges)} edges "
            f"from {len(facts)} facts"
        )
        return len(self.nodes)

    def _infer_relation(self, fa, fb) -> Optional[RelationType]:
        from src.facts.models import FactType as FT
        type_pairs = {
            (FT.ALGORITHM, FT.TECHNOLOGY): RelationType.IMPLEMENTS,
            (FT.ALGORITHM, FT.DATASET): RelationType.EVALUATES,
            (FT.OBJECTIVE, FT.ALGORITHM): RelationType.ACHIEVES,
            (FT.OBJECTIVE, FT.RESULT): RelationType.ACHIEVES,
            (FT.METRIC, FT.RESULT): RelationType.MEASURES,
            (FT.ARCHITECTURE, FT.ALGORITHM): RelationType.COMPOSES,
            (FT.ARCHITECTURE, FT.MODULE): RelationType.COMPOSES,
            (FT.DATASET, FT.METRIC): RelationType.EVALUATES,
            (FT.RESULT, FT.METRIC): RelationType.PRODUCES,
            (FT.REQUIREMENT, FT.ARCHITECTURE): RelationType.DEPENDS_ON,
            (FT.CITATION, FT.ALGORITHM): RelationType.REFERENCES,
            (FT.CITATION, FT.DATASET): RelationType.REFERENCES,
        }
        pair = (fa.fact_type, fb.fact_type)
        reverse_pair = (fb.fact_type, fa.fact_type)
        if pair in type_pairs:
            return type_pairs[pair]
        if reverse_pair in type_pairs:
            return type_pairs[reverse_pair]

        common_concepts = set(c.lower() for c in fa.concepts) & set(c.lower() for c in fb.concepts)
        if len(common_concepts) >= 2:
            return RelationType.RELATED_TO
        return None

    def get_node(self, node_id: str) -> Optional[ProjectNode]:
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[ProjectNode]:
        ids = self._type_index.get(node_type, set())
        return [self.nodes[nid] for nid in ids if nid in self.nodes]

    def get_fact_nodes(self) -> List[ProjectNode]:
        return [n for n in self.nodes.values() if n.fact_ids]

    def query_by_relation(self, node_id: str, relation_type: RelationType) -> List[ProjectNode]:
        target_ids = set()
        for edge in self.edges:
            if edge.source_id == node_id and edge.relation_type == relation_type:
                target_ids.add(edge.target_id)
            if edge.target_id == node_id and edge.relation_type == relation_type:
                target_ids.add(edge.source_id)
        return [self.nodes[nid] for nid in target_ids if nid in self.nodes]

    def get_project_context(self, project_name: str = "") -> Dict:
        algorithms = [n.name for n in self.get_nodes_by_type(NodeType.ALGORITHM)]
        datasets = [n.name for n in self.get_nodes_by_type(NodeType.DATASET)]
        technologies = [n.name for n in self.get_nodes_by_type(NodeType.TECHNOLOGY)]
        architectures = [n.name for n in self.get_nodes_by_type(NodeType.ARCHITECTURE)]
        metrics = [n.name for n in self.get_nodes_by_type(NodeType.METRIC)]
        results = [n.name for n in self.get_nodes_by_type(NodeType.RESULT)]
        objectives = [n.name for n in self.get_nodes_by_type(NodeType.OBJECTIVE)]

        return {
            "project": project_name,
            "objectives": objectives[:10],
            "algorithms": algorithms[:10],
            "datasets": datasets[:10],
            "technologies": technologies[:10],
            "architectures": architectures[:5],
            "metrics": metrics[:10],
            "results": results[:10],
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }

    def to_dict(self) -> Dict:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "by_type": {nt.value: len(ids) for nt, ids in self._type_index.items()},
            "edges": [e.to_dict() for e in self.edges[:50]],
            "central_nodes": [
                n.to_dict() for n in sorted(
                    self.nodes.values(),
                    key=lambda x: sum(
                        1 for e in self.edges
                        if e.source_id == x.node_id or e.target_id == x.node_id
                    ),
                    reverse=True,
                )[:10]
            ],
        }

    @staticmethod
    def _make_node_id(name: str, node_type: NodeType) -> str:
        import re
        clean = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower().strip())[:40]
        return f"{node_type.value.lower()}_{clean}"

    def reset(self):
        self.nodes.clear()
        self.edges.clear()
        self._type_index.clear()


# Backward compatibility aliases
class LegacyKnowledgeGraph:
    """Old concept-graph interface. Delegates to ProjectKnowledgeGraph."""
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self._concepts = []

    def to_dict(self) -> Dict:
        return {"node_count": len(self.nodes), "edge_count": len(self.edges),
                "central_concepts": [], "nodes": {}}


class KnowledgeGraphBuilder:
    """Legacy builder interface. Maintains backward compatibility."""
    def __init__(self):
        self.graph = LegacyKnowledgeGraph()

    def build_from_chunks(self, chunks: List[Dict]) -> LegacyKnowledgeGraph:
        logger.warning("KnowledgeGraphBuilder.build_from_chunks is deprecated. Use ProjectKnowledgeGraph.build_from_facts()")
        self.graph = LegacyKnowledgeGraph()
        for chunk in chunks:
            text = chunk.get("text", "")
            meta = chunk.get("metadata", {})
            source = meta.get("source", "")
            concepts = self._extract_concepts(text)
            for c in concepts:
                self.graph.nodes[c["name"]] = {"name": c["name"], "category": c["category"]}
        return self.graph

    def _extract_concepts(self, text: str) -> List[Dict]:
        import re
        concepts = []
        seen = set()
        for match in re.finditer(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,3}\b', text):
            name = match.group(0).strip()
            if name.lower() in seen or len(name) < 4:
                continue
            seen.add(name.lower())
            concepts.append({"name": name, "category": "concept"})
        return concepts

    def reset(self):
        self.graph = LegacyKnowledgeGraph()


KnowledgeGraph = ProjectKnowledgeGraph
