# AI-Powered Report Generator

A production-grade system for generating professional Word documents and PDFs with dynamic skill-based LLM orchestration, RAG retrieval, multi-agent coordination, and an event-driven pipeline architecture.

## Features

- **Agent System** — 6 domain agents (Research, Writing, Citation, Formatting, Export) injected into `AgentCoordinator` with zero hardcoded imports
- **Hierarchical Generators** — `ReportGenerator` → `ChapterGenerator` → `SectionGenerator` → `SubsectionGenerator` → `ParagraphGenerator` with role-cycled content (analysis, methodology, evaluation, implication)
- **Abstract Retriever Interface** — `BaseRetriever` with `HybridRetriever` and `DummyRetriever` implementations; swap retrieval strategies without touching `ContextAssembler`
- **RAG Pipeline** — Hybrid search (BM25 + vector) + CrossEncoder reranking + dedup + token budget
- **Review Pipeline** — 5 checkers (coherence, style, citations, redundancy, formatting)
- **Memory System** — 5 memory types (Abbreviation, Citation, Style, Topic, Figure) with versioned file persistence, atomic writes, and thread-safety
- **Event Bus** — Pub-sub lifecycle events (`phase.started`, `.completed`, `.failed`) instead of ad-hoc callbacks
- **Error Classification** — `RecoverableError` (skip phase, continue) vs `PhaseError` (halt pipeline)
- **Document State** — `DocumentState` as single source of truth; `Workspace` separates doc/conversation state
- **Blueprint System** — Templates for Engineering Project Reports, Research Papers, Internship Reports
- **Prompt System** — 8 Jinja2 templates with `PromptBuilder`
- **IEEE Formatting** — Auto-compliant heading styles, margins, font, citation format
- **Structural Editing** — Section-aware replace/insert/expand/delete/move preserving tables and formatting
- **PDF Conversion** — Multiple backends (docx2pdf, LibreOffice, Word COM)
- **Dynamic Skill System** — Autonomous skill discovery and chaining based on user intent
- **GPU Acceleration** — Detect and utilize GPU for faster LLM inference

## Project Structure

```
report_generation/
├── src/
│   ├── main.py                  # Entry point with CLI
│   │
│   ├── agents/                  # AI agents (no hardcoded imports)
│   │   ├── base.py              # BaseAgent, AgentResponse
│   │   ├── coordinator.py       # AgentCoordinator (pure container, DI-based)
│   │   ├── research.py          # RAG-based evidence retrieval
│   │   ├── writing.py           # Content generation with PromptBuilder
│   │   ├── citation.py          # Citation validation
│   │   ├── formatting_agent.py  # IEEE formatting compliance
│   │   ├── export_agent.py      # DOCX/PDF export with fallback
│   │   ├── planner.py           # Blueprint-based structure planning
│   │   └── factory.py           # AgentFactory (DI convenience)
│   │
│   ├── pipeline/                # Execution pipelines
│   │   ├── coordinated.py       # CoordinatedPipeline (full e2e, 7 phases)
│   │   ├── generation/          # ScratchPipeline, TemplatePipeline
│   │   └── export/              # PDFExportPipeline, ExportFactory
│   │
│   ├── generator/               # Hierarchical content generators
│   │   ├── report.py            # Report → Chapter → Section → Subsection → Paragraph
│   │   ├── chapter.py
│   │   ├── section.py
│   │   ├── subsection.py
│   │   └── paragraph.py         # Role-cycled templates (analysis/methodology/evaluation/implication)
│   │
│   ├── retrieval/               # RAG retrieval (abstract interface)
│   │   ├── base.py              # BaseRetriever, HybridRetriever, DummyRetriever
│   │   ├── search.py            # HybridSearch (BM25 + vector, RRF fusion)
│   │   ├── reranker.py          # CrossEncoder reranking with fallback
│   │   └── context.py           # ContextAssembler (accepts any BaseRetriever)
│   │
│   ├── memory/                  # Memory systems
│   │   ├── tracking.py          # MemoryHub (versioned persistence, thread-safe)
│   │   ├── extended.py          # StyleMemory, TopicMemory, FigureMemory, ContextCompressor
│   │   ├── context.py           # ContextManager, ConversationContext
│   │   └── history.py           # ReportHistory
│   │
│   ├── core/
│   │   ├── state.py             # DocumentState, ConversationState, Workspace
│   │   ├── events.py            # EventBus (pub-sub lifecycle events)
│   │   ├── errors.py            # RecoverableError, PhaseError
│   │   ├── config.py            # Dependency checks & global config
│   │   └── logger.py            # Structured logging
│   │
│   ├── review/                  # Review pipeline
│   │   └── pipeline.py          # ReviewPipeline (5 checkers)
│   │
│   ├── prompts/                 # Jinja2 templates
│   │   └── builder.py           # PromptBuilder
│   │
│   ├── document/                # Document analysis & building
│   │   ├── builder.py           # BlueprintBuilder
│   │   └── analyzer/            # DOCX analyzer (styles, headings, tables, images, etc.)
│   │
│   └── skills/                  # Dynamic skill system
│
├── tests/                       # 354+ pytest tests
│   ├── test_integration_pipeline.py  # Pipeline, generators, agents, persistence
│   ├── test_state_and_memory.py
│   ├── test_rag_retrieval.py
│   └── ...
│
└── skills/                      # External skill definitions
```

