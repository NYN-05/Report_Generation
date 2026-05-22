"""
Base Skill Module
==================
Skill interface and data structures.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class Skill:
    """Represents a single skill with metadata and content."""
    name: str
    description: str
    folder_path: str
    triggers: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    license: str = ""
    content: str = ""
    loaded_at: Optional[datetime] = None
    relevance_score: float = 0.0

    def relevance_score_for(self, query: str) -> float:
        """Calculate relevance score based on query."""
        score = 0.0
        query_lower = query.lower()

        if '.pdf' in query_lower and self.name == 'pdf':
            score += 5.0
        if '.docx' in query_lower and self.name == 'docx':
            score += 5.0
        if '.xlsx' in query_lower and self.name == 'xlsx':
            score += 5.0
        if '.pptx' in query_lower and self.name == 'pptx':
            score += 5.0

        actions = {
            'create': 2.0, 'generate': 2.0, 'extract': 2.5, 'convert': 2.5,
            'merge': 2.0, 'split': 2.0, 'edit': 1.5, 'fill': 2.0,
            'analyze': 2.0, 'build': 1.5, 'design': 1.5, 'write': 1.5,
            'process': 1.5, 'handle': 1.5, 'manage': 1.5
        }
        for action, weight in actions.items():
            if action in query_lower:
                score += weight

        desc_lower = self.description.lower()
        for word in query_lower.split():
            if len(word) > 3 and word in desc_lower:
                score += 0.3

        for tag in self.tags:
            if tag in query_lower:
                score += 1.0

        return max(0.0, score)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "folder_path": self.folder_path,
            "triggers": self.triggers,
            "keywords": self.keywords,
            "tags": self.tags,
            "license": self.license,
            "relevance_score": self.relevance_score,
        }

    def __repr__(self) -> str:
        return f"<Skill: {self.name}>"


@dataclass
class SkillResult:
    """Result of skill execution."""
    success: bool
    output: Any = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    """Abstract base class for skills."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> SkillResult:
        """Execute the skill with context."""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get skill description."""
        pass

    def validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate required context for skill execution."""
        return True