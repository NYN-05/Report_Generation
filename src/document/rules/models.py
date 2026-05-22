from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class SectionRule:
    """Per-section-type content generation rule."""
    min_paragraphs: int = 5
    min_words_per_paragraph: int = 80
    min_words: int = 600
    structure: List[str] = field(default_factory=list)
    require_data_points: bool = True
    require_examples: bool = True
    require_references: int = 0
    require_subsections: bool = False
    min_subsections: int = 3
    require_figure: bool = False
    require_table: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_paragraphs": self.min_paragraphs,
            "min_words_per_paragraph": self.min_words_per_paragraph,
            "min_words": self.min_words,
            "structure": self.structure,
            "require_data_points": self.require_data_points,
            "require_examples": self.require_examples,
            "require_references": self.require_references,
            "require_subsections": self.require_subsections,
            "min_subsections": self.min_subsections,
            "require_figure": self.require_figure,
            "require_table": self.require_table,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SectionRule:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class GlobalRules:
    """Global rules that apply to every section."""
    min_paragraphs_per_section: int = 5
    min_words_per_paragraph: int = 80
    min_words_per_section: int = 600
    require_data_points: bool = True
    require_examples: bool = True
    use_active_voice: bool = True
    require_transitions: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_paragraphs_per_section": self.min_paragraphs_per_section,
            "min_words_per_paragraph": self.min_words_per_paragraph,
            "min_words_per_section": self.min_words_per_section,
            "require_data_points": self.require_data_points,
            "require_examples": self.require_examples,
            "use_active_voice": self.use_active_voice,
            "require_transitions": self.require_transitions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GlobalRules:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ReportRules:
    """Top-level container for all report writing rules."""
    rules_version: str = "1.0"
    global_: GlobalRules = field(default_factory=GlobalRules)
    section_types: Dict[str, SectionRule] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rules_version": self.rules_version,
            "global": self.global_.to_dict(),
            "section_types": {k: v.to_dict() for k, v in self.section_types.items()},
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReportRules:
        global_data = data.get("global", {})
        sections_data = data.get("section_types", {})
        return cls(
            rules_version=data.get("rules_version", "1.0"),
            global_=GlobalRules.from_dict(global_data),
            section_types={k: SectionRule.from_dict(v) for k, v in sections_data.items()},
            metadata=data.get("metadata", {}),
        )

    def get_rule(self, section_type: str) -> SectionRule:
        base = SectionRule(
            min_paragraphs=self.global_.min_paragraphs_per_section,
            min_words_per_paragraph=self.global_.min_words_per_paragraph,
            min_words=self.global_.min_words_per_section,
            require_data_points=self.global_.require_data_points,
            require_examples=self.global_.require_examples,
        )
        override = self.section_types.get(section_type)
        if override is None:
            override = self.section_types.get("default", None)
        if override is None:
            return base
        merged = SectionRule(
            min_paragraphs=override.min_paragraphs or base.min_paragraphs,
            min_words_per_paragraph=override.min_words_per_paragraph or base.min_words_per_paragraph,
            min_words=override.min_words or base.min_words,
            structure=override.structure or base.structure,
            require_data_points=override.require_data_points if override.require_data_points else base.require_data_points,
            require_examples=override.require_examples if override.require_examples else base.require_examples,
            require_references=override.require_references or base.require_references,
            require_subsections=override.require_subsections or base.require_subsections,
            min_subsections=override.min_subsections or base.min_subsections,
            require_figure=override.require_figure or base.require_figure,
            require_table=override.require_table or base.require_table,
        )
        return merged


@dataclass
class RuleValidationResult:
    """Result of validating content against rules."""
    section_heading: str = ""
    paragraphs: int = 0
    word_count: int = 0
    meets_min_paragraphs: bool = False
    meets_min_words: bool = False
    has_data_points: bool = False
    has_examples: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0
