from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger

logger = get_logger(__name__)


class ChapterSummaryEntry:
    def __init__(self, index: int, heading: str, section_type: str,
                 summary: str, key_facts: Optional[List[str]] = None,
                 word_count: int = 0):
        self.index = index
        self.heading = heading
        self.section_type = section_type
        self.summary = summary
        self.key_facts = key_facts or []
        self.word_count = word_count

    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "heading": self.heading,
            "section_type": self.section_type,
            "summary": self.summary[:300],
            "key_facts": self.key_facts[:5],
            "word_count": self.word_count,
        }


class ChapterSummaryStore:
    def __init__(self, max_summaries: int = 20):
        self._summaries: Dict[str, ChapterSummaryEntry] = OrderedDict()
        self._max_summaries = max_summaries
        self._next_index = 1

    def store(self, heading: str, section_type: str, content: str,
              key_facts: Optional[List[str]] = None):
        summary = self._compress(content)
        entry = ChapterSummaryEntry(
            index=self._next_index,
            heading=heading,
            section_type=section_type,
            summary=summary,
            key_facts=key_facts,
            word_count=len(content.split()),
        )
        self._summaries[section_type] = entry
        self._next_index += 1
        if len(self._summaries) > self._max_summaries:
            oldest = next(iter(self._summaries))
            del self._summaries[oldest]
        logger.debug(f"Stored summary for section '{section_type}' ({len(summary)} chars)")

    def get(self, section_type: str) -> Optional[ChapterSummaryEntry]:
        return self._summaries.get(section_type)

    def get_all_summaries(self) -> List[ChapterSummaryEntry]:
        return list(self._summaries.values())

    def get_summary_texts(self) -> List[str]:
        return [e.summary for e in self._summaries.values()]

    def get_previous_summaries(self, current_type: str,
                                n: int = 3) -> List[str]:
        types = list(self._summaries.keys())
        if current_type in types:
            idx = types.index(current_type)
            prev_types = types[max(0, idx - n):idx]
        else:
            prev_types = types[-n:]
        return [self._summaries[t].summary for t in prev_types]

    def get_chapter_context(self) -> str:
        if not self._summaries:
            return ""
        parts = []
        for entry in self._summaries.values():
            parts.append(f"Chapter {entry.index} — {entry.heading}:\n{entry.summary}")
        return "\n\n".join(parts)

    def _compress(self, text: str, max_chars: int = 500) -> str:
        if len(text) <= max_chars:
            return text
        sentences = text.split(". ")
        result = []
        total = 0
        for sent in sentences:
            if total + len(sent) > max_chars:
                break
            result.append(sent)
            total += len(sent) + 2
        return ". ".join(result) + "."

    def count(self) -> int:
        return len(self._summaries)

    def clear(self):
        self._summaries.clear()
        self._next_index = 1


from collections import OrderedDict
