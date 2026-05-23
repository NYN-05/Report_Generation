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
[Source Material Required]

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
        self._statistics = {
            "retrievals": 0,
            "generations": 0,
            "regenerations": 0,
            "validation_failures": 0,
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
        )

        section, improve_logs = self._improver.improve(section, section_type, topic)
        metadata["improve_logs"] = improve_logs

        depth_score, depth_passed = self._depth_evaluator.evaluate_section(
            section.to_text(),
            evidence_count=len(evidence_chunks),
        )
        metadata["depth_score"] = {
            "overall": depth_score.overall,
            "specificity": depth_score.specificity,
            "technical_detail": depth_score.technical_detail,
            "evidence_usage": depth_score.evidence_usage,
            "terminology_quality": depth_score.terminology_quality,
            "academic_tone": depth_score.academic_tone,
        }

        validation = self._validator.validate_section(section, section_type, topic)
        metadata["validation"] = {
            "overall_score": validation.overall_score(),
            "passed": validation.passed,
            "issues": validation.issues,
        }

        if not depth_passed or not validation.passed:
            self._statistics["validation_failures"] += 1
            for attempt in range(max_regenerations):
                self._statistics["regenerations"] += 1
                metadata["regenerations"] += 1

                logger.info(f"Regenerating {section_type} (attempt {attempt + 1})")

                section = self._writing_engine.generate_section(
                    section_type=section_type,
                    topic=topic,
                    report_type=report_type,
                    retrieval_context=context_text,
                    evidence_chunks=evidence_chunks,
                    previous_summary=previous_summary,
                )

                section, improve_logs = self._improver.improve(section, section_type, topic)

                depth_score, depth_passed = self._depth_evaluator.evaluate_section(
                    section.to_text(),
                    evidence_count=len(evidence_chunks),
                )

                validation = self._validator.validate_section(section, section_type, topic)
                metadata["validation"] = {
                    "overall_score": validation.overall_score(),
                    "passed": validation.passed,
                    "issues": validation.issues,
                }

                if depth_passed and validation.passed:
                    logger.info(f"Regeneration {attempt + 1} passed quality checks")
                    break

            if not depth_passed:
                metadata["depth_failed"] = True
            if not validation.passed:
                logger.warning(f"Section {section_type} failed validation after {max_regenerations} attempts")

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

    def get_generation_prompt(self) -> str:
        return (
            "Evidence-Based Generation Pipeline:\n"
            "1. Retrieve context from uploaded documents\n"
            "2. Rerank by relevance\n"
            "3. Compress to token budget\n"
            "4. Inject into prompt\n"
            "5. Generate content grounded in evidence\n"
            "6. Multi-pass improvement (7 passes)\n"
            "7. Validate quality metrics\n"
            "8. Regenerate if below threshold\n"
        )
