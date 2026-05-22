"""
Base Agent Module
=================
Abstract base class for all agents.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from src.core.logger import get_logger
from src.providers import BaseProvider, get_default_provider

logger = get_logger(__name__)


@dataclass
class AgentResponse:
    """Standardized agent response."""
    success: bool
    data: Any = None
    error: str = ""
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, name: str, provider: Optional[BaseProvider] = None):
        self.name = name
        self.provider = provider or get_default_provider()
        self.logger = get_logger(f"agent.{name}")
        self._initialized = False

    @abstractmethod
    def execute(self, input_data: Any, **kwargs) -> AgentResponse:
        """Execute the agent's main task."""
        pass

    def _create_response(
        self,
        success: bool,
        data: Any = None,
        error: str = "",
        **metadata
    ) -> AgentResponse:
        """Create a standardized response."""
        return AgentResponse(
            success=success,
            data=data,
            error=error,
            metadata=metadata if metadata else {}
        )

    def _log_error(self, operation: str, error: Exception):
        """Log error with context."""
        self.logger.error(f"{operation} failed: {error}")

    def _log_info(self, message: str):
        """Log info message."""
        self.logger.info(f"{self.name}: {message}")

    def is_available(self) -> bool:
        """Check if agent can execute."""
        if self.provider is None:
            return False
        return self.provider.is_available()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"