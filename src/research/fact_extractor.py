from typing import Dict, List, Optional, Tuple
import re
from src.core.logger import get_logger

logger = get_logger(__name__)


class AtomicFact:
    def __init__(self, text: str, source_chunk: Dict, confidence: float,
                 category: str = "general", concepts: Optional[List[str]] = None):
        self.text = text
        self.source_chunk = source_chunk
        self.confidence = confidence
        self.category = category
        self.concepts = concepts or []
        self.source_text = source_chunk.get("text", "")
        self.source_meta = source_chunk.get("metadata", {})

    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "category": self.category,
            "concepts": self.concepts,
            "source": self.source_meta.get("source", "unknown"),
        }


class FactExtractor:
    def __init__(self):
        self._extracted_facts: List[AtomicFact] = []

    def extract_from_chunks(self, chunks: List[Dict]) -> List[AtomicFact]:
        facts = []
        for chunk in chunks:
            chunk_facts = self._extract_chunk_facts(chunk)
            facts.extend(chunk_facts)
        self._extracted_facts.extend(facts)
        logger.info(f"Extracted {len(facts)} facts from {len(chunks)} chunks")
        return facts

    def extract_from_text(self, text: str, source: str = "") -> List[AtomicFact]:
        chunk = {"text": text, "metadata": {"source": source}}
        return self._extract_chunk_facts(chunk)

    def _extract_chunk_facts(self, chunk: Dict) -> List[AtomicFact]:
        text = chunk.get("text", "")
        if not text:
            return []
        facts = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 20:
                continue
            confidence = self._compute_confidence(sent, chunk)
            concepts = self._extract_concepts(sent)
            category = self._categorize_fact(sent)
            fact = AtomicFact(
                text=sent,
                source_chunk=chunk,
                confidence=confidence,
                category=category,
                concepts=concepts,
            )
            facts.append(fact)
        return facts

    def _compute_confidence(self, sentence: str, chunk: Dict) -> float:
        score = 0.7
        if any(kw in sentence.lower() for kw in ["according to", "reported", "published", "study", "survey"]):
            score += 0.15
        if any(kw in sentence.lower() for kw in ["may", "might", "could", "possibly", "suggest"]):
            score -= 0.1
        if any(kw in sentence.lower() for kw in ["always", "never", "all", "none", "every"]):
            score -= 0.05
        meta = chunk.get("metadata", {})
        if meta.get("source"):
            score += 0.05
        return round(min(max(score, 0.0), 1.0), 2)

    def _extract_concepts(self, sentence: str) -> List[str]:
        words = re.findall(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b', sentence)
        return list(set(w for w in words if len(w) > 3))

    def _categorize_fact(self, sentence: str) -> str:
        sl = sentence.lower()
        if any(w in sl for w in ["method", "algorithm", "technique", "approach", "framework"]):
            return "methodology"
        if any(w in sl for w in ["result", "accuracy", "performance", "achieved", "outperformed"]):
            return "result"
        if any(w in sl for w in ["problem", "challenge", "limitation", "issue", "gap"]):
            return "problem"
        if any(w in sl for w in ["dataset", "corpus", "benchmark", "data"]):
            return "dataset"
        if any(w in sl for w in ["system", "architecture", "pipeline", "framework"]):
            return "architecture"
        return "general"

    def get_all_facts(self, category: Optional[str] = None) -> List[AtomicFact]:
        if category:
            return [f for f in self._extracted_facts if f.category == category]
        return list(self._extracted_facts)

    def get_high_confidence_facts(self, threshold: float = 0.7) -> List[AtomicFact]:
        return [f for f in self._extracted_facts if f.confidence >= threshold]

    def reset(self):
        self._extracted_facts.clear()
