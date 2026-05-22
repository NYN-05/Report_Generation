"""
Reranker Module
===============
Cross-encoder reranker with graceful fallback to keyword overlap.

Architecture:
    Query + Candidate Chunks → CrossEncoder → Relevance Scores → Sorted Context

Requirements:
    - sentence-transformers must be installed for model-based reranking
    - Falls back to keyword overlap when model unavailable
    - No heavy imports on construction (only on explicit load_model call)
"""

import hashlib
import threading
from typing import List, Dict, Optional, Callable
from src.core.logger import get_logger

logger = get_logger(__name__)


class Reranker:
    """Re-ranks search results using cross-encoder or fallback scoring.

    Features:
        - Lazy loading (model loaded on first use via load_model())
        - GPU support with CPU fallback
        - Batch scoring
        - Result caching
        - Configurable score calibration [0.0, 1.0]
        - Graceful fallback to keyword overlap when model unavailable
    """

    def __init__(self, model: str = "BAAI/bge-reranker-v2-m3",
                 cache_size: int = 512):
        self._model_name = model
        self._model = None
        self._available = False
        self._lock = threading.Lock()
        self._cache: Dict[str, float] = {}
        self._cache_size = cache_size
        self._import_attempted = False

    def load_model(self) -> bool:
        """Attempt to load the cross-encoder model. Returns True if successful.

        This is the only method that performs heavy imports (sentence-transformers, torch).
        Safe to call at any time — will only attempt once.
        """
        if self._import_attempted:
            return self._available
        self._import_attempted = True

        device = self._detect_device()

        for attempt, dev in [(f"default ({device})", device), ("CPU fallback", "cpu")]:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(
                    self._model_name,
                    device=dev,
                    trust_remote_code=True,
                )
                self._available = True
                logger.info(f"Reranker loaded: {self._model_name} on {dev}")
                return True
            except ImportError:
                logger.warning("sentence-transformers not available; reranker disabled")
                break
            except Exception as e:
                logger.warning(f"Reranker load failed on {dev}: {e}")
                continue

        self._available = False
        return False

    def _detect_device(self) -> str:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"

    def is_available(self) -> bool:
        return self._available

    def is_model_loaded(self) -> bool:
        return self._import_attempted and self._available

    def rerank(self, query: str, results: List[Dict], top_n: int = 5) -> List[Dict]:
        """Re-rank results using loaded model or fallback scoring."""
        if not results:
            return results

        if self._model is not None:
            return self._cross_encoder_rerank(query, results, top_n)

        return self._fallback_rerank(query, results, top_n)

    def _cross_encoder_rerank(self, query: str, results: List[Dict],
                               top_n: int) -> List[Dict]:
        try:
            pairs = [(query, r.get("text", "")) for r in results]
            scores = self._model.predict(
                pairs,
                batch_size=min(32, len(pairs)),
                show_progress_bar=False,
            )

            for r, raw_score in zip(results, scores):
                r["rerank_score"] = self._calibrate(float(raw_score))
                r["method"] = "reranker"

            results.sort(key=lambda x: -x.get("rerank_score", 0))
            return results[:top_n]

        except Exception as e:
            logger.warning(f"Cross-encoder rerank failed: {e}")
            return self._fallback_rerank(query, results, top_n)

    def _calibrate(self, raw_score: float) -> float:
        """Calibrate raw cross-encoder output to [0.0, 1.0]."""
        calibrated = (raw_score + 1.0) / 2.0
        return max(0.0, min(1.0, calibrated))

    def _cached_score(self, query: str, text: str) -> Optional[float]:
        key = hashlib.md5(f"{query}|{text}".encode()).hexdigest()
        return self._cache.get(key)

    def _cache_score(self, query: str, text: str, score: float):
        if len(self._cache) >= self._cache_size:
            self._cache.clear()
        key = hashlib.md5(f"{query}|{text}".encode()).hexdigest()
        self._cache[key] = score

    def _fallback_rerank(self, query: str, results: List[Dict],
                          top_n: int) -> List[Dict]:
        """Keyword overlap fallback when model is unavailable."""
        query_terms = set(query.lower().split())
        for r in results:
            text = r.get("text", "")
            text_lower = text.lower()
            overlap = sum(1 for t in query_terms if t in text_lower)
            base = overlap / max(len(query_terms), 1)
            title_boost = 0.3 if any(q in text_lower[:200] for q in query_terms) else 0
            r["rerank_score"] = min(base + title_boost, 1.0)
            r["method"] = "fallback"
        results.sort(key=lambda x: -x.get("rerank_score", 0))
        return results[:top_n]
