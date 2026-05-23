"""ChapterUniquenessChecker — enforces distinct content across chapters.

Key requirements:
- Every chapter must have a distinct purpose
- Max 20% similarity between chapters
- Detect repeated explanations, examples, statistics, wording, sentence patterns
- Before generating a paragraph, check all previous chapters for semantic similarity
"""

import re
import hashlib
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChapterSignature:
    heading: str
    section_type: str
    terms: Set[str] = field(default_factory=set)
    ngrams: Set[str] = field(default_factory=set)
    sentence_patterns: List[str] = field(default_factory=list)
    statistics: List[str] = field(default_factory=list)
    key_phrases: Counter = field(default_factory=Counter)
    word_count: int = 0

    def similarity_to(self, other: "ChapterSignature") -> float:
        if not self.terms or not other.terms:
            return 0.0

        intersection = self.terms & other.terms
        union = self.terms | other.terms
        jaccard = len(intersection) / max(len(union), 1)

        ngram_intersection = self.ngrams & other.ngrams
        ngram_union = self.ngrams | other.ngrams
        ngram_jaccard = len(ngram_intersection) / max(len(ngram_union), 1)

        return (jaccard * 0.5 + ngram_jaccard * 0.5)


class ChapterUniquenessChecker:
    """Tracks chapter signatures and enforces cross-chapter uniqueness."""

    MAX_SIMILARITY = 0.20

    def __init__(self):
        self._chapters: List[ChapterSignature] = []

    def register_chapter(self, heading: str, section_type: str, content: str):
        sig = self._build_signature(heading, section_type, content)

        if self._chapters:
            max_sim = max(sig.similarity_to(c) for c in self._chapters)
            violations = self._check_violations(sig)
            logger.info(
                f"Chapter '{heading}': max similarity={max_sim:.3f} "
                f"(limit={self.MAX_SIMILARITY}), violations={len(violations)}"
            )
            if max_sim > self.MAX_SIMILARITY:
                logger.warning(
                    f"Chapter '{heading}' has {max_sim:.1%} similarity "
                    f"to previous chapters (limit: {self.MAX_SIMILARITY:.0%})"
                )

        self._chapters.append(sig)

    def _build_signature(self, heading: str, section_type: str, content: str) -> ChapterSignature:
        words = content.lower().split()
        content_lower = content.lower()

        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "can", "shall", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "through", "during",
            "before", "after", "above", "below", "between", "out", "off", "over",
            "under", "again", "further", "then", "once", "here", "there", "when",
            "where", "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only", "own",
            "same", "so", "than", "too", "very", "just", "because", "but", "and",
            "or", "if", "while", "that", "this", "these", "those", "it", "its",
            "also", "about", "which", "who", "whom", "what",
        }

        terms = set(w for w in words if len(w) > 4 and w not in stop_words)

        ngrams = set()
        for i in range(len(words) - 2):
            ngram = " ".join(words[i:i+3])
            if not all(w in stop_words for w in words[i:i+3]):
                ngrams.add(ngram)

        sentence_patterns = []
        sentences = re.split(r'(?<=[.!?])\s+', content)
        for s in sentences[:10]:
            s_lower = s.lower().strip()
            first_words = " ".join(s_lower.split()[:4])
            if first_words:
                sentence_patterns.append(first_words)

        statistics = re.findall(r'\d+\.?\d*\s*%|\d+\.?\d*\s*(?:accuracy|precision|recall|F1|score|percent)', content_lower)

        key_phrases = Counter()
        for i in range(len(words) - 1):
            bigram = " ".join(words[i:i+2])
            if all(len(w) > 3 for w in words[i:i+2]):
                key_phrases[bigram] += 1

        return ChapterSignature(
            heading=heading,
            section_type=section_type,
            terms=terms,
            ngrams=ngrams,
            sentence_patterns=sentence_patterns,
            statistics=statistics,
            key_phrases=key_phrases,
            word_count=len(words),
        )

    def _check_violations(self, sig: ChapterSignature) -> List[str]:
        if not self._chapters:
            return []
        violations = []
        for prev in self._chapters:
            sim = sig.similarity_to(prev)
            if sim > self.MAX_SIMILARITY:
                violations.append(
                    f"{sim:.1%} similarity to '{prev.heading}' "
                    f"(limit: {self.MAX_SIMILARITY:.0%})"
                )

            repeated_phrases = sig.key_phrases & prev.key_phrases
            for phrase in repeated_phrases:
                if sig.key_phrases[phrase] > 1 and prev.key_phrases[phrase] > 1:
                    violations.append(f"Repeated key phrase: '{phrase}' also in '{prev.heading}'")
        return violations

    def check_content_against_all(self, content: str, section_type: str) -> Tuple[float, List[str]]:
        if not self._chapters:
            return 0.0, []
        sig = self._build_signature(content, section_type, content)
        max_sim = max(sig.similarity_to(c) for c in self._chapters) if self._chapters else 0.0
        violations = self._check_violations(sig)
        return max_sim, violations

    def get_chapter_summaries(self) -> List[str]:
        summaries = []
        for ch in self._chapters:
            top_terms = [t for t, _ in ch.key_phrases.most_common(15)]
            summaries.append(f"[{ch.section_type}] {ch.heading}: {', '.join(top_terms[:10])}")
        return summaries

    def get_all_terms(self) -> Set[str]:
        all_terms: Set[str] = set()
        for ch in self._chapters:
            all_terms.update(ch.terms)
        return all_terms

    def reset(self):
        self._chapters = []
