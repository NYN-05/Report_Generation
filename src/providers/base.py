"""
Base Provider Module
====================
Abstract interface for LLM providers.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class ProviderType(Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    raw_response: Optional[Dict] = None


@dataclass
class Message:
    """Chat message structure."""
    role: str
    content: str
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            name=data.get("name")
        )


@dataclass
class CompletionOptions:
    """Options for text completion."""
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: Optional[int] = None
    stop: Optional[List[str]] = None
    stream: bool = False
    timeout: Optional[int] = None


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(
        self,
        model: str = "llama3.2:3b",
        temperature: float = 0.7,
        top_p: float = 0.9,
        timeout: int = 120,
        **kwargs
    ):
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.timeout = timeout
        self.config = kwargs
        self._client = None

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available."""
        pass

    @abstractmethod
    def chat(self, messages: List[Message], options: Optional[CompletionOptions] = None) -> LLMResponse:
        """Send chat request and get response."""
        pass

    @abstractmethod
    def generate(self, prompt: str, options: Optional[CompletionOptions] = None) -> LLMResponse:
        """Generate text from prompt."""
        pass

    def prepare_messages(self, system: str, user: str) -> List[Message]:
        """Prepare message list from system and user input."""
        return [
            Message(role="system", content=system),
            Message(role="user", content=user)
        ]

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.OLLAMA

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} model={self.model}>"