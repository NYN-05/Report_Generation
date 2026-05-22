"""
Style Extractor Module
======================
Extracts specific style properties.
"""

from typing import Dict, Any, Optional
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn

from src.core.logger import get_logger

logger = get_logger(__name__)


class StyleExtractor:
    """Extracts style properties from elements."""

    @staticmethod
    def extract_run_properties(run) -> Dict[str, Any]:
        """Extract properties from a text run."""
        props = {}

        if run.font:
            props['font_name'] = run.font.name
            props['font_size'] = run.font.size.pt if run.font.size else 11
            props['bold'] = run.font.bold
            props['italic'] = run.font.italic
            props['underline'] = run.font.underline

            if run.font.color and run.font.color.rgb:
                rgb = run.font.color.rgb
                props['color'] = f"#{rgb.r:02x}{rgb.g:02x}{rgb.b:02x}"

        return props

    @staticmethod
    def extract_paragraph_properties(paragraph) -> Dict[str, Any]:
        """Extract properties from a paragraph."""
        props = {}

        props['style_name'] = paragraph.style.name if paragraph.style else "Normal"

        pf = paragraph.paragraph_format
        props['alignment'] = str(pf.alignment) if pf.alignment else "left"
        props['space_before'] = pf.space_before.pt if pf.space_before else 0
        props['space_after'] = pf.space_after.pt if pf.space_after else 0
        props['line_spacing'] = pf.line_spacing if pf.line_spacing else 1.15
        props['first_line_indent'] = pf.first_line_indent.pt if pf.first_line_indent else 0

        return props

    @staticmethod
    def extract_table_cell_properties(cell) -> Dict[str, Any]:
        """Extract properties from a table cell."""
        props = {}

        tc = cell._element
        tc_pr = tc.find(qn('w:tcPr'))

        if tc_pr is not None:
            shd = tc_pr.find(qn('w:shd'))
            if shd is not None:
                fill = shd.get(qn('w:fill'))
                if fill:
                    props['background'] = f"#{fill}"

        tc_pf = cell.paragraphs[0].paragraph_format if cell.paragraphs else None
        if tc_pf:
            props['alignment'] = str(tc_pf.alignment) if tc_pf.alignment else "left"

        return props

    @staticmethod
    def extract_table_row_properties(row) -> Dict[str, Any]:
        """Extract properties from a table row."""
        tr_pr = row._element.find(qn('w:trPr'))

        props = {}
        if tr_pr is not None:
            tr_height = tr_pr.find(qn('w:trHeight'))
            if tr_height is not None:
                h = tr_height.get(qn('w:val'))
                props['height'] = int(h) if h else 0

        return props


def extract_style(element) -> Dict[str, Any]:
    """Convenience function to extract style from any element."""
    from docx.text.paragraph import Paragraph
    from docx.text.run import Run

    if isinstance(element, Paragraph):
        return StyleExtractor.extract_paragraph_properties(element)
    elif isinstance(element, Run):
        return StyleExtractor.extract_run_properties(element)

    return {}