from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import uuid
from src.core.logger import get_logger
from src.facts.models import Fact, FactType, SourceReference
from src.facts.store import FactStore

logger = get_logger(__name__)


@dataclass
class ParagraphEvidenceMap:
    paragraph_id: str
    section_type: str
    paragraph_text: str
    fact_ids: List[str] = field(default_factory=list)
    source_references: List[SourceReference] = field(default_factory=list)
    source_documents: List[str] = field(default_factory=list)
    source_pages: List[int] = field(default_factory=list)
    traceability_score: float = 0.0

    @property
    def has_traceability(self) -> bool:
        return len(self.fact_ids) > 0 and len(self.source_references) > 0

    def to_dict(self) -> Dict:
        return {
            "paragraph_id": self.paragraph_id,
            "section_type": self.section_type,
            "fact_count": len(self.fact_ids),
            "fact_ids": self.fact_ids,
            "source_count": len(self.source_documents),
            "source_documents": list(set(self.source_documents)),
            "source_pages": list(set(self.source_pages)),
            "traceability_score": round(self.traceability_score, 3),
            "has_traceability": self.has_traceability,
            "text_preview": self.paragraph_text[:150],
        }


@dataclass
class ReportTraceabilityMap:
    report_id: str
    paragraph_maps: Dict[str, ParagraphEvidenceMap] = field(default_factory=dict)
    fact_coverage: Dict[str, List[str]] = field(default_factory=dict)
    document_coverage: Dict[str, List[str]] = field(default_factory=dict)
    overall_traceability: float = 0.0
    total_paragraphs: int = 0
    traced_paragraphs: int = 0

    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "overall_traceability": round(self.overall_traceability, 3),
            "total_paragraphs": self.total_paragraphs,
            "traced_paragraphs": self.traced_paragraphs,
            "traceability_ratio": round(
                self.traced_paragraphs / max(self.total_paragraphs, 1), 3
            ),
            "fact_coverage": {
                fid: len(para_ids)
                for fid, para_ids in self.fact_coverage.items()
            },
            "document_coverage": {
                doc: len(para_ids)
                for doc, para_ids in self.document_coverage.items()
            },
            "paragraph_count": len(self.paragraph_maps),
        }


