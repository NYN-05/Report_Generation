import hashlib
import threading
from typing import List, Dict, Optional, Callable
from src.core.logger import get_logger

logger = get_logger(__name__)


class Reranker:
    """Cross-encoder reranker using sentence-transformers or BAAI/bge-reranker.

    Architecture:
        Query + Candidate Chunks → CrossEncoder → Relevance Scores → Sorted Context

    Features:
        - Lazy loading (model loaded on first use)
        - GPU support with CPU fallback
        - Batch scoring
        - Result caching
        - Configurable score calibration [0.0, 1.0]
    """

    def __init__(self, model: str = "BAAI/bge-reranker-v2-m3",
                 cache_size: int = 512):
        self._model_name = model
        self._model = None
        self._pipeline = None
        self._available = False
        self._lock = threading.Lock()
        self._cache: Dict[str, float] = {}
        self._cache_size = cache_size
        self._load_attempted = False

    def _load(self):
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(
                self._model_name,
                device=self._detect_device(),
                trust_remote_code=True,
            )
            self._available = True
            logger.info(f"Reranker loaded: {self._model_name} on {self._detect_device()}")
        except ImportError:
            logger.warning("sentence-transformers not available; using fallback reranker")
            self._pipeline = self._fallback_rerank
        except Exception as e:
            logger.warning(f"Failed to load reranker model '{self._model_name}': {e}")
            self._pipeline = self._fallback_rerank
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(
                    self._model_name,
                    device="cpu",
                    trust_remote_code=True,
                )
                self._available = True
                logger.info(f"Reranker loaded on CPU fallback: {self._model_name}")
            except Exception as e2:
                logger.warning(f"CPU fallback also failed: {e2}")

    def _detect_device(self) -> str:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"

    def is_available(self) -> bool:
        self._load()
        return self._available

    def rerank(self, query: str, results: List[Dict], top_n: int = 5) -> List[Dict]:
        if not results:
            return results
        self._load()

        if self._model is not None:
            return self._cross_encoder_rerank(query, results, top_n)

        if self._pipeline is not None:
            return self._pipeline(query, results, top_n)

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
            logger.warning(f"Cross-encoder rerank failed, using fallback: {e}")
            return self._fallback_rerank(query, results, top_n)

    def _calibrate(self, raw_score: float) -> float:
        calibrated = (raw_score + 1.0) / 2.0
        return max(0.0, min(1.0, calibrated))

    def _cached_score(self, query: str, text: str) -> float:
        key = hashlib.md5(f"{query}|{text}".encode()).hexdigest()
        return self._cache.get(key)

    def _cache_score(self, query: str, text: str, score: float):
        if len(self._cache) >= self._cache_size:
            self._cache.clear()
        key = hashlib.md5(f"{query}|{text}".encode()).hexdigest()
        self._cache[key] = score

    def _fallback_rerank(self, query: str, results: List[Dict],
                          top_n: int) -> List[Dict]:
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
