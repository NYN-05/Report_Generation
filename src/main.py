import sys
import time
import argparse
from pathlib import Path
from typing import Optional, List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import get_logger
from src.ingestion.pipeline import IngestionPipeline
from src.facts.extractor import FactExtractor
from src.facts.validator import FactValidator
from src.facts.store import FactStore, FactStoreConfig
from src.facts.models import SourceReference
from src.generator.fact_driven_generator import FactDrivenGenerator, SectionConfidence, EVIDENCE_SECTION_MAP
from src.validation.hallucination_detector import HallucinationDetector
from src.quality.fidelity import evidence_fidelity, hallucination_risk
from src.providers.factory import get_default_provider
from src.evidence.external_acquisition import ExternalAcquisitionPipeline

logger = get_logger("main")


def run(topic: str, knowledge_dir: str = "knowledge", output_path: str = "output/output.docx",
        web_search: bool = False, min_coverage: float = 0.3):
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
    t0 = time.time()

    provider = get_default_provider()
    if provider:
        print(f"  [OK] LLM Provider: {provider.__class__.__name__} ({provider.model})")
    else:
        print(f"  [WARN] No LLM provider - fact-only output (no generation)")

    fact_store = FactStore(FactStoreConfig(deduplicate_on_insert=True))
    fact_extractor = FactExtractor()
    fact_validator = FactValidator()

    print(f"  [1/7] Ingesting documents from '{knowledge_dir}'...")
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

    print(f"  [2/7] Extracting facts from evidence...")
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

    print(f"  [3/7] Building evidence blueprint...")
    generator = FactDrivenGenerator(fact_store, provider)
    blueprint = generator.build_blueprint(topic)
    if not blueprint:
        print(f"  [FAIL] No evidence-based sections could be defined")
        print(f"\n  The system found no facts matching any report section requirements.")
        print(f"  Upload documents with: objectives, datasets, algorithms, metrics, or results.")
        return False
    print(f"  [OK] {len(blueprint)} sections defined from evidence")

    if web_search:
        print(f"  [3b] Checking evidence coverage...")
        acquisition = ExternalAcquisitionPipeline(
            fact_store, provider,
            coverage_threshold=min_coverage,
            min_voting_sources=2,
        )
        needs_acq, low_sections = acquisition.check_coverage(blueprint)
        if needs_acq:
            print(f"  [INFO] Coverage below threshold for: {', '.join(low_sections)}")
            print(f"  [INFO] Acquiring external evidence...")
            added = acquisition.acquire(topic, blueprint, max_results_per_source=3)
            if added:
                print(f"  [OK] {added} verified external facts added to store")
                print(f"  [INFO] Rebuilding blueprint with enriched evidence...")
                blueprint = generator.build_blueprint(topic)
                print(f"  [OK] {len(blueprint)} sections now defined ({fact_store.get_statistics()['total']} total facts)")
            else:
                print(f"  [INFO] No new verified facts from external sources")
        else:
            print(f"  [OK] Coverage sufficient ({min_coverage:.0%}) — no external acquisition needed")

    print(f"  [4/8] Generating fact-driven report...")
    section_contents = []
    section_confidences = []
    for section_info in blueprint:
        stype = section_info["section_type"]
        facts = section_info["facts"]
        heading = section_info["heading"]
        print(f"    Generating {heading} ({len(facts)} facts, mode={generator._compute_mode(facts)})...")
        section = generator.generate_section(stype, heading, facts, topic)
        section_contents.append(section)
        paras = [b for b in section.blocks if hasattr(b, 'text') and b.text]
        confidence = generator.compute_confidence(stype, facts, paras)
        section_confidences.append(confidence)

    print(f"  [5/8] Validating against hallucinations...")
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

    print(f"  [6/8] Computing evidence fidelity...")
    all_facts = fact_store.get_all_facts()
    for i, sc in enumerate(section_contents):
        text = sc.to_text()
        sec_facts = blueprint[i]["facts"]
        fid = evidence_fidelity(text, sec_facts)
        hal = hallucination_risk(text, sec_facts)
        conf = section_confidences[i]
        print(f"    {conf.heading}: fidelity={fid['fidelity']:.0%} "
              f"risk={hal['risk']:.0%} coverage={conf.coverage:.0%} "
              f"sources={conf.source_count} facts={conf.supporting_facts}")

    print(f"  [7/7] Assembling DOCX...")
    try:
        from src.document.docx_v2_generator import DOCXV2Generator
        docx_gen = DOCXV2Generator()
        output = docx_gen.generate(
            title=topic,
            author="",
            sections=section_contents,
            output_path=docx_path,
        )
        print(f"  [OK] DOCX saved: {output}")
    except Exception as e:
        print(f"  [FAIL] DOCX generation: {e}")
        return False

    print(f"  [8/8] Converting to PDF...")
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
    total_facts_used = sum(sc.supporting_facts for sc in section_confidences)
    avg_coverage = sum(sc.coverage for sc in section_confidences) / max(len(section_confidences), 1)
    avg_fidelity = sum(evidence_fidelity(sc.to_text(), blueprint[i]["facts"])["fidelity"]
                       for i, sc in enumerate(section_contents)) / max(len(section_contents), 1)

    print(f"\n{'='*60}")
    print(f"  REPORT COMPLETE in {elapsed:.1f}s")
    print(f"  Sections: {len(section_contents)} | Words: {total_words}")
    print(f"  Evidence Coverage: {avg_coverage:.0%} | Fidelity: {avg_fidelity:.0%}")
    print(f"  Facts Used: {total_facts_used} | Sources: {sum(sc.source_count for sc in section_confidences)}")
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
    parser.add_argument("--web-search", action="store_true", help="Enable web search (requires TAVILY_API_KEY)")
    args = parser.parse_args()

    if not args.topic:
        parser.print_help()
        print("\nExample: python -m src.main \"Climate Change Impact\" --knowledge-dir knowledge")
        return

    run(topic=args.topic, knowledge_dir=args.knowledge_dir,
        output_path=args.output, min_coverage=args.min_coverage,
        web_search=args.web_search)


if __name__ == "__main__":
    main()
