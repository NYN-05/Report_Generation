import re
from typing import List
from docx import Document
from docx.oxml.ns import qn

from .models import CrossReferenceInfo
from src.core.logger import get_logger

logger = get_logger(__name__)


class CrossReferenceDetector:
    """Detects cross-references (figure, table, section, equation refs)."""

    def __init__(self, doc: Document):
        self._doc = doc

    def detect(self) -> List[CrossReferenceInfo]:
        results: List[CrossReferenceInfo] = []
        for pi, para in enumerate(self._doc.paragraphs):
            for run in para.runs:
                instr = run._element.find(qn('w:instrText'))
                if instr is not None and instr.text:
                    text = instr.text
                    ref_type = self._classify_ref(text)
                    if ref_type:
                        ref_text = self._extract_ref(text)
                        results.append(CrossReferenceInfo(
                            reference_type=ref_type,
                            reference_text=ref_text or text,
                            paragraph_index=pi,
                            context_text=para.text[:100],
                        ))
        return results

    def _classify_ref(self, instr: str) -> str:
        if ' REF ' in instr or 'ref ' in instr.lower():
            return "section"
        if ' PAGEREF ' in instr:
            return "page"
        if ' NOTEREF ' in instr:
            return "footnote"
        return ""

    @staticmethod
    def _extract_ref(instr: str) -> str:
        m = re.search(r'(?:REF|PAGEREF|NOTEREF)\s+(\S+)', instr)
        if m:
            return m.group(1)
        return ""
