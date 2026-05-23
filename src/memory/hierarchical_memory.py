from typing import Dict, List, Optional, Tuple, Any
from collections import OrderedDict
import time
from src.core.logger import get_logger

logger = get_logger(__name__)


class HierarchicalMemory:
    def __init__(self, max_tier1: int = 3, max_tier2: int = 10):
        self._tier1: OrderedDict[str, str] = OrderedDict()
        self._tier2: OrderedDict[str, str] = OrderedDict()
        self._tier3: Dict[str, str] = {}
        self._max_tier1 = max_tier1
        self._max_tier2 = max_tier2
        self._access_log: List[Dict] = []

    def store(self, key: str, content: str, importance: float = 0.5):
        tier = self._assign_tier(importance)
        if tier == 1:
            self._tier1[key] = content
            if len(self._tier1) > self._max_tier1:
                oldest = next(iter(self._tier1))
                self._tier2[oldest] = self._tier1.pop(oldest)
        elif tier == 2:
            self._tier2[key] = content
            if len(self._tier2) > self._max_tier2:
                oldest = next(iter(self._tier2))
                self._tier3[oldest] = self._tier2.pop(oldest)
        else:
            self._tier3[key] = content
        self._access_log.append({
            "key": key, "action": "store", "tier": tier, "time": time.time(),
        })
        logger.debug(f"Stored '{key}' in tier {tier} (importance={importance})")

    def retrieve(self, key: str) -> Optional[str]:
        if key in self._tier1:
            self._tier1.move_to_end(key)
            self._log_access(key, 1)
            return self._tier1[key]
        if key in self._tier2:
            self._tier2.move_to_end(key)
            self._log_access(key, 2)
            return self._tier2[key]
        val = self._tier3.get(key)
        if val:
            self._log_access(key, 3)
        return val

    def get_tier1_summary(self) -> str:
        if not self._tier1:
            return ""
        return "\n\n".join(
            f"[{k}]\n{v[:500]}" for k, v in self._tier1.items()
        )

    def get_tier2_summary(self, max_chars: int = 2000) -> str:
        parts = []
        total = 0
        for k, v in self._tier2.items():
            excerpt = v[:300]
            parts.append(f"[{k}]\n{excerpt}")
            total += len(excerpt)
            if total > max_chars:
                break
        return "\n\n".join(parts)

    def get_all_recent(self, n: int = 5) -> List[Tuple[str, str, int]]:
        recent = []
        for k in list(self._tier1.keys())[-n:]:
            recent.append((k, "tier1", 1))
        for k in list(self._tier2.keys())[-n:]:
            recent.append((k, "tier2", 2))
        return recent

    def _assign_tier(self, importance: float) -> int:
        if importance >= 0.7:
            return 1
        elif importance >= 0.4:
            return 2
        return 3

    def _log_access(self, key: str, tier: int):
        self._access_log.append({
            "key": key, "action": "access", "tier": tier, "time": time.time(),
        })

    def stats(self) -> Dict:
        return {
            "tier1_size": len(self._tier1),
            "tier2_size": len(self._tier2),
            "tier3_size": len(self._tier3),
            "total_accesses": len(self._access_log),
        }

    def clear(self):
        self._tier1.clear()
        self._tier2.clear()
        self._tier3.clear()
        self._access_log.clear()
