import re
from typing import List, Dict
from src.core.logger import get_logger

logger = get_logger(__name__)


class SemanticChunker:
    """Splits text into semantically meaningful chunks."""

    SECTION_PATTERN = re.compile(
        r'(^|\n)(#{1,3}\s+|(?:[A-Z][a-z]+\s*){1,4}\n[-=]+\n)',
        re.MULTILINE,
    )

    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, source: str = "") -> List[Dict[str, str]]:
        sections = self._split_by_headings(text)
        if not sections:
            sections = [("text", text)]

        chunks = []
        for heading, body in sections:
            sub_chunks = self._split_large_chunk(body, heading)
            chunks.extend(sub_chunks)

        for i, ch in enumerate(chunks):
            ch["chunk_index"] = i
            ch["source"] = source

        logger.info(f"Split into {len(chunks)} chunks from {source}")
        return chunks

    def _split_by_headings(self, text: str) -> List:
        lines = text.split("\n")
        sections = []
        current_heading = "preamble"
        current_lines = []

        for line in lines:
            heading_match = re.match(r'^(#{1,3})\s+(.+)', line)
            if heading_match:
                if current_lines:
                    sections.append((current_heading, "\n".join(current_lines)))
                current_heading = heading_match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_heading, "\n".join(current_lines)))

        return sections

    def _split_large_chunk(self, text: str, heading: str) -> List[Dict]:
        words = text.split()
        if len(words) * 5 <= self.chunk_size:
            return [{"heading": heading, "text": text, "word_count": len(words)}]

        chunks = []
        para_breaks = [m.start() for m in re.finditer(r'\n\s*\n', text)]
        if not para_breaks:
            para_breaks = self._find_break_points(text)

        if not para_breaks:
            chunks.append({"heading": heading, "text": text, "word_count": len(words)})
            return chunks

        start = 0
        sub_idx = 1
        for bp in para_breaks:
            if bp - start > self.chunk_size and start < bp:
                segment = text[start:bp].strip()
                if segment:
                    sub_heading = f"{heading} (cont. {sub_idx})" if sub_idx > 1 else heading
                    chunks.append({"heading": sub_heading, "text": segment, "word_count": len(segment.split())})
                    sub_idx += 1
                start = bp

        remaining = text[start:].strip()
        if remaining:
            chunks.append({"heading": heading if sub_idx == 1 else f"{heading} (cont. {sub_idx})",
                          "text": remaining, "word_count": len(remaining.split())})
        return chunks

    def _find_break_points(self, text: str) -> List[int]:
        best = []
        target = self.chunk_size
        pos = 0
        while pos < len(text):
            pos += target
            if pos >= len(text):
                break
            nearest = text.rfind('. ', pos - 100, pos + 100)
            if nearest > 0:
                best.append(nearest + 1)
            else:
                best.append(pos)
        return best
