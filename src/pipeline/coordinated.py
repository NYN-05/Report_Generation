"""
Coordinated Pipeline
====================
End-to-end pipeline wiring AgentCoordinator, ReportGenerator,
ContextAssembler, MemoryHub, ReviewPipeline, and ExportAgent.

Flow:
  1. Plan blueprint → 2. Index knowledge (RAG) → 3. Research phase
  4. Report generation (hierarchical) → 5. Review & citation validation
  6. Formatting → 7. Export DOCX/PDF
"""

import asyncio
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from .base import BasePipeline, PipelineResult
from src.core.logger import get_logger
from src.core.state import DocumentState
from src.core.events import EventBus, PHASE_STARTED, PHASE_COMPLETED, PHASE_FAILED
from src.core.errors import RecoverableError, PhaseError

logger = get_logger(__name__)


PHASE_ORDER = ["plan", "research", "generate", "review", "validate", "assemble_doc", "export"]

ALL_PHASES = set(PHASE_ORDER)


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
    review_pipeline: Optional[Any] = None
    blueprint: Optional[Any] = None
    plan: Optional[Any] = None
    export_builder: Optional[Any] = None
    output_path: str = "output/output.docx"
    formats: List[str] = field(default_factory=lambda: ["docx"])
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    event_bus: Optional[EventBus] = None


ProgressCallback = Callable[[str, str], None]


