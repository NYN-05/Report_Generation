from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
import re
from src.core.logger import get_logger
from .knowledge_graph import ProjectKnowledgeGraph as KnowledgeGraph

logger = get_logger(__name__)


class Relationship:
    def __init__(self, source: str, target: str, relation_type: str,
                 strength: float, evidence: Optional[str] = None):
        self.source = source
        self.target = target
        self.relation_type = relation_type
        self.strength = strength
        self.evidence = evidence

    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.relation_type,
            "strength": self.strength,
        }


PATTERNS = {
    "uses": r'\b(?:uses?|utilizes?|employs?|applies?|leverages?)\b',
    "extends": r'\b(?:extends?|builds?(?:\s+on|upon)|improves?|enhances?)\b',
    "compares": r'\b(?:compares?|contrasts?|outperforms?|exceeds?)\b',
    "part_of": r'\b(?:comprises?|consists?(?:\s+of)|includes?|contains?)\b',
    "leads_to": r'\b(?:leads?\s+to|results?\s+in|causes?|produces?|yields?)\b',
    "related_to": r'\b(?:relates?\s+to|associated?\s+with|connected?\s+to)\b',
}


class RelationshipExtractor:
    def __init__(self):
        self._relationships: List[Relationship] = []

    def extract_from_chunks(self, chunks: List[Dict]) -> List[Relationship]:
        rels = []
        for chunk in chunks:
            chunk_rels = self._extract_chunk_relationships(chunk)
            rels.extend(chunk_rels)
        self._relationships.extend(rels)
        logger.info(f"Extracted {len(rels)} relationships from {len(chunks)} chunks")
        return rels

    def extract_from_graph(self, graph: KnowledgeGraph) -> List[Relationship]:
        rels = []
        for node_a in graph.nodes:
            for node_b, strength in graph.get_related(node_a):
                if (node_a, node_b) not in {(r.source, r.target) for r in rels}:
                    rel = Relationship(
                        source=node_a,
                        target=node_b,
                        relation_type="related_to",
                        strength=strength,
                    )
                    rels.append(rel)
        self._relationships.extend(rels)
        logger.info(f"Extracted {len(rels)} graph-based relationships")
        return rels

    def _extract_chunk_relationships(self, chunk: Dict) -> List[Relationship]:
        text = chunk.get("text", "")
        if not text:
            return []
        rels = []
        concepts = self._find_concepts_in_text(text)
        for rel_type, pattern in PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                pos = match.start()
                before = text[max(0, pos - 80):pos]
                after = text[pos + len(match.group()):pos + 80]
                source = self._find_nearest_concept(concepts, before)
                target = self._find_nearest_concept(concepts, after, reverse=False)
                if source and target and source != target:
                    rel = Relationship(
                        source=source,
                        target=target,
                        relation_type=rel_type,
                        strength=0.6,
                        evidence=match.group(),
                    )
                    rels.append(rel)
        return rels

    def _find_concepts_in_text(self, text: str) -> List[Dict]:
        concepts = []
        seen = set()
        for match in re.finditer(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2}\b', text):
            name = match.group(0).strip()
            if name.lower() in seen or len(name) < 4:
                continue
            seen.add(name.lower())
            concepts.append({"name": name, "position": match.start()})
        return concepts

    def _find_nearest_concept(self, concepts: List[Dict], text: str,
                               reverse: bool = True) -> Optional[str]:
        if not concepts:
            for match in re.finditer(r'\b[A-Z][a-z]{2,}\b', text):
                return match.group(0)
            return None
        scored = []
        for c in concepts:
            if c["name"].lower() in text.lower():
                pos = text.lower().index(c["name"].lower())
                dist = pos if reverse else len(text) - pos
                scored.append((dist, c["name"]))
        if scored:
            scored.sort(key=lambda x: x[0])
            return scored[0][1]
        return None

    def get_relationships(self, rel_type: Optional[str] = None) -> List[Relationship]:
        if rel_type:
            return [r for r in self._relationships if r.relation_type == rel_type]
        return list(self._relationships)

    def get_all(self) -> List[Dict]:
        return [r.to_dict() for r in self._relationships]

    def reset(self):
        self._relationships.clear()
