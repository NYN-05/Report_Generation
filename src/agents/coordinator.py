"""
Agent Coordinator
=================
Pure agent management — agents are injected via constructor or register_agent().
No hardcoded imports. No concrete agent instantiation.
"""

from typing import Any, Dict, Optional, List
from .base import BaseAgent, AgentResponse
from src.core.logger import get_logger

logger = get_logger(__name__)

AGENT_PHASES = [
    "research",
    "planning",
    "writing",
    "citation",
    "formatting",
    "export",
]


class AgentCoordinator(BaseAgent):
    """Manages a set of injectable agents with dependency resolution.

    No concrete agent classes are imported. Agents must be provided via:
      - constructor (``agents`` dict)
      - ``register_agent(name, agent)``

    Execution Order:
      1. ResearchAgent  2. PlannerAgent  3. WritingAgent
      4. CitationAgent  5. FormattingAgent  6. ExportAgent
    """

    def __init__(self, agents: Optional[Dict[str, BaseAgent]] = None, provider=None):
        super().__init__("coordinator", provider)
        self.agents: Dict[str, BaseAgent] = agents or {}

    def register_agent(self, name: str, agent: BaseAgent):
        self.agents[name] = agent

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self.agents.get(name)

    def set_context_assembler(self, context_assembler):
        research = self.agents.get("research")
        if research and hasattr(research, "set_context_assembler"):
            research.set_context_assembler(context_assembler)

    def set_prompt_builder(self, prompt_builder):
        writing = self.agents.get("writing")
        if writing and hasattr(writing, "set_prompt_builder"):
            writing.set_prompt_builder(prompt_builder)

    def set_context_assembler(self, context_assembler):
        research = self.agents.get("research")
        if research and hasattr(research, "set_context_assembler"):
            research.set_context_assembler(context_assembler)

    def set_prompt_builder(self, prompt_builder):
        writing = self.agents.get("writing")
        if writing and hasattr(writing, "set_prompt_builder"):
            writing.set_prompt_builder(prompt_builder)

    def execute(self, input_data: Any, **kwargs) -> AgentResponse:
        """Run each registered agent in AGENT_PHASES order.

        This is a simple sequential delegation. The CoordinatedPipeline
        is the primary orchestrator; this method exists for direct agent
        invocation without the full pipeline.
        """
        if not isinstance(input_data, dict):
            return self._create_response(False, error="Input must be a dict")

        topic = input_data.get("topic", "")
        if not topic:
            return self._create_response(False, error="No topic provided")

        plan = kwargs.get("plan")
        results = {}

        for phase in AGENT_PHASES:
            agent = self.agents.get(phase)
            if not agent:
                continue
            if phase == "research":
                agent_input = {"topic": topic, "section": input_data.get("section", "overview")}
            elif phase == "writing":
                agent_input = {"topic": topic, "sections": getattr(plan, "sections", []) if plan else []}
            elif phase == "citation":
                content = "\n\n".join(s.content for s in plan.sections) if plan and hasattr(plan, "sections") else ""
                agent_input = {"content": content, "references": getattr(plan, "references", []) if plan else []}
            elif phase == "formatting":
                sections = [{"heading": s.heading, "content": s.content, "level": s.level}
                            for s in getattr(plan, "sections", [])] if plan else []
                agent_input = {"sections": sections}
            elif phase == "export":
                agent_input = {
                    "plan": plan,
                    "output_path": kwargs.get("output_path", "output/output.docx"),
                    "formats": ["docx"],
                    "builder": kwargs.get("builder"),
                }
            else:
                agent_input = {"topic": topic}

            try:
                result = agent.execute(agent_input)
                results[phase] = {"status": "completed" if result.success else "failed", "data": result.data}
            except Exception as e:
                results[phase] = {"status": "failed", "error": str(e)}

        any_failed = any(r["status"] == "failed" for r in results.values())
        return self._create_response(
            not any_failed,
            data={"topic": topic, "results": results, "summary": {k: v["status"] for k, v in results.items()}},
        )

    def get_agent_status(self) -> Dict[str, bool]:
        return {name: agent.is_available() for name, agent in self.agents.items()}
