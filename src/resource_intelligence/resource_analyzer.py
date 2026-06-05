from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AnalysisResult:
    file_path: str
    resource_type: str
    domain: str
    purpose: str
    confidence: float
    profile_summary: Dict[str, Any]
    has_evidence_categories: Dict[str, bool]
    evidence_count: int
    key_findings: List[str] = field(default_factory=list)
    recommended_sections: List[str] = field(default_factory=list)
    cross_references: List[str] = field(default_factory=list)
    quality_indicators: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "resource_type": self.resource_type,
            "domain": self.domain,
            "purpose": self.purpose,
            "confidence": self.confidence,
            "profile_summary": self.profile_summary,
            "has_evidence_categories": self.has_evidence_categories,
            "evidence_count": self.evidence_count,
            "key_findings": self.key_findings[:10],
            "recommended_sections": self.recommended_sections,
            "cross_references": self.cross_references[:10],
            "quality_indicators": self.quality_indicators,
        }


SECTION_EVIDENCE_MAP: Dict[str, List[str]] = {
    "introduction": ["objectives", "problem_statements"],
    "methodology": ["methodologies", "algorithms", "architectures"],
    "implementation": ["technologies", "architectures", "algorithms"],
    "experimental_setup": ["datasets", "metrics", "technologies"],
    "results": ["evaluation_results", "metrics"],
    "discussion": ["evaluation_results", "problem_statements"],
    "related_work": ["references", "technologies"],
    "conclusion": ["objectives", "evaluation_results"],
}


