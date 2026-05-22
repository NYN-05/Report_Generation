"""
Document State Architecture
===========================
Unified DocumentState and Workspace for artifact separation.

Provides a single source of truth for all document-related state,
separating document state from conversation state.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class DocumentState:
    """Single source of truth for all document-related state.

    Fields:
        title: Document title
        abstract: Document abstract
        chapters: List of chapter headings
        sections: List of section definitions
        references: List of reference strings
        citations: Dict of citation key -> citation text
        figures: List of figure descriptions
        tables: List of table descriptions
        equations: List of equation descriptions
        abbreviations: Dict of abbreviation -> definition
        style_profile: Dict of style settings
        topic_profile: Dict of topic focus information
        generation_history: List of generation events
        review_history: List of review results
        validation_results: Dict of validation outcomes
    """

    title: str = ""
    abstract: str = ""
    chapters: List[str] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    citations: Dict[str, str] = field(default_factory=dict)
    figures: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    equations: List[Dict[str, Any]] = field(default_factory=list)
    abbreviations: Dict[str, str] = field(default_factory=dict)
    style_profile: Dict[str, Any] = field(default_factory=dict)
    topic_profile: Dict[str, Any] = field(default_factory=dict)
    generation_history: List[Dict[str, Any]] = field(default_factory=list)
    review_history: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for field_name in (
            "title", "abstract", "chapters", "references", "citations",
            "figures", "tables", "equations", "abbreviations",
            "style_profile", "topic_profile", "validation_results",
        ):
            result[field_name] = getattr(self, field_name)
        result["section_count"] = len(self.sections)
        result["chapter_count"] = len(self.chapters)
        result["reference_count"] = len(self.references)
        result["figure_count"] = len(self.figures)
        result["table_count"] = len(self.tables)
        result["generation_history_count"] = len(self.generation_history)
        result["review_history_count"] = len(self.review_history)
        return result

    def add_generation_event(self, phase: str, details: Dict[str, Any]):
        self.generation_history.append({
            "phase": phase,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        })

    def add_review_result(self, checker: str, passed: bool, issues: int):
        self.review_history.append({
            "checker": checker,
            "passed": passed,
            "issues": issues,
            "timestamp": datetime.now().isoformat(),
        })


@dataclass
class ConversationState:
    """Separate conversation state — never mixed with DocumentState."""
    session_id: str = ""
    user_instructions: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    active_document_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "instruction_count": len(self.user_instructions),
            "correction_count": len(self.corrections),
            "preferences": self.preferences,
            "active_document_id": self.active_document_id,
        }


@dataclass
class ExecutionState:
    """Tracks pipeline execution progress."""
    current_phase: str = ""
    start_time: Optional[str] = None
    progress_pct: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_phase": self.current_phase,
            "start_time": self.start_time,
            "progress_pct": self.progress_pct,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


class Workspace:
    """Container for DocumentState, ConversationState, and ExecutionState.

    Provides the artifact separation boundary required by Method 3:
    conversation state is never mixed with document state.
    """

    def __init__(self):
        self.document = DocumentState()
        self.conversation = ConversationState()
        self.execution = ExecutionState()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document": self.document.to_dict(),
            "conversation": self.conversation.to_dict(),
            "execution": self.execution.to_dict(),
        }

    def reset_document(self):
        """Start fresh document while preserving conversation context."""
        self.document = DocumentState()
        self.execution = ExecutionState()

    def reset_all(self):
        self.document = DocumentState()
        self.conversation = ConversationState()
        self.execution = ExecutionState()
