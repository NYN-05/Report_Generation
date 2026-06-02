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
            
            # Import document generator v2
            from src.document.docx_v2_generator import DOCXV2Generator
            from src.generator.content_blocks import (
                SectionContent, ParagraphBlock, BulletListBlock, 
                TableBlock, TableRow
            )
            
            # Convert legacy format to SectionContent format
            sections = self._convert_legacy_to_sections(input_data)
            
            # Generate document with v2 generator
            docx_gen = DOCXV2Generator()
            output_path = docx_gen.generate(
                title=input_data.get('title', 'Report'),
                author=input_data.get('author', 'AI Generator'),
                sections=sections,
                output_path=os.path.join(self.output_dir, "output.docx"),
                validate=True
            )
            
            logger.info(f"Report generated: {output_path}")
            
            return PipelineResult(
                success=True,
                output_path=output_path,
                data=input_data
            )
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            return PipelineResult(
                success=False,
                error=str(e)
            )
    
    def _convert_legacy_to_sections(self, input_data: Dict) -> list:
        """
        Convert legacy content format to SectionContent blocks.
        
        Args:
            input_data: Dict with legacy format keys
            
        Returns:
            List of SectionContent objects
        """
        from src.generator.content_blocks import (
            SectionContent, ParagraphBlock, BulletListBlock, BulletItem,
            TableBlock, TableRow, HeadingBlock, SourceRequiredBlock
        )
        
        sections = []
        
        # Executive Summary section
        exec_summary = input_data.get('executive_summary', 'No summary available.')
        if exec_summary and exec_summary != 'No summary available.':
            exec_section = SectionContent(heading="Executive Summary")
            exec_section.add_block(ParagraphBlock(
                text=exec_summary,
                word_count=len(exec_summary.split()),
                topic_sentence=exec_summary.split('.')[0] + '.' if '.' in exec_summary else exec_summary[:50] + '...',
                evidence_source="generated"
            ))
            sections.append(exec_section)
        
        # Introduction section
        intro = input_data.get('introduction', 'No introduction available.')
        if intro and intro != 'No introduction available.':
            intro_section = SectionContent(heading="Introduction")
            intro_section.add_block(ParagraphBlock(
                text=intro,
                word_count=len(intro.split()),
                topic_sentence=intro.split('.')[0] + '.' if '.' in intro else intro[:50] + '...',
                evidence_source="generated"
            ))
            sections.append(intro_section)
        
        # Analysis section (contains threats table and ML methods)
        analysis_section = SectionContent(heading="Analysis")
        
        # Add threats table if present
        threats = input_data.get('threats', [])
        if threats:
            # Convert threats to table format
            table_data = []
            for threat in threats:
                if isinstance(threat, (list, tuple)) and len(threat) >= 2:
                    table_data.append([str(threat[0]), str(threat[1])])
                elif isinstance(threat, dict):
                    table_data.append([str(threat.get('topic', '')), str(threat.get('description', ''))])
                else:
                    table_data.append([str(threat), ""])
            
            if table_data:
                headers = ['Topic', 'Description']
                rows = [TableRow(cells=row) for row in table_data]
                analysis_section.add_block(TableBlock(
                    caption="Threats Analysis",
                    headers=headers,
                    rows=rows
                ))
        
        # Add ML methods as bullet list
        ml_methods = input_data.get('ml_methods', [])
        if ml_methods:
            bullet_items = []
            for method in ml_methods:
                bullet_items.append(BulletItem(
                    title=str(method),
                    description="",
                    evidence_source="generated"
                ))
            
            if bullet_items:
                analysis_section.add_block(BulletListBlock(
                    title="Key Methods",
                    items=bullet_items
                ))
        
        sections.append(analysis_section)
        
        # Case Studies section
        case_studies = input_data.get('case_studies', 'No case studies.')
        if case_studies and case_studies != 'No case studies.':
            case_section = SectionContent(heading="Case Studies")
            case_section.add_block(ParagraphBlock(
                text=str(case_studies),
                word_count=len(str(case_studies).split()),
                topic_sentence=str(case_studies).split('.')[0] + '.' if '.' in str(case_studies) else str(case_studies)[:50] + '...',
                evidence_source="generated"
            ))
            sections.append(case_section)
        
        # Future Trends section
        future_trends = input_data.get('future_trends', [])
        if future_trends:
            trends_section = SectionContent(heading="Future Trends")
            bullet_items = []
            for trend in future_trends:
                bullet_items.append(BulletItem(
                    title=str(trend),
                    description="",
                    evidence_source="generated"
                ))
            
            if bullet_items:
                trends_section.add_block(BulletListBlock(
                    title="Future Trends",
                    items=bullet_items
                ))
            sections.append(trends_section)
        
        # Conclusion section
        conclusion = input_data.get('conclusion', 'No conclusion.')
        if conclusion and conclusion != 'No conclusion.':
            conclusion_section = SectionContent(heading="Conclusion")
            conclusion_section.add_block(ParagraphBlock(
                text=conclusion,
                word_count=len(conclusion.split()),
                topic_sentence=conclusion.split('.')[0] + '.' if '.' in conclusion else conclusion[:50] + '...',
                evidence_source="generated"
            ))
            sections.append(conclusion_section)
        
        # If no sections were created, create a default section
        if not sections:
            default_section = SectionContent(heading="Report")
            default_section.add_block(ParagraphBlock(
                text="No content provided for report generation.",
                word_count=6,
                topic_sentence="No content provided",
                evidence_source="generated"
            ))
            sections.append(default_section)
        
        return sections

    def validate_input(self, input_data: Dict) -> bool:
        """Validate input has required fields."""
        required = ['title']
        for field in required:
            if field not in input_data or not input_data[field]:
                logger.error(f"Missing required field: {field}")
                return False
        return True