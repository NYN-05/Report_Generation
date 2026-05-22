from typing import List, Dict
from src.core.logger import get_logger

logger = get_logger(__name__)


class Reranker:
    """Re-ranks search results for improved relevance."""

    def __init__(self, model: str = "bge-reranker"):
        self._model = model
        self._available = False
        self._init()

    def _init(self):
        self._available = False

    def is_available(self) -> bool:
        return self._available

    def rerank(self, query: str, results: List[Dict], top_n: int = 5) -> List[Dict]:
        if not results:
            return results
        scored = []
        for r in results:
            text = r.get("text", "")
            score = self._score_relevance(query, text)
            r["rerank_score"] = score
            scored.append(r)
        scored.sort(key=lambda x: -x.get("rerank_score", 0))
        return scored[:top_n]

    def _score_relevance(self, query: str, text: str) -> float:
        query_terms = set(query.lower().split())
        text_lower = text.lower()
        overlap = sum(1 for t in query_terms if t in text_lower)
        base = overlap / max(len(query_terms), 1)
        title_boost = 0.3 if any(q in text_lower[:200] for q in query_terms) else 0
        return min(base + title_boost, 1.0)
