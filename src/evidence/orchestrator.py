from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from src.core.logger import get_logger
from src.facts.models import Fact, FactType
from src.facts.store import FactStore, FactStoreConfig
from src.facts.extractor import FactExtractor
from src.facts.validator import FactValidator
from src.facts.linker import FactLinker, FactLink
from src.facts.generation_controller import EvidenceConstrainedGenerator, GenerationConstraint
from src.evidence.coverage_engine import CoverageEngine
from src.evidence.coverage_validator import CoverageValidator
from src.evidence.traceability import TraceabilityBuilder, ReportTraceabilityMap
from src.evidence.fusion_engine import EvidenceFusionEngine, FusionResult
from src.evidence.dashboard import EvidenceDashboard
from src.evidence.report_explainability import ReportExplainer
from src.knowledge.knowledge_graph import ProjectKnowledgeGraph, NodeType, RelationType
from src.resource_intelligence.resource_classifier import ResourceClassifier, ResourceType
from src.resource_intelligence.resource_profiler import ResourceProfiler, ResourceProfile
from src.resource_intelligence.resource_analyzer import ResourceAnalyzer, AnalysisResult
from src.resource_intelligence.resource_metadata_store import ResourceMetadataStore
from src.resource_intelligence.resource_relationship_builder import ResourceRelationshipBuilder
from src.document.blueprint.evidence_blueprint_generator import EvidenceBlueprintGenerator, EvidenceBlueprint

logger = get_logger(__name__)


@dataclass
class EvidencePipelineResult:
    success: bool
    fact_count: int = 0
    section_count: int = 0
    coverage: float = 0.0
    traceability: float = 0.0
    blueprint: Optional[EvidenceBlueprint] = None
    constraints: Dict[str, GenerationConstraint] = field(default_factory=dict)
    fusion_results: List[FusionResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "fact_count": self.fact_count,
            "section_count": self.section_count,
            "coverage": self.coverage,
            "traceability": self.traceability,
            "has_blueprint": self.blueprint is not None,
            "constraint_count": len(self.constraints),
            "fusion_count": len(self.fusion_results),
            "errors": self.errors,
        }


