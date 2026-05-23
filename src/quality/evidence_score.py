from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger

logger = get_logger(__name__)


class EvidenceScore:
    def __init__(self):
        self._source_markers = [
            "according to", "reported by", "based on", "as shown in",
            "as demonstrated", "evidence suggests", "studies indicate",
            "research shows", "as described", "per the",
        ]

    def score(self, text: str, evidence_chunks: Optional[List[Dict]] = None) -> Dict[str, float]:
        if not text:
            return {"evidence_density": 0.0, "source_attribution": 0.0, "overall": 0.0}
        text_lower = text.lower()
        total_sentences = max(text.count(". "), 1)
        attribution_count = sum(text_lower.count(m) for m in self._source_markers)
        attribution_score = min(attribution_count / max(total_sentences * 0.3, 1), 1.0)
        evidence_density = 0.0
        if evidence_chunks:
            chunk_texts = [c.get("text", "").lower() for c in evidence_chunks if c.get("text")]
            if chunk_texts:
                text_words = set(text_lower.split())
                all_chunk_words = set()
                for ct in chunk_texts:
                    all_chunk_words |= set(ct.split())
                if text_words and all_chunk_words:
                    overlap = len(text_words & all_chunk_words)
                    evidence_density = min(overlap / max(len(text_words), 1), 1.0)
        overall = attribution_score * 0.4 + evidence_density * 0.6
        return {
            "evidence_density": round(evidence_density, 3),
            "source_attribution": round(attribution_score, 3),
            "overall": round(overall, 3),
        }

    def score_section_list(self, sections: List[Dict]) -> Dict[str, Dict[str, float]]:
        return {
            s.get("section_type", "unknown"): self.score(
                s.get("text", ""), s.get("evidence_chunks")
            )
            for s in sections
        }
