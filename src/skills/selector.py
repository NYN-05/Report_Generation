"""
Skill Selector Module
=====================
Semantic skill selection based on user intent.
"""

from typing import List, Optional, Dict
from .base import Skill
from .loader import SkillLoader
from src.core.logger import get_logger
from src.core.constants import SkillMatchThreshold

logger = get_logger(__name__)


class SkillSelector:
    """Keyword-based skill selection."""

    def __init__(self, loader: SkillLoader):
        self.loader = loader

    def select(
        self,
        query: str,
        context: str = "",
        max_skills: int = 5,
        min_score: float = SkillMatchThreshold.DEFAULT
    ) -> List[Skill]:
        """Select the most relevant skills for a query."""
        combined_input = f"{query} {context}".strip()

        results = self.loader.search(combined_input, min_score=min_score)

        if not results:
            logger.debug(f"No skills found for: {query}")
            return []

        selected = []
        top_score = results[0][1] if results else 0

        for skill, score in results:
            if score >= SkillMatchThreshold.HIGH:
                selected.append(skill)
            elif score >= SkillMatchThreshold.MEDIUM and top_score < SkillMatchThreshold.HIGH:
                selected.append(skill)
            elif score >= SkillMatchThreshold.LOW and selected and len(selected) < 3:
                if self._is_related(skill, selected):
                    selected.append(skill)

        selected = selected[:max_skills]

        for s in selected:
            logger.info(f"Selected skill: {s.name} (score: {s.relevance_score:.2f})")

        return selected

    def _is_related(self, skill: Skill, selected: List[Skill]) -> bool:
        """Check if skill is related to already selected skills."""
        skill_tags = set(skill.tags + skill.keywords)
        for sel_skill in selected:
            sel_tags = set(sel_skill.tags + sel_skill.keywords)
            if skill_tags & sel_tags:
                return True
        return False

    def chain_skills(self, query: str) -> List[Skill]:
        """Create an ordered skill chain for complex tasks."""
        return self.select(query)

    def suggest_fallback(self) -> Optional[Skill]:
        """Suggest a fallback skill when no exact match."""
        return self.loader.get_skill('docx')

    def explain_selection(self, query: str, skills: List[Skill]) -> str:
        """Generate explanation for skill selection."""
        if not skills:
            return f"No skills found relevant to: {query}"

        explanation = f"Selected {len(skills)} skill(s) for '{query}':\n\n"
        for skill in skills:
            explanation += f"• **{skill.name}**\n"
            explanation += f"  Description: {skill.description[:100]}...\n"
            explanation += f"  Relevance: {skill.relevance_score:.2f}\n"
            explanation += f"  Tags: {', '.join(skill.tags[:3])}\n\n"

        return explanation


class SemanticSkillSelector(SkillSelector):
    """Enhanced selector with semantic matching capabilities."""

    def __init__(self, loader: SkillLoader):
        super().__init__(loader)
        self._embedding_cache: Dict[str, List[float]] = {}

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text (placeholder for semantic matching)."""
        return None

    def select_with_semantics(
        self,
        query: str,
        context: str = "",
        max_skills: int = 5,
        use_semantic: bool = True
    ) -> List[Skill]:
        """Select skills with optional semantic matching."""
        if not use_semantic:
            return self.select(query, context, max_skills)

        results = self.loader.search(query, min_score=SkillMatchThreshold.LOW)
        return [s for s, _ in results[:max_skills]]

    def get_skill_relationships(self) -> Dict[str, List[str]]:
        """Get skill relationship graph based on tags and keywords."""
        relationships = {}
        all_skills = self.loader.get_all_skills()

        for name, skill in all_skills.items():
            related = []
            for other_name, other_skill in all_skills.items():
                if name == other_name:
                    continue

                shared_tags = set(skill.tags) & set(other_skill.tags)
                if shared_tags:
                    related.append(other_name)

            relationships[name] = related

        return relationships

    def suggest_related(self, skill_name: str, max_related: int = 3) -> List[Skill]:
        """Suggest related skills for a given skill."""
        relationships = self.get_skill_relationships()
        related_names = relationships.get(skill_name, [])[:max_related]

        return [
            self.loader.get_skill(name)
            for name in related_names
            if self.loader.get_skill(name)
        ]


def select_skills(query: str, context: str = "", max_skills: int = 5) -> List[Skill]:
    """Convenience function to select skills."""
    loader = SkillLoader()
    loader.initialize()
    selector = SkillSelector(loader)
    return selector.select(query, context, max_skills)