class EvidenceOrchestrator:
    def __init__(self):
        self.fact_store = FactStore(FactStoreConfig(deduplicate_on_insert=True))
        self.fact_extractor = FactExtractor()
        self.fact_validator = FactValidator()
        self.fact_linker = FactLinker()
        self.coverage_engine = CoverageEngine(self.fact_store)
        self.coverage_validator = CoverageValidator()
        self.traceability = TraceabilityBuilder(self.fact_store)
        self.fusion_engine = EvidenceFusionEngine(self.fact_store)
        self.knowledge_graph = ProjectKnowledgeGraph()
        self.resource_classifier = ResourceClassifier()
        self.resource_profiler = ResourceProfiler()
        self.resource_analyzer = ResourceAnalyzer(self.resource_classifier, self.resource_profiler)
        self.resource_store = ResourceMetadataStore()
        self.relationship_builder = ResourceRelationshipBuilder(self.resource_store)
        self.blueprint_generator = EvidenceBlueprintGenerator(self.fact_store, self.coverage_engine)
        self.generation_controller = EvidenceConstrainedGenerator(
            self.fact_store, self.coverage_engine
        )
        self.dashboard = EvidenceDashboard(
            self.fact_store, self.coverage_engine,
            self.traceability, self.knowledge_graph, self.resource_store
        )
        self.explainer = ReportExplainer(
            self.fact_store, self.traceability,
            self.coverage_engine, self.knowledge_graph
        )

    def ingest_resource(self, file_path: str, content: str) -> Dict:
        analysis = self.resource_analyzer.analyze(file_path, content)
        metadata = self.resource_store.store(file_path, analysis)

        source = self._make_source_ref(
            resource_id=metadata.resource_id,
            file_path=file_path,
            file_name=metadata.file_name,
        )
        extraction = self.fact_extractor.extract(content, source)
        validated = self.fact_validator.get_high_confidence_facts(extraction.facts)
        added = self.fact_store.add_facts(validated)

        for fact in validated:
            self.knowledge_graph.add_fact(fact)

        return {
            "resource_id": metadata.resource_id,
            "file_name": metadata.file_name,
            "resource_type": metadata.resource_type,
            "facts_extracted": len(extraction.facts),
            "facts_validated": len(validated),
            "facts_added": added,
            "evidence_categories": analysis.has_evidence_categories,
            "recommended_sections": analysis.recommended_sections,
        }

    def ingest_chunks(self, chunks: List[Dict]) -> Dict:
        total_facts = 0
        for chunk in chunks:
            text = chunk.get("text", chunk.get("content", ""))
            if not text:
                continue
            meta = chunk.get("metadata", {})
            file_path = meta.get("source", "unknown")
            file_name = meta.get("file_name", file_path.split("/")[-1].split("\\")[-1])

            analysis = self.resource_analyzer.analyze(file_path, text)
            metadata = self.resource_store.store(file_path, analysis)
            source = self._make_source_ref(
                resource_id=metadata.resource_id,
                file_path=file_path,
                file_name=file_name,
                chunk_meta=meta,
            )
            extraction = self.fact_extractor.extract(text, source, meta)
            validated = self.fact_validator.get_high_confidence_facts(extraction.facts)
            added = self.fact_store.add_facts(validated)
            total_facts += added

            for fact in validated:
                self.knowledge_graph.add_fact(fact)

        return {"chunks_processed": len(chunks), "total_facts": total_facts}

    def build_graph(self) -> Dict:
        all_facts = self.fact_store.get_all_facts()
        self.fact_linker.link_facts(all_facts)
        node_count = self.knowledge_graph.build_from_facts(all_facts)

        self.fusion_engine.fuse_all(all_facts)

        return {
            "nodes": node_count,
            "edges": len(self.fact_linker.get_all_links()),
            "fusion_results": len(self.fusion_engine.get_all_results()),
        }

    def generate_blueprint(self, title: str) -> EvidenceBlueprint:
        all_facts = self.fact_store.get_all_facts()
        blueprint = self.blueprint_generator.generate(title, all_facts)
        return blueprint

    def build_generation_constraints(self, blueprint: EvidenceBlueprint) -> Dict[str, GenerationConstraint]:
        all_facts = self.fact_store.get_all_facts()
        facts_by_section: Dict[str, List[Fact]] = {}
        for section in blueprint.sections:
            required_types = [FactType(ft) for ft in section.required_fact_types]
            section_facts = [f for f in all_facts if f.fact_type in required_types]
            facts_by_section[section.section_type] = section_facts

        constraints = self.generation_controller.build_constraints(
            [s.section_type for s in blueprint.sections],
            facts_by_section,
        )
        return constraints

    def get_generation_prompts(self, constraints: Dict[str, GenerationConstraint]) -> Dict[str, str]:
        prompts = {}
        all_facts = self.fact_store.get_all_facts()
        for section_type, constraint in constraints.items():
            required_types = [FactType(ft) for ft in constraint.allowed_fact_ids]
            section_facts = [f for f in all_facts if f.fact_id in constraint.allowed_fact_ids]
            prompt = self.generation_controller.get_section_prompt(
                section_type, constraint, section_facts
            )
            prompts[section_type] = prompt
        return prompts

    def validate_generated_content(self, sections: Dict[str, str]) -> Dict:
        all_facts = self.fact_store.get_all_facts()
        validations = {}
        for section_type, text in sections.items():
            constraint = self.generation_controller.get_constraint(section_type)
            if not constraint:
                continue
            section_facts = [f for f in all_facts if f.fact_id in constraint.allowed_fact_ids]
            validation = self.generation_controller.validate_output(
                section_type, text, constraint, section_facts
            )
            validations[section_type] = validation
        return validations

    def build_traceability_map(self, report_id: str,
                                sections: Dict[str, List[Dict]]) -> ReportTraceabilityMap:
        return self.traceability.build_report_map(report_id, sections)

    def get_dashboard_data(self) -> Dict:
        return self.dashboard.get_overview()

    def run(self, resources: List[Dict], title: str) -> EvidencePipelineResult:
        errors = []
        total_facts = 0
        for resource in resources:
            try:
                result = self.ingest_resource(
                    resource.get("file_path", ""),
                    resource.get("content", ""),
                )
                total_facts += result["facts_added"]
            except Exception as e:
                errors.append(f"Resource ingestion failed: {e}")

        try:
            graph_result = self.build_graph()
        except Exception as e:
            errors.append(f"Graph build failed: {e}")

        try:
            blueprint = self.generate_blueprint(title)
        except Exception as e:
            errors.append(f"Blueprint generation failed: {e}")
            blueprint = EvidenceBlueprint(title=title)

        try:
            constraints = self.build_generation_constraints(blueprint)
        except Exception as e:
            errors.append(f"Constraint building failed: {e}")
            constraints = {}

        fusion_results = self.fusion_engine.get_all_results()
        report = self.coverage_engine.get_last_report()
        coverage = report.overall_coverage if report else 0.0
        trace = self.traceability.get_summary()

        return EvidencePipelineResult(
            success=len(errors) == 0,
            fact_count=total_facts,
            section_count=len(blueprint.sections),
            coverage=coverage,
            traceability=trace.get("overall_traceability", 0),
            blueprint=blueprint,
            constraints=constraints,
            fusion_results=fusion_results,
            errors=errors,
        )

    def get_statistics(self) -> Dict:
        return {
            "fact_store": self.fact_store.get_statistics(),
            "knowledge_graph": self.knowledge_graph.to_dict(),
            "traceability": self.traceability.get_summary(),
            "resources": self.resource_store.get_summary(),
            "fact_links": self.fact_linker.get_statistics(),
            "coverage": self.coverage_engine.get_last_report().to_dict()
            if self.coverage_engine.get_last_report() else None,
        }

    def reset(self):
        self.fact_store.clear()
        self.fact_extractor.reset()
        self.fact_validator.reset()
        self.fact_linker.reset()
        self.coverage_engine.reset()
        self.coverage_validator.reset()
        self.traceability.reset()
        self.fusion_engine.reset()
        self.knowledge_graph.reset()
        self.resource_classifier.reset()
        self.resource_profiler.reset()
        self.resource_analyzer.reset()
        self.resource_store.reset()
        self.relationship_builder.reset()
        self.generation_controller.reset()

    @staticmethod
    def _make_source_ref(resource_id: str, file_path: str, file_name: str,
                          chunk_meta: Optional[Dict] = None):
        from src.facts.models import SourceReference
        return SourceReference(
            resource_id=resource_id,
            file_path=file_path,
            file_name=file_name,
            page_number=chunk_meta.get("page_number") if chunk_meta else None,
            chunk_id=chunk_meta.get("chunk_id") if chunk_meta else None,
        )
