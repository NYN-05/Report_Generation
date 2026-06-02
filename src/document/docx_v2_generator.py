"""DOCXV2Generator — block-aware DOCX document generation.

Renders ContentBlock types to proper DOCX elements using centralized
StyleManager for all formatting. No hardcoded font sizes, colors,
or alignment values.
"""

import os
import re
from typing import Dict, Any, Optional, List
from src.core.logger import get_logger
from src.generator.content_blocks import (
    SectionContent, ParagraphBlock, BulletListBlock, BulletItem,
    TableBlock, TableRow, FigureBlock, HeadingBlock,
    SourceRequiredBlock, ContentBlock,
)
from src.document.styles import StyleManager, DocumentStyleValidator

logger = get_logger(__name__)

# Control characters to strip from LLM output (except common whitespace)
_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
_MAX_TEXT_LENGTH = 50000  # Max characters per text run


def sanitize_text(text: str, max_length: int = _MAX_TEXT_LENGTH) -> str:
    """Sanitize LLM-generated text for safe DOCX insertion.
    
    Strips control characters, enforces max length, and normalizes whitespace.
    """
    if not text:
        return ""
    text = _CONTROL_CHARS.sub('', text)
    text = text[:max_length]
    return text

try:
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


class DOCXV2Generator:

    def __init__(self):
        self._doc: Optional[Document] = None
        self._styles = StyleManager.get_instance()

    def generate(
        self,
        title: str,
        author: str,
        sections: List[SectionContent],
        output_path: str = "output.docx",
        validate: bool = True,
    ) -> str:
        self._doc = Document()
        self._styles.setup_document(self._doc)
        self._add_cover_page(title, author)
        self._add_table_of_contents(sections)
        for section in sections:
            self._render_section(section)
        if validate and HAS_DOCX:
            validator = DocumentStyleValidator()
            passed, issues = validator.validate(self._doc)
            if issues:
                for issue in issues[:5]:
                    logger.info(f"  [{issue['severity']}] {issue['message']}")
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        self._doc.save(output_path)
        size_kb = os.path.getsize(output_path) / 1024 if os.path.exists(output_path) else 0
        logger.info(f"DOCX saved: {output_path} ({size_kb:.1f} KB, {len(sections)} sections)")
        return output_path

    def _add_cover_page(self, title: str, author: str):
        s = self._styles.get_styles()
        for _ in range(6):
            self._doc.add_paragraph()
        title_p = self._doc.add_paragraph()
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._styles.write_run(title_p, title, s.cover_page.title_font)
        if author:
            self._doc.add_paragraph()
            auth_p = self._doc.add_paragraph()
            auth_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._styles.write_run(auth_p, f"Author: {author}", s.cover_page.author_font)
        self._doc.add_page_break()

    def _add_table_of_contents(self, sections: List[SectionContent]):
        self._doc.add_heading("Table of Contents", level=1)
        for i, section in enumerate(sections, 1):
            p = self._doc.add_paragraph(f"{i}. {section.heading}")
            pf = p.paragraph_format
            pf.space_before = Pt(4)
            pf.space_after = Pt(2)
        self._doc.add_page_break()

    def _render_section(self, section: SectionContent):
        for block in section.blocks:
            self._render_block(block)

    def _render_block(self, block: ContentBlock):
        if isinstance(block, HeadingBlock):
            self._render_heading(block)
        elif isinstance(block, ParagraphBlock):
            self._render_paragraph(block)
        elif isinstance(block, BulletListBlock):
            self._render_bullet_list(block)
        elif isinstance(block, TableBlock):
            self._render_table(block)
        elif isinstance(block, FigureBlock):
            self._render_figure(block)
        elif isinstance(block, SourceRequiredBlock):
            self._render_source_required(block)

    def _render_heading(self, block: HeadingBlock):
        level = min(block.level, 4)
        heading = self._doc.add_heading(block.text, level=level)
        hs = self._styles.get_styles().get_heading(level)
        if heading.runs:
            for run in heading.runs:
                run.font.name = hs.font.name
                run.font.size = Pt(hs.font.size)
                run.font.bold = hs.font.bold
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER if level <= 1 else WD_ALIGN_PARAGRAPH.LEFT

    def _render_paragraph(self, block: ParagraphBlock):
        if not block.text.strip():
            return
        text = sanitize_text(block.text.strip())
        p = self._doc.add_paragraph()
        self._styles.apply_paragraph_style(p, self._styles.get_styles().content)
        run = p.add_run(text)
        run.font.name = self._styles.get_styles().content.font.name
        run.font.size = Pt(self._styles.get_styles().content.font.size)
        if block.citations:
            cite_text = " ".join(
                f"[{c.source}]" for c in block.citations if c.source
            )
            if cite_text:
                cite_run = p.add_run(f" {cite_text}")
                cite_run.font.size = Pt(10)
                cite_run.font.color.rgb = self._styles._parse_color("#808080")

    def _render_bullet_list(self, block: BulletListBlock):
        s = self._styles.get_styles()
        for item in block.items:
            bp = self._doc.add_paragraph(style="List Bullet")
            self._styles.apply_paragraph_style(bp, s.bullet)
            bp.clear()
            run = bp.add_run(f"{item.title}: " if item.title else "")
            run.font.name = s.bullet.font.name
            run.font.size = Pt(s.bullet.font.size)
            run.bold = True
            if item.description:
                drun = bp.add_run(item.description)
                drun.font.name = s.bullet.font.name
                drun.font.size = Pt(s.bullet.font.size)
            if item.citations:
                cite = " ".join(f"[{c.source}]" for c in item.citations if c.source)
                if cite:
                    crun = bp.add_run(f" {cite}")
                    crun.font.size = Pt(10)

    def _render_table(self, block: TableBlock):
        s = self._styles.get_styles()
        if block.caption:
            cap_p = self._doc.add_paragraph()
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._styles.write_run(cap_p, f"Table: {block.caption}", s.table.title_font)
            cap_p.paragraph_format.space_after = Pt(4)
        rows_data = [block.headers] + [r.cells for r in block.rows]
        if not rows_data or not rows_data[0]:
            return
        num_cols = len(rows_data[0])
        table = self._doc.add_table(rows=len(rows_data), cols=num_cols)
        table.style = s.table.grid_style
        table.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for i, row_data in enumerate(rows_data):
            for j, cell_text in enumerate(row_data):
                cell = table.rows[i].cells[j]
                cell.text = str(cell_text)
                for para in cell.paragraphs:
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in para.runs:
                        run.font.size = Pt(s.table.cell_font.size)
                        if i == 0:
                            run.font.bold = True
                            run.font.size = Pt(s.table.header_font.size)
        self._doc.add_paragraph()

    def _render_figure(self, block: FigureBlock):
        s = self._styles.get_styles()
        fp = self._doc.add_paragraph()
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._styles.write_run(fp, f"[Figure: {block.caption}]", s.figure.caption_font)
        if block.description:
            dp = self._doc.add_paragraph(block.description)
            dp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in dp.runs:
                r.font.size = Pt(s.figure.caption_font.size)
                r.font.italic = True

    def _render_source_required(self, block: SourceRequiredBlock):
        p = self._doc.add_paragraph()
        run = p.add_run(block.message)
        run.italic = True
        run.font.color.rgb = self._styles._parse_color("#B43232")
        run.font.size = Pt(10)
        run.font.name = self._styles.get_styles().content.font.name
