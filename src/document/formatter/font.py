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
from src.document.styles import StyleManager

logger = get_logger(__name__)


class FontFormatter:
    """Formats font properties for text runs."""

    @staticmethod
    def _get_default_font():
        return StyleManager.get_instance().get_styles().content.font.name

    @staticmethod
    def _get_default_size():
        return int(StyleManager.get_instance().get_styles().content.font.size)

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
            font.name = FontFormatter._get_default_font()

        if font_size:
            font.size = Pt(font_size)
        else:
            font.size = Pt(FontFormatter._get_default_size())

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
        s = StyleManager.get_instance().get_styles()
        FontFormatter.format(run, font_name=s.cover_page.title_font.name, font_size=int(s.cover_page.title_font.size), bold=True, color="#003333")

    @staticmethod
    def format_heading(run: Run, level: int = 1):
        """Format heading text."""
        s = StyleManager.get_instance().get_styles()
        h = s.get_heading(level)
        FontFormatter.format(run, font_name=h.font.name, font_size=int(h.font.size), bold=True)

    @staticmethod
    def format_body(run: Run):
        """Format body text."""
        s = StyleManager.get_instance().get_styles()
        FontFormatter.format(run, font_name=s.content.font.name, font_size=int(s.content.font.size))

    @staticmethod
    def format_caption(run: Run):
        """Format caption text."""
        s = StyleManager.get_instance().get_styles()
        FontFormatter.format(run, font_name=s.content.font.name, font_size=max(8, int(s.content.font.size) - 2), italic=True)

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
        name = font_name or FontFormatter._get_default_font()
        rFonts = OxmlElement('w:rFonts')
        rFonts.set(qn('w:ascii'), name)
        rFonts.set(qn('w:hAnsi'), name)
        rFonts.set(qn('w:cs'), name)
        rPr.append(rFonts)
        size = font_size or int(FontFormatter._get_default_size())
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