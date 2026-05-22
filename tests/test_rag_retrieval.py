"""Tests for RAG retrieval: ContextAssembler, HybridSearch fix, Reranker."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestHybridSearchFix:
    """Verify that score normalization is fixed (no negative scores)."""

    def test_rrf_merging_no_negative_scores(self):
        from src.retrieval import HybridSearch
        hs = HybridSearch()
        bm25_results = [
            {"text": "Machine learning is a subset of AI.", "score": 12.5, "metadata": {"heading": "Intro"}},
            {"text": "Deep learning uses neural networks.", "score": 8.3, "metadata": {"heading": "Methods"}},
        ]
        vector_results = [
            {"text": "Machine learning is a subset of AI.", "distance": 0.15},
            {"text": "Neural networks require large datasets.", "distance": 1.85},
        ]
        merged = hs._merge_results_rrf(bm25_results, vector_results, n=5)
        assert len(merged) >= 2
        for r in merged:
            assert r.get("score", -1) >= 0, f"Negative score found: {r['score']}"
            assert r.get("score", 2) <= 1.0, f"Score > 1.0 found: {r['score']}"

    def test_normalize_vector_score(self):
        from src.retrieval.search import HybridSearch
        hs = HybridSearch()
        assert hs._normalize_vector_score(0.0) == 1.0
        assert hs._normalize_vector_score(1.0) == 0.5
        assert hs._normalize_vector_score(2.0) == 0.0
        assert 0 < hs._normalize_vector_score(0.5) < 1

    def test_normalize_bm25_score(self):
        from src.retrieval.search import HybridSearch
        hs = HybridSearch()
        assert hs._normalize_bm25_score(10, 0, 20) == 0.5
        assert hs._normalize_bm25_score(0, 0, 20) == 0.0
        assert hs._normalize_bm25_score(20, 0, 20) == 1.0

    def test_hybrid_search_no_vector_store(self):
        from src.retrieval import HybridSearch
        hs = HybridSearch()
        hs.index_chunks([
            {"text": "AI is transforming industries.", "heading": "Intro", "source": "test.txt"},
            {"text": "Machine learning enables computers to learn.", "heading": "Methods", "source": "test.txt"},
        ])
        results = hs.search("machine learning", n_results=2)
        assert len(results) > 0
        for r in results:
            assert "score" in r
            assert r["score"] >= 0


class TestReranker:
    """Test the real reranker implementation."""

    def test_fallback_rerank(self):
        from src.retrieval import Reranker
        reranker = Reranker()
        results = [
            {"text": "Machine learning is transforming healthcare."},
            {"text": "Quantum computing advances in physics."},
        ]
        reranked = reranker.rerank("machine learning healthcare", results, top_n=2)
        assert len(reranked) == 2
        for r in reranked:
            assert "rerank_score" in r
            assert 0 <= r["rerank_score"] <= 1

    def test_rerank_ordering(self):
        from src.retrieval import Reranker
        reranker = Reranker()
        results = [
            {"text": "Machine learning for healthcare diagnosis."},
            {"text": "Weather patterns in the Pacific region."},
            {"text": "Deep learning in medical imaging analysis."},
        ]
        reranked = reranker.rerank("AI healthcare diagnosis", results, top_n=3)
        assert reranked[0]["rerank_score"] >= reranked[-1]["rerank_score"]

    def test_rerank_no_results(self):
        from src.retrieval import Reranker
        reranker = Reranker()
        assert reranker.rerank("test", []) == []


class TestContextAssembler:
    """Test the ContextAssembler retrieval and assembly."""

    def test_assembly_empty_when_no_knowledge(self):
        from src.retrieval import ContextAssembler
        ca = ContextAssembler()
        assert not ca.is_ready()
        result = ca.retrieve_context("test query")
        assert result["total_chunks"] == 0
        assert result["context_text"] == ""

    def test_assembly_with_knowledge(self):
        from src.retrieval import ContextAssembler
        ca = ContextAssembler(top_k=5, max_tokens=1000)
        chunks = [
            {"text": "Artificial intelligence transforms industries.", "heading": "Introduction", "source": "doc1.txt"},
            {"text": "Machine learning algorithms improve with data.", "heading": "Methods", "source": "doc1.txt"},
            {"text": "Neural networks require large datasets to train effectively.", "heading": "Results", "source": "doc2.txt"},
            {"text": "The history of computing dates back centuries.", "heading": "Background", "source": "doc3.txt"},
        ]
        ca.index_knowledge(chunks)
        assert ca.is_ready()

        result = ca.retrieve_context("machine learning and AI", top_k=3)
        assert result["total_chunks"] > 0
        assert len(result["context_text"]) > 0
        assert len(result["sources"]) > 0
        assert result["avg_score"] >= 0

    def test_deduplication(self):
        from src.retrieval import ContextAssembler
        ca = ContextAssembler()
        results = [
            {"text": "Artificial Intelligence is transforming industries across healthcare, finance, and transportation sectors worldwide.", "metadata": {"heading": "Intro", "source": "a.txt"}},
            {"text": "Artificial Intelligence is transforming industries across healthcare, finance, and transportation sectors worldwide.", "metadata": {"heading": "Intro", "source": "a.txt"}},
        ]
        deduped = ca._deduplicate(results)
        assert len(deduped) == 1

    def test_token_budget(self):
        from src.retrieval import ContextAssembler
        ca = ContextAssembler(max_tokens=100)
        results = [
            {"text": "A" * 1000},
            {"text": "B" * 1000},
            {"text": "C" * 1000},
        ]
        budgeted = ca._apply_token_budget(results)
        total_chars = sum(len(r.get("text", "")) for r in budgeted)
        assert total_chars <= 100 * 4

    def test_format_context(self):
        from src.retrieval import ContextAssembler
        ca = ContextAssembler()
        results = [
            {"text": "AI transforms healthcare.", "rerank_score": 0.95, "metadata": {"heading": "Intro", "source": "doc.txt"}},
        ]
        formatted = ca._format_context(results)
        assert "Context Chunk 1" in formatted
        assert "relevance: 0.95" in formatted
        assert "Section: Intro" in formatted


class TestRAGIntegration:
    """Test that RAG is wired into the pipeline correctly."""

    def test_scratch_pipeline_rag_flag(self):
        from src.pipeline.generation.scratch import ScratchPipeline
        pipeline = ScratchPipeline(knowledge_dir=None)
        assert pipeline._context_assembler is None or not pipeline._context_assembler.is_ready()
