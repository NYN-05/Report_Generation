"""ContentBlockModel — structured content blocks instead of raw text.

Each block is a dataclass that the DOCX renderer can handle appropriately.
Types:
    ParagraphBlock
    BulletListBlock
    TableBlock
    FigureBlock
    EquationBlock
    CodeBlock
    SourceRequiredBlock
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class BlockType(Enum):
    PARAGRAPH = "paragraph"
    BULLET_LIST = "bullet_list"
    TABLE = "table"
    FIGURE = "figure"
    EQUATION = "equation"
    CODE = "code"
    HEADING = "heading"
    SOURCE_REQUIRED = "source_required"


@dataclass
class Citation:
    source: str
    reference: str = ""
    chunk_id: str = ""


@dataclass
class ParagraphBlock:
    text: str
    citations: List[Citation] = field(default_factory=list)
    topic_sentence: str = ""
    word_count: int = 0
    evidence_source: str = ""

    block_type = BlockType.PARAGRAPH

    def validate(self) -> List[str]:
        errors = []
        if self.word_count < 120:
            errors.append(f"Paragraph too short: {self.word_count} words (min 120)")
        if self.word_count > 250:
            errors.append(f"Paragraph too long: {self.word_count} words (max 250)")
        if not self.topic_sentence:
            errors.append("Missing topic sentence")
        if not self.evidence_source and not self.text.startswith("[Source Material Required]"):
            errors.append("No evidence source")
        return errors


@dataclass
class BulletItem:
    title: str
    description: str
    citations: List[Citation] = field(default_factory=list)
    evidence_source: str = ""


@dataclass
class BulletListBlock:
    title: str
    items: List[BulletItem]
    lead_in: str = ""
    lead_out: str = ""
    citations: List[Citation] = field(default_factory=list)

    block_type = BlockType.BULLET_LIST


@dataclass
class TableRow:
    cells: List[str]


@dataclass
class TableBlock:
    caption: str
    headers: List[str]
    rows: List[TableRow]
    citations: List[Citation] = field(default_factory=list)

    block_type = BlockType.TABLE


@dataclass
class FigureBlock:
    caption: str
    description: str
    placeholder_id: str = ""
    citations: List[Citation] = field(default_factory=list)

    block_type = BlockType.FIGURE


@dataclass
class EquationBlock:
    latex: str
    description: str = ""
    label: str = ""

    block_type = BlockType.EQUATION


@dataclass
class CodeBlock:
    code: str
    language: str = ""
    caption: str = ""

    block_type = BlockType.CODE


@dataclass
class HeadingBlock:
    text: str
    level: int = 1

    block_type = BlockType.HEADING


@dataclass
class SourceRequiredBlock:
    query: str
    context: str = ""
    message: str = "[Source Material Required]"

    block_type = BlockType.SOURCE_REQUIRED


ContentBlock = (
    ParagraphBlock
    | BulletListBlock
    | TableBlock
    | FigureBlock
    | EquationBlock
    | CodeBlock
    | HeadingBlock
    | SourceRequiredBlock
)


@dataclass
class SectionContent:
    heading: str
    blocks: List[ContentBlock] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    evidence_sources: List[str] = field(default_factory=list)
    total_words: int = 0
    depth_score: float = 0.0

    def add_block(self, block: ContentBlock):
        self.blocks.append(block)
        if isinstance(block, ParagraphBlock):
            self.total_words += block.word_count
            if block.evidence_source:
                self.evidence_sources.append(block.evidence_source)
        elif isinstance(block, BulletListBlock):
            for item in block.items:
                if item.evidence_source:
                    self.evidence_sources.append(item.evidence_source)
        elif isinstance(block, SourceRequiredBlock):
            if block.message:
                self.total_words += len(block.message.split())

    def to_text(self) -> str:
        parts = []
        for block in self.blocks:
            if isinstance(block, HeadingBlock):
                prefix = "#" * block.level
                parts.append(f"{prefix} {block.text}")
            elif isinstance(block, ParagraphBlock):
                parts.append(block.text)
            elif isinstance(block, BulletListBlock):
                if block.lead_in:
                    parts.append(block.lead_in)
                for item in block.items:
                    parts.append(f"- {item.title}")
                    parts.append(f"  {item.description}")
                if block.lead_out:
                    parts.append(block.lead_out)
            elif isinstance(block, SourceRequiredBlock):
                parts.append(block.message)
            elif isinstance(block, TableBlock):
                parts.append(f"[Table: {block.caption}]")
            elif isinstance(block, FigureBlock):
                parts.append(f"[Figure: {block.caption}]")
        return "\n\n".join(parts)

    def has_evidence(self) -> bool:
        return len(self.evidence_sources) > 0 or any(
            isinstance(b, SourceRequiredBlock) for b in self.blocks
        )
