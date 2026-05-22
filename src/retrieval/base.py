"""Abstract retrieval interfaces for dependency inversion."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class BaseRetriever(ABC):
    """Abstract interface for context retrieval.

    Any retriever implementation can be injected into ContextAssembler,
    enabling swap-in of dense, sparse, hybrid, or external API retrievers.
    """

    @abstractmethod
    def index_chunks(self, chunks: List[Dict]):
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        ...

    @abstractmethod
    def retrieve(self, query: str, top_k: int) -> List[Dict]:
        ...


class HybridRetriever(BaseRetriever):
    """Concrete retriever: hybrid search + cross-encoder reranking."""

    def __init__(self, vector_store=None,
                 model_name: str = "BAAI/bge-reranker-v2-m3",
                 top_k: int = 8):
        from .search import HybridSearch
        from .reranker import Reranker
        self._hybrid = HybridSearch(vector_store=vector_store)
        self._reranker = Reranker(model=model_name)
        self._top_k = top_k
        self._indexed = False

    def index_chunks(self, chunks: List[Dict]):
        self._hybrid.index_chunks(chunks)
        self._indexed = True

    def is_ready(self) -> bool:
        return self._indexed

    def retrieve(self, query: str, top_k: int) -> List[Dict]:
        results = self._hybrid.search(query, n_results=top_k * 2)
        results = self._reranker.rerank(query, results, top_n=top_k)
        return results


class DummyRetriever(BaseRetriever):
    """Minimal retriever for testing / dry-run."""

    def __init__(self):
        self._ready = False

    def index_chunks(self, chunks: List[Dict]):
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    def retrieve(self, query: str, top_k: int) -> List[Dict]:
        return []
