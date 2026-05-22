from typing import List
from docx import Document

from .models import HeaderFooterInfo
from src.core.logger import get_logger

logger = get_logger(__name__)


class HeaderFooterDetector:
    """Detects headers and footers in each document section."""

    def __init__(self, doc: Document):
        self._doc = doc

    def detect(self) -> List[HeaderFooterInfo]:
        results: List[HeaderFooterInfo] = []
        for si, section in enumerate(self._doc.sections):
            for hf_type, hf_obj in [
                ("header", section.header),
                ("footer", section.footer),
                ("first_page_header", section.first_page_header if hasattr(section, 'first_page_header') else None),
                ("first_page_footer", section.first_page_footer if hasattr(section, 'first_page_footer') else None),
                ("even_page_header", section.even_page_header if hasattr(section, 'even_page_header') else None),
                ("even_page_footer", section.even_page_footer if hasattr(section, 'even_page_footer') else None),
            ]:
                if hf_obj is None:
                    continue
                try:
                    para_count = len(hf_obj.paragraphs)
                    texts = [p.text for p in hf_obj.paragraphs if p.text.strip()]
                    full_text = " | ".join(texts)
                    results.append(HeaderFooterInfo(
                        section_index=si,
                        type=hf_type,
                        text=full_text,
                        paragraph_count=para_count,
                    ))
                except Exception as e:
                    logger.debug(f"Could not read section {si} {hf_type}: {e}")
        return results
