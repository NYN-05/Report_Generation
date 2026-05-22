import os
from typing import Dict, Any, List, Optional

from ..base import BasePipeline, PipelineResult
from src.document.template.loader import TemplateLoader
from src.document.structure import (
    build_tree, SectionLocator, DocumentNode,
    ReplaceSection, InsertSection, ExpandSection,
    DeleteSection, MoveSection, EditingPlanner, PlannedOperation,
)
from src.document.styles.manager import FormatPreserver
from src.core.logger import get_logger
from src.core.config import get_config

logger = get_logger(__name__)


class TemplatePipeline(BasePipeline):
    """Pipeline for generating documents from templates using structural editing."""

    def __init__(
        self,
        template_path: str = None,
        template_name: str = None,
        output_dir: str = None
    ):
        super().__init__("template")
        config = get_config()
        self.output_dir = output_dir or config.export.output_directory
        self.template_path = template_path
        self.template_name = template_name
        os.makedirs(self.output_dir, exist_ok=True)

    def execute(self, input_data: Dict, **kwargs) -> PipelineResult:
        content = input_data.get('content', input_data)
        template_path = input_data.get('template_path', self.template_path)
        template_name = input_data.get('template_name', self.template_name)
        edit_instructions = input_data.get('edits', kwargs.get('edits', []))

        try:
            logger.info(f"Generating from template: {template_path or template_name}")

            doc = self._load_document(template_path, template_name)
            if doc is None:
                return PipelineResult(success=False, error="No template specified")

            preserver = FormatPreserver()
            if template_path and os.path.exists(template_path):
                preserver.capture_styles(template_path)
                default_font = preserver.get_default_font()
                logger.info(f"Captured default font: {default_font.get('name')} {default_font.get('size')}pt")
            else:
                logger.info("No template path available for style capture, using defaults")

            tree = build_tree(doc)
            locator = SectionLocator(tree)

            analysis = locator.get_hierarchy()
            logger.info(f"Document structure: {len(analysis)} sections")

            edit_result = self._apply_structural_edits(
                doc, tree, locator, edit_instructions, content, preserver
            )

            if preserver.style_cache:
                preserver.apply_captured_styles(doc)
                logger.info("Applied captured styles after editing")

            output_path = os.path.join(self.output_dir, "template_output.docx")
            doc.save(output_path)

            logger.info(f"Template document generated: {output_path}")

            return PipelineResult(
                success=True,
                output_path=output_path,
                data={
                    "content": content,
                    "mode": "template",
                    "edits_applied": edit_result,
                    "structure": analysis,
                }
            )

        except Exception as e:
            logger.error(f"Template pipeline error: {e}")
            return PipelineResult(success=False, error=str(e))

    def analyze_structure(self, template_path: str = None,
                          template_name: str = None) -> Dict[str, Any]:
        doc = self._load_document(
            template_path or self.template_path,
            template_name or self.template_name,
        )
        if doc is None:
            return {"error": "No template loaded"}

        tree = build_tree(doc)
        locator = SectionLocator(tree)

        return {
            "sections": locator.get_hierarchy(),
            "headings": locator.get_all_headings(),
            "tree": tree.to_dict(),
        }

    def plan_edits(self, instruction: str, template_path: str = None,
                   template_name: str = None) -> List[PlannedOperation]:
        doc = self._load_document(
            template_path or self.template_path,
            template_name or self.template_name,
        )
        if doc is None:
            return []

        tree = build_tree(doc)
        planner = EditingPlanner(tree)
        operations = planner.plan(instruction)
        return operations

    def _load_document(self, template_path: Optional[str],
                       template_name: Optional[str]):
        if template_path:
            from docx import Document
            return Document(template_path)
        elif template_name:
            loader = TemplateLoader()
            return loader.load(template_name)
        return None

    def _apply_structural_edits(
        self, doc, tree: DocumentNode, locator: SectionLocator,
        instructions: List, content: Dict,
        preserver: FormatPreserver = None
    ) -> List[Dict]:
        results = []

        for instruction in instructions:
            if isinstance(instruction, str):
                planner = EditingPlanner(tree)
                operations = planner.plan(instruction)
            elif isinstance(instruction, dict):
                operations = [PlannedOperation(
                    operation=instruction.get("operation", "expand"),
                    target=instruction.get("target", ""),
                    params=instruction.get("params", {}),
                )]
            else:
                continue

            for op in operations:
                result = self._execute_operation(op, doc, tree, locator, content, preserver)
                results.append(result)

        return results

    def _execute_operation(
        self, op: PlannedOperation, doc,
        tree: DocumentNode, locator: SectionLocator, content: Dict,
        preserver: FormatPreserver = None
    ) -> Dict:
        executor_map = {
            "replace": ReplaceSection,
            "insert": InsertSection,
            "expand": ExpandSection,
            "delete": DeleteSection,
            "move": MoveSection,
        }

        executor_class = executor_map.get(op.operation)
        if executor_class is None:
            return {"operation": op.operation, "success": False,
                    "error": "Unknown operation"}

        executor = executor_class(tree, doc)
        if preserver and preserver.style_cache:
            default_font = preserver.get_default_font()
            executor.set_default_font(
                font_name=default_font.get("name"),
                font_size=default_font.get("size"),
            )

        params = dict(op.params)
        params["target"] = op.target

        if op.operation == "expand":
            if op.target.lower() in content:
                text_content = str(content[op.target.lower()])
                paragraphs = [p.strip() for p in text_content.split("\n\n")
                              if p.strip()]
                params.setdefault("append_paragraphs", []).extend(paragraphs)

        section = locator.find_by_heading(op.target)
        if section:
            params["target_node"] = section

        result = executor.execute(**params)

        return {
            "operation": op.operation,
            "target": op.target,
            "success": result.success,
            "elements": result.modified_elements,
            "error": result.error,
        }

    def validate_input(self, input_data: Dict) -> bool:
        if not input_data.get('content'):
            logger.error("No content provided")
            return False

        template_path = input_data.get('template_path') or self.template_path
        template_name = input_data.get('template_name') or self.template_name

        if not template_path and not template_name:
            logger.error("No template specified")
            return False

        return True
