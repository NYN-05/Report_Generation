"""
Pipeline Module
===============
Execution pipelines.
"""

from .base import BasePipeline, PipelineResult, PipelineRegistry
from .runner import PipelineRunner
from .generation.scratch import ScratchPipeline
from .generation.template import TemplatePipeline
from .generator import ReportGeneratorPipeline
from .export.pdf import PDFExportPipeline
from .export.factory import ExportFactory

__all__ = [
    "BasePipeline",
    "PipelineResult",
    "PipelineRegistry",
    "PipelineRunner",
    "ScratchPipeline",
    "TemplatePipeline",
    "ReportGeneratorPipeline",
    "PDFExportPipeline",
    "ExportFactory",
]