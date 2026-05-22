"""
Cache Module
============
Response caching for LLM calls.
"""

import hashlib
import json
import time
from typing import Any, Optional, Dict
from threading import Lock
from dataclasses import dataclass
from src.core.logger import get_logger
from src.core.config import get_config

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with timestamp."""
    key: str
    value: Any
    created_at: float
    ttl: int


class ResponseCache:
    """Simple in-memory cache for LLM responses."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        config = get_config()
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = 1000
        self._default_ttl = config.skills.cache_ttl if hasattr(config, 'skills') else 3600
        self._hit_count = 0
        self._miss_count = 0
        self._initialized = True
        logger.info("ResponseCache initialized")

    @staticmethod
    def _generate_key(messages: list, model: str, options: Dict = None) -> str:
        """Generate cache key from request parameters."""
        key_data = {
            "messages": [
                {"role": m.role, "content": m.content[:200]} if hasattr(m, 'role') else {"content": str(m)[:200]}
                for m in messages
            ],
            "model": model,
            "options": options or {}
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        with self._lock:
            if key not in self._cache:
                self._miss_count += 1
                return None

            entry = self._cache[key]
            age = time.time() - entry.created_at

            if age > entry.ttl:
                del self._cache[key]
                self._miss_count += 1
                return None

            self._hit_count += 1
            logger.debug(f"Cache hit for key: {key[:16]}...")
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set cache value with optional TTL."""
        with self._lock:
            if len(self._cache) >= self._max_size:
                self._evict_oldest()

            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl or self._default_ttl
            )
            logger.debug(f"Cached value for key: {key[:16]}...")

    def _evict_oldest(self):
        """Evict oldest cache entry."""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]
        logger.debug(f"Evicted oldest cache entry: {oldest_key[:16]}...")

    def clear(self):
        """Clear all cache."""
        with self._lock:
            self._cache.clear()
            self._hit_count = 0
            self._miss_count = 0
            logger.info("Cleared response cache")

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hit_count,
                "misses": self._miss_count,
                "hit_rate": round(hit_rate, 2),
            }

    def cleanup_expired(self):
        """Remove expired entries."""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if current_time - entry.created_at > entry.ttl
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


def cache_response(ttl: int = 3600):
    """Decorator to cache function results."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = ResponseCache()

            key_data = {
                "func": func.__name__,
                "args": str(args)[:100],
                "kwargs": str(sorted(kwargs.items()))[:100]
            }
            key = hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

            cached = cache.get(key)
            if cached is not None:
                return cached

            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator