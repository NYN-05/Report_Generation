"""Base class for all hierarchical generators."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GeneratorContext:
    """Context passed down the generator hierarchy."""
    topic: str = ""
    report_type: str = "engineering project report"
    document_state: Optional[Any] = None
    retrieval_context: str = ""
    style_profile: Optional[Dict] = None
    memory_state: Optional[Dict] = None
    chapter_summaries: Optional[Dict[str, str]] = None
    parent_summary: str = ""
    metadata: Dict = field(default_factory=dict)


class BaseGenerator(ABC):
    """Abstract base for hierarchical generators."""

    def __init__(self, name: str = "base"):
        self.name = name
        self._logger = get_logger(f"generator.{name}")

    @abstractmethod
    def generate(self, context: GeneratorContext, **kwargs) -> Any:
        ...

    def log(self, msg: str):
        self._logger.info(f"[{self.name}] {msg}")
