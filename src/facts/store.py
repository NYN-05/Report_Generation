from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from src.core.logger import get_logger
from .models import Fact, FactType, SourceReference

logger = get_logger(__name__)


@dataclass
class FactStoreConfig:
    persist_path: Optional[str] = None
    auto_persist: bool = False
    max_facts: int = 100000
    deduplicate_on_insert: bool = True
    enable_indexing: bool = True


class FactStore:
    def __init__(self, config: Optional[FactStoreConfig] = None):
        self._config = config or FactStoreConfig()
        self._facts: Dict[str, Fact] = {}
        self._type_index: Dict[FactType, Set[str]] = {ft: set() for ft in FactType}
        self._resource_index: Dict[str, Set[str]] = {}
        self._concept_index: Dict[str, Set[str]] = {}

    def add_fact(self, fact: Fact) -> bool:
        if fact.fact_id in self._facts:
            return False
        if len(self._facts) >= self._config.max_facts:
            logger.warning(f"Fact store at capacity ({self._config.max_facts})")
            return False

        if self._config.deduplicate_on_insert:
            for existing in self._facts.values():
                if self._is_duplicate(fact, existing):
                    return False

        self._facts[fact.fact_id] = fact
        self._type_index[fact.fact_type].add(fact.fact_id)

        res_id = fact.source.resource_id
        if res_id:
            self._resource_index.setdefault(res_id, set()).add(fact.fact_id)

        for concept in fact.concepts:
            concept_lower = concept.lower()
            self._concept_index.setdefault(concept_lower, set()).add(fact.fact_id)

        if self._config.auto_persist:
            self._persist()
        return True

    def add_facts(self, facts: List[Fact]) -> int:
        added = 0
        for fact in facts:
            if self.add_fact(fact):
                added += 1
        logger.info(f"Added {added}/{len(facts)} facts to store")
        return added

    def get(self, fact_id: str) -> Optional[Fact]:
        return self._facts.get(fact_id)

    def get_by_type(self, fact_type: FactType) -> List[Fact]:
        ids = self._type_index.get(fact_type, set())
        return [self._facts[fid] for fid in ids if fid in self._facts]

    def get_by_resource(self, resource_id: str) -> List[Fact]:
        ids = self._resource_index.get(resource_id, set())
        return [self._facts[fid] for fid in ids if fid in self._facts]

    def get_by_concept(self, concept: str) -> List[Fact]:
        ids = self._concept_index.get(concept.lower(), set())
        return [self._facts[fid] for fid in ids if fid in self._facts]

    def get_by_confidence(self, min_confidence: float = 0.7) -> List[Fact]:
        return [f for f in self._facts.values() if f.confidence >= min_confidence]

    def search(self, query: str) -> List[Fact]:
        query_lower = query.lower()
        results = []
        for fact in self._facts.values():
            if query_lower in fact.value.lower() or query_lower in fact.normalized_value:
                results.append(fact)
            elif any(query_lower in c.lower() for c in fact.concepts):
                results.append(fact)
        return results[:50]

    def search_by_value(self, value: str) -> List[Fact]:
        value_lower = value.lower().strip()
        return [
            f for f in self._facts.values()
            if value_lower in f.normalized_value
        ]

    def remove(self, fact_id: str) -> bool:
        fact = self._facts.pop(fact_id, None)
        if not fact:
            return False
        self._type_index[fact.fact_type].discard(fact_id)
        res_id = fact.source.resource_id
        if res_id and res_id in self._resource_index:
            self._resource_index[res_id].discard(fact_id)
        for concept in fact.concepts:
            cl = concept.lower()
            if cl in self._concept_index:
                self._concept_index[cl].discard(fact_id)
        return True

    def deactivate_fact(self, fact_id: str) -> bool:
        fact = self._facts.get(fact_id)
        if not fact:
            return False
        fact.deactivate()
        return True

    def count(self) -> Dict[str, int]:
        return {
            "total": len(self._facts),
            "by_type": {ft.value: len(ids) for ft, ids in self._type_index.items()},
        }

    def get_all_facts(self) -> List[Fact]:
        return list(self._facts.values())

    def get_statistics(self) -> Dict:
        total = len(self._facts)
        if total == 0:
            return {"total": 0, "by_type": {}, "avg_confidence": 0}
        avg_conf = sum(f.confidence for f in self._facts.values()) / total
        return {
            "total": total,
            "by_type": {ft.value: len(ids) for ft, ids in self._type_index.items()},
            "by_resource": {
                rid: len(ids) for rid, ids in self._resource_index.items()
            },
            "avg_confidence": round(avg_conf, 3),
            "unique_concepts": len(self._concept_index),
        }

    def clear(self):
        self._facts.clear()
        self._type_index = {ft: set() for ft in FactType}
        self._resource_index.clear()
        self._concept_index.clear()

    def _is_duplicate(self, a: Fact, b: Fact, threshold: float = 0.8) -> bool:
        if a.fact_type != b.fact_type:
            return False
        a_words = set(a.normalized_value.split())
        b_words = set(b.normalized_value.split())
        if not a_words or not b_words:
            return False
        intersection = a_words & b_words
        union = a_words | b_words
        return len(intersection) / len(union) >= threshold

    def _persist(self):
        if not self._config.persist_path:
            return
        path = Path(self._config.persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "facts": [f.to_dict() for f in self._facts.values()],
            "timestamp": datetime.now().isoformat(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str) -> int:
        path = Path(path)
        if not path.exists():
            logger.warning(f"Persist file not found: {path}")
            return 0
        with open(path) as f:
            data = json.load(f)
        count = 0
        for fact_data in data.get("facts", []):
            fact = self._dict_to_fact(fact_data)
            if fact and self.add_fact(fact):
                count += 1
        logger.info(f"Loaded {count} facts from {path}")
        return count

    def _dict_to_fact(self, data: Dict) -> Optional[Fact]:
        try:
            ft = FactType(data["fact_type"])
            src = SourceReference(**data["source"])
            return Fact(
                fact_id=data["fact_id"],
                fact_type=ft,
                value=data["value"],
                normalized_value=data.get("normalized_value", data["value"]),
                confidence=data["confidence"],
                source=src,
                concepts=data.get("concepts", []),
                related_fact_ids=data.get("related_fact_ids", []),
            )
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to reconstruct fact: {e}")
            return None
