# Issue 008: Formatter module exists but is not used by editing operations

**Severity:** MEDIUM
**Files:**
- `src/document/formatter/font.py` — FontFormatter
- `src/document/formatter/paragraph.py` — ParagraphFormatter
- `src/document/formatter/table.py` — TableFormatter
- `src/document/structure/operations.py` — editing operations

**Status:** NOT FIXED (design integration)

## Description
The `src/document/formatter/` module contains well-implemented `FontFormatter`,
`ParagraphFormatter`, and `TableFormatter` classes, but they work with python-docx
`Run` and `Paragraph` objects — not raw XML elements. The editing operations in
`operations.py` work at the `OxmlElement` level (direct body XML manipulation) and
never use the formatters.

## Impact
- Formatting applied via `FontFormatter.format()` or `ParagraphFormatter.format()`
  is lost when operations rebuild the tree via `_rebuild_tree_inplace()`.
- There are two parallel formatting systems that don't communicate:
  1. XML-level (`_make_paragraph_xml`, `_make_heading_xml`) — used by operations
  2. python-docx-level (`FontFormatter`, `ParagraphFormatter`) — standalone

## Recommendation
- Either port the formatters to work at the XML level, or create an adapter layer
  that the operations can call.
- Consider merging `FontFormatter` logic into `_make_rpr_for_text()`.
