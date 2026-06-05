"""
Coordinated Pipeline
====================
End-to-end pipeline wiring AgentCoordinator, ReportGenerator,
ContextAssembler, MemoryHub, ReviewPipeline, and ExportAgent.

Evidence-Centric Flow:
  1. resource_intel → 2. fact_extraction → 3. evidence_graph
  4. evidence_blueprint → 5. coverage_analysis → 6. generation_constraints
  7. evidence_generation → 8. hallucination_check → 9. review
  10. traceability → 11. quality_gate → 12. assemble_doc → 13. export
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


PHASE_ORDER = [
    "resource_intel", "fact_extraction", "evidence_graph",
    "evidence_blueprint", "coverage_analysis", "generation_constraints",
    "evidence_generation", "hallucination_check", "review",
    "traceability", "quality_gate", "assemble_doc", "export",
]

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
    knowledge_driven_generator: Optional[Any] = None
    knowledge_graph: Optional[Any] = None
    domain_classifier: Optional[Any] = None
    fact_memory: Optional[Any] = None
    chapter_summaries: Optional[Any] = None
    hierarchical_memory: Optional[Any] = None
    example_library: Optional[Any] = None
    retrieval_cache: Optional[Any] = None
    context_cache: Optional[Any] = None
    output_path: str = "output/output.docx"
    formats: List[str] = field(default_factory=lambda: ["docx"])
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    event_bus: Optional[EventBus] = None

    evidence_orchestrator: Optional[Any] = None
    fact_store: Optional[Any] = None
    coverage_engine: Optional[Any] = None
    generation_constraints: Optional[Any] = None
    evidence_blueprint: Optional[Any] = None
    traceability_map: Optional[Any] = None
    hallucination_detector: Optional[Any] = None
    fusion_engine: Optional[Any] = None
    resource_analyses: Dict[str, Any] = field(default_factory=dict)
    evidence_prompt_map: Dict[str, str] = field(default_factory=dict)
    coverage_report: Optional[Any] = None
    evidence_quality_report: Optional[Any] = None


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
        ctx.knowledge_driven_generator = comp.get("knowledge_generator")
        ctx.knowledge_graph = comp.get("knowledge_graph")
        ctx.domain_classifier = comp.get("domain_classifier")
        ctx.fact_memory = comp.get("fact_memory")
        ctx.chapter_summaries = comp.get("chapter_summaries")
        ctx.hierarchical_memory = comp.get("hierarchical_memory")
        ctx.example_library = comp.get("example_library")
        ctx.retrieval_cache = comp.get("retrieval_cache")
        ctx.context_cache = comp.get("context_cache")

        ctx.evidence_orchestrator = comp.get("evidence_orchestrator")
        ctx.fact_store = comp.get("fact_store")
        ctx.coverage_engine = comp.get("coverage_engine")
        ctx.fusion_engine = comp.get("fusion_engine")
        ctx.hallucination_detector = comp.get("hallucination_detector")
        if kwargs.get("callback") and ctx.event_bus:
            import functools
            cb = kwargs["callback"]
            ctx.event_bus.on(PHASE_STARTED, functools.partial(cb, status="started"))
            ctx.event_bus.on(PHASE_COMPLETED, functools.partial(cb, status="completed"))
            ctx.event_bus.on(PHASE_FAILED, functools.partial(cb, status="failed"))
        return ctx

    def _resolve_phases(self, kwargs: dict) -> Dict[str, Callable]:
        allowed = kwargs.get("phases")
        phase_map: Dict[str, Callable] = {
            "plan": self._run_plan,
            "research": self._run_research,
            "knowledge": self._run_knowledge,
            "generate": self._run_generate,
            "review": self._run_review,
            "validate": self._run_validate,
            "refine": self._run_refine,
            "assemble_doc": self._run_assemble_doc,
            "quality_gate": self._run_quality_gate,
            "export": self._run_export,
            "resource_intel": self._run_resource_intel,
            "fact_extraction": self._run_fact_extraction,
            "evidence_graph": self._run_evidence_graph,
            "evidence_blueprint": self._run_evidence_blueprint,
            "coverage_analysis": self._run_coverage_analysis,
            "generation_constraints": self._run_generation_constraints,
            "evidence_generation": self._run_evidence_generation,
            "hallucination_check": self._run_hallucination_check,
            "traceability": self._run_traceability,
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
            ctx.metadata["retrieved_chunks"] = result.get("chunks", [])
            self.logger.info(f"Research: {len(result.get('chunks', []))} chunks")
        return True

    def _run_knowledge(self, ctx: PipelineContext) -> bool:
        if ctx.knowledge_driven_generator:
            chunks = ctx.metadata.get("retrieved_chunks", [])
            if not chunks and ctx.context_assembler and ctx.context_assembler.is_ready():
                result = ctx.context_assembler.retrieve_context(ctx.topic)
                chunks = result.get("chunks", [])
            research_data = ctx.knowledge_driven_generator.research_phase(ctx.topic, chunks)
            ctx.metadata["research"] = research_data
            self.logger.info(
                f"Knowledge phase: domain={research_data.get('domain')}, "
                f"facts={research_data.get('facts_extracted', 0)}, "
                f"concepts={research_data.get('knowledge_graph', {}).get('node_count', 0)}"
            )
        return True

    def _run_generate(self, ctx: PipelineContext) -> bool:
        if ctx.knowledge_driven_generator:
            from src.generator.knowledge_driven_generator import KnowledgeDrivenReportGenerator
            gen = ctx.knowledge_driven_generator
            if not isinstance(gen, KnowledgeDrivenReportGenerator):
                gen = KnowledgeDrivenReportGenerator(
                    provider=getattr(ctx.report_generator, '_provider', None)
                    if ctx.report_generator else None,
                    context_assembler=ctx.context_assembler,
                )
            result = gen.generate_full_report(topic=ctx.topic)
            ctx.metadata["report"] = result
            sections = result.get("section_contents", [])
            self.logger.info(
                f"[KnowledgeDriven] Generated: {result.get('section_count', 0)} sections, "
                f"{result.get('total_words', 0)} words, "
                f"{result.get('total_facts', 0)} facts, "
                f"validations passed: {result.get('all_validations_passed', False)}"
            )
            return True

        if ctx.report_generator:
            from src.generator import ReportGenerator
            gen = ctx.report_generator if isinstance(ctx.report_generator, ReportGenerator) else ReportGenerator(
                context_assembler=ctx.context_assembler,
            )
            result = gen.generate_full_report(
                topic=ctx.topic, blueprint=ctx.blueprint,
                context_assembler=ctx.context_assembler,
                document_state=ctx.document_state,
            )
            ctx.metadata["report"] = result
            sections = result.get("section_contents", [])
            self.logger.info(
                f"Generated: {result.get('section_count', 0)} sections, "
                f"{result.get('total_words', 0)} words, "
                f"validations passed: {result.get('all_validations_passed', False)}"
            )
            validation_issues = []
            for name, vr in result.get("validations", {}).items():
                if not vr.get("passed"):
                    for issue in vr.get("issues", []):
                        validation_issues.append(f"{name}: {issue}")
                        ctx.errors.append(f"validation.{name}: {issue}")
            if validation_issues:
                self.logger.warning(f"Validation issues: {len(validation_issues)}")
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

    # ------------------------------------------------------------------ #
    #  Evidence-centric phases
    # ------------------------------------------------------------------ #

    def _ensure_orchestrator(self, ctx: PipelineContext):
        if ctx.evidence_orchestrator is None:
            from src.evidence.orchestrator import EvidenceOrchestrator
            ctx.evidence_orchestrator = EvidenceOrchestrator()
            ctx.fact_store = ctx.evidence_orchestrator.fact_store
            ctx.coverage_engine = ctx.evidence_orchestrator.coverage_engine
            ctx.fusion_engine = ctx.evidence_orchestrator.fusion_engine

    def _run_resource_intel(self, ctx: PipelineContext) -> bool:
        self._ensure_orchestrator(ctx)
        knowledge_chunks = ctx.metadata.get("retrieved_chunks", [])
        if not knowledge_chunks and ctx.context_assembler and ctx.context_assembler.is_ready():
            try:
                result = ctx.context_assembler.retrieve_context(ctx.topic, top_k=50)
                knowledge_chunks = result.get("chunks", [])
            except Exception as e:
                self.logger.warning(f"Context retrieval failed: {e}")
        if knowledge_chunks:
            ingest_result = ctx.evidence_orchestrator.ingest_chunks(knowledge_chunks)
            ctx.metadata["resource_intel"] = ingest_result
            self.logger.info(
                f"Resource intelligence: {ingest_result['total_facts']} facts from "
                f"{ingest_result['chunks_processed']} chunks"
            )
        else:
            self.logger.info("No knowledge chunks available for resource intelligence")
        return True

    def _run_fact_extraction(self, ctx: PipelineContext) -> bool:
        self._ensure_orchestrator(ctx)
        store_stats = ctx.fact_store.get_statistics()
        ctx.metadata["fact_extraction"] = {
            "total_facts": store_stats.get("total", 0),
            "by_type": store_stats.get("by_type", {}),
        }
        self.logger.info(
            f"Fact extraction: {store_stats.get('total', 0)} facts in store, "
            f"types: {len(store_stats.get('by_type', {}))}"
        )
        return True

    def _run_evidence_graph(self, ctx: PipelineContext) -> bool:
        self._ensure_orchestrator(ctx)
        result = ctx.evidence_orchestrator.build_graph()
        ctx.metadata["evidence_graph"] = result
        kg = ctx.evidence_orchestrator.knowledge_graph.to_dict()
        self.logger.info(
            f"Evidence graph: {result['nodes']} nodes, {result['edges']} edges, "
            f"{result['fusion_results']} fusion results"
        )
        return True

    def _run_evidence_blueprint(self, ctx: PipelineContext) -> bool:
        self._ensure_orchestrator(ctx)
        blueprint = ctx.evidence_orchestrator.generate_blueprint(ctx.topic)
        ctx.evidence_blueprint = blueprint
        ctx.metadata["evidence_blueprint"] = blueprint.to_dict()
        self.logger.info(
            f"Evidence blueprint: {len(blueprint.sections)} sections, "
            f"richness={blueprint.evidence_richness:.2%}, "
            f"structure={blueprint.recommended_structure}"
        )
        return True

    def _run_coverage_analysis(self, ctx: PipelineContext) -> bool:
        self._ensure_orchestrator(ctx)
        blueprint = ctx.evidence_blueprint
        if not blueprint:
            self.logger.warning("No blueprint for coverage analysis")
            return True
        all_facts = ctx.fact_store.get_all_facts()
        facts_by_section: Dict = {}
        sections_data: Dict = {}
        for section in blueprint.sections:
            from src.facts.models import FactType
            required_types = []
            for ft_name in section.required_fact_types:
                try:
                    required_types.append(FactType(ft_name))
                except ValueError:
                    pass
            section_facts = [f for f in all_facts if f.fact_type in required_types]
            facts_by_section[section.section_type] = section_facts
            sections_data[section.section_type] = {
                "heading": section.heading,
                "paragraphs": [],
            }
        report = ctx.coverage_engine.build_report(sections_data, facts_by_section)
        ctx.coverage_report = report
        ctx.metadata["coverage_report"] = report.to_dict()

        low = report.sections_below_threshold
        total = len(report.sections)
        self.logger.info(
            f"Coverage analysis: {report.overall_coverage:.1%} overall, "
            f"{low}/{total} sections below threshold, "
            f"mode={report.generation_mode.value}"
        )
        return True

    def _run_generation_constraints(self, ctx: PipelineContext) -> bool:
        self._ensure_orchestrator(ctx)
        blueprint = ctx.evidence_blueprint
        if not blueprint:
            self.logger.warning("No blueprint for constraints")
            return True
        constraints = ctx.evidence_orchestrator.build_generation_constraints(blueprint)
        ctx.generation_constraints = constraints
        ctx.metadata["generation_constraints"] = {
            k: v.to_dict() for k, v in constraints.items()
        }
        prompt_map = ctx.evidence_orchestrator.get_generation_prompts(constraints)
        ctx.evidence_prompt_map = prompt_map
        modes = {k: v.generation_mode.value for k, v in constraints.items()}
        self.logger.info(
            f"Generation constraints: {len(constraints)} sections, "
            f"modes: {modes}"
        )
        return True

    def _run_evidence_generation(self, ctx: PipelineContext) -> bool:
        self._ensure_orchestrator(ctx)
        from src.generator.knowledge_driven_generator import KnowledgeDrivenReportGenerator

        blueprint = ctx.evidence_blueprint
        constraints = ctx.generation_constraints
        if not blueprint or not constraints:
            self.logger.warning("No blueprint/constraints for evidence generation")
            return self._run_generate(ctx)

        llm_available = False
        try:
            if ctx.knowledge_driven_generator and hasattr(ctx.knowledge_driven_generator, '_provider'):
                llm_available = ctx.knowledge_driven_generator._provider is not None
            elif ctx.report_generator and hasattr(ctx.report_generator, '_provider'):
                llm_available = ctx.report_generator._provider is not None
        except Exception:
            llm_available = False

        from src.generator.content_blocks import SectionContent, ParagraphBlock, SourceRequiredBlock
        section_contents = []
        results = []
        has_llm = llm_available

        all_facts = ctx.fact_store.get_all_facts()
        section_types = [s.section_type for s in blueprint.sections
                        if s.section_type in constraints]

        for stype in section_types:
            constraint = constraints.get(stype)
            heading = stype.replace("_", " ").title()
            if not constraint:
                section = SectionContent(heading=heading)
                section.add_block(ParagraphBlock(
                    text=f"[No evidence constraints defined for {stype}]"
                ))
                section_contents.append(section)
                continue

            section_facts = [f for f in all_facts if f.fact_id in constraint.allowed_fact_ids]

            if constraint.generation_mode.value == "not_possible" or not has_llm:
                section = SectionContent(heading=heading)
                if not section_facts:
                    section.add_block(SourceRequiredBlock(
                        query=stype,
                        message="Insufficient source material available for this section."
                    ))
                else:
                    for fact in section_facts:
                        text = getattr(fact, 'content', None) or getattr(fact, 'description', None) or str(fact)
                        section.add_block(ParagraphBlock(text=text))
                    if constraint.generation_mode.value in ("insufficient_evidence", "cautious"):
                        section.add_block(SourceRequiredBlock(
                            query=stype,
                            message="[Additional source material recommended for this section]"
                        ))
                section_contents.append(section)
                results.append({
                    "section_type": stype, "heading": section.heading,
                    "blocks": len(section.blocks), "total_words": section.total_words,
                })
                continue

            # LLM available — generate with evidence
            gen = ctx.knowledge_driven_generator
            if not gen:
                gen = KnowledgeDrivenReportGenerator(
                    provider=ctx.report_generator._provider if ctx.report_generator else None,
                    context_assembler=ctx.context_assembler,
                )

            prompt = ctx.evidence_prompt_map.get(stype, "")
            section, metadata = gen.generate_section(
                section_type=stype,
                topic=ctx.topic,
                retrieval_query=f"{ctx.topic} {stype.replace('_', ' ')}",
            )

            validation = ctx.evidence_orchestrator.validate_generated_content(
                {stype: section.to_text()}
            ).get(stype, {})
            if validation.get("issues"):
                self.logger.warning(
                    f"Evidence validation issues for {stype}: "
                    f"{validation['issues'][:3]}"
                )
                if constraint.generation_mode.value in ("insufficient_evidence", "cautious"):
                    section.add_block(SourceRequiredBlock(
                        query=stype,
                        message="[Additional source material recommended for this section]"
                    ))

            section_contents.append(section)
            results.append({
                "section_type": stype, "heading": section.heading,
                "blocks": len(section.blocks), "total_words": section.total_words,
            })

        ctx.metadata["report"] = {
            "title": ctx.topic,
            "section_contents": section_contents,
            "section_count": len(section_contents),
            "total_words": sum(s.total_words for s in section_contents),
            "chapters": [{
                "heading": s.heading,
                "content": s.to_text(),
            } for s in section_contents],
            "results": results,
        }
        self.logger.info(
            f"Evidence generation: {len(section_contents)} sections, "
            f"{sum(s.total_words for s in section_contents)} words"
        )
        return True

    def _run_hallucination_check(self, ctx: PipelineContext) -> bool:
        self._ensure_orchestrator(ctx)
        from src.validation.hallucination_detector import HallucinationDetector

        report = ctx.metadata.get("report", {})
        sections_text = {}
        for chapter in report.get("chapters", []):
            sections_text[chapter.get("heading", "unknown")] = chapter.get("content", "")

        if not sections_text:
            self.logger.info("No sections for hallucination check")
            return True

        detector = ctx.hallucination_detector or HallucinationDetector(ctx.fact_store)
        result = detector.check_report(ctx.fact_store, sections_text)
        ctx.metadata["hallucination_check"] = result

        if result["hallucination_free"]:
            self.logger.info("Hallucination check: PASSED - no issues found")
        else:
            self.logger.warning(
                f"Hallucination check: {result['total_issues']} issues found "
                f"({result['unsupported_claims']} unsupported claims)"
            )
            for issue in result.get("issues", [])[:5]:
                ctx.errors.append(f"hallucination.{issue['issue_type']}: {issue['message']}")
        return True

    def _run_traceability(self, ctx: PipelineContext) -> bool:
        self._ensure_orchestrator(ctx)
        report = ctx.metadata.get("report", {})
        sections_paras: Dict[str, List[Dict]] = {}
        for chapter in report.get("chapters", []):
            heading = chapter.get("heading", "unknown")
            content = chapter.get("content", "")
            paras = [{"paragraph_id": f"{heading}_p{i}", "text": p.strip()}
                    for i, p in enumerate(content.split("\n\n")) if p.strip()]
            sections_paras[heading] = paras

        if not sections_paras:
            self.logger.info("No sections for traceability")
            return True

        trace_map = ctx.evidence_orchestrator.build_traceability_map(
            f"report_{ctx.topic[:20]}", sections_paras
        )
        ctx.traceability_map = trace_map
        ctx.metadata["traceability"] = trace_map.to_dict()

        self.logger.info(
            f"Traceability: {trace_map.traced_paragraphs}/"
            f"{trace_map.total_paragraphs} paragraphs traced "
            f"(score={trace_map.overall_traceability:.1%})"
        )
        return True

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

    def _run_refine(self, ctx: PipelineContext) -> bool:
        report = ctx.metadata.get("report", {})
        if report and report.get("section_contents"):
            self.logger.info(
                f"Refine phase: {report.get('section_count', 0)} sections, "
                f"{len(report.get('bibliography', []))} bibliography entries"
            )
        return True

    def _run_assemble_doc(self, ctx: PipelineContext) -> bool:
        self._ensure_document_state(ctx)
        report = ctx.metadata.get("report", {})
        section_contents = report.get("section_contents", [])
        if section_contents:
            try:
                from src.document.docx_v2_generator import DOCXV2Generator
                docx_gen = DOCXV2Generator()
                output = docx_gen.generate(
                    title=report.get("title", ctx.topic),
                    author=report.get("author", ""),
                    sections=section_contents,
                    output_path=ctx.output_path,
                )
                ctx.output_path = output
                self.logger.info(f"DOCX assembled: {output}")
                self._validate_docx_styles(output)
                self._convert_to_pdf(output)
            except Exception as e:
                self.logger.warning(f"DOCX assembly via v2 failed: {e}, falling back")
                self._ensure_document_state(ctx)
        else:
            self._ensure_document_state(ctx)
        self.logger.info("Document state assembled")
        return True

    def _validate_docx_styles(self, docx_path: str):
        try:
            from src.document.styles import DocumentStyleValidator
            validator = DocumentStyleValidator()
            issues = validator.validate(docx_path)
            if issues:
                self.logger.warning(f"Style validation found {len(issues)} issue(s)")
                for issue in issues[:5]:
                    self.logger.warning(f"  Style issue: {issue}")
                try:
                    fix_count = validator.auto_fix(docx_path)
                    self.logger.info(f"Auto-fixed {fix_count} style issue(s)")
                except Exception as fix_err:
                    self.logger.warning(f"Auto-fix failed: {fix_err}")
            else:
                self.logger.info("Style validation passed")
        except Exception as e:
            self.logger.warning(f"Style validation skipped: {e}")

    def _convert_to_pdf(self, docx_path: str):
        pdf_path = docx_path.replace(".docx", ".pdf")
        try:
            from src.pipeline.export.pdf import PDFExportPipeline
            pipeline = PDFExportPipeline()
            result = pipeline.execute(docx_path, output_path=pdf_path)
            if result.success:
                self.logger.info(f"PDF created: {pdf_path}")
            else:
                logger.warning(f"PDF conversion skipped: {result.error}")
        except Exception as e:
            logger.warning(f"PDF conversion failed: {e}")

    def _ensure_document_state(self, ctx: PipelineContext):
        if ctx.document_state is None:
            ctx.document_state = DocumentState(title=ctx.topic)
        if ctx.memory_hub and hasattr(ctx.memory_hub, "get_status"):
            ctx.document_state.style_profile = ctx.memory_hub.get_status().get("style_profile", {})

    def _run_quality_gate(self, ctx: PipelineContext) -> bool:
        report = ctx.metadata.get("report", {})
        quality_gate = report.get("quality_gate")
        if not quality_gate:
            self.logger.info("No quality gate data — skipping")
            return True
        if quality_gate.get("all_passed"):
            self.logger.info("Quality Gate PASSED — all sections meet threshold")
            return True
        weak = quality_gate.get("weak_sections", [])
        self.logger.warning(
            f"Quality Gate: {len(weak)} weak section(s) below {quality_gate.get('sections', {}).get(list, {}).get('target', 8.5)}"
        )
        for ws in weak:
            self.logger.warning(f"  Section '{ws['section']}': {ws['overall']}/10")
        ctx.errors.append(f"quality_gate: {len(weak)} weak sections")
        return True

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
