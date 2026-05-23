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

        if self._provider and self._provider.is_available():
            return self._generate_with_llm(context, focus, paragraph_count)

        paragraphs = []
        for i in range(paragraph_count):
            para_ctx = GeneratorContext(
                topic=context.topic,
                retrieval_context=context.retrieval_context,
            )
            para = self._para_gen.generate(para_ctx, focus=focus, index=i)
            paragraphs.append(para)

        return "\n\n".join(paragraphs)

    def _generate_with_llm(self, context: GeneratorContext, focus: str,
                            para_count: int) -> str:
        from src.providers import Message, CompletionOptions
        try:
            prompt = (
                f"Write a subsection about '{focus}' in the context of "
                f"{context.topic}. Write {para_count} formal academic paragraphs "
                f"that flow naturally from one to the next. Include specific "
                f"evidence, analysis, and implications.\n\n"
                f"Each paragraph should be 3-6 sentences with substantive claims."
            )
            if context.retrieval_context:
                prompt += f"\n\nReference Material:\n{context.retrieval_context[:2000]}"

            messages = [
                Message(role="system", content="You are an academic report writer."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.7, max_tokens=2048, timeout=90)
            response = self._provider.chat(messages, options=opts)
            return response.content.strip()
        except Exception as e:
            logger.warning(f"LLM subsection generation failed: {e}")
            paragraphs = []
            for i in range(para_count):
                para = self._para_gen.generate(context, focus=focus, index=i)
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
