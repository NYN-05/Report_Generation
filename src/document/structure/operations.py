import copy
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from docx import Document as DocxDocument
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.table import Table

from .model import (
    StructuralNode, DocumentNode, SectionNode, ParagraphNode,
    TableNode, ImageNode, CoverPageNode, TocNode, ListBlockNode, NodeType,
    build_tree,
)
from .locator import SectionLocator
from src.document.formatter.font import FontFormatter
from src.document.formatter.paragraph import ParagraphFormatter
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EditOperationResult:
    success: bool
    modified_elements: List[str] = field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Low-level DOCX body helpers
# ---------------------------------------------------------------------------

def _make_rpr_for_text(font_name: str = None, font_size: int = None,
                        bold: bool = None, italic: bool = None,
                        color: str = None) -> OxmlElement:
    return FontFormatter.format_run_xml(
        font_name=font_name, font_size=font_size,
        bold=bold, italic=italic, color=color,
    )


def _make_paragraph_xml(text: str, font_name: str = None,
                         font_size: int = None,
                         alignment: str = None,
                         space_after: int = None) -> OxmlElement:
    p = OxmlElement('w:p')
    pPr = ParagraphFormatter.format_paragraph_xml(
        alignment=alignment, space_after=space_after,
    )
    if pPr is not None:
        p.insert(0, pPr)
    rPr = _make_rpr_for_text(font_name=font_name, font_size=font_size)
    r = OxmlElement('w:r')
    r.append(rPr)
    t = OxmlElement('w:t')
    t.text = text
    t.set(qn('xml:space'), 'preserve')
    r.append(t)
    p.append(r)
    return p


def _copy_pPr_from_source(source_p_xml: OxmlElement,
                           target_p_xml: OxmlElement):
    src_pPr = source_p_xml.find(qn('w:pPr'))
    if src_pPr is None:
        return
    existing = target_p_xml.find(qn('w:pPr'))
    if existing is not None:
        target_p_xml.remove(existing)
    target_p_xml.insert(0, copy.deepcopy(src_pPr))


def _make_heading_xml(text: str, level: int = 1,
                       source_heading_xml: OxmlElement = None) -> OxmlElement:
    p = OxmlElement('w:p')
    pPr = OxmlElement('w:pPr')
    pStyle = OxmlElement('w:pStyle')
    pStyle.set(qn('w:val'), f'Heading{level}')
    pPr.append(pStyle)
    p.insert(0, pPr)
    rPr = FontFormatter.format_run_xml(
        font_name="Calibri",
        font_size=max(12, 16 - level * 2),
        bold=True,
    )
    r = OxmlElement('w:r')
    r.append(rPr)
    t = OxmlElement('w:t')
    t.text = text
    t.set(qn('xml:space'), 'preserve')
    r.append(t)
    p.append(r)
    if source_heading_xml is not None:
        _copy_pPr_from_source(source_heading_xml, p)
    return p


def _make_paragraph_node(text: str) -> ParagraphNode:
    return ParagraphNode(text=text)


def _body_children(body) -> List:
    return list(body)


def _tag(elem) -> str:
    return elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag


def _contains_image(elem) -> bool:
    return len(elem.findall('.//' + qn('w:drawing'))) > 0


def _is_section_break(elem) -> bool:
    if _tag(elem) == 'sectPr':
        return True
    pPr = elem.find(qn('w:pPr'))
    if pPr is not None:
        return pPr.find(qn('w:sectPr')) is not None
    return False


def _find_sibling_heading_xml(parent: StructuralNode, level: int,
                               doc: DocxDocument) -> Optional[OxmlElement]:
    for child in parent.children:
        if isinstance(child, SectionNode) and child.level == level:
            if child.element is not None:
                return child.element._element
    for child in parent.children:
        if isinstance(child, SectionNode):
            result = _find_sibling_heading_xml(child, level, doc)
            if result is not None:
                return result
    return None


def _find_heading_body_index(doc: DocxDocument, section: SectionNode) -> int:
    if section.element is None:
        return -1
    heading_xml = section.element._element
    body = doc.element.body
    for i, child in enumerate(body):
        if child is heading_xml:
            return i
    return -1


