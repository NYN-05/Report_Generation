"""Tests for the Report Writing Rules System."""

import os
import json
import tempfile
import pytest

from src.document.rules import (
    ReportRules, SectionRule, GlobalRules, RuleValidationResult,
    RulesLoader, RulesEngine,
)
from src.document.blueprint import (
    Blueprint, BlueprintSection, AIReportPlanner,
)


# =============================================================================
# Models
# =============================================================================

class TestGlobalRules:
    def test_defaults(self):
        g = GlobalRules()
        assert g.min_paragraphs_per_section == 5
        assert g.min_words_per_paragraph == 80
        assert g.require_data_points is True

    def test_to_dict_roundtrip(self):
        g = GlobalRules(min_paragraphs_per_section=7)
        d = g.to_dict()
        g2 = GlobalRules.from_dict(d)
        assert g2.min_paragraphs_per_section == 7

    def test_unknown_fields_ignored(self):
        g = GlobalRules.from_dict({"min_paragraphs_per_section": 6, "unknown": "x"})
        assert g.min_paragraphs_per_section == 6


class TestSectionRule:
    def test_defaults(self):
        r = SectionRule()
        assert r.min_paragraphs == 5
        assert r.structure == []

    def test_custom_structure(self):
        r = SectionRule(structure=["a", "b", "c"], require_references=8)
        assert len(r.structure) == 3
        assert r.require_references == 8

    def test_to_dict_roundtrip(self):
        r = SectionRule(min_paragraphs=8, min_words=900, require_references=5)
        d = r.to_dict()
        r2 = SectionRule.from_dict(d)
        assert r2.min_paragraphs == 8
        assert r2.min_words == 900
        assert r2.require_references == 5


class TestReportRules:
    def test_defaults(self):
        rules = ReportRules()
        assert rules.rules_version == "1.0"
        assert isinstance(rules.global_, GlobalRules)

    def test_get_rule_without_override(self):
        rules = ReportRules(
            global_=GlobalRules(min_paragraphs_per_section=6)
        )
        rule = rules.get_rule("nonexistent")
        assert rule.min_paragraphs == 6

    def test_get_rule_with_override(self):
        rules = ReportRules(
            global_=GlobalRules(min_paragraphs_per_section=5),
            section_types={
                "introduction": SectionRule(min_paragraphs=8, structure=["background", "objectives"]),
            }
        )
        rule = rules.get_rule("introduction")
        assert rule.min_paragraphs == 8
        assert "background" in rule.structure

    def test_get_rule_merges_global_and_specific(self):
        rules = ReportRules(
            global_=GlobalRules(min_paragraphs_per_section=5, require_data_points=True),
            section_types={
                "introduction": SectionRule(min_paragraphs=8),
            }
        )
        rule = rules.get_rule("introduction")
        assert rule.min_paragraphs == 8
        assert rule.require_data_points is True

    def test_to_dict_roundtrip(self):
        rules = ReportRules(
            rules_version="2.0",
            global_=GlobalRules(min_paragraphs_per_section=7),
            section_types={"test": SectionRule(min_paragraphs=10)},
        )
        d = rules.to_dict()
        r2 = ReportRules.from_dict(d)
        assert r2.rules_version == "2.0"
        assert r2.global_.min_paragraphs_per_section == 7
        assert r2.section_types["test"].min_paragraphs == 10

    def test_from_dict_full(self):
        data = {
            "rules_version": "1.1",
            "global": {"min_paragraphs_per_section": 6},
            "section_types": {
                "introduction": {"min_paragraphs": 7, "min_words": 800, "structure": ["a"]},
            },
            "metadata": {"name": "custom"},
        }
        rules = ReportRules.from_dict(data)
        assert rules.rules_version == "1.1"
        assert rules.global_.min_paragraphs_per_section == 6
        assert rules.section_types["introduction"].min_paragraphs == 7
        assert rules.metadata["name"] == "custom"


class TestRuleValidationResult:
    def test_passed_true_when_no_errors(self):
        r = RuleValidationResult()
        assert r.passed is True

    def test_passed_false_when_errors(self):
        r = RuleValidationResult(errors=["too few paragraphs"])
        assert r.passed is False


# =============================================================================
# Loader
# =============================================================================

SAMPLE_JSON = json.dumps({
    "rules_version": "1.0",
    "global": {"min_paragraphs_per_section": 5, "min_words_per_section": 600},
    "section_types": {
        "introduction": {"min_paragraphs": 6, "structure": ["background", "objectives"]},
    },
    "metadata": {"name": "test"},
})

