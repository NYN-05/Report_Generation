# Issue 009: FormatPreserver is never instantiated or used in the pipeline

**Severity:** MEDIUM
**Files:**
- `src/document/styles/manager.py` — FormatPreserver
- `src/pipeline/generation/template.py` — TemplatePipeline

**Status:** NOT FIXED (design integration)

## Description
The `FormatPreserver` class is now implemented (see Issue 001), but it is never
instantiated or called anywhere in the codebase. It remains a standalone utility
class. The `TemplatePipeline` does not capture or apply styles before/after
structural edits.

## Impact
- Even though `_make_paragraph_xml` now creates formatted XML with font properties,
  the formatting is based on hardcoded defaults (Calibri 11pt), not the actual
  document's styles.
- To get document-specific formatting, the pipeline would need to:
  1. Capture styles from the source template before editing (`FormatPreserver.capture_styles`)
  2. Pass style info to operations
  3. Apply styles to the target after editing (`FormatPreserver.apply_captured_styles`)

## Recommendation
- Integrate `FormatPreserver` into `TemplatePipeline._apply_structural_edits()`:
  capture styles before editing, pass default font info to operations, re-apply
  styles after editing.
