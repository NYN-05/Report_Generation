import sys
import time
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Set

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import get_logger
from src.ingestion.pipeline import IngestionPipeline
from src.facts.extractor import FactExtractor
from src.facts.validator import FactValidator
from src.facts.store import FactStore, FactStoreConfig
from src.facts.models import SourceReference
from src.generator.fact_driven_generator import SynthesisGenerator
from src.generator.report_architect import ReportArchitect
from src.analysis.knowledge_model import KnowledgeAnalyzer
from src.analysis.coverage_auditor import KnowledgeCoverageAuditor
from src.validation.hallucination_detector import HallucinationDetector
from src.quality.unified_score import compute_pre_generation_score, compute_post_generation_score
from src.providers.factory import get_default_provider
from src.evidence.external_acquisition import ExternalAcquisitionPipeline
from src.collection.knowledge_collector import KnowledgeCollector

logger = get_logger("main")


def run(topic: str, knowledge_dir: str = "knowledge", output_path: str = "output/output.docx",
        web_search: bool = False, tavily: bool = False, min_coverage: float = 0.3,
        collect: bool = False):
    out_path = Path(output_path)
    if out_path.suffix.lower() == ".pdf":
        docx_path = str(out_path.with_suffix(".docx"))
        pdf_path_user = output_path
    else:
        docx_path = str(out_path.with_suffix(".docx"))
        pdf_path_user = str(out_path.with_suffix(".pdf"))

    print(f"\n{'='*60}")
    print(f"  EVIDENCE-FIRST REPORT: {topic}")
    print(f"{'='*60}\n")
    if collect:
        print(f"  Collecting knowledge from free web sources...")
        collector = KnowledgeCollector(knowledge_dir)
        saved = collector.collect(topic)
        if saved:
            print(f"  [OK] {saved} document(s) saved to '{knowledge_dir}'")
        else:
            print(f"  [INFO] No new documents collected")

    t0 = time.time()

    provider = get_default_provider()
    if provider:
        print(f"  [OK] LLM Provider: {provider.__class__.__name__} ({provider.model})")
    else:
        print(f"  [WARN] No LLM provider - fact-only output (no generation)")

    fact_store = FactStore(FactStoreConfig(deduplicate_on_insert=True))
    fact_extractor = FactExtractor()
    fact_validator = FactValidator()

    print(f"  [1/8] Ingesting documents from '{knowledge_dir}'...")
    ingest = IngestionPipeline()
    ingest.ingest_directory(knowledge_dir)
    chunks = ingest.get_chunks()
    if not chunks:
        print(f"  [FAIL] No documents found in '{knowledge_dir}'")
        print(f"\n{'='*60}")
        print(f"  RESULT: Insufficient evidence available.")
        print(f"  No documents to extract facts from. Add documents to '{knowledge_dir}'.")
        print(f"{'='*60}")
        return False
    print(f"  [OK] {len(chunks)} chunks ingested")

    print(f"  [2/8] Extracting facts from evidence...")
    total_facts = 0
    for chunk in chunks:
        text = chunk.get("text", chunk.get("content", ""))
        if not text:
            continue
        meta = chunk.get("metadata", {})
        source = SourceReference(
            resource_id=meta.get("resource_id", "doc"),
            file_path=meta.get("source", "unknown"),
            file_name=meta.get("file_name", meta.get("source", "unknown").split("/")[-1].split("\\")[-1]),
            page_number=meta.get("page_number"),
            chunk_id=meta.get("chunk_id"),
        )
        extraction = fact_extractor.extract(text, source, meta)
        validated = fact_validator.get_high_confidence_facts(extraction.facts)
        fact_store.add_facts(validated)
        total_facts += len(validated)
    print(f"  [OK] {total_facts} facts extracted ({fact_store.get_statistics()['total']} in store)")

    print(f"  [3/8] Understanding topic and planning report structure...")
    generator = SynthesisGenerator(fact_store, provider)
    analyzer = KnowledgeAnalyzer(fact_store, provider)
    knowledge_model = analyzer.analyze(topic)
    architect = ReportArchitect(fact_store, knowledge_model, provider)
    report_plan = architect.design(min_facts=3)
    sections = report_plan.sections
    active = report_plan.active_sections
    if not active:
        print(f"  [FAIL] No evidence-based sections meet minimum threshold")
        return False
    pruned = [s for s in sections if not s.meets_threshold]
    for s in pruned:
        print(f"    [PRUNED] {s.heading} ({s.pruning_reason})")
    print(f"  [OK] {len(active)}/{len(sections)} sections "
          f"(utilization: {report_plan.utilization_rate:.1%} of "
          f"{report_plan.total_facts_available} facts, {report_plan.report_type})")

    if web_search:
        backends = "DuckDuckGo"
        if tavily:
            backends += " + Tavily"
        print(f"  [3b] Checking evidence coverage (backends: {backends})...")
        acquisition = ExternalAcquisitionPipeline(
            fact_store, provider,
            coverage_threshold=min_coverage,
            min_voting_sources=2,
        )
        needs_acq, low_sections = acquisition.check_coverage(sections)
        if needs_acq:
            print(f"  [INFO] Coverage below threshold for: {', '.join(low_sections)}")
            print(f"  [INFO] Acquiring external evidence...")
            added = acquisition.acquire(topic, sections, max_results_per_source=3, use_tavily=tavily)
            if added:
                print(f"  [OK] {added} verified external facts added to store")
                print(f"  [INFO] Rebuilding knowledge model...")
                knowledge_model = analyzer.analyze(topic, max_facts_per_cluster=60)
                architect = ReportArchitect(fact_store, knowledge_model, provider)
                report_plan = architect.design(min_facts=3)
                sections = report_plan.sections
                active = report_plan.active_sections
                print(f"  [OK] {len(active)} sections now defined "
                      f"(utilization: {report_plan.utilization_rate:.1%})")
            else:
                print(f"  [INFO] No new verified external facts")
        else:
            print(f"  [OK] Coverage sufficient ({min_coverage:.0%}) — no external acquisition needed")

    print(f"  [4/9] Running coverage audit...")
    auditor = KnowledgeCoverageAuditor(fact_store, provider)

    section_contents = []
    section_scores = []

    print(f"  [5/9] Synthesizing report from knowledge clusters...")
    for section in active:
        pre_score = compute_pre_generation_score(section.facts)
        print(f"    Synthesizing {section.heading} ({len(section.facts)} facts, score={pre_score:.0%})...")
        gen_section = generator.generate_section(
            section.heading, section.heading, section.facts, topic,
            sub_themes=section.sub_themes,
            key_findings=section.key_findings,
        )
        section_contents.append(gen_section)
        post_score = compute_post_generation_score(gen_section.to_text(), section.facts)
        section_scores.append({"heading": section.heading, **post_score})

    generated_fact_lists = [s.facts for s in active]

    coverage_audit = auditor.audit(
        knowledge_model, generated_fact_lists,
        threshold=0.60
    )
    utilization_warn = ""
    if coverage_audit.needs_expansion:
        utilization_warn = (
            f"\n  [WARN] Fact utilization {coverage_audit.utilization_rate:.1%} "
            f"below 60% target "
            f"({coverage_audit.generated_facts}/{coverage_audit.total_facts})"
        )
        for rec in coverage_audit.expansion_recommendations[:3]:
            utilization_warn += f"\n    * {rec}"

    print(f"  [6/9] Validating against hallucinations...")
    detector = HallucinationDetector(fact_store)
    sections_text = {sc.heading: sc.to_text() for sc in section_contents}
    result = detector.check_report(fact_store, sections_text)
    if result["hallucination_free"]:
        print(f"  [OK] No hallucination issues detected")
    else:
        print(f"  [WARN] {result['total_issues']} issues detected")
        filtered = detector.filter_sections(section_contents, result["issues"])
        if filtered:
            print(f"  [FIX] Replaced {filtered} hallucinated paragraph(s) with source-required blocks")

    print(f"  [7/9] Computing evidence quality & utilization...")
    unused_summary = coverage_audit.unused_by_category
    for sc in section_contents:
        for si in section_scores:
            if si["heading"] == sc.heading:
                print(f"    {sc.heading}: unified={si['unified_score']:.0%} "
                      f"fidelity={si['evidence_fidelity']:.0%} "
                      f"risk={si['hallucination_risk']:.0%}")
                break
    if unused_summary:
        cats = " | ".join(f"{k}={v}" for k, v in unused_summary.items() if v > 0)
        print(f"    Unused fact profile: {cats}")
    if utilization_warn:
        print(utilization_warn)

    print(f"  [8/9] Assembling DOCX...")
    try:
        from src.document.docx_v2_generator import DOCXV2Generator
        docx_gen = DOCXV2Generator()
        subtitle = f"A {report_plan.report_type.replace('_', ' ').title()} Report"
        kf_section = generator.generate_key_findings_section(
            knowledge_model.clusters
        )
        utilization_summary = coverage_audit.to_dict()
        output = docx_gen.generate(
            title=topic,
            author="",
            subtitle=subtitle,
            metadata={
                "domain": report_plan.domain,
                "report_type": report_plan.report_type,
                "audience": report_plan.audience,
            },
            sections=section_contents,
            output_path=docx_path,
            executive_summary=report_plan.executive_summary,
            key_findings_section=kf_section,
            utilization_summary=utilization_summary,
        )
        print(f"  [OK] DOCX saved: {output}")
    except Exception as e:
        print(f"  [FAIL] DOCX generation: {e}")
        return False

    print(f"  [9/9] Converting to PDF...")
    try:
        from docx2pdf import convert
        convert(output, pdf_path_user)
        print(f"  [OK] PDF saved: {pdf_path_user}")
        pdf_path_out = pdf_path_user
    except Exception as e:
        logger.warning(f"PDF conversion failed: {e}")
        print(f"  [INFO] PDF conversion skipped ({e})")
        pdf_path_out = None

    elapsed = time.time() - t0
    total_words = sum(sc.total_words for sc in section_contents)
    avg_unified = sum(s["unified_score"] for s in section_scores) / max(len(section_scores), 1)
    avg_fidelity = sum(s["evidence_fidelity"] for s in section_scores) / max(len(section_scores), 1)

    print(f"\n{'='*60}")
    print(f"  REPORT COMPLETE in {elapsed:.1f}s")
    print(f"  Sections: {len(section_contents)} | Words: {total_words}")
    print(f"  Fact Utilization: {coverage_audit.utilization_rate:.1%} "
          f"({coverage_audit.generated_facts}/{coverage_audit.total_facts})")
    print(f"  Source Coverage: {coverage_audit.source_coverage_rate:.0%} "
          f"({coverage_audit.covered_sources}/{coverage_audit.total_sources})")
    print(f"  Unified Score: {avg_unified:.0%} | Fidelity: {avg_fidelity:.0%}")
    print(f"  Hallucination Issues: {result['total_issues']}")
    print(f"  DOCX: {output}")
    if pdf_path_out:
        print(f"  PDF:  {pdf_path_out}")
    print(f"{'='*60}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Evidence-First Report Generator")
    parser.add_argument("topic", nargs="?", help="Report topic")
    parser.add_argument("--knowledge-dir", default="knowledge", help="Directory with reference documents")
    parser.add_argument("--output", default="output/output.docx", help="Output DOCX path")
    parser.add_argument("--min-coverage", type=float, default=0.3, help="Minimum coverage threshold (0-1)")
    parser.add_argument("--web-search", action="store_true", help="Enable web search (DuckDuckGo, always free)")
    parser.add_argument("--tavily", action="store_true", help="Use Tavily API (costs credits) alongside DuckDuckGo")
    parser.add_argument("--collect", action="store_true", help="Download topic knowledge from free web sources before ingestion")
    args = parser.parse_args()

    if not args.topic:
        parser.print_help()
        print("\nExample: python -m src.main \"Climate Change Impact\" --knowledge-dir knowledge")
        return

    run(topic=args.topic, knowledge_dir=args.knowledge_dir,
        output_path=args.output, min_coverage=args.min_coverage,
        web_search=args.web_search, tavily=args.tavily,
        collect=args.collect)


if __name__ == "__main__":
    main()
