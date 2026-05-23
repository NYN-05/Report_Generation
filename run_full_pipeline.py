"""
Full Pipeline Demo — uses every feature of the report generation system.

Usage:
    set TAVILY_API_KEY=tvly-...  (optional, enables web search)
    python run_full_pipeline.py "Your Topic"
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.logger import get_logger
from src.retrieval import ContextAssembler, HybridRetriever, WebSearchRetriever, MultiSourceRetriever
from src.generator.knowledge_driven_generator import KnowledgeDrivenReportGenerator
from src.pipeline.coordinated import CoordinatedPipeline
from src.document.styles import StyleManager, DocumentStyleValidator
from src.content import (
    GenericContentDetector, TechnicalDepthEnhancer,
    ParagraphQualityEngine, SectionSpecificWriter,
    ContentTypeClassifier, QualityGate,
)
from src.quality import EvidenceCoverageScore, TechnicalDepthScore, EvidenceScore, CoherenceScore, AcademicScore

logger = get_logger("demo")


def demo(topic: str, output_path: str = "output/full_report.docx", enable_web: bool = True):
    print("=" * 70)
    print(f"  FULL PIPELINE DEMO — {topic}")
    print("=" * 70)

    # ── 1. Provider (Ollama) ──
    print("\n[1/8] Initializing LLM provider...")
    from src.providers.ollama import OllamaProvider
    provider = OllamaProvider(model="llama3.2:3b")
    if not provider.is_available():
        print("  ⚠ Ollama not available — some features will be limited")
    else:
        print(f"  ✓ Ollama ready ({provider.model})")

    # ── 2. Local knowledge ingestion ──
    print("\n[2/8] Loading local knowledge...")
    local_retriever = None
    from src.ingestion.pipeline import IngestionPipeline
    knowledge_dir = os.path.join(os.path.dirname(__file__), "knowledge")
    if os.path.isdir(knowledge_dir):
        ingest = IngestionPipeline()
        ingest.ingest_directory(knowledge_dir)
        chunks = ingest.get_chunks()
        if chunks:
            local_retriever = HybridRetriever(
                vector_store=ingest.store if ingest.store.is_available() else None
            )
            local_retriever.index_chunks(chunks)
            print(f"  ✓ {len(chunks)} chunks indexed from knowledge/")
        else:
            print("  ⚠ No chunks found in knowledge/")
    else:
        print("  ⚠ No knowledge/ directory found")

    # ── 3. Web search ──
    web_retriever = None
    if enable_web:
        print("\n[3/8] Setting up web search...")
        web_retriever = WebSearchRetriever()
        if web_retriever.is_ready():
            print(f"  ✓ Tavily ready ({web_retriever.get_rate_stats()['max']} RPM)")
        else:
            print("  ⚠ Web search skipped (no TAVILY_API_KEY)")

    # ── 4. Multi-source retriever ──
    print("\n[4/8] Building multi-source retriever...")
    if local_retriever and web_retriever and web_retriever.is_ready():
        retriever = MultiSourceRetriever(local_retriever, web_retriever)
        print("  ✓ MultiSource: local + web")
    elif local_retriever:
        retriever = local_retriever
        print("  ✓ Local-only retrieval")
    elif web_retriever and web_retriever.is_ready():
        retriever = web_retriever
        print("  ✓ Web-only retrieval")
    else:
        retriever = None
        print("  ⚠ No retriever available")

    context_assembler = ContextAssembler(retriever=retriever) if retriever else None
    if context_assembler:
        if local_retriever:
            context_assembler.index_knowledge(ingest.get_chunks())

    # ── 5. Knowledge-driven generator ──
    print("\n[5/8] Creating knowledge-driven generator...")
    gen = KnowledgeDrivenReportGenerator(
        provider=provider if provider.is_available() else None,
        context_assembler=context_assembler,
    )
    print("  ✓ Generator ready (10 layers: research, knowledge, domain, citation, refinement,"
          "\n                long-context, blueprint, quality, few-shot, production)")

    # ── 6. Style manager ──
    print("\n[6/8] Configuring document styles...")
    sm = StyleManager.get_instance()
    s = sm.get_styles()
    print(f"  ✓ Page: {s.page.top_margin}\" margins")
    print(f"  ✓ Body: {s.content.font.name} {s.content.font.size}pt, {s.content.line_spacing}x spacing")
    print(f"  ✓ Heading 1: {s.get_heading(1).font.name} {s.get_heading(1).font.size}pt")
    print(f"  ✓ Heading 2: {s.get_heading(2).font.name} {s.get_heading(2).font.size}pt")

    # ── 7. Pipeline execution ──
    print("\n[7/8] Running pipeline...")
    print(f"\n  Phases: plan → research → knowledge → generate → review → validate")
    print(f"          → refine → assemble_doc → quality_gate → export")
    print(f"  Output: {output_path}")
    print()

    phases = [
        "plan", "research", "knowledge", "generate",
        "review", "validate", "refine", "assemble_doc",
        "quality_gate", "export",
    ]

    pipe = CoordinatedPipeline()
    start = time.time()
    result = pipe.execute(
        {"topic": topic, "output_path": output_path, "formats": ["docx", "pdf"]},
        phases=phases,
        callback=lambda phase, status: print(f"    [{status}] {phase}"),
        components={
            "report_generator": None,
            "knowledge_generator": gen,
            "memory_hub": None,
            "context_assembler": context_assembler,
        },
    )
    elapsed = time.time() - start

    # ── 8. Results ──
    print(f"\n[8/8] Results")
    print("=" * 70)
    print(f"  Status:     {'✓ PASSED' if result.success else '✗ FAILED'}")
    print(f"  Time:       {elapsed:.1f}s")
    print(f"  Output:     {result.output_path}")

    report = result.data.get("report", {}) if result.data else {}
    quality = report.get("quality_gate", {}) if report else {}
    pdf_path = str(output_path).replace(".docx", ".pdf")

    if report:
        print(f"  Sections:   {report.get('section_count', '?')}")
        print(f"  Words:      {report.get('total_words', '?')}")
        print(f"  Facts:      {report.get('total_facts', '?')}")

        if quality:
            passed = quality.get("all_passed", False)
            weak = quality.get("weak_sections", [])
            print(f"  Quality:    {'✓ ALL PASSED' if passed else f'✗ {len(weak)} weak section(s)'}")
            for ws in weak:
                print(f"               - {ws['section']}: {ws['overall']}/10")

        if os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path) / 1024
            print(f"  PDF:        ✓ {pdf_path} ({pdf_size:.0f} KB)")

    print("=" * 70)
    print()

    # ── Feature verification ──
    print("\nFeature checklist:")
    checks = [
        ("Knowledge-driven generation (10 layers)", bool(report)),
        ("Fact extraction from evidence", report.get("total_facts", 0) > 0 if report else False),
        ("Evidence coverage scoring", report.get("results", [{}])[0].get("metadata", {}).get("evidence_coverage") is not None if report.get("results") else False),
        ("Generic content detection", report.get("results", [{}])[0].get("metadata", {}).get("filler_check") is not None if report.get("results") else False),
        ("Technical depth enforcement", report.get("results", [{}])[0].get("metadata", {}).get("depth_check") is not None if report.get("results") else False),
        ("Paragraph quality engine", report.get("results", [{}])[0].get("metadata", {}).get("paragraph_quality") is not None if report.get("results") else False),
        ("Section-specific writing (forbidden topics)", report.get("results", [{}])[0].get("metadata", {}).get("section_compliance") is not None if report.get("results") else False),
        ("Content type classification", report.get("results", [{}])[0].get("metadata", {}).get("classified_blocks") is not None if report.get("results") else False),
        ("Quality gate (all sections scored)", bool(quality)),
        ("Centralized StyleManager formatting", True),
        ("Auto PDF conversion", os.path.exists(pdf_path)),
        ("Web search integration", web_retriever is not None and web_retriever.is_ready()),
    ]
    for name, ok in checks:
        print(f"    {'✓' if ok else ' '}  {name}")

    return result.success


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "Machine Learning for Network Intrusion Detection"
    output = sys.argv[2] if len(sys.argv) > 2 else "output/full_report.docx"
    success = demo(topic, output)
    sys.exit(0 if success else 1)
