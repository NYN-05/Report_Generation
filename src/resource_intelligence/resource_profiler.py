from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import re
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResourceProfile:
    file_path: str
    file_name: str
    file_size_bytes: int
    line_count: int
    word_count: int
    has_tables: bool = False
    has_figures: bool = False
    has_code_blocks: bool = False
    has_references: bool = False
    has_equations: bool = False
    has_metrics: bool = False
    has_datasets: bool = False
    has_algorithms: bool = False
    has_architectures: bool = False
    has_methodologies: bool = False
    objectives: List[str] = field(default_factory=list)
    problem_statements: List[str] = field(default_factory=list)
    methodologies: List[str] = field(default_factory=list)
    algorithms: List[str] = field(default_factory=list)
    datasets: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    architectures: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    evaluation_results: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    key_terms: Dict[str, int] = field(default_factory=dict)
    section_headers: List[str] = field(default_factory=list)
    language: str = "unknown"
    encoding: str = "utf-8"

    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size_bytes": self.file_size_bytes,
            "line_count": self.line_count,
            "word_count": self.word_count,
            "has_tables": self.has_tables,
            "has_figures": self.has_figures,
            "has_code_blocks": self.has_code_blocks,
            "has_references": self.has_references,
            "has_equations": self.has_equations,
            "has_metrics": self.has_metrics,
            "has_datasets": self.has_datasets,
            "has_algorithms": self.has_algorithms,
            "has_architectures": self.has_architectures,
            "has_methodologies": self.has_methodologies,
            "objectives": self.objectives[:5],
            "problem_statements": self.problem_statements[:5],
            "methodologies": self.methodologies[:5],
            "algorithms": self.algorithms[:5],
            "datasets": self.datasets[:5],
            "technologies": self.technologies[:5],
            "architectures": self.architectures[:5],
            "metrics": self.metrics[:5],
            "evaluation_results": self.evaluation_results[:5],
            "references_count": len(self.references),
            "key_terms": dict(sorted(self.key_terms.items(), key=lambda x: -x[1])[:20]),
            "section_headers": self.section_headers[:20],
            "language": self.language,
        }


OBJECTIVE_PATTERNS = [
    r"(?:objective|goal|aim|purpose|target)\s*(?:is|of|:)\s*.{10,200}?[.!\n]",
    r"(?:to\s+\w+\s+(?:and\s+\w+\s+)?\w+.*?)[.!\n]",
]

PROBLEM_PATTERNS = [
    r"(?:problem|challenge|issue|limitation|gap)\s*(?:is|of|statement|:)\s*.{20,300}?[.!\n]",
    r"(?:however|despite|although)\s*.{20,200}?[.!\n]",
]

METHODOLOGY_PATTERNS = [
    r"(?:method|approach|technique|framework|pipeline)\s*(?:is|:|\swith)\s*.{20,300}?[.!\n]",
]

ALGORITHM_PATTERNS = [
    r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:algorithm|classifier|regressor|network)\b",
    r"\b(?:Random Forest|SVM|K-Means|KNN|CNN|RNN|LSTM|Transformer|BERT|GPT)\b",
]

DATASET_PATTERNS = [
    r"\b(?:[A-Z][a-zA-Z0-9_-]{2,})\s*(?:dataset|corpus|benchmark|data)\b",
    r"\b(?:dataset|corpus)\s*(?:[A-Z][a-zA-Z0-9_-]{2,})\b",
]

TECHNOLOGY_PATTERNS = [
    r"\b(?:Python|PyTorch|TensorFlow|Keras|scikit-learn|JAX|NumPy|Pandas)\b",
    r"\b(?:Docker|Kubernetes|AWS|Azure|GCP|Git|Linux|CUDA)\b",
]

ARCHITECTURE_PATTERNS = [
    r"\b(?:architecture|system design|pipeline|framework)\s*(?:of|for|using)\s*.{20,200}?[.!\n]",
]

METRIC_PATTERNS = [
    r"\b(?:accuracy|precision|recall|f1[-\s]?score|AUC|ROC|BLEU|ROUGE)\s*(?:of|:|=|reached)\s*\d+\.?\d*\%?",
    r"\d+\.?\d*\s*\%?\s*(?:accuracy|precision|recall|f1)",
]


