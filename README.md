# AI-Powered Report Generator

A production-grade system for generating professional Word documents and PDFs with knowledge-driven generation, dynamic skill-based LLM orchestration, RAG retrieval, multi-agent coordination, centralized formatting, and an event-driven pipeline architecture.

## Features

- **Evidence-Centric Architecture** — Fact extraction → FactStore → Evidence coverage → Evidence-constrained generation (src/facts/, src/evidence/)
- **Resource Intelligence** — Resource classification, metadata extraction, structural analysis, relationship mapping for PDF, DOCX, PPTX, XLSX, CSV, source code, GitHub repos, images (src/resource_intelligence/)
- **Hallucination Detection** — Multi-check validation for unsupported metrics, technologies, citations, methodologies, and results (src/validation/hallucination_detector.py)
- **Knowledge-Driven Generation** — 12 architectural layers (research, fact extraction, knowledge graph, domain intelligence, citation grounding, evidence coverage, iterative refinement, long-context memory, dynamic blueprint, quality scoring, few-shot learning, production optimization) integrated into a single `KnowledgeDrivenReportGenerator`
- **Centralized Formatting** — `StyleManager` singleton as single source of truth for all DOCX formatting; `DocumentStyleValidator` with pre-save compliance checking and auto-fix
- **Agent System** — 7 domain agents (Research, Writing, Citation, Formatting, Export, Planner, Editor) injected into `AgentCoordinator` with zero hardcoded imports
- **Hierarchical Generators** — `ReportGenerator` → `ChapterGenerator` → `SectionGenerator` → `SubsectionGenerator` → `ParagraphGenerator` with role-cycled content (analysis, methodology, evaluation, implication)
- **Abstract Retriever Interface** — `BaseRetriever` with `HybridRetriever` and `DummyRetriever` implementations; swap retrieval strategies without touching `ContextAssembler`
- **RAG Pipeline** — Hybrid search (BM25 + vector) + CrossEncoder reranking + dedup + token budget
- **Review Pipeline** — 6 checkers (coherence, style, citations, redundancy, formatting, coverage)
- **Memory System** — 6 memory types (Abbreviation, Citation, Style, Topic, Figure, Fact) with versioned file persistence, atomic writes, and thread-safety
- **Event Bus** — Pub-sub lifecycle events (`phase.started`, `.completed`, `.failed`) instead of ad-hoc callbacks
- **Error Classification** — `RecoverableError` (skip phase, continue) vs `PhaseError` (halt pipeline)
- **Document State** — `DocumentState` as single source of truth; `Workspace` separates doc/conversation state
- **Blueprint System** — Templates for Engineering Project Reports, Research Papers, Internship Reports + evidence-driven blueprint generation
- **Prompt System** — 8 Jinja2 templates with `PromptBuilder`
- **Structural Editing** — Section-aware replace/insert/expand/delete/move preserving tables and formatting
- **PDF Conversion** — Multiple backends (docx2pdf, LibreOffice, Word COM) — auto-generated after every DOCX build
- **Dynamic Skill System** — Autonomous skill discovery and chaining based on user intent
- **GPU Acceleration** — Detect and utilize GPU for faster LLM inference
- **Ollama-Only** — No silent LLM fallback; provider unavailability raises `ProviderNotAvailableError`

## Project Structure

