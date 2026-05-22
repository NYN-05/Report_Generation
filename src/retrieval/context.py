"""Context Assembler — retrieves, reranks, and assembles relevant context for generation.

Architecture:
    Section Query → Hybrid Search → Reranker → Dedup → Token Budget → Assembled Context
"""

from typing import List, Dict, Optional
from src.core.logger import get_logger
from src.retrieval.search import HybridSearch
from src.retrieval.reranker import Reranker

logger = get_logger(__name__)


class ContextAssembler:
    """Assembles relevant context chunks for section generation.

    For each section query:
    1. Performs hybrid search (BM25 + vector)
    2. Reranks results using CrossEncoder
    3. Deduplicates by content hash
    4. Applies token budget
    5. Returns structured context
    """

    def __init__(self, vector_store=None,
                 model_name: str = "BAAI/bge-reranker-v2-m3",
                 top_k: int = 8,
                 max_tokens: int = 4096):
        self._hybrid = HybridSearch(vector_store=vector_store)
        self._reranker = Reranker(model=model_name)
        self._top_k = top_k
        self._max_tokens = max_tokens
        self._chunks_indexed = False

    def index_knowledge(self, chunks: List[Dict]):
        """Index knowledge chunks for hybrid search."""
        self._hybrid.index_chunks(chunks)
        self._chunks_indexed = True
        logger.info(f"ContextAssembler indexed {len(chunks)} knowledge chunks")

    def is_ready(self) -> bool:
        return self._chunks_indexed

    def retrieve_context(self, query: str, top_k: Optional[int] = None) -> Dict:
        """Retrieve and assemble context for a section query.

        Returns:
            Dict with keys:
                - chunks: List[Dict] of relevant context chunks
                - context_text: str — formatted context for prompt injection
                - sources: List[str] — source documents
                - total_chunks: int
                - avg_score: float
        """
        if not self._chunks_indexed:
            return self._empty_result()

        k = top_k or self._top_k

        results = self._hybrid.search(query, n_results=k * 2)
        results = self._reranker.rerank(query, results, top_n=k)
        results = self._deduplicate(results)
        results = self._apply_token_budget(results)

        context_text = self._format_context(results)
        sources = list(set(
            r.get("metadata", {}).get("source", "") or ""
            for r in results
        ))
        scores = [r.get("rerank_score", r.get("score", 0)) for r in results]
        avg_score = sum(scores) / max(len(scores), 1)

        logger.info(
            f"Retrieved {len(results)} chunks for query '{query[:60]}' "
            f"from {len(sources)} sources (avg score: {avg_score:.3f})"
        )

        return {
            "chunks": results,
            "context_text": context_text,
            "sources": sources,
            "total_chunks": len(results),
            "avg_score": avg_score,
        }

    def _deduplicate(self, results: List[Dict]) -> List[Dict]:
        seen = set()
        deduped = []
        for r in results:
            text = r.get("text", "")
            content_hash = hash(text[:500])
            if content_hash not in seen:
                seen.add(content_hash)
                deduped.append(r)
        return deduped

    def _apply_token_budget(self, results: List[Dict]) -> List[Dict]:
        if not results:
            return results

        budgeted = []
        total_chars = 0
        char_budget = self._max_tokens * 4

        for r in results:
            text_len = len(r.get("text", "")) + 200
            if total_chars + text_len > char_budget:
                remaining = char_budget - total_chars
                if remaining > 200:
                    truncated = r.get("text", "")[:remaining]
                    r["text"] = truncated
                    r["truncated"] = True
                    budgeted.append(r)
                break
            budgeted.append(r)
            total_chars += text_len

        return budgeted

    def _format_context(self, results: List[Dict]) -> str:
        parts = []
        for i, r in enumerate(results):
            heading = r.get("metadata", {}).get("heading", "")
            source = r.get("metadata", {}).get("source", "")
            score = r.get("rerank_score", r.get("score", 0))
            header_parts = []
            if heading:
                header_parts.append(f"Section: {heading}")
            if source:
                header_parts.append(f"Source: {source}")
            header = f"[{', '.join(header_parts)}]" if header_parts else ""

            text = r.get("text", "")
            parts.append(
                f"--- Context Chunk {i + 1} (relevance: {score:.3f}) ---\n"
                f"{header}\n{text}"
            )

        return "\n\n".join(parts)

    def _empty_result(self) -> Dict:
        return {
            "chunks": [],
            "context_text": "",
            "sources": [],
            "total_chunks": 0,
            "avg_score": 0.0,
        }
