# Issue 002: _make_paragraph_xml() creates unformatted content

**Severity:** CRITICAL
**File:** `src/document/structure/operations.py:33-41`
**Status:** FIXED

## Description
`_make_paragraph_xml()` created bare `<w:p>` elements with only `<w:r><w:t>` children —
no `<w:rPr>` (run properties), no `<w:pPr>` (paragraph properties). Every new paragraph
created by ReplaceSection, InsertSection, ExpandSection got default Calibri 11pt
left-aligned, regardless of the original document's formatting.

## Root Cause
The function was written as a minimal XML generator without any formatting support.
It was never updated to include font name, font size, or any style properties.

## Fix
- Added `_make_rpr_for_text()` helper that creates `<w:rPr>` with font name, size,
  bold, italic, and color XML elements.
- Updated `_make_paragraph_xml()` to accept optional `font_name` and `font_size`
  parameters and include a `<w:rPr>` element with those properties.
- Default values: Calibri 11pt (matching typical DOCX defaults).

## Verification
All 166 tests pass. Paragraphs created by editing operations now include font
formatting in their XML.