```
report_generation/
├── src/
│   ├── main.py                       # Entry point with CLI
│   │
│   ├── agents/                       # AI agents (no hardcoded imports)
│   │   ├── base.py                   # BaseAgent, AgentResponse
│   │   ├── coordinator.py            # AgentCoordinator (pure container, DI-based)
│   │   ├── research.py               # RAG-based evidence retrieval
│   │   ├── writing.py                # Content generation with PromptBuilder
│   │   ├── citation.py               # Citation validation
│   │   ├── formatting_agent.py       # Formatting compliance
│   │   ├── export_agent.py           # DOCX/PDF export with fallback
│   │   ├── planner.py                # Blueprint-based structure planning
│   │   ├── editor.py                 # Structural content editing
│   │   ├── orchestrator.py           # Multi-agent orchestration
│   │   └── factory.py                # AgentFactory (DI convenience)
│   │
│   ├── pipeline/                     # Execution pipelines
│   │   ├── base.py                   # BasePipeline
│   │   ├── coordinated.py            # CoordinatedPipeline (full e2e, 9 phases)
│   │   ├── generator.py              # Pipeline generator
│   │   ├── runner.py                 # Pipeline runner
│   │   ├── generation/               # ScratchPipeline, TemplatePipeline
│   │   └── export/                   # PDFExportPipeline, ExportFactory
│   │
│   ├── generator/                    # Hierarchical content generators
│   │   ├── report.py                 # Report → Chapter → Section → Subsection → Paragraph
│   │   ├── chapter.py
│   │   ├── chapter_uniqueness.py     # Cross-chapter content dedup
│   │   ├── section.py
│   │   ├── subsection.py
│   │   ├── paragraph.py              # Role-cycled templates
│   │   ├── paragraph_quality.py      # Paragraph-level quality checks
│   │   ├── content_validator.py      # Tuple-aware content validation
│   │   ├── content_blocks.py         # Content block definitions
│   │   ├── base.py                   # BaseGenerator
│   │   ├── knowledge_driven_generator.py  # Integrates 12 architectural layers
│   │   ├── evidence_based_generator.py    # Evidence-constrained generation
│   │   ├── academic_writing_engine.py # Academic tone & style enforcement
│   │   ├── multi_pass_improver.py    # Iterative content improvement
│   │   ├── technical_depth.py        # Technical depth enhancer
│   │   └── prompt_builder_v2.py      # Advanced prompt construction
│   │
│   ├── facts/                        # Fact Extraction & Store (Evidence Core)
│   │   ├── models.py                 # Fact, FactType, EvidenceSpan, SourceReference
│   │   ├── extractor.py              # FactExtractor (regex-based extraction)
│   │   ├── store.py                  # FactStore (in-memory + persist, indexed)
│   │   ├── validator.py              # FactValidator (confidence, type checks)
│   │   ├── linker.py                 # FactLinker (cross-fact relationship graph)
│   │   └── generation_controller.py  # EvidenceConstrainedGenerator
│   │
│   ├── evidence/                     # Evidence Coverage & Explainability
│   │   ├── coverage_models.py        # SectionCoverage, CoverageLevel, GenerationMode
│   │   ├── coverage_engine.py        # Coverage computation per section
│   │   ├── coverage_validator.py     # Coverage threshold validation
│   │   ├── traceability.py           # Source-to-content trace links
│   │   ├── fusion_engine.py          # Multi-source evidence fusion
│   │   ├── dashboard.py              # Explainability dashboard
│   │   ├── report_explainability.py  # Supplementary evidence reports
│   │   └── orchestrator.py           # Evidence pipeline orchestration
│   │
│   ├── resource_intelligence/        # Resource Understanding Layer
│   │   ├── resource_classifier.py    # Resource type classification
│   │   ├── resource_analyzer.py      # Deep resource content analysis
│   │   ├── resource_profiler.py      # Resource structure profiling
│   │   ├── resource_metadata_store.py # Resource metadata persistence
│   │   └── resource_relationship_builder.py  # Cross-resource relationships
│   │
│   ├── research/                     # Research Layer
│   │   ├── fact_extractor.py         # LLM-based fact extraction
│   │   ├── evidence_builder.py       # Evidence construction from sources
│   │   ├── source_validator.py       # Source credibility validation
│   │   └── research_planner.py       # Research plan generation
│   │
│   ├── knowledge/                    # Knowledge Layer
│   │   ├── knowledge_graph.py        # KnowledgeGraphBuilder
│   │   ├── concept_mapper.py         # ConceptMapper
│   │   └── relationship_extractor.py
│   │
│   ├── domain/                       # Domain Intelligence Layer
│   │   ├── classifier.py             # DomainClassifier
│   │   └── prompt_packs.py           # DomainSpecificPromptPacks
│   │
│   ├── citation/                     # Citation Grounding Layer
│   │   ├── evidence_citation_mapper.py
│   │   └── source_paragraph_generator.py
│   │
│   ├── content/                      # Content Generation Engine
│   │   ├── content_type_classifier.py
│   │   ├── fact_driven_generator.py  # Fact-constrained content generation
│   │   ├── section_writer.py
│   │   ├── paragraph_quality_engine.py
│   │   ├── technical_depth_enhancer.py
│   │   ├── refinement_loop.py
│   │   ├── quality_gate.py
│   │   └── generic_detector.py
│   │
│   ├── refinement/                   # Iterative Refinement Layer
│   │   ├── section_refiner.py        # SectionRefiner
│   │   └── quality_feedback_loop.py  # QualityFeedbackLoop
│   │
│   ├── memory/                       # Memory systems
│   │   ├── tracking.py               # MemoryHub (versioned persistence, thread-safe)
│   │   ├── extended.py               # StyleMemory, TopicMemory, FigureMemory, ContextCompressor
│   │   ├── context.py                # ContextManager, ConversationContext
│   │   ├── history.py                # ReportHistory
│   │   ├── hierarchical_memory.py    # HierarchicalMemory
│   │   ├── chapter_summary_store.py  # ChapterSummaryStore
│   │   └── fact_memory.py            # FactMemory
│   │
│   ├── blueprint/                    # Dynamic Blueprint Layer
│   │   └── topic_blueprint.py        # TopicSpecificBlueprintGenerator
│   │
│   ├── quality/                      # Quality Scoring Layer
│   │   ├── technical_depth_score.py  # TechnicalDepthScore
│   │   ├── evidence_score.py         # EvidenceScore
│   │   ├── evidence_coverage_score.py
│   │   ├── coherence_score.py        # CoherenceScore
│   │   ├── academic_score.py         # AcademicScore
│   │   ├── evidence_fidelity_score.py  # Truthfulness scoring
│   │   ├── fact_utilization_score.py   # Fact usage efficiency
│   │   ├── source_coverage_score.py    # Source coverage breadth
│   │   ├── traceability_score.py       # Source traceability
│   │   ├── hallucination_risk_score.py # Hallucination probability
│   │   └── comprehensive_quality_score.py  # Weighted aggregate scoring
│   │
│   ├── few_shot/                     # Few-Shot Learning Layer
│   │   ├── example_library.py        # ExampleLibrary
│   │   └── example_retriever.py      # DynamicExampleRetriever
│   │
│   ├── optimization/                 # Production Optimization Layer
│   │   ├── async_retrieval.py        # AsyncRetrieval
│   │   ├── async_generation.py       # AsyncGeneration
│   │   ├── streaming_writer.py       # StreamingWriter
│   │   ├── retrieval_cache.py        # RetrievalCache
│   │   └── context_cache.py          # ContextCache
│   │
│   ├── validation/                   # Validation Layer
│   │   ├── base.py                   # BaseValidator
│   │   ├── content.py                # Content validation
│   │   ├── document.py               # Document validation
│   │   ├── schema.py                 # Schema validation
│   │   └── hallucination_detector.py # Hallucination detection engine
│   │
│   ├── retrieval/                    # RAG retrieval (abstract interface)
│   │   ├── base.py                   # BaseRetriever, HybridRetriever, DummyRetriever
│   │   ├── search.py                 # HybridSearch (BM25 + vector, RRF fusion)
│   │   ├── reranker.py               # CrossEncoder reranking with fallback
│   │   ├── context.py                # ContextAssembler (accepts any BaseRetriever)
│   │   ├── benchmarks.py             # Retrieval benchmarks
│   │   └── web.py                    # Web search integration
│   │
│   ├── ingestion/                    # Document Ingestion Layer
│   │   ├── parser.py                 # Multi-format document parser
│   │   ├── chunker.py                # Document chunking strategies
│   │   ├── embeddings.py             # Embedding generation
│   │   ├── store.py                  # Vector store interface
│   │   └── pipeline.py               # Ingestion pipeline
│   │
│   ├── document/                     # Document generation & formatting
│   │   ├── base.py                   # BaseDocumentGenerator
│   │   ├── builder.py                # DocumentBuilder
│   │   ├── docx_v2_generator.py      # Main DOCX generator (uses StyleManager)
│   │   ├── parser.py                 # Document parser
│   │   ├── pdf_converter.py          # PDF conversion (multi-backend)
│   │   ├── blueprint/                # BlueprintBuilder, models, catalog
│   │   │   ├── builder.py
│   │   │   ├── models.py
│   │   │   ├── planner.py
│   │   │   ├── loader.py
│   │   │   ├── selector.py
│   │   │   ├── validator.py
│   │   │   ├── evidence_blueprint_generator.py
│   │   │   ├── topic_blueprint_generator.py
│   │   │   └── catalog/
│   │   ├── styles/                   # Centralized formatting (single source of truth)
│   │   │   ├── document_styles.py    # Dataclass definitions
│   │   │   ├── default_styles.py     # Default style presets
│   │   │   ├── manager.py            # StyleManager (singleton)
│   │   │   ├── style_manager.py      # Backward compat wrapper
│   │   │   ├── style_validator.py    # DocumentStyleValidator (9 rules)
│   │   │   ├── analyzer.py           # Style analysis
│   │   │   └── extractor.py          # Style extraction
│   │   ├── formatter/                # Utility formatters
│   │   │   ├── font.py               # FontFormatter (reads defaults from StyleManager)
│   │   │   ├── paragraph.py          # ParagraphFormatter
│   │   │   └── table.py              # TableFormatter
│   │   ├── structure/                # Structural document editing
│   │   │   ├── model.py              # StructuralNode tree
│   │   │   ├── locator.py            # SectionLocator
│   │   │   ├── operations.py         # Replace/Insert/Expand/Delete/Move
│   │   │   └── planner.py            # StructurePlanner
│   │   ├── analyzer/                 # Document analysis
│   │   │   ├── parser.py
│   │   │   ├── models.py
│   │   │   ├── classifier.py
│   │   │   ├── heading.py
│   │   │   ├── styles.py
│   │   │   ├── tables.py
│   │   │   ├── images.py
│   │   │   ├── references.py
│   │   │   ├── equations.py
│   │   │   ├── footnotes.py
│   │   │   ├── headers_footers.py
│   │   │   ├── cross_references.py
│   │   │   ├── watermarks.py
│   │   │   └── graph.py
│   │   ├── rules/                    # Document validation rules
│   │   │   ├── engine.py
│   │   │   ├── loader.py
│   │   │   └── models.py
│   │   └── template/                 # Template system
│   │       ├── loader.py
│   │       └── catalog/
│   │
│   ├── core/                         # Core framework
│   │   ├── state.py                  # DocumentState, ConversationState, Workspace
│   │   ├── events.py                 # EventBus (pub-sub lifecycle events)
│   │   ├── errors.py                 # RecoverableError, PhaseError, ProviderNotAvailableError
│   │   ├── config.py                 # Dependency checks & global config
│   │   ├── logger.py                 # Structured logging
│   │   ├── constants.py              # System-wide constants
│   │   ├── decorators.py             # Utility decorators
│   │   ├── exceptions.py             # Exception hierarchy
│   │   ├── gpu_check.py              # GPU detection & acceleration
│   │   └── utils.py                  # Shared utilities
│   │
│   ├── review/                       # Review pipeline
│   │   ├── base.py                   # BaseChecker
│   │   ├── pipeline.py               # ReviewPipeline (6 checkers)
│   │   ├── coherence.py
│   │   ├── style.py
│   │   ├── citations.py
│   │   ├── redundancy.py
│   │   └── formatting.py
│   │
│   ├── prompts/                      # Jinja2 templates
│   │   └── builder.py                # PromptBuilder
│   │
│   ├── providers/                    # LLM providers
│   │   ├── base.py                   # BaseProvider
│   │   ├── factory.py                # ProviderFactory
│   │   ├── ollama.py                 # Ollama provider (mandatory, no fallback)
│   │   └── retry.py                  # Retry logic for provider calls
│   │
│   └── skills/                       # Dynamic skill system
│       ├── base.py
│       ├── loader.py
│       ├── orchestrator.py
│       ├── registry.py
│       └── selector.py
│
├── tests/                            # 354+ pytest tests
│   ├── test_integration_pipeline.py
│   ├── test_state_and_memory.py
│   ├── test_rag_retrieval.py
│   ├── test_document_structure.py
│   ├── test_editing_operations.py
│   ├── test_blueprint_system.py
│   └── ...
│
├── knowledge/                        # Reference documents
│   └── HUMAN_BRAIN.md
│
└── skills/                           # External skill definitions
```

