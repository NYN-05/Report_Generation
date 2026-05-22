import os
import uuid
from typing import List, Dict, Optional
from src.core.logger import get_logger

logger = get_logger(__name__)


class VectorStore:
    """Wrapper around ChromaDB for storing and retrieving document chunks."""

    def __init__(self, collection_name: str = "report_knowledge",
                 persist_dir: str = None):
        self.collection_name = collection_name
        self.persist_dir = persist_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "cache", "vectordb"
        )
        self._client = None
        self._collection = None
        self._available = False
        self._init_store()

    def _init_store(self):
        try:
            import chromadb
            from chromadb.config import Settings
            os.makedirs(self.persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self._available = True
            count = self._collection.count()
            logger.info(f"VectorStore initialized: {self.collection_name} ({count} docs)")
        except Exception as e:
            logger.warning(f"VectorStore unavailable: {e}")

    def is_available(self) -> bool:
        return self._available

    def add_chunks(self, chunks: List[Dict]) -> int:
        if not self._available or not chunks:
            return 0
        ids = []
        documents = []
        metadatas = []
        for ch in chunks:
            cid = str(uuid.uuid4())
            ids.append(cid)
            documents.append(ch.get("text", ""))
            metadatas.append({
                "heading": ch.get("heading", ""),
                "source": ch.get("source", ""),
                "chunk_index": ch.get("chunk_index", 0),
            })
        try:
            embeddings = None
            if "embedding" in chunks[0]:
                embeddings = [ch["embedding"] for ch in chunks]
            self._collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )
            logger.info(f"Added {len(chunks)} chunks to vector store")
            return len(chunks)
        except Exception as e:
            logger.error(f"Failed to add chunks: {e}")
            return 0

    def search(self, query: str, n_results: int = 5,
               where: Optional[Dict] = None) -> List[Dict]:
        if not self._available:
            return []
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
            )
            return self._format_results(results)
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def search_by_vector(self, embedding: List[float], n_results: int = 5) -> List[Dict]:
        if not self._available:
            return []
        try:
            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
            )
            return self._format_results(results)
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def count(self) -> int:
        if not self._available:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0

    def delete_collection(self):
        if not self._available:
            return
        try:
            self._client.delete_collection(self.collection_name)
            self._collection = None
            logger.info(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")

    def _format_results(self, results) -> List[Dict]:
        formatted = []
        if not results or not results.get("ids"):
            return formatted
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i] if results.get("documents") else "",
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                "distance": results["distances"][0][i] if results.get("distances") else 0.0,
            })
        return formatted
