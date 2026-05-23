from typing import Dict, List, Optional, Tuple
import time
import hashlib
from collections import OrderedDict
from src.core.logger import get_logger

logger = get_logger(__name__)


class RetrievalCache:
    def __init__(self, max_size: int = 50, ttl: int = 300):
        self._cache: OrderedDict[str, Tuple[float, Dict]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    def get(self, query: str, top_k: int = 8) -> Optional[Dict]:
        key = self._make_key(query, top_k)
        if key in self._cache:
            timestamp, data = self._cache[key]
            if time.time() - timestamp < self._ttl:
                self._cache.move_to_end(key)
                self._hits += 1
                return data
            else:
                del self._cache[key]
        self._misses += 1
        return None

    def set(self, query: str, top_k: int, data: Dict):
        key = self._make_key(query, top_k)
        self._cache[key] = (time.time(), data)
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def _make_key(self, query: str, top_k: int) -> str:
        normalized = query.lower().strip()
        return hashlib.md5(f"{normalized}|{top_k}".encode()).hexdigest()

    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / max(total, 1)

    def stats(self) -> Dict:
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate(), 3),
            "ttl": self._ttl,
        }

    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def invalidate(self, query: str, top_k: int = 8):
        key = self._make_key(query, top_k)
        self._cache.pop(key, None)
