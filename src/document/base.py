"""
Base Document Module
====================
Document interface and metadata.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class DocumentMetadata:
    """Metadata for a document."""
    title: str = ""
    subtitle: str = ""
    author: str = ""
    date: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    template_path: Optional[str] = None
    styles_preserved: bool = True
    section_count: int = 0
    paragraph_count: int = 0
    table_count: int = 0


@dataclass
class Section:
    """Represents a document section."""
    title: str
    content: str
    level: int = 1
    subsections: List["Section"] = field(default_factory=list)


class BaseDocument(ABC):
    """Abstract base class for documents."""

    def __init__(self, metadata: Optional[DocumentMetadata] = None):
        self.metadata = metadata or DocumentMetadata()

    @abstractmethod
    def save(self, path: str) -> bool:
        """Save document to file."""
        pass

    @abstractmethod
    def load(self, path: str) -> bool:
        """Load document from file."""
        pass

    @abstractmethod
    def add_section(self, section: Section) -> bool:
        """Add a section to the document."""
        pass

    @abstractmethod
    def get_sections(self) -> List[Section]:
        """Get all sections."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metadata": {
                "title": self.metadata.title,
                "subtitle": self.metadata.subtitle,
                "author": self.metadata.author,
                "date": self.metadata.date,
                "template_path": self.metadata.template_path,
                "section_count": self.metadata.section_count,
            }
        }