<#
.SYNOPSIS
  Comprehensive demo script for the AI-Powered Report Generator.
  Exercises all major features: coordinated pipeline, evidence-centric mode,
  RAG knowledge, web search, phase selection, review, export formats.

.DESCRIPTION
  Runs multiple report generation scenarios to showcase the full feature set.
  Results are saved to output/ with timestamps.

.EXAMPLE
  .\run_demo.ps1
  .\run_demo.ps1 -Topic "Machine Learning for NID"
#>

param(
    [string]$Topic = "Human Brain",
    [string]$KnowledgeDir = "knowledge",
    [switch]$SkipLong = $false
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSCommandPath
$Python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputDir = Join-Path $Root "output"

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

function Write-Step {
    param([string]$Title, [string]$Cmd)
    $sep = "=" * 70
    Write-Host "`n$sep" -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor White
    Write-Host "  > $Cmd" -ForegroundColor Gray
    Write-Host "$sep`n" -ForegroundColor Cyan
}

function Run-Test {
    param([string]$Name, [string]$Arguments)
    $log = Join-Path $OutputDir "demo_${Timestamp}_${Name}.log"
    $cmd = "$Python -m src.main $Arguments"
    Write-Step -Title $Name -Cmd $cmd
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $fullCmd = "$Python -m src.main $Arguments"
        Write-Host "  Running: $fullCmd" -ForegroundColor Gray
        $output = cmd /c $fullCmd 2>&1
        $exitCode = $LASTEXITCODE
        if ($output) { $output | Out-File -FilePath $log -Encoding utf8; $output | ForEach-Object { Write-Host "  $_" } }
        if ($exitCode -ne 0) {
            Write-Host "  [FAILED] Exit code: $exitCode" -ForegroundColor Red
        } else {
            Write-Host "  [PASSED]" -ForegroundColor Green
        }
    } catch {
        Write-Host "  [FAILED] $_" -ForegroundColor Red
    }
    $sw.Stop()
    Write-Host "  Duration: $($sw.Elapsed.TotalSeconds.ToString('F1'))s" -ForegroundColor Yellow
}

Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║     AI-Powered Report Generator — Full Feature Demo         ║
║     $Timestamp
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Magenta

# ───────────────────────────────────────────────
# 1. SYSTEM HEALTH
# ───────────────────────────────────────────────
Run-Test -Name "1. System Status" -Arguments "--status"

# ───────────────────────────────────────────────
# 2. SKILL LIST
# ───────────────────────────────────────────────
Run-Test -Name "2. List Available Skills" -Arguments "--list-skills"

# ───────────────────────────────────────────────
# 3. LEGACY PIPELINE (topic only)
# ───────────────────────────────────────────────
Run-Test -Name "3. Legacy Pipeline (topic only)" -Arguments (
    """$Topic"" --output output/demo_${Timestamp}_legacy.docx"
)

# ───────────────────────────────────────────────
# 4. LEGACY PIPELINE + KNOWLEDGE + REVIEW
# ───────────────────────────────────────────────
Run-Test -Name "4. Legacy + Knowledge + Review" -Arguments (
    """$Topic"" --knowledge-dir $KnowledgeDir --output output/demo_${Timestamp}_legacy_knowledge.docx"
)

# ───────────────────────────────────────────────
# 5. COORDINATED PIPELINE (full 9 phases)
# ───────────────────────────────────────────────
Run-Test -Name "5. Coordinated Pipeline (full)" -Arguments (
    """$Topic"" --coordinated --output output/demo_${Timestamp}_coordinated.docx"
)

# ───────────────────────────────────────────────
# 6. COORDINATED + KNOWLEDGE DIRECTORY
# ───────────────────────────────────────────────
Run-Test -Name "6. Coordinated + Knowledge RAG" -Arguments (
    """$Topic"" --coordinated --knowledge-dir $KnowledgeDir --output output/demo_${Timestamp}_coordinated_rag.docx"
)

