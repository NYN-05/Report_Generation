from typing import List, Optional
from docx import Document
from docx.oxml.ns import qn

from .models import FootnoteInfo
from src.core.logger import get_logger

logger = get_logger(__name__)


class FootnoteDetector:
    """Detects footnotes and endnotes in a DOCX document."""

    def __init__(self, doc: Document):
        self._doc = doc

    def detect(self) -> List[FootnoteInfo]:
        footnotes = self._detect_from_part("footnotes")
        footnotes.extend(self._detect_from_part("endnotes"))
        return footnotes

    def _detect_from_part(self, part_name: str) -> List[FootnoteInfo]:
        results: List[FootnoteInfo] = []
        try:
            doc_part = self._doc.part
            for rel in doc_part.rels.values():
                if rel.reltype.endswith(f"/{part_name}"):
                    notes_part = rel.target_part
                    blob = notes_part.blob
                    from lxml import etree
                    root = etree.fromstring(blob)
                    nsmap = {
                        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
                    }
                    for note in root.findall('.//w:footnote', nsmap):
                        note_id = note.get(qn('w:id'), default='')
                        if note_id in ('0', '-1'):
                            continue
                        texts = []
                        for t in note.findall('.//w:t', nsmap):
                            if t.text:
                                texts.append(t.text)
                        text = ' '.join(texts)
                        para_count = len(note.findall('.//w:p', nsmap))
                        results.append(FootnoteInfo(
                            index=len(results),
                            footnote_id=note_id,
                            text=text,
                            paragraph_count=para_count,
                        ))
                    break
        except Exception as e:
            logger.debug(f"Could not parse {part_name}: {e}")
        return results
