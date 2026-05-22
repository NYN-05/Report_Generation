import re
from typing import Dict, Set, List, Optional
from threading import Lock
from src.core.logger import get_logger

logger = get_logger(__name__)


class AbbreviationTracker:
    """Tracks abbreviations and their definitions across a report."""

    def __init__(self):
        self._abbrevs: Dict[str, str] = {}
        self._reverse: Dict[str, str] = {}
        self._lock = Lock()

    def register(self, abbreviation: str, definition: str):
        with self._lock:
            abbr = abbreviation.strip().upper()
            self._abbrevs[abbr] = definition.strip()
            self._reverse[definition.strip().lower()] = abbr

    def get_definition(self, abbreviation: str) -> Optional[str]:
        return self._abbrevs.get(abbreviation.strip().upper())

    def get_abbreviation(self, definition: str) -> Optional[str]:
        return self._reverse.get(definition.strip().lower())

    def scan_text(self, text: str):
        abbr_def = re.compile(r'([A-Z][A-Z0-9]{1,10})\s*\(([^)]+)\)')
        for match in abbr_def.finditer(text):
            abbr = match.group(1)
            definition = match.group(2)
            if len(abbr) >= 2 and len(definition) > len(abbr):
                self.register(abbr, definition)
                logger.debug(f"Registered abbreviation: {abbr} → {definition}")

        def_abbr = re.compile(r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,5})\s*\(([A-Z][A-Z0-9]{1,10})\)')
        for match in def_abbr.finditer(text):
            definition = match.group(1)
            abbr = match.group(2)
            if len(abbr) >= 2:
                self.register(abbr, definition)
                logger.debug(f"Registered abbreviation: {abbr} → {definition}")

    def check_usage(self, text: str) -> List[str]:
        issues = []
        for abbr, definition in self._abbrevs.items():
            abbr_lower = abbr.lower()
            if abbr_lower not in text.lower():
                continue
            if definition.lower() in text.lower()[:200]:
                continue
            idx = text.lower().index(abbr_lower)
            context_before = text[max(0, idx - 50):idx]
            if definition.lower() not in context_before.lower():
                issues.append(f"Abbreviation '{abbr}' used without definition nearby")
        return issues

    def all_abbreviations(self) -> Dict[str, str]:
        return dict(self._abbrevs)

    def clear(self):
        with self._lock:
            self._abbrevs.clear()
            self._reverse.clear()


class CitationTracker:
    """Tracks citations across the report to ensure consistent referencing."""

    def __init__(self):
        self._citations: Dict[str, str] = {}
        self._next_index: int = 1
        self._lock = Lock()
        self._cite_pattern = re.compile(r'\[(\d+(?:[-,]\s*\d+)*)\]')

    def register(self, key: str, text: str) -> int:
        with self._lock:
            if key not in self._citations:
                idx = self._next_index
                self._citations[key] = text
                self._next_index += 1
                return idx
            return list(self._citations.keys()).index(key) + 1

    def get_text(self, key: str) -> Optional[str]:
        return self._citations.get(key)

    def get_index(self, key: str) -> Optional[int]:
        for i, k in enumerate(self._citations.keys()):
            if k == key:
                return i + 1
        return None

    def validate_references(self, text: str) -> List[str]:
        issues = []
        cites = self._cite_pattern.findall(text)
        for cite_group in cites:
            for part in cite_group.split(","):
                part = part.strip()
                if "-" in part:
                    continue
                try:
                    idx = int(part)
                    if idx > len(self._citations):
                        issues.append(f"Reference [{idx}] exceeds reference list ({len(self._citations)} refs)")
                except ValueError:
                    issues.append(f"Invalid citation format: '{part}'")
        return issues

    def all_citations(self) -> Dict[str, str]:
        return dict(self._citations)

    def count(self) -> int:
        return len(self._citations)

    def clear(self):
        with self._lock:
            self._citations.clear()
            self._next_index = 1


class MemoryHub:
    """Central access point for all memory subsystems."""

    def __init__(self):
        self.abbreviations = AbbreviationTracker()
        self.citations = CitationTracker()
        self._style = None
        self._topic = None
        self._figures = None
        self._context = None
        self._init_extended()

    def _init_extended(self):
        try:
            from .extended import StyleMemory, TopicMemory, FigureMemory, ContextCompressor
            self._style = StyleMemory()
            self._topic = TopicMemory()
            self._figures = FigureMemory()
            self._context = ContextCompressor()
        except ImportError:
            pass

    @property
    def style(self):
        return self._style

    @property
    def topic(self):
        return self._topic

    @property
    def figures(self):
        return self._figures

    @property
    def context(self):
        return self._context

    def process_section(self, content: str, heading: str = "") -> List[str]:
        self.abbreviations.scan_text(content)
        issues = self.citations.validate_references(content)
        if self._style:
            self._style.analyze(content)
        if self._topic and heading:
            self._topic.register_coverage(heading, content)
        if issues:
            logger.warning(f"Citation validation issues: {issues}")
        return issues

    def process_plan(self, sections: List[dict]):
        for sec in sections:
            content = sec.get("content", "")
            heading = sec.get("heading", "")
            self.process_section(content, heading=heading)

    def get_status(self) -> dict:
        status = {
            "abbreviation_count": len(self.abbreviations.all_abbreviations()),
            "citation_count": self.citations.count(),
        }
        if self._style:
            status["style_profile"] = self._style.get_profile()
        if self._topic:
            status["topic_summary"] = self._topic.get_summary()
        if self._figures:
            status["figure_summary"] = self._figures.get_summary()
        return status
