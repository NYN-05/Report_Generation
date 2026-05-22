import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple


@dataclass
class FontInfo:
    name: str = ""
    size: float = 0.0
    bold: bool = False
    italic: bool = False
    color: Optional[str] = None
    underline: bool = False
    strike: bool = False
    superscript: bool = False
    subscript: bool = False


@dataclass
class ParagraphFormatInfo:
    alignment: str = "LEFT"
    spacing_before: float = 0.0
    spacing_after: float = 0.0
    line_spacing: float = 1.0
    line_spacing_rule: str = "SINGLE"
    indent_left: float = 0.0
    indent_right: float = 0.0
    indent_first_line: float = 0.0
    outline_level: int = -1
    keep_with_next: bool = False
    page_break_before: bool = False
    widow_control: bool = True


@dataclass
class StyleProfile:
    style_id: str
    style_name: str
    type: str = "paragraph"
    based_on: Optional[str] = None
    font: FontInfo = field(default_factory=FontInfo)
    paragraph_format: ParagraphFormatInfo = field(default_factory=ParagraphFormatInfo)
    is_heading: bool = False
    heading_level: int = 0
    is_custom: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "style_id": self.style_id,
            "style_name": self.style_name,
            "type": self.type,
            "based_on": self.based_on,
            "is_heading": self.is_heading,
            "heading_level": self.heading_level,
            "is_custom": self.is_custom,
            "font": {
                "name": self.font.name,
                "size": self.font.size,
                "bold": self.font.bold,
                "italic": self.font.italic,
                "color": self.font.color,
                "underline": self.font.underline,
                "strike": self.font.strike,
            },
            "paragraph_format": {
                "alignment": self.paragraph_format.alignment,
                "spacing_before": self.paragraph_format.spacing_before,
                "spacing_after": self.paragraph_format.spacing_after,
                "line_spacing": self.paragraph_format.line_spacing,
                "indent_left": self.paragraph_format.indent_left,
                "indent_right": self.paragraph_format.indent_right,
                "indent_first_line": self.paragraph_format.indent_first_line,
            },
        }


@dataclass
class HeadingInfo:
    level: int
    text: str
    style_name: str = ""
    numbering: Optional[str] = None
    paragraph_index: int = -1
    page_number: int = 0
    style_profile: Optional[StyleProfile] = None
    is_numbered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "text": self.text,
            "style_name": self.style_name,
            "numbering": self.numbering,
            "paragraph_index": self.paragraph_index,
            "page_number": self.page_number,
            "is_numbered": self.is_numbered,
        }


@dataclass
class ParagraphInfo:
    text: str
    style_name: str
    paragraph_index: int
    font: FontInfo = field(default_factory=FontInfo)
    paragraph_format: ParagraphFormatInfo = field(default_factory=ParagraphFormatInfo)
    is_heading: bool = False
    heading_level: int = 0
    contains_citation: bool = False
    citations: List[str] = field(default_factory=list)


@dataclass
class TableInfo:
    index: int
    rows: int
    cols: int
    caption: Optional[str] = None
    headers: List[str] = field(default_factory=list)
    data: List[List[str]] = field(default_factory=list)
    style_name: Optional[str] = None
    has_merged_cells: bool = False
    column_widths: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "rows": self.rows,
            "cols": self.cols,
            "caption": self.caption,
            "headers": self.headers,
            "style_name": self.style_name,
            "has_merged_cells": self.has_merged_cells,
        }


@dataclass
class ImageInfo:
    index: int
    rId: str
    width_emus: int = 0
    height_emus: int = 0
    width_inches: float = 0.0
    height_inches: float = 0.0
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    anchor_section: Optional[str] = None
    paragraph_index: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "rId": self.rId,
            "width_inches": round(self.width_inches, 2),
            "height_inches": round(self.height_inches, 2),
            "caption": self.caption,
            "alt_text": self.alt_text,
            "anchor_section": self.anchor_section,
            "paragraph_index": self.paragraph_index,
        }


@dataclass
class ReferenceInfo:
    raw_text: str
    format: str = "ieee"
    index: int = 0
    citation_key: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    title: Optional[str] = None
    year: Optional[str] = None
    source: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "format": self.format,
            "raw_text": self.raw_text[:200],
            "citation_key": self.citation_key,
            "authors": self.authors,
            "title": self.title,
            "year": self.year,
            "source": self.source,
        }


