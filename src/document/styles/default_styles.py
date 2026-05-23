from .document_styles import DocumentStyles, FontStyle, ParagraphStyle, Alignment


def create_default_styles() -> DocumentStyles:
    return DocumentStyles()


def create_ieee_styles() -> DocumentStyles:
    s = DocumentStyles()
    s.content.font.name = "Times New Roman"
    s.content.font.size = 10.0
    s.content.line_spacing = 1.0
    s.content.first_line_indent = 0.0
    s.heading_main.font.name = "Times New Roman"
    s.heading_main.font.size = 14.0
    s.heading_main.alignment = Alignment.CENTER
    s.heading_sub.font.name = "Times New Roman"
    s.heading_sub.font.size = 12.0
    s.heading_sub.alignment = Alignment.LEFT
    s.page.top_margin = 0.75
    s.page.bottom_margin = 0.75
    s.page.left_margin = 0.75
    s.page.right_margin = 0.75
    return s


def create_compact_styles() -> DocumentStyles:
    s = DocumentStyles()
    s.content.line_spacing = 1.15
    s.content.first_line_indent = 0.0
    s.content.space_after = 3.0
    s.heading_main.space_before = 6.0
    s.heading_main.space_after = 3.0
    return s
