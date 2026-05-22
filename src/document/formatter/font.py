"""
Font Formatter Module
=====================
Font formatting utilities. Works with both python-docx Run objects
(raw text runs) and OxmlElement XML (for document body editing).
"""

from typing import Optional
from docx.shared import Pt, RGBColor
from docx.text.run import Run
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from src.core.logger import get_logger

logger = get_logger(__name__)


class FontFormatter:
    """Formats font properties for text runs."""

    DEFAULT_FONT = "Calibri"
    DEFAULT_SIZE = 11

    @staticmethod
    def format(
        run: Run,
        font_name: str = None,
        font_size: int = None,
        bold: bool = None,
        italic: bool = None,
        underline: bool = None,
        color: str = None,
        font_color: RGBColor = None
    ):
        """Apply font formatting to a run."""
        font = run.font

        if font_name:
            font.name = font_name
        else:
            font.name = FontFormatter.DEFAULT_FONT

        if font_size:
            font.size = Pt(font_size)
        else:
            font.size = Pt(FontFormatter.DEFAULT_SIZE)

        if bold is not None:
            font.bold = bold

        if italic is not None:
            font.italic = italic

        if underline is not None:
            font.underline = underline

        if color:
            font.color.rgb = FontFormatter._parse_color(color)
        elif font_color:
            font.color.rgb = font_color

    @staticmethod
    def _parse_color(color_str: str) -> RGBColor:
        """Parse color string to RGBColor."""
        if color_str.startswith('#'):
            color_str = color_str[1:]

        if len(color_str) == 6:
            r = int(color_str[0:2], 16)
            g = int(color_str[2:4], 16)
            b = int(color_str[4:6], 16)
            return RGBColor(r, g, b)

        return RGBColor(0, 0, 0)

    @staticmethod
    def format_title(run: Run):
        """Format title text."""
        FontFormatter.format(run, font_name="Calibri", font_size=28, bold=True, color="#003366")

    @staticmethod
    def format_heading(run: Run, level: int = 1):
        """Format heading text."""
        sizes = {1: 24, 2: 20, 3: 16}
        FontFormatter.format(run, font_name="Calibri", font_size=sizes.get(level, 16), bold=True)

    @staticmethod
    def format_body(run: Run):
        """Format body text."""
        FontFormatter.format(run, font_name="Calibri", font_size=11)

    @staticmethod
    def format_caption(run: Run):
        """Format caption text."""
        FontFormatter.format(run, font_name="Calibri", font_size=10, italic=True)

    @staticmethod
    def copy_style(source_run: Run, target_run: Run):
        """Copy font style from source to target."""
        target_run.font.name = source_run.font.name
        target_run.font.size = source_run.font.size
        target_run.font.bold = source_run.font.bold
        target_run.font.italic = source_run.font.italic
        target_run.font.underline = source_run.font.underline
        if source_run.font.color and source_run.font.color.rgb:
            target_run.font.color.rgb = source_run.font.color.rgb

    @staticmethod
    def format_run_xml(
        font_name: str = None,
        font_size: int = None,
        bold: bool = None,
        italic: bool = None,
        underline: bool = None,
        color: str = None,
    ) -> OxmlElement:
        """Create a w:rPr OxmlElement with the specified font properties."""
        rPr = OxmlElement('w:rPr')
        name = font_name or FontFormatter.DEFAULT_FONT
        rFonts = OxmlElement('w:rFonts')
        rFonts.set(qn('w:ascii'), name)
        rFonts.set(qn('w:hAnsi'), name)
        rFonts.set(qn('w:cs'), name)
        rPr.append(rFonts)
        size = font_size or FontFormatter.DEFAULT_SIZE
        sz = OxmlElement('w:sz')
        sz.set(qn('w:val'), str(int(size * 2)))
        rPr.append(sz)
        szCs = OxmlElement('w:szCs')
        szCs.set(qn('w:val'), str(int(size * 2)))
        rPr.append(szCs)
        if bold:
            b = OxmlElement('w:b')
            rPr.append(b)
        if italic:
            i = OxmlElement('w:i')
            rPr.append(i)
        if underline:
            u = OxmlElement('w:u')
            u.set(qn('w:val'), 'single')
            rPr.append(u)
        if color:
            c = OxmlElement('w:color')
            c.set(qn('w:val'), color.lstrip('#'))
            rPr.append(c)
        return rPr

    @staticmethod
    def format_paragraph_xml(
        alignment: str = None,
        space_before: int = None,
        space_after: int = None,
        line_spacing: float = None,
        first_line_indent: float = None,
    ) -> Optional[OxmlElement]:
        """Create a w:pPr OxmlElement with the specified paragraph properties."""
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