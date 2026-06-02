"""Retrieval quality benchmarks for RAG pipeline evaluation.

Provides standardized metrics: Recall@k, Precision@k, MRR, NDCG
to measure and compare retrieval strategies objectively.
"""

import math
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievalMetrics:
    """Standard retrieval quality metrics for a single query."""
    recall_at_k: float = 0.0
    precision_at_k: float = 0.0
    mrr: float = 0.0
    ndcg_at_k: float = 0.0
    total_relevant: int = 0
    retrieved_relevant: int = 0

    def to_dict(self) -> Dict:
        return {
            "recall_at_k": round(self.recall_at_k, 4),
            "precision_at_k": round(self.precision_at_k, 4),
            "mrr": round(self.mrr, 4),
            "ndcg_at_k": round(self.ndcg_at_k, 4),
            "total_relevant": self.total_relevant,
            "retrieved_relevant": self.retrieved_relevant,
        }


def dcg(relevances: List[float], k: int) -> float:
    """Compute Discounted Cumulative Gain at k."""
    relevances = relevances[:k]
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg(relevances: List[float], ideal_relevances: List[float], k: int) -> float:
    """Compute Normalized Discounted Cumulative Gain at k."""
    actual = dcg(relevances, k)
    ideal = dcg(ideal_relevances, k)
    return actual / ideal if ideal > 0 else 0.0


def evaluate_retrieval(
    query: str,
    retrieved: List[Dict],
    relevant_ids: set,
    k: int = 10,
    relevance_fn: Optional[Callable[[Dict], float]] = None,
) -> RetrievalMetrics:
    """Evaluate retrieval quality for a single query against known relevant documents.

    Args:
        query: The search query
        retrieved: List of retrieved chunks with 'id' field
        relevant_ids: Set of relevant document IDs
        k: Top-k cutoff
        relevance_fn: Optional function returning relevance grade [0,1] for each result

    Returns:
        RetrievalMetrics with all standard metrics computed
    """
    retrieved_at_k = retrieved[:k]
    total_relevant = len(relevant_ids)

    if total_relevant == 0:
        return RetrievalMetrics(total_relevant=0)

    # Count relevant retrieved
    retrieved_relevant = 0
    relevances = []
    first_relevant_rank = None

    for rank, doc in enumerate(retrieved_at_k):
        doc_id = doc.get("id", str(doc.get("text", ""))[:50])
        if doc_id in relevant_ids:
            retrieved_relevant += 1
            if first_relevant_rank is None:
                first_relevant_rank = rank + 1

        if relevance_fn:
            relevances.append(relevance_fn(doc))
        else:
            relevances.append(1.0 if doc_id in relevant_ids else 0.0)

    recall = retrieved_relevant / total_relevant if total_relevant > 0 else 0.0
    precision = retrieved_relevant / k
    reciprocal_rank = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
    ndcg_value = ndcg(relevances, sorted(relevances, reverse=True), k)

    return RetrievalMetrics(
        recall_at_k=recall,
        precision_at_k=precision,
        mrr=reciprocal_rank,
        ndcg_at_k=ndcg_value,
        total_relevant=total_relevant,
        retrieved_relevant=retrieved_relevant,
    )


def evaluate_retrieval_batch(
    queries: List[tuple],
    retriever_fn: Callable[[str, int], List[Dict]],
    k: int = 10,
) -> Dict:
    """Evaluate retrieval quality across multiple queries.

    Args:
        queries: List of (query, relevant_ids) tuples
        retriever_fn: Function that takes (query, top_k) and returns results
        k: Top-k cutoff

    Returns:
        Dict with averaged metrics across all queries
    """
    all_metrics = []
    for query, relevant_ids in queries:
        retrieved = retriever_fn(query, k)
        metrics = evaluate_retrieval(query, retrieved, relevant_ids, k)
        all_metrics.append(metrics)
        logger.info(
            f"Query '{query[:50]}': "
            f"Recall@{k}={metrics.recall_at_k:.3f}, "
            f"MRR={metrics.mrr:.3f}"
        )

    if not all_metrics:
        return {}

    avg_recall = sum(m.recall_at_k for m in all_metrics) / len(all_metrics)
    avg_precision = sum(m.precision_at_k for m in all_metrics) / len(all_metrics)
    avg_mrr = sum(m.mrr for m in all_metrics) / len(all_metrics)
    avg_ndcg = sum(m.ndcg_at_k for m in all_metrics) / len(all_metrics)

    return {
        "average_recall_at_k": round(avg_recall, 4),
        "average_precision_at_k": round(avg_precision, 4),
        "average_mrr": round(avg_mrr, 4),
        "average_ndcg_at_k": round(avg_ndcg, 4),
        "num_queries": len(all_metrics),
        "k": k,
        "per_query": [m.to_dict() for m in all_metrics],
    }
