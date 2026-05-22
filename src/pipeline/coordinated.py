"""
Coordinated Pipeline
====================
End-to-end pipeline wiring AgentCoordinator, ReportGenerator,
ContextAssembler, MemoryHub, and ExportAgent into a single workflow.

Flow:
  1. Plan blueprint → 2. Index knowledge (RAG) → 3. Research phase
  4. Report generation (hierarchical) → 5. Citation validation
  6. Formatting → 7. Export DOCX/PDF
"""

import os
import time
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field

from .base import BasePipeline, PipelineResult
from src.core.logger import get_logger
from src.core.state import DocumentState

logger = get_logger(__name__)


@dataclass
class PipelineContext:
    """Shared context across pipeline phases."""
    topic: str = ""
    document_state: Optional[DocumentState] = None
    agent_coordinator: Optional[Any] = None
    report_generator: Optional[Any] = None
    context_assembler: Optional[Any] = None
    memory_hub: Optional[Any] = None
    planner: Optional[Any] = None
    blueprint: Optional[Any] = None
    plan: Optional[Any] = None
    export_builder: Optional[Any] = None
    output_path: str = "output/output.docx"
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class CoordinatedPipeline(BasePipeline):
    """End-to-end pipeline that wires all components together."""

    def __init__(self, output_dir: str = "output"):
        super().__init__("coordinated")
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._ctx: Optional[PipelineContext] = None

    def execute(self, input_data: Any, **kwargs) -> PipelineResult:
        ctx = PipelineContext(
            topic=input_data.get("topic", "") if isinstance(input_data, dict) else str(input_data),
            output_path=input_data.get("output_path", os.path.join(self.output_dir, "output.docx"))
            if isinstance(input_data, dict) else os.path.join(self.output_dir, "output.docx"),
        )

        components = kwargs.get("components", {})
        ctx.agent_coordinator = components.get("coordinator")
        ctx.report_generator = components.get("report_generator")
        ctx.context_assembler = components.get("context_assembler")
        ctx.memory_hub = components.get("memory_hub")
        ctx.planner = components.get("planner")
        ctx.export_builder = components.get("builder")

        start = time.perf_counter()

        if not ctx.topic:
            return PipelineResult(False, error="No topic provided", execution_time=0)

        self.logger.info(f"Starting coordinated pipeline for topic: {ctx.topic}")

        phases = {
            "plan": self._run_plan,
            "research": self._run_research,
            "generate": self._run_generate,
            "validate": self._run_validate,
            "assemble_doc": self._run_assemble_doc,
            "export": self._run_export,
        }

        for phase_name, phase_fn in phases.items():
            self.logger.info(f"Phase: {phase_name}")
            if not phase_fn(ctx):
                elapsed = time.perf_counter() - start
                return PipelineResult(
                    False,
                    error=f"Phase '{phase_name}' failed",
                    data={"errors": ctx.errors, "phase": phase_name},
                    execution_time=elapsed,
                )

        elapsed = time.perf_counter() - start
        self.logger.info(f"Pipeline complete in {elapsed:.2f}s")

        return PipelineResult(
            True,
            output_path=ctx.output_path,
            data={
                "topic": ctx.topic,
                "phases_completed": list(phases.keys()),
                "output_path": ctx.output_path,
                "document_state": ctx.document_state,
                "errors": ctx.errors,
            },
            execution_time=elapsed,
        )

    def _run_plan(self, ctx: PipelineContext) -> bool:
        try:
            if ctx.planner:
                from src.agents.planner import PlannerAgent
                planner = ctx.planner if isinstance(ctx.planner, PlannerAgent) else PlannerAgent()
                result = planner.execute(ctx.topic)
                if result.success:
                    ctx.plan = result.data.get("plan")
                    ctx.blueprint = result.data.get("blueprint")
                    self.logger.info(f"Plan created: {len(ctx.plan.sections) if ctx.plan else 0} sections")
                    return True
            ctx.document_state = DocumentState(title=ctx.topic)
            return True
        except Exception as e:
            ctx.errors.append(f"plan: {e}")
            logger.warning(f"Plan phase skipped ({e})")
            ctx.document_state = DocumentState(title=ctx.topic)
            return True

    def _run_research(self, ctx: PipelineContext) -> bool:
        try:
            if ctx.context_assembler and hasattr(ctx.context_assembler, "is_ready"):
                if ctx.context_assembler.is_ready():
                    result = ctx.context_assembler.retrieve_context(ctx.topic)
                    if ctx.memory_hub and hasattr(ctx.memory_hub, "record_search"):
                        ctx.memory_hub.record_search(ctx.topic, len(result.get("chunks", [])))
                    self.logger.info(f"Research: {len(result.get('chunks', []))} chunks retrieved")
            return True
        except Exception as e:
            ctx.errors.append(f"research: {e}")
            logger.warning(f"Research phase skipped ({e})")
            return True

    def _run_generate(self, ctx: PipelineContext) -> bool:
        try:
            if ctx.report_generator:
                from src.generator.report import ReportGenerator
                gen = ctx.report_generator if isinstance(ctx.report_generator, ReportGenerator) else ReportGenerator()
                result = gen.generate_full_report(
                    topic=ctx.topic,
                    blueprint=ctx.blueprint,
                    context_assembler=ctx.context_assembler,
                    document_state=ctx.document_state,
                )
                ctx.metadata["report"] = result
                self.logger.info(f"Generated: {result.get('chapter_count', 0)} chapters, {result.get('total_words', 0)} words")

                if ctx.memory_hub and hasattr(ctx.memory_hub, "record_topics"):
                    ctx.memory_hub.record_topics(ctx.topic, result.get("full_content", ""))
                return True

            if ctx.agent_coordinator and ctx.plan:
                result = ctx.agent_coordinator.execute(
                    {"topic": ctx.topic},
                    pipeline=self, plan=ctx.plan,
                    blueprint=ctx.blueprint, output_path=ctx.output_path,
                    builder=ctx.export_builder,
                )
                ctx.metadata["coordinator_result"] = result.data
                self.logger.info("Generated via agent coordinator")
                return True

            logger.warning("No generator or coordinator available")
            return True
        except Exception as e:
            ctx.errors.append(f"generate: {e}")
            logger.warning(f"Generation phase skipped ({e})")
            return True

    def _run_validate(self, ctx: PipelineContext) -> bool:
        try:
            if ctx.memory_hub and ctx.document_state:
                validation = ctx.memory_hub.validate_document(ctx.document_state)
                ctx.document_state.validation_results = validation
                if validation.get("errors"):
                    logger.warning(f"Validation errors: {validation['errors']}")
                self.logger.info(f"Validation: {len(validation.get('errors', []))} errors, "
                              f"{len(validation.get('warnings', []))} warnings")
            return True
        except Exception as e:
            ctx.errors.append(f"validate: {e}")
            return True

    def _run_assemble_doc(self, ctx: PipelineContext) -> bool:
        try:
            if ctx.memory_hub and ctx.document_state:
                ctx.memory_hub.update_document_state(ctx.document_state)
            self.logger.info("Document state assembled")
            return True
        except Exception as e:
            ctx.errors.append(f"assemble: {e}")
            return True

    def _run_export(self, ctx: PipelineContext) -> bool:
        try:
            from src.agents.export_agent import ExportAgent
            agent = ExportAgent()
            result = agent.execute({
                "plan": ctx.plan,
                "output_path": ctx.output_path,
                "formats": ["docx"],
                "builder": ctx.export_builder,
            })
            if result.success:
                self.logger.info(f"Exported to {result.data.get('output_path', ctx.output_path)}")
                return True
            logger.warning(f"Export agent failed: {result.error}")
            return True
        except Exception as e:
            ctx.errors.append(f"export: {e}")
            logger.warning(f"Export phase skipped ({e})")
            return True
