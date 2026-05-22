"""Simple event bus for phase lifecycle events.

Replaces ad-hoc callback lambdas with typed events that
multiple listeners can subscribe to.
"""

from typing import Callable, Dict, List
from src.core.logger import get_logger

logger = get_logger(__name__)

# Event types
PHASE_STARTED = "phase.started"
PHASE_COMPLETED = "phase.completed"
PHASE_FAILED = "phase.failed"
PHASE_SKIPPED = "phase.skipped"
PIPELINE_STARTED = "pipeline.started"
PIPELINE_COMPLETED = "pipeline.completed"


class EventBus:
    """Lightweight pub-sub event bus for pipeline lifecycle events.

    Usage:
        bus = EventBus()
        bus.on("phase.started", lambda phase: print(f"Starting {phase}"))
        bus.emit("phase.started", phase="research")
    """

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def on(self, event: str, callback: Callable):
        """Subscribe to an event."""
        self._listeners.setdefault(event, []).append(callback)

    def off(self, event: str, callback: Callable):
        """Unsubscribe from an event."""
        listeners = self._listeners.get(event, [])
        if callback in listeners:
            listeners.remove(callback)

    def emit(self, event: str, **data):
        """Emit an event to all subscribers."""
        for cb in self._listeners.get(event, []):
            try:
                cb(**data)
            except Exception as e:
                logger.warning(f"Event handler {cb.__name__} failed on {event}: {e}")

    def clear(self):
        self._listeners.clear()

    @property
    def listener_count(self) -> int:
        return sum(len(v) for v in self._listeners.values())