def _build_section_body_map(doc: DocxDocument, root: DocumentNode
                            ) -> Dict[int, str]:
    all_sections = root.find_by_type(NodeType.SECTION)
    para_idx_to_sec_id = {}
    for sec in all_sections:
        if sec.element is None:
            continue
        target_xml = sec.element._element
        para_list = doc.paragraphs
        for i, p in enumerate(para_list):
            if p._element is target_xml:
                para_idx_to_sec_id[i] = sec.node_id
                break

    body = doc.element.body
    body_children_list = list(body)
    result = {}
    p_idx = 0
    current_sec_id = None
    for child_idx, child in enumerate(body_children_list):
        tag = _tag(child)
        if tag == 'p':
            if p_idx in para_idx_to_sec_id:
                current_sec_id = para_idx_to_sec_id[p_idx]
            p_idx += 1
        if current_sec_id is not None:
            result[child_idx] = current_sec_id
    return result


def _section_body_range(doc: DocxDocument, root: DocumentNode,
                        section: SectionNode) -> Tuple[int, int]:
    child_ids = set()
    for s in section.find_by_type(NodeType.SECTION):
        child_ids.add(s.node_id)
    child_ids.add(section.node_id)

    body_map = _build_section_body_map(doc, root)
    indices = sorted([idx for idx, sid in body_map.items()
                      if sid in child_ids])
    if not indices:
        return (-1, -1)
    return (indices[0], indices[-1] + 1)


def _sibling_section_body_start(doc: DocxDocument, root: DocumentNode,
                                section: SectionNode) -> int:
    parent = section.parent
    if parent is None:
        return len(list(doc.element.body))
    siblings = [c for c in parent.children
                if isinstance(c, SectionNode)]
    my_idx = -1
    for i, s in enumerate(siblings):
        if s.node_id == section.node_id:
            my_idx = i
            break
    if my_idx < len(siblings) - 1:
        nxt = siblings[my_idx + 1]
        return _find_heading_body_index(doc, nxt)
    if parent.node_type == NodeType.DOCUMENT:
        return len(list(doc.element.body))
    return _sibling_section_body_start(doc, root, parent)


def _collect_paragraph_nodes(section: SectionNode) -> List[ParagraphNode]:
    result = []
    for child in section.children:
        if isinstance(child, ParagraphNode):
            result.append(child)
        elif isinstance(child, SectionNode):
            result.extend(_collect_paragraph_nodes(child))
    return result


def _rebuild_tree_inplace(root: DocumentNode, doc: DocxDocument):
    new_root = build_tree(doc)
    root.children = new_root.children
    for child in root.children:
        child.parent = root
    root.metadata = new_root.metadata


# ---------------------------------------------------------------------------
# Base operation
# ---------------------------------------------------------------------------

class EditOperation(ABC):
    def __init__(self, root: DocumentNode, docx: DocxDocument):
        self.root = root
        self.docx = docx
        self.locator = SectionLocator(root)
        self.default_font_name: Optional[str] = None
        self.default_font_size: Optional[int] = None

    def set_default_font(self, font_name: str = None, font_size: int = None):
        self.default_font_name = font_name
        self.default_font_size = font_size

    @abstractmethod
    def execute(self, **kwargs) -> EditOperationResult:
        pass


# ---------------------------------------------------------------------------
# ReplaceSection
# ---------------------------------------------------------------------------

