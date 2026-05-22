from typing import List, Dict, Optional
from .parser import DocumentParser
from .chunker import SemanticChunker
from .embeddings import EmbeddingProvider
from .store import VectorStore
from src.core.logger import get_logger

logger = get_logger(__name__)


class IngestionPipeline:
    """End-to-end pipeline: file(s) → parse → chunk → embed → store."""

    def __init__(self, collection_name: str = "report_knowledge",
                 persist_dir: str = None):
        self.parser = DocumentParser()
        self.chunker = SemanticChunker()
        self.embeddings = EmbeddingProvider()
        self.store = VectorStore(collection_name=collection_name, persist_dir=persist_dir)
        self._current_docs = []

    def ingest_file(self, filepath: str) -> int:
        text = self.parser.parse(filepath)
        if not text:
            return 0
        chunks = self.chunker.chunk(text, source=filepath)
        if self.embeddings.is_available():
            chunks = self.embeddings.embed_chunks(chunks)
        count = self.store.add_chunks(chunks)
        logger.info(f"Ingested {filepath}: {count} chunks")
        return count

    def ingest_directory(self, dirpath: str) -> int:
        docs = self.parser.parse_directory(dirpath)
        total = 0
        for doc in docs:
            chunks = self.chunker.chunk(doc["text"], source=doc["filename"])
            if self.embeddings.is_available():
                chunks = self.embeddings.embed_chunks(chunks)
            count = self.store.add_chunks(chunks)
            total += count
        logger.info(f"Ingested directory {dirpath}: {total} total chunks")
        return total

    def search(self, query: str, n_results: int = 5) -> List[Dict]:
        return self.store.search(query, n_results=n_results)

    def count(self) -> int:
        return self.store.count()

    def is_available(self) -> bool:
        return self.store.is_available()
