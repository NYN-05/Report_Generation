import re
from typing import List, Optional, Tuple
from docx import Document as DocxDocument
from docx.oxml.ns import qn

from .models import HeadingInfo, StyleProfile


HEADING_STYLE_PATTERN = re.compile(r'^heading\s+\d+$', re.IGNORECASE)
CUSTOM_HEADING_PREFIX = re.compile(r'^heading\s+', re.IGNORECASE)

NUMBERING_PATTERNS = [
    re.compile(r'^(\d+)\.?\s+'),           # 1. or 1
    re.compile(r'^(\d+\.\d+)\.?\s+'),       # 1.1 or 1.1.
    re.compile(r'^(\d+\.\d+\.\d+)\.?\s+'),  # 1.1.1
    re.compile(r'^\(([a-z])\)\s+'),          # (a)
    re.compile(r'^([A-Z])\.\s+'),           # A.
    re.compile(r'^([ivx]+)\.\s+'),          # i. or iv.
    re.compile(r'^[IVX]+\.\s+'),           # I. II.
]


class HeadingDetector:
    """Detects and classifies all headings in a DOCX document."""

    def __init__(self, doc: DocxDocument):
        self.doc = doc
        self._headings: List[HeadingInfo] = []
        self._custom_heading_styles: List[str] = []

    def detect(self) -> List[HeadingInfo]:
        self._headings = []
        self._discover_custom_heading_styles()

        for idx, para in enumerate(self.doc.paragraphs):
            text = para.text.strip()
            if not text:
                continue

            style = para.style
            style_name = style.name or "" if style else ""

            level = self._get_heading_level(style_name, para)
            if level is None:
                continue

            numbering = self._extract_numbering(text)
            clean_text = self._strip_numbering(text) if numbering else text

            heading = HeadingInfo(
                level=level,
                text=clean_text,
                style_name=style_name,
                numbering=numbering,
                paragraph_index=idx,
                is_numbered=numbering is not None,
            )
            self._headings.append(heading)

        return self._headings

    def build_hierarchy(self) -> List[HeadingInfo]:
        return self._headings

    def get_hierarchy_tree(self) -> List[dict]:
        """Build a nested tree from flat heading list."""
        tree: List[dict] = []
        stack: List[tuple] = []

        for h in self._headings:
            node = {
                "heading": h.to_dict(),
                "children": [],
            }
            while stack and stack[-1][0] >= h.level:
                stack.pop()
            if stack:
                stack[-1][1]["children"].append(node)
            else:
                tree.append(node)
            stack.append((h.level, node))

        return tree

    def _discover_custom_heading_styles(self):
        self._custom_heading_styles = []
        for style in self.doc.styles:
            if style.type is None or style.type.name != "PARAGRAPH":
                continue
            sname = style.name or ""
            if HEADING_STYLE_PATTERN.match(sname):
                self._custom_heading_styles.append(sname)
                continue
            if style.builtin:
                continue
            based_on = style.base_style
            if based_on and CUSTOM_HEADING_PREFIX.match(based_on.name or ""):
                self._custom_heading_styles.append(sname)
                continue
            if sname.lower().startswith("heading") and sname.lower() not in (
                "heading", "heading 1", "heading 2", "heading 3",
                "heading 4", "heading 5", "heading 6", "heading 7", "heading 8", "heading 9",
            ):
                self._custom_heading_styles.append(sname)

    def _get_heading_level(self, style_name: str, para) -> Optional[int]:
        if not style_name:
            return None

        lower = style_name.lower()
        if lower.startswith("heading ") and not lower.startswith("heading "):
            pass

        builtin_match = re.match(r'^heading\s+(\d+)$', lower)
        if builtin_match:
            return int(builtin_match.group(1))

        if self._is_custom_heading(style_name):
            return self._infer_level_from_format(para) or 2

        pPr = para._element.find(qn('w:pPr'))
        if pPr is not None:
            outline = pPr.find(qn('w:outlineLvl'))
            if outline is not None:
                val = outline.get(qn('w:val'))
                if val is not None:
                    return int(val) + 1
            numPr = pPr.find(qn('w:numPr'))
            if numPr is not None:
                ilvl = numPr.find(qn('w:ilvl'))
                if ilvl is not None:
                    val = ilvl.get(qn('w:val'))
                    if val is not None:
                        return int(val) + 1

        return None

    def _is_custom_heading(self, style_name: str) -> bool:
        return style_name in self._custom_heading_styles

    def _infer_level_from_format(self, para) -> Optional[int]:
        font_sizes = []
        for run in para.runs:
            if run.font.size:
                font_sizes.append(run.font.size.pt if hasattr(run.font.size, 'pt') else float(run.font.size))

        if font_sizes:
            avg_size = sum(font_sizes) / len(font_sizes)
            if avg_size >= 18:
                return 1
            elif avg_size >= 14:
                return 2
            elif avg_size >= 12:
                return 3
        return None

    def _extract_numbering(self, text: str) -> Optional[str]:
        for pattern in NUMBERING_PATTERNS:
            m = pattern.match(text)
            if m:
                return m.group(1)
        return None

    def _strip_numbering(self, text: str) -> str:
        for pattern in NUMBERING_PATTERNS:
            m = pattern.match(text)
            if m:
                return text[m.end():].strip()
        return text

    def get_heading_count(self) -> int:
        return len(self._headings)

    def get_headings_by_level(self, level: int) -> List[HeadingInfo]:
        return [h for h in self._headings if h.level == level]
