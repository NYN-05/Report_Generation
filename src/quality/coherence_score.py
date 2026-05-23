from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger

logger = get_logger(__name__)


class CoherenceScore:
    def __init__(self):
        self._transition_words = {
            "addition": ["furthermore", "moreover", "additionally", "also", "besides"],
            "contrast": ["however", "nevertheless", "conversely", "although", "whereas", "despite"],
            "cause": ["therefore", "thus", "consequently", "hence", "accordingly", "because"],
            "sequence": ["first", "second", "third", "next", "then", "finally", "subsequently"],
            "example": ["for example", "for instance", "specifically", "particularly", "notably"],
            "conclusion": ["in conclusion", "to summarize", "overall", "in summary", "ultimately"],
        }

    def score(self, text: str) -> Dict[str, float]:
        if not text or len(text.split()) < 20:
            return {"transition_score": 0.0, "cross_reference_score": 0.0, "overall": 0.0}
        text_lower = text.lower()
        sentences = [s.strip() for s in text.replace("! ", ". ").replace("? ", ". ").split(". ")]
        sentences = [s for s in sentences if len(s.split()) > 3]
        if len(sentences) < 2:
            return {"transition_score": 0.0, "cross_reference_score": 0.0, "overall": 0.5}
        transitions_found = 0
        total_transition_groups = 0
        for group, words in self._transition_words.items():
            count = sum(text_lower.count(w) for w in words)
            if count > 0:
                transitions_found += count
                total_transition_groups += 1
        max_needed = max(len(sentences) * 0.3, 2)
        transition_score = min(transitions_found / max_needed, 1.0)
        term_overlap_score = self._compute_term_overlap(sentences)
        cross_reference = self._compute_cross_references(text_lower)
        cross_ref_score = min(cross_reference * 0.1, 0.3)
        overall = transition_score * 0.3 + term_overlap_score * 0.5 + cross_ref_score * 0.2
        return {
            "transition_score": round(transition_score, 3),
            "cross_reference_score": round(term_overlap_score + cross_ref_score, 3),
            "overall": round(overall, 3),
        }

    def _compute_term_overlap(self, sentences: List[str]) -> float:
        if len(sentences) < 2:
            return 1.0
        pairs = 0
        overlapping = 0
        for i in range(len(sentences) - 1):
            current = set(w.lower() for w in sentences[i].split() if len(w) > 4)
            following = set(w.lower() for w in sentences[i + 1].split() if len(w) > 4)
            if current and following:
                pairs += 1
                overlap = len(current & following)
                if overlap >= 1:
                    overlapping += min(overlap / 3.0, 1.0)
        return overlapping / max(pairs, 1)

    def _compute_cross_references(self, text: str) -> int:
        import re
        patterns = [
            r'as discussed in (?:section|chapter)',
            r'as mentioned (?:in|previously|above)',
            r'as described in',
            r'as shown in',
            r'refer(?:s|ence)? to',
            r'in the (?:previous|following|next)',
        ]
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, text))
        return count
