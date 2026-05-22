"""
Base Pipeline Module
====================
Abstract pipeline base class and registry.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from src.core.logger import get_logger
from src.core.exceptions import PipelineException

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    """Result of pipeline execution."""
    success: bool
    output_path: str = ""
    data: Dict = field(default_factory=dict)
    error: str = ""
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "output_path": self.output_path,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat()
        }


class BasePipeline(ABC):
    """Abstract base class for pipelines."""

    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"pipeline.{name}")
        self._initialized = False

    @abstractmethod
    def execute(self, input_data: Any, **kwargs) -> PipelineResult:
        """Execute the pipeline."""
        pass

    def validate_input(self, input_data: Any) -> bool:
        """Validate input data."""
        return True

    def on_start(self, input_data: Any):
        """Hook called before execution."""
        self.logger.info(f"Starting pipeline: {self.name}")

    def on_complete(self, result: PipelineResult):
        """Hook called after execution."""
        self.logger.info(f"Pipeline complete: {self.name}, success={result.success}")

    def on_error(self, error: Exception):
        """Hook called on error."""
        self.logger.error(f"Pipeline error: {self.name}, error={error}")


class PipelineRegistry:
    """Registry of available pipelines."""

    _instance = None
    _pipelines: Dict[str, type] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, name: str, pipeline_class: type):
        """Register a pipeline class."""
        cls._pipelines[name.lower()] = pipeline_class
        logger.info(f"Registered pipeline: {name}")

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """Get pipeline class by name."""
        return cls._pipelines.get(name.lower())

    @classmethod
    def create(cls, name: str, **kwargs) -> Optional[BasePipeline]:
        """Create a pipeline instance."""
        pipeline_class = cls.get(name)
        if pipeline_class:
            return pipeline_class(**kwargs)
        return None

    @classmethod
    def list_pipelines(cls) -> list:
        """List all registered pipelines."""
        return list(cls._pipelines.keys())

    @classmethod
    def register_defaults(cls):
        """Register default pipelines."""
        from .generation.scratch import ScratchPipeline
        from .generation.template import TemplatePipeline
        from .export.pdf import PDFExportPipeline

        cls.register("scratch", ScratchPipeline)
        cls.register("template", TemplatePipeline)
        cls.register("pdf", PDFExportPipeline)