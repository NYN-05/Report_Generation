from typing import List, Dict, Optional
from src.core.logger import get_logger

logger = get_logger(__name__)


class HybridSearch:
    """Combines BM25 keyword search with vector similarity search."""

    def __init__(self, vector_store=None):
        self._vector_store = vector_store
        self._bm25_index = None
        self._bm25_docs = []

    def index_chunks(self, chunks: List[Dict]):
        texts = [c.get("text", "") for c in chunks]
        self._build_bm25(texts)
        self._bm25_docs = chunks

    def _build_bm25(self, texts: List[str]):
        try:
            from rank_bm25 import BM25Okapi
            tokenized = [t.lower().split() for t in texts]
            self._bm25_index = BM25Okapi(tokenized)
            logger.info(f"BM25 index built with {len(texts)} documents")
        except ImportError:
            logger.warning("rank-bm25 not available, BM25 disabled")

    def search(self, query: str, n_results: int = 5) -> List[Dict]:
        bm25_scores = self._bm25_search(query) if self._bm25_index else []
        vector_results = self._vector_store.search(query, n_results=n_results * 2) if self._vector_store else []

        merged = self._merge_results(query, bm25_scores, vector_results, n_results)

        for i, r in enumerate(merged):
            r["rank"] = i + 1
        return merged[:n_results]

    def _bm25_search(self, query: str) -> List[Dict]:
        if not self._bm25_index or not self._bm25_docs:
            return []
        tokenized = query.lower().split()
        scores = self._bm25_index.get_scores(tokenized)
        scored = [(i, scores[i]) for i in range(len(scores))]
        scored.sort(key=lambda x: -x[1])
        results = []
        for idx, score in scored[:10]:
            if score > 0:
                doc = self._bm25_docs[idx]
                results.append({
                    "text": doc.get("text", ""),
                    "metadata": {"heading": doc.get("heading", ""), "source": doc.get("source", "")},
                    "score": float(score),
                    "method": "bm25",
                })
        return results

    def _merge_results(self, query: str, bm25: List[Dict],
                       vector: List[Dict], n: int) -> List[Dict]:
        seen_texts = set()
        merged = []

        for v in vector:
            norm = v.get("text", "")[:200]
            if norm not in seen_texts:
                v["method"] = "vector"
                v["score"] = 1.0 - v.get("distance", 0)
                seen_texts.add(norm)
                merged.append(v)

        for b in bm25:
            norm = b.get("text", "")[:200]
            if norm not in seen_texts:
                b["method"] = "bm25"
                b["score"] = b.get("score", 0) / 10.0
                merged.append(b)

        merged.sort(key=lambda x: -x.get("score", 0))
        return merged[:n]
