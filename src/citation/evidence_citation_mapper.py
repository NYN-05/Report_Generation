from typing import Dict, List, Optional, Set
from src.core.logger import get_logger

logger = get_logger(__name__)


class EvidenceCitation:
    def __init__(self, fact_text: str, source: str, section_type: str,
                 confidence: float, citation_index: int = 0,
                 direct_quote: Optional[str] = None):
        self.fact_text = fact_text
        self.source = source
        self.section_type = section_type
        self.confidence = confidence
        self.citation_index = citation_index
        self.direct_quote = direct_quote

    def to_dict(self) -> Dict:
        return {
            "fact": self.fact_text[:200],
            "source": self.source,
            "citation_index": self.citation_index,
            "confidence": self.confidence,
        }


class EvidenceToCitationMapper:
    def __init__(self):
        self._citations: List[EvidenceCitation] = []
        self._source_index: Dict[str, int] = {}
        self._next_index = 1

    def map_facts_to_citations(self, facts: List, section_type: str) -> List[EvidenceCitation]:
        citations = []
        for fact in facts:
            source = fact.source_meta.get("source", "") if hasattr(fact, "source_meta") else ""
            if not source and hasattr(fact, "source_text"):
                source = "retrieved_knowledge"
            if source not in self._source_index:
                self._source_index[source] = self._next_index
                self._next_index += 1
            citation = EvidenceCitation(
                fact_text=fact.text if hasattr(fact, "text") else str(fact),
                source=source,
                section_type=section_type,
                confidence=fact.confidence if hasattr(fact, "confidence") else 0.5,
                citation_index=self._source_index[source],
                direct_quote=self._extract_direct_quote(fact),
            )
            citations.append(citation)
        self._citations.extend(citations)
        logger.info(f"Mapped {len(citations)} citations for section '{section_type}'")
        return citations

    def map_chunks_to_citations(self, chunks: List[Dict],
                                 section_type: str) -> List[EvidenceCitation]:
        citations = []
        for chunk in chunks:
            text = chunk.get("text", "")
            meta = chunk.get("metadata", {})
            source = meta.get("source", "retrieved_knowledge")
            heading = meta.get("heading", "")
            if source not in self._source_index:
                self._source_index[source] = self._next_index
                self._next_index += 1
            citation = EvidenceCitation(
                fact_text=text[:300],
                source=source,
                section_type=section_type,
                confidence=self._estimate_chunk_confidence(chunk),
                citation_index=self._source_index[source],
                direct_quote=self._extract_key_sentence(text),
            )
            citations.append(citation)
        self._citations.extend(citations)
        return citations

    def _extract_direct_quote(self, fact) -> Optional[str]:
        text = fact.text if hasattr(fact, "text") else str(fact)
        return self._extract_key_sentence(text)

    def _extract_key_sentence(self, text: str) -> Optional[str]:
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for s in sentences:
            if len(s.split()) >= 8 and len(s.split()) <= 40:
                return s.strip()
        return None

    def _estimate_chunk_confidence(self, chunk: Dict) -> float:
        score = 0.6
        meta = chunk.get("metadata", {})
        if meta.get("source"):
            score += 0.1
        rerank_score = chunk.get("rerank_score", chunk.get("score", 0))
        if isinstance(rerank_score, (int, float)):
            score += min(rerank_score * 0.3, 0.2)
        return round(min(score, 1.0), 2)

    def get_citations_for_section(self, section_type: str) -> List[EvidenceCitation]:
        return [c for c in self._citations if c.section_type == section_type]

    def get_bibliography(self) -> List[Dict]:
        seen = set()
        bib = []
        for c in self._citations:
            if c.source not in seen:
                seen.add(c.source)
                bib.append({
                    "index": c.citation_index,
                    "source": c.source,
                    "texts": [cc.fact_text[:100] for cc in self._citations
                              if cc.source == c.source][:3],
                })
        bib.sort(key=lambda x: x["index"])
        return bib

    def format_inline_citation(self, source: str) -> str:
        idx = self._source_index.get(source)
        if idx:
            return f"[{idx}]"
        return ""

    def reset(self):
        self._citations.clear()
        self._source_index.clear()
        self._next_index = 1
