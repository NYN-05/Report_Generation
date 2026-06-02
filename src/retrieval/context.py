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

_TIKTOKEN_ENCODING = None


def _get_tokenizer():
    """Get tiktoken encoder with lazy loading and fallback to character count."""
    global _TIKTOKEN_ENCODING
    if _TIKTOKEN_ENCODING is not None:
        return _TIKTOKEN_ENCODING
    try:
        import tiktoken
        _TIKTOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")
        logger.info("tiktoken initialized for accurate token counting")
        return _TIKTOKEN_ENCODING
    except (ImportError, Exception) as e:
        logger.debug(f"tiktoken not available, using character estimation: {e}")
        return None


def count_tokens(text: str) -> int:
    """Count tokens accurately using tiktoken, falling back to 4x char estimate."""
    enc = _get_tokenizer()
    if enc:
        return len(enc.encode(text))
    return len(text) // 4


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
        total_tokens = 0
        overhead_per_chunk = 50  # metadata overhead
        for r in results:
            text = r.get("text", "")
            chunk_tokens = count_tokens(text) + overhead_per_chunk
            if total_tokens + chunk_tokens > self._max_tokens:
                remaining = self._max_tokens - total_tokens
                if remaining > 50:
                    # Truncate at token boundary using char estimate as fallback
                    char_ratio = len(text) / max(count_tokens(text), 1)
                    truncated_chars = int(remaining * char_ratio)
                    if truncated_chars > 200:
                        r["text"] = text[:truncated_chars]
                        r["truncated"] = True
                        budgeted.append(r)
                break
            budgeted.append(r)
            total_tokens += chunk_tokens
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
