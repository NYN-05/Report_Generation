"""ContentTypeClassifier — classifies generated content blocks into typed DOCX elements.

Never renders bullet points as inline text.
Always renders using proper DOCX list formatting.
"""

from typing import Dict, List, Optional
import re
from enum import Enum
from src.core.logger import get_logger

logger = get_logger(__name__)


class ContentBlockType(Enum):
    PARAGRAPH = "paragraph"
    BULLET_LIST = "bullet_list"
    COMPARISON_TABLE = "comparison_table"
    FIGURE = "figure"
    EQUATION = "equation"
    HEADING = "heading"


class ContentBlock:
    def __init__(self, block_type: ContentBlockType, text: str = "",
                 items: Optional[List[str]] = None, rows: Optional[List[List[str]]] = None,
                 headers: Optional[List[str]] = None, caption: str = "",
                 level: int = 0):
        self.block_type = block_type
        self.text = text
        self.items = items or []
        self.rows = rows or []
        self.headers = headers or []
        self.caption = caption
        self.level = level

    def to_text(self) -> str:
        if self.block_type == ContentBlockType.BULLET_LIST:
            parts = [f"  • {item}" for item in self.items]
            return "\n".join(parts)
        if self.block_type == ContentBlockType.COMPARISON_TABLE:
            parts = [f"[Table: {self.caption}]"] if self.caption else []
            if self.headers:
                parts.append(" | ".join(self.headers))
            for row in self.rows:
                parts.append(" | ".join(row))
            return "\n".join(parts)
        if self.block_type == ContentBlockType.HEADING:
            return f"{'#' * self.level} {self.text}"
        return self.text


class ContentTypeClassifier:

    BULLET_PATTERNS = [
        re.compile(r"(?:^|\n)\s*[-*•]\s+.+", re.MULTILINE),
        re.compile(r"(?:^|\n)\s*\d+[.)]\s+.+", re.MULTILINE),
    ]

    TABLE_PATTERNS = [
        re.compile(r"\|.+\|.+\|"),
        re.compile(r"^\+[-+]+\+", re.MULTILINE),
    ]

    FIGURE_PATTERNS = [
        re.compile(r"\[Figure:?.+\]", re.IGNORECASE),
        re.compile(r"^Figure\s+\d+[:.]", re.MULTILINE | re.IGNORECASE),
    ]

    EQUATION_PATTERNS = [
        re.compile(r"\[Equation:?.+\]", re.IGNORECASE),
        re.compile(r"^\s*[A-Za-z\s]+\s*=", re.MULTILINE),
    ]

    def classify(self, text: str) -> List[ContentBlock]:
        lines = text.split("\n")
        blocks: List[ContentBlock] = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Detect heading
            if line.startswith("### "):
                blocks.append(ContentBlock(ContentBlockType.HEADING, text=line[4:], level=3))
                i += 1
                continue
            if line.startswith("## "):
                blocks.append(ContentBlock(ContentBlockType.HEADING, text=line[3:], level=2))
                i += 1
                continue
            if line.startswith("# "):
                blocks.append(ContentBlock(ContentBlockType.HEADING, text=line[2:], level=1))
                i += 1
                continue

            # Detect figure
            if any(p.match(line) for p in self.FIGURE_PATTERNS):
                caption = re.sub(r"^\[Figure:\s*|\]$", "", line)
                blocks.append(ContentBlock(ContentBlockType.FIGURE, caption=caption, text=line))
                i += 1
                continue

            # Detect equation
            if any(p.match(line) for p in self.EQUATION_PATTERNS):
                caption = re.sub(r"^\[Equation:\s*|\]$", "", line)
                blocks.append(ContentBlock(ContentBlockType.EQUATION, caption=caption, text=line))
                i += 1
                continue

            # Detect table
            if self._is_table_start(line, lines, i):
                table_lines, end = self._extract_table(lines, i)
                parsed = self._parse_table(table_lines)
                blocks.append(ContentBlock(
                    ContentBlockType.COMPARISON_TABLE,
                    headers=parsed.get("headers", []),
                    rows=parsed.get("rows", []),
                    caption=parsed.get("caption", ""),
                ))
                i = end
                continue

            # Detect bullet list
            if any(p.match(line) for p in self.BULLET_PATTERNS):
                items, end = self._extract_bullet_items(lines, i)
                blocks.append(ContentBlock(ContentBlockType.BULLET_LIST, items=items))
                i = end
                continue

            # Default: paragraph (accumulate consecutive lines)
            para_lines = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    break
                if any(p.match(next_line) for p in self.BULLET_PATTERNS):
                    break
                if next_line.startswith("#"):
                    break
                if "|" in next_line and next_line.count("|") >= 2:
                    break
                para_lines.append(next_line)
                i += 1
            blocks.append(ContentBlock(ContentBlockType.PARAGRAPH, text=" ".join(para_lines)))

        return blocks

    def _is_table_start(self, line: str, lines: List[str], idx: int) -> bool:
        if "|" in line and line.count("|") >= 2:
            return True
        if re.match(r"^\+[-+]+\+", line):
            return True
        if idx + 1 < len(lines):
            nxt = lines[idx + 1].strip()
            if "|" in nxt and nxt.count("|") >= 2:
                return bool(re.match(r"\[Table", line, re.IGNORECASE))
        return False

    def _extract_table(self, lines: List[str], start: int) -> tuple:
        table_lines = []
        i = start
        while i < len(lines):
            line = lines[i].strip()
            if "|" in line and line.count("|") >= 2:
                table_lines.append(line)
            elif re.match(r"^\+[-+]+\+", line):
                table_lines.append(line)
            elif not line:
                i += 1
                break
            else:
                break
            i += 1
        return table_lines, i

    def _parse_table(self, table_lines: List[str]) -> Dict:
        data_lines = [l for l in table_lines if "|" in l and l.count("|") >= 2 and "---" not in l]
        caption = ""
        if data_lines:
            caption_match = re.search(r"\[Table:\s*(.+?)\]", data_lines[0], re.IGNORECASE)
            if caption_match:
                caption = caption_match.group(1)
                data_lines = data_lines[1:]
        headers = []
        rows = []
        if data_lines:
            first = [c.strip() for c in data_lines[0].split("|") if c.strip()]
            if first:
                headers = first
            for dl in data_lines[1:]:
                cells = [c.strip() for c in dl.split("|") if c.strip()]
                if cells:
                    rows.append(cells)
        return {"headers": headers, "rows": rows, "caption": caption}

    def _extract_bullet_items(self, lines: List[str], start: int) -> tuple:
        items = []
        i = start
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                break
            if any(p.match(line) for p in self.BULLET_PATTERNS):
                item = re.sub(r"^[\s]*[-*•]\s+", "", line)
                item = re.sub(r"^\d+[.)]\s+", "", item)
                items.append(item)
                i += 1
            else:
                break
        return items, i
