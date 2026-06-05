from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class FactType(Enum):
    OBJECTIVE = "objective"
    DATASET = "dataset"
    METRIC = "metric"
    ALGORITHM = "algorithm"
    RESULT = "result"
    CITATION = "citation"
    TECHNOLOGY = "technology"
    ARCHITECTURE = "architecture"
    REQUIREMENT = "requirement"
    METHODOLOGY = "methodology"
    PROBLEM = "problem"
    MODULE = "module"
    GENERAL = "general"


@dataclass
class EvidenceSpan:
    text: str
    start_char: int
    end_char: int
    page_number: Optional[int] = None
    section_name: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "text": self.text[:200],
            "start_char": self.start_char,
            "end_char": self.end_char,
            "page_number": self.page_number,
            "section_name": self.section_name,
        }


@dataclass
class SourceReference:
    resource_id: str
    file_path: str
    file_name: str
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None
    span: Optional[EvidenceSpan] = None

    def to_dict(self) -> Dict:
        return {
            "resource_id": self.resource_id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "page_number": self.page_number,
            "chunk_id": self.chunk_id,
            "span": self.span.to_dict() if self.span else None,
        }


@dataclass
class Fact:
    fact_id: str
    fact_type: FactType
    value: str
    normalized_value: str
    confidence: float
    source: SourceReference
    span: Optional[EvidenceSpan] = None
    concepts: List[str] = field(default_factory=list)
    related_fact_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True
    source_tier: int = 1
    source_url: str = ""
    retrieval_timestamp: str = ""
    verification_count: int = 0
    is_verified: bool = True

    def to_dict(self) -> Dict:
        return {
            "fact_id": self.fact_id,
            "fact_type": self.fact_type.value,
            "value": self.value[:200],
            "normalized_value": self.normalized_value[:200],
            "confidence": self.confidence,
            "source": self.source.to_dict(),
            "concepts": self.concepts[:10],
            "related_fact_ids": self.related_fact_ids[:10],
            "created_at": self.created_at,
            "is_active": self.is_active,
            "source_tier": self.source_tier,
            "source_url": self.source_url,
            "verification_count": self.verification_count,
            "is_verified": self.is_verified,
        }

    def deactivate(self):
        self.is_active = False


@dataclass
class ObjectiveFact(Fact):
    objective_type: str = ""

    def __post_init__(self):
        self.fact_type = FactType.OBJECTIVE


@dataclass
class DatasetFact(Fact):
    dataset_name: str = ""
    dataset_size: Optional[str] = None
    dataset_source: Optional[str] = None
    dataset_domain: Optional[str] = None

    def __post_init__(self):
        self.fact_type = FactType.DATASET


@dataclass
class MetricFact(Fact):
    metric_name: str = ""
    metric_value: Optional[float] = None
    metric_unit: str = ""
    is_percentage: bool = False

    def __post_init__(self):
        self.fact_type = FactType.METRIC


@dataclass
class AlgorithmFact(Fact):
    algorithm_name: str = ""
    algorithm_type: str = ""
    implementation_language: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.fact_type = FactType.ALGORITHM


@dataclass
class ResultFact(Fact):
    metric_name: str = ""
    metric_value: Optional[float] = None
    baseline_value: Optional[float] = None
    improvement_pct: Optional[float] = None
    is_significant: bool = True

    def __post_init__(self):
        self.fact_type = FactType.RESULT


@dataclass
class CitationFact(Fact):
    citation_key: str = ""
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    title: str = ""
    venue: str = ""
    doi: Optional[str] = None

    def __post_init__(self):
        self.fact_type = FactType.CITATION


@dataclass
class TechnologyFact(Fact):
    technology_name: str = ""
    version: Optional[str] = None
    category: str = ""

    def __post_init__(self):
        self.fact_type = FactType.TECHNOLOGY


@dataclass
class ArchitectureFact(Fact):
    architecture_name: str = ""
    components: List[str] = field(default_factory=list)
    pattern_type: str = ""

    def __post_init__(self):
        self.fact_type = FactType.ARCHITECTURE


@dataclass
class RequirementFact(Fact):
    requirement_type: str = ""
    priority: str = "medium"
    stakeholders: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.fact_type = FactType.REQUIREMENT
