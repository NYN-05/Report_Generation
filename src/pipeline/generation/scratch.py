"""
Scratch Generation Pipeline
===========================
Generates documents from scratch using the Dynamic Academic Report Blueprint System.
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
                 use_llm: bool = False):
        super().__init__("scratch")
        self.output_dir = output_dir
        self._use_llm = use_llm
        config = get_config()
        self.output_dir = config.export.output_directory
        os.makedirs(self.output_dir, exist_ok=True)

        from src.document.rules import RulesEngine
        self._rules_engine = RulesEngine(rules_path=rules_path) if rules_path else RulesEngine()
        self._bp_loader = BlueprintLoader()
        self._bp_selector = BlueprintSelector(self._bp_loader)
        self._bp_planner = AIReportPlanner(rules_engine=self._rules_engine)
        self._bp_builder = BlueprintBuilder()
        self._bp_validator = BlueprintValidator()

    def execute(self, input_data: Dict, **kwargs) -> PipelineResult:
        content = input_data.get('content', input_data)
        query = content.get('blueprint_query',
                            content.get('report_type',
                                        content.get('topic', '')))
        custom_blueprint = content.get('custom_blueprint', kwargs.get('custom_blueprint'))

        try:
            logger.info(f"Generating report: {content.get('title', 'Untitled')}")

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