## Quick Start

```bash
pip install python-docx
```

```bash
# Generate a report (knowledge-driven pipeline)
python -m src.main "Machine Learning for NID" --coordinated --output output/knowledge_report.docx
```

## Usage

```bash
# Coordinated pipeline (full e2e — recommended, auto-generates DOCX + PDF)
python -m src.main "Your Topic" --coordinated

# Legacy pipeline
python -m src.main "Your Topic"

# Select specific phases
python -m src.main "Machine Learning" --coordinated --phases plan,research,generate,review,assemble_doc,export

# Custom output path
python -m src.main "AI Ethics" --coordinated --output reports/ethics.docx

# Show system status
python -m src.main --status

# List available skills
python -m src.main --list-skills
```

## CLI Reference

| Flag | Description |
|------|-------------|
| `topic` | Report topic (positional) |
| `--status`, `-s` | Show system status |
| `--list-skills` | List available skills |
| `--explain TASK` | Explain skill selection |
| `--rules FILE` | Custom rules JSON/MD |
| `--use-llm` | Use LLM for planning (Ollama — mandatory, no fallback) |
| `--knowledge-dir DIR` | RAG reference documents |
| `--skip-review` | Skip review pipeline |
| `--coordinated` | Use CoordinatedPipeline (9 phases) |
| `--phases PHASES` | Comma-separated: plan,research,knowledge,generate,review,validate,refine,assemble_doc,export |
| `--output FILE` | Output file path (default: output/output.docx + automatic .pdf) |
| `--format FMT` | Export format: docx, pdf (default: docx) |

