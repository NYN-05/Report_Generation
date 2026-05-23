from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger
from src.generator.content_blocks import (
    SectionContent, ParagraphBlock, BulletListBlock, BulletItem,
    Citation, SourceRequiredBlock,
)
from .evidence_citation_mapper import EvidenceToCitationMapper, EvidenceCitation

logger = get_logger(__name__)


class SourceBackedParagraphGenerator:
    def __init__(self, citation_mapper: Optional[EvidenceToCitationMapper] = None):
        self._citation_mapper = citation_mapper or EvidenceToCitationMapper()

    def generate_paragraph(self, text: str, evidence_chunks: List[Dict],
                           section_type: str) -> ParagraphBlock:
        citations = self._citation_mapper.map_chunks_to_citations(
            evidence_chunks, section_type
        )
        inline_cites = []
        for cit in citations[:3]:
            inline_cites.append(Citation(source=f"[{cit.citation_index}]"))
        evidence_source = self._find_best_source(text, evidence_chunks)
        block = ParagraphBlock(
            text=text,
            word_count=len(text.split()),
            topic_sentence=text.split(".")[0] if "." in text else text,
            evidence_source=evidence_source,
            citations=inline_cites or None,
        )
        return block

    def generate_source_anchored_paragraphs(
        self,
        raw_text: str,
        evidence_chunks: List[Dict],
        section_type: str,
    ) -> List[ParagraphBlock]:
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        blocks = []
        for para in paragraphs:
            if len(para.split()) < 30:
                continue
            citations = self._assign_source_anchors(para, evidence_chunks)
            inline_cites = [
                Citation(source=f"[{c.citation_index}]")
                for c in citations[:3]
            ]
            evidence_source = self._find_best_source(para, evidence_chunks)
            block = ParagraphBlock(
                text=para,
                word_count=len(para.split()),
                topic_sentence=para.split(".")[0] if "." in para else para,
                evidence_source=evidence_source,
                citations=inline_cites or None,
            )
            blocks.append(block)
        return blocks

    def _assign_source_anchors(self, text: str,
                                chunks: List[Dict]) -> List[EvidenceCitation]:
        from collections import Counter
        text_lower = text.lower()
        word_overlaps = []
        for chunk in chunks:
            chunk_text = chunk.get("text", "").lower()
            chunk_words = set(chunk_text.split())
            text_words = set(text_lower.split())
            overlap = len(chunk_words & text_words)
            if overlap > 5:
                word_overlaps.append((overlap, chunk))
        word_overlaps.sort(key=lambda x: -x[0])
        citations = []
        for _, chunk in word_overlaps[:3]:
            source = chunk.get("metadata", {}).get("source", "")
            if source:
                citations.append(EvidenceCitation(
                    fact_text=text[:200],
                    source=source,
                    section_type="",
                    confidence=0.6,
                ))
        return citations

    def _find_best_source(self, text: str, chunks: List[Dict]) -> str:
        if not chunks:
            return ""
        text_lower = text.lower()
        best_overlap = 0
        best_source = ""
        for chunk in chunks:
            chunk_text = chunk.get("text", "").lower()
            chunk_words = set(chunk_text.split())
            text_words = set(text_lower.split())
            overlap = len(chunk_words & text_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_source = chunk.get("metadata", {}).get("source", "")
        return best_source

    def get_citation_mapper(self) -> EvidenceToCitationMapper:
        return self._citation_mapper
