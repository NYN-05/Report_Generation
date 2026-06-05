from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from src.core.logger import get_logger
from src.facts.models import Fact, FactType
from src.facts.store import FactStore

if TYPE_CHECKING:
    from src.evidence.coverage_models import SectionCoverage, CoverageLevel, GenerationMode
    from src.evidence.coverage_engine import CoverageEngine
    from src.evidence.coverage_validator import CoverageValidator

logger = get_logger(__name__)


@dataclass
class GenerationConstraint:
    section_type: str
    generation_mode: str  # "normal", "cautious", "insufficient_evidence", "not_possible"
    allowed_fact_ids: List[str] = field(default_factory=list)
    restricted_claims: List[str] = field(default_factory=list)
    must_include_facts: List[str] = field(default_factory=list)
    min_confidence_threshold: float = 0.5
    max_hallucination_risk: float = 0.3

    def to_dict(self) -> Dict:
        return {
            "section_type": self.section_type,
            "mode": self.generation_mode,
            "allowed_fact_count": len(self.allowed_fact_ids),
            "must_include_count": len(self.must_include_facts),
            "min_confidence": self.min_confidence_threshold,
        }


class EvidenceConstrainedGenerator:
    def __init__(self, fact_store: FactStore, coverage_engine=None):
        self._fact_store = fact_store
        self._coverage_engine = coverage_engine
        self._coverage_validator = None
        self._constraints: Dict[str, GenerationConstraint] = {}

    @property
    def _validator(self):
        if self._coverage_validator is None:
            from src.evidence.coverage_validator import CoverageValidator
            self._coverage_validator = CoverageValidator()
        return self._coverage_validator

    def build_constraints(
        self,
        section_types: List[str],
        facts_by_section: Dict[str, List[Fact]],
        paragraphs_by_section: Optional[Dict[str, List[Dict]]] = None,
    ) -> Dict[str, GenerationConstraint]:
        constraints = {}
        for section_type in section_types:
            facts = facts_by_section.get(section_type, [])
            coverage = self._compute_section_coverage(
                section_type, facts
            )
            decision = self._get_generation_decision(coverage)

            constraint = GenerationConstraint(
                section_type=section_type,
                generation_mode=coverage.get("generation_mode", "not_possible"),
                allowed_fact_ids=[f.fact_id for f in facts],
                must_include_facts=self._get_mandatory_facts(facts, coverage),
                min_confidence_threshold=self._compute_threshold(coverage),
            )

            mode = constraint.generation_mode
            if mode == "cautious":
                constraint.restricted_claims = [
                    "Do not use absolute language",
                    "Flag low-confidence predictions",
                    "Do not invent missing metrics",
                ]
            elif mode == "insufficient_evidence":
                constraint.restricted_claims = [
                    "Do not fabricate evidence",
                    "Insert [Insufficient evidence] where facts missing",
                    "Do not expand beyond provided facts",
                ]
            elif mode == "not_possible":
                constraint.restricted_claims = [
                    "DO NOT GENERATE this section",
                    "Return empty section with missing evidence marker",
                ]

            constraints[section_type] = constraint
            self._constraints[section_type] = constraint

            logger.info(
                f"Constraint [{section_type}]: mode={constraint.generation_mode}, "
                f"facts={len(constraint.allowed_fact_ids)}, "
                f"mandatory={len(constraint.must_include_facts)}"
            )
        return constraints

    def _compute_section_coverage(self, section_type: str,
                                    facts: List[Fact]) -> Dict:
        if not facts:
            return {
                "coverage_score": 0.0,
                "confidence_score": 0.0,
                "generation_mode": "not_possible",
            }
        avg_confidence = sum(f.confidence for f in facts) / len(facts)
        type_diversity = min(len(set(f.fact_type for f in facts)) / 5.0, 1.0)
        coverage_score = min(1.0, avg_confidence * 0.6 + type_diversity * 0.4)

        if coverage_score >= 0.8:
            mode = "normal"
        elif coverage_score >= 0.5:
            mode = "cautious"
        elif coverage_score >= 0.1:
            mode = "insufficient_evidence"
        else:
            mode = "not_possible"

        return {
            "coverage_score": round(coverage_score, 3),
            "confidence_score": round(avg_confidence, 3),
            "generation_mode": mode,
        }

    def _get_generation_decision(self, coverage: Dict) -> Dict:
        mode = coverage.get("generation_mode", "not_possible")
        if mode == "normal":
            return {
                "can_generate": True,
                "mode": "normal",
                "message": "Sufficient evidence for full generation",
                "restrictions": [],
            }
        elif mode == "cautious":
            return {
                "can_generate": True,
                "mode": "cautious",
                "message": "Generate with evidence gap warnings",
                "restrictions": ["Flag unsupported claims", "Use hedging language"],
            }
        elif mode == "insufficient_evidence":
            return {
                "can_generate": True,
                "mode": "insufficient_evidence",
                "message": "Insufficient evidence - mark gaps explicitly",
                "restrictions": ["Do not fabricate", "Insert gap markers"],
            }
        return {
            "can_generate": False,
            "mode": "not_possible",
            "message": "Cannot generate - no evidence",
            "restrictions": ["Do not generate this section"],
        }

    def _get_mandatory_facts(self, facts: List[Fact],
                              coverage: Dict) -> List[str]:
        mode = coverage.get("generation_mode", "not_possible")
        if mode == "normal":
            high_conf = [f for f in facts if f.confidence >= 0.8]
            return [f.fact_id for f in high_conf[:5]]
        elif mode == "cautious":
            high_conf = [f for f in facts if f.confidence >= 0.7]
            return [f.fact_id for f in high_conf[:3]]
        return [f.fact_id for f in facts[:2]]

    def _compute_threshold(self, coverage: Dict) -> float:
        mode = coverage.get("generation_mode", "not_possible")
        thresholds = {"normal": 0.5, "cautious": 0.6, "insufficient_evidence": 0.7}
        return thresholds.get(mode, 0.8)

    def get_section_prompt(self, section_type: str, constraint: GenerationConstraint,
                            facts: List[Fact]) -> str:
        if constraint.generation_mode == "not_possible":
            return (
                f"CANNOT GENERATE: '{section_type}'\n"
                f"No evidence available. Do not fabricate content.\n"
                f"Return: 'Insufficient source material available for this section.'"
            )

        parts = [
            f"GENERATE: {section_type.replace('_', ' ').upper()}",
            f"Generation Mode: {constraint.generation_mode.upper()}",
            "",
            "CRITICAL RULES:",
            "1. Use ONLY the facts listed below. Do NOT invent information.",
            "2. Every claim MUST trace to at least one fact by its Fact ID.",
            "3. If evidence is insufficient, insert: "
            "'[Insufficient source material available for this claim.]'",
            "4. Never fabricate: metrics, datasets, algorithms, citations, or results.",
            "5. Prefer incomplete but accurate output over fabricated output.",
        ]

        if constraint.restricted_claims:
            parts.append("")
            parts.append("RESTRICTED CLAIMS (DO NOT USE):")
            for rc in constraint.restricted_claims:
                parts.append(f"  - {rc}")

        parts.extend(["", "AVAILABLE FACTS:"])
        for i, fact in enumerate(facts):
            parts.append(f"  FACT {i+1} [{fact.fact_type.value}] {fact.value[:200]}")
            parts.append(f"         Confidence: {fact.confidence}, "
                        f"Source: {fact.source.file_name}")

        mandatory = constraint.must_include_facts
        if mandatory:
            parts.append("")
            parts.append("MANDATORY FACTS (must be referenced):")
            for mf in [f for f in facts if f.fact_id in mandatory]:
                parts.append(f"  -> {mf.value[:200]}")

        parts.extend([
            "",
            "WRITING CONSTRAINTS:",
            f"- Minimum confidence threshold: {constraint.min_confidence_threshold}",
            "- Reference facts by ID: FACT 1, FACT 2, etc.",
            "- Use academic tone",
            "- Each paragraph: topic sentence -> fact -> explanation -> analysis",
        ])

        return "\n".join(parts)

    def validate_output(self, section_type: str, generated_text: str,
                         constraint: GenerationConstraint,
                         facts: List[Fact]) -> Dict:
        issues = []
        text_lower = generated_text.lower()

        fact_ids_referenced = set()
        for fact in facts:
            if fact.normalized_value[:40] in text_lower:
                fact_ids_referenced.add(fact.fact_id)

        coverage = len(fact_ids_referenced) / max(len(facts), 1)
        if coverage < 0.3:
            issues.append("Less than 30% of facts referenced in generated content")

        for mf_id in constraint.must_include_facts:
            if mf_id not in fact_ids_referenced:
                issues.append(f"Mandatory fact {mf_id} not referenced")

        hallucination_risk = 1.0 - coverage
        if hallucination_risk > 0.5 and constraint.generation_mode == "normal":
            issues.append("High hallucination risk relative to generation mode")

        return {
            "section_type": section_type,
            "fact_coverage": round(coverage, 3),
            "facts_referenced": len(fact_ids_referenced),
            "total_facts": len(facts),
            "hallucination_risk": round(hallucination_risk, 3),
            "issues": issues,
            "passed": len(issues) == 0,
        }

    def get_constraint(self, section_type: str) -> Optional[GenerationConstraint]:
        return self._constraints.get(section_type)

    def get_all_constraints(self) -> Dict[str, GenerationConstraint]:
        return dict(self._constraints)

    def reset(self):
        self._constraints.clear()
