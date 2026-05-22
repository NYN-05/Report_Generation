import math
from typing import List, Dict, Optional
from src.core.logger import get_logger

logger = get_logger(__name__)


class HybridSearch:
    """Combines BM25 keyword search with vector similarity search.

    Fusion uses Reciprocal Rank Fusion (RRF) as the primary strategy,
    with optional weighted score fusion as fallback.
    """

    RRF_K = 60

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
        bm25_results = self._bm25_search(query) if self._bm25_index else []
        vector_results = self._vector_store.search(query, n_results=n_results * 3) if self._vector_store else []

        merged = self._merge_results_rrf(bm25_results, vector_results, n_results)

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
        for idx, score in scored[:15]:
            if score > 0:
                doc = self._bm25_docs[idx]
                results.append({
                    "text": doc.get("text", ""),
                    "metadata": {"heading": doc.get("heading", ""), "source": doc.get("source", "")},
                    "score": float(score),
                    "method": "bm25",
                })
        return results

    def _merge_results_rrf(self, bm25: List[Dict],
                           vector: List[Dict], n: int) -> List[Dict]:
        """Reciprocal Rank Fusion — principled rank-based merging.

        RRF avoids score normalization issues entirely by operating on ranks.
        Score = 1 / (k + rank) for each result from each method.
        """
        rrf_scores: Dict[str, Dict] = {}

        for rank, v in enumerate(vector):
            norm = v.get("text", "")[:200]
            if norm not in rrf_scores:
                entry = dict(v)
                entry["method"] = "vector"
                entry.pop("distance", None)
                rrf_scores[norm] = entry
                rrf_scores[norm]["_rrf"] = 0.0
            rrf_scores[norm]["_rrf"] += 1.0 / (self.RRF_K + rank + 1)

        for rank, b in enumerate(bm25):
            norm = b.get("text", "")[:200]
            if norm not in rrf_scores:
                entry = dict(b)
                entry["method"] = "bm25"
                entry["metadata"] = dict(b.get("metadata", {}))
                rrf_scores[norm] = entry
                rrf_scores[norm]["_rrf"] = 0.0
            rrf_scores[norm]["_rrf"] += 1.0 / (self.RRF_K + rank + 1)

        results = list(rrf_scores.values())
        results.sort(key=lambda x: -x["_rrf"])

        for r in results:
            r["score"] = round(r.pop("_rrf"), 4)

        return results[:n]

    def _normalize_vector_score(self, distance: float) -> float:
        """Normalize ChromaDB cosine distance [0,2] to similarity [0,1].

        ChromaDB uses cosine distance = 1 - cosine_similarity.
        Range: 0 (identical) to 2 (opposite).
        """
        return 1.0 - (distance / 2.0)

    def _normalize_bm25_score(self, score: float, min_score: float,
                               max_score: float) -> float:
        """Min-max normalize BM25 score to [0,1].

        BM25 scores are unbounded and corpus-dependent.
        Min-max normalization provides stable [0,1] mapping.
        """
        if max_score <= min_score:
            return 0.0
        return (score - min_score) / (max_score - min_score)
