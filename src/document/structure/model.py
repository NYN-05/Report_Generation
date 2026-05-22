import uuid
from enum import Enum
from typing import Dict, List, Any, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from docx import Document as DocxDocument
from docx.text.paragraph import Paragraph
from docx.table import Table
from docx.oxml.ns import qn

T = TypeVar("T")


class NodeType(Enum):
    DOCUMENT = "document"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    IMAGE = "image"
    TOC = "toc"
    COVER_PAGE = "cover_page"
    LIST_BLOCK = "list_block"
    PAGE_BREAK = "page_break"


@dataclass
class StructuralNode:
    node_type: NodeType
    element: Any = None
    children: List["StructuralNode"] = field(default_factory=list)
    parent: Optional["StructuralNode"] = None
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_child(self, child: "StructuralNode"):
        child.parent = self
        self.children.append(child)

    def insert_child(self, index: int, child: "StructuralNode"):
        child.parent = self
        self.children.insert(index, child)

    def remove_child(self, child: "StructuralNode"):
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def find_by_id(self, node_id: str) -> Optional["StructuralNode"]:
        if self.node_id == node_id:
            return self
        for child in self.children:
            result = child.find_by_id(node_id)
            if result:
                return result
        return None

    def find_by_type(self, node_type) -> List["StructuralNode"]:
        if isinstance(node_type, str):
            node_type = NodeType(node_type)
        results = []
        if self.node_type == node_type:
            results.append(self)
        for child in self.children:
            results.extend(child.find_by_type(node_type))
        return results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "metadata": self.metadata,
            "children": [c.to_dict() for c in self.children],
        }

    def __repr__(self) -> str:
        return f"<{self.node_type.value} id={self.node_id}>"


class DocumentNode(StructuralNode):
    def __init__(self):
        super().__init__(node_type=NodeType.DOCUMENT, metadata={"title": ""})


class SectionNode(StructuralNode):
    def __init__(self, heading: str = "", level: int = 1, element: Any = None):
        super().__init__(
            node_type=NodeType.SECTION,
            element=element,
            metadata={"heading": heading, "level": level},
        )

    @property
    def heading(self) -> str:
        return self.metadata.get("heading", "")

    @heading.setter
    def heading(self, value: str):
        self.metadata["heading"] = value

    @property
    def level(self) -> int:
        return self.metadata.get("level", 1)

    @level.setter
    def level(self, value: int):
        self.metadata["level"] = value

    def __repr__(self) -> str:
        return f"<Section lvl={self.level} heading='{self.heading[:40]}' id={self.node_id}>"


class ParagraphNode(StructuralNode):
    def __init__(self, text: str = "", element: Any = None, style: str = "Normal"):
        super().__init__(
            node_type=NodeType.PARAGRAPH,
            element=element,
            metadata={"text": text, "style": style},
        )

    @property
    def text(self) -> str:
        return self.metadata.get("text", "")

    def __repr__(self) -> str:
        t = self.text[:50]
        return f"<Paragraph text='{t}' id={self.node_id}>"


class TableNode(StructuralNode):
    def __init__(self, element: Any = None, rows: int = 0, cols: int = 0):
        super().__init__(
            node_type=NodeType.TABLE,
            element=element,
            metadata={"rows": rows, "cols": cols},
        )

    def __repr__(self) -> str:
        return f"<Table {self.metadata.get('rows', 0)}x{self.metadata.get('cols', 0)} id={self.node_id}>"


class ImageNode(StructuralNode):
    def __init__(self, element: Any = None, alt_text: str = ""):
        super().__init__(
            node_type=NodeType.IMAGE,
            element=element,
            metadata={"alt_text": alt_text},
        )

    def __repr__(self) -> str:
        return f"<Image alt='{self.metadata.get('alt_text', '')}' id={self.node_id}>"


class TocNode(StructuralNode):
    def __init__(self):
        super().__init__(node_type=NodeType.TOC, metadata={})

    def __repr__(self) -> str:
        return "<TOC>"


class CoverPageNode(StructuralNode):
    def __init__(self, title: str = "", subtitle: str = ""):
        super().__init__(
            node_type=NodeType.COVER_PAGE,
            metadata={"title": title, "subtitle": subtitle},
        )

    def __repr__(self) -> str:
        return f"<CoverPage title='{self.metadata.get('title', '')}' id={self.node_id}>"


class ListBlockNode(StructuralNode):
    def __init__(self, items: List[str] = None, ordered: bool = False):
        super().__init__(
            node_type=NodeType.LIST_BLOCK,
            metadata={"items": items or [], "ordered": ordered},
        )

    def __repr__(self) -> str:
        return f"<ListBlock {'ordered' if self.metadata.get('ordered') else 'bullet'} count={len(self.metadata.get('items', []))}>"


def _get_image_info(paragraph: Paragraph) -> Optional[Dict]:
    for run in paragraph.runs:
        drawing = run._element.findall(qn('w:drawing'))
        if drawing:
            for d in drawing:
                blip = d.findall('.//' + qn('a:blip'))
                if blip:
                    embed = blip[0].get(qn('r:embed'))
                    alt_text = ""
                    descr = d.findall('.//' + qn('wp:inline') + '/'
                                      + qn('wp:docPr'))
                    if descr:
                        alt_text = descr[0].get('descr', '')
                    return {"embed": embed, "alt_text": alt_text}
    return None


