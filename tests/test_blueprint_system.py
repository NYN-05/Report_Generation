"""Tests for the Dynamic Academic Report Blueprint System."""

import os
import json
import tempfile
import pytest
from pathlib import Path


class TestBlueprintModels:
    def test_blueprint_section_defaults(self):
        from src.document.blueprint import BlueprintSection
        bs = BlueprintSection(id="test", heading="Test Section")
        assert bs.id == "test"
        assert bs.heading == "Test Section"
        assert bs.level == 1
        assert bs.mandatory is True
        assert bs.subsections == []

    def test_blueprint_section_to_dict(self):
        from src.document.blueprint import BlueprintSection
        bs = BlueprintSection(id="intro", heading="Introduction", level=1)
        d = bs.to_dict()
        assert d["id"] == "intro"
        assert d["heading"] == "Introduction"
        assert d["level"] == 1
        assert d["subsections"] == []

    def test_blueprint_section_from_dict(self):
        from src.document.blueprint import BlueprintSection
        data = {
            "id": "test", "heading": "Test", "level": 2,
            "mandatory": False, "subsections": [
                {"id": "sub", "heading": "Sub", "level": 3}
            ]
        }
        bs = BlueprintSection.from_dict(data)
        assert bs.id == "test"
        assert bs.level == 2
        assert bs.mandatory is False
        assert len(bs.subsections) == 1
        assert bs.subsections[0].id == "sub"

    def test_blueprint_to_dict(self):
        from src.document.blueprint import Blueprint
        bp = Blueprint(id="eng", name="Engineering", description="Test")
        d = bp.to_dict()
        assert d["id"] == "eng"
        assert d["name"] == "Engineering"
        assert d["sections"] == []

    def test_blueprint_from_dict(self):
        from src.document.blueprint import Blueprint
        data = {
            "id": "test", "name": "Test BP", "description": "Desc",
            "sections": [
                {"id": "s1", "heading": "S1", "level": 1}
            ],
        }
        bp = Blueprint.from_dict(data)
        assert bp.id == "test"
        assert len(bp.sections) == 1
        assert bp.sections[0].heading == "S1"

    def test_plan_section_defaults(self):
        from src.document.blueprint import PlanSection
        ps = PlanSection(blueprint_section_id="intro", heading="Introduction")
        assert ps.blueprint_section_id == "intro"
        assert ps.level == 1
        assert ps.content == ""
        assert ps.subsections == []

    def test_report_plan_to_dict(self):
        from src.document.blueprint import ReportPlan, PlanSection
        plan = ReportPlan(
            blueprint_id="eng", blueprint_name="Engineering",
            title="Test", sections=[
                PlanSection(blueprint_section_id="intro", heading="Introduction"),
            ]
        )
        d = plan.to_dict()
        assert d["blueprint_id"] == "eng"
        assert d["title"] == "Test"
        assert d["section_count"] == 1


