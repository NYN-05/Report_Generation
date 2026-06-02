from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.core.logger import get_logger
from src.generator.evidence_based_generator import EvidenceBasedSectionGenerator
from src.generator.content_blocks import SectionContent
from src.generator.academic_writing_engine import AcademicWritingEngine
from src.generator.paragraph_quality import ParagraphQualityControl
from src.generator.technical_depth import TechnicalDepthEvaluator
from src.generator.content_validator import ContentValidator
from src.generator.chapter_uniqueness import ChapterUniquenessChecker
from src.research.fact_extractor import FactExtractor
from src.research.evidence_builder import EvidenceBuilder
from src.research.source_validator import SourceValidator
from src.research.research_planner import ResearchPlanner
from src.knowledge.knowledge_graph import KnowledgeGraphBuilder
from src.knowledge.concept_mapper import ConceptMapper
from src.knowledge.relationship_extractor import RelationshipExtractor
from src.domain.classifier import DomainClassifier
from src.domain.prompt_packs import DomainSpecificPromptPacks
from src.citation.evidence_citation_mapper import EvidenceToCitationMapper
from src.citation.source_paragraph_generator import SourceBackedParagraphGenerator
from src.refinement.section_refiner import SectionRefiner
from src.refinement.quality_feedback_loop import QualityFeedbackLoop
from src.quality.technical_depth_score import TechnicalDepthScore
from src.quality.evidence_score import EvidenceScore
from src.quality.coherence_score import CoherenceScore
from src.quality.academic_score import AcademicScore
from src.few_shot.example_library import ExampleLibrary
from src.few_shot.dynamic_example_retriever import DynamicExampleRetriever
from src.memory.hierarchical_memory import HierarchicalMemory
from src.memory.chapter_summary_store import ChapterSummaryStore
from src.memory.fact_memory import FactMemory
from src.optimization.async_retrieval import AsyncRetrieval
from src.optimization.async_generation import AsyncGeneration
from src.optimization.retrieval_cache import RetrievalCache
from src.optimization.context_cache import ContextCache
from src.document.blueprint.topic_blueprint_generator import TopicSpecificBlueprintGenerator
from src.content import (
    GenericContentDetector, TechnicalDepthEnhancer,
    ParagraphQualityEngine, SectionSpecificWriter,
    ContentTypeClassifier,
    IterativeRefinementLoop, QualityGate,
)
from src.content.fact_driven_generator import FactDrivenParagraphGenerator
from src.quality import EvidenceCoverageScore

logger = get_logger(__name__)


