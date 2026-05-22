"""
Document Builder Module
========================
Builds DOCX documents from content.
"""

import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.style import WD_STYLE_TYPE

from .base import BaseDocument, DocumentMetadata, Section
from src.core.logger import get_logger
from src.core.constants import DEFAULT_PAGE_MARGIN, DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE

logger = get_logger(__name__)


class DocumentBuilder(BaseDocument):
    """Builds Word documents using python-docx."""

    def __init__(
        self,
        metadata: Optional[DocumentMetadata] = None,
        margin: int = DEFAULT_PAGE_MARGIN,
        font_name: str = DEFAULT_FONT_NAME,
        font_size: int = DEFAULT_FONT_SIZE
    ):
        super().__init__(metadata)
        self._document: Optional[Document] = None
        self._margin = margin
        self._font_name = font_name
        self._font_size = font_size

    def create(self) -> "DocumentBuilder":
        """Create a new empty document."""
        self._document = Document()
        self._setup_page()
        return self

    def _setup_page(self):
        """Setup page margins."""
        section = self._document.sections[0]
        section.top_margin = Inches(self._margin / 1440)
        section.bottom_margin = Inches(self._margin / 1440)
        section.left_margin = Inches(self._margin / 1440)
        section.right_margin = Inches(self._margin / 1440)

    def add_cover_page(
        self,
        title: str,
        subtitle: str = "",
        author: str = "",
        date: str = ""
    ) -> "DocumentBuilder":
        """Add a cover page."""
        if not self._document:
            self.create()

        title_para = self._document.add_paragraph()
        title_run = title_para.add_run(title)
        self._format_title(title_run)

        if subtitle:
            subtitle_para = self._document.add_paragraph()
            subtitle_run = subtitle_para.add_run(subtitle)
            subtitle_run.font.name = self._font_name
            subtitle_run.font.size = Pt(16)
            subtitle_run.font.color.rgb = RGBColor(100, 100, 100)
            subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        self._document.add_paragraph()

        if author or date:
            info_para = self._document.add_paragraph()
            info_parts = []
            if author:
                info_parts.append(f"Author: {author}")
            if date:
                info_parts.append(f"Date: {date}")

            info_run = info_para.add_run("\n".join(info_parts))
            info_run.font.name = self._font_name
            info_run.font.size = Pt(12)
            info_run.font.color.rgb = RGBColor(80, 80, 80)
            info_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        self._document.add_page_break()
        return self

    def _format_title(self, run):
        """Format title text."""
        run.font.name = self._font_name
        run.font.size = Pt(28)
        run.font.color.rgb = RGBColor(0, 51, 102)
        run.font.bold = True

    def add_toc(self, entries: List[str]) -> "DocumentBuilder":
        """Add table of contents."""
        if not self._document:
            self.create()

        self._document.add_heading('Table of Contents', level=1)
        for i, entry in enumerate(entries, 1):
            p = self._document.add_paragraph(f'{i}. {entry}')
            p.paragraph_format.space_before = Pt(6)

        self._document.add_page_break()
        return self

    def add_section(
        self,
        title: str,
        content: str = "",
        level: int = 1,
        add_page_break: bool = False
    ) -> "DocumentBuilder":
        """Add a section to the document."""
        if not self._document:
            self.create()

        self._document.add_heading(title, level=level)

        if content:
            if isinstance(content, list):
                content = "\n\n".join(str(item) for item in content)
            for para_text in content.split("\n\n"):
                para_text = para_text.strip()
                if para_text:
                    self._document.add_paragraph(para_text)

        if add_page_break:
            self._document.add_page_break()

        return self

    def add_paragraph(
        self,
        text: str,
        style: str = "Normal",
        bold: bool = False,
        italic: bool = False
    ) -> "DocumentBuilder":
        """Add a paragraph."""
        if not self._document:
            self.create()

        para = self._document.add_paragraph(text)
        if style != "Normal":
            para.style = style

        for run in para.runs:
            run.font.bold = bold
            run.font.italic = italic

        return self

    def add_bullet_list(self, items: List[str]) -> "DocumentBuilder":
        """Add a bullet list."""
        if not self._document:
            self.create()

        for item in items:
            p = self._document.add_paragraph(item)
            p.style = 'List Bullet'

        return self

    def add_numbered_list(self, items: List[str]) -> "DocumentBuilder":
        """Add a numbered list."""
        if not self._document:
            self.create()

        for item in items:
            p = self._document.add_paragraph(item)
            p.style = 'List Number'

        return self

    def add_table(
        self,
        data: List[List[str]],
        headers: Optional[List[str]] = None,
        style: str = "Table Grid"
    ) -> "DocumentBuilder":
        """Add a table."""
        if not self._document:
            self.create()

        rows = len(data)
        cols = len(data[0]) if data else 0

        if headers:
            rows += 1

        table = self._document.add_table(rows=rows, cols=cols)
        table.style = style

        row_idx = 0

        if headers:
            for col_idx, header in enumerate(headers):
                table.rows[row_idx].cells[col_idx].text = header
            row_idx += 1

        for row in data:
            for col_idx, cell in enumerate(row):
                table.rows[row_idx].cells[col_idx].text = cell
            row_idx += 1

        return self

    def save(self, path: str) -> bool:
        """Save document to file."""
        if not self._document:
            logger.error("No document to save")
            return False

        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self._document.save(path)

            self.metadata.modified_at = datetime.now()
            self.metadata.paragraph_count = len(self._document.paragraphs)
            self.metadata.table_count = len(self._document.tables)

            logger.info(f"Document saved: {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            return False

    def load(self, path: str) -> bool:
        """Load document from file."""
        try:
            self._document = Document(path)
            logger.info(f"Document loaded: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load document: {e}")
            return False

    def get_sections(self) -> List[Section]:
        """Get all sections."""
        if not self._document:
            return []

        sections = []
        for para in self._document.paragraphs:
            if para.style.name.startswith('Heading'):
                sections.append(Section(
                    title=para.text,
                    content="",
                    level=int(para.style.name[-1]) if para.style.name[-1].isdigit() else 1
                ))

        return sections

    def build_from_content(self, content: Dict[str, Any]) -> bool:
        """Build document from content dictionary."""
        self.create()

        self.add_cover_page(
            title=content.get('title', 'Report'),
            subtitle=content.get('subtitle', ''),
            author=content.get('author', ''),
            date=content.get('date', '')
        )

        toc_entries = content.get('toc_entries', [])
        if toc_entries:
            self.add_toc(toc_entries)

        if content.get('executive_summary'):
            self.add_section('Executive Summary', content['executive_summary'])

        if content.get('introduction'):
            self.add_section('Introduction', content['introduction'])

        sections = content.get('sections', [])
        for section in sections:
            self.add_section(
                title=section.get('heading', 'Section'),
                content=section.get('content', ''),
                level=2
            )

        if content.get('conclusion'):
            self.add_section('Conclusion', content['conclusion'])

        self.metadata.title = content.get('title', 'Report')
        self.metadata.subtitle = content.get('subtitle', '')
        self.metadata.author = content.get('author', '')
        self.metadata.date = content.get('date', '')
        self.metadata.section_count = len(sections) + 2

        return True