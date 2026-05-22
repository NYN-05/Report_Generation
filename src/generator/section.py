"""SectionGenerator — generates sections with subsections."""

from typing import List, Optional
from .base import BaseGenerator, GeneratorContext
from .subsection import SubsectionGenerator
from src.core.logger import get_logger

logger = get_logger(__name__)


class SectionGenerator(BaseGenerator):
    """Generates sections (level 2) composed of subsections and paragraphs."""

    def __init__(self, provider=None, subsection_generator=None):
        super().__init__("section")
        self._sub_gen = subsection_generator or SubsectionGenerator(provider)
        self._provider = provider

    def generate(self, context: GeneratorContext, **kwargs) -> str:
        heading = kwargs.get("heading", "")
        subsection_count = kwargs.get("subsection_count", 3)
        paragraph_count = kwargs.get("paragraph_count", 4)

        if self._provider and self._provider.is_available():
            return self._generate_with_llm(context, heading, paragraph_count)

        paragraphs = []
        for i in range(paragraph_count):
            para_ctx = GeneratorContext(
                topic=context.topic,
                retrieval_context=context.retrieval_context,
            )
            from .paragraph import ParagraphGenerator
            pg = ParagraphGenerator(self._provider)
            para = pg.generate(para_ctx, focus=heading, index=i)
            paragraphs.append(para)

        body = "\n\n".join(paragraphs)

        if subsection_count > 0:
            subs = self._sub_gen.generate_subsections(
                context, count=subsection_count, base_heading=heading,
            )
            body += "\n\n" + "\n\n".join(subs)

        return body

    def _generate_with_llm(self, context: GeneratorContext, heading: str,
                            para_count: int) -> str:
        from src.providers import Message, CompletionOptions
        try:
            prompt = (
                f"Write the section '{heading}' for a {context.report_type} on {context.topic}.\n"
                f"Write {para_count} formal academic paragraphs.\n"
            )
            if context.retrieval_context:
                prompt += f"\nReference Material:\n{context.retrieval_context}\n"
            if context.chapter_summaries:
                for ch, summary in context.chapter_summaries.items():
                    prompt += f"\n[{ch}]: {summary}"

            messages = [
                Message(role="system", content="You are an academic report writer."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.7, max_tokens=4096, timeout=120)
            response = self._provider.chat(messages, options=opts)
            return response.content
        except Exception as e:
            logger.warning(f"LLM section generation failed: {e}")
            return self.generate(context, heading=heading,
                                 subsection_count=0, paragraph_count=para_count)

    def generate_sections(self, context: GeneratorContext,
                           headings: List[str]) -> List[str]:
        return [self.generate(context, heading=h) for h in headings]