class ResourceAnalyzer:
    def __init__(self, classifier=None, profiler=None):
        from .resource_classifier import ResourceClassifier
        from .resource_profiler import ResourceProfiler
        self._classifier = classifier or ResourceClassifier()
        self._profiler = profiler or ResourceProfiler()
        self._results: Dict[str, AnalysisResult] = {}

    def analyze(self, file_path: str, content: str) -> AnalysisResult:
        classification = self._classifier.classify(file_path, content)
        profile = self._profiler.profile(file_path, content)

        evidence_categories = {
            "has_objectives": len(profile.objectives) > 0,
            "has_problems": len(profile.problem_statements) > 0,
            "has_methodologies": len(profile.methodologies) > 0,
            "has_algorithms": len(profile.algorithms) > 0,
            "has_datasets": len(profile.datasets) > 0,
            "has_technologies": len(profile.technologies) > 0,
            "has_architectures": len(profile.architectures) > 0,
            "has_metrics": len(profile.metrics) > 0,
            "has_evaluation_results": len(profile.evaluation_results) > 0,
            "has_references": len(profile.references) > 0,
        }

        evidence_count = sum(1 for v in evidence_categories.values() if v)

        key_findings = self._generate_findings(classification, profile, evidence_categories)
        recommended_sections = self._recommend_sections(evidence_categories)
        cross_references = self._extract_cross_references(content)
        quality_indicators = self._compute_quality_indicators(profile, evidence_categories)

        result = AnalysisResult(
            file_path=file_path,
            resource_type=classification["resource_type"],
            domain=classification["domain"],
            purpose=classification["purpose"],
            confidence=classification["confidence"],
            profile_summary={
                "word_count": profile.word_count,
                "line_count": profile.line_count,
                "section_count": len(profile.section_headers),
                "key_terms_count": len(profile.key_terms),
            },
            has_evidence_categories=evidence_categories,
            evidence_count=evidence_count,
            key_findings=key_findings,
            recommended_sections=recommended_sections,
            cross_references=cross_references,
            quality_indicators=quality_indicators,
        )

        self._results[file_path] = result
        logger.info(
            f"Analyzed {classification['file_name']}: "
            f"{evidence_count}/10 evidence categories, "
            f"recommends {len(recommended_sections)} sections"
        )
        return result

    def _generate_findings(self, classification: Dict, profile,
                           evidence_categories: Dict[str, bool]) -> List[str]:
        findings = []
        name = classification["file_name"]
        findings.append(f"Resource '{name}' classified as {classification['resource_type']}")
        findings.append(f"Domain: {classification['domain']}, Purpose: {classification['purpose']}")
        if evidence_categories["has_methodologies"]:
            findings.append(f"Contains {len(profile.methodologies)} methodology descriptions")
        if evidence_categories["has_algorithms"]:
            findings.append(f"References {len(profile.algorithms)} algorithms")
        if evidence_categories["has_datasets"]:
            findings.append(f"Mentions {len(profile.datasets)} datasets")
        if evidence_categories["has_technologies"]:
            findings.append(f"Uses {len(profile.technologies)} technologies")
        if evidence_categories["has_metrics"]:
            findings.append(f"Contains {len(profile.metrics)} evaluation metrics")
        if evidence_categories["has_evaluation_results"]:
            findings.append(f"Reports {len(profile.evaluation_results)} evaluation results")
        if len(profile.section_headers) > 0:
            findings.append(f"Has {len(profile.section_headers)} structured sections")
        if len(profile.references) > 0:
            findings.append(f"Contains {len(profile.references)} references")
        return findings

    def _recommend_sections(self, evidence_categories: Dict[str, bool]) -> List[str]:
        sections = []
        for section, required_categories in SECTION_EVIDENCE_MAP.items():
            if any(evidence_categories.get(cat, False) for cat in required_categories):
                sections.append(section)
        if "introduction" not in sections and evidence_categories.get("has_objectives"):
            sections.insert(0, "introduction")
        return sections

    def _extract_cross_references(self, content: str) -> List[str]:
        import re
        refs = re.findall(r"(?:see|as described in|as shown in|refer to)\s+\[?\d*\]?\.?[^.]{10,100}\.", content, re.IGNORECASE)
        return [r.strip()[:200] for r in refs[:10]]

    def _compute_quality_indicators(self, profile,
                                     evidence_categories: Dict[str, bool]) -> Dict[str, float]:
        indicators = {}
        indicators["evidence_richness"] = min(1.0, sum(1 for v in evidence_categories.values() if v) / 10.0)
        indicators["structural_quality"] = min(1.0, len(profile.section_headers) / 10.0)
        indicators["reference_quality"] = min(1.0, len(profile.references) / 20.0)
        indicators["term_specificity"] = min(1.0, sum(1 for t in profile.key_terms.values() if t >= 5) / 10.0)
        indicators["numerical_content"] = 0.8 if profile.has_metrics else 0.2
        return indicators

    def get_result(self, file_path: str) -> Optional[AnalysisResult]:
        return self._results.get(file_path)

    def get_all_results(self) -> Dict[str, AnalysisResult]:
        return dict(self._results)

    def get_combined_evidence_summary(self) -> Dict:
        all_objectives = []
        all_problems = []
        all_methodologies = []
        all_algorithms = []
        all_datasets = []
        all_technologies = []
        all_architectures = []
        all_metrics = []
        all_results_ev = []

        for result in self._results.values():
            profile = self._profiler.get_profile(result.file_path)
            if not profile:
                continue
            all_objectives.extend(profile.objectives)
            all_problems.extend(profile.problem_statements)
            all_methodologies.extend(profile.methodologies)
            all_algorithms.extend(profile.algorithms)
            all_datasets.extend(profile.datasets)
            all_technologies.extend(profile.technologies)
            all_architectures.extend(profile.architectures)
            all_metrics.extend(profile.metrics)
            all_results_ev.extend(profile.evaluation_results)

        return {
            "resource_count": len(self._results),
            "total_objectives": len(all_objectives),
            "total_problems": len(all_problems),
            "total_methodologies": len(all_methodologies),
            "total_algorithms": len(list(set(all_algorithms))),
            "total_datasets": len(list(set(all_datasets))),
            "total_technologies": len(list(set(all_technologies))),
            "total_architectures": len(all_architectures),
            "total_metrics": len(all_metrics),
            "total_evaluation_results": len(all_results_ev),
            "algorithms": list(set(all_algorithms))[:15],
            "datasets": list(set(all_datasets))[:15],
            "technologies": list(set(all_technologies))[:15],
        }

    def reset(self):
        self._results.clear()
        self._classifier.reset()
        self._profiler.reset()
