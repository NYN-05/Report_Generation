"""AcademicWritingEngine — section-specific writing behavior.

Each section type has unique structure requirements:
- Introduction: Background, Problem Statement, Motivation, Objectives, Scope, Contribution
- Literature Review: Research Area, Existing Work, Strengths, Limitations, Research Gap
- Methodology: System Architecture, Workflow, Algorithms, Models, Implementation Strategy
- Results: Experimental Setup, Observations, Metrics, Analysis
- Discussion: Interpretation, Advantages, Limitations, Future Improvements
- Conclusion: Summary, Achievements, Future Work
"""

from typing import Dict, Any, Optional, List
from src.core.logger import get_logger
from .content_blocks import (
    SectionContent, ParagraphBlock, BulletListBlock, BulletItem,
    HeadingBlock, Citation, SourceRequiredBlock, TableBlock, TableRow,
)
from .paragraph_quality import ParagraphQualityControl

logger = get_logger(__name__)


class AcademicWritingEngine:

    def __init__(self, provider=None):
        self._provider = provider
        self._quality = ParagraphQualityControl()

    def generate_section(
        self,
        section_type: str,
        topic: str,
        report_type: str = "engineering project report",
        retrieval_context: str = "",
        evidence_chunks: Optional[List[Dict]] = None,
        previous_summary: str = "",
    ) -> SectionContent:
        if not retrieval_context and not evidence_chunks:
            return self._generate_no_evidence_section(section_type, topic)

        prompt = self._build_section_prompt(
            section_type, topic, report_type,
            retrieval_context, evidence_chunks, previous_summary,
        )

        if self._provider and self._provider.is_available():
            raw = self._generate_with_llm(prompt)
            return self._parse_response(section_type, raw, evidence_chunks)
        else:
            return self._template_section(section_type, topic, evidence_chunks)

    def _build_section_prompt(
        self,
        section_type: str,
        topic: str,
        report_type: str,
        retrieval_context: str,
        evidence_chunks: Optional[List[Dict]],
        previous_summary: str,
    ) -> str:
        from .prompt_builder_v2 import PromptBuilderV2
        builder = PromptBuilderV2()
        return builder.build_prompt(
            section_type=section_type,
            topic=topic,
            report_type=report_type,
            retrieval_context=retrieval_context,
            previous_section_summary=previous_summary,
        )

    def _generate_with_llm(self, prompt: str) -> str:
        from src.providers import Message, CompletionOptions
        try:
            messages = [
                Message(role="system", content=(
                    "You are an engineering student writing a university project report. "
                    "Write with technical precision and academic rigor. "
                    "Base every claim on the provided evidence. "
                    "Do not invent facts, statistics, or references. "
                    "If evidence is missing, write [Source Material Required]."
                )),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.3, max_tokens=4096, timeout=180)
            response = self._provider.chat(messages, options=opts)
            return response.content.strip()
        except Exception as e:
            logger.warning(f"LLM generation failed for section: {e}")
            return ""

    def _parse_response(
        self,
        section_type: str,
        raw: str,
        evidence_chunks: Optional[List[Dict]],
    ) -> SectionContent:
        heading_map = {
            "introduction": "Introduction",
            "literature_review": "Literature Review",
            "methodology": "Methodology",
            "implementation": "Implementation",
            "results": "Results",
            "discussion": "Discussion",
            "conclusion": "Conclusion",
        }
        heading = heading_map.get(section_type, section_type.replace("_", " ").title())

        section = SectionContent(heading=heading)
        section.add_block(HeadingBlock(text=heading, level=1))

        if not raw:
            section.add_block(SourceRequiredBlock(
                query=section_type,
                message=f"[Source Material Required] Evidence retrieval returned no content for {heading}."
            ))
            return section

        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]

        for para in paragraphs:
            if para.startswith("[Table:") or para.startswith("|"):
                continue
            if para.startswith("[Source Material Required]"):
                section.add_block(SourceRequiredBlock(
                    query=section_type,
                    message=para,
                ))
                continue

            lines = para.split("\n")
            clean_lines = [l for l in lines if not l.startswith("|") and not l.startswith("---")]
            text = " ".join(l.strip() for l in clean_lines if l.strip())

            if len(text.split()) < 30:
                continue

            if ":" in text and "\n" in para:
                self._add_bullet_block(section, para, evidence_chunks)
                continue

            block = ParagraphBlock(
                text=text,
                word_count=len(text.split()),
                topic_sentence=text.split(".")[0] if "." in text else text,
                evidence_source=self._find_evidence_source(text, evidence_chunks),
            )
            section.add_block(block)

        return section

    def _add_bullet_block(
        self,
        section: SectionContent,
        para: str,
        evidence_chunks: Optional[List[Dict]],
    ):
        lines = [l.strip() for l in para.split("\n") if l.strip()]
        items = []
        current_title = ""
        current_desc = ""

        for line in lines:
            if ":" in line and len(line.split(":")[0].split()) <= 6:
                parts = line.split(":", 1)
                potential_title = parts[0].strip()
                potential_desc = parts[1].strip()
                if current_title and current_desc:
                    items.append(BulletItem(
                        title=current_title,
                        description=current_desc,
                        evidence_source=self._find_evidence_source(current_desc, evidence_chunks),
                    ))
                current_title = potential_title.lstrip("-•* ").strip()
                current_desc = potential_desc
            else:
                if current_desc:
                    current_desc += " " + line
                else:
                    current_desc = line

        if current_title:
            items.append(BulletItem(
                title=current_title,
                description=current_desc,
                evidence_source=self._find_evidence_source(current_desc, evidence_chunks),
            ))

        if items:
            block = BulletListBlock(
                title="",
                items=items,
            )
            section.add_block(block)

    def _find_evidence_source(self, text: str, chunks: Optional[List[Dict]]) -> str:
        if not chunks:
            return ""
        for chunk in chunks:
            chunk_text = chunk.get("text", "")
            chunk_words = set(chunk_text.lower().split())
            text_words = set(text.lower().split())
            overlap = chunk_words & text_words
            if len(overlap) / max(len(text_words), 1) > 0.15:
                source = chunk.get("metadata", {}).get("source", "")
                if source:
                    return source
        return ""

    def _generate_no_evidence_section(self, section_type: str, topic: str) -> SectionContent:
        heading_map = {
            "introduction": "Introduction",
            "literature_review": "Literature Review",
            "methodology": "Methodology",
            "implementation": "Implementation",
            "results": "Results",
            "discussion": "Discussion",
            "conclusion": "Conclusion",
        }
        heading = heading_map.get(section_type, section_type)

        section = SectionContent(heading=heading)
        section.add_block(HeadingBlock(text=heading, level=1))
        section.add_block(SourceRequiredBlock(
            query=section_type,
            message=(
                f"[Source Material Required] No source documents were retrieved "
                f"for the {heading} section. Evidence-based content generation "
                f"requires uploaded reference materials covering {topic}."
            ),
        ))
        return section

    def _template_section(
        self,
        section_type: str,
        topic: str,
        evidence_chunks: Optional[List[Dict]],
    ) -> SectionContent:
        if evidence_chunks:
            return self._build_section_from_evidence(section_type, topic, evidence_chunks)
        return self._generate_no_evidence_section(section_type, topic)

    def _build_section_from_evidence(
        self,
        section_type: str,
        topic: str,
        evidence_chunks: List[Dict],
    ) -> SectionContent:
        section = SectionContent(heading=section_type.replace("_", " ").title())
        section.add_block(HeadingBlock(text=section_type.replace("_", " ").title(), level=1))

        for i, chunk in enumerate(evidence_chunks[:5]):
            text = chunk.get("text", "").strip()
            source = chunk.get("metadata", {}).get("source", "unknown")
            if not text:
                continue
            block = ParagraphBlock(
                text=text,
                word_count=len(text.split()),
                topic_sentence=text.split(".")[0] if "." in text else text[:80],
                evidence_source=source,
                citations=[Citation(source=source)],
            )
            section.add_block(block)

        if len(section.blocks) <= 1:
            section.add_block(SourceRequiredBlock(
                query=section_type,
                message=f"[Source Material Required] No usable evidence chunks for {section_type}.",
            ))
        return section
