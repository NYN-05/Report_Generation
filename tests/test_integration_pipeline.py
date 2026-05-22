"""Integration tests for the coordinated end-to-end pipeline."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestCoordinatedPipeline:
    """Verify the CoordinatedPipeline wires all components correctly."""

    def test_pipeline_imports(self):
        from src.pipeline import CoordinatedPipeline, PipelineContext
        assert CoordinatedPipeline is not None
        assert PipelineContext is not None

    def test_pipeline_instantiation(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline(output_dir="output")
        assert pipe.name == "coordinated"
        assert pipe.output_dir == "output"

    def test_pipeline_empty_topic(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        result = pipe.execute({})
        assert result.success is False
        assert "topic" in result.error.lower() or "no topic" in result.error.lower()

    def test_pipeline_with_topic_no_components(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        result = pipe.execute({"topic": "Quantum Computing"})
        assert result.success is True  # gracefully skips all phases

    def test_pipeline_execution_flow(self):
        from src.pipeline import CoordinatedPipeline
        from src.core.state import DocumentState

        pipe = CoordinatedPipeline(output_dir="test_output")
        mock_memory = MockMemoryHub()
        result = pipe.execute(
            {"topic": "Renewable Energy Trends", "output_path": "test_output/test.docx"},
            components={"memory_hub": mock_memory},
        )
        assert result.success is True
        assert result.data["topic"] == "Renewable Energy Trends"

    def test_pipeline_with_research_phase(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        mock_assembler = MockContextAssembler()
        result = pipe.execute(
            {"topic": "AI Ethics"},
            components={"context_assembler": mock_assembler},
        )
        assert result.success is True

    def test_pipeline_export_fallback(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        result = pipe.execute(
            {"topic": "Test", "output_path": "output/test.docx"},
        )
        assert result.success is True

    def test_pipeline_validation_phase(self):
        from src.pipeline import CoordinatedPipeline
        from src.core.state import DocumentState

        pipe = CoordinatedPipeline()
        ds = DocumentState(title="Validation Test")
        mock_memory = MockMemoryHub()

        class MockCoordinator:
            def execute(self, *args, **kwargs):
                from src.agents.base import AgentResponse
                return AgentResponse(success=True, data={"phases": {}}, error="")

        result = pipe.execute(
            {"topic": "Validation Test"},
            components={
                "memory_hub": mock_memory,
                "coordinator": MockCoordinator(),
            },
        )
        assert result.success is True

    def test_pipeline_result_structure(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        result = pipe.execute({"topic": "Result Structure Test"})

        assert hasattr(result, "success")
        assert hasattr(result, "output_path")
        assert hasattr(result, "data")
        assert hasattr(result, "error")
        assert hasattr(result, "execution_time")
        assert result.execution_time >= 0

    def test_pipeline_multiple_sequential(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        topics = ["Topic A", "Topic B", "Topic C"]
        for topic in topics:
            result = pipe.execute({"topic": topic})
            assert result.success is True

    def test_pipeline_agent_coordinator_integration(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()

        class MockPlan:
            class Section:
                def __init__(self, heading, blueprint_id, level=2, content=""):
                    self.heading = heading
                    self.blueprint_section_id = blueprint_id
                    self.level = level
                    self.content = content
                    self.retrieval_context = ""

            def __init__(self):
                self.sections = [
                    self.Section("Methods", "methods"),
                    self.Section("Results", "results"),
                ]
                self.references = []

        class MockCoordinator:
            def execute(self, *args, **kwargs):
                from src.agents.base import AgentResponse
                return AgentResponse(
                    success=True,
                    data={
                        "phases": {
                            "research": {"status": "completed"},
                            "writing": {"status": "completed"},
                        },
                        "summary": {"research": "completed", "writing": "completed"},
                    },
                )

        mock_plan = MockPlan()
        pipe._run_research(pipe._PipelineContext__ctx) if hasattr(pipe, "_PipelineContext__ctx") else None

        from src.pipeline.coordinated import PipelineContext
        ctx = PipelineContext(topic="Integration")
        ctx.agent_coordinator = MockCoordinator()
        ctx.plan = mock_plan

        result = pipe._run_generate(ctx)
        assert result is True

    def test_registry_includes_coordinated(self):
        from src.pipeline.base import PipelineRegistry
        PipelineRegistry.register_defaults()
        from src.pipeline import CoordinatedPipeline

        PipelineRegistry.register("coordinated", CoordinatedPipeline)
        assert PipelineRegistry.get("coordinated") is CoordinatedPipeline

    def test_pipeline_phase_failure_handling(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()

        from src.pipeline.coordinated import PipelineContext
        ctx = PipelineContext(topic="Fail Test")
        ctx.errors = []

        class FailingExport:
            def execute(self, *args, **kwargs):
                raise RuntimeError("Export failure")

        ctx.export_builder = FailingExport()
        result = pipe._run_export(ctx)
        assert result is True  # graceful fallback

    def test_generator_imports(self):
        from src.generator import (
            ReportGenerator,
            ChapterGenerator,
            SectionGenerator,
            SubsectionGenerator,
            ParagraphGenerator,
        )
        assert ReportGenerator is not None
        assert ChapterGenerator is not None
        assert SectionGenerator is not None
        assert SubsectionGenerator is not None
        assert ParagraphGenerator is not None

    def test_generator_hierarchy(self):
        from src.generator.base import GeneratorContext
        from src.generator.paragraph import ParagraphGenerator

        pg = ParagraphGenerator()
        ctx = GeneratorContext(topic="Test Topic")
        result = pg.generate(ctx, focus="testing", index=0)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Test Topic" in result or "testing" in result

    def test_section_generator_creates_content(self):
        from src.generator.base import GeneratorContext
        from src.generator.section import SectionGenerator

        sg = SectionGenerator()
        ctx = GeneratorContext(topic="Machine Learning")
        result = sg.generate(ctx, heading="Overview", subsection_count=0, paragraph_count=2)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_subsection_generator(self):
        from src.generator.base import GeneratorContext
        from src.generator.subsection import SubsectionGenerator

        sg = SubsectionGenerator()
        ctx = GeneratorContext(topic="Data Science")
        result = sg.generate(ctx, heading="Methods", paragraph_count=2)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_chapter_generator(self):
        from src.generator.base import GeneratorContext
        from src.generator.chapter import ChapterGenerator

        cg = ChapterGenerator()
        ctx = GeneratorContext(topic="Climate Change")
        result = cg.generate(ctx, heading="Introduction", section_count=2)
        assert isinstance(result, dict)
        assert result["heading"] == "Introduction"
        assert len(result["sections"]) == 2

    def test_report_generator(self):
        from src.generator.base import GeneratorContext
        from src.generator.report import ReportGenerator

        rg = ReportGenerator()
        ctx = GeneratorContext(topic="Renewable Energy")
        result = rg.generate(ctx, title="Full Report", sections=[
            {"heading": "Chapter 1", "level": 1, "section_count": 2},
            {"heading": "Chapter 2", "level": 1, "section_count": 2},
        ])
        assert isinstance(result, dict)
        assert result["title"] == "Full Report"
        assert result["chapter_count"] == 2
        assert result["total_words"] > 0

    def test_agent_coordinator_imports(self):
        from src.agents import (
            ResearchAgent, WritingAgent, CitationAgent,
            FormattingAgent, ExportAgent, AgentCoordinator,
        )
        assert ResearchAgent is not None
        assert WritingAgent is not None
        assert CitationAgent is not None
        assert FormattingAgent is not None
        assert ExportAgent is not None
        assert AgentCoordinator is not None

    def test_agent_coordinator_initialization(self):
        from src.agents import AgentCoordinator
        coord = AgentCoordinator()
        assert coord.name == "coordinator"
        status = coord.get_agent_status()
        assert "research" in status
        assert "writing" in status
        assert "citation" in status
        assert "formatting" in status
        assert "export" in status

    def test_agent_coordinator_execute_no_topic(self):
        from src.agents import AgentCoordinator
        coord = AgentCoordinator()
        result = coord.execute("not a dict")
        assert result.success is False

    def test_agent_coordinator_execute_with_topic(self):
        from src.agents import AgentCoordinator
        coord = AgentCoordinator()
        result = coord.execute({"topic": "Test Topic"})
        assert result.success is True
        assert "phases" in result.data
        assert result.data["topic"] == "Test Topic"

    def test_coordinator_phases_all_accounted(self):
        from src.agents.coordinator import AGENT_PHASES
        expected = {"research", "planning", "writing", "citation", "formatting", "export"}
        assert set(AGENT_PHASES) == expected

    def test_memory_hub_in_pipeline(self):
        from src.memory import MemoryHub
        mh = MemoryHub()
        assert hasattr(mh, "process_section")
        assert hasattr(mh, "get_status")

    def test_context_assembler_interface(self):
        from src.retrieval.context import ContextAssembler
        ca = ContextAssembler()
        assert hasattr(ca, "index_knowledge")
        assert hasattr(ca, "retrieve_context")
        assert hasattr(ca, "is_ready")

    def test_coordinated_pipeline_dry_run(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        result = pipe.execute({"topic": "Dry Run"})
        assert result.success is True
        stats = result.data
        assert stats["topic"] == "Dry Run"
        assert "phases_completed" in stats


class MockMemoryHub:
    """Minimal mock of MemoryHub for pipeline testing."""
    name = "memory_hub"

    def record_search(self, query, count):
        pass

    def record_topics(self, topic, content):
        pass

    def validate_document(self, doc_state):
        return {"errors": [], "warnings": []}

    def update_document_state(self, doc_state):
        pass


class MockContextAssembler:
    """Minimal mock of ContextAssembler for pipeline testing."""

    def is_ready(self):
        return True

    def retrieve_context(self, query):
        return {"chunks": [], "context_text": "Mock context for testing."}
