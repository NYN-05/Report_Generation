"""
Scratch Generation Pipeline
===========================
Generates documents from scratch using the Dynamic Academic Report Blueprint System.
Integrates RAG retrieval (ContextAssembler), review pipeline, and memory tracking.
"""

import os
from typing import Dict, Any, Optional, List

from ..base import BasePipeline, PipelineResult
from src.document.blueprint import (
    BlueprintLoader, BlueprintSelector, AIReportPlanner,
    BlueprintBuilder, BlueprintValidator,
)
from src.core.logger import get_logger
from src.core.config import get_config

logger = get_logger(__name__)


class ScratchPipeline(BasePipeline):
    """Pipeline for generating Word documents from scratch using blueprints."""

    def __init__(self, output_dir: str = "output", rules_path: Optional[str] = None,
                 use_llm: bool = False, knowledge_dir: Optional[str] = None,
                 enable_review: bool = True):
        super().__init__("scratch")
        self._use_llm = use_llm
        self._enable_review = enable_review
        config = get_config()
        self.output_dir = config.export.output_directory
        os.makedirs(self.output_dir, exist_ok=True)

        from src.document.rules import RulesEngine
        self._rules_engine = RulesEngine(rules_path=rules_path) if rules_path else RulesEngine()
        self._bp_loader = BlueprintLoader()
        self._bp_selector = BlueprintSelector(self._bp_loader)
        self._bp_builder = BlueprintBuilder()
        self._bp_validator = BlueprintValidator()

        self._ingestion = None
        self._review = None
        self._memory = None
        self._context_assembler = None
        self._init_optional_modules(knowledge_dir)

        self._bp_planner = AIReportPlanner(
            rules_engine=self._rules_engine,
            context_assembler=self._context_assembler,
        )

    def _init_optional_modules(self, knowledge_dir: Optional[str] = None):
        try:
            from src.ingestion import IngestionPipeline
            self._ingestion = IngestionPipeline()
            if knowledge_dir and os.path.isdir(knowledge_dir):
                count = self._ingestion.ingest_directory(knowledge_dir)
                logger.info(f"Ingested {count} knowledge chunks from {knowledge_dir}")
                chunks = self._ingestion.get_chunks()
                if chunks:
                    from src.retrieval.context import ContextAssembler
                    self._context_assembler = ContextAssembler()
                    self._context_assembler.index_knowledge(chunks)
                    logger.info(f"ContextAssembler indexed {len(chunks)} chunks for RAG retrieval")
        except Exception as e:
            logger.warning(f"Ingestion/RAG module init failed: {e}")

        try:
            from src.review import ReviewPipeline
            self._review = ReviewPipeline()
        except Exception as e:
            logger.warning(f"Review module init failed: {e}")

        try:
            from src.memory import MemoryHub
            self._memory = MemoryHub()
        except Exception as e:
            logger.warning(f"Memory module init failed: {e}")

    def execute(self, input_data: Dict, **kwargs) -> PipelineResult:
        content = input_data.get('content', input_data)
        query = content.get('blueprint_query',
                            content.get('report_type',
                                        content.get('topic', '')))
        custom_blueprint = content.get('custom_blueprint', kwargs.get('custom_blueprint'))

        try:
            logger.info(f"Generating report: {content.get('title', 'Untitled')}")

            rag_active = bool(self._context_assembler and self._context_assembler.is_ready())
            if rag_active:
                logger.info("RAG retrieval active: per-section context will be injected")

            if custom_blueprint:
                blueprint = self._bp_loader.load_custom(custom_blueprint)
                if blueprint is None:
                    return PipelineResult(
                        success=False,
                        error=f"Custom blueprint not found: {custom_blueprint}"
                    )
                logger.info(f"Using custom blueprint: {blueprint.name}")
            elif query:
                blueprint = self._bp_selector.select_with_fallback(query)
                logger.info(f"Selected blueprint: {blueprint.name} for query: {query}")
            else:
                blueprints = self._bp_loader.load_all()
                if not blueprints:
                    return PipelineResult(success=False,
                                          error="No blueprints available")
                blueprint = list(blueprints.values())[0]
                logger.info(f"Using default blueprint: {blueprint.name}")

            plan = self._bp_planner.plan(
                topic=content.get('topic', content.get('title', 'Report')),
                blueprint=blueprint,
                title=content.get('title', ''),
                author=content.get('author', ''),
                date=content.get('date', ''),
                use_llm=self._use_llm,
                llm_timeout=60,
            )

            errors = self._bp_validator.validate(plan, blueprint)
            if errors:
                logger.warning(f"Validation issues: {errors}")
                for err in errors:
                    logger.warning(f"  - {err}")

            review_results = {}
            if self._enable_review and self._review:
                sections_data = [
                    {"heading": s.heading, "content": s.content}
                    for s in plan.sections
                ]
                review_results = self._review.review_sections(sections_data)
                summary = self._review.get_summary(review_results)
                logger.info(f"Review: {summary}")

            if self._memory:
                for sec in plan.sections:
                    if sec.content:
                        self._memory.process_section(sec.content)
                mem_status = self._memory.get_status()
                logger.info(f"Memory: {mem_status}")

            output_path = os.path.join(self.output_dir, "output.docx")
            success = self._bp_builder.build(plan, output_path)

            if success:
                logger.info(f"Report generated: {output_path}")
                return PipelineResult(
                    success=True,
                    output_path=output_path,
                    data={
                        "content": content,
                        "mode": "scratch",
                        "blueprint": plan.blueprint_name,
                        "plan": plan.to_dict(),
                        "validation_errors": errors,
                        "review": review_results,
                        "rag_active": bool(self._context_assembler and self._context_assembler.is_ready()),
                    }
                )
            else:
                return PipelineResult(
                    success=False,
                    error="Failed to save document"
                )

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            return PipelineResult(
                success=False,
                error=str(e)
            )

    def validate_input(self, input_data: Dict) -> bool:
        content = input_data.get('content', input_data)
        if not content:
            logger.error("No content provided")
            return False
        if 'title' not in content and 'topic' not in content:
            logger.error("Missing required field: title or topic")
            return False
        return True

    def list_blueprints(self) -> Dict[str, str]:
        return self._bp_loader.get_available()

    def preview_plan(self, topic: str, report_type: str = "",
                     custom_blueprint: str = "") -> Dict[str, Any]:
        if custom_blueprint:
            blueprint = self._bp_loader.load_custom(custom_blueprint)
        elif report_type:
            blueprint = self._bp_selector.select_with_fallback(report_type)
        else:
            blueprint = self._bp_selector.select_with_fallback(topic)

        if blueprint is None:
            return {"error": "No blueprint available"}

        plan = self._bp_planner._plan_fallback(
            topic=topic, blueprint=blueprint,
            title=topic, author="", date=""
        )
        errors = self._bp_validator.validate(plan, blueprint)

        return {
            "blueprint": blueprint.name,
            "blueprint_id": blueprint.id,
            "sections": [{
                "id": s.blueprint_section_id,
                "heading": s.heading,
                "level": s.level,
                "subsections": [
                    {"heading": ss.heading, "level": ss.level}
                    for ss in s.subsections
                ],
            } for s in plan.sections],
            "total_pages": plan.total_pages,
            "total_references": plan.total_references,
            "validation_errors": errors,
        }
