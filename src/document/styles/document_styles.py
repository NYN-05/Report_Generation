from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class Alignment(Enum):
    LEFT = "LEFT"
    CENTER = "CENTER"
    RIGHT = "RIGHT"
    JUSTIFY = "JUSTIFY"


@dataclass
class FontStyle:
    name: str = "Times New Roman"
    size: float = 12.0
    bold: bool = False
    italic: bool = False
    color: Optional[str] = None
    size_pt: float = 12.0

    @property
    def pt(self) -> float:
        return self.size


@dataclass
class ParagraphStyle:
    font: FontStyle = field(default_factory=FontStyle)
    alignment: Alignment = Alignment.JUSTIFY
    line_spacing: float = 1.5
    space_before: float = 0.0
    space_after: float = 6.0
    first_line_indent: float = 0.5
    left_indent: float = 0.0
    keep_with_next: bool = False
    outline_level: Optional[int] = None


@dataclass
class HeadingStyle:
    font: FontStyle = field(default_factory=FontStyle)
    alignment: Alignment = Alignment.CENTER
    line_spacing: float = 1.5
    space_before: float = 12.0
    space_after: float = 6.0
    keep_with_next: bool = True
    outline_level: int = 1


@dataclass
class BulletStyle:
    font: FontStyle = field(default_factory=lambda: FontStyle(name="Times New Roman", size=12.0))
    alignment: Alignment = Alignment.LEFT
    line_spacing: float = 1.5
    space_before: float = 0.0
    space_after: float = 3.0
    left_indent: float = 0.5
    first_line_indent: float = -0.25
    bullet_char: str = "•"
    use_docx_style: bool = True


@dataclass
class TableStyle:
    header_font: FontStyle = field(default_factory=lambda: FontStyle(name="Times New Roman", size=11.0, bold=True))
    cell_font: FontStyle = field(default_factory=lambda: FontStyle(name="Times New Roman", size=11.0))
    title_font: FontStyle = field(default_factory=lambda: FontStyle(name="Times New Roman", size=12.0, bold=True))
    alignment: Alignment = Alignment.CENTER
    header_alignment: Alignment = Alignment.CENTER
    cell_alignment: Alignment = Alignment.CENTER
    grid_style: str = "Table Grid"


@dataclass
class FigureStyle:
    caption_font: FontStyle = field(default_factory=lambda: FontStyle(name="Times New Roman", size=11.0, italic=True))
    alignment: Alignment = Alignment.CENTER
    space_before: float = 6.0
    space_after: float = 6.0


@dataclass
class ReferenceStyle:
    font: FontStyle = field(default_factory=lambda: FontStyle(name="Times New Roman", size=12.0))
    alignment: Alignment = Alignment.LEFT
    line_spacing: float = 1.5
    hanging_indent: float = 0.5
    space_after: float = 6.0


@dataclass
class CoverPageStyle:
    title_font: FontStyle = field(default_factory=lambda: FontStyle(name="Times New Roman", size=28.0, bold=True))
    subtitle_font: FontStyle = field(default_factory=lambda: FontStyle(name="Times New Roman", size=16.0))
    author_font: FontStyle = field(default_factory=lambda: FontStyle(name="Times New Roman", size=14.0))
    alignment: Alignment = Alignment.CENTER


@dataclass
class PageStyle:
    top_margin: float = 1.0
    bottom_margin: float = 1.0
    left_margin: float = 1.25
    right_margin: float = 1.25
    header_distance: float = 0.5
    footer_distance: float = 0.5


@dataclass
class DocumentStyles:
    page: PageStyle = field(default_factory=PageStyle)
    cover_page: CoverPageStyle = field(default_factory=CoverPageStyle)
    content: ParagraphStyle = field(default_factory=ParagraphStyle)
    heading_main: HeadingStyle = field(default_factory=lambda: HeadingStyle(
        font=FontStyle(name="Times New Roman", size=16.0, bold=True),
        alignment=Alignment.CENTER,
    ))
    heading_sub: HeadingStyle = field(default_factory=lambda: HeadingStyle(
        font=FontStyle(name="Times New Roman", size=14.0, bold=True),
        alignment=Alignment.LEFT,
    ))
    heading_section: HeadingStyle = field(default_factory=lambda: HeadingStyle(
        font=FontStyle(name="Times New Roman", size=12.0, bold=True),
        alignment=Alignment.LEFT,
    ))
    bullet: BulletStyle = field(default_factory=BulletStyle)
    table: TableStyle = field(default_factory=TableStyle)
    figure: FigureStyle = field(default_factory=FigureStyle)
    reference: ReferenceStyle = field(default_factory=ReferenceStyle)
    chapter_title: HeadingStyle = field(default_factory=lambda: HeadingStyle(
        font=FontStyle(name="Times New Roman", size=16.0, bold=True),
        alignment=Alignment.CENTER,
    ))

    def get_heading(self, level: int = 1) -> HeadingStyle:
        if level <= 0:
            return self.chapter_title
        if level == 1:
            return self.heading_main
        if level == 2:
            return self.heading_sub
        return self.heading_section

    def to_dict(self) -> Dict:
        return {
            "page": {
                "top_margin": self.page.top_margin,
                "bottom_margin": self.page.bottom_margin,
                "left_margin": self.page.left_margin,
                "right_margin": self.page.right_margin,
            },
            "content": {
                "font": {"name": self.content.font.name, "size": self.content.font.size},
                "alignment": self.content.alignment.value,
                "line_spacing": self.content.line_spacing,
                "first_line_indent": self.content.first_line_indent,
            },
            "heading_main": {
                "font": {"name": self.heading_main.font.name, "size": self.heading_main.font.size, "bold": True},
                "alignment": self.heading_main.alignment.value,
            },
            "heading_sub": {
                "font": {"name": self.heading_sub.font.name, "size": self.heading_sub.font.size, "bold": True},
                "alignment": self.heading_sub.alignment.value,
            },
        }
