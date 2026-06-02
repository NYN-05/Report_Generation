"""Benchmark tests for RAG retrieval quality.

Tests measure recall, precision, MRR, and NDCG for the retrieval pipeline
to ensure retrieval quality does not regress.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestRetrievalBenchmarks:
    """Benchmark retrieval quality metrics."""

    def test_retrieval_metrics_perfect(self):
        """Perfect retrieval should give 1.0 for all metrics."""
        from src.retrieval.benchmarks import evaluate_retrieval

        retrieved = [
            {"id": "doc1", "text": "Relevant doc 1"},
            {"id": "doc2", "text": "Relevant doc 2"},
            {"id": "doc3", "text": "Relevant doc 3"},
        ]
        relevant = {"doc1", "doc2", "doc3"}

        metrics = evaluate_retrieval("query", retrieved, relevant, k=3)
        assert metrics.recall_at_k == 1.0
        assert metrics.precision_at_k == 1.0
        assert metrics.mrr == 1.0
        assert metrics.ndcg_at_k == 1.0

    def test_retrieval_metrics_no_relevant(self):
        """No relevant documents should give 0.0 for all metrics."""
        from src.retrieval.benchmarks import evaluate_retrieval

        retrieved = [
            {"id": "doc1", "text": "Unrelated 1"},
            {"id": "doc2", "text": "Unrelated 2"},
        ]
        relevant = {"doc999"}

        metrics = evaluate_retrieval("query", retrieved, relevant, k=3)
        assert metrics.recall_at_k == 0.0
        assert metrics.precision_at_k == 0.0
        assert metrics.mrr == 0.0

    def test_retrieval_metrics_partial(self):
        """Partial retrieval should give intermediate scores."""
        from src.retrieval.benchmarks import evaluate_retrieval

        retrieved = [
            {"id": "doc1", "text": "Relevant doc"},
            {"id": "doc2", "text": "Unrelated"},
            {"id": "doc3", "text": "Unrelated"},
        ]
        relevant = {"doc1", "doc_extra"}

        metrics = evaluate_retrieval("query", retrieved, relevant, k=3)
        assert metrics.recall_at_k == 0.5
        assert metrics.precision_at_k == pytest.approx(1/3)
        assert metrics.mrr == 1.0

    def test_retrieval_metrics_custom_relevance(self):
        """Custom relevance function should affect NDCG."""
        from src.retrieval.benchmarks import evaluate_retrieval

        retrieved = [
            {"id": "doc1", "text": "Perfect match", "score": 0.9},
            {"id": "doc2", "text": "Good match", "score": 0.7},
            {"id": "doc3", "text": "Weak match", "score": 0.3},
        ]
        relevant = {"doc1", "doc2", "doc3"}

        metrics = evaluate_retrieval(
            "query", retrieved, relevant, k=3,
            relevance_fn=lambda d: d.get("score", 0),
        )
        # NDCG should be 1.0 since ranking matches relevance order
        assert metrics.ndcg_at_k == 1.0
        assert metrics.recall_at_k == 1.0

    def test_batch_evaluation(self):
        """Batch evaluation should average metrics across queries."""
        from src.retrieval.benchmarks import evaluate_retrieval_batch

        queries = [
            ("AI query", {"doc1", "doc2"}),
            ("ML query", {"doc3"}),
        ]

        def mock_retriever(query, k):
            return [
                {"id": "doc1", "text": "AI doc"},
                {"id": "doc2", "text": "ML doc"},
                {"id": "doc3", "text": "Unrelated"},
            ]

        results = evaluate_retrieval_batch(queries, mock_retriever, k=3)
        assert results["num_queries"] == 2
        assert 0 < results["average_recall_at_k"] <= 1.0
        assert 0 < results["average_mrr"] <= 1.0
        assert len(results["per_query"]) == 2

    def test_dcg_computation(self):
        """Verify DCG computation is correct."""
        from src.retrieval.benchmarks import dcg

        # Perfect ranking of 3 relevant items
        assert dcg([1, 1, 1], 3) > 0
        # No relevant items
        assert dcg([0, 0, 0], 3) == 0.0
        # Single relevant at top
        assert dcg([1, 0, 0], 1) == 1.0

    def test_ndcg_computation(self):
        """Verify NDCG computation is correct."""
        from src.retrieval.benchmarks import ndcg

        # Perfect ranking
        assert ndcg([1, 1, 1], [1, 1, 1], 3) == 1.0
        # Imperfect ranking
        assert ndcg([0, 1, 0], [1, 1, 1], 3) < 1.0
        # No ideal
        assert ndcg([0, 0], [0, 0], 2) == 0.0
