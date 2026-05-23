from typing import Dict, List, Optional, Tuple
import re
from src.core.logger import get_logger

logger = get_logger(__name__)


class SourceValidation:
    def __init__(self, source: str, is_valid: bool, score: float,
                 issues: Optional[List[str]] = None):
        self.source = source
        self.is_valid = is_valid
        self.score = score
        self.issues = issues or []

    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "is_valid": self.is_valid,
            "score": self.score,
            "issues": self.issues,
        }


class SourceValidator:
    def __init__(self):
        self._validations: Dict[str, SourceValidation] = {}

    def validate_chunk(self, chunk: Dict) -> SourceValidation:
        text = chunk.get("text", "")
        meta = chunk.get("metadata", {})
        source = meta.get("source", "unknown")
        if source in self._validations:
            return self._validations[source]
        issues = []
        score = 1.0
        if not text or len(text.strip()) < 20:
            issues.append("Content too short (<20 chars)")
            score -= 0.3
        word_count = len(text.split())
        if word_count < 10:
            issues.append("Too few words for meaningful evidence")
            score -= 0.2
        gibberish_score = self._detect_gibberish(text)
        if gibberish_score > 0.3:
            issues.append(f"Possible low-quality content (gibberish score: {gibberish_score:.2f})")
            score -= gibberish_score * 0.5
        if not meta.get("source"):
            issues.append("Missing source attribution")
            score -= 0.1
        is_valid = score >= 0.5
        validation = SourceValidation(
            source=source,
            is_valid=is_valid,
            score=round(max(score, 0.0), 2),
            issues=issues,
        )
        self._validations[source] = validation
        return validation

    def validate_chunks(self, chunks: List[Dict]) -> List[SourceValidation]:
        results = []
        for chunk in chunks:
            val = self.validate_chunk(chunk)
            results.append(val)
        valid_count = sum(1 for r in results if r.is_valid)
        logger.info(
            f"Validated {len(results)} sources: {valid_count} valid, "
            f"{len(results) - valid_count} with issues"
        )
        return results

    def filter_valid(self, chunks: List[Dict]) -> List[Dict]:
        validated = self.validate_chunks(chunks)
        valid_sources = set()
        for val, chunk in zip(validated, chunks):
            if val.is_valid:
                meta = chunk.get("metadata", {})
                valid_sources.add(meta.get("source", ""))
        filtered = []
        for val, chunk in zip(validated, chunks):
            if val.is_valid:
                filtered.append(chunk)
        rejected = len(chunks) - len(filtered)
        if rejected:
            logger.info(f"Filtered out {rejected} low-quality chunks")
        return filtered

    def _detect_gibberish(self, text: str) -> float:
        if not text.strip():
            return 1.0
        words = text.split()
        if len(words) < 5:
            return 0.0
        repeated = len([w for w in words if words.count(w) > 3])
        repeat_ratio = repeated / len(words) if words else 0
        avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
        length_score = 0.0
        if avg_word_len < 2.5:
            length_score = 0.3
        elif avg_word_len > 15:
            length_score = 0.2
        has_punctuation = sum(1 for c in text if c in ".!?") / max(len(text) / 100, 1)
        punct_score = max(0.0, 1.0 - has_punctuation / 5.0) if has_punctuation < 0.5 else 0.0
        return round(repeat_ratio * 0.4 + length_score * 0.3 + punct_score * 0.3, 2)

    def reset(self):
        self._validations.clear()
