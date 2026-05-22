"""Context Assembler — retrieves, reranks, and assembles relevant context for generation.

Architecture:
    Retriever (injectable)  →  Dedup  →  Token Budget  →  Formatted Context

The retriever is abstracted behind BaseRetriever, so any search strategy
(hybrid, dense-only, external API) can be swapped in.
"""

from typing import List, Dict, Optional
from src.core.logger import get_logger
from .base import BaseRetriever, HybridRetriever

logger = get_logger(__name__)


class ContextAssembler:
    """Assembles relevant context chunks for section generation.

    Delegates retrieval to an injectable BaseRetriever, then applies
    deduplication, token-budget limiting, and formatting.

    For each section query:
    1. Retrieves via injected retriever
    2. Deduplicates by content hash
    3. Applies token budget
    4. Returns structured context
    """

    def __init__(self, retriever: Optional[BaseRetriever] = None,
                 top_k: int = 8,
                 max_tokens: int = 4096):
        self._retriever = retriever or HybridRetriever()
        self._top_k = top_k
        self._max_tokens = max_tokens

    def set_retriever(self, retriever: BaseRetriever):
        self._retriever = retriever

    def index_knowledge(self, chunks: List[Dict]):
        self._retriever.index_chunks(chunks)
        logger.info(f"ContextAssembler indexed {len(chunks)} knowledge chunks")

    def is_ready(self) -> bool:
        return self._retriever.is_ready()

    def retrieve_context(self, query: str, top_k: Optional[int] = None) -> Dict:
        if not self._retriever.is_ready():
            return self._empty_result()

        k = top_k or self._top_k
        results = self._retriever.retrieve(query, k)
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

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "chunks": [], "context_text": "", "sources": [],
            "total_chunks": 0, "avg_score": 0.0,
        }
