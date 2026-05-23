"""ReportGenerator — top-level orchestrator for evidence-based report generation.

Bridges the old chapter-based interface with the new evidence-based pipeline.
When sections are provided as chapter configs, uses chapter-based structure
but generates content via EvidenceBasedSectionGenerator.

When no sections provided, generates the 7 standard sections:
    Introduction, Literature Review, Methodology, Implementation,
    Results, Discussion, Conclusion
"""

from typing import List, Optional, Dict, Any, Tuple
from .base import BaseGenerator, GeneratorContext
from .evidence_based_generator import EvidenceBasedSectionGenerator
from .content_blocks import SectionContent, HeadingBlock, SourceRequiredBlock
from .content_validator import ContentValidator, ValidationResult
from src.core.logger import get_logger
from src.retrieval.context import ContextAssembler

logger = get_logger(__name__)

STANDARD_SECTION_TYPES = [
    "introduction",
    "literature_review",
    "methodology",
    "implementation",
    "results",
    "discussion",
    "conclusion",
]

SECTION_TYPE_HEADINGS = {
    "introduction": "Introduction",
    "literature_review": "Literature Review",
    "methodology": "Methodology",
    "implementation": "Implementation",
    "results": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
}


class ReportGenerator(BaseGenerator):
    """Top-level generator using evidence-based pipeline for all sections.

    Architecture:
        ReportGenerator
            └─ EvidenceBasedSectionGenerator (per section type)
                 ├─ retrieve_context()
                 ├─ rerank()
                 ├─ compress_context()
                 ├─ inject_context()
                 ├─ generate_content()
                 ├─ multi_pass_improve()
                 └─ validate()
    """

    def __init__(
        self,
        provider=None,
        context_assembler: Optional[ContextAssembler] = None,
    ):
        super().__init__("report")
        self._section_gen = EvidenceBasedSectionGenerator(
            provider=provider,
            context_assembler=context_assembler,
        )
        self._validator = ContentValidator()
        self._provider = provider

    def generate(self, context: GeneratorContext, **kwargs) -> Dict[str, Any]:
        title = kwargs.get("title", context.topic)
        author = kwargs.get("author", "")
        sections_config = kwargs.get("sections", [])

        if sections_config:
            return self._generate_from_config(context, title, author, sections_config)

        return self._generate_standard_sections(context, title, author)

    def _generate_standard_sections(
        self,
        context: GeneratorContext,
        title: str,
        author: str,
    ) -> Dict[str, Any]:
        section_types = STANDARD_SECTION_TYPES
        previous_summary = ""
        section_contents: List[SectionContent] = []
        results = []

        for stype in section_types:
            logger.info(f"Generating section: {stype}")
            section, metadata = self._section_gen.generate_section(
                section_type=stype,
                topic=context.topic,
                report_type=context.report_type or "engineering project report",
                retrieval_query=f"{context.topic} {stype.replace('_', ' ')}",
                previous_summary=previous_summary,
            )
            section_contents.append(section)
            results.append({
                "section_type": stype,
                "heading": section.heading,
                "blocks": len(section.blocks),
                "total_words": section.total_words,
                "evidence_sources": len(section.evidence_sources),
                "metadata": metadata,
            })
            previous_summary = section.to_text()[:500]
            self._section_gen._improver.set_previous_content(
                [s.to_text() for s in section_contents]
            )

        validation_results = self._validate_all(section_contents, context.topic)
        all_passed = all(vr.get("passed", False) for vr in validation_results.values())

        all_content = "\n\n".join(s.to_text() for s in section_contents)
        total_words = sum(s.total_words for s in section_contents)

        chapters = [
            {
                "heading": s.heading,
                "content": s.to_text(),
                "sections": [{"heading": s.heading, "content": s.to_text()}],
            }
            for s in section_contents
        ]

        return {
            "title": title,
            "author": author,
            "topic": context.topic,
            "section_contents": section_contents,
            "chapters": chapters,
            "chapter_count": len(chapters),
            "full_content": all_content,
            "total_words": total_words,
            "results": results,
            "validations": validation_results,
            "all_validations_passed": all_passed,
            "coherence": self._check_section_coherence(section_contents),
            "statistics": self._section_gen.get_statistics(),
        }

    def _generate_from_config(
        self,
        context: GeneratorContext,
        title: str,
        author: str,
        sections_config: List[Dict],
    ) -> Dict[str, Any]:
        section_contents: List[SectionContent] = []
        results = []
        previous_summary = ""

        for config in sections_config:
            heading = config.get("heading", "Section")
            section_count = config.get("section_count", 3)
            stype = self._heading_to_section_type(heading, section_count)

            logger.info(f"Generating chapter: {heading} (type={stype})")
            section, metadata = self._section_gen.generate_section(
                section_type=stype,
                topic=context.topic,
                report_type=context.report_type or "engineering project report",
                retrieval_query=f"{context.topic} {heading}",
                previous_summary=previous_summary,
            )
            section_contents.append(section)
            results.append({
                "section_type": stype,
                "heading": heading,
                "blocks": len(section.blocks),
                "total_words": section.total_words,
                "evidence_sources": len(section.evidence_sources),
                "metadata": metadata,
            })

            previous_summary = section.to_text()[:300]

        validation_results = self._validate_all(section_contents, context.topic)

        all_content = "\n\n".join(s.to_text() for s in section_contents)
        total_words = sum(s.total_words for s in section_contents)

        chapters = [
            {
                "heading": config.get("heading", s.heading),
                "content": s.to_text(),
                "sections": [{"heading": s.heading, "content": s.to_text()}],
            }
            for config, s in zip(sections_config, section_contents)
        ]

        return {
            "title": title,
            "author": author,
            "topic": context.topic,
            "section_contents": section_contents,
            "chapters": chapters,
            "chapter_count": len(chapters),
            "full_content": all_content,
            "total_words": total_words,
            "results": results,
            "validations": validation_results,
            "all_validations_passed": all(vr.get("passed", False) for vr in validation_results.values()),
            "coherence": self._check_section_coherence(section_contents),
            "statistics": self._section_gen.get_statistics(),
        }

    def _validate_all(
        self,
        section_contents: List[SectionContent],
        topic: str,
    ) -> Dict[str, Any]:
        results = {}
        for section in section_contents:
            stype = section.heading.lower().replace(" ", "_")
            vr = self._validator.validate_section(section, stype, topic)
            results[section.heading] = {
                "overall_score": vr.overall_score(),
                "passed": vr.passed,
                "issues": vr.issues,
                "details": vr.details,
            }
        return results

    def _heading_to_section_type(self, heading: str, section_count: int) -> str:
        heading_lower = heading.lower()
        for stype, h in SECTION_TYPE_HEADINGS.items():
            if h.lower() in heading_lower or heading_lower in h.lower():
                return stype
        if "foundation" in heading_lower:
            return "introduction"
        if "mechanism" in heading_lower or "driver" in heading_lower:
            return "literature_review"
        if "impact" in heading_lower or "consequence" in heading_lower:
            return "results"
        if "intervention" in heading_lower or "future" in heading_lower:
            return "conclusion"
        return "introduction"

    def _check_section_coherence(self, section_contents: List[SectionContent]) -> Dict:
        if len(section_contents) < 2:
            return {"passed": True, "warnings": []}
        warnings = []
        texts = [s.to_text() for s in section_contents]
        for i in range(len(texts) - 1):
            words_i = set(texts[i].lower().split())
            words_j = set(texts[i + 1].lower().split())
            overlap = words_i & words_j
            if len(overlap) < max(len(words_i) * 0.05, 3):
                warnings.append(
                    f"Low term overlap between '{section_contents[i].heading}' "
                    f"and '{section_contents[i + 1].heading}'"
                )
        return {"passed": len(warnings) == 0, "warnings": warnings}

    def generate_full_report(
        self,
        topic: str,
        blueprint=None,
        title: str = "",
        author: str = "",
        context_assembler: Optional[ContextAssembler] = None,
        document_state=None,
    ) -> Dict[str, Any]:
        ctx = GeneratorContext(
            topic=topic,
            report_type=blueprint.name if blueprint else "report",
            document_state=document_state,
        )

        if context_assembler and context_assembler.is_ready():
            self._section_gen._context_assembler = context_assembler

        sections = []
        if blueprint:
            sections = [
                {"heading": s.heading, "blueprint_id": s.id, "level": s.level}
                for s in blueprint.sections
                if s.id not in ("cover_page", "table_of_contents",
                                "list_of_figures", "list_of_tables")
            ]

        if sections:
            return self.generate(ctx, title=title, author=author, sections=sections)
        return self.generate(ctx, title=title, author=author)

    def generate_docx(
        self,
        topic: str,
        title: str = "",
        author: str = "",
        context_assembler: Optional[ContextAssembler] = None,
        output_path: str = "output/output.docx",
    ) -> str:
        report = self.generate_full_report(
            topic=topic,
            title=title or topic,
            author=author,
            context_assembler=context_assembler,
        )
        from src.document.docx_v2_generator import DOCXV2Generator
        docx_gen = DOCXV2Generator()
        return docx_gen.generate(
            title=report.get("title", topic),
            author=report.get("author", ""),
            sections=report.get("section_contents", []),
            output_path=output_path,
        )
