from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from src.core.logger import get_logger

logger = get_logger(__name__)


class ConceptNode:
    def __init__(self, name: str, category: str = "general",
                 frequency: int = 1, sources: Optional[List[str]] = None):
        self.name = name
        self.category = category
        self.frequency = frequency
        self.sources = sources or []
        self.related: Dict[str, float] = {}

    def add_related(self, concept_name: str, strength: float):
        existing = self.related.get(concept_name, 0)
        self.related[concept_name] = max(existing, strength)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "category": self.category,
            "frequency": self.frequency,
            "sources": self.sources,
            "related_count": len(self.related),
        }


class KnowledgeGraph:
    def __init__(self):
        self.nodes: Dict[str, ConceptNode] = {}
        self.edges: List[Tuple[str, str, float]] = []

    def add_concept(self, name: str, category: str = "general",
                    source: str = "") -> ConceptNode:
        if name not in self.nodes:
            self.nodes[name] = ConceptNode(name, category, sources=[source] if source else [])
        else:
            self.nodes[name].frequency += 1
            if source and source not in self.nodes[name].sources:
                self.nodes[name].sources.append(source)
        return self.nodes[name]

    def add_relationship(self, concept_a: str, concept_b: str, strength: float):
        if concept_a in self.nodes and concept_b in self.nodes:
            self.nodes[concept_a].add_related(concept_b, strength)
            self.nodes[concept_b].add_related(concept_a, strength)
            self.edges.append((concept_a, concept_b, strength))

    def get_related(self, concept: str, min_strength: float = 0.0) -> List[Tuple[str, float]]:
        node = self.nodes.get(concept)
        if not node:
            return []
        return [(c, s) for c, s in node.related.items() if s >= min_strength]

    def get_central_concepts(self, top_n: int = 10) -> List[Tuple[str, int]]:
        scored = [(n.name, n.frequency + len(n.related))
                  for n in self.nodes.values()]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_n]

    def to_dict(self) -> Dict:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "central_concepts": self.get_central_concepts(5),
            "nodes": {n: nd.to_dict() for n, nd in self.nodes.items()},
        }


class KnowledgeGraphBuilder:
    def __init__(self):
        self.graph = KnowledgeGraph()

    def build_from_chunks(self, chunks: List[Dict]) -> KnowledgeGraph:
        for chunk in chunks:
            text = chunk.get("text", "")
            meta = chunk.get("metadata", {})
            source = meta.get("source", "")
            concepts = self._extract_concepts(text)
            for concept in concepts:
                self.graph.add_concept(concept["name"], concept["category"], source)
            for i, ca in enumerate(concepts):
                for cb in concepts[i + 1:]:
                    co_occur = self._compute_cooccurrence_strength(
                        ca["name"], cb["name"], text
                    )
                    if co_occur > 0.1:
                        self.graph.add_relationship(ca["name"], cb["name"], co_occur)
        logger.info(
            f"KnowledgeGraph built: {len(self.graph.nodes)} concepts, "
            f"{len(self.graph.edges)} relationships"
        )
        return self.graph

    def _extract_concepts(self, text: str) -> List[Dict]:
        import re
        concepts = []
        seen = set()
        patterns = [
            r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,3}\b',
            r'\b[A-Z]{2,}(?:\s+[A-Z]{2,})?\b',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                name = match.group(0).strip()
                if name.lower() in seen or len(name) < 4:
                    continue
                seen.add(name.lower())
                category = self._categorize(name, text)
                concepts.append({"name": name, "category": category})
        return concepts

    def _categorize(self, name: str, context: str) -> str:
        sl = context.lower()
        if any(w in sl for w in ["algorithm", "method", "technique"]):
            return "technique"
        if any(w in sl for w in ["dataset", "data", "corpus"]):
            return "dataset"
        if any(w in sl for w in ["system", "platform", "tool", "framework"]):
            return "system"
        if any(w in sl for w in ["metric", "evaluation", "score", "accuracy"]):
            return "metric"
        return "concept"

    def _compute_cooccurrence_strength(self, a: str, b: str, text: str) -> float:
        import re
        a_positions = [m.start() for m in re.finditer(re.escape(a), text)]
        b_positions = [m.start() for m in re.finditer(re.escape(b), text)]
        if not a_positions or not b_positions:
            return 0.0
        min_dist = min(abs(pa - pb) for pa in a_positions for pb in b_positions)
        return round(max(0.0, 1.0 - min_dist / len(text)), 2)

    def reset(self):
        self.graph = KnowledgeGraph()