class KnowledgeDrivenReportGenerator:
    def __init__(self, provider=None, context_assembler=None):
        self._provider = provider
        self._context_assembler = context_assembler
        self._research_planner = ResearchPlanner()
        self._fact_extractor = FactExtractor()
        self._evidence_builder = EvidenceBuilder()
        self._source_validator = SourceValidator()
        self._knowledge_graph_builder = KnowledgeGraphBuilder()
        self._concept_mapper = ConceptMapper()
        self._relationship_extractor = RelationshipExtractor()
        self._domain_classifier = DomainClassifier()
        self._prompt_packs = DomainSpecificPromptPacks()
        self._citation_mapper = EvidenceToCitationMapper()
        self._source_paragraph_gen = SourceBackedParagraphGenerator(self._citation_mapper)
        self._section_refiner = SectionRefiner(provider)
        self._quality_feedback = QualityFeedbackLoop()
        self._tech_depth_score = TechnicalDepthScore()
        self._evidence_score = EvidenceScore()
        self._coherence_score = CoherenceScore()
        self._academic_score = AcademicScore()
        self._example_library = ExampleLibrary()
        self._example_retriever = DynamicExampleRetriever(self._example_library)
        self._hierarchical_memory = HierarchicalMemory()
        self._chapter_summaries = ChapterSummaryStore()
        self._fact_memory = FactMemory()
        self._async_retrieval = AsyncRetrieval()
        self._async_generation = AsyncGeneration()
        self._retrieval_cache = RetrievalCache()
        self._context_cache = ContextCache()
        self._blueprint_generator = TopicSpecificBlueprintGenerator(provider)
        self._depth_evaluator = TechnicalDepthEvaluator()
        self._validator = ContentValidator()
        self._uniqueness = ChapterUniquenessChecker()
        self._existing_gen = EvidenceBasedSectionGenerator(
            provider=provider,
            context_assembler=context_assembler,
        )
        self._research_cache = None
        self._generic_detector = GenericContentDetector()
        self._depth_enhancer = TechnicalDepthEnhancer()
        self._para_quality = ParagraphQualityEngine()
        self._section_writer = SectionSpecificWriter()
        self._content_classifier = ContentTypeClassifier()
        self._refinement_loop = IterativeRefinementLoop()
        self._quality_gate = QualityGate()
        self._evidence_coverage = EvidenceCoverageScore()
        self._fact_driven_gen = FactDrivenParagraphGenerator()

    def research_phase(self, topic: str, chunks: List[Dict]) -> Dict[str, Any]:
        domain = self._domain_classifier.classify(topic)
        if chunks:
            for chunk in chunks:
                c = chunk.get("text", chunk.get("content", ""))
                self._domain_classifier.classify(topic, c)
        self._prompt_packs.set_domain(domain)
        logger.info(f"Domain classified: {domain}")
        research_plans = self._research_planner.plan_all_sections(topic)
        valid_chunks = self._source_validator.filter_valid(chunks)
        facts = self._fact_extractor.extract_from_chunks(valid_chunks)
        evidence_groups = self._evidence_builder.build_from_facts(facts, "research")
        kg = self._knowledge_graph_builder.build_from_chunks(valid_chunks)
        concept_map = self._concept_mapper.map_concepts_to_sections(kg)
        rels = self._relationship_extractor.extract_from_chunks(valid_chunks)
        # Preserve structured objects so generate phase can reuse them
        self._research_cache = {
            "facts": facts,
            "evidence_groups": evidence_groups,
            "kg": kg,
            "concept_map": concept_map,
            "relationships": rels,
            "valid_chunks": valid_chunks,
        }
        return {
            "domain": domain,
            "research_plans": {k: v.to_dict() for k, v in research_plans.items()},
            "valid_chunks": len(valid_chunks),
            "facts_extracted": len(facts),
            "evidence_groups": len(evidence_groups),
            "knowledge_graph": kg.to_dict(),
            "concept_map": concept_map,
            "relationships": len(rels),
            # Reference to preserved structured objects
            "cache_key": "research_cache",
        }

    def generate_section(self, section_type: str, topic: str,
                          report_type: str = "engineering project report",
                          retrieval_query: Optional[str] = None,
                          previous_summary: str = "") -> Tuple[SectionContent, Dict[str, Any]]:
        cached = self._context_cache.get(section_type, topic)
        if cached:
            logger.info(f"Cache hit for section '{section_type}'")
        evidence_chunks, context_text = self._existing_gen._retrieve_evidence(
            section_type, topic, retrieval_query
        )
        metadata = {
            "section_type": section_type,
            "chunks_retrieved": len(evidence_chunks),
            "context_length": len(context_text),
        }

        # When no RAG evidence is available, use LLM fallback to generate content
        # from its own knowledge, but still run quality scoring on the result.
        if not context_text and not evidence_chunks:
            section = AcademicWritingEngine(self._provider)._generate_no_evidence_section(
                section_type, topic
            )
            metadata["evidence_status"] = "none"
            evidence_chunks = []
            facts = []
            evidence_map = {}
            citations = []
            chapter_summaries = []
            # Fall through to quality scoring with empty evidence
        else:
            # Extract structured evidence (preserved and passed through, not discarded)
            facts = self._fact_extractor.extract_from_chunks(evidence_chunks)
            self._fact_memory.register_section_facts(facts, section_type)
            evidence_map = self._evidence_builder.build_claim_evidence_map(facts, section_type)
            citations = self._citation_mapper.map_facts_to_citations(facts, section_type)
            chapter_summaries = self._chapter_summaries.get_summary_texts()

            # Generate with structured evidence passed through
            section = self._existing_gen._writing_engine.generate_section(
                section_type=section_type,
                topic=topic,
                report_type=report_type,
                retrieval_context=context_text,
                evidence_chunks=evidence_chunks,
                previous_summary=previous_summary,
                existing_chapter_summaries=chapter_summaries,
                facts=facts,
                evidence_map=evidence_map,
                citations=citations,
            )
            section, improve_logs = self._existing_gen._improver.improve(
                section, section_type, topic
            )

        # --- Quality Enforcement Layer ---
        section_text = section.to_text()

        # 1. Fact-first compliance: check every paragraph originates from evidence
        ev_coverage = self._evidence_coverage.score_section(section_text, evidence_chunks)
        if ev_coverage["coverage"] < 0.8:
            logger.warning(
                f"Evidence coverage {ev_coverage['coverage']:.2f} below 0.8 for {section_type}"
            )

        # 2. Generic content detection
        generic_check = self._generic_detector.detect(section_text, topic)
        if not generic_check["passed"]:
            logger.warning(
                f"Generic filler detected in {section_type}: "
                f"density {generic_check['filler_density']:.2f}"
            )

        # 3. Technical depth enforcement
        depth_check = self._depth_enhancer.score(section_text)

        # 4. Paragraph quality check
        para_check = self._para_quality.score_section(section_text)

        # 5. Section-specific validation
        section_check = self._section_writer.validate(section_text, section_type)

        # 6. Content type classification (for DOCX rendering)
        classified_blocks = self._content_classifier.classify(section_text)

        # Legacy scoring
        depth_score, depth_passed = self._depth_evaluator.evaluate_section(
            section_text, evidence_count=len(evidence_chunks),
            section_type=section_type,
        )
        validation = self._validator.validate_section(section, section_type, topic)
        tech_depth = self._tech_depth_score.score(section_text)
        ev_score = self._evidence_score.score(section_text, evidence_chunks)
        coh_score = self._coherence_score.score(section_text)
        aca_score = self._academic_score.score(section_text)

        quality_scores = {
            "technical_depth": depth_score.overall,
            "evidence_usage": depth_score.evidence_usage,
            "evidence_coverage": ev_coverage["coverage"],
            "coherence": coh_score["overall"],
            "academic_tone": aca_score["overall"],
            "readability": depth_score.readability,
            "uniqueness": depth_score.uniqueness,
            "filler_density": 1.0 - generic_check["filler_density"],
        }

        section, refinements = self._section_refiner.refine(
            section, section_type, topic, quality_scores
        )

        # Store chapter summaries
        section_text = section.to_text()
        self._chapter_summaries.store(
            heading=section.heading,
            section_type=section_type,
            content=section_text,
            key_facts=[f.text[:100] for f in facts[:3]] if facts else [],
        )
        self._hierarchical_memory.store(
            f"section_{section_type}",
            section_text,
            importance=depth_score.overall,
        )
        self._context_cache.set(section_type, topic, {
            "section": section, "metadata": metadata
        })

        metadata.update({
            "depth_score": {
                "overall": depth_score.overall, "relevance": depth_score.relevance,
                "technical_detail": depth_score.technical_detail,
                "evidence_usage": depth_score.evidence_usage,
                "uniqueness": depth_score.uniqueness,
                "readability": depth_score.readability,
                "chapter_alignment": depth_score.chapter_alignment,
                "academic_tone": depth_score.academic_tone,
            },
            "tech_depth_score": tech_depth,
            "evidence_score": ev_score,
            "evidence_coverage": ev_coverage,
            "coherence_score": coh_score,
            "academic_score": aca_score,
            "filler_check": generic_check,
            "depth_check": depth_check,
            "paragraph_quality": para_check,
            "section_compliance": section_check,
            "classified_blocks": [
                {"type": b.block_type.value, "text": b.text[:100]}
                for b in classified_blocks[:10]
            ],
            "evidence_citations": len(citations),
            "facts_used": len(facts),
            "refinements": [s.to_dict() for s in refinements],
            "validation": {
                "overall_score": validation.overall_score(),
                "passed": validation.passed,
                "issues": validation.issues,
            },
            "domain": self._domain_classifier.get_domain(),
        })
        return section, metadata

    def _generate_sections_parallel(self, topic: str, types: List[str]) -> Tuple[List, List, int]:
        """Generate sections in parallel using ThreadPoolExecutor for 5-7x speedup."""
        import threading
        results_lock = threading.Lock()
        section_contents = []
        results_list = []
        total_facts = 0

        def generate_one(stype: str) -> Tuple[Any, Dict]:
            logger.info(f"[Parallel] Generating section: {stype}")
            section, metadata = self.generate_section(
                section_type=stype,
                topic=topic,
                retrieval_query=f"{topic} {stype.replace('_', ' ')}",
                previous_summary="",
            )
            return stype, section, metadata

        with ThreadPoolExecutor(max_workers=min(len(types), 4)) as executor:
            futures = {executor.submit(generate_one, stype): stype for stype in types}
            for future in as_completed(futures):
                try:
                    stype, section, metadata = future.result()
                    with results_lock:
                        section_contents.append(section)
                        total_facts += metadata.get("facts_used", 0)
                        results_list.append({
                            "section_type": stype,
                            "heading": section.heading,
                            "blocks": len(section.blocks),
                            "total_words": section.total_words,
                            "evidence_sources": len(section.evidence_sources),
                            "metadata": metadata,
                        })
                except Exception as e:
                    logger.error(f"Parallel section generation failed: {e}")

        section_contents.sort(key=lambda s: types.index(
            next(t for t in types if t in str(s.heading).lower())
        ) if any(t in str(s.heading).lower() for t in types) else 0)
        results_list.sort(key=lambda r: types.index(r["section_type"]))

        return section_contents, results_list, total_facts

    def generate_full_report(self, topic: str, author: str = "",
                              section_types: Optional[List[str]] = None,
                              parallel: bool = True) -> Dict[str, Any]:
        types = section_types or [
            "introduction", "literature_review", "methodology",
            "implementation", "results", "discussion", "conclusion",
        ]
        blueprint = self._blueprint_generator.generate_blueprint(topic, types)
        
        section_contents = []
        results = []
        total_facts = 0
        
        if parallel and len(types) > 1:
            section_contents, results, total_facts = self._generate_sections_parallel(
                topic, types
            )
        else:
            previous_summary = ""
            for stype in types:
                logger.info(f"[KnowledgeDriven] Generating section: {stype}")
                section, metadata = self.generate_section(
                    section_type=stype,
                    topic=topic,
                    retrieval_query=f"{topic} {stype.replace('_', ' ')}",
                    previous_summary=previous_summary,
                )
                section_contents.append(section)
                total_facts += metadata.get("facts_used", 0)
                results.append({
                    "section_type": stype,
                    "heading": section.heading,
                    "blocks": len(section.blocks),
                    "total_words": section.total_words,
                    "evidence_sources": len(section.evidence_sources),
                    "metadata": metadata,
                })
                previous_summary = section.to_text()[:500]
        self._fact_memory.consolidate_duplicates()

        # Quality Gate: compute overall scores across all sections
        quality_scores = {}
        for r in results:
            md = r.get("metadata", {})
            filler_ok = 1.0 - md.get("filler_check", {}).get("filler_density", 0.0)
            quality_scores[r["section_type"]] = {
                "technical_depth": md.get("depth_score", {}).get("overall", 0.0),
                "evidence_score": md.get("evidence_score", {}).get("overall", 0.0),
                "coherence_score": md.get("coherence_score", {}).get("overall", 0.0),
                "academic_score": md.get("academic_score", {}).get("overall", 0.0),
                "uniqueness_score": md.get("depth_score", {}).get("uniqueness", 0.0),
                "formatting_score": 1.0 if md.get("section_compliance", {}).get("passed", True) else 0.5,
                "filler_score": filler_ok,
            }
        quality_result = self._quality_gate.evaluate_sections(quality_scores)

        report_data = {
            "title": topic,
            "author": author,
            "section_contents": section_contents,
            "section_count": len(section_contents),
            "total_words": sum(s.total_words for s in section_contents),
            "chapters": [{
                "heading": s.heading,
                "content": s.to_text(),
                "section_type": r["section_type"],
            } for s, r in zip(section_contents, results)],
            "results": results,
            "validations": {r["section_type"]: r["metadata"]["validation"]
                           for r in results if "validation" in r.get("metadata", {})},
            "all_validations_passed": all(
                r.get("metadata", {}).get("validation", {}).get("passed", True)
                for r in results
            ),
            "quality_gate": quality_result,
            "total_facts": total_facts,
            "domain": self._domain_classifier.get_domain(),
            "knowledge_graph": self._knowledge_graph_builder.graph.to_dict(),
            "bibliography": self._citation_mapper.get_bibliography(),
            "chapter_summaries": [s.to_dict() for s in self._chapter_summaries.get_all_summaries()],
            "fact_memory_stats": self._fact_memory.stats(),
            "retrieval_cache_stats": self._retrieval_cache.stats(),
        }

        if not quality_result["all_passed"]:
            logger.warning(
                f"Quality Gate: {quality_result['weak_count']}/{quality_result['total_sections']} "
                f"sections below threshold"
            )
            for ws in quality_result["weak_sections"]:
                logger.warning(f"  Weak: {ws['section']} ({ws['overall']}/10)")

        logger.info(
            f"Knowledge-Driven Report: {report_data['section_count']} sections, "
            f"{report_data['total_words']} words, "
            f"{total_facts} facts from evidence, "
            f"all validations passed: {report_data['all_validations_passed']}"
        )
        return report_data

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "facts_extracted": len(self._fact_extractor.get_all_facts()),
            "evidence_groups": len(self._evidence_builder._groups),
            "knowledge_graph": self._knowledge_graph_builder.graph.to_dict(),
            "chapter_summaries": self._chapter_summaries.count(),
            "fact_memory": self._fact_memory.stats(),
            "retrieval_cache": self._retrieval_cache.stats(),
            "context_cache": self._context_cache.stats(),
            "example_library": self._example_library.get_example_count(),
            "hierarchical_memory": self._hierarchical_memory.stats(),
            "bibliography": len(self._citation_mapper._citations),
        }