SAMPLE_MD = """# Report Writing Rules

## Global Rules
- Each section must have at least 5 paragraphs
- Each section must have at least 600 words
- Include data points and statistics

## Section-Specific Rules

### Introduction
- Minimum 6 paragraphs
- Must cover: background, problem statement, objectives
- Must include at least 3 statistics
- Minimum 700 words

### Conclusion
- Minimum 4 paragraphs
- Must cover: summary, contributions, future work
"""


class TestRulesLoader:
    def test_load_json_from_path(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(SAMPLE_JSON)
            f.flush()
            path = f.name
        try:
            loader = RulesLoader()
            rules = loader.load_json(path)
            assert rules.section_types["introduction"].min_paragraphs == 6
            assert rules.global_.min_paragraphs_per_section == 5
        finally:
            os.unlink(path)

    def test_load_markdown(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(SAMPLE_MD)
            f.flush()
            path = f.name
        try:
            loader = RulesLoader()
            rules = loader.load_markdown(path)
            intro = rules.section_types.get("introduction")
            assert intro is not None, f"introduction not found in {list(rules.section_types.keys())}"
            assert intro.min_paragraphs == 6
            assert len(intro.structure) >= 2
        finally:
            os.unlink(path)

    def test_load_auto_json_by_ext(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(SAMPLE_JSON)
            f.flush()
            path = f.name
        try:
            loader = RulesLoader()
            rules = loader.load(path)
            assert rules.section_types["introduction"].min_paragraphs == 6
        finally:
            os.unlink(path)

    def test_load_auto_md_by_ext(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(SAMPLE_MD)
            f.flush()
            path = f.name
        try:
            loader = RulesLoader()
            rules = loader.load(path)
            assert rules.section_types["introduction"].min_paragraphs == 6
        finally:
            os.unlink(path)

    def test_parse_rules_text_json(self):
        loader = RulesLoader()
        rules = loader.parse_rules_text(SAMPLE_JSON, fmt="json")
        assert rules.section_types["introduction"].min_paragraphs == 6

    def test_parse_rules_text_auto_json(self):
        loader = RulesLoader()
        rules = loader.parse_rules_text(SAMPLE_JSON)
        assert rules.section_types["introduction"].min_paragraphs == 6

    def test_parse_rules_text_markdown(self):
        loader = RulesLoader()
        rules = loader.parse_rules_text(SAMPLE_MD, fmt="md")
        intro = rules.section_types.get("introduction")
        assert intro is not None
        assert intro.min_paragraphs == 6

    def test_load_nonexistent_file(self):
        loader = RulesLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_json("nonexistent.json")

    def test_load_unsupported_format(self):
        loader = RulesLoader()
        with pytest.raises(ValueError, match="Unsupported"):
            loader.load("rules.txt")

    def test_load_default(self):
        loader = RulesLoader()
        rules = loader.load_default()
        assert isinstance(rules, ReportRules)
        assert rules.section_types["introduction"].min_paragraphs >= 5

    def test_default_rules_json_exists(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src", "document", "rules", "default_rules.json")
        assert os.path.exists(path), f"default_rules.json not found at {path}"

    def test_default_rules_md_exists(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src", "document", "rules", "report_rules.md")
        assert os.path.exists(path), f"report_rules.md not found at {path}"


# =============================================================================
# Engine
# =============================================================================

class TestRulesEngine:
    def test_default_engine_loads(self):
        engine = RulesEngine()
        assert isinstance(engine.rules, ReportRules)

    def test_determine_section_type_introduction(self):
        engine = RulesEngine()
        assert engine.determine_section_type("1. Introduction") == "introduction"

    def test_determine_section_type_literature(self):
        engine = RulesEngine()
        assert engine.determine_section_type("Literature Review") == "literature_review"

    def test_determine_section_type_methodology(self):
        engine = RulesEngine()
        assert engine.determine_section_type("Methodology and Approach") == "methodology"

    def test_determine_section_type_results(self):
        engine = RulesEngine()
        assert engine.determine_section_type("Experimental Results") == "results"

    def test_determine_section_type_discussion(self):
        engine = RulesEngine()
        assert engine.determine_section_type("Discussion of Findings") == "discussion"

    def test_determine_section_type_conclusion(self):
        engine = RulesEngine()
        assert engine.determine_section_type("Conclusion and Future Work") == "conclusion"

    def test_determine_section_type_references(self):
        engine = RulesEngine()
        assert engine.determine_section_type("References") == "references"

    def test_determine_section_type_unknown_falls_back_to_chapters(self):
        engine = RulesEngine()
        assert engine.determine_section_type("Some Random Heading") == "chapters"

    def test_determine_section_type_with_blueprint_id(self):
        engine = RulesEngine()
        assert engine.determine_section_type("Anything", blueprint_section_id="introduction") == "introduction"

    def test_generate_section_content_is_substantial(self):
        engine = RulesEngine()
        content = engine.generate_section_content(
            topic="Renewable Energy",
            heading="1. Introduction",
            blueprint_section_id="introduction",
        )
        word_count = len(content.split())
        para_count = len([p for p in content.split("\n\n") if p.strip()])
        assert word_count >= 600, f"Only {word_count} words, expected >= 600"
        assert para_count >= 5, f"Only {para_count} paragraphs, expected >= 5"

    def test_generate_section_content_introduction_has_data_points(self):
        engine = RulesEngine()
        content = engine.generate_section_content(
            topic="Artificial Intelligence",
            heading="Introduction",
            blueprint_section_id="introduction",
        )
        assert any(c.isdigit() for c in content), "Content should contain numbers/data points"

    def test_generate_section_content_chapters(self):
        engine = RulesEngine()
        content = engine.generate_section_content(
            topic="Machine Learning",
            heading="3. Methodology",
            blueprint_section_id="chapters",
        )
        word_count = len(content.split())
        assert word_count >= 400, f"Chapter content too short: {word_count} words"

    def test_generate_subsections(self):
        engine = RulesEngine()
        subs = engine.generate_subsections(
            topic="Data Science",
            section_heading="3. Methodology",
            blueprint_section_id="chapters",
            count=3,
        )
        assert len(subs) >= 3
        for heading, content, level in subs:
            assert isinstance(heading, str) and len(heading) > 0
            assert isinstance(content, str) and len(content) > 50
            assert level == 2

    def test_generate_subsections_numbered(self):
        engine = RulesEngine()
        subs = engine.generate_subsections(
            topic="Cybersecurity",
            section_heading="1. Introduction",
            count=3,
        )
        assert len(subs) >= 3
        first_heading = subs[0][0]
        assert "1.1" in first_heading or any(c.isdigit() for c in first_heading)

    def test_validate_content_short_content_fails(self):
        engine = RulesEngine()
        result = engine.validate_content(
            content="Short content.",
            heading="Conclusion",
            blueprint_section_id="conclusion",
        )
        assert not result.passed
        assert len(result.errors) > 0

    def test_validate_content_rich_content_passes(self):
        engine = RulesEngine()
        content = engine.generate_section_content(
            topic="Quantum Computing",
            heading="Conclusion and Future Work",
            blueprint_section_id="conclusion",
        )
        result = engine.validate_content(
            content=content,
            heading="Conclusion and Future Work",
            blueprint_section_id="conclusion",
        )
        assert result.meets_min_paragraphs, f"Only {result.paragraphs} paragraphs, errors: {result.errors}"
        assert result.has_data_points, "Missing data points"
        assert result.word_count >= 300, f"Only {result.word_count} words"

    def test_load_custom_rules(self):
        engine = RulesEngine()
        custom = json.dumps({
            "rules_version": "1.0",
            "global": {"min_paragraphs_per_section": 10, "min_words_per_section": 1000},
            "section_types": {},
        })
        engine.load_custom_rules(custom)
        assert engine.rules.global_.min_paragraphs_per_section == 10

    def test_load_custom_markdown(self):
        engine = RulesEngine()
        engine.load_custom_markdown(SAMPLE_MD)
        intro = engine.rules.section_types.get("introduction")
        assert intro is not None
        assert intro.min_paragraphs == 6

    def test_reload(self):
        engine = RulesEngine()
        original = engine.rules.global_.min_paragraphs_per_section
        engine.reload()
        assert engine.rules.global_.min_paragraphs_per_section == original

    def test_generate_section_different_topics_different_content(self):
        engine = RulesEngine()
        c1 = engine.generate_section_content(topic="Biology", heading="Introduction")
        c2 = engine.generate_section_content(topic="Physics", heading="Introduction")
        assert c1 != c2


# =============================================================================
# Integration: RulesEngine + AIReportPlanner
# =============================================================================

@pytest.fixture
def eng_blueprint():
    return Blueprint(
        id="engineering_project",
        name="Engineering Project Report",
        description="Test blueprint",
        sections=[
            BlueprintSection(id="cover_page", heading="Cover Page", mandatory=True),
            BlueprintSection(id="table_of_contents", heading="Table of Contents", mandatory=True),
            BlueprintSection(id="abstract", heading="Abstract", mandatory=True),
            BlueprintSection(id="chapters", heading="Chapters", level=1, mandatory=True,
                             subsections=[]),
            BlueprintSection(id="references", heading="References", mandatory=True),
        ],
        default_chapter_count=4,
    )


class TestRulesIntegrationWithPlanner:
    def test_planner_with_rules_generates_rich_chapters(self, eng_blueprint):
        engine = RulesEngine()
        planner = AIReportPlanner(rules_engine=engine)
        plan = planner._plan_fallback(
            topic="Renewable Energy",
            blueprint=eng_blueprint,
            title="Analysis of Renewable Energy Systems",
        )
        chapter_sections = [s for s in plan.sections if s.blueprint_section_id == "chapters"]
        assert len(chapter_sections) > 0
        for ch in chapter_sections:
            words = len(ch.content.split())
            assert words >= 300, f"Chapter '{ch.heading}' too short: {words} words"
            assert len(ch.subsections) >= 2, f"Chapter '{ch.heading}' has too few subsections"
            for sub in ch.subsections:
                sub_words = len(sub.content.split())
                assert sub_words >= 80, f"Subsection '{sub.heading}' too short: {sub_words} words"

    def test_planner_with_rules_generates_rich_abstract(self, eng_blueprint):
        engine = RulesEngine()
        planner = AIReportPlanner(rules_engine=engine)
        plan = planner._plan_fallback(
            topic="Artificial Intelligence",
            blueprint=eng_blueprint,
            title="AI in Healthcare",
        )
        abstract = next((s for s in plan.sections if s.blueprint_section_id == "abstract"), None)
        assert abstract is not None
        words = len(abstract.content.split())
        assert words >= 200, f"Abstract too short: {words} words"

    def test_planner_content_vs_old_style(self, eng_blueprint):
        """Verify that content with rules is substantially longer than old placeholder style."""
        engine = RulesEngine()
        planner = AIReportPlanner(rules_engine=engine)
        plan = planner._plan_fallback(
            topic="Machine Learning",
            blueprint=eng_blueprint,
            title="ML Survey",
        )
        all_content = " ".join(s.content for s in plan.sections if s.content)
        total_words = len(all_content.split())
        assert total_words >= 3000, f"Total content only {total_words} words, expected much more"


# =============================================================================
# End-to-end: Rules file → Engine → Content generation
# =============================================================================

class TestRulesEndToEnd:
    def test_json_rules_to_content(self):
        custom_rules = {
            "rules_version": "1.0",
            "global": {"min_paragraphs_per_section": 7, "min_words_per_section": 800},
            "section_types": {
                "introduction": {"min_paragraphs": 8, "structure": ["background", "problem", "objectives", "scope", "methodology", "outline", "significance", "roadmap"]},
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(custom_rules, f)
            path = f.name
        try:
            engine = RulesEngine(rules_path=path)
            content = engine.generate_section_content(
                topic="Blockchain Technology",
                heading="1. Introduction",
                blueprint_section_id="introduction",
            )
            words = len(content.split())
            paras = len([p for p in content.split("\n\n") if p.strip()])
            assert paras >= 7, f"Only {paras} paragraphs, expected >= 7"
            assert words >= 800, f"Only {words} words, expected >= 800"
        finally:
            os.unlink(path)

    def test_md_rules_to_content(self):
        md_rules = """# Custom Rules

## Global Rules
- Each section must have at least 6 paragraphs
- Each section must have at least 500 words
- Include data points and examples

## Section-Specific Rules

### Introduction
- Minimum 5 paragraphs
- Must cover: background, objectives, scope
- Minimum 500 words
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(md_rules)
            path = f.name
        try:
            engine = RulesEngine(rules_path=path)
            content = engine.generate_section_content(
                topic="Cloud Computing",
                heading="Introduction",
                blueprint_section_id="introduction",
            )
            words = len(content.split())
            assert words >= 450, f"Only {words} words with MD rules — expected >= 450"
        finally:
            os.unlink(path)


# =============================================================================
# Tests for LLM planning path (use_llm=True)
# =============================================================================

class FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content


class FakeProvider:
    def __init__(self, available=True, response_text="", fail=False):
        self._available = available
        self._response_text = response_text
        self._fail = fail
        self.last_messages = None
        self.last_options = None

    def is_available(self):
        return self._available

    def chat(self, messages, options=None):
        self.last_messages = messages
        self.last_options = options
        if self._fail:
            raise RuntimeError("Provider failure")
        return FakeLLMResponse(self._response_text)

    def generate(self, prompt, options=None):
        return FakeLLMResponse("")


SAMPLE_LLM_STRUCTURE = json.dumps({
    "sections": [
        {
            "blueprint_section_id": "chapters",
            "heading": "1. Introduction",
            "allocated_pages": 4,
            "level": 1,
            "subsections": [
                {"heading": "1.1 Background", "level": 2},
                {"heading": "1.2 Problem Statement", "level": 2},
            ],
            "requires_figure": False,
            "requires_table": False,
        },
        {
            "blueprint_section_id": "chapters",
            "heading": "2. Literature Review",
            "allocated_pages": 5,
            "level": 1,
            "subsections": [
                {"heading": "2.1 Theoretical Framework", "level": 2},
                {"heading": "2.2 Related Work", "level": 2},
            ],
            "requires_figure": True,
            "figure_description": "Research methodology flowchart",
            "requires_table": True,
            "table_headers": ["Study", "Method", "Result"],
        },
    ]
})


TEST_BP = lambda: Blueprint(
    id="engineering_project", name="Test BP", description="Test",
    sections=[BlueprintSection(id="chapters", heading="Chapters", level=1)],
)


class TestLlmPlanningPath:
    def test_llm_unavailable_falls_back(self):
        provider = FakeProvider(available=False)
        planner = AIReportPlanner(provider=provider)
        plan = planner._plan_with_llm(
            topic="Test", blueprint=TEST_BP(),
            title="Test", author="", date="",
        )
        assert plan is not None
        assert plan.blueprint_id == "engineering_project"

    def test_llm_failure_falls_back(self):
        provider = FakeProvider(available=True, fail=True)
        planner = AIReportPlanner(provider=provider)
        plan = planner._plan_with_llm(
            topic="Test", blueprint=TEST_BP(),
            title="Test", author="", date="",
        )
        assert plan is not None
        assert plan.blueprint_id == "engineering_project"

    def test_llm_empty_response_falls_back(self):
        provider = FakeProvider(available=True, response_text="{}")
        planner = AIReportPlanner(provider=provider)
        plan = planner._plan_with_llm(
            topic="Test", blueprint=TEST_BP(),
            title="Test", author="", date="",
        )
        assert plan is not None
        assert plan.blueprint_id == "engineering_project"

    def test_llm_parse_bare_json(self):
        planner = AIReportPlanner()
        result = planner._extract_json('{"sections": [{"heading": "Test"}]}')
        assert result is not None
        assert result["sections"][0]["heading"] == "Test"

    def test_llm_parse_markdown_fenced(self):
        planner = AIReportPlanner()
        result = planner._extract_json('```json\n{"sections": [{"heading": "Test"}]}\n```')
        assert result is not None
        assert result["sections"][0]["heading"] == "Test"

    def test_llm_parse_single_quotes(self):
        planner = AIReportPlanner()
        result = planner._extract_json("{'sections': [{'heading': 'Test'}]}")
        assert result is not None
        assert result["sections"][0]["heading"] == "Test"

    def test_llm_parse_trailing_commas(self):
        planner = AIReportPlanner()
        result = planner._extract_json('{"sections": [{"heading": "Test",}],}')
        assert result is not None
        assert result["sections"][0]["heading"] == "Test"

    def test_llm_parse_js_comments(self):
        planner = AIReportPlanner()
        result = planner._extract_json(
            '{"sections": [{"heading": "Test"}]} // end comment'
        )
        assert result is not None
        assert result["sections"][0]["heading"] == "Test"

    def test_llm_plan_with_valid_structure(self, eng_blueprint):
        provider = FakeProvider(available=True, response_text=SAMPLE_LLM_STRUCTURE)
        planner = AIReportPlanner(provider=provider)
        plan = planner._plan_with_llm(
            topic="Quantum Computing",
            blueprint=eng_blueprint,
            title="Quantum Computing Survey",
            author="Dr. Smith",
            date="2026",
        )
        assert plan is not None
        assert len(plan.sections) == 2
        intro = plan.sections[0]
        assert "Introduction" in intro.heading
        assert len(intro.content.split()) >= 300
        assert len(intro.subsections) >= 2
        assert intro.requires_figure is False

        lit_review = plan.sections[1]
        assert "Literature" in lit_review.heading
        assert lit_review.requires_figure is True
        assert lit_review.figure_description == "Research methodology flowchart"
        assert lit_review.requires_table is True

    def test_llm_plan_passes_options(self):
        provider = FakeProvider(available=True, response_text=SAMPLE_LLM_STRUCTURE)
        planner = AIReportPlanner(provider=provider)
        planner._plan_with_llm(
            topic="AI", blueprint=TEST_BP(),
            title="AI", author="", date="",
        )
        assert provider.last_options is not None
        assert provider.last_options.temperature == 0.3
        assert provider.last_options.max_tokens == 4096
        assert provider.last_options.timeout == 60
