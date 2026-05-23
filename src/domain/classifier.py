from typing import Dict, List, Optional, Set
import re
from src.core.logger import get_logger

logger = get_logger(__name__)


DOMAIN_KEYWORDS = {
    "computer_science": [
        "algorithm", "data structure", "software", "programming", "computation",
        "machine learning", "neural", "network", "database", "system design",
        "cybersecurity", "intrusion", "encryption", "authentication",
    ],
    "engineering": [
        "circuit", "mechanical", "electrical", "thermal", "structural",
        "signal processing", "control system", "embedded", "sensor",
        "manufacturing", "material", "prototype",
    ],
    "biomedical": [
        "clinical", "patient", "diagnosis", "treatment", "disease",
        "genomic", "protein", "cell", "molecular", "drug",
        "imaging", "MRI", "CT scan", "biomarker",
    ],
    "business": [
        "market", "strategy", "revenue", "investment", "portfolio",
        "management", "organization", "stakeholder", "supply chain",
        "consumer", "brand", "marketing",
    ],
    "social_science": [
        "survey", "participant", "demographic", "qualitative", "quantitative",
        "interview", "questionnaire", "statistical", "correlation",
        "hypothesis", "population", "sampling",
    ],
    "natural_science": [
        "climate", "environment", "species", "ecosystem", "geological",
        "chemical", "molecule", "particle", "quantum", "radiation",
        "experiment", "laboratory", "observation",
    ],
}

DEFAULT_DOMAIN = "computer_science"


class DomainClassifier:
    def __init__(self):
        self._domain: str = DEFAULT_DOMAIN
        self._confidence: float = 0.0
        self._subdomains: List[str] = []

    def classify(self, topic: str, knowledge_text: Optional[str] = None) -> str:
        combined = topic.lower()
        if knowledge_text:
            combined += " " + knowledge_text.lower()[:5000]
        scores: Dict[str, float] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                count = combined.count(kw.lower())
                if count > 0:
                    score += count * (1.0 + 0.5 * (len(kw.split()) > 1))
            scores[domain] = score
        if not scores or max(scores.values()) == 0:
            self._domain = DEFAULT_DOMAIN
            self._confidence = 0.3
            return self._domain
        best = max(scores, key=scores.get)
        total = sum(scores.values())
        self._domain = best
        self._confidence = round(scores[best] / max(total, 1), 2)
        threshold = max(scores.values()) * 0.5
        self._subdomains = [d for d, s in scores.items() if s >= threshold and d != best]
        logger.info(f"Classified domain: {best} (confidence={self._confidence}, "
                    f"subdomains={self._subdomains})")
        return self._domain

    def get_domain(self) -> str:
        return self._domain

    def get_confidence(self) -> float:
        return self._confidence

    def get_subdomains(self) -> List[str]:
        return list(self._subdomains)

    def is_technical(self) -> bool:
        return self._domain in ("computer_science", "engineering", "biomedical", "natural_science")
