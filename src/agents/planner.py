"""
Planner Agent Module
====================
Task planning and decomposition agent.
"""

import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from .base import BaseAgent, AgentResponse
from src.providers import BaseProvider, Message
from src.core.logger import get_logger

logger = get_logger(__name__)


class TaskComplexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class SubTask:
    """Represents a subtask in the execution plan."""
    id: str
    description: str
    depends_on: List[str] = field(default_factory=list)
    skills_required: List[str] = field(default_factory=list)
    estimated_time: float = 0.0


@dataclass
class ExecutionPlan:
    """Complete execution plan for a task."""
    task: str
    complexity: TaskComplexity
    subtasks: List[SubTask]
    total_estimated_time: float = 0.0
    parallel_execution: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def get_execution_order(self) -> List[SubTask]:
        """Get subtasks in topological order."""
        executed = set()
        ordered = []

        while len(executed) < len(self.subtasks):
            for subtask in self.subtasks:
                if subtask.id in executed:
                    continue
                if all(dep in executed for dep in subtask.depends_on):
                    ordered.append(subtask)
                    executed.add(subtask.id)

        return ordered

    def to_dict(self) -> Dict:
        return {
            "task": self.task,
            "complexity": self.complexity.value,
            "subtasks": [
                {
                    "id": s.id,
                    "description": s.description,
                    "depends_on": s.depends_on,
                    "skills_required": s.skills_required,
                    "estimated_time": s.estimated_time
                }
                for s in self.subtasks
            ],
            "total_estimated_time": self.total_estimated_time,
            "parallel_execution": self.parallel_execution
        }


class PlannerAgent(BaseAgent):
    """Agent for task planning and decomposition."""

    def __init__(self, provider: Optional[BaseProvider] = None):
        super().__init__("planner", provider)

    def execute(self, input_data: Any, **kwargs) -> AgentResponse:
        """Create execution plan for a task."""
        if isinstance(input_data, str):
            task = input_data
        elif isinstance(input_data, dict):
            task = input_data.get('task', '')
        else:
            return self._create_response(False, error="Invalid input")

        if not task:
            return self._create_response(False, error="No task provided")

        try:
            plan = self._create_plan(task)
            return self._create_response(
                success=True,
                data=plan.to_dict(),
                metadata={'subtask_count': len(plan.subtasks)}
            )

        except Exception as e:
            self._log_error("planning", e)
            return self._create_response(False, error=str(e))

    def _create_plan(self, task: str) -> ExecutionPlan:
        """Create execution plan using LLM or fallback."""
        if self.provider and self.provider.is_available():
            try:
                return self._llm_plan(task)
            except Exception as e:
                logger.warning(f"LLM planning failed: {e}, using fallback")

        return self._fallback_plan(task)

    def _llm_plan(self, task: str) -> ExecutionPlan:
        """Use LLM to create execution plan."""
        prompt = f"""Create an execution plan for this task: {task}

Provide a JSON response with:
- "complexity": "simple", "medium", or "complex"
- "subtasks": Array of objects with:
  - "id": subtask identifier
  - "description": what to do
  - "depends_on": array of IDs this depends on
  - "skills_required": array of skill names needed
- "total_estimated_time": in seconds
- "parallel_execution": true/false

Return ONLY valid JSON."""

        messages = [
            Message(role="system", content="You create task execution plans."),
            Message(role="user", content=prompt)
        ]

        response = self.provider.chat(messages)
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)

        if json_match:
            data = json.loads(json_match.group())
            complexity = TaskComplexity(data.get('complexity', 'medium'))

            subtasks = [
                SubTask(
                    id=s['id'],
                    description=s['description'],
                    depends_on=s.get('depends_on', []),
                    skills_required=s.get('skills_required', [])
                )
                for s in data.get('subtasks', [])
            ]

            return ExecutionPlan(
                task=task,
                complexity=complexity,
                subtasks=subtasks,
                total_estimated_time=data.get('total_estimated_time', 10.0),
                parallel_execution=data.get('parallel_execution', False)
            )

        raise ValueError("Failed to parse plan from LLM")

    def _fallback_plan(self, task: str) -> ExecutionPlan:
        """Create a basic fallback plan."""
        return ExecutionPlan(
            task=task,
            complexity=TaskComplexity.MEDIUM,
            subtasks=[
                SubTask(
                    id="understand",
                    description="Understand task requirements",
                    skills_required=["docx"]
                ),
                SubTask(
                    id="generate",
                    description="Generate report content",
                    skills_required=["docx"]
                ),
                SubTask(
                    id="export",
                    description="Export to required format",
                    skills_required=["pdf"]
                )
            ],
            total_estimated_time=30.0,
            parallel_execution=False
        )

    def estimate_time(self, plan: ExecutionPlan) -> float:
        """Estimate total execution time."""
        return sum(s.estimated_time for s in plan.subtasks)

    def can_parallelize(self, plan: ExecutionPlan) -> bool:
        """Check if plan can be parallelized."""
        return plan.parallel_execution