"""
Agent Factory Module
====================
Factory for creating and managing agents.
"""

from typing import Dict, Type, Optional
from .base import BaseAgent
from .orchestrator import OrchestratorAgent
from src.core.constants import ExecutionMode
from .planner import PlannerAgent
from .editor import EditorAgent
from src.providers import BaseProvider
from src.core.logger import get_logger

logger = get_logger(__name__)


class AgentFactory:
    """Factory for creating and managing agents."""

    _agents: Dict[str, BaseAgent] = {}
    _registry: Dict[str, Type[BaseAgent]] = {
        "orchestrator": OrchestratorAgent,
        "planner": PlannerAgent,
        "editor": EditorAgent,
    }

    @classmethod
    def register(cls, name: str, agent_class: Type[BaseAgent]):
        """Register a new agent type."""
        cls._registry[name.lower()] = agent_class
        logger.info(f"Registered agent: {name}")

    @classmethod
    def create(
        cls,
        agent_type: str,
        provider: Optional[BaseProvider] = None,
        **kwargs
    ) -> BaseAgent:
        """Create an agent by type."""
        provider_repr = repr(provider) if provider else "none"
        key = f"{agent_type}_{provider_repr}"

        if key not in cls._agents:
            if agent_type.lower() not in cls._registry:
                raise ValueError(f"Unknown agent type: {agent_type}")

            agent_class = cls._registry[agent_type.lower()]
            cls._agents[key] = agent_class(provider=provider, **kwargs)
            logger.info(f"Created agent: {agent_type}")

        return cls._agents[key]

    @classmethod
    def create_orchestrator(
        cls,
        mode: ExecutionMode = ExecutionMode.SCRATCH,
        template_path: Optional[str] = None,
        provider: Optional[BaseProvider] = None
    ) -> OrchestratorAgent:
        """Create an orchestrator agent."""
        return OrchestratorAgent(
            provider=provider,
            execution_mode=mode,
            template_path=template_path
        )

    @classmethod
    def create_planner(cls, provider: Optional[BaseProvider] = None) -> PlannerAgent:
        """Create a planner agent."""
        return PlannerAgent(provider=provider)

    @classmethod
    def create_editor(cls, provider: Optional[BaseProvider] = None) -> EditorAgent:
        """Create an editor agent."""
        return EditorAgent(provider=provider)

    @classmethod
    def create_coordinator(cls, provider: Optional[BaseProvider] = None) -> BaseAgent:
        """Create an AgentCoordinator with default agents injected."""
        from .research import ResearchAgent
        from .writing import WritingAgent
        from .citation import CitationAgent
        from .formatting_agent import FormattingAgent
        from .export_agent import ExportAgent
        from .coordinator import AgentCoordinator
        agents = {
            "research": ResearchAgent(provider=provider),
            "writing": WritingAgent(provider=provider),
            "citation": CitationAgent(provider=provider),
            "formatting": FormattingAgent(provider=provider),
            "export": ExportAgent(provider=provider),
        }
        return AgentCoordinator(agents=agents, provider=provider)

    @classmethod
    def get_agent(cls, name: str) -> Optional[BaseAgent]:
        """Get an existing agent by name."""
        for agent in cls._agents.values():
            if agent.name == name:
                return agent
        return None

    @classmethod
    def clear_cache(cls):
        """Clear agent cache."""
        cls._agents.clear()
        logger.info("Cleared agent cache")