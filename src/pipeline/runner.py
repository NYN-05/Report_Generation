"""
Pipeline Runner Module
======================
Executes pipelines with logging and error handling.
"""

import time
from typing import Optional, Any

from .base import BasePipeline, PipelineResult
from src.core.logger import get_logger

logger = get_logger(__name__)


class PipelineRunner:
    """Runs pipelines with logging and error handling."""

    def __init__(self):
        self._current_pipeline: Optional[BasePipeline] = None

    def run(
        self,
        pipeline: BasePipeline,
        input_data: Any,
        **kwargs
    ) -> PipelineResult:
        """Run a pipeline and return result."""
        self._current_pipeline = pipeline
        start_time = time.perf_counter()

        try:
            pipeline.on_start(input_data)

            if not pipeline.validate_input(input_data):
                return PipelineResult(
                    success=False,
                    error="Input validation failed",
                    execution_time=time.perf_counter() - start_time
                )

            result = pipeline.execute(input_data, **kwargs)
            result.execution_time = time.perf_counter() - start_time

            pipeline.on_complete(result)
            return result

        except Exception as e:
            execution_time = time.perf_counter() - start_time
            logger.error(f"Pipeline execution failed: {e}")

            pipeline.on_error(e)

            return PipelineResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    async def run_async(
        self,
        pipeline: BasePipeline,
        input_data: Any,
        **kwargs
    ) -> PipelineResult:
        """Run a pipeline asynchronously."""
        import asyncio

        return await asyncio.to_thread(self.run, pipeline, input_data, **kwargs)

    def run_chain(
        self,
        pipelines: list,
        input_data: Any
    ) -> PipelineResult:
        """Run a chain of pipelines sequentially."""
        current_data = input_data
        last_result = None

        for pipeline in pipelines:
            result = self.run(pipeline, current_data)

            if not result.success:
                return result

            current_data = result.data
            last_result = result

        return last_result or PipelineResult(success=False, error="No pipelines executed")

    def get_current_pipeline(self) -> Optional[BasePipeline]:
        """Get the current executing pipeline."""
        return self._current_pipeline