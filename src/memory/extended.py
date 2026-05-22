"""
Extended Memory Types
=====================
Style, Topic, Figure memory systems + ContextCompressor.

Completing the memory architecture from 2 types (Abbreviation, Citation)
to 5 types (Abbreviation, Citation, Style, Topic, Figure).
"""

import re
from typing import Dict, List, Set, Optional, Tuple
from collections import Counter
from src.core.logger import get_logger

logger = get_logger(__name__)


class StyleMemory:
    """Tracks writing style for consistency across sections.

    Maintains:
    - Sentence length distribution
    - Academic tone markers
    - Voice consistency (active vs passive)
    - Terminology usage patterns
    - Paragraph structure patterns
    """

    def __init__(self):
        self._sentence_lengths: List[int] = []
        self._tone_markers: Dict[str, int] = Counter()
        self._passive_count = 0
        self._active_count = 0
        self._terminology: Dict[str, int] = Counter()
        self._paragraph_lengths: List[int] = []
        self._first_person_count = 0

    def analyze(self, text: str):
        """Analyze text and update style profile."""
        sentences = re.split(r'[.!?]+', text)
        for s in sentences:
            s = s.strip()
            if len(s) > 5:
                self._sentence_lengths.append(len(s.split()))

        passive = len(re.findall(r'\b(is|are|was|were|been|being)\s+\w+ed\b', text, re.IGNORECASE))
        self._passive_count += passive

        active_verbs = len(re.findall(r'\b(analyzes|develops|implements|proposes|evaluates)\b', text, re.IGNORECASE))
        self._active_count += active_verbs

        first_person = len(re.findall(r'\b(I|we|my|our)\b', text))
        self._first_person_count += first_person

        words = re.findall(r'\b[A-Z][a-z]{3,}\b', text)
        self._terminology.update(w for w in words if len(w) > 4)

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        self._paragraph_lengths.extend(len(p.split()) for p in paragraphs)

    @property
    def avg_sentence_length(self) -> float:
        if not self._sentence_lengths:
            return 0.0
        return sum(self._sentence_lengths) / len(self._sentence_lengths)

    @property
    def passive_ratio(self) -> float:
        total = self._passive_count + self._active_count
        if total == 0:
            return 0.5
        return self._passive_count / total

    @property
    def common_terms(self) -> List[Tuple[str, int]]:
        return self._terminology.most_common(20)

    def get_profile(self) -> Dict:
        return {
            "avg_sentence_length": round(self.avg_sentence_length, 1),
            "passive_ratio": round(self.passive_ratio, 2),
            "first_person_count": self._first_person_count,
            "unique_terms": len(self._terminology),
            "common_terms": [t for t, _ in self._terminology.most_common(10)],
            "avg_paragraph_length": round(
                sum(self._paragraph_lengths) / max(len(self._paragraph_lengths), 1), 1
            ),
        }

    def clear(self):
        self._sentence_lengths.clear()
        self._tone_markers.clear()
        self._passive_count = 0
        self._active_count = 0
        self._terminology.clear()
        self._paragraph_lengths.clear()
        self._first_person_count = 0


class TopicMemory:
    """Preserves report focus and prevents topic drift across sections.

    Maintains:
    - Report objective
    - Per-chapter objectives
    - Key themes and concepts
    - Cross-section consistency markers
    """

    def __init__(self):
        self._report_objective: str = ""
        self._chapter_objectives: Dict[str, str] = {}
        self._key_themes: Set[str] = set()
        self._covered_topics: Set[str] = set()
        self._recent_focus: List[str] = []

    def set_report_objective(self, objective: str):
        self._report_objective = objective

    def set_chapter_objective(self, chapter: str, objective: str):
        self._chapter_objectives[chapter] = objective

    def register_theme(self, theme: str):
        self._key_themes.add(theme)

    def register_coverage(self, section_heading: str, content: str):
        words = set(w.lower() for w in content.split() if len(w) > 4)
        self._covered_topics.update(words)
        self._recent_focus.append(section_heading)
        if len(self._recent_focus) > 20:
            self._recent_focus = self._recent_focus[-20:]

    def is_already_covered(self, text: str) -> List[str]:
        words = set(w.lower() for w in text.split() if len(w) > 5)
        overlap = words & self._covered_topics
        if len(overlap) > max(len(words) * 0.4, 5):
            return list(overlap)
        return []

    def get_summary(self) -> str:
        parts = []
        if self._report_objective:
            parts.append(f"Objective: {self._report_objective}")
        if self._key_themes:
            parts.append(f"Themes: {', '.join(sorted(self._key_themes)[:5])}")
        if self._recent_focus:
            parts.append(f"Recent: {' → '.join(self._recent_focus[-3:])}")
        return " | ".join(parts)

    def clear(self):
        self._report_objective = ""
        self._chapter_objectives.clear()
        self._key_themes.clear()
        self._covered_topics.clear()
        self._recent_focus.clear()


