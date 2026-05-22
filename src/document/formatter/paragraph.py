"""
Paragraph Formatter Module
==========================
Paragraph formatting utilities.
"""

from typing import Optional
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.text.paragraph import Paragraph

from src.core.logger import get_logger

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
        spaces_before = {1: 12, 2: 6, 3: 3}
        ParagraphFormatter.format(
            paragraph,
            space_before=spaces_before.get(level, 6),
            space_after=6
        )

    @staticmethod
    def format_body(paragraph: Paragraph):
        """Format body paragraph."""
        ParagraphFormatter.format(
            paragraph,
            space_after=6,
            line_spacing=1.15
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