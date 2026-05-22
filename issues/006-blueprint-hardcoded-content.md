# Issue 006: Blueprint system has disguised hardcoded content

**Severity:** MEDIUM
**Files:**
- `src/document/blueprint/planner.py:117` — Only engineering_project has chapter templates
- `src/document/blueprint/planner.py:175-196` — Certificate/declaration content hardcoded
- `src/document/blueprint/builder.py:140-143` — LOF/LOT are placeholder text
- `src/document/blueprint/planner.py:204` — References are fabricated

**Status:** NOT FIXED (requires LLM integration or template-based content generation)

## Description
Despite having a dynamic blueprint system, much of the generated content is hardcoded:

1. **Chapter templates** only exist for `engineering_project`. Research paper and
   internship report blueprints have `default_chapter_count: 0` and produce no chapters.

2. **Certificate/declaration** text is the same for every project (only topic differs).

3. **LOF/LOT** (List of Figures / List of Tables) insert placeholder text like
   "Figure 1: [Figure description]" instead of using actual figure/table captions.

4. **References** are fabricated as `[1] Author, "Title," Journal, Year.` — 10 fake
   entries every time.

## Recommendation
- Replace hardcoded fallback with LLM-generated content when `use_llm=True`.
- For `use_llm=False`, load templates from catalog JSON or external files.
- Implement actual figure/table tracking to populate LOF/LOT dynamically.
