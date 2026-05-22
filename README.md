# AI-Powered Report Generator

A production-grade system for generating professional Word documents and PDFs with dynamic skill-based LLM orchestration.

## Features

- **Dynamic Skill System** - Autonomous skill discovery and chaining based on user intent
- **Document Generation** - Create professional Word documents with python-docx
- **PDF Conversion** - Convert DOCX to PDF using multiple methods (docx2pdf, LibreOffice, Word COM)
- **GPU Acceleration** - Detect and utilize GPU for faster LLM inference
- **Modular Architecture** - Clean separation of concerns with src/ package

## Project Structure

```
report_generation/
├── src/                    # Main source code
│   ├── main.py            # Entry point
│   ├── core/              # Configuration & system utilities
│   │   ├── config.py      # Dependency checks & global config
│   │   └── gpu_check.py   # GPU acceleration detection
│   ├── document/          # Document generation
│   │   ├── doc_generator.py   # Word document creation
│   │   └── pdf_converter.py   # PDF conversion
│   ├── input/             # User input configuration
│   │   └── user_input.py      # Report templates & content
│   └── skills/            # Dynamic skill system
│       ├── skill_loader.py   # Skill discovery & indexing
│       └── skill_orchestrator.py  # LLM skill orchestration
├── skills/                # External skill definitions (17 skills)
│   ├── docx/             # Word document skills
│   ├── pdf/               # PDF processing skills
│   ├── pptx/              # PowerPoint skills
│   ├── xlsx/              # Spreadsheet skills
│   └── ...                # More skills
├── output.docx            # Generated Word document
└── output.pdf             # Generated PDF
```

## Installation

```bash
pip install python-docx docx2pdf
```

## Usage

```bash
# Run full workflow
python -m src.main

# Quick run (no GPU check, no PDF)
python -m src.main --quick
```

## Available Skills

The system automatically discovers skills from the `skills/` directory:

- **docx** - Word document creation, editing, analysis
- **pdf** - PDF processing (read, merge, split, fill forms, OCR)
- **pptx** - PowerPoint presentation generation
- **xlsx** - Spreadsheet operations
- **webapp-testing** - Web application testing with Playwright
- **theme-factory** - Theme generation for artifacts
- **slack-gif-creator** - Animated GIF creation
- **skill-creator** - Skill development and evaluation
- **mcp-builder** - MCP server generation
- **frontend-design** - Frontend UI creation
- **canvas-design** - Canvas-based visual design
- **algorithmic-art** - Generative art with p5.js
- **brand-guidelines** - Anthropic brand styling
- **internal-comms** - Internal communications
- **doc-coauthoring** - Document collaboration
- **claude-api** - Claude API integration
- **frontend-design** - Web UI development

## Customization

Edit `src/input/user_input.py` to modify:

- Report title, subtitle, author, date
- Table of contents entries
- Section content (summary, introduction, conclusion)
- Threats table data
- Bullet point lists
- Styling colors

## Dynamic Skill Loading

The skill system automatically:

1. Scans `skills/` directory for SKILL.md files
2. Extracts metadata (name, description, triggers)
3. Calculates relevance scores based on user input
4. Chains multiple skills when needed
5. Loads skill content for LLM context

Example:
```
User: "Create a Word document report"
Skills: docx, canvas-design, xlsx

User: "Extract text from PDF"
Skills: pdf

User: "Make a PowerPoint presentation"
Skills: pptx
```

## Requirements

- Python 3.10+
- python-docx
- docx2pdf (optional, for PDF conversion)
- win32com (Windows, optional for PDF conversion)

## License

See individual skill LICENSE files in `skills/` directory.