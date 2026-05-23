"""EvidenceCoverageScore — measures what fraction of available evidence is used per paragraph."""

from typing import Dict, List, Optional
from src.core.logger import get_logger

logger = get_logger(__name__)


class EvidenceCoverageScore:
    MIN_COVERAGE = 0.8

    def score_paragraph(self, paragraph_text: str,
                        evidence_chunks: List[Dict]) -> float:
        if not paragraph_text or not evidence_chunks:
            return 0.0
        text_lower = paragraph_text.lower()
        chunk_texts = [
            c.get("text", "").lower()
            for c in evidence_chunks if c.get("text")
        ]
        if not chunk_texts:
            return 0.0
        used = 0
        for ct in chunk_texts:
            key_phrases = self._extract_phrases(ct)
            if any(phrase in text_lower for phrase in key_phrases):
                used += 1
        return used / len(chunk_texts)

    def score_section(self, section_text: str,
                      evidence_chunks: List[Dict]) -> Dict[str, float]:
        paragraphs = [p.strip() for p in section_text.split("\n\n") if p.strip()]
        if not paragraphs:
            return {"coverage": 0.0, "paragraphs_below_threshold": 0, "total": 0}

        per_para = []
        below = 0
        for p in paragraphs:
            cov = self.score_paragraph(p, evidence_chunks)
            per_para.append(cov)
            if cov < self.MIN_COVERAGE:
                below += 1

        overall = sum(per_para) / len(per_para) if per_para else 0.0
        return {
            "coverage": round(overall, 3),
            "paragraphs_below_threshold": below,
            "total_paragraphs": len(per_para),
            "threshold": self.MIN_COVERAGE,
            "passed": overall >= self.MIN_COVERAGE,
        }

    def _extract_phrases(self, text: str) -> List[str]:
        sentences = [s.strip() for s in text.replace(". ", ".|").split("|") if s.strip()]
        phrases = []
        for sent in sentences:
            words = sent.split()
            if len(words) >= 4:
                phrases.append(" ".join(words[:3]).lower())
            if len(words) >= 6:
                mid = len(words) // 2
                phrases.append(" ".join(words[mid:mid+3]).lower())
        return phrases
