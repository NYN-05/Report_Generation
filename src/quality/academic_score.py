from typing import Dict, List, Optional, Tuple
import re
from collections import Counter
from src.core.logger import get_logger

logger = get_logger(__name__)


class AcademicScore:
    def __init__(self):
        self._formal_patterns = {
            "academic_verbs": [
                "analyze", "demonstrate", "investigate", "examine", "propose",
                "evaluate", "assess", "determine", "validate", "verify",
                "formulate", "implement", "develop", "establish", "identify",
            ],
            "hedging": [
                "suggests", "indicates", "may", "could", "likely",
                "potentially", "possibly", "tends to", "appears to",
            ],
            "weak_words": [
                "very", "really", "quite", "somewhat", "kind of",
                "sort of", "a lot", "nice", "good", "bad",
                "big", "small", "thing", "stuff",
            ],
        }

    def score(self, text: str) -> Dict[str, float]:
        if not text or len(text.split()) < 10:
            return {"formality": 0.5, "hedging_balance": 0.5, "overall": 0.5}
        text_lower = text.lower()
        words = text.split()
        word_count = len(words)
        formal_verb_count = sum(text_lower.count(v) for v in self._formal_patterns["academic_verbs"])
        hedging_count = sum(text_lower.count(h) for h in self._formal_patterns["hedging"])
        weak_count = sum(text_lower.count(w) for w in self._formal_patterns["weak_words"])
        formal_score = min(formal_verb_count / max(word_count * 0.02, 1), 1.0)
        hedged = min(hedging_count / max(formal_verb_count + 1, 1), 1.0)
        hedging_balance = 1.0 - abs(hedged - 0.3) / 0.7
        weak_penalty = min(weak_count * 0.1, 0.3)
        passive_count = len(re.findall(r'\b(is|are|was|were|been|being)\s+\w+ed\b', text, re.IGNORECASE))
        passive_score = min(passive_count / max(word_count * 0.03, 1), 1.0)
        sentence_lens = [len(s.split()) for s in re.split(r'[.!?]+', text) if len(s.split()) > 3]
        avg_len = sum(sentence_lens) / max(len(sentence_lens), 1) if sentence_lens else 15
        length_score = 1.0 - abs(avg_len - 20) / 20.0
        formality = max(0.0, min(1.0, formal_score * 0.3 + passive_score * 0.2 + length_score * 0.3 - weak_penalty))
        overall = formality * 0.5 + hedging_balance * 0.2 + length_score * 0.3
        return {
            "formality": round(formality, 3),
            "hedging_balance": round(hedging_balance, 3),
            "passive_ratio": round(passive_score, 3),
            "avg_sentence_length": round(avg_len, 1),
            "overall": round(overall, 3),
        }

    def score_sections(self, sections: Dict[str, str]) -> Dict[str, Dict[str, float]]:
        return {name: self.score(text) for name, text in sections.items()}
