from typing import Dict, List, Optional, Generator
from src.core.logger import get_logger

logger = get_logger(__name__)


class StreamingWriter:
    def __init__(self, buffer_size: int = 5):
        self._buffer: List[Dict] = []
        self._buffer_size = buffer_size
        self._total_written = 0
        self._callbacks: List[callable] = []

    def on_chunk(self, callback: callable):
        self._callbacks.append(callback)

    def write_block(self, block_type: str, content: str,
                     metadata: Optional[Dict] = None):
        chunk = {
            "type": block_type,
            "content": content,
            "metadata": metadata or {},
            "index": self._total_written,
        }
        self._buffer.append(chunk)
        self._total_written += 1
        for cb in self._callbacks:
            cb(chunk)
        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def write_paragraph(self, text: str, **kwargs):
        self.write_block("paragraph", text, kwargs)

    def write_heading(self, text: str, level: int = 1, **kwargs):
        self.write_block("heading", text, {"level": level, **kwargs})

    def write_bullet(self, title: str, description: str = "", **kwargs):
        self.write_block("bullet", f"{title}: {description}", kwargs)

    def flush(self) -> List[Dict]:
        flushed = list(self._buffer)
        self._buffer.clear()
        return flushed

    def get_stream(self) -> Generator[Dict, None, None]:
        while self._buffer:
            yield self._buffer.pop(0)

    @property
    def total_written(self) -> int:
        return self._total_written

    def reset(self):
        self._buffer.clear()
        self._total_written = 0
        self._callbacks.clear()