## Architecture

### Pipeline Flow

```
CoordinatedPipeline (9 phases)
│
├── plan          → Blueprint / ReportPlan
├── research      → ContextAssembler / BaseRetriever (facts, evidence, sources)
├── knowledge     → KnowledgeGraphBuilder / DomainClassifier / ConceptMapper
├── generate      → KnowledgeDrivenReportGenerator (hierarchical + 12 layers)
│                   ├── Evidence-constrained generation (FactStore → CoverageEngine)
│                   ├── Resource Intelligence
│                   └── Hallucination-aware prompts
├── review        → ReviewPipeline (coherence, style, citations, redundancy, formatting)
├── validate      → MemoryHub persistence + quality scoring (evidence fidelity, traceability, hallucination risk)
├── refine        → SectionRefiner / QualityFeedbackLoop (iterative improvement)
├── assemble_doc  → DOCXV2Generator → StyleManager → DocumentStyleValidator → auto PDF
└── export        → ExportAgent (DOCX + PDF)
```

Each phase emits typed events (`phase.started`, `.completed`, `.failed`) to the `EventBus`. Recoverable failures skip the phase; fatal failures halt the pipeline.

### Knowledge-Driven Generation

```
KnowledgeDrivenReportGenerator
  │
  ├── Fact Extraction       → FactExtractor, FactStore, FactValidator, FactLinker
  ├── Evidence Coverage     → CoverageEngine, CoverageValidator, GenerationController
  ├── Resource Intelligence → ResourceClassifier, ResourceAnalyzer, ResourceProfiler
  ├── Research Layer        → FactExtractor, EvidenceBuilder, SourceValidator, ResearchPlanner
  ├── Knowledge Layer       → KnowledgeGraphBuilder, ConceptMapper, RelationshipExtractor
  ├── Domain Intelligence   → DomainClassifier, DomainSpecificPromptPacks
  ├── Citation Grounding    → EvidenceToCitationMapper, SourceBackedParagraphGenerator
  ├── Iterative Refinement  → SectionRefiner, QualityFeedbackLoop
  ├── Long Context          → HierarchicalMemory, ChapterSummaryStore, FactMemory
  ├── Dynamic Blueprint     → TopicSpecificBlueprintGenerator, EvidenceBlueprintGenerator
  ├── Quality Scoring       → EvidenceFidelity, FactUtilization, SourceCoverage,
  │                           Traceability, HallucinationRisk, TechnicalDepth, Academic
  ├── Hallucination Detection → Multi-check validation (metrics, techs, citations)
  ├── Few-Shot Learning     → ExampleLibrary, DynamicExampleRetriever
  └── Production Optimizer  → AsyncRetrieval, AsyncGeneration, StreamingWriter, Caches
```