class CoordinatedPipeline(BasePipeline):
    """End-to-end pipeline that wires all components together.

    Supports:
    - Selective phase execution via ``phases`` kwarg
    - Progress callbacks via ``callback`` kwarg
    - Async execution via ``execute_async``
    - All phases gracefully fall back on missing components
    """

    def __init__(self, output_dir: str = "output"):
        super().__init__("coordinated")
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def execute(self, input_data: Any, **kwargs) -> PipelineResult:
        return self._execute_sync(input_data, **kwargs)

    async def execute_async(self, input_data: Any, **kwargs) -> PipelineResult:
        return await asyncio.to_thread(self._execute_sync, input_data, **kwargs)

    def _execute_sync(self, input_data: Any, **kwargs) -> PipelineResult:
        ctx = self._build_context(input_data, kwargs)
        if not ctx.topic:
            return PipelineResult(False, error="No topic provided", execution_time=0)

        selected = self._resolve_phases(kwargs)

        self.logger.info(f"[{ctx.topic}] phases={list(selected.keys())}")

        start = time.perf_counter()
        for phase_name, phase_fn in selected.items():
            ctx.event_bus.emit(PHASE_STARTED, phase=phase_name)
            self.logger.info(f"[{phase_name}]")
            try:
                ok = phase_fn(ctx)
            except RecoverableError as e:
                ctx.errors.append(str(e))
                logger.warning(f"[{phase_name}] Recoverable: {e}")
                ctx.event_bus.emit(PHASE_COMPLETED, phase=phase_name)
                continue
            except PhaseError as e:
                ctx.errors.append(str(e))
                logger.error(f"[{phase_name}] Fatal: {e}")
                ctx.event_bus.emit(PHASE_FAILED, phase=phase_name)
                elapsed = time.perf_counter() - start
                return PipelineResult(
                    False, error=f"Phase '{phase_name}' failed: {e}",
                    data={"errors": ctx.errors, "phase": phase_name},
                    execution_time=elapsed,
                )
            if not ok:
                ctx.event_bus.emit(PHASE_FAILED, phase=phase_name)
                elapsed = time.perf_counter() - start
                return PipelineResult(
                    False, error=f"Phase '{phase_name}' returned failure",
                    data={"errors": ctx.errors, "phase": phase_name},
                    execution_time=elapsed,
                )
            ctx.event_bus.emit(PHASE_COMPLETED, phase=phase_name)

        elapsed = time.perf_counter() - start
        self.logger.info(f"Pipeline complete in {elapsed:.2f}s")

        return PipelineResult(
            True, output_path=ctx.output_path,
            data={
                "topic": ctx.topic,
                "phases_completed": list(selected.keys()),
                "output_path": ctx.output_path,
                "document_state": ctx.document_state,
                "errors": ctx.errors,
            },
            execution_time=elapsed,
        )

    def _build_context(self, input_data: Any, kwargs: dict) -> PipelineContext:
        topic = input_data.get("topic", "") if isinstance(input_data, dict) else str(input_data)
        bus = kwargs.get("event_bus")
        ctx = PipelineContext(
            topic=topic,
            output_path=input_data.get("output_path", os.path.join(self.output_dir, "output.docx"))
            if isinstance(input_data, dict) else os.path.join(self.output_dir, "output.docx"),
            formats=input_data.get("formats", ["docx"]),
            event_bus=bus or EventBus(),
        )
        comp = kwargs.get("components", {})
        ctx.agent_coordinator = comp.get("coordinator")
        ctx.report_generator = comp.get("report_generator")
        ctx.context_assembler = comp.get("context_assembler")
        ctx.memory_hub = comp.get("memory_hub")
        ctx.planner = comp.get("planner")
        ctx.review_pipeline = comp.get("review_pipeline")
        ctx.export_builder = comp.get("builder")
        if kwargs.get("callback") and ctx.event_bus:
            cb = kwargs["callback"]
            def _make_cb(status_val):
                return lambda phase, **kw: cb(phase, status_val)
            ctx.event_bus.on(PHASE_STARTED, _make_cb("started"))
            ctx.event_bus.on(PHASE_COMPLETED, _make_cb("completed"))
            ctx.event_bus.on(PHASE_FAILED, _make_cb("failed"))
        return ctx

    def _resolve_phases(self, kwargs: dict) -> Dict[str, Callable]:
        allowed = kwargs.get("phases")
        phase_map: Dict[str, Callable] = {
            "plan": self._run_plan,
            "research": self._run_research,
            "generate": self._run_generate,
            "review": self._run_review,
            "validate": self._run_validate,
            "assemble_doc": self._run_assemble_doc,
            "export": self._run_export,
        }
        if allowed:
            allowed_set = set(allowed)
            return {k: v for k, v in phase_map.items() if k in allowed_set}
        return phase_map

    # ------------------------------------------------------------------ #
    #  Phase implementations
    # ------------------------------------------------------------------ #

    def _run_plan(self, ctx: PipelineContext) -> bool:
        if ctx.planner:
            from src.agents.planner import PlannerAgent
            planner = ctx.planner if isinstance(ctx.planner, PlannerAgent) else PlannerAgent()
            result = planner.execute(ctx.topic)
            if result.success:
                ctx.plan = result.data.get("plan")
                ctx.blueprint = result.data.get("blueprint")
                self.logger.info(f"Plan: {len(ctx.plan.sections) if ctx.plan else 0} sections")
                return True
            raise RecoverableError("plan", "Planner returned no success")
        ctx.document_state = DocumentState(title=ctx.topic)
        return True

    def _run_research(self, ctx: PipelineContext) -> bool:
        if ctx.context_assembler and ctx.context_assembler.is_ready():
            result = ctx.context_assembler.retrieve_context(ctx.topic)
            self.logger.info(f"Research: {len(result.get('chunks', []))} chunks")
        return True

    def _run_generate(self, ctx: PipelineContext) -> bool:
        if ctx.report_generator:
            from src.generator.report import ReportGenerator
            gen = ctx.report_generator if isinstance(ctx.report_generator, ReportGenerator) else ReportGenerator()
            result = gen.generate_full_report(
                topic=ctx.topic, blueprint=ctx.blueprint,
                context_assembler=ctx.context_assembler,
                document_state=ctx.document_state,
            )
            ctx.metadata["report"] = result
            self.logger.info(f"Generated: {result.get('chapter_count', 0)} chapters, "
                          f"{result.get('total_words', 0)} words")
            if ctx.memory_hub and hasattr(ctx.memory_hub, "process_section"):
                ctx.memory_hub.process_section(result.get("full_content", ""), "report")
            return True

        if ctx.agent_coordinator and ctx.plan:
            result = ctx.agent_coordinator.execute(
                {"topic": ctx.topic},
                plan=ctx.plan, output_path=ctx.output_path,
                builder=ctx.export_builder,
            )
            ctx.metadata["coordinator_result"] = result.data
            self.logger.info("Generated via coordinator")
            return True

        raise RecoverableError("generate", "No generator or coordinator available")

    def _run_review(self, ctx: PipelineContext) -> bool:
        pipeline = ctx.review_pipeline
        if pipeline is None:
            from src.review.pipeline import ReviewPipeline
            pipeline = ReviewPipeline()
        if ctx.plan and hasattr(ctx.plan, "sections"):
            sections = [{"heading": s.heading, "content": s.content}
                        for s in ctx.plan.sections if s.content]
            if sections:
                result = pipeline.review_sections(sections)
                ctx.metadata["review"] = result
                self.logger.info(f"Review: {'PASS' if result.get('passed') else 'ISSUES'} "
                              f"({result.get('total_issues', 0)} issues)")
                if not result.get("passed"):
                    for name, r in result.get("results", {}).items():
                        for issue in r.get("issues", []):
                            ctx.errors.append(f"review.{name}: {issue.get('message', '')}")
        return True

    def _run_validate(self, ctx: PipelineContext) -> bool:
        if ctx.memory_hub and ctx.document_state:
            if hasattr(ctx.memory_hub, "validate_document"):
                validation = ctx.memory_hub.validate_document(ctx.document_state)
                ctx.document_state.validation_results = validation
                self.logger.info(f"Validation: {len(validation.get('errors', []))} err, "
                              f"{len(validation.get('warnings', []))} warn")
        if ctx.memory_hub:
            ctx.memory_hub.save()
        return True

    def _run_assemble_doc(self, ctx: PipelineContext) -> bool:
        self._ensure_document_state(ctx)
        self.logger.info("Document state assembled")
        return True

    def _ensure_document_state(self, ctx: PipelineContext):
        if ctx.document_state is None:
            ctx.document_state = DocumentState(title=ctx.topic)
        if ctx.memory_hub and hasattr(ctx.memory_hub, "get_status"):
            ctx.document_state.style_profile = ctx.memory_hub.get_status().get("style_profile", {})

    def _run_export(self, ctx: PipelineContext) -> bool:
        try:
            plan = ctx.plan or self._make_fallback_plan(ctx)
            from src.agents.export_agent import ExportAgent
            agent = ExportAgent()
            result = agent.execute({
                "plan": plan,
                "output_path": ctx.output_path,
                "formats": ctx.formats,
                "builder": ctx.export_builder,
            })
            if result.success:
                self.logger.info(f"Exported to {ctx.output_path}")
            else:
                logger.warning(f"Export issues: {result.error}")
            return True
        except Exception as e:
            ctx.errors.append(f"export: {e}")
            logger.warning(f"Export skipped ({e})")
            return True

    @staticmethod
    def _make_fallback_plan(ctx: PipelineContext):
        """Build a minimal plan object from the report generator output."""
        report = ctx.metadata.get("report", {})
        if not report or not report.get("chapters"):
            return None

        class _Section:
            def __init__(self, heading, content):
                self.heading = heading
                self.content = content
                self.blueprint_section_id = "chapters"
                self.level = 1

        class _FallbackPlan:
            def __init__(self, chapters):
                self.sections = [_Section(ch.get("heading", "Chapter"), ch.get("content", ""))
                                 for ch in chapters]
                self.references = []

        return _FallbackPlan(report.get("chapters", []))
