from enum import Enum
from typing import Dict, List, Optional, Set
from pathlib import Path
import re
from src.core.logger import get_logger

logger = get_logger(__name__)


class ResourceType(Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    CSV = "csv"
    MARKDOWN = "markdown"
    SOURCE_CODE = "source_code"
    GITHUB_REPO = "github_repo"
    IMAGE = "image"
    UNKNOWN = "unknown"


EXTENSION_MAP: Dict[str, ResourceType] = {
    ".pdf": ResourceType.PDF,
    ".docx": ResourceType.DOCX,
    ".pptx": ResourceType.PPTX,
    ".xlsx": ResourceType.XLSX,
    ".xls": ResourceType.XLSX,
    ".csv": ResourceType.CSV,
    ".md": ResourceType.MARKDOWN,
    ".mdx": ResourceType.MARKDOWN,
    ".py": ResourceType.SOURCE_CODE,
    ".js": ResourceType.SOURCE_CODE,
    ".ts": ResourceType.SOURCE_CODE,
    ".java": ResourceType.SOURCE_CODE,
    ".cpp": ResourceType.SOURCE_CODE,
    ".c": ResourceType.SOURCE_CODE,
    ".h": ResourceType.SOURCE_CODE,
    ".hpp": ResourceType.SOURCE_CODE,
    ".rs": ResourceType.SOURCE_CODE,
    ".go": ResourceType.SOURCE_CODE,
    ".rb": ResourceType.SOURCE_CODE,
    ".swift": ResourceType.SOURCE_CODE,
    ".kt": ResourceType.SOURCE_CODE,
    ".scala": ResourceType.SOURCE_CODE,
    ".r": ResourceType.SOURCE_CODE,
    ".sql": ResourceType.SOURCE_CODE,
    ".sh": ResourceType.SOURCE_CODE,
    ".yaml": ResourceType.SOURCE_CODE,
    ".yml": ResourceType.SOURCE_CODE,
    ".json": ResourceType.SOURCE_CODE,
    ".toml": ResourceType.SOURCE_CODE,
    ".png": ResourceType.IMAGE,
    ".jpg": ResourceType.IMAGE,
    ".jpeg": ResourceType.IMAGE,
    ".gif": ResourceType.IMAGE,
    ".svg": ResourceType.IMAGE,
    ".webp": ResourceType.IMAGE,
}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".hpp",
    ".rs", ".go", ".rb", ".swift", ".kt", ".scala", ".r", ".sql",
    ".sh", ".yaml", ".yml", ".json", ".toml",
}


class ResourceDomain(Enum):
    COMPUTER_SCIENCE = "computer_science"
    DATA_SCIENCE = "data_science"
    SOFTWARE_ENGINEERING = "software_engineering"
    MACHINE_LEARNING = "machine_learning"
    SYSTEMS = "systems"
    MATHEMATICS = "mathematics"
    ENGINEERING = "engineering"
    BUSINESS = "business"
    SCIENCE = "science"
    GENERAL = "general"


DOMAIN_SIGNATURES: Dict[ResourceDomain, List[str]] = {
    ResourceDomain.COMPUTER_SCIENCE: [
        "algorithm", "data structure", "computational", "complexity",
        "turing", "automata", "compiler", "operating system",
    ],
    ResourceDomain.DATA_SCIENCE: [
        "data analysis", "statistical", "visualization", "pandas",
        "data pipeline", "etl", "data warehouse", "analytics",
    ],
    ResourceDomain.SOFTWARE_ENGINEERING: [
        "software design", "architecture", "microservice", "api",
        "rest", "deployment", "ci/cd", "testing", "refactoring",
    ],
    ResourceDomain.MACHINE_LEARNING: [
        "neural network", "deep learning", "training", "inference",
        "model", "gradient", "backpropagation", "loss function",
        "accuracy", "precision", "recall", "dataset", "feature",
    ],
    ResourceDomain.SYSTEMS: [
        "distributed system", "consistency", "replication", "latency",
        "throughput", "load balancing", "fault tolerance",
    ],
    ResourceDomain.MATHEMATICS: [
        "theorem", "proof", "equation", "calculus", "linear algebra",
        "probability", "statistics", "optimization",
    ],
    ResourceDomain.ENGINEERING: [
        "circuit", "mechanical", "thermal", "structural", "prototype",
        "signal processing", "control system", "embedded",
    ],
    ResourceDomain.BUSINESS: [
        "market", "revenue", "strategy", "investment", "stakeholder",
        "business model", "roi", "cost analysis",
    ],
    ResourceDomain.SCIENCE: [
        "experiment", "hypothesis", "observation", "laboratory",
        "clinical", "species", "molecular", "quantum",
    ],
}