class TestBlueprintLoader:
    def test_load_engineering_blueprint(self):
        from src.document.blueprint import BlueprintLoader
        loader = BlueprintLoader()
        bp = loader.load("engineering_project")
        assert bp is not None
        assert bp.id == "engineering_project"
        assert bp.name == "Engineering Project Report"
        assert len(bp.sections) > 0

    def test_load_research_blueprint(self):
        from src.document.blueprint import BlueprintLoader
        loader = BlueprintLoader()
        bp = loader.load("research_paper")
        assert bp is not None
        assert bp.id == "research_paper"
        assert len(bp.sections) > 0

    def test_load_internship_blueprint(self):
        from src.document.blueprint import BlueprintLoader
        loader = BlueprintLoader()
        bp = loader.load("internship_report")
        assert bp is not None
        assert bp.id == "internship_report"
        assert len(bp.sections) > 0

    def test_load_nonexistent_blueprint(self):
        from src.document.blueprint import BlueprintLoader
        loader = BlueprintLoader()
        bp = loader.load("nonexistent_blueprint_xyz")
        assert bp is None

    def test_load_all_blueprints(self):
        from src.document.blueprint import BlueprintLoader
        loader = BlueprintLoader()
        all_bp = loader.load_all()
        assert len(all_bp) >= 3
        assert "engineering_project" in all_bp
        assert "research_paper" in all_bp
        assert "internship_report" in all_bp

    def test_load_custom_blueprint(self):
        from src.document.blueprint import BlueprintLoader
        custom_data = {
            "id": "custom_test",
            "name": "Custom Test Blueprint",
            "description": "A test blueprint",
            "sections": [
                {"id": "intro", "heading": "Introduction", "level": 1}
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False, encoding="utf-8") as f:
            json.dump(custom_data, f)
            tmp_path = f.name

        try:
            loader = BlueprintLoader()
            bp = loader.load_custom(tmp_path)
            assert bp is not None
            assert bp.id == "custom_test"
            assert bp.name == "Custom Test Blueprint"
            assert len(bp.sections) == 1
        finally:
            os.unlink(tmp_path)

    def test_get_available(self):
        from src.document.blueprint import BlueprintLoader
        loader = BlueprintLoader()
        available = loader.get_available()
        assert len(available) >= 3
        assert "Engineering Project Report" in available.values()


class TestBlueprintSelector:
    def test_select_engineering(self):
        from src.document.blueprint import BlueprintSelector
        selector = BlueprintSelector()
        bp = selector.select("Generate Final Year Project Report")
        assert bp is not None
        assert bp.id == "engineering_project"

    def test_select_research(self):
        from src.document.blueprint import BlueprintSelector
        selector = BlueprintSelector()
        bp = selector.select("Write a research paper on AI")
        assert bp is not None
        assert bp.id == "research_paper"

    def test_select_internship(self):
        from src.document.blueprint import BlueprintSelector
        selector = BlueprintSelector()
        bp = selector.select("Internship report at tech company")
        assert bp is not None
        assert bp.id == "internship_report"

    def test_select_with_fallback(self):
        from src.document.blueprint import BlueprintSelector
        selector = BlueprintSelector()
        bp = selector.select_with_fallback("some random query with no match")
        assert bp is not None

    def test_suggest_top_n(self):
        from src.document.blueprint import BlueprintSelector
        selector = BlueprintSelector()
        suggestions = selector.suggest("project", top_n=3)
        assert len(suggestions) <= 3
        assert all(len(s) == 3 for s in suggestions)

    def test_list_blueprints(self):
        from src.document.blueprint import BlueprintSelector
        selector = BlueprintSelector()
        bp_list = selector.list_blueprints()
        assert len(bp_list) >= 3


class TestAIReportPlanner:
    def test_fallback_plan_engineering(self):
        from src.document.blueprint import BlueprintLoader, AIReportPlanner
        loader = BlueprintLoader()
        bp = loader.load("engineering_project")
        planner = AIReportPlanner(provider=None)
        plan = planner._plan_fallback(
            topic="Smart Home Automation System",
            blueprint=bp,
            title="Smart Home Automation",
            author="John Doe",
            date="2026-05-22",
        )
        assert plan is not None
        assert plan.title == "Smart Home Automation"
        assert plan.blueprint_id == "engineering_project"
        assert len(plan.sections) > 0

    def test_fallback_plan_has_required_sections(self):
        from src.document.blueprint import BlueprintLoader, AIReportPlanner
        loader = BlueprintLoader()
        bp = loader.load("engineering_project")
        planner = AIReportPlanner(provider=None)
        plan = planner._plan_fallback(
            topic="Test", blueprint=bp,
        )
        section_ids = {s.blueprint_section_id for s in plan.sections}
        assert "certificate" in section_ids
        assert "declaration" in section_ids
        assert "abstract" in section_ids

    def test_fallback_plan_has_chapters(self):
        from src.document.blueprint import BlueprintLoader, AIReportPlanner
        loader = BlueprintLoader()
        bp = loader.load("engineering_project")
        planner = AIReportPlanner(provider=None)
        plan = planner._plan_fallback(
            topic="Machine Learning", blueprint=bp,
        )
        chapter_sections = [s for s in plan.sections
                            if s.blueprint_section_id == "chapters"]
        assert len(chapter_sections) >= 4

    def test_fallback_plan_research(self):
        from src.document.blueprint import BlueprintLoader, AIReportPlanner
        loader = BlueprintLoader()
        bp = loader.load("research_paper")
        planner = AIReportPlanner(provider=None)
        plan = planner._plan_fallback(
            topic="Deep Learning", blueprint=bp,
        )
        assert plan.blueprint_id == "research_paper"
        section_ids = {s.blueprint_section_id for s in plan.sections}
        assert "introduction" in section_ids
        assert "methodology" in section_ids
        assert "conclusion" in section_ids

    def test_fallback_plan_internship(self):
        from src.document.blueprint import BlueprintLoader, AIReportPlanner
        loader = BlueprintLoader()
        bp = loader.load("internship_report")
        planner = AIReportPlanner(provider=None)
        plan = planner._plan_fallback(
            topic="Software Engineering Internship", blueprint=bp,
        )
        section_ids = {s.blueprint_section_id for s in plan.sections}
        assert "company_profile" in section_ids
        assert "work_done" in section_ids
        assert "outcomes" in section_ids

    def test_fallback_plan_total_pages_positive(self):
        from src.document.blueprint import BlueprintLoader, AIReportPlanner
        loader = BlueprintLoader()
        bp = loader.load("engineering_project")
        planner = AIReportPlanner(provider=None)
        plan = planner._plan_fallback(
            topic="IoT", blueprint=bp,
        )
        assert plan.total_pages > 0
        assert plan.total_references > 0
        assert plan.references is not None


class TestBlueprintBuilder:
    def test_build_basic_document(self):
        from src.document.blueprint import BlueprintBuilder, ReportPlan, PlanSection
        builder = BlueprintBuilder()
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Test Report", author="Author",
            sections=[
                PlanSection(blueprint_section_id="abstract",
                            heading="Abstract",
                            content="This is a test abstract."),
                PlanSection(blueprint_section_id="introduction",
                            heading="1. Introduction",
                            content="This is the introduction.\n\nIt has two paragraphs.",
                            subsections=[
                                PlanSection(blueprint_section_id="introduction",
                                            heading="1.1 Background",
                                            level=2,
                                            content="Background content."),
                            ]),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_output.docx")
            result = builder.build(plan, output_path)
            assert result is True
            assert os.path.exists(output_path)
            file_size = os.path.getsize(output_path)
            assert file_size > 0

    def test_build_with_references(self):
        from src.document.blueprint import BlueprintBuilder, ReportPlan, PlanSection
        builder = BlueprintBuilder()
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Test",
            sections=[
                PlanSection(blueprint_section_id="introduction",
                            heading="Introduction", content="Intro."),
                PlanSection(blueprint_section_id="references",
                            heading="References", content=""),
            ],
            references=["[1] Author, Title, 2024.",
                        "[2] Researcher, Paper, 2025."],
            total_references=2,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.docx")
            result = builder.build(plan, output_path)
            assert result is True
            assert os.path.exists(output_path)

    def test_build_with_toc(self):
        from src.document.blueprint import BlueprintBuilder, ReportPlan, PlanSection
        builder = BlueprintBuilder()
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Test Report",
            sections=[
                PlanSection(blueprint_section_id="table_of_contents",
                            heading="Table of Contents"),
                PlanSection(blueprint_section_id="chapters",
                            heading="1. Chapter One", content="Content."),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.docx")
            result = builder.build(plan, output_path)
            assert result is True

    def test_build_cover_page(self):
        from src.document.blueprint import BlueprintBuilder, ReportPlan, PlanSection
        builder = BlueprintBuilder()
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Cover Page Test", author="Test Author", date="2026-05-22",
            subtitle="A Subtitle",
            sections=[
                PlanSection(blueprint_section_id="cover_page",
                            heading="Cover Page"),
                PlanSection(blueprint_section_id="abstract",
                            heading="Abstract", content="Abstract text."),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.docx")
            result = builder.build(plan, output_path)
            assert result is True

    def test_build_with_tables(self):
        from src.document.blueprint import BlueprintBuilder, ReportPlan, PlanSection
        builder = BlueprintBuilder()
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Test",
            sections=[
                PlanSection(
                    blueprint_section_id="results",
                    heading="4. Results",
                    content="Results here.",
                    requires_table=True,
                    table_headers=["Metric", "Value"],
                    table_rows=[["Accuracy", "95%"], ["Precision", "93%"]],
                ),
            ],
            total_tables=1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.docx")
            result = builder.build(plan, output_path)
            assert result is True


class TestBlueprintValidator:
    def test_valid_plan_passes(self):
        from src.document.blueprint import (
            Blueprint, BlueprintSection, ReportPlan, PlanSection, BlueprintValidator,
        )
        blueprint = Blueprint(
            id="test", name="Test", description="Test",
            sections=[BlueprintSection(id="intro", heading="Introduction")],
        )
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Test",
            sections=[PlanSection(blueprint_section_id="intro", heading="Introduction")],
            total_pages=10,
            total_references=5,
        )
        validator = BlueprintValidator()
        errors = validator.validate(plan, blueprint)
        assert len(errors) == 0

    def test_missing_mandatory_section(self):
        from src.document.blueprint import (
            Blueprint, BlueprintSection, ReportPlan, PlanSection, BlueprintValidator,
        )
        blueprint = Blueprint(
            id="test", name="Test", description="Test",
            sections=[
                BlueprintSection(id="intro", heading="Introduction", mandatory=True),
                BlueprintSection(id="conclusion", heading="Conclusion", mandatory=True),
            ],
        )
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Test",
            sections=[PlanSection(blueprint_section_id="intro", heading="Introduction")],
            total_pages=10,
            total_references=3,
        )
        validator = BlueprintValidator()
        errors = validator.validate(plan, blueprint)
        assert len(errors) >= 1
        assert any("conclusion" in e.lower() for e in errors)

    def test_zero_pages_fails(self):
        from src.document.blueprint import (
            Blueprint, BlueprintSection, ReportPlan, PlanSection, BlueprintValidator,
        )
        blueprint = Blueprint(
            id="test", name="Test", description="Test",
            sections=[BlueprintSection(id="intro", heading="Introduction")],
        )
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Test",
            sections=[PlanSection(blueprint_section_id="intro", heading="Introduction")],
            total_pages=0,
        )
        validator = BlueprintValidator()
        errors = validator.validate(plan, blueprint)
        assert len(errors) >= 1
        assert any("pages" in e.lower() for e in errors)

    def test_reference_count_mismatch(self):
        from src.document.blueprint import (
            Blueprint, BlueprintSection, ReportPlan, PlanSection, BlueprintValidator,
        )
        blueprint = Blueprint(
            id="test", name="Test", description="Test",
            sections=[BlueprintSection(id="intro", heading="Introduction")],
            references_style="ieee",
        )
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Test",
            sections=[PlanSection(blueprint_section_id="intro", heading="Introduction")],
            total_pages=10,
            total_references=5,
            references=["[1] Ref A", "[2] Ref B"],
        )
        validator = BlueprintValidator()
        errors = validator.validate(plan, blueprint)
        assert any("reference" in e.lower() for e in errors)

    def test_validate_with_warnings(self):
        from src.document.blueprint import (
            Blueprint, BlueprintSection, ReportPlan, PlanSection, BlueprintValidator,
        )
        blueprint = Blueprint(
            id="test", name="Test", description="Test",
            sections=[BlueprintSection(id="intro", heading="Introduction")],
            requires_lof=True,
        )
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Test",
            sections=[PlanSection(blueprint_section_id="intro", heading="Introduction")],
            total_pages=10,
            total_figures=0,
        )
        validator = BlueprintValidator()
        errors, warnings = validator.validate_with_warnings(plan, blueprint)
        assert any("figures" in w.lower() for w in warnings)

    def test_is_valid(self):
        from src.document.blueprint import (
            Blueprint, BlueprintSection, ReportPlan, PlanSection, BlueprintValidator,
        )
        blueprint = Blueprint(
            id="test", name="Test", description="Test",
            sections=[BlueprintSection(id="intro", heading="Introduction")],
        )
        plan = ReportPlan(
            blueprint_id="test", blueprint_name="Test",
            title="Test",
            sections=[PlanSection(blueprint_section_id="intro", heading="Introduction")],
            total_pages=10,
        )
        validator = BlueprintValidator()
        assert validator.is_valid(plan, blueprint) is True

    def test_engineering_project_validates(self):
        from src.document.blueprint import BlueprintLoader, AIReportPlanner, BlueprintValidator
        loader = BlueprintLoader()
        bp = loader.load("engineering_project")
        planner = AIReportPlanner(provider=None)
        plan = planner._plan_fallback(
            topic="Smart Home", blueprint=bp,
        )
        validator = BlueprintValidator()
        errors = validator.validate(plan, bp)
        assert len(errors) == 0, f"Validation errors: {errors}"