class ReplaceSection(EditOperation):
    def execute(self, target: str = None, target_node: SectionNode = None,
                new_content: str = "", new_paragraphs: List[str] = None,
                preserve_children: bool = False, **kwargs) -> EditOperationResult:
        section = target_node or self.locator.find_by_heading(target)
        if section is None:
            return EditOperationResult(
                success=False, error=f"Section not found: {target or target_node}"
            )

        modified = []

        # Determine body range [start, end) for this section
        start = _find_heading_body_index(self.docx, section)
        if start == -1:
            return EditOperationResult(
                success=False, error="Cannot locate section in document body"
            )
        end = _sibling_section_body_start(self.docx, self.root, section)

        body = self.docx.element.body
        body_children_list = list(body)

        # Collect existing runs of content elements before the end boundary
        content = new_paragraphs if new_paragraphs else []
        if not content and new_content:
            for para_text in new_content.split("\n\n"):
                para_text = para_text.strip()
                if para_text:
                    content.append(para_text)

        # Remove content elements (keep heading if not renaming)
        keep_heading = not kwargs.get("new_heading")
        elements_to_remove = []
        if keep_heading:
            remove_range = range(start + 1, min(end, len(body_children_list)))
        else:
            remove_range = range(start, min(end, len(body_children_list)))

        for idx in remove_range:
            if idx < len(body_children_list):
                elem = body_children_list[idx]
                if (preserve_children and
                    (_tag(elem) == 'tbl' or _contains_image(elem))):
                    continue
                if _is_section_break(elem):
                    continue
                elements_to_remove.append(elem)

        for elem in elements_to_remove:
            body.remove(elem)

        old_heading = section.metadata.get("heading", "")
        new_heading_val = kwargs.get("new_heading", "")
        if new_heading_val:
            section.heading = new_heading_val
            modified.append(f"renamed heading: '{old_heading}' -> '{new_heading_val}'")
            heading_idx = _find_heading_body_index(self.docx, section)
            if heading_idx != -1 and heading_idx < len(body_children_list):
                old_heading_xml = body_children_list[heading_idx]
                new_h_xml = _make_heading_xml(new_heading_val, section.level,
                                               source_heading_xml=old_heading_xml)
                body.replace(body_children_list[heading_idx], new_h_xml)

        # Insert new content after the heading (or at start if heading was removed)
        insert_pos = _find_heading_body_index(self.docx, section)
        if insert_pos == -1:
            insert_pos = start

        if not preserve_children:
            to_remove_children = [
                c for c in section.children
                if not isinstance(c, (TableNode, ImageNode, SectionNode))
            ]
            for child in to_remove_children:
                section.remove_child(child)

        if content:
            new_xml_elements = []
            for para_text in content:
                p_xml = _make_paragraph_xml(para_text,
                                            font_name=self.default_font_name,
                                            font_size=self.default_font_size)
                new_xml_elements.append(p_xml)
                pn = ParagraphNode(text=para_text)
                section.add_child(pn)
                modified.append(f"paragraph: {para_text[:50]}")

            insert_at = insert_pos + 1
            current_children = list(body)
            for xml_elem in new_xml_elements:
                if insert_at <= len(current_children):
                    body.insert(insert_at, xml_elem)
                    insert_at += 1
                else:
                    body.append(xml_elem)

        _rebuild_tree_inplace(self.root, self.docx)

        return EditOperationResult(
            success=True,
            modified_elements=modified,
        )


# ---------------------------------------------------------------------------
# InsertSection
# ---------------------------------------------------------------------------

class InsertSection(EditOperation):
    def execute(self, target: str = None, target_node: StructuralNode = None,
                new_section: SectionNode = None, heading: str = "",
                content: str = "", level: int = 1, position: str = "after",
                **kwargs) -> EditOperationResult:
        anchor = target_node or (
            self.locator.find_by_heading(target) if target else None
        )

        if anchor is None and target is not None:
            return EditOperationResult(
                success=False, error=f"Target section not found: {target}"
            )

        if new_section is None:
            new_section = SectionNode(heading=heading, level=level)
            if content:
                for para_text in content.split("\n\n"):
                    para_text = para_text.strip()
                    if para_text:
                        new_section.add_child(ParagraphNode(text=para_text))

        body = self.docx.element.body

        if anchor is None:
            parent = self.root
            insert_idx = len(parent.children)
            body_insert = len(list(body))
        elif position in ("first_child", "last_child"):
            parent = anchor
            if position == "last_child":
                # Insert after last body element of this section
                s_range = _section_body_range(self.docx, self.root, anchor)
                body_insert = s_range[1] if s_range != (-1, -1) else (
                    _find_heading_body_index(self.docx, anchor) + 1
                )
            else:
                body_insert = _find_heading_body_index(self.docx, anchor) + 1
                if body_insert <= 0:
                    body_insert = 0
            insert_idx = len(parent.children) if position == "last_child" else 0
        else:
            parent = anchor.parent or self.root
            siblings = parent.children
            anchor_idx = -1
            for i, c in enumerate(siblings):
                if c.node_id == anchor.node_id:
                    anchor_idx = i
                    break

            if position == "after":
                insert_idx = anchor_idx + 1
                s_range = _section_body_range(self.docx, self.root, anchor)
                body_insert = s_range[1] if s_range != (-1, -1) else (
                    _find_heading_body_index(self.docx, anchor) + 1
                )
            else:
                insert_idx = anchor_idx
                body_insert = _find_heading_body_index(self.docx, anchor)
                if body_insert < 0:
                    body_insert = 0

        source_heading_xml = _find_sibling_heading_xml(parent, new_section.level,
                                                        self.docx)
        new_xml = _make_heading_xml(new_section.heading, new_section.level,
                                     source_heading_xml=source_heading_xml)
        current_children = list(body)
        if body_insert < len(current_children):
            body.insert(body_insert, new_xml)
        else:
            body.append(new_xml)
        body_insert += 1

        child_paras = _collect_paragraph_nodes(new_section)
        for pn in child_paras:
            px = _make_paragraph_xml(pn.text,
                                     font_name=self.default_font_name,
                                     font_size=self.default_font_size)
            if body_insert < len(list(body)):
                body.insert(body_insert, px)
            else:
                body.append(px)
            body_insert += 1

        parent.insert_child(insert_idx, new_section)

        _rebuild_tree_inplace(self.root, self.docx)

        return EditOperationResult(
            success=True,
            modified_elements=[
                f"inserted section: {new_section.metadata.get('heading', 'Untitled')}"
            ],
        )


