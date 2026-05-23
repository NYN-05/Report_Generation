import asyncio
from typing import Dict, List, Optional, Callable, Any
from src.core.logger import get_logger

logger = get_logger(__name__)


class AsyncRetrieval:
    def __init__(self, max_concurrent: int = 4):
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def retrieve(self, query: str, retriever_fn: Callable,
                        top_k: int = 8) -> Dict:
        async with self._semaphore:
            if asyncio.iscoroutinefunction(retriever_fn):
                return await retriever_fn(query, top_k)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, retriever_fn, query, top_k)

    async def retrieve_batch(self, queries: List[str],
                              retriever_fn: Callable,
                              top_k: int = 8) -> Dict[str, Dict]:
        tasks = [self.retrieve(q, retriever_fn, top_k) for q in queries]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        results = {}
        for query, result in zip(queries, results_list):
            if isinstance(result, Exception):
                logger.warning(f"Async retrieval failed for '{query[:50]}': {result}")
                results[query] = {"chunks": [], "context_text": ""}
            else:
                results[query] = result
        logger.info(f"Async batch retrieved {len(queries)} queries")
        return results

    def retrieve_batch_sync(self, queries: List[str],
                              retriever_fn: Callable,
                              top_k: int = 8) -> Dict[str, Dict]:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.retrieve_batch(queries, retriever_fn, top_k)
            )
        finally:
            loop.close()
