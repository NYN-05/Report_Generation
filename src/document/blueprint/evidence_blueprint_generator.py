from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from src.core.logger import get_logger
from src.facts.models import Fact, FactType
from src.facts.store import FactStore
from src.evidence.coverage_models import CoverageLevel
from src.evidence.coverage_engine import CoverageEngine

logger = get_logger(__name__)


@dataclass
class BlueprintSection:
    section_type: str
    heading: str
    description: str
    required_fact_types: List[str] = field(default_factory=list)
    fact_count: int = 0
    coverage_level: str = "none"
    is_auto_generated: bool = True
    priority: int = 0
    subsections: List["BlueprintSection"] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "section_type": self.section_type,
            "heading": self.heading,
            "description": self.description[:100],
            "required_fact_types": self.required_fact_types,
            "fact_count": self.fact_count,
            "coverage_level": self.coverage_level,
            "is_auto_generated": self.is_auto_generated,
            "priority": self.priority,
            "subsections": [s.to_dict() for s in self.subsections],
        }


@dataclass
class EvidenceBlueprint:
    title: str
    sections: List[BlueprintSection] = field(default_factory=list)
    total_facts: int = 0
    evidence_richness: float = 0.0
    recommended_structure: str = "standard"

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "sections": [s.to_dict() for s in self.sections],
            "total_facts": self.total_facts,
            "evidence_richness": self.evidence_richness,
            "recommended_structure": self.recommended_structure,
            "section_count": len(self.sections),
        }


EVIDENCE_TO_SECTION_MAP: Dict[str, Dict] = {
    "introduction": {
        "required_types": [FactType.OBJECTIVE, FactType.PROBLEM],
        "description": "Background, problem statement, and objectives based on available evidence",
        "priority": 1,
    },
    "methodology": {
        "required_types": [FactType.METHODOLOGY, FactType.ALGORITHM, FactType.ARCHITECTURE],
        "description": "Technical approach, algorithms, and architectural decisions",
        "priority": 2,
    },
    "implementation": {
        "required_types": [FactType.TECHNOLOGY, FactType.ALGORITHM, FactType.ARCHITECTURE],
        "description": "Implementation details, technologies used, and system components",
        "priority": 3,
    },
    "experimental_setup": {
        "required_types": [FactType.DATASET, FactType.METRIC, FactType.TECHNOLOGY],
        "description": "Experimental configuration, datasets, and evaluation metrics",
        "priority": 4,
    },
    "results": {
        "required_types": [FactType.RESULT, FactType.METRIC],
        "description": "Experimental results and performance evaluation",
        "priority": 5,
    },
    "discussion": {
        "required_types": [FactType.RESULT, FactType.PROBLEM],
        "description": "Analysis of results and comparison with existing approaches",
        "priority": 6,
    },
    "related_work": {
        "required_types": [FactType.CITATION, FactType.TECHNOLOGY],
        "description": "Review of relevant literature and existing solutions",
        "priority": 7,
    },
    "conclusion": {
        "required_types": [FactType.OBJECTIVE, FactType.RESULT],
        "description": "Summary of findings, contributions, and future directions",
        "priority": 8,
    },
}


class EvidenceBlueprintGenerator:
    def __init__(self, fact_store: Optional[FactStore] = None,
                 coverage_engine: Optional[CoverageEngine] = None):
        self._fact_store = fact_store or FactStore()
        self._coverage_engine = coverage_engine or CoverageEngine(fact_store)

    def generate(self, title: str, facts: List[Fact]) -> EvidenceBlueprint:
        fact_type_counts: Dict[FactType, int] = {}
        for fact in facts:
            fact_type_counts[fact.fact_type] = fact_type_counts.get(fact.fact_type, 0) + 1

        sections: List[BlueprintSection] = []
        total_facts = len(facts)

        for section_type, config in EVIDENCE_TO_SECTION_MAP.items():
            required_types = config["required_types"]
            matching_facts = [
                f for f in facts if f.fact_type in required_types
            ]

            if not matching_facts:
                continue

            coverage_level = self._compute_coverage_level(
                matching_facts, required_types, fact_type_counts
            )

            section = BlueprintSection(
                section_type=section_type,
                heading=section_type.replace("_", " ").title(),
                description=config["description"],
                required_fact_types=[ft.value for ft in required_types],
                fact_count=len(matching_facts),
                coverage_level=coverage_level.value,
                is_auto_generated=True,
                priority=config["priority"],
                subsections=self._generate_subsections(section_type, matching_facts),
            )
            sections.append(section)

        sections.sort(key=lambda s: s.priority)

        evidence_types_present = len(fact_type_counts)
        evidence_richness = min(1.0, evidence_types_present / len(EVIDENCE_TO_SECTION_MAP))

        recommended = "standard"
        if evidence_richness < 0.3:
            recommended = "minimal"
        elif evidence_richness > 0.7:
            recommended = "comprehensive"

        if any(s.coverage_level == "high" for s in sections):
            pass

        blueprint = EvidenceBlueprint(
            title=title,
            sections=sections,
            total_facts=total_facts,
            evidence_richness=round(evidence_richness, 2),
            recommended_structure=recommended,
        )

        logger.info(
            f"Evidence blueprint generated: {len(sections)} sections, "
            f"{total_facts} facts, richness={evidence_richness:.2%}, "
            f"structure={recommended}"
        )
        return blueprint

    def _compute_coverage_level(self, matching_facts: List[Fact],
                                  required_types: List[FactType],
                                  type_counts: Dict[FactType, int]) -> CoverageLevel:
        matched_types = set(f.fact_type for f in matching_facts)
        type_coverage = len(matched_types & set(required_types)) / max(len(required_types), 1)

        avg_confidence = sum(f.confidence for f in matching_facts) / max(len(matching_facts), 1)

        score = type_coverage * 0.5 + avg_confidence * 0.5
        return CoverageLevel.from_score(score)

    def _generate_subsections(self, section_type: str,
                               facts: List[Fact]) -> List[BlueprintSection]:
        if section_type == "methodology":
            algo_facts = [f for f in facts if f.fact_type == FactType.ALGORITHM]
            arch_facts = [f for f in facts if f.fact_type == FactType.ARCHITECTURE]
            subs = []
            if algo_facts:
                subs.append(BlueprintSection(
                    section_type="algorithm_details",
                    heading="Algorithm Details",
                    description=f"Details on {len(algo_facts)} algorithms",
                    fact_count=len(algo_facts),
                ))
            if arch_facts:
                subs.append(BlueprintSection(
                    section_type="architecture",
                    heading="System Architecture",
                    description=f"Architecture based on {len(arch_facts)} facts",
                    fact_count=len(arch_facts),
                ))
            return subs
        return []

    def generate_from_fact_store(self, title: str) -> EvidenceBlueprint:
        facts = self._fact_store.get_all_facts()
        return self.generate(title, facts)

    def get_summary(self, blueprint: EvidenceBlueprint) -> Dict:
        return {
            "title": blueprint.title,
            "sections": len(blueprint.sections),
            "facts": blueprint.total_facts,
            "richness": blueprint.evidence_richness,
            "structure": blueprint.recommended_structure,
            "coverage_by_section": {
                s.section_type: s.coverage_level for s in blueprint.sections
            },
        }
