from typing import Dict, List, Optional, Any
from src.core.logger import get_logger
from src.facts.store import FactStore
from src.facts.models import Fact, FactType
from src.evidence.traceability import TraceabilityBuilder, ParagraphEvidenceMap
from src.evidence.coverage_engine import CoverageEngine
from src.knowledge.knowledge_graph import ProjectKnowledgeGraph

logger = get_logger(__name__)


class ReportExplainer:
    def __init__(self, fact_store: FactStore,
                 traceability: TraceabilityBuilder,
                 coverage_engine: CoverageEngine,
                 knowledge_graph: ProjectKnowledgeGraph):
        self._fact_store = fact_store
        self._traceability = traceability
        self._coverage_engine = coverage_engine
        self._knowledge_graph = knowledge_graph

    def explain_paragraph(self, paragraph_id: str) -> Dict:
        pm = self._traceability.trace_paragraph(paragraph_id)
        if not pm:
            return {"paragraph_id": paragraph_id, "status": "not_found"}

        fact_details = []
        for fid in pm.fact_ids:
            fact = self._fact_store.get(fid)
            if fact:
                fact_details.append(fact.to_dict())

        return {
            "paragraph_id": pm.paragraph_id,
            "section_type": pm.section_type,
            "traceability_score": pm.traceability_score,
            "has_traceability": pm.has_traceability,
            "facts": fact_details,
            "source_documents": list(set(pm.source_documents)),
            "source_pages": list(set(pm.source_pages)),
            "text_preview": pm.paragraph_text[:200],
        }

    def explain_section(self, section_type: str,
                         paragraphs: List[Dict]) -> Dict:
        para_explanations = []
        total_facts = set()
        total_sources = set()

        for para in paragraphs:
            para_id = para.get("paragraph_id", "unknown")
            explanation = self.explain_paragraph(para_id)
            para_explanations.append(explanation)
            for fid in explanation.get("facts", []):
                total_facts.add(fid.get("fact_id"))
            for doc in explanation.get("source_documents", []):
                total_sources.add(doc)

        return {
            "section_type": section_type,
            "paragraph_count": len(paragraphs),
            "unique_facts_used": len(total_facts),
            "unique_sources_used": len(total_sources),
            "paragraphs": para_explanations,
        }

    def explain_report(self, sections: Dict[str, List[Dict]]) -> Dict:
        section_explanations = {}
        total_facts = set()
        total_sources = set()

        for section_type, paragraphs in sections.items():
            explanation = self.explain_section(section_type, paragraphs)
            section_explanations[section_type] = explanation
            for para in explanation.get("paragraphs", []):
                for fact in para.get("facts", []):
                    total_facts.add(fact.get("fact_id"))
                for doc in para.get("source_documents", []):
                    total_sources.add(doc)

        return {
            "sections": section_explanations,
            "total_facts_used": len(total_facts),
            "total_sources_used": len(total_sources),
            "section_count": len(sections),
        }

    def trace_claim_to_source(self, claim: str) -> Dict:
        matching_facts = self._fact_store.search(claim)
        if not matching_facts:
            return {
                "claim": claim[:200],
                "status": "no_matching_evidence",
                "recommendation": "Claim cannot be verified against stored evidence",
            }

        results = []
        for fact in matching_facts[:5]:
            pm_list = self._traceability.trace_fact(fact.fact_id)
            results.append({
                "fact": fact.to_dict(),
                "used_in_paragraphs": [pm.paragraph_id for pm in pm_list],
                "source_document": fact.source.file_name,
                "source_page": fact.source.page_number,
            })

        return {
            "claim": claim[:200],
            "status": "evidence_found",
            "matching_facts_count": len(matching_facts),
            "results": results,
        }

    def get_explainability_summary(self) -> Dict:
        trace_summary = self._traceability.get_summary()
        report = self._coverage_engine.get_last_report()

        return {
            "traceability": trace_summary,
            "coverage": report.to_dict() if report else None,
            "fact_store_stats": self._fact_store.get_statistics(),
            "graph_summary": self._knowledge_graph.to_dict(),
        }
