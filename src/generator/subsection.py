"""SubsectionGenerator — generates subsections with multiple paragraphs."""

from typing import List, Optional
from .base import BaseGenerator, GeneratorContext
from .paragraph import ParagraphGenerator
from src.core.logger import get_logger

logger = get_logger(__name__)


class SubsectionGenerator(BaseGenerator):
    """Generates subsections (level 3+) composed of multiple paragraphs."""

    def __init__(self, provider=None, paragraph_generator=None):
        super().__init__("subsection")
        self._para_gen = paragraph_generator or ParagraphGenerator(provider)
        self._provider = provider

    def generate(self, context: GeneratorContext, **kwargs) -> str:
        heading = kwargs.get("heading", "")
        paragraph_count = kwargs.get("paragraph_count", 3)
        focus = kwargs.get("focus", heading or context.topic)

        paragraphs = []
        for i in range(paragraph_count):
            para_ctx = GeneratorContext(
                topic=context.topic,
                retrieval_context=context.retrieval_context,
            )
            para = self._para_gen.generate(para_ctx, focus=focus, index=i)
            paragraphs.append(para)

        return "\n\n".join(paragraphs)

    def generate_subsections(self, context: GeneratorContext, count: int = 3,
                              base_heading: str = "") -> List[str]:
        results = []
        for i in range(count):
            heading = f"{base_heading} - Aspect {i+1}" if base_heading else f"Aspect {i+1}"
            content = self.generate(context, heading=heading, paragraph_count=2)
            results.append(content)
        return results
