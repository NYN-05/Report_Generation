import json
import os
import re
from typing import Dict, Set, List, Optional
from threading import Lock
from datetime import datetime
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


_MEMORY_HUB_VERSION = 3


class MemoryHub:
    """Central access point for all memory subsystems with versioned file persistence."""

    def __init__(self, persistence_path: Optional[str] = None):
        self.abbreviations = AbbreviationTracker()
        self.citations = CitationTracker()
        self._style = None
        self._topic = None
        self._figures = None
        self._context = None
        self._persistence_path = persistence_path
        self._lock = Lock()
        self._init_extended()
        if persistence_path and os.path.exists(persistence_path):
            self.load()

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

    def save(self, path: Optional[str] = None) -> str:
        path = path or self._persistence_path
        if not path:
            path = "memory_hub_state.json"
        data = {
            "_version": _MEMORY_HUB_VERSION,
            "_timestamp": datetime.now().isoformat(),
            "abbreviations": self.abbreviations.all_abbreviations(),
            "citations": self.citations.all_citations(),
        }
        if self._style:
            data["style_profile"] = self._style.get_profile()
        if self._figures:
            data["figures"] = self._figures.all_figures()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with self._lock:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        logger.info(f"MemoryHub saved to {path}")
        return path

    def load(self, path: Optional[str] = None) -> bool:
        path = path or self._persistence_path
        if not path or not os.path.exists(path):
            return False
        try:
            with self._lock:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            version = data.pop("_version", 1)
            data = self._migrate(version, data)
            for abbr, defn in data.get("abbreviations", {}).items():
                self.abbreviations.register(abbr, defn)
            for key, text in data.get("citations", {}).items():
                self.citations.register(key, text)
            if self._style and "style_profile" in data:
                sp = data["style_profile"]
                self._style._sentence_lengths = [int(sp.get("avg_sentence_length", 20))]
                self._style._passive_count = int(sp.get("passive_ratio", 0.5) * 100)
                self._style._first_person_count = sp.get("first_person_count", 0)
            if self._figures and "figures" in data:
                for f in data["figures"]:
                    self._figures.register_figure(
                        f.get("description", ""), f.get("section", ""), f.get("caption", ""))
            logger.info(f"MemoryHub loaded (v{version}) {len(data.get('abbreviations', {}))} abbr, "
                        f"{len(data.get('citations', {}))} cites from {path}")
            return True
        except Exception as e:
            logger.warning(f"Failed to load MemoryHub state: {e}")
            return False

    @staticmethod
    def _migrate(version: int, data: dict) -> dict:
        if version < 2:
            if "citations" not in data and "citation_keys" in data:
                data["citations"] = dict(zip(data["citation_keys"], data.get("citation_texts", [])))
            version = 2
        if version < 3:
            if "style_profile" in data and isinstance(data["style_profile"], dict):
                data["style_profile"].setdefault("first_person_count", 0)
            version = 3
        return data
