"""
Report Generator Pipeline
==========================
Pipeline for generating Word documents.
"""

import os
from typing import Dict
from .base import BasePipeline, PipelineResult
from src.core.logger import get_logger


logger = get_logger(__name__)


class ReportGeneratorPipeline(BasePipeline):
    """Pipeline for generating Word documents."""
    
    def __init__(self, output_dir: str = "."):
        super().__init__("report_generator")
        self.output_dir = output_dir
        self._setup_output_dir()
    
    def _setup_output_dir(self):
        """Ensure output directory exists."""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def execute(self, input_data: Dict) -> PipelineResult:
        """
        Generate Word document from content.
        
        Args:
            input_data: Dict with keys: title, subtitle, author, date, 
                       toc_entries, executive_summary, introduction, 
                       threats, ml_methods, case_studies, future_trends, conclusion
        """
        try:
            logger.info(f"Generating report: {input_data.get('title', 'Untitled')}")
            
            # Import document generator
            from src.document.doc_generator import generate_document
            
            # Generate document with content
            success = generate_document(content=input_data)
            
            if success:
                output_path = os.path.join(self.output_dir, "output.docx")
                logger.info(f"Report generated: {output_path}")
                
                return PipelineResult(
                    success=True,
                    output_path=output_path,
                    data=input_data
                )
            else:
                return PipelineResult(
                    success=False,
                    error="Document generation failed"
                )
                
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            return PipelineResult(
                success=False,
                error=str(e)
            )
    
    def validate_input(self, input_data: Dict) -> bool:
        """Validate input has required fields."""
        required = ['title']
        for field in required:
            if field not in input_data or not input_data[field]:
                logger.error(f"Missing required field: {field}")
                return False
        return True