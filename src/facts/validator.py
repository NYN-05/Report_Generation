from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from src.core.logger import get_logger
from .models import Fact, FactType, MetricFact, ResultFact, DatasetFact

logger = get_logger(__name__)


@dataclass
class FactValidationIssue:
    field: str
    message: str
    severity: str = "warning"

    def to_dict(self) -> Dict:
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class FactValidationResult:
    is_valid: bool
    fact_id: str
    issues: List[FactValidationIssue] = field(default_factory=list)
    confidence_adjustment: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "fact_id": self.fact_id,
            "issues": [i.to_dict() for i in self.issues],
            "confidence_adjustment": self.confidence_adjustment,
        }


class FactValidator:
    def __init__(self):
        self._results: List[FactValidationResult] = []

    def validate(self, fact: Fact) -> FactValidationResult:
        issues = []
        confidence_adjustment = 0.0

        if not fact.value or len(fact.value.strip()) < 5:
            issues.append(FactValidationIssue("value", "Fact value too short", "error"))
        if not fact.source.resource_id:
            issues.append(FactValidationIssue("source", "Missing resource_id", "warning"))
            confidence_adjustment -= 0.1
        if fact.confidence <= 0.0 or fact.confidence > 1.0:
            issues.append(FactValidationIssue("confidence", "Confidence out of range [0,1]", "error"))
        if fact.fact_type == FactType.GENERAL and fact.confidence > 0.8:
            issues.append(FactValidationIssue("confidence", "General fact with high confidence", "warning"))
            confidence_adjustment -= 0.1

        if isinstance(fact, MetricFact):
            type_issues = self._validate_metric_fact(fact)
            issues.extend(type_issues)
        elif isinstance(fact, ResultFact):
            type_issues = self._validate_result_fact(fact)
            issues.extend(type_issues)
        elif isinstance(fact, DatasetFact):
            type_issues = self._validate_dataset_fact(fact)
            issues.extend(type_issues)

        is_valid = not any(i.severity == "error" for i in issues)
        result = FactValidationResult(
            is_valid=is_valid,
            fact_id=fact.fact_id,
            issues=issues,
            confidence_adjustment=round(confidence_adjustment, 2),
        )
        self._results.append(result)
        return result

    def _validate_metric_fact(self, fact: MetricFact) -> List[FactValidationIssue]:
        issues = []
        if not fact.metric_name:
            issues.append(FactValidationIssue("metric_name", "Missing metric name", "warning"))
        if fact.metric_value is not None and (fact.metric_value < 0 or fact.metric_value > 1000):
            issues.append(FactValidationIssue("metric_value", f"Unusual metric value: {fact.metric_value}", "warning"))
        return issues

    def _validate_result_fact(self, fact: ResultFact) -> List[FactValidationIssue]:
        issues = []
        if fact.metric_value is not None and fact.metric_value > 1000:
            issues.append(FactValidationIssue("metric_value", f"Result value unusually high: {fact.metric_value}", "warning"))
        if fact.metric_value is not None and fact.baseline_value is not None:
            if fact.metric_value == fact.baseline_value:
                issues.append(FactValidationIssue("improvement", "No improvement over baseline", "warning"))
        return issues

    def _validate_dataset_fact(self, fact: DatasetFact) -> List[FactValidationIssue]:
        issues = []
        if fact.dataset_size and fact.dataset_size.isdigit():
            size = int(fact.dataset_size)
            if size > 10**12:
                issues.append(FactValidationIssue("dataset_size", "Dataset size unusually large", "warning"))
        return issues

    def validate_batch(self, facts: List[Fact]) -> List[FactValidationResult]:
        return [self.validate(f) for f in facts]

    def get_high_confidence_facts(self, facts: List[Fact]) -> List[Fact]:
        valid = []
        for fact in facts:
            result = self.validate(fact)
            if result.is_valid:
                adjusted = fact.confidence + result.confidence_adjustment
                if adjusted >= 0.5:
                    valid.append(fact)
        return valid

    def get_results(self) -> List[FactValidationResult]:
        return list(self._results)

    def get_summary(self) -> Dict:
        total = len(self._results)
        if total == 0:
            return {"total_validated": 0, "valid": 0, "invalid": 0}
        valid = sum(1 for r in self._results if r.is_valid)
        return {
            "total_validated": total,
            "valid": valid,
            "invalid": total - valid,
            "total_issues": sum(len(r.issues) for r in self._results),
        }

    def reset(self):
        self._results.clear()
