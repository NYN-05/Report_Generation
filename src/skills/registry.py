"""
Skill Registry Module
=====================
Central registry for managing skills.
"""

from typing import Dict, List, Optional
from .base import Skill
from .loader import SkillLoader
from .selector import SkillSelector, SemanticSkillSelector
from src.core.logger import get_logger

logger = get_logger(__name__)


class SkillRegistry:
    """Central registry for managing skills."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.loader = SkillLoader()
        self.selector = SkillSelector(self.loader)
        self.semantic_selector = SemanticSkillSelector(self.loader)
        self._initialized = True

    def initialize(self) -> int:
        """Initialize the registry."""
        return self.loader.initialize()

    def find_for_task(
        self,
        task: str,
        context: str = "",
        max_skills: int = 5,
        use_semantic: bool = False
    ) -> List[Skill]:
        """Find skills for a specific task."""
        if use_semantic:
            return self.semantic_selector.select_with_semantics(task, context, max_skills)
        return self.selector.select(task, context, max_skills)

    def get_skill_content(self, name: str, max_length: int = 1500) -> Optional[str]:
        """Get full content of a skill."""
        skill = self.loader.get_skill(name)
        if skill:
            return skill.content[:max_length] if len(skill.content) > max_length else skill.content
        return None

    def get_full_content(self, name: str) -> Optional[str]:
        """Get full content without truncation."""
        skill = self.loader.get_skill(name)
        return skill.content if skill else None

    def list_skills(self) -> List[Dict]:
        """List all available skills with metadata."""
        return [
            {
                'name': name,
                'description': skill.description[:200],
                'tags': skill.tags[:5],
                'triggers': skill.triggers[:5],
                'relevance_score': skill.relevance_score
            }
            for name, skill in self.loader.get_all_skills().items()
        ]

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a specific skill by name."""
        return self.loader.get_skill(name)

    def reload(self) -> int:
        """Reload all skills."""
        return self.loader.reload()

    def get_related_skills(self, skill_name: str, max_related: int = 3) -> List[Skill]:
        """Get related skills."""
        return self.semantic_selector.suggest_related(skill_name, max_related)

    def explain_selection(self, task: str, skills: List[Skill]) -> str:
        """Explain skill selection."""
        return self.selector.explain_selection(task, skills)

    def get_skill_by_tag(self, tag: str) -> List[Skill]:
        """Get skills by tag."""
        return self.loader.get_skills_by_tag(tag)


def get_registry() -> SkillRegistry:
    """Get the singleton skill registry."""
    return SkillRegistry()