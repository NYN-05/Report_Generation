import asyncio
from typing import Dict, List, Optional, Callable, Any, Tuple
from src.core.logger import get_logger

logger = get_logger(__name__)


class AsyncGeneration:
    def __init__(self, max_concurrent: int = 3):
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def generate_section(self, section_type: str, topic: str,
                                 generator_fn: Callable) -> Tuple:
        async with self._semaphore:
            if asyncio.iscoroutinefunction(generator_fn):
                return await generator_fn(section_type, topic)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, generator_fn, section_type, topic
            )

    async def generate_all(self, section_types: List[str], topic: str,
                            generator_fn: Callable) -> Dict[str, Any]:
        tasks = [
            self.generate_section(st, topic, generator_fn)
            for st in section_types
        ]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        results = {}
        for st, result in zip(section_types, results_list):
            if isinstance(result, Exception):
                logger.warning(f"Async generation failed for '{st}': {result}")
                results[st] = None
            else:
                results[st] = result
        logger.info(f"Async generated {len(section_types)} sections")
        return results

    def generate_all_sync(self, section_types: List[str], topic: str,
                            generator_fn: Callable) -> Dict[str, Any]:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.generate_all(section_types, topic, generator_fn)
            )
        finally:
            loop.close()
