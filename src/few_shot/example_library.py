from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger

logger = get_logger(__name__)


class ExampleEntry:
    def __init__(self, section_type: str, topic: str, content: str,
                 quality_score: float = 1.0, domain: str = "general",
                 metadata: Optional[Dict] = None):
        self.section_type = section_type
        self.topic = topic
        self.content = content
        self.quality_score = quality_score
        self.domain = domain
        self.metadata = metadata or {}

    def to_dict(self) -> Dict:
        return {
            "section_type": self.section_type,
            "topic_words": self.topic.split()[:10],
            "quality_score": self.quality_score,
            "domain": self.domain,
            "content_preview": self.content[:200],
        }


class ExampleLibrary:
    def __init__(self):
        self._examples: Dict[str, List[ExampleEntry]] = {}
        self._max_per_type = 10

    def add_example(self, section_type: str, topic: str, content: str,
                     quality_score: float = 1.0, domain: str = "general",
                     metadata: Optional[Dict] = None):
        entry = ExampleEntry(
            section_type=section_type,
            topic=topic,
            content=content,
            quality_score=quality_score,
            domain=domain,
            metadata=metadata,
        )
        if section_type not in self._examples:
            self._examples[section_type] = []
        self._examples[section_type].append(entry)
        self._examples[section_type].sort(key=lambda e: -e.quality_score)
        if len(self._examples[section_type]) > self._max_per_type:
            self._examples[section_type] = self._examples[section_type][:self._max_per_type]
        logger.debug(f"Added example for '{section_type}' (topic: {topic[:40]}...)")

    def get_examples(self, section_type: str, n: int = 2) -> List[ExampleEntry]:
        examples = self._examples.get(section_type, [])
        return examples[:n]

    def get_all_types(self) -> List[str]:
        return list(self._examples.keys())

    def get_example_count(self) -> int:
        return sum(len(v) for v in self._examples.values())

    def get_high_quality(self, min_score: float = 0.8) -> Dict[str, List[ExampleEntry]]:
        return {
            stype: [e for e in entries if e.quality_score >= min_score]
            for stype, entries in self._examples.items()
        }

    def clear(self):
        self._examples.clear()
