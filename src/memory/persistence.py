"""
Persistence Module
==================
Context persistence to disk.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from src.core.logger import get_logger
from src.core.exceptions import ContextError

logger = get_logger(__name__)


class PersistenceManager:
    """Manages context persistence to disk."""

    def __init__(self, storage_dir: str = "logs/contexts"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"PersistenceManager initialized: {self.storage_dir}")

    def save_context(
        self,
        session_id: str,
        context_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Save context to disk."""
        try:
            filename = f"{session_id}.json"
            filepath = self.storage_dir / filename

            data = {
                "session_id": session_id,
                "saved_at": datetime.now().isoformat(),
                "context": context_data,
                "metadata": metadata or {}
            }

            filepath.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            logger.debug(f"Saved context: {session_id}")
            return filepath

        except Exception as e:
            raise ContextError(f"Failed to save context: {e}")

    def load_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load context from disk."""
        try:
            filename = f"{session_id}.json"
            filepath = self.storage_dir / filename

            if not filepath.exists():
                return None

            data = json.loads(filepath.read_text(encoding="utf-8"))
            logger.debug(f"Loaded context: {session_id}")
            return data.get("context", {})

        except Exception as e:
            logger.warning(f"Failed to load context {session_id}: {e}")
            return None

    def delete_context(self, session_id: str) -> bool:
        """Delete context from disk."""
        try:
            filename = f"{session_id}.json"
            filepath = self.storage_dir / filename

            if filepath.exists():
                filepath.unlink()
                logger.debug(f"Deleted context: {session_id}")
                return True
            return False

        except Exception as e:
            logger.warning(f"Failed to delete context {session_id}: {e}")
            return False

    def list_contexts(self) -> list:
        """List all saved contexts."""
        return [f.stem for f in self.storage_dir.glob("*.json")]

    def cleanup_old_contexts(self, max_age_days: int = 7):
        """Clean up old context files."""
        import time
        cutoff = time.time() - (max_age_days * 86400)

        removed = 0
        for filepath in self.storage_dir.glob("*.json"):
            if filepath.stat().st_mtime < cutoff:
                filepath.unlink()
                removed += 1

        if removed:
            logger.info(f"Cleaned up {removed} old context files")

        return removed


def save_to_json(data: Dict, filepath: str) -> bool:
    """Utility to save data to JSON file."""
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to save JSON to {filepath}: {e}")
        return False


def load_from_json(filepath: str) -> Optional[Dict]:
    """Utility to load data from JSON file."""
    try:
        path = Path(filepath)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None
    except Exception as e:
        logger.error(f"Failed to load JSON from {filepath}: {e}")
        return None