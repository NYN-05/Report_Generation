"""DOCXV2Generator — block-aware DOCX document generation.

Renders ContentBlock types to proper DOCX elements:
- ParagraphBlock → Normal paragraphs
- BulletListBlock → Real DOCX bullet lists with title + description
- TableBlock → Actual tables
- FigureBlock → Figure blocks
- HeadingBlock → Heading styles
- SourceRequiredBlock → Italicized placeholder
"""

import os
from typing import Dict, Any, Optional, List
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from src.core.logger import get_logger
from src.generator.content_blocks import (
    SectionContent, ParagraphBlock, BulletListBlock, BulletItem,
    TableBlock, TableRow, FigureBlock, HeadingBlock,
    SourceRequiredBlock, ContentBlock,
)

logger = get_logger(__name__)

OUTPUT_DOCX = "output.docx"

HEADING_COLORS = {
    0: RGBColor(0, 51, 102),
    1: RGBColor(0, 51, 102),
    2: RGBColor(60, 80, 110),
    3: RGBColor(80, 80, 80),
}

BULLET_INDENT = Inches(0.5)
BULLET_TAB = Inches(0.8)


class DOCXV2Generator:

    def __init__(self):
        self._doc: Optional[Document] = None

    def generate(
        self,
        title: str,
        author: str,
        sections: List[SectionContent],
        output_path: str = OUTPUT_DOCX,
    ) -> str:
        self._doc = Document()
        self._setup_styles()

        self._add_cover_page(title, author)
        self._add_table_of_contents(sections)

        for section in sections:
            self._render_section(section)

        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        self._doc.save(output_path)

        size_kb = os.path.getsize(output_path) / 1024 if os.path.exists(output_path) else 0
        logger.info(f"DOCX saved: {output_path} ({size_kb:.1f} KB, {len(sections)} sections)")
        return output_path

    def _setup_styles(self):
        section = self._doc.sections[0]
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

        style = self._doc.styles["Normal"]
        style.font.name = "Calibri"
        style.font.size = Pt(11)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.line_spacing = 1.15

    def _add_cover_page(self, title: str, author: str):
        for _ in range(6):
            self._doc.add_paragraph()

        title_p = self._doc.add_paragraph()
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title_p.add_run(title)
        run.font.name = "Calibri"
        run.font.size = Pt(28)
        run.font.color.rgb = RGBColor(0, 51, 102)
        run.bold = True

        if author:
            self._doc.add_paragraph()
            auth_p = self._doc.add_paragraph()
            auth_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = auth_p.add_run(f"Author: {author}")
            run.font.name = "Calibri"
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(80, 80, 80)

        self._doc.add_page_break()

    def _add_table_of_contents(self, sections: List[SectionContent]):
        self._doc.add_heading("Table of Contents", level=1)
        for i, section in enumerate(sections, 1):
            p = self._doc.add_paragraph(f"{i}. {section.heading}")
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(2)
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
        for run in heading.runs:
            run.font.color.rgb = HEADING_COLORS.get(level, RGBColor(0, 0, 0))

    def _render_paragraph(self, block: ParagraphBlock):
        if not block.text.strip():
            return

        text = block.text.strip()

        if block.citations:
            cite_suffix = " ".join(f"[{c.source}]" for c in block.citations if c.source)
            if cite_suffix:
                text += f" {cite_suffix}"

        p = self._doc.add_paragraph(text)

        p.paragraph_format.first_line_indent = Inches(0.3)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.line_spacing = 1.15

    def _render_bullet_list(self, block: BulletListBlock):
        if block.lead_in:
            lead_p = self._doc.add_paragraph(block.lead_in)
            lead_p.paragraph_format.space_after = Pt(4)

        for item in block.items:
            self._render_bullet_item(item)

        if block.lead_out:
            out_p = self._doc.add_paragraph(block.lead_out)
            out_p.paragraph_format.space_before = Pt(4)

    def _render_bullet_item(self, item: BulletItem):
        bullet_p = self._doc.add_paragraph(style="List Bullet")
        bullet_p.paragraph_format.left_indent = BULLET_INDENT
        bullet_p.paragraph_format.first_line_indent = Inches(-0.25)
        bullet_p.paragraph_format.space_after = Pt(2)

        run = bullet_p.add_run(f"{item.title}: ")
        run.bold = True
        run.font.size = Pt(11)

        if item.description:
            desc_run = bullet_p.add_run(item.description)
            desc_run.font.size = Pt(11)

        if item.citations:
            cite_text = " ".join(f"[{c.source}]" for c in item.citations if c.source)
            if cite_text:
                cite_run = bullet_p.add_run(f" {cite_text}")
                cite_run.font.size = Pt(10)
                cite_run.font.color.rgb = RGBColor(80, 80, 80)

        if item.description:
            desc_p = self._doc.add_paragraph(item.description)
            desc_p.paragraph_format.left_indent = BULLET_TAB
            desc_p.paragraph_format.space_after = Pt(6)
            desc_p.paragraph_format.first_line_indent = Inches(0)

    def _render_table(self, block: TableBlock):
        if block.caption:
            cap_p = self._doc.add_paragraph()
            cap_run = cap_p.add_run(f"Table: {block.caption}")
            cap_run.bold = True
            cap_run.font.size = Pt(10)
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap_p.paragraph_format.space_after = Pt(4)

        rows_data = [block.headers] + [r.cells for r in block.rows]
        if not rows_data or not rows_data[0]:
            return

        num_cols = len(rows_data[0])
        table = self._doc.add_table(rows=len(rows_data), cols=num_cols)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        for i, row_data in enumerate(rows_data):
            for j, cell_text in enumerate(row_data):
                cell = table.rows[i].cells[j]
                cell.text = str(cell_text)
                for paragraph in cell.paragraphs:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in paragraph.runs:
                        run.font.size = Pt(10)
                        if i == 0:
                            run.bold = True

        self._doc.add_paragraph()

    def _render_figure(self, block: FigureBlock):
        placeholder_p = self._doc.add_paragraph()
        placeholder_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = placeholder_p.add_run(f"[Figure: {block.caption}]")
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(100, 100, 100)
        run.italic = True

        if block.description:
            desc_p = self._doc.add_paragraph(block.description)
            desc_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            desc_p.paragraph_format.space_before = Pt(2)
            for r in desc_p.runs:
                r.font.size = Pt(10)
                r.font.color.rgb = RGBColor(100, 100, 100)

    def _render_source_required(self, block: SourceRequiredBlock):
        p = self._doc.add_paragraph()
        run = p.add_run(block.message)
        run.italic = True
        run.font.color.rgb = RGBColor(180, 50, 50)
        run.font.size = Pt(10)
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
