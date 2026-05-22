import os
from typing import Dict, Any, Optional
from docx import Document as DocxDocument
from docx import Document

from .models import DocKnowledgeGraph
from .heading import HeadingDetector
from .classifier import SectionClassifier
from .styles import StyleExtractor
from .tables import TableDetector
from .images import ImageDetector
from .references import ReferenceDetector
from .graph import KnowledgeGraphBuilder


class DocxAnalyzer:
    """Main orchestrator for deep DOCX document analysis."""

    def __init__(self):
        self._last_graph: Optional[DocKnowledgeGraph] = None

    def analyze(self, filepath: str) -> DocKnowledgeGraph:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Document not found: {filepath}")

        doc = Document(filepath)
        filename = os.path.basename(filepath)

        builder = KnowledgeGraphBuilder(doc)
        graph = builder.build(filename=filename)
        self._last_graph = graph
        return graph

    def analyze_doc(self, doc: DocxDocument, filename: str = "document.docx") -> DocKnowledgeGraph:
        builder = KnowledgeGraphBuilder(doc)
        graph = builder.build(filename=filename)
        self._last_graph = graph
        return graph

    def get_summary(self) -> Dict[str, Any]:
        if not self._last_graph:
            return {"error": "No analysis performed yet"}
        return self._last_graph.to_dict()

    def get_statistics(self) -> Dict[str, Any]:
        if not self._last_graph:
            return {}
        return self._last_graph.statistics

    def get_heading_hierarchy(self) -> list:
        if not self._last_graph:
            return []
        detector = HeadingDetector.__new__(HeadingDetector)
        detector._headings = self._last_graph.headings
        return detector.get_hierarchy_tree()

    def get_section_types(self) -> Dict[str, int]:
        if not self._last_graph:
            return {}
        counts: Dict[str, int] = {}
        for sec in self._last_graph.sections:
            st = sec.section_type
            counts[st] = counts.get(st, 0) + 1
            for s2 in sec.children:
                counts[s2.section_type] = counts.get(s2.section_type, 0) + 1
        return counts

    def export_json(self, filepath: str) -> bool:
        if not self._last_graph:
            return False
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._last_graph.to_dict(), f, indent=2, default=str)
        return True
