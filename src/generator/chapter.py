"""ChapterGenerator — generates full chapters with sections and subsections."""

from typing import List, Optional, Dict
from .base import BaseGenerator, GeneratorContext
from .section import SectionGenerator
from src.core.logger import get_logger

logger = get_logger(__name__)


class ChapterGenerator(BaseGenerator):
    """Generates chapters (level 1) composed of sections and subsections."""

    def __init__(self, provider=None, section_generator=None):
        super().__init__("chapter")
        self._sec_gen = section_generator or SectionGenerator(provider)
        self._provider = provider

    def generate(self, context: GeneratorContext, **kwargs) -> Dict:
        heading = kwargs.get("heading", "")
        section_count = kwargs.get("section_count", 3)
        section_headings = kwargs.get("section_headings", [])
        context_summary = context.parent_summary

        if not section_headings:
            section_headings = [
                f"{heading} - Overview",
                f"{heading} - Analysis",
                f"{heading} - Summary",
            ][:section_count]

        sections = []
        for sh in section_headings:
            sec_ctx = GeneratorContext(
                topic=context.topic,
                report_type=context.report_type,
                retrieval_context=context.retrieval_context,
                chapter_summaries=context.chapter_summaries,
                parent_summary=context_summary,
            )
            content = self._sec_gen.generate(
                sec_ctx, heading=sh, subsection_count=2, paragraph_count=3,
            )
            sections.append({"heading": sh, "content": content})

        chapter_content = f"# {heading}\n\n"
        chapter_content += "\n\n".join(s["content"] for s in sections)

        return {
            "heading": heading,
            "content": chapter_content,
            "sections": sections,
        }

    def generate_chapters(self, context: GeneratorContext,
                           chapter_configs: List[Dict]) -> List[Dict]:
        results = []
        for i, config in enumerate(chapter_configs):
            ch_ctx = GeneratorContext(
                topic=context.topic,
                report_type=context.report_type,
                retrieval_context=context.retrieval_context,
                parent_summary="",
            )
            result = self.generate(
                ch_ctx,
                heading=config.get("heading", f"Chapter {i+1}"),
                section_count=config.get("section_count", 3),
                section_headings=config.get("section_headings", []),
            )
            results.append(result)

            if hasattr(context, "chapter_summaries") and context.chapter_summaries is not None:
                content = result.get("content", "")
                context.chapter_summaries[result["heading"]] = content[:300]

        return results
