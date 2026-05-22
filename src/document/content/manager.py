"""
Content Manager Module
======================
Manages document content structure.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ContentSection:
    """A content section."""
    title: str
    content: str
    level: int = 1
    subsections: List["ContentSection"] = field(default_factory=list)


@dataclass
class ContentStructure:
    """Complete content structure."""
    title: str = ""
    subtitle: str = ""
    author: str = ""
    date: str = ""
    toc_entries: List[str] = field(default_factory=list)
    sections: List[ContentSection] = field(default_factory=list)


class ContentManager:
    """Manages content for document generation."""

    def __init__(self):
        self._structure = ContentStructure()

    def set_metadata(
        self,
        title: str,
        subtitle: str = "",
        author: str = "",
        date: str = ""
    ):
        """Set document metadata."""
        self._structure.title = title
        self._structure.subtitle = subtitle
        self._structure.author = author
        self._structure.date = date

    def add_section(self, title: str, content: str, level: int = 1):
        """Add a section to the content."""
        section = ContentSection(
            title=title,
            content=content,
            level=level
        )
        self._structure.sections.append(section)

        if level == 1 and title not in self._structure.toc_entries:
            self._structure.toc_entries.append(title)

    def add_subsection(self, parent_title: str, title: str, content: str):
        """Add a subsection to an existing section."""
        for section in self._structure.sections:
            if section.title == parent_title:
                subsection = ContentSection(
                    title=title,
                    content=content,
                    level=2
                )
                section.subsections.append(subsection)
                return

        logger.warning(f"Parent section not found: {parent_title}")

    def set_toc(self, entries: List[str]):
        """Set table of contents entries."""
        self._structure.toc_entries = entries

    def get_structure(self) -> ContentStructure:
        """Get the content structure."""
        return self._structure

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for document generation."""
        return {
            "title": self._structure.title,
            "subtitle": self._structure.subtitle,
            "author": self._structure.author,
            "date": self._structure.date,
            "toc_entries": self._structure.toc_entries,
            "sections": [
                {
                    "heading": s.title,
                    "content": s.content,
                    "level": s.level,
                    "subsections": [
                        {"heading": sub.title, "content": sub.content}
                        for sub in s.subsections
                    ]
                }
                for s in self._structure.sections
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContentManager":
        """Create content manager from dictionary."""
        manager = cls()

        manager.set_metadata(
            title=data.get("title", ""),
            subtitle=data.get("subtitle", ""),
            author=data.get("author", ""),
            date=data.get("date", "")
        )

        manager.set_toc(data.get("toc_entries", []))

        sections = data.get("sections", [])
        for section in sections:
            manager.add_section(
                title=section.get("heading", ""),
                content=section.get("content", ""),
                level=section.get("level", 1)
            )

        return manager