def _is_heading(paragraph: Paragraph) -> Optional[int]:
    style_name = paragraph.style.name if paragraph.style else ""
    if style_name.startswith("Heading"):
        level = 1
        try:
            level = int(style_name[-1])
        except (ValueError, IndexError):
            pass
        return level
    return None


def _is_toc(paragraph: Paragraph) -> bool:
    text = paragraph.text.strip().lower()
    if "table of contents" in text:
        return True
    for run in paragraph.runs:
        instr = run._element.find(qn('w:instrText'))
        if instr is not None and "TOC" in (instr.text or ""):
            return True
    return False


def _has_page_break(paragraph: Paragraph) -> bool:
    for run in paragraph.runs:
        br = run._element.find(qn('w:br'))
        if br is not None and br.get(qn('w:type')) == 'page':
            return True
    pPr = paragraph._element.find(qn('w:pPr'))
    if pPr is not None:
        pb = pPr.find(qn('w:pageBreakBefore'))
        if pb is not None:
            return True
    return False


def _is_list_paragraph(paragraph: Paragraph) -> bool:
    style_name = paragraph.style.name if paragraph.style else ""
    return "List" in style_name


def build_tree(doc: DocxDocument) -> DocumentNode:
    root = DocumentNode()
    section_stack: List[SectionNode] = []
    preamble_nodes: List[ParagraphNode] = []
    list_items: List[ParagraphNode] = []
    list_ordered = False
    has_seen_heading = False
    has_seen_page_break = False

    def _finalize_preamble():
        nonlocal has_seen_page_break, preamble_nodes
        if preamble_nodes and has_seen_page_break:
            cover = CoverPageNode()
            for n in preamble_nodes:
                cover.add_child(n)
            root.add_child(cover)
        elif preamble_nodes:
            for n in preamble_nodes:
                root.add_child(n)
        preamble_nodes = []

    for para in doc.paragraphs:
        text = para.text.strip()

        if _has_page_break(para) and not has_seen_heading:
            has_seen_page_break = True
            _finalize_preamble()
            if not text:
                continue

        img_info = _get_image_info(para)
        if img_info:
            _finalize_preamble()
            inode = ImageNode(element=para, alt_text=img_info["alt_text"])
            if section_stack:
                section_stack[-1].add_child(inode)
            else:
                root.add_child(inode)
            continue

        heading_level = _is_heading(para)
        if heading_level is not None:
            has_seen_heading = True
            _finalize_preamble()

            if _is_toc(para):
                tn = TocNode()
                if list_items:
                    _flush_list(list_items, list_ordered, section_stack[-1] if section_stack else root)
                    list_items = []
                if section_stack:
                    section_stack[-1].add_child(tn)
                else:
                    root.add_child(tn)
                continue

            if list_items:
                _flush_list(list_items, list_ordered, section_stack[-1] if section_stack else root)
                list_items = []

            new_section = SectionNode(heading=text, level=heading_level, element=para)

            while section_stack and section_stack[-1].level >= heading_level:
                section_stack.pop()

            if not section_stack:
                root.add_child(new_section)
            else:
                section_stack[-1].add_child(new_section)

            section_stack.append(new_section)
            continue

        if not has_seen_heading and not has_seen_page_break:
            if text:
                pn = ParagraphNode(text=text, element=para,
                                   style=para.style.name if para.style else "Normal")
                preamble_nodes.append(pn)
            continue

        _finalize_preamble()

        if _is_list_paragraph(para) and text:
            pn = ParagraphNode(text=text, element=para,
                               style=para.style.name if para.style else "List")
            list_items.append(pn)
            if "Number" in (para.style.name or ""):
                list_ordered = True
            continue
        else:
            if list_items:
                _flush_list(list_items, list_ordered, section_stack[-1] if section_stack else root)
                list_items = []

        if text or _has_page_break(para):
            pn = ParagraphNode(text=text, element=para,
                               style=para.style.name if para.style else "Normal")
            if _has_page_break(para) and has_seen_heading:
                pn.metadata["page_break_before"] = True
            if section_stack:
                section_stack[-1].add_child(pn)
            else:
                root.add_child(pn)

    if list_items:
        _flush_list(list_items, list_ordered, section_stack[-1] if section_stack else root)

    _finalize_preamble()
    _attach_tables_to_sections(doc, root)

    return root


def _flush_list(items: List[ParagraphNode], ordered: bool, parent: StructuralNode):
    if not items:
        return
    lb = ListBlockNode(
        items=[p.metadata.get("text", "") for p in items],
        ordered=ordered,
    )
    for p in items:
        lb.add_child(p)
    parent.add_child(lb)


def _attach_tables_to_sections(doc: DocxDocument, root: DocumentNode):
    all_sections = root.find_by_type(NodeType.SECTION)
    if not all_sections:
        return

    body = doc.element.body
    body_children = list(body)

    para_to_section = {}
    for sec in all_sections:
        para_obj = sec.element
        if para_obj is None:
            continue
        para_xml = para_obj._element
        for i, p in enumerate(doc.paragraphs):
            if p._element is para_xml:
                para_to_section[i] = sec
                break

    p_idx = 0
    current_section = None
    for child in body_children:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

        if tag == 'p':
            if p_idx in para_to_section:
                current_section = para_to_section[p_idx]
            p_idx += 1

        elif tag == 'tbl':
            if current_section is not None:
                tn = TableNode(
                    element=child,
                    rows=sum(1 for _ in child.iter(qn('w:tr'))),
                    cols=0,
                )
                current_section.add_child(tn)


def tree_to_dict(node: StructuralNode) -> Dict[str, Any]:
    return node.to_dict()