## Quick Start

```bash
pip install python-docx
```

```bash
# Generate a report
python -m src.main "Human Impulsive Behaviour" --coordinated --output output/report.docx

# With specific phases
python -m src.main "Quantum Computing" --coordinated --phases plan,generate,export

# As PDF
python -m src.main "Data Science" --coordinated --format pdf
```

## Usage

```bash
# Coordinated pipeline (full e2e — recommended)
python -m src.main "Your Topic" --coordinated

# Legacy pipeline
python -m src.main "Your Topic"

# Select specific phases
python -m src.main "Machine Learning" --coordinated --phases plan,generate,export

# Export format
python -m src.main "Cybersecurity" --coordinated --format pdf

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
| `--use-llm` | Use LLM for planning (Ollama) |
| `--knowledge-dir DIR` | RAG reference documents |
| `--skip-review` | Skip review pipeline |
| `--coordinated` | Use CoordinatedPipeline |
| `--phases PHASES` | Comma-separated: plan,research,generate,review,validate,assemble_doc,export |
| `--output FILE` | Output file path (default: output/output.docx) |
| `--format FMT` | Export format: docx, pdf (default: docx) |

## Architecture

### Pipeline Flow

```
CoordinatedPipeline (single orchestrator)
│
├── plan          → Blueprint / DocumentState
├── research      → ContextAssembler / BaseRetriever
├── generate      → ReportGenerator (hierarchical) or AgentCoordinator
├── review        → ReviewPipeline (5 checkers)
├── validate      → MemoryHub persistence
├── assemble_doc  → DocumentState sync
└── export        → ExportAgent (DOCX → PDF)
```

Each phase emits typed events (`phase.started`, `.completed`, `.failed`) to the `EventBus`. Recoverable failures skip the phase; fatal failures halt the pipeline.

### Agent System (DI-based)

```
AgentFactory.create_coordinator()
  └── AgentCoordinator (pure container, no hardcoded imports)
       ├── ResearchAgent    → ContextAssembler → BaseRetriever
       ├── WritingAgent     → PromptBuilder → Jinja2 templates
       ├── CitationAgent    → Citation validation
       ├── FormattingAgent  → IEEE compliance
       └── ExportAgent      → DOCX + PDF with fallback
```

Agents are injected via constructor `agents=dict` or `register_agent()`. No concrete classes are imported by the coordinator.

### Retrieval Architecture

```
BaseRetriever (abstract interface)
├── HybridRetriever   → HybridSearch → CrossEncoder Reranker
├── DummyRetriever    → No-op (testing)
└── [Custom]          → Implement retrieve() + index_chunks()

ContextAssembler
  └── accepts any BaseRetriever via set_retriever()
  └── dedup → token budget → format
```

### Memory Architecture

```
MemoryHub (versioned JSON persistence, thread-safe)
├── AbbreviationTracker  → "Definition (Abbr)" patterns
├── CitationTracker      → [1], [2-4] reference validation
├── StyleMemory          → Sentence length, passive voice, terminology
├── TopicMemory          → Topic drift prevention
├── FigureMemory         → Figure deduplication
└── ContextCompressor    → Chapter summaries

Persistence:
  save() → atomic write via os.replace(tmp, path) under Lock
  load() → version migration (v1→v2→v3)
```

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
RecoverableError  → phase skipped, pipeline continues
PhaseError        → pipeline halts immediately
```

Import in phase implementations to distinguish expected skips from real failures.

## Testing

```bash
# Run all 354 tests
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
| Ollama | No | Local LLM inference |
