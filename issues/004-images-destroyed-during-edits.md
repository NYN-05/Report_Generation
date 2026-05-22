# Issue 004: Images destroyed during section edits

**Severity:** HIGH
**File:** `src/document/structure/operations.py:227, 482`
**Status:** FIXED

## Description
During ReplaceSection and DeleteSection (delete_children_only), only `<w:tbl>` elements
were protected from removal. Images (represented as `<w:drawing>` inside `<w:p>`) were
deleted when their containing section was edited, because the filter only checked for
table elements.

## Root Cause
The `preserve_children` and `delete_children_only` flags only checked `_tag(elem) == 'tbl'`.
Images in DOCX are inline drawings inside `<w:r><w:drawing>` within `<w:p>` elements,
so they were not recognized as protected content.

## Fix
- Added `_contains_image()` helper that checks if an XML element contains any
  descendant `<w:drawing>` element.
- Updated `ReplaceSection` element removal loop to skip elements containing images
  when `preserve_children=True`.
- Updated `DeleteSection.delete_children_only` element removal loop to skip elements
  containing images.

## Verification
All 166 tests pass. Tables (previously the only protected type) continue to be
preserved, and images are now also protected.