@dataclass
class CitationLink:
    citation_marker: str
    reference_index: int
    context_text: str
    paragraph_index: int = -1
    confidence: float = 1.0


@dataclass
class SectionInfo:
    heading: Optional[HeadingInfo] = None
    section_type: str = "unknown"
    confidence: float = 0.0
    level: int = 1
    children: List["SectionInfo"] = field(default_factory=list)
    paragraphs: List[ParagraphInfo] = field(default_factory=list)
    tables: List[TableInfo] = field(default_factory=list)
    images: List[ImageInfo] = field(default_factory=list)
    references: List[ReferenceInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "heading": self.heading.to_dict() if self.heading else None,
            "section_type": self.section_type,
            "confidence": round(self.confidence, 2),
            "level": self.level,
            "children": [c.to_dict() for c in self.children],
            "paragraph_count": len(self.paragraphs),
            "table_count": len(self.tables),
            "image_count": len(self.images),
        }


@dataclass
class FootnoteInfo:
    index: int
    footnote_id: str = ""
    text: str = ""
    paragraph_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "id": self.footnote_id,
            "text": self.text[:200],
            "paragraph_count": self.paragraph_count,
        }


@dataclass
class HeaderFooterInfo:
    section_index: int
    type: str = "header"
    text: str = ""
    paragraph_count: int = 0
    is_linked_to_previous: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_index": self.section_index,
            "type": self.type,
            "text": self.text[:200],
            "paragraph_count": self.paragraph_count,
        }


@dataclass
class CrossReferenceInfo:
    reference_type: str = ""
    reference_text: str = ""
    paragraph_index: int = -1
    context_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.reference_type,
            "reference_text": self.reference_text,
            "paragraph_index": self.paragraph_index,
            "context_text": self.context_text[:200] if self.context_text else "",
        }


@dataclass
class WatermarkInfo:
    type: str = "text"
    text: str = ""
    is_section_watermark: bool = True
    section_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "text": self.text[:200] if self.text else "",
            "is_section_watermark": self.is_section_watermark,
            "section_index": self.section_index,
        }


@dataclass
class EquationInfo:
    index: int
    paragraph_index: int = -1
    math_type: str = "omml"
    inline: bool = True
    plain_text_approx: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "paragraph_index": self.paragraph_index,
            "math_type": self.math_type,
            "inline": self.inline,
            "plain_text_approx": self.plain_text_approx[:100],
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.reference_type,
            "reference_text": self.reference_text,
            "paragraph_index": self.paragraph_index,
        }


@dataclass
class DocKnowledgeGraph:
    filename: str
    sections: List[SectionInfo] = field(default_factory=list)
    headings: List[HeadingInfo] = field(default_factory=list)
    styles: Dict[str, StyleProfile] = field(default_factory=dict)
    tables: List[TableInfo] = field(default_factory=list)
    figures: List[ImageInfo] = field(default_factory=list)
    references: List[ReferenceInfo] = field(default_factory=list)
    citation_links: List[CitationLink] = field(default_factory=list)
    paragraphs: List[ParagraphInfo] = field(default_factory=list)
    footnotes: List[FootnoteInfo] = field(default_factory=list)
    headers_footers: List[HeaderFooterInfo] = field(default_factory=list)
    cross_references: List[CrossReferenceInfo] = field(default_factory=list)
    watermarks: List[WatermarkInfo] = field(default_factory=list)
    equations: List[EquationInfo] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "filename": self.filename,
            "statistics": self.statistics,
            "headings": [h.to_dict() for h in self.headings],
            "sections": [s.to_dict() for s in self.sections],
            "style_count": len(self.styles),
            "table_count": len(self.tables),
            "figure_count": len(self.figures),
            "reference_count": len(self.references),
            "citation_link_count": len(self.citation_links),
            "footnote_count": len(self.footnotes),
            "header_footer_count": len(self.headers_footers),
            "cross_reference_count": len(self.cross_references),
            "watermark_count": len(self.watermarks),
            "equation_count": len(self.equations),
            "total_paragraphs": len(self.paragraphs),
        }
