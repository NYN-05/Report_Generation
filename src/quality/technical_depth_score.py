from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger

logger = get_logger(__name__)


class TechnicalDepthScore:
    def __init__(self):
        self._depth_keywords = {
            "algorithm": 0.15, "architecture": 0.12, "framework": 0.1,
            "methodology": 0.12, "technique": 0.1, "approach": 0.08,
            "mechanism": 0.12, "protocol": 0.12, "strategy": 0.08,
            "implementation": 0.1, "deployment": 0.1, "optimization": 0.12,
            "complexity": 0.12, "parameter": 0.1, "configuration": 0.1,
            "analysis": 0.08, "evaluation": 0.08, "comparison": 0.08,
            "trade-off": 0.15, "bottleneck": 0.12, "scalability": 0.12,
        }
        self._technical_indicators = {
            r'\b\d+\.\d+\b': 0.1,
            r'\b\d+%\b': 0.08,
            r'\b[A-Z][A-Z]+(?:\s+[A-Z]+)*\b': 0.05,
            r'\b(?:equation|formula|function|matrix|vector|schema)\b': 0.12,
        }

    def score(self, text: str) -> float:
        if not text or len(text.split()) < 10:
            return 0.0
        words = text.lower().split()
        keyword_score = 0.0
        for kw, weight in self._depth_keywords.items():
            count = text.lower().count(kw)
            keyword_score += count * weight
        normalized_kw = min(keyword_score / max(len(words) * 0.02, 1), 1.0)
        import re
        indicator_score = 0.0
        for pattern, weight in self._technical_indicators.items():
            matches = re.findall(pattern, text)
            indicator_score += len(matches) * weight
        normalized_ind = min(indicator_score, 1.0)
        domain_terms = len(re.findall(r'\b[A-Z][a-z]{3,}(?:\s+[A-Z][a-z]{3,}){0,2}\b', text))
        term_score = min(domain_terms * 0.05, 0.3)
        total = normalized_kw * 0.4 + normalized_ind * 0.35 + term_score * 0.25
        return round(min(max(total, 0.0), 1.0), 3)

    def score_sections(self, sections_text: Dict[str, str]) -> Dict[str, float]:
        return {name: self.score(text) for name, text in sections_text.items()}
