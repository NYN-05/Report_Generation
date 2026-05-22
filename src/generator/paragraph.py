"""ParagraphGenerator — generates individual paragraphs."""

from typing import List, Optional
from .base import BaseGenerator, GeneratorContext
from src.core.logger import get_logger

logger = get_logger(__name__)

_PARAGRAPH_TEMPLATES = [
    "A critical aspect of {topic} is {focus}, which provides the necessary framework for understanding how various components interact and contribute to the overall objectives of this section.",
    "When focusing on {focus} of {topic}, several interconnected factors play a significant role in determining the effectiveness of approaches taken and the outcomes achieved in real-world applications.",
    "A comprehensive evaluation of {focus} requires careful consideration of both theoretical foundations and practical implementations, drawing from existing knowledge across different contexts.",
    "The {focus} encompasses a range of considerations that directly impact the quality and effectiveness of work in this area, from initial planning through execution and evaluation.",
    "Examining the {focus} of {topic} reveals important patterns and trends that inform decision-making and strategic planning in this domain.",
]


class ParagraphGenerator(BaseGenerator):
    """Generates individual paragraphs. Lowest level in the hierarchy."""

    def __init__(self, provider=None):
        super().__init__("paragraph")
        self._provider = provider

    def generate(self, context: GeneratorContext, **kwargs) -> str:
        focus = kwargs.get("focus", context.topic)
        index = kwargs.get("index", 0)
        template = _PARAGRAPH_TEMPLATES[index % len(_PARAGRAPH_TEMPLATES)]
        paragraph = template.format(topic=context.topic, focus=focus)

        if context.retrieval_context:
            evidence = self._extract_evidence(context.retrieval_context, focus)
            if evidence:
                paragraph += f" {evidence}"

        return paragraph

    def _extract_evidence(self, context_text: str, focus: str) -> str:
        lines = [l.strip() for l in context_text.split("\n") if l.strip()]
        relevant = [l for l in lines if focus.lower() in l.lower() or any(
            w in l.lower() for w in focus.lower().split()[:3]
        )]
        if relevant:
            return f"According to source material: {relevant[0][:200]}"
        return ""
