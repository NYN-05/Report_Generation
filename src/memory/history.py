"""
History Module
==============
Report history management.
"""

import json
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
from threading import Lock
from dataclasses import dataclass, field, asdict
from src.core.logger import get_logger
from src.core.config import get_config

logger = get_logger(__name__)


@dataclass
class ReportRecord:
    """Single report history record."""
    task: str
    title: str
    skills_used: List[str]
    success: bool
    mode: str = "scratch"
    template_path: Optional[str] = None
    output_path: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    execution_time: float = 0.0
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


class ReportHistory:
    """Stores history of generated reports."""

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
        self._history: List[ReportRecord] = []
        self._max_records = 100
        self._storage_path = Path("logs/report_history.json")
        self._initialized = True
        self._load_from_disk()
        logger.info("ReportHistory initialized")

    def _load_from_disk(self):
        """Load history from disk."""
        if self._storage_path.exists():
            try:
                data = json.loads(self._storage_path.read_text(encoding="utf-8"))
                self._history = [ReportRecord(**r) for r in data]
                logger.info(f"Loaded {len(self._history)} history records")
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")

    def _save_to_disk(self):
        """Save history to disk."""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = [r.to_dict() for r in self._history[-self._max_records:]]
            self._storage_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def add(
        self,
        task: str,
        title: str,
        skills_used: List[str],
        success: bool,
        mode: str = "scratch",
        template_path: Optional[str] = None,
        output_path: Optional[str] = None,
        error: Optional[str] = None,
        execution_time: float = 0.0,
        metadata: Optional[Dict] = None
    ):
        """Add report to history."""
        with self._lock:
            record = ReportRecord(
                task=task,
                title=title,
                skills_used=skills_used,
                success=success,
                mode=mode,
                template_path=template_path,
                output_path=output_path,
                error=error,
                execution_time=execution_time,
                metadata=metadata or {}
            )

            self._history.append(record)

            if len(self._history) > self._max_records:
                self._history = self._history[-self._max_records:]

            self._save_to_disk()
            logger.debug(f"Added report to history: {task}")

    def get_recent(self, count: int = 10, success_only: bool = False) -> List[ReportRecord]:
        """Get recent reports."""
        with self._lock:
            history = self._history[-count:] if count > 0 else self._history
            if success_only:
                history = [r for r in history if r.success]
            return history

    def get_by_task(self, task: str) -> List[ReportRecord]:
        """Get reports by task pattern."""
        with self._lock:
            return [r for r in self._history if task.lower() in r.task.lower()]

    def get_by_mode(self, mode: str) -> List[ReportRecord]:
        """Get reports by execution mode."""
        with self._lock:
            return [r for r in self._history if r.mode == mode]

    def get_stats(self) -> Dict:
        """Get statistics about history."""
        with self._lock:
            total = len(self._history)
            successful = sum(1 for r in self._history if r.success)
            failed = total - successful

            modes = {}
            for r in self._history:
                modes[r.mode] = modes.get(r.mode, 0) + 1

            avg_time = 0
            if self._history:
                times = [r.execution_time for r in self._history if r.execution_time > 0]
                if times:
                    avg_time = sum(times) / len(times)

            return {
                "total": total,
                "successful": successful,
                "failed": failed,
                "success_rate": (successful / total * 100) if total > 0 else 0,
                "modes": modes,
                "average_execution_time": round(avg_time, 2),
            }

    def clear(self):
        """Clear all history."""
        with self._lock:
            self._history.clear()
            self._save_to_disk()
            logger.info("Cleared report history")

    def set_max_records(self, count: int):
        """Set maximum number of records to keep."""
        self._max_records = count
        if len(self._history) > count:
            self._history = self._history[-count:]
            self._save_to_disk()