class ResourceClassifier:
    def __init__(self):
        self._classifications: Dict[str, Dict] = {}

    def classify(self, file_path: str, content_sample: str = "") -> Dict:
        path = Path(file_path)
        ext = path.suffix.lower()
        resource_type = EXTENSION_MAP.get(ext, ResourceType.UNKNOWN)
        domain = self._detect_domain(file_path, content_sample)
        purpose = self._detect_purpose(resource_type, content_sample)
        confidence = self._compute_confidence(resource_type, content_sample, domain)

        result = {
            "file_path": file_path,
            "file_name": path.name,
            "resource_type": resource_type.value,
            "domain": domain.value,
            "purpose": purpose,
            "confidence": confidence,
            "extension": ext,
            "is_code": ext in CODE_EXTENSIONS,
            "is_document": resource_type in (
                ResourceType.PDF, ResourceType.DOCX, ResourceType.MARKDOWN
            ),
            "is_data": resource_type in (ResourceType.XLSX, ResourceType.CSV),
            "is_presentation": resource_type == ResourceType.PPTX,
        }
        self._classifications[file_path] = result
        logger.info(
            f"Classified {path.name}: type={resource_type.value}, "
            f"domain={domain.value}, purpose={purpose}, confidence={confidence:.2f}"
        )
        return result

    def _detect_domain(self, file_path: str, content: str) -> ResourceDomain:
        text = (file_path + " " + content).lower()
        scores: Dict[ResourceDomain, int] = {}
        for domain, signatures in DOMAIN_SIGNATURES.items():
            score = sum(1 for sig in signatures if sig in text)
            if score > 0:
                scores[domain] = score
        if not scores:
            return ResourceDomain.GENERAL
        return max(scores, key=scores.get)

    def _detect_purpose(self, resource_type: ResourceType, content: str) -> str:
        text = content.lower()
        if any(w in text for w in ["abstract", "introduction", "overview"]):
            return "introduction_overview"
        if any(w in text for w in ["method", "algorithm", "implementation"]):
            return "technical_specification"
        if any(w in text for w in ["dataset", "data", "benchmark"]):
            return "data_source"
        if any(w in text for w in ["result", "experiment", "evaluation"]):
            return "results_evaluation"
        if any(w in text for w in ["api", "sdk", "library", "framework"]):
            return "reference_documentation"
        if any(w in text for w in ["tutorial", "guide", "how to"]):
            return "tutorial_guide"
        if any(w in text for w in ["requirement", "specification", "design doc"]):
            return "specification"
        if resource_type == ResourceType.SOURCE_CODE:
            return "source_code_implementation"
        if resource_type == ResourceType.IMAGE:
            return "visual_diagram"
        return "general_reference"

    def _compute_confidence(self, resource_type: ResourceType,
                            content: str, domain: ResourceDomain) -> float:
        confidence = 0.5
        if resource_type != ResourceType.UNKNOWN:
            confidence += 0.2
        if len(content) > 100:
            confidence += 0.1
        if domain != ResourceDomain.GENERAL:
            confidence += 0.1
        if len(content) > 1000:
            confidence += 0.1
        return round(min(confidence, 1.0), 2)

    def get_classification(self, file_path: str) -> Optional[Dict]:
        return self._classifications.get(file_path)

    def get_all_classifications(self) -> Dict[str, Dict]:
        return dict(self._classifications)

    def reset(self):
        self._classifications.clear()
