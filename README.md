# AI-Powered Report Generator

A production-grade system for generating professional Word documents and PDFs with dynamic skill-based LLM orchestration, RAG retrieval, and multi-agent coordination.

## Features

- **Agent System** — 6 domain agents (Research, Writing, Citation, Formatting, Export) coordinated by `AgentCoordinator`
- **Hierarchical Generators** — `ReportGenerator` → `ChapterGenerator` → `SectionGenerator` → `SubsectionGenerator` → `ParagraphGenerator`
- **RAG Pipeline** — Hybrid search (BM25 + vector) + CrossEncoder reranking + dedup + token budget
- **Review Pipeline** — 5 checkers (coherence, style, citations, redundancy, formatting)
- **Memory System** — 5 memory types (Abbreviation, Citation, Style, Topic, Figure) with file persistence
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
│   ├── agents/                  # AI agents
│   │   ├── base.py              # BaseAgent, AgentResponse
│   │   ├── coordinator.py       # AgentCoordinator (orchestrates 6 agents)
│   │   ├── research.py          # RAG-based evidence retrieval
│   │   ├── writing.py           # Content generation with PromptBuilder
│   │   ├── citation.py          # Citation validation
│   │   ├── formatting_agent.py  # IEEE formatting compliance
│   │   ├── export_agent.py      # DOCX/PDF export
│   │   └── planner.py           # Blueprint-based structure planning
│   ├── pipeline/                # Execution pipelines
│   │   ├── coordinated.py       # CoordinatedPipeline (full e2e)
│   │   ├── generation/          # ScratchPipeline, TemplatePipeline
│   │   └── export/              # PDFExportPipeline, ExportFactory
│   ├── generator/               # Hierarchical content generators
│   │   ├── report.py            # Report → Chapter → Section → Subsection → Paragraph
│   │   ├── chapter.py
│   │   ├── section.py
│   │   ├── subsection.py
│   │   └── paragraph.py
│   ├── retrieval/               # RAG retrieval
│   │   ├── search.py            # HybridSearch (BM25 + vector)
│   │   ├── reranker.py          # CrossEncoder reranking
│   │   └── context.py           # ContextAssembler
│   ├── memory/                  # Memory systems
│   │   ├── tracking.py          # MemoryHub, AbbreviationTracker, CitationTracker
│   │   ├── extended.py          # StyleMemory, TopicMemory, FigureMemory, ContextCompressor
│   │   ├── context.py           # ContextManager, ConversationContext
│   │   └── history.py           # ReportHistory
│   ├── core/
│   │   ├── state.py             # DocumentState, ConversationState, Workspace
│   │   ├── config.py            # Dependency checks & global config
│   │   └── logger.py            # Structured logging
│   ├── review/                  # Review pipeline
│   │   └── pipeline.py          # ReviewPipeline (5 checkers)
│   ├── prompts/                 # Jinja2 templates
│   │   └── builder.py           # PromptBuilder
│   ├── document/                # Document analysis & building
│   │   ├── builder.py           # BlueprintBuilder
│   │   └── analyzer/            # DOCX analyzer (styles, headings, tables, images, etc.)
│   └── skills/                  # Dynamic skill system
├── tests/                       # 342+ pytest tests
│   ├── test_integration_pipeline.py
│   ├── test_state_and_memory.py
│   ├── test_rag_retrieval.py
│   └── ...
└── skills/                      # External skill definitions
```

## Installation

```bash
pip install python-docx docx2pdf
```

## Usage

```bash
# Legacy pipeline
python -m src.main "Climate Change Impact on Agriculture"

# Coordinated pipeline (full e2e with all agents)
python -m src.main "Quantum Computing" --coordinated

# Select specific phases
python -m src.main "Machine Learning" --coordinated --phases plan,generate,export

# Export to specific format
python -m src.main "Data Science" --coordinated --format pdf

# Custom output path
python -m src.main "Cybersecurity" --coordinated --output reports/cyber.docx

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
| `--use-llm` | Use LLM for planning |
| `--knowledge-dir DIR` | RAG reference documents |
| `--skip-review` | Skip review pipeline |
| `--coordinated` | Use CoordinatedPipeline |
| `--phases PHASES` | Comma-separated phases |
| `--output FILE` | Output file path |
| `--format FMT` | Export format (docx/pdf) |

## Architecture

### Pipeline Flow (CoordinatedPipeline)

```
Plan → Research → Generate → Review → Validate → Assemble → Export
 │        │           │          │         │          │         │
Blueprint  RAG       Agents/    5       Memory     Document   DOCX/
                    Generators Checkers  Save      State      PDF
```

### Agent System (AgentCoordinator)

```
AgentCoordinator
├── ResearchAgent    → ContextAssembler (HybridSearch → Reranker → Dedup)
├── WritingAgent     → PromptBuilder (Jinja2 templates)
├── CitationAgent    → Validates citation patterns
├── FormattingAgent  → IEEE compliance checks
└── ExportAgent      → DOCX generator + PDF converter
```

### Memory Architecture

```
MemoryHub (with file persistence)
├── AbbreviationTracker  → Scans text for "Abbr (Definition)" patterns
├── CitationTracker      → Validates [1], [2-4] reference patterns
├── StyleMemory          → Tracks sentence length, passive voice, terminology
├── TopicMemory          → Prevents topic drift across sections
├── FigureMemory         → Deduplicates figures and captions
└── ContextCompressor    → Chapter summaries for context injection
```

### Hierarchical Generators

```
ReportGenerator
└── ChapterGenerator (level 1)
    └── SectionGenerator (level 2)
        └── SubsectionGenerator (level 3+)
            └── ParagraphGenerator (atomic unit)
```

Each layer receives `GeneratorContext` with:
- Topic and report type
- Document state (`DocumentState`)
- Retrieval context (from `ContextAssembler`)
- Style profile (from `StyleMemory`)
- Chapter summaries (for cross-chapter coherence)

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_integration_pipeline.py -v

# Run with coverage
pytest tests/ --cov=src
```

## Requirements

- Python 3.10+
- python-docx
- docx2pdf (optional, for PDF conversion)
- win32com (Windows, optional for PDF conversion)
- sentence-transformers (optional, for CrossEncoder reranking)
- rank-bm25 (optional, for BM25 search)
- Jinja2 (optional, for prompt templates)
- Ollama (optional, for local LLM inference)
