"""
Tests for the upgraded architecture modules: ingestion, review, memory.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# =============================================================================
# Ingestion Module Tests
# =============================================================================

class TestDocumentParser:
    def test_parse_text_file(self):
        from src.ingestion import DocumentParser
        parser = DocumentParser()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello world.\nThis is a test document.")
            path = f.name
        try:
            text = parser.parse(path)
            assert text is not None
            assert "Hello world" in text
        finally:
            os.unlink(path)

    def test_parse_unsupported_format(self):
        from src.ingestion import DocumentParser
        parser = DocumentParser()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            f.write("test")
            path = f.name
        try:
            text = parser.parse(path)
            assert text is None
        finally:
            os.unlink(path)

    def test_parse_nonexistent_file(self):
        from src.ingestion import DocumentParser
        parser = DocumentParser()
        text = parser.parse("/nonexistent/path.txt")
        assert text is None

    def test_parse_directory(self):
        from src.ingestion import DocumentParser
        parser = DocumentParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                with open(os.path.join(tmpdir, f"doc{i}.txt"), "w") as f:
                    f.write(f"Content of document {i}")
            results = parser.parse_directory(tmpdir)
            assert len(results) == 3


class TestSemanticChunker:
    def test_chunk_simple_text(self):
        from src.ingestion import SemanticChunker
        chunker = SemanticChunker(chunk_size=500)
        text = "Hello world. " * 50
        chunks = chunker.chunk(text, source="test.txt")
        assert len(chunks) >= 1
        for ch in chunks:
            assert "text" in ch
            assert "heading" in ch
            assert "source" in ch

    def test_chunk_by_headings(self):
        from src.ingestion import SemanticChunker
        chunker = SemanticChunker()
        text = "# Introduction\nIntro content here.\n\n# Methodology\nMethod content here.\n\n# Results\nResults content here."
        chunks = chunker.chunk(text, source="test.md")
        assert len(chunks) >= 3
        headings = [c["heading"] for c in chunks]
        assert "Introduction" in headings

    def test_chunk_large_text(self):
        from src.ingestion import SemanticChunker
        chunker = SemanticChunker(chunk_size=200)
        text = ("Paragraph one. " * 30) + "\n\n" + ("Paragraph two. " * 30) + "\n\n" + ("Paragraph three. " * 30)
        chunks = chunker.chunk(text, source="test.txt")
        assert len(chunks) >= 2


class TestVectorStore:
    def test_store_and_search(self):
        from src.ingestion import VectorStore
        store_dir = tempfile.mkdtemp()
        try:
            store = VectorStore(collection_name="test_coll", persist_dir=store_dir)
            if store.is_available():
                chunks = [
                    {"text": "Machine learning is a subset of artificial intelligence.", "heading": "Introduction", "source": "test.txt", "chunk_index": 0},
                    {"text": "Deep learning uses neural networks with many layers.", "heading": "Methods", "source": "test.txt", "chunk_index": 1},
                ]
                count = store.add_chunks(chunks)
                assert count == 2
                results = store.search("machine learning", n_results=2)
                assert len(results) > 0
                store.delete_collection()
            else:
                pytest.skip("ChromaDB not available")
        finally:
            import shutil
            shutil.rmtree(store_dir, ignore_errors=True)

    def test_empty_store(self):
        from src.ingestion import VectorStore
        store_dir = tempfile.mkdtemp()
        try:
            store = VectorStore(collection_name="empty_test", persist_dir=store_dir)
            if store.is_available():
                assert store.count() >= 0
                results = store.search("anything")
                assert isinstance(results, list)
                store.delete_collection()
            else:
                pytest.skip("ChromaDB not available")
        finally:
            import shutil
            shutil.rmtree(store_dir, ignore_errors=True)


class TestIngestionPipeline:
    def test_ingest_and_search(self):
        from src.ingestion import IngestionPipeline
        work_dir = tempfile.mkdtemp()
        try:
            doc_path = os.path.join(work_dir, "test.txt")
            with open(doc_path, "w") as f:
                f.write("# Artificial Intelligence\n\nAI is transforming industries.\n\n# Machine Learning\n\nML enables computers to learn without explicit programming.")
            pipeline = IngestionPipeline(collection_name="test_pipeline", persist_dir=os.path.join(work_dir, "vectordb"))
            if pipeline.is_available():
                count = pipeline.ingest_file(doc_path)
                assert count > 0
                results = pipeline.search("AI", n_results=2)
                assert isinstance(results, list)
            else:
                pytest.skip("Vector store not available")
        finally:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)


# =============================================================================
# Review Pipeline Tests
# =============================================================================

class TestCoherenceChecker:
    def test_no_issues_for_good_structure(self):
        from src.review import CoherenceChecker
        checker = CoherenceChecker()
        sections = [
            {"heading": "1. Introduction", "content": "This introduces AI. " * 20},
            {"heading": "2. Literature Review", "content": "Literature on AI. " * 20},
            {"heading": "3. Methodology", "content": "Methodology for AI. " * 20},
        ]
        result = checker.check(sections)
        assert result.passed

    def test_warning_for_isolation(self):
        from src.review import CoherenceChecker
        checker = CoherenceChecker()
        sections = [
            {"heading": "Results", "content": "Results data " * 100},
        ]
        result = checker.check(sections)
        assert len(result.issues) >= 1
        assert any("few" in i["message"].lower() for i in result.issues)


class TestStyleChecker:
    def test_detects_informal_language(self):
        from src.review import StyleChecker
        checker = StyleChecker()
        sections = [
            {"heading": "Introduction", "content": "This is a really important topic that we think you'll find interesting."}
        ]
        result = checker.check(sections)
        assert not result.passed
        assert len(result.issues) > 0

    def test_clean_content_passes(self):
        from src.review import StyleChecker
        checker = StyleChecker()
        sections = [
            {"heading": "Introduction", "content": "This study examines the impact of artificial intelligence on modern healthcare systems. The analysis reveals significant improvements in diagnostic accuracy."}
        ]
        result = checker.check(sections)
        assert result.passed


class TestCitationChecker:
    def test_detects_missing_citations(self):
        from src.review.citations import CitationChecker
        checker = CitationChecker()
        sections = [
            {"heading": "Introduction", "content": "AI is transforming healthcare."},
            {"heading": "Methodology", "content": "We used neural networks [1]."},
        ]
        result = checker.check(sections)
        assert not result.passed

    def test_well_cited_passes(self):
        from src.review.citations import CitationChecker
        checker = CitationChecker()
        sections = [
            {"heading": "Introduction", "content": "AI is important [1][2]."},
            {"heading": "Methodology", "content": "We used neural networks [1][3]."},
            {"heading": "Results", "content": "Our findings confirm [2][4]."},
        ]
        result = checker.check(sections)
        assert result.passed


class TestRedundancyChecker:
    def test_detects_duplicate_content(self):
        from src.review import RedundancyChecker
        checker = RedundancyChecker(ngram_size=5)
        repeated = "artificial intelligence transforms industries across multiple sectors"
        sections = [
            {"heading": "Introduction", "content": repeated * 5},
            {"heading": "Discussion", "content": repeated * 5},
        ]
        result = checker.check(sections)
        assert not result.passed


class TestFormattingChecker:
    def test_detects_short_section(self):
        from src.review import FormattingChecker
        checker = FormattingChecker()
        sections = [{"heading": "Introduction", "content": "Too short."}]
        result = checker.check(sections)
        assert not result.passed

    def test_good_section_passes(self):
        from src.review import FormattingChecker
        checker = FormattingChecker()
        sections = [{"heading": "Introduction", "content": "Word " * 200}]
        result = checker.check(sections)
        assert result.passed


class TestReviewPipeline:
    def test_full_pipeline(self):
        from src.review import ReviewPipeline
        pipeline = ReviewPipeline()
        sections = [
            {"heading": "Introduction", "content": "This is a really informal introduction. " * 10},
            {"heading": "Methodology", "content": "Standard methodology description. " * 20},
        ]
        report = pipeline.review_sections(sections)
        assert "results" in report
        assert "total_issues" in report
        assert report["total_issues"] >= 0

    def test_get_summary(self):
        from src.review import ReviewPipeline
        pipeline = ReviewPipeline()
        report = {
            "passed": True,
            "total_issues": 0,
            "results": {
                "coherence": {"checker": "coherence", "passed": True, "issue_count": 0, "issues": []},
            },
        }
        summary = pipeline.get_summary(report)
        assert "Review Results" in summary


# =============================================================================
# Memory Module Tests
# =============================================================================

class TestAbbreviationTracker:
    def test_register_and_lookup(self):
        from src.memory import AbbreviationTracker
        tracker = AbbreviationTracker()
        tracker.register("AI", "Artificial Intelligence")
        assert tracker.get_definition("AI") == "Artificial Intelligence"
        assert tracker.get_abbreviation("artificial intelligence") == "AI"

    def test_scan_text(self):
        from src.memory import AbbreviationTracker
        tracker = AbbreviationTracker()
        tracker.scan_text("Machine Learning (ML) is a subset of AI.")
        assert tracker.get_definition("ML") is not None

    def test_all_abbreviations(self):
        from src.memory import AbbreviationTracker
        tracker = AbbreviationTracker()
        tracker.register("CNN", "Convolutional Neural Network")
        tracker.register("RNN", "Recurrent Neural Network")
        all_abbrs = tracker.all_abbreviations()
        assert len(all_abbrs) == 2

    def test_clear(self):
        from src.memory import AbbreviationTracker
        tracker = AbbreviationTracker()
        tracker.register("AI", "Artificial Intelligence")
        tracker.clear()
        assert len(tracker.all_abbreviations()) == 0


class TestCitationTracker:
    def test_register_and_get(self):
        from src.memory import CitationTracker
        tracker = CitationTracker()
        idx = tracker.register("smith2023", "Smith, J. (2023). AI Research.")
        assert idx == 1
        assert tracker.get_index("smith2023") == 1
        assert tracker.get_text("smith2023") == "Smith, J. (2023). AI Research."

    def test_validate_references(self):
        from src.memory import CitationTracker
        tracker = CitationTracker()
        tracker.register("ref1", "Author (2023). Title.")
        issues = tracker.validate_references("See [1] and [5]")
        assert len(issues) > 0


class TestMemoryHub:
    def test_process_section(self):
        from src.memory import MemoryHub
        hub = MemoryHub()
        hub.process_section("Convolutional Neural Networks (CNN) are used for image processing [1].")
        assert len(hub.abbreviations.all_abbreviations()) > 0

    def test_get_status(self):
        from src.memory import MemoryHub
        hub = MemoryHub()
        hub.abbreviations.register("AI", "Artificial Intelligence")
        hub.citations.register("ref", "Some reference")
        status = hub.get_status()
        assert status["abbreviation_count"] == 1
        assert status["citation_count"] == 1
