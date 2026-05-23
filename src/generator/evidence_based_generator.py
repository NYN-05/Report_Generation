"""EvidenceBasedSectionGenerator — replaces RulesEngine.generate_section_content().

Every paragraph must be supported by:
- retrieved chunk
- uploaded document
- citation source

The model must not invent:
- statistics
- performance values
- accuracy percentages
- datasets
- references

If evidence is unavailable, insert:
Insufficient source material available for this claim.

Generation flow:
    retrieve_context()
        ↓
    rerank()
        ↓
    compress_context()
        ↓
    inject_context()
        ↓
    generate_content()
        ↓
    uniqueness_check()
        ↓
    quality_check()
        ↓
    depth_check()
        ↓
    validate()
"""

import time
from typing import Dict, Any, Optional, List, Tuple
from src.core.logger import get_logger
from .content_blocks import (
    SectionContent, ParagraphBlock, BulletListBlock,
    HeadingBlock, Citation, SourceRequiredBlock,
)
from .academic_writing_engine import AcademicWritingEngine
from .paragraph_quality import ParagraphQualityControl
from .technical_depth import TechnicalDepthEvaluator, DepthScore
from .multi_pass_improver import MultiPassImprover
from .content_validator import ContentValidator, ValidationResult
from .chapter_uniqueness import ChapterUniquenessChecker
from src.retrieval.context import ContextAssembler

logger = get_logger(__name__)

MAX_RETRIES = 3


