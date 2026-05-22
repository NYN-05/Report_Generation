import json
import os
from typing import Dict, Optional
from pathlib import Path

from .models import Blueprint
from src.core.logger import get_logger

logger = get_logger(__name__)


class BlueprintLoader:
    """Loads blueprints from catalog files and custom paths."""

    def __init__(self, catalog_dir: Optional[str] = None):
        self.catalog_dir = Path(
            catalog_dir or os.path.join(os.path.dirname(__file__), "catalog")
        )
        self._cache: Dict[str, Blueprint] = {}

    def load(self, blueprint_id: str) -> Optional[Blueprint]:
        if blueprint_id in self._cache:
            return self._cache[blueprint_id]

        path = self.catalog_dir / f"{blueprint_id}.json"
        if not path.exists():
            logger.warning(f"Blueprint not found: {blueprint_id} at {path}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            bp = Blueprint.from_dict(data)
            self._cache[blueprint_id] = bp
            logger.info(f"Loaded blueprint: {bp.name} ({blueprint_id})")
            return bp
        except Exception as e:
            logger.error(f"Failed to load blueprint {blueprint_id}: {e}")
            return None

    def load_all(self) -> Dict[str, Blueprint]:
        if not self.catalog_dir.exists():
            logger.warning(f"Catalog directory not found: {self.catalog_dir}")
            return {}

        for fpath in sorted(self.catalog_dir.glob("*.json")):
            bp_id = fpath.stem
            if bp_id not in self._cache:
                self.load(bp_id)

        return dict(self._cache)

    def load_custom(self, filepath: str) -> Optional[Blueprint]:
        path = Path(filepath)
        if not path.exists():
            logger.error(f"Custom blueprint file not found: {filepath}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            bp = Blueprint.from_dict(data)
            bp_id = data.get("id", path.stem)
            self._cache[bp_id] = bp
            logger.info(f"Loaded custom blueprint: {bp.name} from {filepath}")
            return bp
        except Exception as e:
            logger.error(f"Failed to load custom blueprint {filepath}: {e}")
            return None

    def get_available(self) -> Dict[str, str]:
        result = {}
        if not self.catalog_dir.exists():
            return result
        for fpath in sorted(self.catalog_dir.glob("*.json")):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result[data.get("id", fpath.stem)] = data.get("name", fpath.stem)
            except Exception:
                result[fpath.stem] = fpath.stem
        return result

    def clear_cache(self):
        self._cache.clear()
