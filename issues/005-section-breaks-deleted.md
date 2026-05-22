# Issue 005: Section breaks deleted during section removal

**Severity:** HIGH
**File:** `src/document/structure/operations.py:501-503`
**Status:** FIXED

## Description
`DeleteSection` (full delete mode) removed ALL body children in the section's range,
including `<w:sectPr>` elements. This destroyed page layout boundaries (margins,
headers, footers, page numbering) for the document, merging the remaining sections'
layouts unpredictably.

## Root Cause
The element removal loop iterated over the range `[s_range[0], s_range[1])` and
appended every element unconditionally. No check was made for section break properties.

## Fix
- Added `_is_section_break()` helper that detects:
  - Standalone `<w:sectPr>` elements (direct body children).
  - `<w:p>` elements whose `<w:pPr>` contains a `<w:sectPr>` child.
- Updated `DeleteSection` full delete loop to skip section break elements.
- Updated `ReplaceSection` and `DeleteSection.delete_children_only` loops to also
  skip section break elements.

## Verification
All 166 tests pass. Section breaks are preserved during deletions and replacements,
maintaining document layout boundaries.
