"""
Skill Orchestrator Module
==========================
Skill execution coordination.
"""

from typing import List, Dict, Any, Optional
from .base import Skill, SkillResult
from .registry import SkillRegistry
from src.core.logger import get_logger

logger = get_logger(__name__)


class SkillChain:
    """Represents a chain of skills to execute."""

    def __init__(self):
        self.skills: List[Skill] = []
        self.execution_order: List[int] = []

    def add_skill(self, skill: Skill, position: int = -1):
        """Add a skill to the chain."""
        if position < 0:
            self.skills.append(skill)
        else:
            self.skills.insert(position, skill)
        self._update_order()

    def _update_order(self):
        """Update execution order based on dependencies."""
        self.execution_order = list(range(len(self.skills)))

    def get_execution_order(self) -> List[Skill]:
        """Get skills in execution order."""
        return [self.skills[i] for i in self.execution_order]

    def __len__(self) -> int:
        return len(self.skills)

    def __repr__(self) -> str:
        return f"SkillChain({[s.name for s in self.skills]})"


class SkillOrchestrator:
    """Coordinates skill execution based on task requirements."""

    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry or SkillRegistry()
        self.registry.initialize()

    def prepare_for_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        max_skills: int = 5
    ) -> SkillChain:
        """Prepare a skill chain for a task."""
        skills = self.registry.find_for_task(task, context or {}, max_skills)

        chain = SkillChain()
        for skill in skills:
            chain.add_skill(skill)

        logger.info(f"Prepared skill chain for task: {chain}")
        return chain

    def execute_chain(
        self,
        chain: SkillChain,
        context: Dict[str, Any],
        merge_results: bool = True
    ) -> Dict[str, Any]:
        """Execute a skill chain and merge results."""
        results = {}
        accumulated_context = context.copy()

        for skill in chain.get_execution_order():
            logger.info(f"Executing skill: {skill.name}")

            try:
                skill_context = accumulated_context.copy()
                result = self._execute_skill(skill, skill_context)

                results[skill.name] = result

                if result.success and merge_results:
                    if isinstance(result.output, dict):
                        accumulated_context.update(result.output)

                logger.info(f"Skill {skill.name} completed: {result.success}")

            except Exception as e:
                logger.error(f"Skill {skill.name} failed: {e}")
                results[skill.name] = SkillResult(
                    success=False,
                    error=str(e)
                )

        return {
            "chain": chain,
            "results": results,
            "merged_context": accumulated_context
        }

    def _execute_skill(self, skill: Skill, context: Dict[str, Any]) -> SkillResult:
        """Execute a single skill (placeholder for actual execution)."""
        return SkillResult(
            success=True,
            output={"executed": skill.name, "content": skill.content[:500]},
            metadata={"skill": skill.name}
        )

    def get_skill_context(
        self,
        skills: List[Skill],
        max_length: int = 1500
    ) -> str:
        """Build context string from skill contents."""
        if not skills:
            return ""

        skill_parts = []
        for skill in skills:
            content = self.registry.get_skill_content(skill.name, max_length)
            if content:
                skill_parts.append(f"## {skill.name}\n{content}")

        return "\n\n---\n\n".join(skill_parts)

    def explain_chain(self, chain: SkillChain, task: str) -> str:
        """Generate explanation of skill chain."""
        explanation = f"Task: {task}\n\n"
        explanation += f"Selected {len(chain)} skill(s):\n\n"

        for i, skill in enumerate(chain.get_execution_order(), 1):
            explanation += f"{i}. **{skill.name}**\n"
            explanation += f"   - {skill.description[:100]}...\n"
            explanation += f"   - Tags: {', '.join(skill.tags[:3])}\n\n"

        return explanation


def orchestrate_skills(
    task: str,
    context: Dict[str, Any],
    max_skills: int = 5
) -> Dict[str, Any]:
    """Convenience function to orchestrate skills for a task."""
    orchestrator = SkillOrchestrator()
    chain = orchestrator.prepare_for_task(task, context, max_skills)
    return orchestrator.execute_chain(chain, context)