class TestScratchPipelineBlueprint:
    def test_pipeline_blueprint_listing(self):
        from src.pipeline.generation.scratch import ScratchPipeline
        pipeline = ScratchPipeline()
        blueprints = pipeline.list_blueprints()
        assert len(blueprints) >= 3

    def test_pipeline_preview_plan(self):
        from src.pipeline.generation.scratch import ScratchPipeline
        pipeline = ScratchPipeline()
        preview = pipeline.preview_plan(topic="Machine Learning Project",
                                        report_type="engineering")
        assert preview is not None
        assert "blueprint" in preview
        assert "sections" in preview
        assert len(preview["sections"]) > 0

    def test_pipeline_validate_input(self):
        from src.pipeline.generation.scratch import ScratchPipeline
        pipeline = ScratchPipeline()
        assert pipeline.validate_input({"content": {"title": "Test"}}) is True
        assert pipeline.validate_input({"content": {"topic": "AI"}}) is True
        assert pipeline.validate_input({"content": {}}) is False
        assert pipeline.validate_input({"content": None}) is False

    def test_pipeline_execute_scratch(self):
        from src.pipeline.generation.scratch import ScratchPipeline
        pipeline = ScratchPipeline()
        result = pipeline.execute({
            "content": {
                "title": "Test Document",
                "author": "Tester",
                "report_type": "research_paper",
            }
        })
        assert result.success is True
        assert result.output_path is not None
        assert os.path.exists(result.output_path)

    def test_pipeline_execute_engineering(self):
        from src.pipeline.generation.scratch import ScratchPipeline
        pipeline = ScratchPipeline()
        result = pipeline.execute({
            "content": {
                "title": "Engineering Project: Smart Home",
                "author": "John Doe",
                "report_type": "engineering_project",
            }
        })
        assert result.success is True
        assert result.output_path is not None

    def test_pipeline_execute_custom_blueprint(self):
        from src.pipeline.generation.scratch import ScratchPipeline
        custom_data = {
            "id": "mini_report",
            "name": "Mini Report",
            "description": "A minimal test report",
            "sections": [
                {"id": "summary", "heading": "Summary", "level": 1},
                {"id": "details", "heading": "1. Details", "level": 1},
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False, encoding="utf-8") as f:
            json.dump(custom_data, f)
            tmp_path = f.name

        try:
            pipeline = ScratchPipeline()
            result = pipeline.execute({
                "content": {"title": "Custom Test"},
                "custom_blueprint": tmp_path,
            })
            assert result.success is True
        finally:
            os.unlink(tmp_path)


class TestBlueprintIntegration:
    def test_full_flow_engineering_project(self):
        from src.document.blueprint import (
            BlueprintLoader, AIReportPlanner, BlueprintBuilder, BlueprintValidator,
        )
        loader = BlueprintLoader()
        bp = loader.load("engineering_project")
        assert bp is not None

        planner = AIReportPlanner(provider=None)
        plan = planner._plan_fallback(
            topic="IoT Based Smart Agriculture System",
            blueprint=bp,
            title="IoT Based Smart Agriculture System",
            author="Jane Smith",
        )
        assert len(plan.sections) >= 6

        validator = BlueprintValidator()
        errors = validator.validate(plan, bp)
        assert len(errors) == 0, f"Validation errors: {errors}"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "engineering_report.docx")
            builder = BlueprintBuilder()
            result = builder.build(plan, output_path)
            assert result is True
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 1000

    def test_full_flow_custom_blueprint(self):
        from src.document.blueprint import (
            BlueprintLoader, AIReportPlanner, BlueprintBuilder, BlueprintValidator,
        )
        custom_data = {
            "id": "test_full",
            "name": "Full Flow Test",
            "description": "End-to-end test",
            "sections": [
                {"id": "intro", "heading": "1. Introduction", "level": 1},
                {"id": "body", "heading": "2. Main Body", "level": 1},
                {"id": "conclusion", "heading": "3. Conclusion", "level": 1},
                {"id": "references", "heading": "References", "level": 1},
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False, encoding="utf-8") as f:
            json.dump(custom_data, f)
            tmp_path = f.name

        try:
            loader = BlueprintLoader()
            bp = loader.load_custom(tmp_path)
            assert bp is not None
            assert len(bp.sections) == 4

            planner = AIReportPlanner(provider=None)
            plan = planner._plan_fallback(
                topic="Custom Topic", blueprint=bp,
                title="Custom Report",
            )
            assert len(plan.sections) == 4

            validator = BlueprintValidator()
            assert validator.is_valid(plan, bp) is True

            with tempfile.TemporaryDirectory() as tmpdir2:
                output_path = os.path.join(tmpdir2, "custom_report.docx")
                builder = BlueprintBuilder()
                result = builder.build(plan, output_path)
                assert result is True
        finally:
            os.unlink(tmp_path)
