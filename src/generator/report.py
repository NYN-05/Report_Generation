"""ReportGenerator — top-level orchestrator for hierarchical generation.

Architecture:
    Report
      └─ ChapterGenerator
           └─ SectionGenerator
                └─ SubsectionGenerator
                     └─ ParagraphGenerator
"""

from typing import List, Optional, Dict, Any
from .base import BaseGenerator, GeneratorContext
from .chapter import ChapterGenerator
from src.core.logger import get_logger

logger = get_logger(__name__)


class ReportGenerator(BaseGenerator):
    """Top-level generator that orchestrates the full hierarchy.

    Each layer receives:
    - document state (DocumentState)
    - retrieval context (from ContextAssembler)
    - memory state (abbreviations, citations, style)
    - style state (StyleMemory profile)

    Each layer returns structured output (Pydantic-compatible dicts).
    """

    def __init__(self, provider=None, chapter_generator=None):
        super().__init__("report")
        self._ch_gen = chapter_generator or ChapterGenerator(provider)
        self._provider = provider

    def generate(self, context: GeneratorContext, **kwargs) -> Dict[str, Any]:
        blueprint = kwargs.get("blueprint")
        sections = kwargs.get("sections", [])
        title = kwargs.get("title", context.topic)
        author = kwargs.get("author", "")

        if not sections and blueprint:
            sections = [
                {"heading": s.heading, "blueprint_id": s.id, "level": s.level,
                 "section_count": 3}
                for s in blueprint.sections
                if s.id not in ("cover_page", "table_of_contents",
                                "list_of_figures", "list_of_tables")
            ]

        chapter_configs = [
            s for s in sections
            if s.get("level", 1) <= 1
        ]

        if not chapter_configs:
            chapter_configs = [{"heading": f"Chapter {i+1}", "section_count": 3}
                               for i in range(4)]

        chapters = self._ch_gen.generate_chapters(context, chapter_configs)

        all_content = "\n\n".join(
            ch.get("content", "") for ch in chapters
        )

        return {
            "title": title,
            "author": author,
            "topic": context.topic,
            "chapters": chapters,
            "full_content": all_content,
            "chapter_count": len(chapters),
            "total_words": len(all_content.split()),
        }

    def generate_full_report(self, topic: str, blueprint=None,
                              title: str = "", author: str = "",
                              context_assembler=None,
                              document_state=None) -> Dict[str, Any]:
        ctx = GeneratorContext(
            topic=topic,
            report_type=blueprint.name if blueprint else "report",
            document_state=document_state,
            chapter_summaries={},
        )

        if context_assembler and context_assembler.is_ready():
            result = context_assembler.retrieve_context(topic)
            ctx.retrieval_context = result.get("context_text", "")

        sections = []
        if blueprint:
            sections = [
                {"heading": s.heading, "blueprint_id": s.id, "level": s.level,
                 "section_count": 3}
                for s in blueprint.sections
                if s.id not in ("cover_page", "table_of_contents",
                                "list_of_figures", "list_of_tables")
            ]

        return self.generate(ctx, blueprint=blueprint, sections=sections,
                             title=title, author=author)
