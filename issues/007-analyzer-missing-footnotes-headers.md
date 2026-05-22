# Issue 007: Deep DOCX analysis missing footnotes, headers, cross-references

**Severity:** MEDIUM
**File:** `src/document/analyzer/` (all modules)

**Status:** NOT FIXED (scope addition)

## Description
The DOCX analyzer (scored 8/10) is comprehensive but misses several features that
would be needed for full document understanding:

| Missing Feature | File | Priority |
|---|---|---|
| Footnote detection | ℹ Not implemented | MEDIUM |
| Endnote detection | ℹ Not implemented | LOW |
| Header/footer extraction | ℹ Not implemented | MEDIUM |
| Comment detection | ℹ Not implemented | LOW |
| Watermark detection | ℹ Not implemented | LOW |
| Equation detection | ℹ Not implemented | LOW |
| Cross-reference detection | ℹ Not implemented | MEDIUM |

Additionally, `images.py` caption attachment uses a reversed-paragraph heuristic
that can mis-assign captions, and `references.py` parsing is minimal (single-regex).

## Recommendation
- Add footnote/endnote detection by parsing `footnotes.xml` and `endnotes.xml`.
- Add header/footer extraction from `header*.xml` and `footer*.xml`.
- Add cross-reference detection by analyzing `w:instrText` for REF fields.
- Improve caption attachment with distance-based scoring.
