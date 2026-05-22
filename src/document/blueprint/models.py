from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class BlueprintSection:
    id: str
    heading: str
    level: int = 1
    mandatory: bool = True
    page_break: bool = False
    page_allocation: float = 0.0
    generate_content: bool = True
    content_hint: str = ""
    subsections: List["BlueprintSection"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "heading": self.heading,
            "level": self.level,
            "mandatory": self.mandatory,
            "page_break": self.page_break,
            "page_allocation": self.page_allocation,
            "generate_content": self.generate_content,
            "content_hint": self.content_hint,
            "subsections": [s.to_dict() for s in self.subsections],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlueprintSection":
        subsections_data = data.pop("subsections", [])
        section = cls(**data)
        section.subsections = [cls.from_dict(s) for s in subsections_data]
        return section


@dataclass
class Blueprint:
    id: str
    name: str
    description: str
    sections: List[BlueprintSection] = field(default_factory=list)
    default_chapter_count: int = 4
    default_chapter_level: int = 1
    references_style: str = "ieee"
    requires_toc: bool = True
    requires_lof: bool = False
    requires_lot: bool = False
    requires_appendix: bool = False
    total_pages_estimate: int = 30

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "sections": [s.to_dict() for s in self.sections],
            "default_chapter_count": self.default_chapter_count,
            "default_chapter_level": self.default_chapter_level,
            "references_style": self.references_style,
            "requires_toc": self.requires_toc,
            "requires_lof": self.requires_lof,
            "requires_lot": self.requires_lot,
            "requires_appendix": self.requires_appendix,
            "total_pages_estimate": self.total_pages_estimate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Blueprint":
        sections_data = data.pop("sections", [])
        bp = cls(**data)
        bp.sections = [BlueprintSection.from_dict(s) for s in sections_data]
        return bp


@dataclass
class PlanSection:
    blueprint_section_id: str
    heading: str
    level: int = 1
    content: str = ""
    subsections: List["PlanSection"] = field(default_factory=list)
    allocated_pages: int = 0
    requires_figure: bool = False
    figure_description: str = ""
    requires_table: bool = False
    table_description: str = ""
    table_headers: List[str] = field(default_factory=list)
    table_rows: List[List[str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blueprint_section_id": self.blueprint_section_id,
            "heading": self.heading,
            "level": self.level,
            "content": self.content[:200] if self.content else "",
            "subsections": [s.to_dict() for s in self.subsections],
            "allocated_pages": self.allocated_pages,
            "requires_figure": self.requires_figure,
            "requires_table": self.requires_table,
        }


@dataclass
class ReportPlan:
    blueprint_id: str
    blueprint_name: str
    title: str
    subtitle: str = ""
    author: str = ""
    date: str = ""
    sections: List[PlanSection] = field(default_factory=list)
    total_pages: int = 0
    total_references: int = 0
    total_figures: int = 0
    total_tables: int = 0
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "blueprint_name": self.blueprint_name,
            "title": self.title,
            "subtitle": self.subtitle,
            "author": self.author,
            "date": self.date,
            "section_count": len(self.sections),
            "total_pages": self.total_pages,
            "total_references": self.total_references,
            "total_figures": self.total_figures,
            "total_tables": self.total_tables,
        }