### Centralized Formatting

```
StyleManager (singleton, single source of truth)
  │
  ├── setup_document()       → Applies page margins, Normal style, font defaults
  ├── apply_paragraph_style() → Applies ParagraphStyle/HeadingStyle/ReferenceStyle to element
  ├── write_run()            → Creates formatted text run
  └── validate_document()    → Runtime compliance check

DocumentStyles (dataclass)
  ├── content         → 12pt Times New Roman, justified, 1.5 spacing
  ├── heading_main    → 16pt bold centered
  ├── heading_sub     → 14pt bold left
  ├── heading_section → 12pt bold left
  ├── cover_page      → 28pt title / 16pt subtitle / 14pt author
  ├── reference       → 12pt, hanging indent 0.5"
  └── table           → 11pt header/cell, Table Grid

DocumentStyleValidator (9 rules)
  ├── font, size, alignment, spacing, heading consistency
  └── auto-fix on violations

No hardcoded Pt(), font.name, or WD_ALIGN_PARAGRAPH outside styles/
```

### Agent System (DI-based)

```
AgentFactory.create_coordinator()
  └── AgentCoordinator (pure container, no hardcoded imports)
       ├── ResearchAgent    → ContextAssembler → BaseRetriever
       ├── WritingAgent     → PromptBuilder → Jinja2 templates
       ├── CitationAgent    → Citation validation
       ├── FormattingAgent  → Compliance checking
       └── ExportAgent      → DOCX + PDF with fallback
```

