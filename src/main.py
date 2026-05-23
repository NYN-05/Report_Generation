"""
Main Entry Point
=================
Unified entry point for the report generation platform.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import config
from src.core.logger import get_logger
from src.agents import OrchestratorAgent
from src.pipeline import ScratchPipeline, PDFExportPipeline
from src.memory import ContextManager, ReportHistory


logger = get_logger("main")


def run_coordinated(topic: str, output_path: str = "output/output.docx",
                    formats: Optional[list] = None,
                    phases: Optional[list] = None,
                    use_provider: bool = True):
    """Run the CoordinatedPipeline with optional phase selection."""
    logger.info(f"Coordinated pipeline for: {topic}")
    from src.pipeline import CoordinatedPipeline
    from src.generator import ReportGenerator
    from src.memory import MemoryHub
    from src.providers.factory import get_default_provider

    provider = get_default_provider() if use_provider else None
    if provider:
        logger.info(f"Using provider: {provider.__class__.__name__} ({provider.model})")
    else:
        logger.warning("No LLM provider available — using template fallback")

    pipe = CoordinatedPipeline()
    result = pipe.execute(
        {"topic": topic, "output_path": output_path, "formats": formats or ["docx"]},
        phases=phases,
        callback=lambda phase, status: print(f"  [{status}] {phase}"),
        components={
            "report_generator": ReportGenerator(provider=provider),
            "memory_hub": MemoryHub(),
            "context_assembler": None,
        },
    )
    if result.success:
        print(f"\n[OK] Pipeline complete in {result.execution_time:.2f}s")
        print(f"     Output: {result.output_path}")
        phases_done = result.data.get("phases_completed", [])
        print(f"     Phases: {', '.join(phases_done)}")
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
            knowledge_dir=knowledge_dir,
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
    
    args = parser.parse_args()
    
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
        if args.coordinated:
            run_coordinated(
                topic=args.topic,
                output_path=args.output,
                formats=args.format.split(","),
                phases=args.phases.split(",") if args.phases else None,
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