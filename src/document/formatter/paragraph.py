"""
Paragraph Formatter Module
==========================
Paragraph formatting utilities for both python-docx Paragraph objects
and OxmlElement XML (for document body editing).
"""

from typing import Optional
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.text.paragraph import Paragraph
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from src.core.logger import get_logger
from src.document.styles import StyleManager

logger = get_logger(__name__)


class ParagraphFormatter:
    """Formats paragraph properties."""

    @staticmethod
    def format(
        paragraph: Paragraph,
        alignment: WD_ALIGN_PARAGRAPH = None,
        space_before: int = None,
        space_after: int = None,
        line_spacing: float = None,
        first_line_indent: float = None
    ):
        """Apply paragraph formatting."""
        pf = paragraph.paragraph_format

        if alignment:
            pf.alignment = alignment

        if space_before is not None:
            pf.space_before = Pt(space_before)

        if space_after is not None:
            pf.space_after = Pt(space_after)

        if line_spacing:
            pf.line_spacing = line_spacing

        if first_line_indent is not None:
            pf.first_line_indent = Inches(first_line_indent / 72)

    @staticmethod
    def format_center(paragraph: Paragraph):
        """Center align paragraph."""
        ParagraphFormatter.format(paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER)

    @staticmethod
    def format_justify(paragraph: Paragraph):
        """Justify paragraph."""
        ParagraphFormatter.format(paragraph, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY)

    @staticmethod
    def format_left(paragraph: Paragraph):
        """Left align paragraph."""
        ParagraphFormatter.format(paragraph, alignment=WD_ALIGN_PARAGRAPH.LEFT)

    @staticmethod
    def format_heading(paragraph: Paragraph, level: int = 1):
        """Format heading paragraph."""
        s = StyleManager.get_instance().get_styles()
        h = s.get_heading(level)
        ParagraphFormatter.format(
            paragraph,
            space_before=h.space_before,
            space_after=h.space_after
        )

    @staticmethod
    def format_body(paragraph: Paragraph):
        """Format body paragraph."""
        s = StyleManager.get_instance().get_styles()
        ParagraphFormatter.format(
            paragraph,
            space_after=s.content.space_after,
            line_spacing=s.content.line_spacing
        )

    @staticmethod
    def format_list_item(paragraph: Paragraph):
        """Format list item paragraph."""
        ParagraphFormatter.format(
            paragraph,
            first_line_indent=0.5,
            space_after=3
        )

    @staticmethod
    def copy_style(source_para: Paragraph, target_para: Paragraph):
        """Copy paragraph style from source to target."""
        source_pf = source_para.paragraph_format
        target_pf = target_para.paragraph_format

        target_pf.alignment = source_pf.alignment
        target_pf.space_before = source_pf.space_before
        target_pf.space_after = source_pf.space_after
        target_pf.line_spacing = source_pf.line_spacing
        target_pf.first_line_indent = source_pf.first_line_indent

    @staticmethod
    def format_paragraph_xml(
        alignment: str = None,
        space_before: int = None,
        space_after: int = None,
        line_spacing: float = None,
        first_line_indent: float = None,
    ) -> Optional[OxmlElement]:
        """Create a w:pPr OxmlElement with paragraph formatting."""
        pPr = OxmlElement('w:pPr')
        has_content = False
        if alignment:
            jc = OxmlElement('w:jc')
            jc.set(qn('w:val'), alignment)
            pPr.append(jc)
            has_content = True
        spacing = OxmlElement('w:spacing')
        has_spacing = False
        if space_before is not None:
            spacing.set(qn('w:before'), str(int(space_before * 20)))
            has_spacing = True
        if space_after is not None:
            spacing.set(qn('w:after'), str(int(space_after * 20)))
            has_spacing = True
        if line_spacing is not None:
            spacing.set(qn('w:line'), str(int(line_spacing * 240)))
            spacing.set(qn('w:lineRule'), 'auto')
            has_spacing = True
        if has_spacing:
            pPr.append(spacing)
            has_content = True
        if first_line_indent is not None:
            ind = OxmlElement('w:ind')
            ind.set(qn('w:firstLine'), str(int(first_line_indent * 20)))
            pPr.append(ind)
            has_content = True
        return pPr if has_content else None