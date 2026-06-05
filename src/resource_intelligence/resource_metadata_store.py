from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResourceMetadata:
    resource_id: str
    file_path: str
    file_name: str
    file_hash: str
    resource_type: str
    domain: str
    purpose: str
    confidence: float
    word_count: int
    section_count: int
    evidence_categories: Dict[str, bool] = field(default_factory=dict)
    evidence_count: int = 0
    key_terms: Dict[str, int] = field(default_factory=dict)
    recommended_sections: List[str] = field(default_factory=list)
    algorithms: List[str] = field(default_factory=list)
    datasets: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    ingested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "resource_id": self.resource_id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_hash": self.file_hash,
            "resource_type": self.resource_type,
            "domain": self.domain,
            "purpose": self.purpose,
            "confidence": self.confidence,
            "word_count": self.word_count,
            "section_count": self.section_count,
            "evidence_count": self.evidence_count,
            "evidence_categories": self.evidence_categories,
            "key_terms_count": len(self.key_terms),
            "recommended_sections": self.recommended_sections,
            "algorithms_count": len(self.algorithms),
            "datasets_count": len(self.datasets),
            "technologies_count": len(self.technologies),
            "ingested_at": self.ingested_at,
            "tags": self.tags,
        }


class ResourceMetadataStore:
    def __init__(self):
        self._resources: Dict[str, ResourceMetadata] = {}

    def store(self, file_path: str, analysis_result) -> ResourceMetadata:
        file_hash = self._compute_hash(file_path)
        resource_id = f"res_{file_hash[:12]}"

        metadata = ResourceMetadata(
            resource_id=resource_id,
            file_path=file_path,
            file_name=analysis_result.profile_summary.get("file_name", file_path.split("/")[-1].split("\\")[-1]),
            file_hash=file_hash,
            resource_type=analysis_result.resource_type,
            domain=analysis_result.domain,
            purpose=analysis_result.purpose,
            confidence=analysis_result.confidence,
            word_count=analysis_result.profile_summary.get("word_count", 0),
            section_count=analysis_result.profile_summary.get("section_count", 0),
            evidence_categories=analysis_result.has_evidence_categories,
            evidence_count=analysis_result.evidence_count,
            recommended_sections=analysis_result.recommended_sections,
            tags=self._generate_tags(analysis_result),
        )

        self._resources[resource_id] = metadata
        logger.info(
            f"Stored metadata for {metadata.file_name}: "
            f"id={resource_id}, type={metadata.resource_type}"
        )
        return metadata

    def _compute_hash(self, file_path: str) -> str:
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except (IOError, FileNotFoundError):
            import time
            return hashlib.sha256(f"{file_path}{time.time()}".encode()).hexdigest()

    def _generate_tags(self, result) -> List[str]:
        tags = [result.resource_type, result.domain, result.purpose]
        if result.evidence_count >= 5:
            tags.append("evidence_rich")
        if result.profile_summary.get("section_count", 0) > 0:
            tags.append("structured")
        name_lower = result.file_path.lower()
        if "code" in name_lower or result.resource_type == "source_code":
            tags.append("implementation")
        if "data" in name_lower or result.resource_type in ("xlsx", "csv"):
            tags.append("data_source")
        if "paper" in name_lower:
            tags.append("research_paper")
        if "report" in name_lower:
            tags.append("report")
        return list(set(tags))

    def get(self, resource_id: str) -> Optional[ResourceMetadata]:
        metadata = self._resources.get(resource_id)
        if metadata:
            metadata.last_accessed = datetime.now().isoformat()
        return metadata

    def get_by_path(self, file_path: str) -> Optional[ResourceMetadata]:
        normalized = file_path.replace("\\", "/")
        for metadata in self._resources.values():
            if metadata.file_path.replace("\\", "/") == normalized:
                metadata.last_accessed = datetime.now().isoformat()
                return metadata
        return None

    def list_all(self) -> List[ResourceMetadata]:
        return list(self._resources.values())

    def search_by_type(self, resource_type: str) -> List[ResourceMetadata]:
        return [r for r in self._resources.values() if r.resource_type == resource_type]

    def search_by_domain(self, domain: str) -> List[ResourceMetadata]:
        return [r for r in self._resources.values() if r.domain == domain]

    def search_by_tag(self, tag: str) -> List[ResourceMetadata]:
        return [r for r in self._resources.values() if tag in r.tags]

    def update_tags(self, resource_id: str, tags: List[str]) -> bool:
        metadata = self._resources.get(resource_id)
        if not metadata:
            return False
        metadata.tags = list(set(metadata.tags + tags))
        return True

    def remove(self, resource_id: str) -> bool:
        if resource_id in self._resources:
            del self._resources[resource_id]
            return True
        return False

    def count(self) -> int:
        return len(self._resources)

    def get_summary(self) -> Dict:
        types: Dict[str, int] = {}
        domains: Dict[str, int] = {}
        for r in self._resources.values():
            types[r.resource_type] = types.get(r.resource_type, 0) + 1
            domains[r.domain] = domains.get(r.domain, 0) + 1
        return {
            "total_resources": len(self._resources),
            "by_type": types,
            "by_domain": domains,
            "average_confidence": round(
                sum(r.confidence for r in self._resources.values()) / max(len(self._resources), 1), 2
            ),
            "total_evidence_categories": sum(r.evidence_count for r in self._resources.values()),
        }

    def reset(self):
        self._resources.clear()
