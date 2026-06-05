from typing import Dict, List, Optional, Any
from src.core.logger import get_logger
from src.facts.store import FactStore
from src.facts.models import FactType
from src.facts.linker import FactLinker
from src.evidence.coverage_engine import CoverageEngine
from src.evidence.traceability import TraceabilityBuilder
from src.knowledge.knowledge_graph import ProjectKnowledgeGraph, NodeType
from src.resource_intelligence.resource_metadata_store import ResourceMetadataStore

logger = get_logger(__name__)


class EvidenceDashboard:
    def __init__(self, fact_store: FactStore,
                 coverage_engine: CoverageEngine,
                 traceability: TraceabilityBuilder,
                 knowledge_graph: ProjectKnowledgeGraph,
                 resource_store: Optional[ResourceMetadataStore] = None):
        self._fact_store = fact_store
        self._coverage_engine = coverage_engine
        self._traceability = traceability
        self._knowledge_graph = knowledge_graph
        self._resource_store = resource_store or ResourceMetadataStore()

    def get_overview(self) -> Dict:
        fact_stats = self._fact_store.get_statistics()
        trace_summary = self._traceability.get_summary()
        report = self._coverage_engine.get_last_report()
        graph_dict = self._knowledge_graph.to_dict()

        return {
            "fact_store": {
                "total_facts": fact_stats.get("total", 0),
                "by_type": fact_stats.get("by_type", {}),
                "avg_confidence": fact_stats.get("avg_confidence", 0),
                "by_resource": fact_stats.get("by_resource", {}),
            },
            "coverage": report.to_dict() if report else {"status": "no_report"},
            "traceability": trace_summary,
            "knowledge_graph": {
                "node_count": graph_dict.get("node_count", 0),
                "edge_count": graph_dict.get("edge_count", 0),
                "by_type": graph_dict.get("by_type", {}),
            },
            "resources": self._resource_store.get_summary(),
        }

    def get_section_dashboard(self, section_type: str) -> Dict:
        facts = self._fact_store.get_by_type(self._fact_type_from_name(section_type))
        coverage = None
        report = self._coverage_engine.get_last_report()
        if report and section_type in report.sections:
            coverage = report.sections[section_type]

        return {
            "section_type": section_type,
            "facts_available": len(facts),
            "fact_types": list(set(f.fact_type.value for f in facts)),
            "avg_confidence": round(
                sum(f.confidence for f in facts) / max(len(facts), 1), 3
            ),
            "coverage": coverage.to_dict() if coverage else None,
        }

    def get_fact_browser(self, page: int = 0, per_page: int = 20) -> Dict:
        all_facts = self._fact_store.get_all_facts()
        start = page * per_page
        end = start + per_page
        page_facts = all_facts[start:end]

        return {
            "total": len(all_facts),
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (len(all_facts) + per_page - 1) // per_page),
            "facts": [f.to_dict() for f in page_facts],
            "by_type": {
                ft.value: sum(1 for f in all_facts if f.fact_type == ft)
                for ft in FactType
            },
        }

    def get_source_browser(self) -> Dict:
        resources = self._resource_store.list_all()
        source_facts: Dict[str, List[Dict]] = {}
        for resource in resources:
            facts = self._fact_store.get_by_resource(resource.resource_id)
            source_facts[resource.file_name] = {
                "resource_id": resource.resource_id,
                "type": resource.resource_type,
                "fact_count": len(facts),
                "confidence": resource.confidence,
                "facts": [f.to_dict() for f in facts[:10]],
            }

        return {
            "total_sources": len(resources),
            "sources": source_facts,
        }

    def get_coverage_report(self) -> Dict:
        report = self._coverage_engine.get_last_report()
        if not report:
            return {"status": "no_coverage_report"}
        return report.to_dict()

    def get_missing_information_report(self) -> Dict:
        report = self._coverage_engine.get_last_report()
        if not report:
            return {"missing_sections": [], "missing_fact_types": {}, "recommendations": []}

        missing_sections = []
        for section_type, coverage in report.sections.items():
            if coverage.coverage_level.value in ("low", "none"):
                missing_sections.append({
                    "section_type": section_type,
                    "coverage": coverage.coverage_score,
                    "missing_fact_types": coverage.missing_fact_types,
                    "recommendation": "Add more evidence before generating this section",
                })

        return {
            "missing_sections": missing_sections,
            "recommendations": [
                f"Add evidence for {len(missing_sections)} under-covered sections"
            ],
            "overall_assessment": (
                "sufficient" if report.generation_mode.value in ("normal", "cautious")
                else "insufficient"
            ),
        }

    def get_resource_summary(self) -> Dict:
        resources = self._resource_store.list_all()
        return {
            "total_resources": len(resources),
            "resource_breakdown": {
                rtype: sum(1 for r in resources if r.resource_type == rtype)
                for rtype in set(r.resource_type for r in resources)
            },
            "total_evidence_categories": sum(r.evidence_count for r in resources),
            "recommended_sections": list(set(
                s for r in resources for s in r.recommended_sections
            )),
        }

    def _fact_type_from_name(self, name: str) -> FactType:
        mapping = {
            "introduction": FactType.OBJECTIVE,
            "methodology": FactType.ALGORITHM,
            "implementation": FactType.TECHNOLOGY,
            "results": FactType.RESULT,
            "discussion": FactType.RESULT,
            "experimental_setup": FactType.DATASET,
        }
        return mapping.get(name.lower().replace(" ", "_"), FactType.GENERAL)