Agents are injected via constructor `agents=dict` or `register_agent()`. No concrete classes are imported by the coordinator.

### Hierarchical Generators

```
ReportGenerator  ─── topic → "Foundations of ...", "Mechanisms of ...", ...
  └── ChapterGenerator
       └── SectionGenerator  ─── roles: analysis, methodology, evaluation, implication
            └── SubsectionGenerator
                 └── ParagraphGenerator  ─── 4 template groups
```

Each layer receives `GeneratorContext` with topic, retrieval context, style profile, and chapter summaries for cross-chapter coherence.

### Error Handling

```
RecoverableError        → phase skipped, pipeline continues
PhaseError              → pipeline halts immediately
ProviderNotAvailableError → halts when Ollama is unreachable
```

## Testing

```bash
# Run all 354+ tests
pytest tests/

# Specific test file
pytest tests/test_integration_pipeline.py -v

# With coverage
pytest tests/ --cov=src
```

## Requirements

| Package | Required | Purpose |
|---------|----------|---------|
| python-docx | Yes | DOCX generation |
| docx2pdf | No | PDF conversion |
| win32com | No (Windows) | PDF conversion via Word |
| sentence-transformers | No | CrossEncoder reranking |
| rank-bm25 | No | BM25 search |
| Jinja2 | No | Prompt templates |
| Ollama | Yes (at runtime) | Local LLM inference (mandatory, no fallback) |
| json | Yes | Fact/evidence serialization |
