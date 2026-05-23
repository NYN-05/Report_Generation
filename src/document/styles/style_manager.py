from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger
from .document_styles import (
    DocumentStyles, FontStyle, ParagraphStyle, HeadingStyle,
    BulletStyle, TableStyle, FigureStyle, Alignment,
)

logger = get_logger(__name__)

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

WD_ALIGN_MAP = {
    Alignment.LEFT: WD_ALIGN_PARAGRAPH.LEFT if HAS_DOCX else None,
    Alignment.CENTER: WD_ALIGN_PARAGRAPH.CENTER if HAS_DOCX else None,
    Alignment.RIGHT: WD_ALIGN_PARAGRAPH.RIGHT if HAS_DOCX else None,
    Alignment.JUSTIFY: WD_ALIGN_PARAGRAPH.JUSTIFY if HAS_DOCX else None,
}


class StyleManager:
    _instance = None
    _styles: DocumentStyles = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._styles = DocumentStyles()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "StyleManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_styles(cls, styles: DocumentStyles):
        cls._styles = styles

    @classmethod
    def get_styles(cls) -> DocumentStyles:
        if cls._styles is None:
            cls._styles = DocumentStyles()
        return cls._styles

    @classmethod
    def apply_paragraph_style(cls, paragraph, style):
        if not HAS_DOCX:
            return
        pf = paragraph.paragraph_format
        if style.font:
            for run in paragraph.runs:
                run.font.name = style.font.name
                run.font.size = Pt(style.font.size)
                run.font.bold = style.font.bold
                run.font.italic = style.font.italic
                if style.font.color:
                    run.font.color.rgb = RGBColor(*cls._parse_color(style.font.color))
        pf.alignment = WD_ALIGN_MAP.get(style.alignment, WD_ALIGN_PARAGRAPH.JUSTIFY)
        pf.line_spacing = getattr(style, 'line_spacing', 1.5)
        sb = getattr(style, 'space_before', None)
        if sb is not None:
            pf.space_before = Pt(sb)
        sa = getattr(style, 'space_after', 6)
        pf.space_after = Pt(sa)
        fli = getattr(style, 'first_line_indent', None)
        if fli:
            pf.first_line_indent = Inches(fli)
        li = getattr(style, 'left_indent', None)
        if li:
            pf.left_indent = Inches(li)
        if getattr(style, 'keep_with_next', False):
            pPr = paragraph._p.get_or_add_pPr()
            keepNext = pPr.makeelement(qn('w:keepNext'), {})
            pPr.append(keepNext)

    @classmethod
    def apply_heading_style(cls, paragraph, style: HeadingStyle):
        cls.apply_paragraph_style(paragraph, style)

    @classmethod
    def setup_document(cls, doc, styles: Optional[DocumentStyles] = None):
        s = styles or cls.get_styles()
        if not HAS_DOCX:
            return
        section = doc.sections[0]
        section.top_margin = Inches(s.page.top_margin)
        section.bottom_margin = Inches(s.page.bottom_margin)
        section.left_margin = Inches(s.page.left_margin)
        section.right_margin = Inches(s.page.right_margin)
        style = doc.styles["Normal"]
        style.font.name = s.content.font.name
        style.font.size = Pt(s.content.font.size)
        rpr = style.element.get_or_add_rPr()
        rFonts = rpr.makeelement(qn('w:rFonts'), {
            qn('w:ascii'): s.content.font.name,
            qn('w:hAnsi'): s.content.font.name,
            qn('w:cs'): s.content.font.name,
        })
        rpr.insert(0, rFonts)
        pf = style.paragraph_format
        pf.alignment = WD_ALIGN_MAP.get(s.content.alignment, WD_ALIGN_PARAGRAPH.JUSTIFY)
        pf.line_spacing = s.content.line_spacing
        pf.space_after = Pt(s.content.space_after)

    @classmethod
    def write_run(cls, paragraph, text: str, font_style: Optional[FontStyle] = None):
        run = paragraph.add_run(text)
        if font_style:
            run.font.name = font_style.name
            run.font.size = Pt(font_style.size)
            run.font.bold = font_style.bold
            run.font.italic = font_style.italic
            if font_style.color:
                run.font.color.rgb = RGBColor(*cls._parse_color(font_style.color))
        return run

    @classmethod
    def _parse_color(cls, color_str: str) -> Tuple[int, int, int]:
        c = color_str.lstrip("#")
        if len(c) == 6:
            return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        if len(c) == 3:
            return int(c[0]*2, 16), int(c[1]*2, 16), int(c[2]*2, 16)
        return (0, 0, 0)

    @classmethod
    def validate_document(cls, doc) -> List[str]:
        issues = []
        s = cls.get_styles()
        if not HAS_DOCX:
            return issues
        for paragraph in doc.paragraphs:
            style_name = paragraph.style.name if paragraph.style else ""
            if style_name.startswith("Heading"):
                for run in paragraph.runs:
                    if run.font.name and run.font.name != s.content.font.name:
                        issues.append(
                            f"Heading font '{run.font.name}' != '{s.content.font.name}' "
                            f"in: {paragraph.text[:50]}"
                        )
            elif style_name == "Normal" or not style_name:
                pf = paragraph.paragraph_format
                if pf.alignment is not None and pf.alignment != WD_ALIGN_MAP.get(s.content.alignment):
                    issues.append(
                        f"Paragraph alignment mismatch in: {paragraph.text[:50]}"
                    )
                for run in paragraph.runs:
                    if run.font.name and run.font.name != s.content.font.name:
                        issues.append(
                            f"Font '{run.font.name}' != '{s.content.font.name}' "
                            f"in: {paragraph.text[:50]}"
                        )
        return issues


def qn(tag: str) -> str:
    from docx.oxml.ns import qn as _qn
    return _qn(tag)
