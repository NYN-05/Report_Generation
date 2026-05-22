"""
Context Module
==============
Conversation context management.
"""

import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from src.core.logger import get_logger
from src.core.exceptions import ContextError

logger = get_logger(__name__)


@dataclass
class ConversationContext:
    """Stores conversation context."""
    session_id: str
    user_id: str = "default"
    task: str = ""
    skills_used: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

    def update(self, **kwargs):
        """Update context fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()

    def is_expired(self) -> bool:
        """Check if context has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def set_ttl(self, seconds: int):
        """Set time-to-live for context."""
        self.expires_at = datetime.now() + timedelta(seconds=seconds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "task": self.task,
            "skills_used": self.skills_used,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class ContextManager:
    """Manages conversation contexts with thread safety."""

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
        self._contexts: Dict[str, ConversationContext] = {}
        self._user_contexts: Dict[str, List[str]] = {}
        self._session_timeout = 3600
        self._initialized = True
        logger.info("ContextManager initialized")

    def create_context(self, user_id: str = "default", task: str = "") -> ConversationContext:
        """Create a new context."""
        session_id = str(uuid.uuid4())
        context = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            task=task
        )
        context.set_ttl(self._session_timeout)

        with self._lock:
            self._contexts[session_id] = context

            if user_id not in self._user_contexts:
                self._user_contexts[user_id] = []
            self._user_contexts[user_id].append(session_id)

        logger.debug(f"Created context: {session_id} for user: {user_id}")
        return context

    def get_context(self, session_id: str = None, user_id: str = "default") -> Optional[ConversationContext]:
        """Get context by session ID or latest user context."""
        with self._lock:
            if session_id and session_id in self._contexts:
                context = self._contexts[session_id]
                if not context.is_expired():
                    return context
                else:
                    del self._contexts[session_id]

            if user_id in self._user_contexts:
                for sid in reversed(self._user_contexts[user_id]):
                    if sid in self._contexts:
                        context = self._contexts[sid]
                        if not context.is_expired():
                            return context

        return self.create_context(user_id)

    def update_context(self, session_id: str, **kwargs):
        """Update context for session."""
        with self._lock:
            if session_id in self._contexts:
                self._contexts[session_id].update(**kwargs)
                self._contexts[session_id].set_ttl(self._session_timeout)
            else:
                raise ContextError(f"Session not found: {session_id}")

    def delete_context(self, session_id: str):
        """Delete a context."""
        with self._lock:
            if session_id in self._contexts:
                context = self._contexts[session_id]
                user_id = context.user_id

                del self._contexts[session_id]

                if user_id in self._user_contexts:
                    self._user_contexts[user_id] = [
                        sid for sid in self._user_contexts[user_id] if sid != session_id
                    ]

                logger.debug(f"Deleted context: {session_id}")

    def clear_expired(self):
        """Clear expired contexts."""
        with self._lock:
            expired = [
                sid for sid, ctx in self._contexts.items() if ctx.is_expired()
            ]

            for sid in expired:
                ctx = self._contexts[sid]
                user_id = ctx.user_id
                del self._contexts[sid]

                if user_id in self._user_contexts:
                    self._user_contexts[user_id] = [
                        s for s in self._user_contexts[user_id] if s != sid
                    ]

            if expired:
                logger.info(f"Cleared {len(expired)} expired contexts")

    def get_all_sessions(self, user_id: str) -> List[ConversationContext]:
        """Get all sessions for a user."""
        with self._lock:
            if user_id not in self._user_contexts:
                return []

            return [
                self._contexts[sid]
                for sid in self._user_contexts[user_id]
                if sid in self._contexts and not self._contexts[sid].is_expired()
            ]

    def set_session_timeout(self, seconds: int):
        """Set default session timeout."""
        self._session_timeout = seconds