class EvidenceBasedSectionGenerator:

    def __init__(
        self,
        provider=None,
        context_assembler: Optional[ContextAssembler] = None,
    ):
        self._provider = provider
        self._context_assembler = context_assembler
        self._writing_engine = AcademicWritingEngine(provider)
        self._quality = ParagraphQualityControl()
        self._depth_evaluator = TechnicalDepthEvaluator()
        self._improver = MultiPassImprover(provider)
        self._validator = ContentValidator()
        self._uniqueness = ChapterUniquenessChecker()
        self._statistics = {
            "retrievals": 0,
            "generations": 0,
            "regenerations": 0,
            "validation_failures": 0,
            "uniqueness_violations": 0,
        }

    def generate_section(
        self,
        section_type: str,
        topic: str,
        report_type: str = "engineering project report",
        retrieval_query: Optional[str] = None,
        previous_summary: str = "",
        quality_threshold: float = 0.6,
        max_regenerations: int = MAX_RETRIES,
    ) -> Tuple[SectionContent, Dict[str, Any]]:
        self._statistics["generations"] += 1
        metadata = {"section_type": section_type, "regenerations": 0}

        chapter_summaries = self._uniqueness.get_chapter_summaries()

        evidence_chunks, context_text = self._retrieve_evidence(section_type, topic, retrieval_query)
        metadata["chunks_retrieved"] = len(evidence_chunks)
        metadata["context_length"] = len(context_text)

        if not context_text and not evidence_chunks:
            logger.warning(f"No evidence retrieved for {section_type}")
            section = self._writing_engine._generate_no_evidence_section(section_type, topic)
            metadata["evidence_status"] = "none"
            return section, metadata

        section = self._writing_engine.generate_section(
            section_type=section_type,
            topic=topic,
            report_type=report_type,
            retrieval_context=context_text,
            evidence_chunks=evidence_chunks,
            previous_summary=previous_summary,
            existing_chapter_summaries=chapter_summaries,
        )

        max_sim, sim_violations = self._uniqueness.check_content_against_all(
            section.to_text(), section_type
        )
        metadata["max_similarity"] = round(max_sim, 4)
        metadata["similarity_violations"] = sim_violations
        if max_sim > self._uniqueness.MAX_SIMILARITY:
            self._statistics["uniqueness_violations"] += 1
            logger.warning(
                f"Section {section_type}: {max_sim:.1%} similarity to previous "
                f"(limit {self._uniqueness.MAX_SIMILARITY:.0%})"
            )

        section, improve_logs = self._improver.improve(section, section_type, topic)
        metadata["improve_logs"] = improve_logs

        depth_score, depth_passed = self._depth_evaluator.evaluate_section(
            section.to_text(),
            evidence_count=len(evidence_chunks),
            section_type=section_type,
        )
        metadata["depth_score"] = {
            "overall": depth_score.overall,
            "relevance": depth_score.relevance,
            "technical_detail": depth_score.technical_detail,
            "evidence_usage": depth_score.evidence_usage,
            "uniqueness": depth_score.uniqueness,
            "readability": depth_score.readability,
            "chapter_alignment": depth_score.chapter_alignment,
            "academic_tone": depth_score.academic_tone,
        }

        validation = self._validator.validate_section(section, section_type, topic)
        metadata["validation"] = {
            "overall_score": validation.overall_score(),
            "passed": validation.passed,
            "issues": validation.issues,
        }

        if not depth_passed or not validation.passed or max_sim > self._uniqueness.MAX_SIMILARITY:
            self._statistics["validation_failures"] += 1
            for attempt in range(max_regenerations):
                self._statistics["regenerations"] += 1
                metadata["regenerations"] += 1

                logger.info(
                    f"Regenerating {section_type} (attempt {attempt + 1}) "
                    f"depth={depth_score.overall:.2f} validation={validation.overall_score():.2f} "
                    f"sim={max_sim:.3f}"
                )

                section = self._writing_engine.generate_section(
                    section_type=section_type,
                    topic=topic,
                    report_type=report_type,
                    retrieval_context=context_text,
                    evidence_chunks=evidence_chunks,
                    previous_summary=previous_summary,
                    existing_chapter_summaries=chapter_summaries,
                )

                section, improve_logs = self._improver.improve(section, section_type, topic)

                depth_score, depth_passed = self._depth_evaluator.evaluate_section(
                    section.to_text(),
                    evidence_count=len(evidence_chunks),
                    section_type=section_type,
                )

                validation = self._validator.validate_section(section, section_type, topic)
                metadata["validation"] = {
                    "overall_score": validation.overall_score(),
                    "passed": validation.passed,
                    "issues": validation.issues,
                }

                max_sim, sim_violations = self._uniqueness.check_content_against_all(
                    section.to_text(), section_type
                )
                metadata["max_similarity"] = round(max_sim, 4)

                if depth_passed and validation.passed and max_sim <= self._uniqueness.MAX_SIMILARITY:
                    logger.info(f"Regeneration {attempt + 1} passed all quality checks")
                    break

            if not depth_passed:
                metadata["depth_failed"] = True
            if not validation.passed:
                logger.warning(f"Section {section_type} failed validation after {max_regenerations} attempts")
            if max_sim > self._uniqueness.MAX_SIMILARITY:
                metadata["uniqueness_failed"] = True
                logger.warning(
                    f"Section {section_type}: similarity {max_sim:.1%} still exceeds "
                    f"limit {self._uniqueness.MAX_SIMILARITY:.0%} after {max_regenerations} attempts"
                )

        self._uniqueness.register_chapter(
            heading=section.heading,
            section_type=section_type,
            content=section.to_text(),
        )

        return section, metadata

    def _retrieve_evidence(
        self,
        section_type: str,
        topic: str,
        retrieval_query: Optional[str] = None,
    ) -> Tuple[List[Dict], str]:
        self._statistics["retrievals"] += 1

        if not self._context_assembler or not self._context_assembler.is_ready():
            return [], ""

        query = retrieval_query or f"{topic} {section_type.replace('_', ' ')}"

        result = self._context_assembler.retrieve_context(query, top_k=8)
        chunks = result.get("chunks", [])
        context_text = result.get("context_text", "")

        if chunks:
            logger.info(
                f"Retrieved {len(chunks)} chunks for '{query}' "
                f"(avg score: {result.get('avg_score', 0):.3f}) "
                f"from {len(result.get('sources', []))} sources"
            )

        return chunks, context_text

    def get_statistics(self) -> Dict[str, int]:
        return dict(self._statistics)

    def reset_uniqueness(self):
        self._uniqueness.reset()

    def get_generation_prompt(self) -> str:
        return (
            "Evidence-Based Generation Pipeline:\n"
            "1. Retrieve context from uploaded documents\n"
            "2. Rerank by relevance\n"
            "3. Compress to token budget\n"
            "4. Inject into prompt\n"
            "5. Generate content grounded in evidence\n"
            "6. Uniqueness check against previous chapters\n"
            "7. Multi-pass improvement (7 passes)\n"
            "8. Validate quality metrics (7 dimensions)\n"
            "9. Regenerate if below threshold\n"
        )
