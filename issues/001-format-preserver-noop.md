# Issue 001: FormatPreserver.apply_captured_styles() is a no-op

**Severity:** CRITICAL
**File:** `src/document/styles/manager.py:73-93`
**Status:** FIXED

## Description
`FormatPreserver.apply_captured_styles()` logged a message but never actually applied
any styles to the target document. The method was defined but contained no code to
transfer font/paragraph properties from the captured style cache to the target doc.

## Root Cause
The `FormatPreserver` class was added as a design placeholder. `capture_styles()` worked
(calling `StyleAnalyzer.analyze()` which returned style data), but `apply_captured_styles()`
was never implemented — it only logged "Applying captured styles" and returned.

Additionally, `StyleAnalyzer` only extracted style *names*, not font/paragraph *properties*,
so even a naive implementation would have had insufficient data.

## Fix
- Enhanced `StyleAnalyzer._extract_style_properties()` to read full font/paragraph properties
  from styles.xml: font name, size, bold, italic, color, alignment, spacing, indentation.
- Updated `_get_paragraph_styles()` and `_get_character_styles()` to return full properties.
- Updated `_get_default_font()` and `_get_default_paragraph()` to actually read from the
  document's `w:rPrDefault` and `w:pPrDefault` instead of returning hardcoded values.
- Implemented `FormatPreserver.apply_captured_styles()` to copy default font to Normal style
  and apply each paragraph/character style's properties to the target document's styles.
- Added `FormatPreserver.get_default_font()` and `get_heading_font()` utility methods.

## Verification
All 166 tests pass. The `FormatPreserver` is now usable by editing operations.
