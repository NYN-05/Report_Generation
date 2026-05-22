import re
from typing import List, Tuple, Optional
from .models import ReferenceInfo, CitationLink, ParagraphInfo


IEEE_PATTERN = re.compile(r'\[(\d+)(?:[,\-]\s*\d+)*\]')
APA_PATTERN = re.compile(r'\(([^()]+?\d{4}[a-z]?)\)')
MLA_PATTERN = re.compile(r'\(([^()]+?\d+)\)')

REF_SECTION_PATTERNS = re.compile(
    r'^(references|bibliography|works\s+cited)', re.IGNORECASE
)

IEEE_REF_PATTERN = re.compile(
    r'^\[(\d+)\]\s+(.+?)(?:\.\s|$)', re.DOTALL
)

APA_REF_PATTERN = re.compile(
    r'^([A-Z][^,]+(?:,\s*[A-Z]\.)+)\s*(?:\((\d{4})\))?\s*\.\s*(.+?)\s*\.\s*(.+?)$',
    re.DOTALL,
)

MLA_REF_PATTERN = re.compile(
    r'^([A-Z][^,]+)\s*\.\s*"([^"]+)"\s*\.\s*(.+?)\s*\.\s*(\d+)\s*\.$',
    re.DOTALL,
)


class ReferenceDetector:
    def __init__(self):
        self._references: List[ReferenceInfo] = []
        self._citation_links: List[CitationLink] = []

    def detect(self, paragraphs: List[ParagraphInfo], raw_paragraphs) -> Tuple[List[ReferenceInfo], List[CitationLink]]:
        self._references = []
        self._citation_links = []
        self._find_reference_section(paragraphs, raw_paragraphs)
        self._find_citation_links(paragraphs, raw_paragraphs)
        return self._references, self._citation_links

    def _find_reference_section(self, paragraphs: List[ParagraphInfo], raw_paragraphs):
        in_refs = False
        ref_idx = 0
        for pi, para in enumerate(paragraphs):
            text = para.text.strip()
            if not text:
                if in_refs:
                    break
                continue
            if not in_refs:
                if REF_SECTION_PATTERNS.match(text):
                    in_refs = True
                continue
            ref = self._parse_reference(text, ref_idx)
            if ref:
                ref.index = ref_idx
                self._references.append(ref)
                ref_idx += 1

    def _parse_reference(self, text: str, idx: int) -> Optional[ReferenceInfo]:
        ieee_m = IEEE_REF_PATTERN.match(text)
        if ieee_m:
            ref = ReferenceInfo(
                raw_text=text,
                format="ieee",
                citation_key=f"[{ieee_m.group(1)}]",
                confidence=0.9,
            )
            body = ieee_m.group(2)
            self._parse_ieee_body(ref, body)
            return ref

        ref = ReferenceInfo(raw_text=text, format="ieee", confidence=0.5)
        year_m = re.search(r'[(\s](\d{4})[)\s]', text)
        if year_m:
            ref.year = year_m.group(1)
        author_m = re.search(r'^([A-Z][^.]+?)[,.\s]', text)
        if author_m:
            ref.authors = [author_m.group(1).strip()]
        ref.index = idx
        return ref

    def _parse_ieee_body(self, ref: ReferenceInfo, body: str):
        year_m = re.search(r'[(\s](\d{4})[)\s]', body)
        if year_m:
            ref.year = year_m.group(1)
        author_m = re.search(r'^([A-Z][^.]+?)[,.\s]', body)
        if author_m:
            ref.authors = [a.strip() for a in author_m.group(1).split(',') if a.strip()]
        title_m = re.search(r'"([^"]+)"', body)
        if title_m:
            ref.title = title_m.group(1)

    def _find_citation_links(self, paragraphs: List[ParagraphInfo], raw_paragraphs):
        for pi, para in enumerate(paragraphs):
            text = para.text
            for m in IEEE_PATTERN.finditer(text):
                ref_nums = re.findall(r'\d+', m.group())
                for rn in ref_nums:
                    ref_idx = int(rn) - 1
                    if 0 <= ref_idx < len(self._references):
                        link = CitationLink(
                            citation_marker=m.group(),
                            reference_index=ref_idx,
                            context_text=text[max(0, m.start()-50):m.end()+50],
                            paragraph_index=pi,
                        )
                        self._citation_links.append(link)

            for m in APA_PATTERN.finditer(text):
                marker = m.group(1)
                for ri, ref in enumerate(self._references):
                    if ref.authors and any(a.split()[-1] in marker for a in ref.authors):
                        if ref.year and ref.year in marker:
                            link = CitationLink(
                                citation_marker=f"({marker})",
                                reference_index=ri,
                                context_text=text[max(0, m.start()-30):m.end()+30],
                                paragraph_index=pi,
                                confidence=0.7,
                            )
                            self._citation_links.append(link)
                            break

    def get_reference_count(self) -> int:
        return len(self._references)
