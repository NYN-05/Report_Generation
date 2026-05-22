from typing import Dict, Optional
from docx import Document as DocxDocument
from docx.shared import Pt, Emu, RGBColor
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH

from .models import StyleProfile, FontInfo, ParagraphFormatInfo


ALIGNMENT_MAP = {
    WD_ALIGN_PARAGRAPH.LEFT: "LEFT",
    WD_ALIGN_PARAGRAPH.CENTER: "CENTER",
    WD_ALIGN_PARAGRAPH.RIGHT: "RIGHT",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "JUSTIFY",
    None: "LEFT",
}

LINE_SPACING_RULES = {0: "SINGLE", 1: "SINGLE", 2: "DOUBLE", 3: "1.5"}


class StyleExtractor:
    """Extracts and profiles all styles from a DOCX document."""

    def __init__(self, doc: DocxDocument):
        self.doc = doc
        self._profiles: Dict[str, StyleProfile] = {}

    def extract_all(self) -> Dict[str, StyleProfile]:
        self._profiles = {}
        for style in self.doc.styles:
            profile = self._extract_style(style)
            if profile:
                self._profiles[profile.style_id] = profile
        return self._profiles

    def get_profile(self, style_name: str) -> Optional[StyleProfile]:
        return self._profiles.get(style_name)

    def extract_paragraph_format(self, para) -> ParagraphFormatInfo:
        pf = para.paragraph_format
        fmt = ParagraphFormatInfo()
        if pf.alignment is not None:
            fmt.alignment = ALIGNMENT_MAP.get(pf.alignment, "LEFT")
        if pf.space_before is not None:
            fmt.spacing_before = pf.space_before.pt if hasattr(pf.space_before, 'pt') else float(pf.space_before)
        if pf.space_after is not None:
            fmt.spacing_after = pf.space_after.pt if hasattr(pf.space_after, 'pt') else float(pf.space_after)
        if pf.line_spacing is not None:
            fmt.line_spacing = float(pf.line_spacing)
        if pf.line_spacing_rule is not None:
            fmt.line_spacing_rule = LINE_SPACING_RULES.get(pf.line_spacing_rule, "SINGLE")
        if pf.left_indent is not None:
            fmt.indent_left = pf.left_indent.pt if hasattr(pf.left_indent, 'pt') else float(pf.left_indent)
        if pf.right_indent is not None:
            fmt.indent_right = pf.right_indent.pt if hasattr(pf.right_indent, 'pt') else float(pf.right_indent)
        if pf.first_line_indent is not None:
            fmt.indent_first_line = pf.first_line_indent.pt if hasattr(pf.first_line_indent, 'pt') else float(pf.first_line_indent)
        if pf.keep_with_next is not None:
            fmt.keep_with_next = pf.keep_with_next
        if pf.page_break_before is not None:
            fmt.page_break_before = pf.page_break_before
        if pf.widow_control is not None:
            fmt.widow_control = pf.widow_control
        return fmt

    def extract_run_font(self, run) -> FontInfo:
        font = FontInfo()
        rPr = run._element.find(qn('w:rPr'))
        if rPr is not None:
            rFonts = rPr.find(qn('w:rFonts'))
            if rFonts is not None:
                font.name = rFonts.get(qn('w:ascii')) or rFonts.get(qn('w:hAnsi')) or ""
            sz = rPr.find(qn('w:sz'))
            if sz is not None:
                val = sz.get(qn('w:val'))
                if val:
                    font.size = int(val) / 2.0
            b = rPr.find(qn('w:b'))
            if b is not None:
                val = b.get(qn('w:val'))
                font.bold = val is None or val not in ("false", "0", "off")
            i = rPr.find(qn('w:i'))
            if i is not None:
                val = i.get(qn('w:val'))
                font.italic = val is None or val not in ("false", "0", "off")
            u = rPr.find(qn('w:u'))
            if u is not None:
                val = u.get(qn('w:val'))
                font.underline = val is not None and val not in ("none", "false")
            strike = rPr.find(qn('w:strike'))
            if strike is not None:
                val = strike.get(qn('w:val'))
                font.strike = val is None or val not in ("false", "0", "off")
            color = rPr.find(qn('w:color'))
            if color is not None:
                font.color = color.get(qn('w:val'))
            vertAlign = rPr.find(qn('w:vertAlign'))
            if vertAlign is not None:
                align_val = vertAlign.get(qn('w:val'))
                font.superscript = align_val == "superscript"
                font.subscript = align_val == "subscript"
        else:
            font.name = run.font.name or ""
            if run.font.size:
                font.size = run.font.size.pt if hasattr(run.font.size, 'pt') else float(run.font.size)
            font.bold = run.font.bold or False
            font.italic = run.font.italic or False
            if run.font.color and run.font.color.rgb:
                font.color = str(run.font.color.rgb)
        return font

    def _extract_style(self, style) -> Optional[StyleProfile]:
        if style.type is None:
            return None
        sname = style.name or ""
        sid = style.style_id or sname
        stype = style.type.name.lower() if style.type.name else "paragraph"

        base_style_name = None
        if hasattr(style, 'base_style') and style.base_style:
            base_style_name = style.base_style.name
        profile = StyleProfile(
            style_id=sid,
            style_name=sname,
            type=stype,
            based_on=base_style_name,
        )

        lower = sname.lower()
        if lower.startswith("heading "):
            parts = lower.split()
            if len(parts) == 2 and parts[1].isdigit():
                profile.is_heading = True
                profile.heading_level = int(parts[1])

        is_builtin = getattr(style, 'builtin', False)
        if not is_builtin and not lower.startswith("heading "):
            profile.is_custom = True

        if hasattr(style, 'font') and style.font:
            f = profile.font
            f.name = style.font.name or ""
            if style.font.size:
                f.size = style.font.size.pt if hasattr(style.font.size, 'pt') else float(style.font.size)
            f.bold = style.font.bold or False
            f.italic = style.font.italic or False
            if style.font.color and style.font.color.rgb:
                f.color = str(style.font.color.rgb)

        if hasattr(style, 'paragraph_format') and style.paragraph_format:
            pf = style.paragraph_format
            p = profile.paragraph_format
            if pf.alignment is not None:
                p.alignment = ALIGNMENT_MAP.get(pf.alignment, "LEFT")
            if pf.space_before is not None:
                p.spacing_before = pf.space_before.pt if hasattr(pf.space_before, 'pt') else float(pf.space_before)
            if pf.space_after is not None:
                p.spacing_after = pf.space_after.pt if hasattr(pf.space_after, 'pt') else float(pf.space_after)
            if pf.line_spacing is not None:
                p.line_spacing = float(pf.line_spacing)
            if pf.left_indent is not None:
                p.indent_left = pf.left_indent.pt if hasattr(pf.left_indent, 'pt') else float(pf.left_indent)
            if pf.first_line_indent is not None:
                p.indent_first_line = pf.first_line_indent.pt if hasattr(pf.first_line_indent, 'pt') else float(pf.first_line_indent)

        return profile
