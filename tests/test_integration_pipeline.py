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
        assert result.success is True

    def test_pipeline_execution_flow(self):
        from src.pipeline import CoordinatedPipeline
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
        pipe = CoordinatedPipeline()
        mock_memory = MockMemoryHub()
        result = pipe.execute(
            {"topic": "Validation Test"},
            components={"memory_hub": mock_memory},
        )
        assert result.success is True

    def test_pipeline_result_structure(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        result = pipe.execute({"topic": "Result Structure Test"})
        for attr in ("success", "output_path", "data", "error", "execution_time"):
            assert hasattr(result, attr)
        assert result.execution_time >= 0

    def test_pipeline_multiple_sequential(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        for topic in ["Topic A", "Topic B", "Topic C"]:
            result = pipe.execute({"topic": topic})
            assert result.success is True

    def test_pipeline_agent_coordinator_integration(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()

        mock_plan = MockPlan()
        mock_coord = MockCoordinator()

        from src.pipeline.coordinated import PipelineContext
        ctx = PipelineContext(topic="Integration")
        ctx.agent_coordinator = mock_coord
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
        assert result is True

    def test_generator_imports(self):
        from src.generator import (
            ReportGenerator, ChapterGenerator, SectionGenerator,
            SubsectionGenerator, ParagraphGenerator,
        )
        for cls in (ReportGenerator, ChapterGenerator, SectionGenerator,
                    SubsectionGenerator, ParagraphGenerator):
            assert cls is not None

    def test_generator_hierarchy(self):
        from src.generator.base import GeneratorContext
        from src.generator.paragraph import ParagraphGenerator
        pg = ParagraphGenerator()
        ctx = GeneratorContext(topic="Test Topic")
        result = pg.generate(ctx, focus="testing", index=0)
        assert isinstance(result, str) and len(result) > 0

    def test_section_generator_creates_content(self):
        from src.generator.base import GeneratorContext
        from src.generator.section import SectionGenerator
        sg = SectionGenerator()
        ctx = GeneratorContext(topic="Machine Learning")
        result = sg.generate(ctx, heading="Overview", subsection_count=0, paragraph_count=2)
        assert isinstance(result, str) and len(result) > 0

    def test_subsection_generator(self):
        from src.generator.base import GeneratorContext
        from src.generator.subsection import SubsectionGenerator
        sg = SubsectionGenerator()
        ctx = GeneratorContext(topic="Data Science")
        result = sg.generate(ctx, heading="Methods", paragraph_count=2)
        assert isinstance(result, str) and len(result) > 0

    def test_chapter_generator(self):
        from src.generator.base import GeneratorContext
        from src.generator.chapter import ChapterGenerator
        cg = ChapterGenerator()
        ctx = GeneratorContext(topic="Climate Change")
        result = cg.generate(ctx, heading="Introduction", section_count=2)
        assert isinstance(result, dict) and result["heading"] == "Introduction"
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
        assert result["title"] == "Full Report"
        assert result["chapter_count"] == 2
        assert result["total_words"] > 0

    def test_report_generator_coherence(self):
        from src.generator.base import GeneratorContext
        from src.generator.report import ReportGenerator
        rg = ReportGenerator()
        ctx = GeneratorContext(topic="Renewable Energy")
        result = rg.generate(ctx, title="Coherence Test", sections=[
            {"heading": "Chapter 1", "level": 1, "section_count": 1},
            {"heading": "Chapter 2", "level": 1, "section_count": 1},
        ])
        assert "coherence" in result
        assert "warnings" in result["coherence"]

    def test_agent_coordinator_imports(self):
        from src.agents import (
            ResearchAgent, WritingAgent, CitationAgent,
            FormattingAgent, ExportAgent, AgentCoordinator,
        )
        for cls in (ResearchAgent, WritingAgent, CitationAgent,
                    FormattingAgent, ExportAgent, AgentCoordinator):
            assert cls is not None

    def test_agent_coordinator_initialization(self):
        from src.agents import AgentCoordinator
        from src.agents.base import BaseAgent, AgentResponse
        class _DummyAgent(BaseAgent):
            def execute(self, input_data, **kwargs):
                return AgentResponse(success=True)
        coord = AgentCoordinator(agents={
            "research": _DummyAgent("research"),
            "writing": _DummyAgent("writing"),
        })
        assert coord.name == "coordinator"
        status = coord.get_agent_status()
        assert "research" in status
        assert "writing" in status

    def test_agent_coordinator_execute_no_topic(self):
        from src.agents import AgentCoordinator
        from src.agents.base import BaseAgent, AgentResponse
        class _DummyAgent(BaseAgent):
            def execute(self, input_data, **kwargs):
                return AgentResponse(success=True)
        coord = AgentCoordinator(agents={"dummy": _DummyAgent("dummy")})
        assert coord.execute("not a dict").success is False

    def test_agent_coordinator_execute_with_topic(self):
        from src.agents.base import BaseAgent, AgentResponse
        from src.agents import AgentCoordinator
        class _DummyAgent(BaseAgent):
            def execute(self, input_data, **kwargs):
                return AgentResponse(success=True, data={"phase": "dummy"})
        coord = AgentCoordinator(agents={"dummy": _DummyAgent("dummy")})
        result = coord.execute({"topic": "Test Topic"})
        assert result.success is True
        assert result.data["topic"] == "Test Topic"

    def test_coordinator_phases_all_accounted(self):
        from src.agents.coordinator import AGENT_PHASES
        assert set(AGENT_PHASES) == {"research", "planning", "writing", "citation", "formatting", "export"}

    def test_memory_hub_in_pipeline(self):
        from src.memory import MemoryHub
        mh = MemoryHub()
        assert hasattr(mh, "process_section") and hasattr(mh, "get_status")

    def test_context_assembler_interface(self):
        from src.retrieval.context import ContextAssembler
        ca = ContextAssembler()
        for attr in ("index_knowledge", "retrieve_context", "is_ready"):
            assert hasattr(ca, attr)

    def test_coordinated_pipeline_dry_run(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        result = pipe.execute({"topic": "Dry Run"})
        assert result.success is True
        assert result.data["topic"] == "Dry Run"
        assert "phases_completed" in result.data

    def test_phase_selection_plan_only(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        result = pipe.execute({"topic": "Selective"}, phases=["plan"])
        assert result.success is True
        phases_done = result.data["phases_completed"]
        assert "plan" in phases_done
        assert "generate" not in phases_done

    def test_phase_selection_export_only(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        result = pipe.execute({"topic": "Export Only"}, phases=["export"])
        assert result.success is True
        assert result.data["phases_completed"] == ["export"]

    def test_phase_selection_generate_and_export(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        result = pipe.execute({"topic": "Partial"}, phases=["generate", "export"])
        assert result.success is True
        done = result.data["phases_completed"]
        assert "generate" in done and "export" in done
        assert "plan" not in done

    def test_progress_callback(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        events = []

        def cb(phase, status):
            events.append((phase, status))

        result = pipe.execute(
            {"topic": "Callback Test"},
            callback=cb,
        )
        assert result.success is True
        assert len(events) > 0
        assert events[0][1] == "started"

    def test_review_phase_smoke(self):
        from src.pipeline import CoordinatedPipeline
        pipe = CoordinatedPipeline()
        from src.review.pipeline import ReviewPipeline
        rp = ReviewPipeline()
        result = pipe.execute(
            {"topic": "Review Test"},
            components={"review_pipeline": rp},
            phases=["review"],
        )
        assert result.success is True
        assert "review" in result.data["phases_completed"]

    def test_memory_hub_persistence(self):
        import tempfile, os
        from src.memory import MemoryHub

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            mh1 = MemoryHub(persistence_path=path)
            mh1.abbreviations.register("AI", "Artificial Intelligence")
            mh1.save()

            mh2 = MemoryHub(persistence_path=path)
            assert mh2.abbreviations.get_definition("AI") == "Artificial Intelligence"
        finally:
            os.unlink(path)

    def test_memory_hub_persistence_no_file(self):
        from src.memory import MemoryHub
        mh = MemoryHub(persistence_path="nonexistent/path.json")
        assert mh.abbreviations.all_abbreviations() == {}

    def test_export_agent_fallback_docx(self):
        from src.agents.export_agent import ExportAgent
        agent = ExportAgent()

        class MockSection:
            def __init__(self, heading, content):
                self.heading = heading
                self.content = content

        class MockPlan:
            def __init__(self):
                self.sections = [
                    MockSection("Introduction", "This is the introduction."),
                    MockSection("Conclusion", "This is the conclusion."),
                ]

        output_path = "test_output/fallback_test.docx"
        os.makedirs("test_output", exist_ok=True)
        result = agent.execute({
            "plan": MockPlan(),
            "output_path": output_path,
            "formats": ["docx"],
        })
        assert result.success is True
        assert os.path.exists(output_path)
        os.unlink(output_path)

    def test_export_agent_missing_plan(self):
        from src.agents.export_agent import ExportAgent
        agent = ExportAgent()
        result = agent.execute({"formats": ["docx"]})
        assert result.success is False

    def test_phases_constant(self):
        from src.pipeline.coordinated import PHASE_ORDER, ALL_PHASES
        assert len(PHASE_ORDER) == 10
        assert ALL_PHASES == set(PHASE_ORDER)
        assert "review" in ALL_PHASES


class TestMockCoordinator:
    def test_mock_coordinator(self):
        mc = MockCoordinator()
        from src.agents.base import AgentResponse
        result = mc.execute({})
        assert isinstance(result, AgentResponse)
        assert result.success is True


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

    def process_section(self, content, heading):
        return []

    def get_status(self):
        return {}

    def save(self):
        pass


class MockContextAssembler:
    def is_ready(self):
        return True

    def retrieve_context(self, query):
        return {"chunks": [], "context_text": "Mock context for testing."}


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
                "phases": {"research": {"status": "completed"}, "writing": {"status": "completed"}},
                "summary": {"research": "completed", "writing": "completed"},
            },
        )
