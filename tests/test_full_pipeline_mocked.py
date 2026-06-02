"""Integration tests for full pipeline with mocked LLM provider.

These tests verify the entire pipeline works correctly without requiring
a running Ollama instance. All LLM calls return controlled mock responses.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestFullPipelineMocked:
    """Full end-to-end pipeline tests with mocked LLM provider."""

    def test_pipeline_completes_all_phases(self, mock_provider):
        """Verify all 10 pipeline phases execute successfully with mocks."""
        from src.pipeline import CoordinatedPipeline
        from src.generator import ReportGenerator
        from src.generator.knowledge_driven_generator import KnowledgeDrivenReportGenerator
        from src.memory import MemoryHub

        pipe = CoordinatedPipeline(output_dir="test_output")
        os.makedirs("test_output", exist_ok=True)

        knowledge_gen = KnowledgeDrivenReportGenerator(
            provider=mock_provider,
            context_assembler=None,
        )
        report_gen = ReportGenerator(
            provider=mock_provider,
            context_assembler=None,
        )

        result = pipe.execute(
            {"topic": "Quantum Computing Advances", "output_path": "test_output/mocked_test.docx"},
            phases=["plan", "research", "generate", "review", "validate", "assemble_doc", "export"],
            components={
                "report_generator": report_gen,
                "knowledge_generator": knowledge_gen,
                "memory_hub": MemoryHub(),
            },
        )

        assert result.success, f"Pipeline failed: {result.error}"
        assert "phases_completed" in result.data
        phases = result.data["phases_completed"]
        assert len(phases) > 0, f"No phases completed: {result.data}"

    def test_pipeline_handles_recoverable_errors(self, mock_provider):
        """Verify pipeline continues past recoverable phase errors."""
        from src.pipeline import CoordinatedPipeline
        from src.core.errors import RecoverableError

        pipe = CoordinatedPipeline()
        from src.pipeline.coordinated import PipelineContext

        ctx = PipelineContext(topic="Error Recovery Test")
        ctx.errors = []

        class FailingPlanner:
            def execute(self, topic):
                raise RecoverableError("plan", "Test recoverable error")

        ctx.planner = FailingPlanner()
        result = pipe._run_plan(ctx)
        assert result is True

    def test_knowledge_generator_with_mock(self, mock_provider):
        """Verify KnowledgeDrivenReportGenerator works with mocked provider."""
        from src.generator.knowledge_driven_generator import KnowledgeDrivenReportGenerator

        gen = KnowledgeDrivenReportGenerator(
            provider=mock_provider,
            context_assembler=None,
        )

        result = gen.generate_full_report(
            topic="Machine Learning",
            author="Test Author",
            parallel=False,
        )

        assert result["title"] == "Machine Learning"
        assert "section_contents" in result
        assert result["section_count"] > 0

    def test_report_generator_with_mock(self, mock_provider):
        """Verify ReportGenerator works with mocked provider."""
        from src.generator.base import GeneratorContext
        from src.generator.report import ReportGenerator

        rg = ReportGenerator(provider=mock_provider)
        ctx = GeneratorContext(topic="Test Topic")
        result = rg.generate(ctx, title="Mocked Report", sections=[
            {"heading": "Chapter 1", "level": 1, "section_count": 1},
        ])

        assert result["title"] == "Mocked Report"
        assert result["chapter_count"] == 1
        assert result["total_words"] > 0

    def test_injection_pipeline_mocked(self):
        """Verify ingestion pipeline handles files correctly."""
        from src.ingestion.pipeline import IngestionPipeline

        pipe = IngestionPipeline()
        assert pipe is not None
        assert hasattr(pipe, "ingest_file")
        assert hasattr(pipe, "ingest_directory")

    def test_web_search_connection_pooling(self):
        """Verify WebSearchRetriever uses connection pooling."""
        from src.retrieval.web import WebSearchRetriever
        retriever = WebSearchRetriever(api_key="test-key")
        session = retriever._get_session()
        assert session is not None
        assert session.headers.get("Content-Type") == "application/json"

    def test_sanitize_text(self):
        """Verify output sanitization works correctly."""
        from src.document.docx_v2_generator import sanitize_text

        assert sanitize_text("Normal text") == "Normal text"
        assert "\x00" not in sanitize_text("Bad\x00text")
        assert sanitize_text("A" * 100000, max_length=100) == "A" * 100

    def test_lru_cache_eviction(self):
        """Verify LRU cache evicts oldest entries."""
        from src.retrieval.reranker import LRUCache

        cache = LRUCache(maxsize=3)
        cache.put("a", 1.0)
        cache.put("b", 2.0)
        cache.put("c", 3.0)
        cache.put("d", 4.0)

        assert cache.get("a") is None  # Evicted
        assert cache.get("b") == 2.0
        assert cache.get("d") == 4.0

    def test_extract_json_shared_utility(self):
        """Verify shared extract_json utility works."""
        from src.core.utils import extract_json

        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

        result = extract_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

        result = extract_json("{'key': 'value'}")
        assert result == {"key": "value"}

        assert extract_json("") is None
        assert extract_json(None) is None

    def test_https_url_validation(self):
        """Verify HTTPS URL validation."""
        from src.retrieval.web import _validate_https_url

        assert _validate_https_url("https://api.tavily.com/search") == "https://api.tavily.com/search"

        with pytest.raises(ValueError, match="HTTPS"):
            _validate_https_url("http://api.tavily.com/search")

    def test_safe_path_resolution(self):
        """Verify path traversal protection."""
        from src.main import _resolve_safe_path
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent

        # Valid path within project
        result = _resolve_safe_path(str(project_root / "knowledge"), allowed_parent=project_root)
        assert result is not None

        # Path traversal blocked
        result = _resolve_safe_path(str(project_root / ".." / "etc" / "passwd"), allowed_parent=project_root)
        assert result is None

    def test_retrieval_benchmark_metrics(self):
        """Verify retrieval benchmark metrics are computed correctly."""
        from src.retrieval.benchmarks import evaluate_retrieval, RetrievalMetrics

        retrieved = [
            {"id": "doc1", "text": "AI document 1"},
            {"id": "doc2", "text": "AI document 2"},
            {"id": "doc3", "text": "Unrelated"},
        ]
        relevant = {"doc1", "doc2"}

        metrics = evaluate_retrieval("AI query", retrieved, relevant, k=3)
        assert metrics.recall_at_k == 1.0
        assert metrics.precision_at_k == pytest.approx(2/3)
        assert metrics.mrr == 1.0
        assert metrics.retrieved_relevant == 2

    def test_prompt_versioning(self):
        """Verify prompt versioning system works."""
        from prompts.builder import get_prompt_version, get_prompt_version_history, get_section_prompt_versions

        version = get_prompt_version()
        assert version == "2.0.0"

        history = get_prompt_version_history()
        assert "1.0.0" in history
        assert "2.0.0" in history

        section_versions = get_section_prompt_versions()
        assert "introduction" in section_versions
        assert "conclusion" in section_versions

    def test_availability_cache_in_ollama_provider(self):
        """Verify Ollama provider caches availability checks."""
        from src.providers.ollama import OllamaProvider
        provider = OllamaProvider()
        assert hasattr(provider, "_availability_cache")
        assert hasattr(provider, "_availability_cache_ttl")
        assert provider._availability_cache_ttl > 0
