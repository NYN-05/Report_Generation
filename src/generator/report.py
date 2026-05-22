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
            topic = context.topic
            chapters = self._topic_chapters(topic)
            chapter_configs = [{"heading": h, "section_count": 3} for h in chapters]

        chapters = self._ch_gen.generate_chapters(context, chapter_configs)

        all_content = "\n\n".join(
            ch.get("content", "") for ch in chapters
        )

        coherence = self._check_coherence(chapters)
        if coherence.get("warnings"):
            for w in coherence["warnings"]:
                logger.warning(f"Coherence: {w}")

        return {
            "title": title,
            "author": author,
            "topic": context.topic,
            "chapters": chapters,
            "full_content": all_content,
            "chapter_count": len(chapters),
            "total_words": len(all_content.split()),
            "coherence": coherence,
        }

    @staticmethod
    def _topic_chapters(topic: str) -> List[str]:
        """Derive meaningful chapter headings from the topic."""
        words = topic.lower().split()
        key_terms = [w for w in words if len(w) > 3]
        core = " ".join(key_terms[:3]) if key_terms else topic
        return [
            f"Foundations of {core}",
            f"Mechanisms and Drivers of {core}",
            f"Impact and Consequences of {core}",
            f"Interventions and Future Directions in {core}",
        ]

    @staticmethod
    def _check_coherence(chapters: List[Dict]) -> Dict:
        if len(chapters) < 2:
            return {"passed": True, "warnings": []}

        warnings = []
        terms_by_chapter = {}
        for ch in chapters:
            content = ch.get("content", "")
            words = [w.lower() for w in content.split() if len(w) > 5]
            from collections import Counter
            terms_by_chapter[ch.get("heading", "")] = {
                w for w, _ in Counter(words).most_common(30)
            }

        headings = list(terms_by_chapter.keys())
        for i in range(len(headings) - 1):
            ch_terms = terms_by_chapter[headings[i]]
            next_terms = terms_by_chapter[headings[i + 1]]
            overlap = ch_terms & next_terms
            if len(overlap) < max(len(ch_terms), 1) * 0.15:
                warnings.append(
                    f"Low term overlap ({len(overlap)} shared terms) between "
                    f"'{headings[i]}' and '{headings[i+1]}'")

        for ch in chapters:
            content = ch.get("content", "")
            heading = ch.get("heading", "")
            heading_words = set(heading.lower().split())
            if heading_words:
                content_words = set(w.lower() for w in content.split() if len(w) > 3)
                overlap = heading_words & content_words
                if len(overlap) < max(len(heading_words) * 0.3, 1):
                    warnings.append(f"Chapter '{heading}' content may drift from its heading")

        return {"passed": len(warnings) == 0, "warnings": warnings}

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