class FigureMemory:
    """Tracks figures, captions, and cross-references to prevent duplicates.

    Maintains:
    - Figure list with descriptions
    - Caption text
    - Figure-to-section mapping
    - Cross-reference tracking
    """

    def __init__(self):
        self._figures: List[Dict] = []
        self._used_captions: Set[str] = set()
        self._figure_count = 0

    def register_figure(self, description: str, section: str = "",
                        caption: str = "") -> int:
        self._figure_count += 1
        entry = {
            "figure_number": self._figure_count,
            "description": description,
            "section": section,
            "caption": caption or f"Fig. {self._figure_count}. {description}",
        }
        self._figures.append(entry)
        self._used_captions.add(caption or entry["caption"])
        logger.debug(f"Registered figure {self._figure_count}: {description}")
        return self._figure_count

    def is_duplicate(self, description: str) -> bool:
        desc_lower = description.lower()
        return any(desc_lower == f["description"].lower() for f in self._figures)

    def find_similar(self, description: str, threshold: float = 0.7) -> bool:
        desc_lower = description.lower()
        desc_words = set(desc_lower.split())
        for f in self._figures:
            f_words = set(f["description"].lower().split())
            overlap = len(desc_words & f_words)
            if overlap / max(len(desc_words | f_words), 1) > threshold:
                return True
        return False

    def all_figures(self) -> List[Dict]:
        return list(self._figures)

    def count(self) -> int:
        return self._figure_count

    def get_summary(self) -> str:
        if not self._figures:
            return "No figures registered"
        sections = Counter(f.get("section", "") for f in self._figures)
        return f"{self._figure_count} figures across {len(sections)} sections"

    def clear(self):
        self._figures.clear()
        self._used_captions.clear()
        self._figure_count = 0


class ContextCompressor:
    """Generates chapter summaries for context injection.

    Reduces token usage by compressing previous chapters
    into concise summaries rather than injecting full text.
    """

    def __init__(self, max_summary_length: int = 500):
        self._chapter_summaries: Dict[str, str] = {}
        self._max_length = max_summary_length

    def summarize_chapter(self, chapter_heading: str, content: str,
                          key_points: Optional[List[str]] = None):
        summary = self._compress_content(content, key_points)
        self._chapter_summaries[chapter_heading] = summary
        logger.debug(f"Compressed '{chapter_heading}' to {len(summary)} chars")

    def get_summary(self, chapter_heading: str) -> str:
        return self._chapter_summaries.get(chapter_heading, "")

    def get_all_summaries(self) -> Dict[str, str]:
        return dict(self._chapter_summaries)

    def get_context_for(self, chapter_heading: str) -> str:
        parts = []
        for ch, summary in self._chapter_summaries.items():
            if ch == chapter_heading:
                break
            parts.append(f"[{ch}]: {summary[:self._max_length]}")

        if not parts:
            return ""
        return "\n\n".join(parts)

    def _compress_content(self, content: str,
                          key_points: Optional[List[str]] = None) -> str:
        if key_points:
            return "; ".join(key_points)

        sentences = re.split(r'(?<=[.!?])\s+', content.strip())
        if len(sentences) <= 3:
            return content[:self._max_length]

        important = [s for i, s in enumerate(sentences)
                     if i < 2 or any(kw in s.lower()
                                     for kw in ["therefore", "conclude", "find",
                                                "show", "demonstrate", "key",
                                                "important", "contribution"])]
        result = " ".join(important[:5])
        return result[:self._max_length]

    def clear(self):
        self._chapter_summaries.clear()