# ───────────────────────────────────────────────
# 7. COORDINATED + SKIP REVIEW
# ───────────────────────────────────────────────
Run-Test -Name "7. Coordinated + Skip Review" -Arguments (
    """$Topic"" --coordinated --skip-review --output output/demo_${Timestamp}_noreview.docx"
)

# ───────────────────────────────────────────────
# 8. COORDINATED + CUSTOM PHASES (plan → research → generate → export)
# ───────────────────────────────────────────────
Run-Test -Name "8. Coordinated (custom phases)" -Arguments (
    """$Topic"" --coordinated --phases plan,research,generate,export --output output/demo_${Timestamp}_custom_phases.docx"
)

# ───────────────────────────────────────────────
# 9. COORDINATED + PDF OUTPUT
# ───────────────────────────────────────────────
Run-Test -Name "9. Coordinated + PDF Output" -Arguments (
    """$Topic"" --coordinated --format pdf --output output/demo_${Timestamp}_pdf.pdf"
)

# ───────────────────────────────────────────────
# 10. EVIDENCE-CENTRIC PIPELINE (full evidence layer)
# ───────────────────────────────────────────────
Run-Test -Name "10. Evidence-Centric Pipeline" -Arguments (
    """$Topic"" --evidence-centric --knowledge-dir $KnowledgeDir --output output/demo_${Timestamp}_evidence.docx"
)

# ───────────────────────────────────────────────
# 11. EVIDENCE-CENTRIC + PDF
# ───────────────────────────────────────────────
Run-Test -Name "11. Evidence-Centric + PDF" -Arguments (
    """$Topic"" --evidence-centric --knowledge-dir $KnowledgeDir --format pdf --output output/demo_${Timestamp}_evidence_pdf.pdf"
)

# ───────────────────────────────────────────────
# 12. COORDINATED + LLM PLANNING
# ───────────────────────────────────────────────
Run-Test -Name "12. Coordinated + LLM Planning" -Arguments (
    """$Topic"" --coordinated --use-llm --output output/demo_${Timestamp}_llmplan.docx"
)

# ───────────────────────────────────────────────
# 13. COORDINATED + WEB SEARCH
# ───────────────────────────────────────────────
Run-Test -Name "13. Coordinated + Web Search" -Arguments (
    """$Topic"" --coordinated --web-search --output output/demo_${Timestamp}_web.docx"
)

# ───────────────────────────────────────────────
# 14. COORDINATED + CUSTOM RULES
# ───────────────────────────────────────────────
Run-Test -Name "14. Coordinated + Custom Rules" -Arguments (
    """$Topic"" --coordinated --rules prompts/default_rules.json --output output/demo_${Timestamp}_rules.docx"
)

# ───────────────────────────────────────────────
# 15. RUN ALL PHASES EXPLICITLY
# ───────────────────────────────────────────────
Run-Test -Name "15. All Phases Explicit" -Arguments (
    """$Topic"" --coordinated --phases plan,research,knowledge,generate,review,validate,refine,assemble_doc,export --output output/demo_${Timestamp}_allphases.docx"
)

# ───────────────────────────────────────────────
# SUMMARY
# ───────────────────────────────────────────────
Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                       DEMO COMPLETE                          ║
╠══════════════════════════════════════════════════════════════╣
║  All outputs saved to:                                       ║
║    $OutputDir
╚══════════════════════════════════════════════════════════════╝

Completed scenarios:
  1.  System Status
  2.  List Skills
  3.  Legacy Pipeline
  4.  Legacy + Knowledge + Review
  5.  Coordinated Pipeline
  6.  Coordinated + RAG
  7.  Coordinated + Skip Review
  8.  Coordinated + Custom Phases
  9.  Coordinated + PDF
  10. Evidence-Centric Pipeline
  11. Evidence-Centric + PDF
  12. Coordinated + LLM Planning
  13. Coordinated + Web Search
  14. Coordinated + Custom Rules
  15. Coordinated + All Phases

"@ -ForegroundColor Green

# List output files
Write-Host "Output files:" -ForegroundColor Cyan
Get-ChildItem $OutputDir -Filter "demo_${Timestamp}_*" | ForEach-Object {
    Write-Host "  $($_.Name) ($(($_.Length / 1KB).ToString('F1')) KB)" -ForegroundColor Gray
}
