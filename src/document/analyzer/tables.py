import re
from typing import List, Optional
from docx import Document as DocxDocument
from docx.oxml.ns import qn

from .models import TableInfo


CAPTION_PATTERN = re.compile(
    r'^(table|tab\.)\s+(\d+[\.:]?)', re.IGNORECASE
)


class TableDetector:
    """Detects and extracts metadata from all tables in a DOCX document."""

    def __init__(self, doc: DocxDocument):
        self.doc = doc
        self._tables: List[TableInfo] = []

    def detect(self) -> List[TableInfo]:
        self._tables = []
        for idx, table in enumerate(self.doc.tables):
            info = self._extract_table(idx, table)
            self._tables.append(info)
        return self._tables

    def detect_with_captions(self, paragraphs) -> List[TableInfo]:
        self.detect()
        self._attach_captions(paragraphs)
        return self._tables

    def _extract_table(self, idx: int, table) -> TableInfo:
        rows = len(table.rows)
        cols = len(table.columns) if table.columns else 0

        headers: List[str] = []
        data: List[List[str]] = []
        has_merged = False

        for ri, row in enumerate(table.rows):
            row_data: List[str] = []
            for ci, cell in enumerate(row.cells):
                text = cell.text.strip()
                row_data.append(text)

                tc = cell._tc
                if tc is not None:
                    tcPr = tc.find(qn('w:tcPr'))
                    if tcPr is not None:
                        hmerge = tcPr.find(qn('w:gridSpan'))
                        vmerge = tcPr.find(qn('w:vMerge'))
                        if hmerge is not None or vmerge is not None:
                            has_merged = True

            if ri == 0:
                headers = row_data
            data.append(row_data)

        col_widths: List[float] = []
        if table.columns:
            for col in table.columns:
                if col.width:
                    col_widths.append(col.width.pt if hasattr(col.width, 'pt') else float(col.width))
                else:
                    col_widths.append(0.0)

        return TableInfo(
            index=idx,
            rows=rows,
            cols=cols,
            headers=headers,
            data=data,
            style_name=table.style.name if table.style else None,
            has_merged_cells=has_merged,
            column_widths=col_widths,
        )

    def _attach_captions(self, paragraphs):
        para_iter = iter(enumerate(paragraphs))
        table_idx = 0
        for pi, para in para_iter:
            if table_idx >= len(self._tables):
                break
            text = para.text.strip()
            m = CAPTION_PATTERN.match(text)
            if m:
                self._tables[table_idx].caption = text
                table_idx += 1
                continue
            if hasattr(para, '_element'):
                p_elem = para._element
                tbl_sibling = p_elem.getnext() if hasattr(p_elem, 'getnext') else None
                if tbl_sibling is not None:
                    tag = tbl_sibling.tag.split('}')[-1] if '}' in tbl_sibling.tag else tbl_sibling.tag
                    if tag == 'tbl':
                        table_idx += 1

    def get_table_count(self) -> int:
        return len(self._tables)

    def find_table_by_caption(self, caption: str) -> Optional[TableInfo]:
        lower = caption.lower()
        for t in self._tables:
            if t.caption and lower in t.caption.lower():
                return t
        return None
