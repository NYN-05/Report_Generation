import os
from typing import List, Dict, Optional
from pathlib import Path
from src.core.logger import get_logger

logger = get_logger(__name__)


class DocumentParser:
    """Parses documents from various formats into plain text."""

    SUPPORTED_FORMATS = {'.txt', '.md', '.pdf', '.csv'}

    def __init__(self):
        self._pdf_available = False
        try:
            import fitz
            self._pdf_available = True
        except ImportError:
            logger.warning("pymupdf not available, PDF parsing disabled")

    def parse(self, filepath: str) -> Optional[str]:
        ext = Path(filepath).suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            logger.warning(f"Unsupported format: {ext}")
            return None
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return None

        try:
            if ext == '.pdf':
                return self._parse_pdf(filepath)
            return self._parse_text(filepath)
        except Exception as e:
            logger.error(f"Failed to parse {filepath}: {e}")
            return None

    def parse_directory(self, dirpath: str) -> List[Dict[str, str]]:
        results = []
        if not os.path.isdir(dirpath):
            logger.error(f"Directory not found: {dirpath}")
            return results
        for fname in sorted(os.listdir(dirpath)):
            fpath = os.path.join(dirpath, fname)
            if os.path.isfile(fpath) and Path(fname).suffix.lower() in self.SUPPORTED_FORMATS:
                text = self.parse(fpath)
                if text:
                    results.append({"filename": fname, "text": text})
                    logger.info(f"Parsed {fname} ({len(text)} chars)")
        return results

    def _parse_text(self, filepath: str) -> str:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    def _parse_pdf(self, filepath: str) -> str:
        if not self._pdf_available:
            return self._parse_pdf_fallback(filepath)
        import fitz
        doc = fitz.open(filepath)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)

    def _parse_pdf_fallback(self, filepath: str) -> str:
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            return "\n\n".join(pages)
        except ImportError:
            logger.error("No PDF parser available (install pymupdf or pdfplumber)")
            return ""
