from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger
from .example_library import ExampleLibrary, ExampleEntry

logger = get_logger(__name__)


class DynamicExampleRetriever:
    def __init__(self, library: ExampleLibrary):
        self._library = library

    def retrieve(self, section_type: str, topic: str,
                  n: int = 2) -> List[ExampleEntry]:
        examples = self._library.get_examples(section_type, n * 3)
        topic_lower = topic.lower()
        topic_words = set(topic_lower.split())
        if not examples:
            return []
        scored = []
        for ex in examples:
            ex_topic_words = set(ex.topic.lower().split())
            overlap = len(topic_words & ex_topic_words)
            topic_sim = overlap / max(len(topic_words | ex_topic_words), 1)
            combined = topic_sim * 0.4 + ex.quality_score * 0.6
            scored.append((combined, ex))
        scored.sort(key=lambda x: -x[0])
        return [ex for _, ex in scored[:n]]

    def retrieve_for_sections(self, section_types: List[str],
                               topic: str,
                               n_per_type: int = 1) -> Dict[str, List[ExampleEntry]]:
        return {
            stype: self.retrieve(stype, topic, n_per_type)
            for stype in section_types
        }

    def format_examples_for_prompt(self, examples: List[ExampleEntry]) -> str:
        if not examples:
            return ""
        parts = ["Here are high-quality examples for reference:"]
        for i, ex in enumerate(examples, 1):
            preview = ex.content[:500]
            parts.append(f"\nExample {i} (quality: {ex.quality_score:.2f}):\n{preview}")
        return "\n".join(parts)
