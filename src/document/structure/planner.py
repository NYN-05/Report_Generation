import re
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

from .model import DocumentNode, SectionNode
from .locator import SectionLocator
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PlannedOperation:
    operation: str
    target: str
    params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class EditingPlanner:
    """Translates natural language editing instructions into structured operations."""

    def __init__(self, root: Optional[DocumentNode] = None):
        self.root = root
        self.locator = SectionLocator(root) if root else None

    def set_document(self, root: DocumentNode):
        self.root = root
        self.locator = SectionLocator(root)

    def plan(self, instruction: str) -> List[PlannedOperation]:
        instruction_lower = instruction.lower().strip()

        operations = []

        expand_match = re.search(
            r'(?:expand|elaborate|add\s+detail\s+to|extend)\s+(?:section\s+)?["\']([^"\']+)["\']',
            instruction_lower,
        )
        if not expand_match:
            expand_match = re.search(
                r'(?:expand|elaborate|add\s+detail\s+to|extend)\s+(?:section\s+)?([a-z][a-z\s]+?)(?:\s+with|\s+to\s+include|\s*$)',
                instruction_lower,
            )
        if expand_match:
            target = expand_match.group(1).strip().rstrip(".")
            subsections = self._extract_subsections_from_text(instruction)
            params = {"new_subsections": subsections or [{"heading": "Details", "content": "Additional information."}]}
            if "append" in instruction_lower or "add paragraph" in instruction_lower:
                params["append_paragraphs"] = [instruction]
            operations.append(PlannedOperation(
                operation="expand", target=target, params=params,
            ))
            return operations

        replace_match = re.search(
            r'(?:replace|change|rewrite|update)\s+(?:section\s+)?["\']?(.+?)["\']?(?:\s+with\s+)?',
            instruction_lower,
        )
        if replace_match:
            target = replace_match.group(1).strip().rstrip(".")
            new_content = self._extract_new_content(instruction)
            operations.append(PlannedOperation(
                operation="replace", target=target,
                params={"new_content": new_content or "Updated content."},
            ))
            return operations

        insert_match = re.search(
            r'(?:insert|add|create)\s+(?:a\s+|an\s+|new\s+)?(?:section\s+)?["\']?(.+?)["\']?(?:\s+(?:before|after|under)\s+["\']?(.+?)["\']?)?',
            instruction_lower,
        )
        if insert_match:
            heading = insert_match.group(1).strip().rstrip(".")
            target = insert_match.group(2).strip().rstrip(".") if insert_match.group(2) else ""
            position = "after"
            if "before" in instruction_lower:
                position = "before"
            elif "under" in instruction_lower or "inside" in instruction_lower:
                position = "last_child"
            content = self._extract_new_content(instruction)
            params = {
                "heading": heading,
                "content": content or "",
                "level": 1,
                "position": position,
            }
            if target:
                params["target"] = target
            operations.append(PlannedOperation(
                operation="insert", target=target or "__end__", params=params,
            ))
            return operations

        delete_match = re.search(
            r'(?:delete|remove|drop)\s+(?:section\s+)?["\']?(.+?)["\']?',
            instruction_lower,
        )
        if delete_match:
            target = delete_match.group(1).strip().rstrip(".")
            params = {}
            if "children" in instruction_lower or "content" in instruction_lower:
                params["delete_children_only"] = True
            operations.append(PlannedOperation(
                operation="delete", target=target, params=params,
            ))
            return operations

        move_match = re.search(
            r'(?:move|reorder|shift)\s+(?:section\s+)?["\']?(.+?)["\']?(?:\s+(?:to|after|before)\s+["\']?(.+?)["\']?)?',
            instruction_lower,
        )
        if move_match:
            target = move_match.group(1).strip().rstrip(".")
            destination = move_match.group(2).strip().rstrip(".") if move_match.group(2) else ""
            position = "after"
            if "before" in instruction_lower:
                position = "before"
            params = {"position": position}
            if destination:
                params["destination"] = destination
            operations.append(PlannedOperation(
                operation="move", target=target, params=params,
            ))
            return operations

        logger.warning(f"Could not parse editing instruction: {instruction}")
        return []

    def plan_with_llm(self, instruction: str, provider=None) -> List[PlannedOperation]:
        if self.locator:
            headings = self.locator.get_all_headings()
            hierarchy = self.locator.get_hierarchy()
        else:
            headings = []
            hierarchy = []

        prompt = f"""Parse the following editing instruction into structured operations.

Available sections in the document:
{json.dumps(hierarchy, indent=2)}

Instruction: {instruction}

Output a JSON array of operations. Each operation has:
- "operation": one of "expand", "replace", "insert", "delete", "move"
- "target": section heading text to target
- "params": dict with operation-specific parameters

For "expand":
  params: {{"new_subsections": [{{"heading": "...", "content": "..."}}], "append_paragraphs": [...]}}

For "replace":
  params: {{"new_content": "...", "new_heading": "..."}}

For "insert":
  params: {{"heading": "...", "content": "...", "level": 1, "position": "after|before|first_child|last_child"}}
  If inserting relative to another section, use "target": "Other Section Heading"

For "delete":
  params: {{"delete_children_only": false}}

For "move":
  params: {{"destination": "Target Section", "position": "after|before|first_child|last_child"}}

Return ONLY valid JSON array."""

        if not provider or not provider.is_available():
            return self.plan(instruction)

        try:
            from src.providers import Message
            messages = [
                Message(role="system", content="You convert document editing instructions into structured operation plans."),
                Message(role="user", content=prompt),
            ]
            response = provider.chat(messages)
            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return [PlannedOperation(**op) for op in data]
        except Exception as e:
            logger.error(f"LLM planning failed: {e}")

        return self.plan(instruction)

    def _extract_subsections_from_text(self, text: str) -> List[Dict[str, str]]:
        subsections = []
        lines = text.split("\n")
        current_heading = None
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            section_match = re.match(
                r'^(?:section|subsection|part)\s+\d+[\.:\)]?\s+(.+?)$',
                line, re.IGNORECASE
            )
            if section_match:
                if current_heading and current_content:
                    subsections.append({
                        "heading": current_heading,
                        "content": " ".join(current_content),
                    })
                current_heading = section_match.group(1)
                current_content = []
            elif current_heading:
                current_content.append(line)

        if current_heading and current_content:
            subsections.append({
                "heading": current_heading,
                "content": " ".join(current_content),
            })

        return subsections

    def _extract_new_content(self, text: str) -> str:
        after_markers = re.split(
            r'(?:with|containing|that says|that reads|text:)\s*["\']?',
            text, maxsplit=1, flags=re.IGNORECASE
        )
        if len(after_markers) > 1:
            content = after_markers[1].strip()
            content = re.sub(r'["\']$', '', content)
            return content
        return ""

    def explain_plan(self, operations: List[PlannedOperation]) -> str:
        if not operations:
            return "No operations could be planned from the instruction."

        lines = []
        for i, op in enumerate(operations, 1):
            op_name = op.operation.upper()
            target = op.target
            params_desc = []
            for k, v in op.params.items():
                if isinstance(v, str) and len(v) > 60:
                    v = v[:60] + "..."
                params_desc.append(f"{k}={v}")
            param_str = ", ".join(params_desc)
            lines.append(f"{i}. {op_name} '{target}' [{param_str}] (confidence: {op.confidence:.1f})")

        return "\n".join(lines)
