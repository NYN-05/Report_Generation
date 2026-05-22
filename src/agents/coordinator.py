"""
Agent Coordinator
=================
Dependency-aware orchestration of all agents for end-to-end report generation.
"""

from typing import Any, Dict, Optional, List
from .base import BaseAgent, AgentResponse
from .research import ResearchAgent
from .writing import WritingAgent
from .citation import CitationAgent
from .formatting_agent import FormattingAgent
from .export_agent import ExportAgent
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
    """Orchestrates all agents with dependency-aware execution.

    Execution Order:
    1. ResearchAgent  — gather knowledge via RAG
    2. PlannerAgent   — create report structure (delegates to AIReportPlanner)
    3. WritingAgent   — generate section content with evidence
    4. CitationAgent  — validate citations and build bibliography
    5. FormattingAgent— ensure IEEE formatting compliance
    6. ExportAgent    — generate DOCX/PDF
    """

    def __init__(self, provider=None):
        super().__init__("coordinator", provider)
        self.agents: Dict[str, BaseAgent] = {}
        self._init_agents()

    def _init_agents(self):
        self.agents["research"] = ResearchAgent(provider=self.provider)
        self.agents["writing"] = WritingAgent(provider=self.provider)
        self.agents["citation"] = CitationAgent(provider=self.provider)
        self.agents["formatting"] = FormattingAgent(provider=self.provider)
        self.agents["export"] = ExportAgent(provider=self.provider)

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

    def execute(self, input_data: Any, **kwargs) -> AgentResponse:
        if not isinstance(input_data, dict):
            return self._create_response(False, error="Input must be a dict")

        topic = input_data.get("topic", "")
        pipeline = kwargs.get("pipeline")
        plan = kwargs.get("plan")
        blueprint = kwargs.get("blueprint")

        if not topic:
            return self._create_response(False, error="No topic provided")

        phases = {
            "research": {"status": "pending", "result": None},
            "writing": {"status": "pending", "result": None},
            "citation": {"status": "pending", "result": None},
            "formatting": {"status": "pending", "result": None},
            "export": {"status": "pending", "result": None},
        }

        project_evidence = {}

        if "research" in self.agents:
            try:
                research = self.agents["research"]
                ctx = research.retrieve_for_section(topic, "overview")
                project_evidence["knowledge"] = ctx
                phases["research"]["status"] = "completed"
                phases["research"]["result"] = ctx
                self._log_info(f"Research: gathered {ctx.get('total_chunks', 0)} evidence chunks")
            except Exception as e:
                phases["research"]["status"] = "failed"
                self._log_error("research phase", e)

        if "writing" in self.agents and plan:
            try:
                writing = self.agents["writing"]
                context_text = project_evidence.get("knowledge", {}).get("context_text", "")
                total_sections = 0
                for sec in plan.sections:
                    if sec.blueprint_section_id in ("cover_page", "references", "appendices"):
                        continue
                    if sec.content:
                        total_sections += 1

                for sec in plan.sections:
                    sec_context = context_text
                    if sec.blueprint_section_id == "chapters" or not sec.content:
                        research_agent = self.agents.get("research")
                        if research_agent:
                            ctx = research_agent.retrieve_for_section(topic, sec.heading)
                            sec_context = ctx.get("context_text", context_text)

                    if sec_context:
                        sec.retrieval_context = sec_context

                phases["writing"]["status"] = "completed"
                phases["writing"]["result"] = {"sections_processed": total_sections}
                self._log_info(f"Writing: processed {total_sections} sections with evidence")
            except Exception as e:
                phases["writing"]["status"] = "failed"
                self._log_error("writing phase", e)

        if "citation" in self.agents and plan:
            try:
                citation = self.agents["citation"]
                all_content = "\n\n".join(s.content for s in plan.sections if s.content)
                result = citation.execute({
                    "content": all_content,
                    "references": plan.references or [],
                })
                phases["citation"]["status"] = "completed"
                phases["citation"]["result"] = result.data
                issues = result.data.get("issues", [])
                if issues:
                    logger.warning(f"Citation issues: {issues}")
            except Exception as e:
                phases["citation"]["status"] = "failed"
                self._log_error("citation phase", e)

        if "formatting" in self.agents and plan:
            try:
                formatting = self.agents["formatting"]
                sections_data = [
                    {"heading": s.heading, "content": s.content, "level": s.level}
                    for s in plan.sections
                ]
                result = formatting.execute({"sections": sections_data})
                phases["formatting"]["status"] = "completed"
                phases["formatting"]["result"] = result.data
            except Exception as e:
                phases["formatting"]["status"] = "failed"
                self._log_error("formatting phase", e)

        if "export" in self.agents and pipeline:
            try:
                export = self.agents["export"]
                output_path = kwargs.get("output_path", "output/output.docx")
                builder = kwargs.get("builder")
                result = export.execute({
                    "plan": plan, "output_path": output_path,
                    "formats": ["docx", "pdf"],
                    "builder": builder,
                })
                phases["export"]["status"] = "completed"
                phases["export"]["result"] = result.data
            except Exception as e:
                phases["export"]["status"] = "failed"
                self._log_error("export phase", e)

        any_failed = any(p["status"] == "failed" for p in phases.values())
        return self._create_response(
            not any_failed,
            data={
                "topic": topic,
                "phases": phases,
                "summary": {k: v["status"] for k, v in phases.items()},
            },
        )

    def get_agent_status(self) -> Dict[str, bool]:
        return {name: agent.is_available() for name, agent in self.agents.items()}