# ---------------------------------------------------------------------------
# ExpandSection
# ---------------------------------------------------------------------------

class ExpandSection(EditOperation):
    def execute(self, target: str = None, target_node: SectionNode = None,
                new_subsections: List[Dict[str, Any]] = None,
                append_paragraphs: List[str] = None,
                **kwargs) -> EditOperationResult:
        section = target_node or self.locator.find_by_heading(target)
        if section is None:
            return EditOperationResult(
                success=False, error=f"Section not found: {target}"
            )

        modified = []
        body = self.docx.element.body

        s_range = _section_body_range(self.docx, self.root, section)
        body_insert = s_range[1] if s_range != (-1, -1) else (
            _find_heading_body_index(self.docx, section) + 1
        )
        if body_insert < 0:
            body_insert = 0

        if new_subsections:
            for sub_data in new_subsections:
                sub_heading = sub_data.get("heading", "Subsection")
                sub_content = sub_data.get("content", "")
                sub_level = sub_data.get("level", section.level + 1)

                sub_source = _find_sibling_heading_xml(section, sub_level,
                                                        self.docx)
                sub_xml = _make_heading_xml(sub_heading, sub_level,
                                             source_heading_xml=sub_source)
                current_children = list(body)
                if body_insert < len(current_children):
                    body.insert(body_insert, sub_xml)
                else:
                    body.append(sub_xml)
                body_insert += 1

                sub_section = SectionNode(heading=sub_heading, level=sub_level)
                if sub_content:
                    for para_text in sub_content.split("\n\n"):
                        para_text = para_text.strip()
                        if para_text:
                            px = _make_paragraph_xml(para_text,
                                                     font_name=self.default_font_name,
                                                     font_size=self.default_font_size)
                            if body_insert < len(list(body)):
                                body.insert(body_insert, px)
                            else:
                                body.append(px)
                            body_insert += 1
                            sub_section.add_child(ParagraphNode(text=para_text))

                section.add_child(sub_section)
                modified.append(f"subsection: {sub_heading}")

        if append_paragraphs:
            for para_text in append_paragraphs:
                px = _make_paragraph_xml(para_text,
                                         font_name=self.default_font_name,
                                         font_size=self.default_font_size)
                current_children = list(body)
                if body_insert < len(current_children):
                    body.insert(body_insert, px)
                else:
                    body.append(px)
                body_insert += 1
                pn = ParagraphNode(text=para_text)
                section.add_child(pn)
                modified.append(f"paragraph: {para_text[:50]}")

        _rebuild_tree_inplace(self.root, self.docx)

        return EditOperationResult(
            success=True,
            modified_elements=modified,
        )


# ---------------------------------------------------------------------------
# DeleteSection
# ---------------------------------------------------------------------------

