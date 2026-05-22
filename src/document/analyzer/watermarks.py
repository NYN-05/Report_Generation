from typing import List
from docx import Document as DocxDocument
from docx.oxml.ns import qn

from .models import WatermarkInfo


class WatermarkDetector:
    """Detects watermarks in each document section's headers."""

    def __init__(self, doc: DocxDocument):
        self.doc = doc

    def detect(self) -> List[WatermarkInfo]:
        results: List[WatermarkInfo] = []
        for si, section in enumerate(self.doc.sections):
            for header in section.header.paragraphs:
                wm = self._extract_from_para(header._element, si)
                if wm is not None:
                    results.append(wm)
        return results

    def _extract_from_para(self, para_elem, section_index: int) -> WatermarkInfo:
        nsmap = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
            'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        }
        watermark = para_elem.find('.//w:watermark', nsmap)
        if watermark is None:
            return None
        wtype = watermark.get(qn('w:type'), 'text')
        texts = watermark.findall('.//w:docPart', nsmap)
        if not texts:
            texts = watermark.findall('.//w:t', nsmap)
        text_content = " ".join(t.text or "" for t in texts if t.text).strip()
        if not text_content:
            texts2 = watermark.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
            text_content = " ".join(t.text or "" for t in texts2 if t.text).strip()
        if wtype == 'picture' and not text_content:
            text_content = "[Picture watermark]"
        return WatermarkInfo(
            type=wtype,
            text=text_content,
            section_index=section_index,
        )