class TraceabilityBuilder:
    def __init__(self, fact_store: Optional[FactStore] = None):
        self._fact_store = fact_store or FactStore()
        self._trace_maps: Dict[str, ReportTraceabilityMap] = {}

    def build_paragraph_map(
        self,
        paragraph_id: str,
        section_type: str,
        paragraph_text: str,
        paragraph_fact_ids: Optional[List[str]] = None,
    ) -> ParagraphEvidenceMap:
        fact_ids: Set[str] = set(paragraph_fact_ids or [])

        source_refs: List[SourceReference] = []
        source_docs: Set[str] = set()
        source_pages: Set[int] = set()

        for fid in fact_ids:
            fact = self._fact_store.get(fid)
            if fact:
                source_refs.append(fact.source)
                if fact.source.file_path:
                    source_docs.add(fact.source.file_path)
                if fact.source.page_number is not None:
                    source_pages.add(fact.source.page_number)

        if not fact_ids:
            matched_facts = self._find_facts_in_text(paragraph_text)
            for fact in matched_facts:
                fact_ids.add(fact.fact_id)
                source_refs.append(fact.source)
                if fact.source.file_path:
                    source_docs.add(fact.source.file_path)
                if fact.source.page_number is not None:
                    source_pages.add(fact.source.page_number)

        score = 0.0
        if fact_ids:
            confidences = []
            for fid in fact_ids:
                fact = self._fact_store.get(fid)
                if fact:
                    confidences.append(fact.confidence)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            source_div = min(len(source_docs) / 3.0, 1.0)
            score = avg_conf * 0.6 + source_div * 0.4

        return ParagraphEvidenceMap(
            paragraph_id=paragraph_id,
            section_type=section_type,
            paragraph_text=paragraph_text,
            fact_ids=list(fact_ids),
            source_references=source_refs,
            source_documents=list(source_docs),
            source_pages=list(source_pages),
            traceability_score=round(score, 3),
        )

    def build_report_map(
        self,
        report_id: str,
        sections: Dict[str, List[Dict]],
    ) -> ReportTraceabilityMap:
        para_maps: Dict[str, ParagraphEvidenceMap] = {}
        fact_to_paras: Dict[str, List[str]] = defaultdict(list)
        doc_to_paras: Dict[str, List[str]] = defaultdict(list)
        total = 0
        traced = 0

        for section_type, paragraphs in sections.items():
            for i, para in enumerate(paragraphs):
                para_id = para.get("paragraph_id", f"{section_type}_p{i}")
                para_text = para.get("text", "")
                para_fact_ids = para.get("fact_ids", [])

                pm = self.build_paragraph_map(
                    paragraph_id=para_id,
                    section_type=section_type,
                    paragraph_text=para_text,
                    paragraph_fact_ids=para_fact_ids,
                )
                para_maps[para_id] = pm
                total += 1

                for fid in pm.fact_ids:
                    fact_to_paras[fid].append(para_id)
                for doc in pm.source_documents:
                    doc_to_paras[doc].append(para_id)
                if pm.has_traceability:
                    traced += 1

        trace_map = ReportTraceabilityMap(
            report_id=report_id,
            paragraph_maps=para_maps,
            fact_coverage=dict(fact_to_paras),
            document_coverage=dict(doc_to_paras),
            overall_traceability=round(traced / max(total, 1), 3),
            total_paragraphs=total,
            traced_paragraphs=traced,
        )

        self._trace_maps[report_id] = trace_map
        logger.info(
            f"Traceability map '{report_id}': {trace_map.traced_paragraphs}/"
            f"{trace_map.total_paragraphs} paragraphs traced "
            f"(score={trace_map.overall_traceability:.1%})"
        )
        return trace_map

    def _find_facts_in_text(self, text: str) -> List[Fact]:
        text_lower = text.lower()
        matched = []
        for fact in self._fact_store.get_all_facts():
            if fact.normalized_value[:40] in text_lower:
                matched.append(fact)
            elif any(c.lower() in text_lower for c in fact.concepts):
                matched.append(fact)
        return matched[:5]

    def trace_paragraph(self, paragraph_id: str) -> Optional[ParagraphEvidenceMap]:
        for trace_map in self._trace_maps.values():
            if paragraph_id in trace_map.paragraph_maps:
                return trace_map.paragraph_maps[paragraph_id]
        return None

    def trace_fact(self, fact_id: str) -> List[ParagraphEvidenceMap]:
        results = []
        for trace_map in self._trace_maps.values():
            para_ids = trace_map.fact_coverage.get(fact_id, [])
            for pid in para_ids:
                if pid in trace_map.paragraph_maps:
                    results.append(trace_map.paragraph_maps[pid])
        return results

    def trace_source(self, source_path: str) -> List[ParagraphEvidenceMap]:
        results = []
        for trace_map in self._trace_maps.values():
            para_ids = trace_map.document_coverage.get(source_path, [])
            for pid in para_ids:
                if pid in trace_map.paragraph_maps:
                    results.append(trace_map.paragraph_maps[pid])
        return results

    def get_report_map(self, report_id: str) -> Optional[ReportTraceabilityMap]:
        return self._trace_maps.get(report_id)

    def get_summary(self) -> Dict:
        if not self._trace_maps:
            return {"total_reports": 0}
        total_paras = sum(m.total_paragraphs for m in self._trace_maps.values())
        total_traced = sum(m.traced_paragraphs for m in self._trace_maps.values())
        return {
            "total_reports": len(self._trace_maps),
            "total_paragraphs": total_paras,
            "total_traced": total_traced,
            "overall_traceability": round(total_traced / max(total_paras, 1), 3),
        }

    def reset(self):
        self._trace_maps.clear()
