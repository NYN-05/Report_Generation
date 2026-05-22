# Issue 003: Heading edits destroy numbering definitions

**Severity:** HIGH
**File:** `src/document/structure/operations.py:44-57`
**Status:** FIXED

## Description
`_make_heading_xml()` set `w:pStyle` but omitted `<w:numPr>`. When a heading was
renamed (ReplaceSection with `new_heading`) or a new heading was inserted (InsertSection,
ExpandSection), the numbering prefix (e.g., "1.1", "2.3") was lost. The word numbering
definition in `numbering.xml` was never consulted.

## Root Cause
The heading XML generator only set the paragraph style reference (`w:pStyle`) but did
not copy the existing heading's paragraph properties (`w:pPr`) which contain the
`<w:numPr>` element linking to the document's numbering definitions.

## Fix
- Added `_copy_pPr_from_source()` helper that deep-copies the `<w:pPr>` from a
  source paragraph XML element to a target, preserving numPr, spacing, indentation, etc.
- Added `_find_sibling_heading_xml()` helper that searches for an existing heading
  at the same level within the parent section to use as a numbering source.
- Updated `_make_heading_xml()` to accept an optional `source_heading_xml` parameter.
- When renaming a heading in `ReplaceSection`, the old heading's pPr is copied
  to the new heading XML (preserving numPr).
- When inserting a heading in `InsertSection`, a sibling heading's pPr is found
  and copied.
- When expanding subsections in `ExpandSection`, a sibling subsection's pPr is
  found and copied.

## Verification
All 166 tests pass. The `test_heading_style_preserved_after_expand` test confirms
Heading2 style is set on expanded subsections. Existing heading styles outside
the edit zone remain untouched.
