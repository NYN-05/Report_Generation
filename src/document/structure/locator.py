from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher
from .model import (
    StructuralNode, DocumentNode, SectionNode, ParagraphNode,
    TableNode, ImageNode, NodeType,
)


class SectionLocator:
    """Locates structural elements within a document tree."""

    def __init__(self, root: DocumentNode):
        self.root = root
        self._flat_cache: List[SectionNode] = []
        self._heading_cache: Dict[str, SectionNode] = {}
        self._build_cache()

    def _build_cache(self):
        self._flat_cache = self.root.find_by_type(NodeType.SECTION)
        self._heading_cache = {}
        for sec in self._flat_cache:
            h = sec.metadata.get("heading", "").strip().lower()
            if h:
                self._heading_cache[h] = sec

    def find_by_heading(self, heading: str, exact: bool = True) -> Optional[SectionNode]:
        heading_lower = heading.strip().lower()
        if exact:
            for key, sec in self._heading_cache.items():
                if key == heading_lower:
                    return sec
        best_match = None
        best_ratio = 0.0
        for key, sec in self._heading_cache.items():
            ratio = SequenceMatcher(None, heading_lower, key).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = sec
        if best_ratio >= 0.6:
            return best_match
        return None

    def find_by_heading_fuzzy(self, heading: str, threshold: float = 0.5) -> List[SectionNode]:
        heading_lower = heading.strip().lower()
        results = []
        for sec in self._flat_cache:
            h = sec.metadata.get("heading", "").strip().lower()
            ratio = SequenceMatcher(None, heading_lower, h).ratio()
            if ratio >= threshold:
                results.append((sec, ratio))
        results.sort(key=lambda x: x[1], reverse=True)
        return [r[0] for r in results]

    def find_by_hierarchy(self, path: List[str]) -> Optional[SectionNode]:
        current: Optional[StructuralNode] = self.root
        for segment in path:
            found = None
            for child in current.children:
                if isinstance(child, SectionNode):
                    h = child.metadata.get("heading", "").strip().lower()
                    if h == segment.strip().lower():
                        found = child
                        break
            if found is None:
                return None
            current = found
        return current

    def find_content_blocks(self, section: SectionNode) -> List[ParagraphNode]:
        return [c for c in section.children if isinstance(c, ParagraphNode)]

    def find_paragraphs(self, section: SectionNode) -> List[ParagraphNode]:
        return self.find_content_blocks(section)

    def find_tables(self, section: SectionNode) -> List[TableNode]:
        return [c for c in section.children if isinstance(c, TableNode)]

    def find_images(self, section: SectionNode) -> List[ImageNode]:
        return [c for c in section.children if isinstance(c, ImageNode)]

    def find_subsections(self, section: SectionNode) -> List[SectionNode]:
        return [c for c in section.children if isinstance(c, SectionNode)]

    def find_by_level(self, level: int) -> List[SectionNode]:
        return [s for s in self._flat_cache if s.metadata.get("level") == level]

    def find_by_id(self, node_id: str) -> Optional[StructuralNode]:
        return self.root.find_by_id(node_id)

    def get_parent(self, node: StructuralNode) -> Optional[StructuralNode]:
        return node.parent

    def get_path(self, node: StructuralNode) -> List[str]:
        path = []
        current = node
        while current is not None and current.node_type != NodeType.DOCUMENT:
            if isinstance(current, SectionNode):
                h = current.metadata.get("heading", "")
                path.insert(0, h)
            current = current.parent
        return path

    def get_sibling_index(self, node: StructuralNode) -> int:
        if node.parent is None:
            return -1
        for i, child in enumerate(node.parent.children):
            if child.node_id == node.node_id:
                return i
        return -1

    def find_section_containing(self, node: StructuralNode) -> Optional[SectionNode]:
        current = node.parent
        while current is not None:
            if isinstance(current, SectionNode):
                return current
            current = current.parent
        return None

    def find_next_sibling(self, node: StructuralNode) -> Optional[StructuralNode]:
        if node.parent is None:
            return None
        idx = self.get_sibling_index(node)
        if 0 <= idx < len(node.parent.children) - 1:
            return node.parent.children[idx + 1]
        return None

    def find_previous_sibling(self, node: StructuralNode) -> Optional[StructuralNode]:
        if node.parent is None:
            return None
        idx = self.get_sibling_index(node)
        if idx > 0:
            return node.parent.children[idx - 1]
        return None

    def get_all_headings(self) -> List[Dict[str, Any]]:
        return [
            {"heading": s.metadata.get("heading", ""), "level": s.metadata.get("level", 1)}
            for s in self._flat_cache
        ]

    def get_hierarchy(self) -> List[Dict[str, Any]]:
        result = []
        for sec in self._flat_cache:
            path = self.get_path(sec)
            result.append({
                "heading": sec.metadata.get("heading", ""),
                "level": sec.metadata.get("level", 1),
                "path": path,
                "node_id": sec.node_id,
                "child_count": len(sec.children),
                "subsection_count": len(self.find_subsections(sec)),
            })
        return result