class DeleteSection(EditOperation):
    def execute(self, target: str = None, target_node: SectionNode = None,
                delete_children_only: bool = False,
                **kwargs) -> EditOperationResult:
        section = target_node or self.locator.find_by_heading(target)
        if section is None:
            return EditOperationResult(
                success=False, error=f"Section not found: {target}"
            )

        heading = section.metadata.get("heading", "")

        if delete_children_only:
            s_range = _section_body_range(self.docx, self.root, section)
            body = self.docx.element.body
            elements_to_remove = []
            heading_idx = _find_heading_body_index(self.docx, section)
            for idx in range(s_range[0] if s_range != (-1, -1) else heading_idx + 1,
                             s_range[1] if s_range != (-1, -1) else len(list(body))):
                if idx == heading_idx:
                    continue
                children_list = list(body)
                if idx < len(children_list):
                    elem = children_list[idx]
                    if _tag(elem) == 'tbl' or _contains_image(elem):
                        continue
                    if _is_section_break(elem):
                        continue
                    elements_to_remove.append(elem)

            for elem in elements_to_remove:
                try:
                    body.remove(elem)
                except ValueError:
                    pass

            to_remove = list(section.children)
            for child in to_remove:
                section.remove_child(child)
            modified = [f"cleared content of: {heading}"]
        else:
            s_range = _section_body_range(self.docx, self.root, section)
            body = self.docx.element.body
            children_list = list(body)
            elements_to_remove = []
            for idx in range(s_range[0], min(s_range[1], len(children_list))):
                if idx < len(children_list):
                    elem = children_list[idx]
                    if _is_section_break(elem):
                        continue
                    elements_to_remove.append(elem)

            for elem in elements_to_remove:
                try:
                    body.remove(elem)
                except ValueError:
                    pass

            parent = section.parent
            if parent is None:
                return EditOperationResult(
                    success=False, error="Cannot delete root document node"
                )
            parent.remove_child(section)
            modified = [f"deleted section: {heading}"]

        _rebuild_tree_inplace(self.root, self.docx)

        return EditOperationResult(
            success=True,
            modified_elements=modified,
        )


# ---------------------------------------------------------------------------
# MoveSection
# ---------------------------------------------------------------------------

class MoveSection(EditOperation):
    def execute(self, target: str = None, target_node: SectionNode = None,
                destination: str = None, dest_node: SectionNode = None,
                position: str = "after",
                **kwargs) -> EditOperationResult:
        section = target_node or self.locator.find_by_heading(target)
        if section is None:
            return EditOperationResult(
                success=False, error=f"Source section not found: {target}"
            )

        if dest_node is None and destination:
            dest_node = self.locator.find_by_heading(destination)

        if dest_node is None and destination is not None:
            return EditOperationResult(
                success=False, error=f"Destination section not found: {destination}"
            )

        old_parent = section.parent
        if old_parent is None:
            return EditOperationResult(
                success=False, error="Cannot move root document node"
            )

        body = self.docx.element.body

        # --- 1. Remove source elements ---
        s_range = _section_body_range(self.docx, self.root, section)
        children_list = list(body)
        source_elements = []
        for idx in range(s_range[0], min(s_range[1], len(children_list))):
            if idx < len(children_list):
                source_elements.append(children_list[idx])

        for elem in source_elements:
            try:
                body.remove(elem)
            except ValueError:
                pass

        old_parent.remove_child(section)

        # --- 2. Determine insertion point ---
        if dest_node:
            target_parent = dest_node.parent
            if target_parent is None:
                old_parent.add_child(section)
                return EditOperationResult(
                    success=False, error="Destination has no parent"
                )

            if position in ("first_child", "last_child"):
                body_insert = _find_heading_body_index(self.docx, dest_node)
                if body_insert < 0:
                    body_insert = 0
                if position == "last_child":
                    dr = _section_body_range(self.docx, self.root, dest_node)
                    body_insert = dr[1] if dr != (-1, -1) else body_insert + 1
                else:
                    body_insert += 1
                parent = dest_node
                insert_idx = 0 if position == "first_child" else len(dest_node.children)
            else:
                siblings = target_parent.children
                dest_idx = -1
                for i, c in enumerate(siblings):
                    if c.node_id == dest_node.node_id:
                        dest_idx = i
                        break
                if position == "after":
                    insert_idx = dest_idx + 1
                    dr = _section_body_range(self.docx, self.root, dest_node)
                    body_insert = dr[1] if dr != (-1, -1) else (
                        _find_heading_body_index(self.docx, dest_node) + 1
                    )
                else:
                    insert_idx = dest_idx
                    body_insert = _find_heading_body_index(self.docx, dest_node)
                    if body_insert < 0:
                        body_insert = 0
                parent = target_parent

            if body_insert < 0:
                body_insert = 0
            current_len = len(list(body))
            for i, elem in enumerate(source_elements):
                pos = body_insert + i
                if pos < current_len:
                    body.insert(pos, elem)
                else:
                    body.append(elem)
            target_parent.insert_child(insert_idx, section)
        else:
            old_parent.add_child(section)
            body.append(source_elements[0])

        name = section.metadata.get("heading", "Untitled")

        _rebuild_tree_inplace(self.root, self.docx)

        return EditOperationResult(
            success=True,
            modified_elements=[f"moved section: {name}"],
        )
