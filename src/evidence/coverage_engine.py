from typing import Dict, List, Optional, Set, Tuple
import re
from src.core.logger import get_logger
from .coverage_models import (
    SectionCoverage, ParagraphCoverage, EvidenceCoverageReport,
    CoverageLevel, GenerationMode,
)
from src.facts.models import Fact, FactType
from src.facts.store import FactStore

logger = get_logger(__name__)


class CoverageEngine:
    def __init__(self, fact_store: Optional[FactStore] = None):
        self._fact_store = fact_store or FactStore()
        self._reports: Dict[str, EvidenceCoverageReport] = {}

    def compute_section_coverage(
        self,
        section_type: str,
        heading: str,
        paragraphs: List[Dict],
        facts: List[Fact],
    ) -> SectionCoverage:
        paragraph_coverages = []
        all_supporting_ids: Set[str] = set()
        all_missing: List[str] = []

        for i, para in enumerate(paragraphs):
            para_id = para.get("paragraph_id", f"{section_type}_p{i}")
            para_text = para.get("text", "")
            para_fact_ids = para.get("fact_ids", [])

            pc = self._compute_paragraph_coverage(
                para_id=para_id,
                para_text=para_text,
                para_fact_ids=para_fact_ids,
                section_facts=facts,
            )
            paragraph_coverages.append(pc)
            all_supporting_ids.update(pc.fact_ids)
            all_missing.extend(pc.missing_requirements)

        if not paragraph_coverages:
            return SectionCoverage(
                section_type=section_type,
                heading=heading,
                coverage_score=0.0,
                confidence_score=0.0,
            )

        avg_coverage = sum(pc.coverage_score for pc in paragraph_coverages) / len(paragraph_coverages)

        used_fact_ids = list(all_supporting_ids)
        used_facts = [f for f in facts if f.fact_id in used_fact_ids]
        confidence = sum(f.confidence for f in used_facts) / max(len(used_facts), 1) if used_facts else 0.0

        supported_types = set(f.fact_type for f in used_facts)
        all_fact_types = set(f.fact_type for f in facts)
        missing_types = [ft.value for ft in all_fact_types if ft not in supported_types]

        coverage = SectionCoverage(
            section_type=section_type,
            heading=heading,
            coverage_score=round(avg_coverage, 3),
            confidence_score=round(confidence, 3),
            paragraph_coverages=paragraph_coverages,
            supporting_fact_ids=list(all_supporting_ids),
            fact_count=len(used_fact_ids),
            missing_fact_types=missing_types,
            missing_requirements=list(set(all_missing)),
        )

        logger.info(
            f"Section '{section_type}' coverage: {coverage.coverage_score:.1%} "
            f"({coverage.fact_count} facts, mode={coverage.generation_mode.value})"
        )
        return coverage

    def _compute_paragraph_coverage(
        self,
        para_id: str,
        para_text: str,
        para_fact_ids: List[str],
        section_facts: List[Fact],
    ) -> ParagraphCoverage:
        if not para_text:
            return ParagraphCoverage(
                paragraph_id=para_id,
                paragraph_text="",
                coverage_score=0.0,
            )

        text_lower = para_text.lower()
        matched_fact_ids: Set[str] = set(para_fact_ids)

        for fact in section_facts:
            if fact.fact_id in matched_fact_ids:
                continue
            if self._fact_referenced_in_text(fact, text_lower):
                matched_fact_ids.add(fact.fact_id)

        matched_facts = [f for f in section_facts if f.fact_id in matched_fact_ids]

        total_relevant = len(section_facts)
        if total_relevant == 0:
            return ParagraphCoverage(
                paragraph_id=para_id,
                paragraph_text=para_text,
                coverage_score=0.0,
                missing_requirements=["No evidence available"],
            )

        coverage = len(matched_fact_ids) / max(total_relevant, 1)

        source_docs = list(set(
            f.source.file_path for f in matched_facts if f.source.file_path
        ))
        source_pages = list(set(
            f.source.page_number for f in matched_facts
            if f.source and f.source.page_number is not None
        ))

        missing = []
        required_types = self._get_required_fact_types(para_text)
        matched_types = set(f.fact_type for f in matched_facts)
        for rt in required_types:
            if rt not in matched_types:
                missing.append(f"Missing fact type: {rt.value}")

        return ParagraphCoverage(
            paragraph_id=para_id,
            paragraph_text=para_text,
            coverage_score=round(coverage, 3),
            fact_ids=list(matched_fact_ids),
            source_documents=source_docs,
            source_pages=source_pages,
            missing_requirements=missing,
        )

    def _fact_referenced_in_text(self, fact: Fact, text_lower: str) -> bool:
        value_lower = fact.value.lower()
        if len(value_lower) > 20:
            key_phrases = self._extract_key_phrases(value_lower)
            if any(phrase in text_lower for phrase in key_phrases):
                return True
        return fact.normalized_value[:30] in text_lower

    def _extract_key_phrases(self, text: str) -> List[str]:
        sentences = re.split(r'[.!\n]', text)
        phrases = []
        for sent in sentences:
            words = sent.strip().split()
            if len(words) >= 4:
                phrases.append(" ".join(words[:4]))
            if len(words) >= 6:
                mid = len(words) // 2
                phrases.append(" ".join(words[mid:mid + 4]))
            if len(words) >= 10:
                phrases.append(" ".join(words[-4:]))
        return [p for p in phrases if len(p) > 15]

    def _get_required_fact_types(self, paragraph_text: str) -> Set[FactType]:
        text_lower = paragraph_text.lower()
        required = set()
        if any(w in text_lower for w in ["accuracy", "precision", "recall", "f1", "metric", "score", "evaluation"]):
            required.add(FactType.METRIC)
        if any(w in text_lower for w in ["dataset", "data", "corpus", "benchmark"]):
            required.add(FactType.DATASET)
        if any(w in text_lower for w in ["algorithm", "model", "method", "technique", "classifier"]):
            required.add(FactType.ALGORITHM)
        if any(w in text_lower for w in ["architecture", "system design", "framework", "pipeline"]):
            required.add(FactType.ARCHITECTURE)
        if any(w in text_lower for w in ["result", "achieved", "outperformed", "improvement"]):
            required.add(FactType.RESULT)
        if any(w in text_lower for w in ["objective", "goal", "aim", "purpose"]):
            required.add(FactType.OBJECTIVE)
        return required

    def build_report(
        self,
        sections: Dict[str, Dict],
        facts_by_section: Dict[str, List[Fact]],
    ) -> EvidenceCoverageReport:
        section_coverages = {}
        total_facts = 0

        for section_type, section_data in sections.items():
            heading = section_data.get("heading", section_type)
            paragraphs = section_data.get("paragraphs", [])
            facts = facts_by_section.get(section_type, [])

            coverage = self.compute_section_coverage(
                section_type=section_type,
                heading=heading,
                paragraphs=paragraphs,
                facts=facts,
            )
            section_coverages[section_type] = coverage
            total_facts += len(facts)

        report = EvidenceCoverageReport(
            sections=section_coverages,
            total_facts=total_facts,
        )

        self._reports[report.overall_coverage] = report
        logger.info(
            f"Coverage report: {report.overall_coverage:.1%} overall, "
            f"{report.sections_below_threshold}/{len(report.sections)} sections below threshold"
        )
        return report

    def get_coverage_recommendation(self, section_type: str,
                                     coverage: SectionCoverage) -> str:
        if coverage.generation_mode == GenerationMode.NORMAL:
            return "full generation supported"
        elif coverage.generation_mode == GenerationMode.CAUTIOUS:
            return "generate with evidence gaps flagged"
        elif coverage.generation_mode == GenerationMode.INSUFFICIENT:
            return "report insufficient evidence skip fabrication"
        else:
            return "do not generate section"

    def get_last_report(self) -> Optional[EvidenceCoverageReport]:
        if not self._reports:
            return None
        return self._reports[max(self._reports.keys())]

    def reset(self):
        self._reports.clear()
