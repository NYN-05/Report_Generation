"""
Main Entry Point
=================
Unified entry point for the report generation platform.
"""

import os
import sys
import signal
import argparse
from pathlib import Path
from typing import Optional, List, Dict

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import config
from src.core.logger import get_logger
from src.agents import OrchestratorAgent
from src.pipeline import ScratchPipeline, PDFExportPipeline
from src.memory import ContextManager, ReportHistory


logger = get_logger("main")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_shutdown_requested = False


def _signal_handler(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT."""
    global _shutdown_requested
    if _shutdown_requested:
        logger.warning("Forced exit")
        sys.exit(1)
    _shutdown_requested = True
    logger.warning(f"Received signal {signum}, shutting down gracefully...")
    print("\n[INFO] Shutdown requested. Finishing current operation...")


def _setup_signal_handlers():
    """Install signal handlers for graceful shutdown."""
    signal.signal(signal.SIGTERM, _signal_handler)
    try:
        signal.signal(signal.SIGINT, _signal_handler)
    except (ValueError, AttributeError):
        pass  # SIGINT not available on all platforms


def health_check() -> Dict:
    """Perform system health check and return status dict."""
    status = {"status": "ok", "checks": {}}
    try:
        deps = config.check_dependencies()
        status["checks"]["dependencies"] = {
            k: "available" if v else "missing" for k, v in deps.items()
        }
        critical = ["python-docx"]
        missing_critical = [d for d in critical if not deps.get(d)]
        if missing_critical:
            status["status"] = "degraded"
            status["checks"]["critical_missing"] = missing_critical

        import shutil
        output_disk = shutil.disk_usage("output") if os.path.isdir("output") else None
        if output_disk:
            free_gb = output_disk.free / (1024 ** 3)
            status["checks"]["disk"] = {
                "free_gb": round(free_gb, 1),
                "healthy": free_gb > 0.5,
            }
            if free_gb < 0.5:
                status["status"] = "degraded"

        log_dir = Path("logs")
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log"))
            log_age_days = {}
            for f in log_files:
                try:
                    mtime = f.stat().st_mtime
                    import time
                    age = (time.time() - mtime) / 86400
                    log_age_days[f.name] = round(age, 1)
                except OSError:
                    pass
            status["checks"]["logs"] = {
                "count": len(log_files),
                "oldest_days": max(log_age_days.values()) if log_age_days else 0,
            }

        status["checks"]["project"] = {
            "root": str(_PROJECT_ROOT),
            "requirements_exists": Path("requirements.txt").exists(),
            "knowledge_files": len(list(_PROJECT_ROOT.glob("knowledge/*.*"))),
        }
    except Exception as e:
        status["status"] = "error"
        status["error"] = str(e)
    return status


def _resolve_safe_path(user_path: str, allowed_parent: Optional[Path] = None) -> Optional[str]:
    """Resolve and validate a file path, preventing directory traversal.
    
    Ensures the resolved path stays within the allowed parent directory.
    Returns None if the path is invalid or traverses outside allowed bounds.
    """
    if not user_path:
        return None
    try:
        resolved = Path(user_path).resolve()
        parent = allowed_parent or _PROJECT_ROOT
        parent = Path(parent).resolve()
        if parent not in resolved.parents and resolved != parent:
            logger.warning(f"Path traversal blocked: {user_path} -> {resolved} (outside {parent})")
            return None
        return str(resolved)
    except (ValueError, OSError, RuntimeError) as e:
        logger.warning(f"Path resolution failed for {user_path}: {e}")
        return None


def run_coordinated(topic: str, output_path: str = "output/output.docx",
                    formats: Optional[list] = None,
                    phases: Optional[list] = None,
                    use_provider: bool = True,
                    web_search: bool = False):
    """Run the CoordinatedPipeline with optional phase selection."""
    logger.info(f"Coordinated pipeline for: {topic}")
    from src.pipeline import CoordinatedPipeline
    from src.generator import ReportGenerator, EvidenceBasedSectionGenerator
    from src.generator.knowledge_driven_generator import KnowledgeDrivenReportGenerator
    from src.memory import MemoryHub
    from src.providers.factory import get_default_provider

    provider = get_default_provider() if use_provider else None
    if provider:
        logger.info(f"Using provider: {provider.__class__.__name__} ({provider.model})")
    else:
        logger.warning("No LLM provider available — evidence-based mode still active")

    context_assembler = None
    local_chunks = []
    local_retriever = None
    try:
        from src.retrieval.context import ContextAssembler
        from src.retrieval.base import HybridRetriever
        from src.retrieval.web import WebSearchRetriever, MultiSourceRetriever
        from src.ingestion.pipeline import IngestionPipeline
        import os
        # Resolve knowledge_dir relative to project root with path traversal protection
        project_root = Path(__file__).resolve().parent.parent
        knowledge_dir = str(project_root / "knowledge")
        knowledge_dir = _resolve_safe_path(knowledge_dir)
        if knowledge_dir and os.path.isdir(knowledge_dir):
            ingest = IngestionPipeline()
            ingest.ingest_directory(knowledge_dir)
            local_chunks = ingest.get_chunks()
            if local_chunks:
                local_retriever = HybridRetriever(
                    vector_store=ingest.store if ingest.store.is_available() else None
                )
                local_retriever.index_chunks(local_chunks)
        else:
            logger.warning("No knowledge directory found at 'knowledge/'")

        if web_search and not os.environ.get("TAVILY_API_KEY"):
            logger.warning(
                "--web-search set but TAVILY_API_KEY not found. "
                "Set TAVILY_API_KEY env var to enable."
            )

        if web_search:
            web_retriever = WebSearchRetriever()
            retriever = MultiSourceRetriever(local_retriever, web_retriever) if local_retriever else web_retriever
            logger.info("Web search enabled")
        else:
            retriever = local_retriever

        if retriever:
            context_assembler = ContextAssembler(retriever=retriever)
            if local_chunks:
                context_assembler.index_knowledge(local_chunks)
            logger.info(
                f"ContextAssembler ready "
                f"({'web + ' if web_search else ''}{len(local_chunks)} knowledge chunks)"
            )
    except Exception as e:
        logger.warning(f"Context assembler init skipped: {e}")

    knowledge_generator = KnowledgeDrivenReportGenerator(
        provider=provider,
        context_assembler=context_assembler,
    )

    report_generator = ReportGenerator(
        provider=provider,
        context_assembler=context_assembler,
    )

    pipe = CoordinatedPipeline()
    result = pipe.execute(
        {"topic": topic, "output_path": output_path, "formats": formats or ["docx"]},
        phases=phases,
        callback=lambda phase, status: print(f"  [{status}] {phase}"),
        components={
            "report_generator": report_generator,
            "knowledge_generator": knowledge_generator,
            "memory_hub": MemoryHub(),
            "context_assembler": context_assembler,
        },
    )
    if result.success:
        print(f"\n[OK] Pipeline complete in {result.execution_time:.2f}s")
        print(f"     Output: {result.output_path}")
        phases_done = result.data.get("phases_completed", [])
        print(f"     Phases: {', '.join(phases_done)}")
        stats = knowledge_generator.get_statistics()
        print(f"     Facts: {stats['facts_extracted']} | "
              f"Graph: {stats['knowledge_graph']['node_count']} concepts | "
              f"Examples: {stats['example_library']}")
    else:
        print(f"\n[ERROR] {result.error}")
    return result.success


def run_with_topic(topic: str, rules_path: Optional[str] = None,
                   use_llm: bool = False,
                   knowledge_dir: Optional[str] = None,
                   skip_review: bool = False):
    """Run report generation for a topic."""
    logger.info(f"Starting report generation for: {topic}")
    
    try:
        # Validate knowledge_dir path
        safe_knowledge_dir = None
        if knowledge_dir:
            safe_knowledge_dir = _resolve_safe_path(knowledge_dir)
            if safe_knowledge_dir is None:
                logger.error(f"Invalid knowledge_dir path (blocked traversal): {knowledge_dir}")
                print(f"\n[ERROR] Invalid knowledge directory path")
                return False
        
        # Step 1: Initialize orchestrator with LLM
        logger.info("Initializing orchestrator...")
        orchestrator = OrchestratorAgent()
        
        # Step 2: Generate content via orchestration
        logger.info("Generating content via AI...")
        result = orchestrator.execute({'task': topic})
        
        if not result.success:
            logger.error(f"Content generation failed: {result.error}")
            print(f"\n[ERROR] {result.error}")
            return False
        
        content = result.data['content']
        skills = result.data['skills_used']
        
        print(f"\n[OK] Content generated using skills: {skills}")
        print(f"     Title: {content.get('title', 'N/A')}")
        
        # Step 3: Store in context
        context = ContextManager()
        ctx = context.get_context(user_id="default")
        ctx.update(task=topic, skills_used=skills)
        
        # Step 4: Generate document
        logger.info("Generating Word document...")
        gen_pipeline = ScratchPipeline(
            rules_path=rules_path, use_llm=use_llm,
            knowledge_dir=safe_knowledge_dir,
            enable_review=not skip_review,
        )
        doc_result = gen_pipeline.execute(content)
        
        if not doc_result.success:
            logger.error(f"Document generation failed: {doc_result.error}")
            print(f"\n[ERROR] {doc_result.error}")
            return False
        
        print(f"\n[OK] Document created: {doc_result.output_path}")
        
        # Step 5: Convert to PDF if available
        deps = config.check_dependencies()
        if deps.get('docx2pdf') or deps.get('win32com'):
            logger.info("Converting to PDF...")
            pdf_pipeline = PDFExportPipeline()
            pdf_result = pdf_pipeline.execute(doc_result.output_path)
            
            if pdf_result.success:
                print(f"[OK] PDF created: {pdf_result.output_path}")
            else:
                print(f"[INFO] PDF conversion skipped: {pdf_result.error}")
        
        # Step 6: Log to history
        history = ReportHistory()
        history.add(
            task=topic,
            title=content.get('title', ''),
            skills_used=skills,
            success=True
        )
        
        print("\n" + "=" * 60)
        print("  COMPLETE - Report Generated Successfully!")
        print("=" * 60)
        return True
        
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n[ERROR] {e}")
        return False


def show_status():
    """Show system status."""
    print("\n" + "=" * 60)
    print("  SYSTEM STATUS")
    print("=" * 60)
    
    # Configuration
    deps = config.check_dependencies()
    print("\n[Configuration]")
    print(f"   python-docx: {'OK' if deps.get('python-docx') else 'MISSING'}")
    print(f"   docx2pdf: {'OK' if deps.get('docx2pdf') else 'MISSING'}")
    print(f"   Ollama: {'OK' if deps.get('ollama') else 'MISSING'}")
    
    # Skills
    from src.skills import SkillRegistry
    registry = SkillRegistry()
    count = registry.initialize()
    print(f"\n[Skills]")
    print(f"   Available: {count}")
    
    # Available skills
    if count > 0:
        skills = registry.list_skills()[:5]
        for s in skills:
            print(f"   - {s['name']}")
        if count > 5:
            print(f"   ... and {count - 5} more")
    
    print("\n" + "=" * 60)


def run_evidence_centric(topic: str, output_path: str = "output/output.docx",
                         formats: Optional[list] = None,
                         knowledge_dir: Optional[str] = None,
                         web_search: bool = False):
    """Run the evidence-centric pipeline using EvidenceOrchestrator + CoordinatedPipeline."""
    logger.info(f"Evidence-centric pipeline for: {topic}")
    from src.pipeline import CoordinatedPipeline
    from src.evidence import EvidenceOrchestrator
    from src.generator.knowledge_driven_generator import KnowledgeDrivenReportGenerator
    from src.memory import MemoryHub
    from src.providers.factory import get_default_provider

    provider = get_default_provider() if not web_search else None
    orchestrator = EvidenceOrchestrator()

    context_assembler = None
    local_chunks = []
    try:
        from src.retrieval.context import ContextAssembler
        from src.retrieval.base import HybridRetriever
        from src.ingestion.pipeline import IngestionPipeline
        import os
        project_root = Path(__file__).resolve().parent.parent
        kd = knowledge_dir or str(project_root / "knowledge")
        kd = _resolve_safe_path(kd)
        if kd and os.path.isdir(kd):
            ingest = IngestionPipeline()
            ingest.ingest_directory(kd)
            local_chunks = ingest.get_chunks()
            if local_chunks:
                retriever = HybridRetriever(
                    vector_store=ingest.store if ingest.store.is_available() else None
                )
                retriever.index_chunks(local_chunks)
                context_assembler = ContextAssembler(retriever=retriever)
                context_assembler.index_knowledge(local_chunks)
    except Exception as e:
        logger.warning(f"Context assembler init skipped: {e}")

    knowledge_generator = KnowledgeDrivenReportGenerator(
        provider=provider,
        context_assembler=context_assembler,
    )

    evidence_phases = [
        "resource_intel", "fact_extraction", "evidence_graph",
        "evidence_blueprint", "coverage_analysis", "generation_constraints",
        "evidence_generation", "hallucination_check", "traceability",
        "quality_gate", "assemble_doc", "export",
    ]

    pipe = CoordinatedPipeline()
    result = pipe.execute(
        {"topic": topic, "output_path": output_path, "formats": formats or ["docx"]},
        phases=evidence_phases,
        callback=lambda phase, status: print(f"  [{status}] {phase}"),
        components={
            "evidence_orchestrator": orchestrator,
            "fact_store": orchestrator.fact_store,
            "coverage_engine": orchestrator.coverage_engine,
            "knowledge_generator": knowledge_generator,
            "memory_hub": MemoryHub(),
            "context_assembler": context_assembler,
        },
    )

    if result.success:
        print(f"\n[OK] Evidence-centric pipeline complete in {result.execution_time:.2f}s")
        print(f"     Output: {result.output_path}")
        phases_done = result.data.get("phases_completed", [])
        print(f"     Phases: {', '.join(phases_done)}")
        stats = orchestrator.get_statistics()
        print(f"     Facts: {stats['fact_store'].get('total', 0)} | "
              f"Graph: {stats['knowledge_graph'].get('node_count', 0)} nodes")
        try:
            dashboard = orchestrator.get_dashboard_data()
            cov = dashboard.get("coverage", {})
            if cov and cov != {"status": "no_report"}:
                print(f"     Coverage: {cov.get('overall_coverage', 'N/A')} | "
                      f"Trust: {cov.get('overall_confidence', 'N/A')}")
        except Exception:
            pass
    else:
        print(f"\n[ERROR] {result.error}")
    return result.success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AI-Powered Report Generation Platform"
    )
    
    parser.add_argument(
        'topic',
        nargs='?',
        help='Topic for report generation'
    )
    
    parser.add_argument(
        '--status', '-s',
        action='store_true',
        help='Show system status'
    )
    
    parser.add_argument(
        '--list-skills',
        action='store_true',
        help='List available skills'
    )
    
    parser.add_argument(
        '--explain',
        metavar='TASK',
        help='Explain skill selection for a task'
    )
    
    parser.add_argument(
        '--rules',
        metavar='FILE',
        help='Path to custom rules JSON/MD file'
    )

    parser.add_argument(
        '--use-llm',
        action='store_true',
        help='Use LLM for dynamic structure planning (requires Ollama)'
    )

    parser.add_argument(
        '--knowledge-dir',
        metavar='DIR',
        help='Directory with reference documents (PDFs/txt) for RAG'
    )

    parser.add_argument(
        '--skip-review',
        action='store_true',
        help='Skip the multi-pass review pipeline'
    )

    # Coordinated pipeline flags
    parser.add_argument(
        '--coordinated',
        action='store_true',
        help='Use the CoordinatedPipeline (wires all agents & generators)'
    )

    parser.add_argument(
        '--evidence-centric',
        action='store_true',
        help='Use evidence-centric pipeline: resource_intel -> fact_extraction -> '
             'evidence_graph -> blueprint -> coverage -> constrained generation'
    )

    parser.add_argument(
        '--phases',
        metavar='PHASES',
        help='Comma-separated phases for CoordinatedPipeline: '
             'plan,research,generate,review,validate,assemble_doc,export'
    )

    parser.add_argument(
        '--output',
        metavar='FILE',
        default='output/output.docx',
        help='Output file path (default: output/output.docx)'
    )

    parser.add_argument(
        '--format',
        metavar='FMT',
        default='docx',
        help='Export format(s): docx, pdf (default: docx)'
    )

    parser.add_argument(
        '--web-search',
        action='store_true',
        help='Enable internet search (requires TAVILY_API_KEY env var)'
    )

    args = parser.parse_args()
    
    _setup_signal_handlers()
    
    if args.status:
        show_status()
        return
    
    if args.list_skills:
        from src.skills import SkillRegistry
        registry = SkillRegistry()
        registry.initialize()
        skills = registry.list_skills()
        print(f"\nAvailable Skills ({len(skills)}):")
        for s in skills:
            print(f"  - {s['name']}: {s['description'][:60]}...")
        return
    
    if args.explain:
        from src.skills import SkillRegistry
        registry = SkillRegistry()
        registry.initialize()
        print(registry._selector.explain_selection(args.explain))
        return
    
    if args.topic:
        if args.evidence_centric:
            run_evidence_centric(
                topic=args.topic,
                output_path=args.output,
                formats=args.format.split(","),
                knowledge_dir=args.knowledge_dir,
                web_search=args.web_search,
            )
        elif args.coordinated:
            run_coordinated(
                topic=args.topic,
                output_path=args.output,
                formats=args.format.split(","),
                phases=args.phases.split(",") if args.phases else None,
                web_search=args.web_search,
            )
        else:
            run_with_topic(args.topic, rules_path=args.rules, use_llm=args.use_llm,
                           knowledge_dir=args.knowledge_dir,
                           skip_review=args.skip_review)
    else:
        parser.print_help()
        print("\nExample:")
        print("  python -m src.main \"Climate Change Impact on Agriculture\"")
        print("  python -m src.main \"Quantum Computing\" --coordinated --phases plan,generate,export")


if __name__ == "__main__":
    main()