class ResourceProfiler:
    def __init__(self):
        self._profiles: Dict[str, ResourceProfile] = {}

    def profile(self, file_path: str, content: str) -> ResourceProfile:
        path = Path(file_path)
        file_size = path.stat().st_size if path.exists() else len(content)
        lines = content.split("\n")
        words = content.split()

        profile = ResourceProfile(
            file_path=file_path,
            file_name=path.name,
            file_size_bytes=file_size,
            line_count=len(lines),
            word_count=len(words),
        )

        profile.has_tables = bool(re.search(r"\|.*\|.*\|", content) or "\\begin{tabular}" in content)
        profile.has_figures = bool(re.search(r"!\[.*\]\(.*\)", content) or "\\includegraphics" in content)
        profile.has_code_blocks = bool(re.search(r"```[\s\S]*?```", content) or "\\begin{code}" in content)
        profile.has_references = bool(re.search(r"\[.*\]\(.*\)", content) or "\\bibliography" in content or "references" in content[:1000].lower())
        profile.has_equations = bool("=" in content and re.search(r"\$\$.*?\$\$|\\begin{equation}", content))
        profile.has_metrics = bool(re.search(r"\d+\.?\d*\s*\%", content))
        profile.has_datasets = bool(re.search(r"\b(dataset|corpus|benchmark)\b", content.lower()))
        profile.has_algorithms = bool(
            re.search(r"\b(algorithm|classifier|regression|clustering)\b", content.lower())
        )
        profile.has_architectures = "architecture" in content.lower()
        profile.has_methodologies = "methodology" in content.lower() or "method" in content.lower()

        profile.objectives = self._extract_patterns(content, OBJECTIVE_PATTERNS)
        profile.problem_statements = self._extract_patterns(content, PROBLEM_PATTERNS)
        profile.methodologies = self._extract_patterns(content, METHODOLOGY_PATTERNS)
        profile.algorithms = self._extract_named_entities(content, ALGORITHM_PATTERNS)
        profile.datasets = self._extract_named_entities(content, DATASET_PATTERNS)
        profile.technologies = self._extract_named_entities(content, TECHNOLOGY_PATTERNS)
        profile.architectures = self._extract_patterns(content, ARCHITECTURE_PATTERNS)
        profile.metrics = self._extract_values(content, METRIC_PATTERNS)
        profile.evaluation_results = self._extract_evaluation_results(content)
        profile.references = self._extract_references(content)
        profile.key_terms = self._extract_key_terms(content)
        profile.section_headers = self._extract_section_headers(content)

        self._profiles[file_path] = profile
        logger.info(
            f"Profiled {path.name}: {profile.word_count} words, "
            f"{len(profile.algorithms)} algorithms, {len(profile.datasets)} datasets"
        )
        return profile

    def _extract_patterns(self, text: str, patterns: List[str]) -> List[str]:
        matches = []
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                matches.append(m.group(0).strip()[:200])
        return matches[:10]

    def _extract_named_entities(self, text: str, patterns: List[str]) -> List[str]:
        matches = []
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                matches.append(m.group(0).strip())
        return list(set(matches))[:10]

    def _extract_values(self, text: str, patterns: List[str]) -> List[str]:
        matches = []
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                matches.append(m.group(0).strip()[:150])
        return matches[:10]

    def _extract_evaluation_results(self, text: str) -> List[str]:
        matches = re.findall(
            r"(?:achieved|reached|obtained|yielded|produced)\s+(?:an?\s+)?"
            r"\w+\s+(?:of\s+)?\d+\.?\d*\s*\%?",
            text, re.IGNORECASE
        )
        return [m.strip()[:150] for m in matches[:10]]

    def _extract_references(self, text: str) -> List[str]:
        refs = re.findall(r"\[(\d+)\]\s*.{30,200}?(?=\[|\n|$)", text)
        return [r.strip()[:200] for r in refs[:20]]

    def _extract_key_terms(self, text: str, min_freq: int = 3) -> Dict[str, int]:
        words = re.findall(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b', text)
        freq: Dict[str, int] = {}
        for w in words:
            w_norm = w.strip()
            if len(w_norm) > 3:
                freq[w_norm] = freq.get(w_norm, 0) + 1
        return {k: v for k, v in freq.items() if v >= min_freq}

    def _extract_section_headers(self, text: str) -> List[str]:
        headers = re.findall(r"^#{1,3}\s+(.+)$", text, re.MULTILINE)
        if not headers:
            headers = re.findall(r"^(?:[A-Z][A-Za-z\s]+)\n[=]+$", text, re.MULTILINE)
        if not headers:
            headers = re.findall(r"^(?:[A-Z][A-Za-z\s]+)\n[-]+$", text, re.MULTILINE)
        return [h.strip() for h in headers[:20]]

    def get_profile(self, file_path: str) -> Optional[ResourceProfile]:
        return self._profiles.get(file_path)

    def get_all_profiles(self) -> Dict[str, ResourceProfile]:
        return dict(self._profiles)

    def reset(self):
        self._profiles.clear()
