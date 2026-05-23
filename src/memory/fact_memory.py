from typing import Dict, List, Optional, Set, Tuple
import time
from src.core.logger import get_logger

logger = get_logger(__name__)


class FactMemory:
    def __init__(self, max_facts: int = 200):
        self._facts: Dict[str, Dict] = {}
        self._max_facts = max_facts
        self._section_fact_map: Dict[str, List[str]] = {}

    def register_fact(self, fact_text: str, section_type: str,
                       source: str = "", confidence: float = 0.5,
                       concepts: Optional[List[str]] = None) -> str:
        fact_key = self._make_key(fact_text)
        if fact_key not in self._facts:
            self._facts[fact_key] = {
                "text": fact_text,
                "first_seen": section_type,
                "sections": [section_type],
                "source": source,
                "confidence": confidence,
                "concepts": concepts or [],
                "times_cited": 1,
                "timestamp": time.time(),
            }
        else:
            if section_type not in self._facts[fact_key]["sections"]:
                self._facts[fact_key]["sections"].append(section_type)
            self._facts[fact_key]["times_cited"] += 1
            self._facts[fact_key]["timestamp"] = time.time()
            if confidence > self._facts[fact_key]["confidence"]:
                self._facts[fact_key]["confidence"] = confidence
        if section_type not in self._section_fact_map:
            self._section_fact_map[section_type] = []
        if fact_key not in self._section_fact_map[section_type]:
            self._section_fact_map[section_type].append(fact_key)
        if len(self._facts) > self._max_facts:
            oldest = min(self._facts, key=lambda k: self._facts[k]["timestamp"])
            del self._facts[oldest]
        return fact_key

    def register_section_facts(self, facts: List, section_type: str):
        for fact in facts:
            text = fact.text if hasattr(fact, "text") else str(fact)
            source = fact.source_meta.get("source", "") if hasattr(fact, "source_meta") else ""
            conf = fact.confidence if hasattr(fact, "confidence") else 0.5
            concepts = fact.concepts if hasattr(fact, "concepts") else []
            self.register_fact(text, section_type, source, conf, concepts)

    def get_facts_for_section(self, section_type: str) -> List[Dict]:
        fact_keys = self._section_fact_map.get(section_type, [])
        return [self._facts[k] for k in fact_keys if k in self._facts]

    def check_fact_overlap(self, text: str, threshold: float = 0.3) -> List[Tuple[str, str, float]]:
        text_lower = text.lower()
        text_words = set(text_lower.split())
        overlaps = []
        for fact_key, fact_data in self._facts.items():
            fact_lower = fact_data["text"].lower()
            fact_words = set(fact_lower.split())
            if not fact_words or not text_words:
                continue
            overlap = len(text_words & fact_words) / len(text_words | fact_words)
            if overlap > threshold:
                overlaps.append((
                    fact_data["first_seen"],
                    fact_data["text"][:100],
                    overlap,
                ))
        overlaps.sort(key=lambda x: -x[2])
        return overlaps[:5]

    def consolidate_duplicates(self, threshold: float = 0.7) -> int:
        keys = list(self._facts.keys())
        merged = 0
        for i, ka in enumerate(keys):
            if ka not in self._facts:
                continue
            for kb in keys[i + 1:]:
                if kb not in self._facts:
                    continue
                a_text = self._facts[ka]["text"].lower()
                b_text = self._facts[kb]["text"].lower()
                a_words = set(a_text.split())
                b_words = set(b_text.split())
                sim = len(a_words & b_words) / max(len(a_words | b_words), 1)
                if sim > threshold:
                    self._facts[ka]["times_cited"] += self._facts[kb]["times_cited"]
                    self._facts[ka]["sections"].extend(
                        s for s in self._facts[kb]["sections"]
                        if s not in self._facts[ka]["sections"]
                    )
                    del self._facts[kb]
                    merged += 1
        if merged:
            logger.info(f"Consolidated {merged} duplicate facts")
        return merged

    def stats(self) -> Dict:
        return {
            "total_facts": len(self._facts),
            "sections_with_facts": len(self._section_fact_map),
            "avg_citations": sum(f["times_cited"] for f in self._facts.values()) / max(len(self._facts), 1),
            "avg_confidence": sum(f["confidence"] for f in self._facts.values()) / max(len(self._facts), 1),
        }

    def _make_key(self, text: str) -> str:
        return text.lower().strip()[:100]

    def clear(self):
        self._facts.clear()
        self._section_fact_map.clear()
