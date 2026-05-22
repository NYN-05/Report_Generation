from typing import List, Optional
from src.core.logger import get_logger

logger = get_logger(__name__)


class EmbeddingProvider:
    """Interface for generating text embeddings."""

    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        try:
            from langchain_ollama import OllamaEmbeddings
            self._client = OllamaEmbeddings(model=self.model)
            self._available = True
            logger.info(f"Embedding provider initialized: {self.model}")
        except ImportError:
            try:
                from langchain_community.embeddings import OllamaEmbeddings
                self._client = OllamaEmbeddings(model=self.model)
                self._available = True
                logger.info(f"Embedding provider initialized (fallback): {self.model}")
            except ImportError:
                logger.warning("langchain-ollama not available, embeddings disabled")

    def is_available(self) -> bool:
        return self._available

    def embed(self, text: str) -> Optional[List[float]]:
        if not self._available:
            return None
        try:
            return self._client.embed_query(text)
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        if not self._available:
            return None
        try:
            return self._client.embed_documents(texts)
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return None

    def embed_chunks(self, chunks: List[dict]) -> List[dict]:
        texts = [c["text"] for c in chunks]
        vectors = self.embed_batch(texts)
        if vectors is None:
            return chunks
        for chunk, vec in zip(chunks, vectors):
            chunk["embedding"] = vec
        return chunks
