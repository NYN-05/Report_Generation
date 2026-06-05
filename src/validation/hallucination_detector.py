from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
import re
from src.core.logger import get_logger
from src.facts.models import Fact, FactType, MetricFact, ResultFact
from src.facts.store import FactStore
from src.generator.content_blocks import SectionContent, ParagraphBlock, SourceRequiredBlock

logger = get_logger(__name__)


@dataclass
class HallucinationIssue:
    issue_type: str
    claim: str
    severity: str
    message: str
    suggested_fix: str = ""
    location: str = ""

    def to_dict(self) -> Dict:
        return {
            "issue_type": self.issue_type,
            "claim": self.claim[:200],
            "severity": self.severity,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
            "location": self.location,
        }


HALLUCINATION_PATTERNS = {
    "unsupported_metric": {
        "patterns": [
            r"(?:achieved|reached|obtained|reported)\s+(?:an?\s+)?"
            r"(?:accuracy|precision|recall|f1[-\s]?score|AUC|BLEU|ROUGE)\s+"
            r"(?:of\s+)?\d+\.?\d*\s*\%?",
            r"\d+\.?\d*\s*\%\s+(?:accuracy|precision|recall|f1)",
        ],
        "fact_types": {FactType.METRIC, FactType.RESULT},
    },
    "unsupported_algorithm": {
        "patterns": [
            r"\b(?:we\s+(?:used|applied|implemented|employed)\s+(?:the\s+)?)"
            r"(?:Random Forest|SVM|K-Means|CNN|RNN|LSTM|Transformer|BERT|GPT)",
            r"\b(?:our\s+(?:algorithm|model|method|approach))\s+"
            r"(?:is\s+based\s+on|uses|employs)\s+[A-Z][a-zA-Z]+",
        ],
        "fact_types": {FactType.ALGORITHM},
    },
    "unsupported_dataset": {
        "patterns": [
            r"\b(?:using|on|with)\s+(?:the\s+)?"
            r"(?:[A-Z][a-zA-Z0-9_-]{2,})\s*(?:dataset|corpus|benchmark)",
            r"\b(?:dataset|corpus|data)\s+(?:contain(?:s|ing)\s+)?\d+[kKmMbB]?",
        ],
        "fact_types": {FactType.DATASET},
    },
    "unsupported_technology": {
        "patterns": [
            r"\b(?:implemented|built|developed|deployed)\s+(?:using|with|on)\s+"
            r"(?:[A-Z][a-zA-Z0-9_.+-]+)",
        ],
        "fact_types": {FactType.TECHNOLOGY},
    },
    "unsupported_architecture": {
        "patterns": [
            r"\b(?:our\s+)?(?:architecture|system|framework|pipeline)\s+"
            r"(?:consists?|comprises?|includes?)\s+\w+",
        ],
        "fact_types": {FactType.ARCHITECTURE},
    },
    "unsupported_citation": {
        "patterns": [
            r"\[(\d+)\]",
            r"\([A-Z][a-zA-Z]*\s+et\s+al\.?\s*,\s*\d{4}\)",
        ],
        "fact_types": {FactType.CITATION},
    },
    "absolute_claim": {
        "patterns": [
            r"\b(?:always|never|all\s+cases|every\s+time|no\s+exception)\b",
        ],
        "fact_types": set(),
    },
}


class HallucinationDetector:
    def __init__(self, fact_store: Optional[FactStore] = None):
        self._fact_store = fact_store
        self._issues: List[HallucinationIssue] = []

    def check(self, fact_store: FactStore, paragraph_text: str,
              paragraph_id: str = "") -> List[HallucinationIssue]:
        issues = []
        text = paragraph_text

        for issue_type, config in HALLUCINATION_PATTERNS.items():
            for pattern in config["patterns"]:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    claim = match.group(0).strip()
                    if len(claim) < 10:
                        continue
                    if config["fact_types"]:
                        if not self._is_supported_by_facts(claim, fact_store, config["fact_types"]):
                            issue = HallucinationIssue(
                                issue_type=issue_type,
                                claim=claim,
                                severity="high" if issue_type != "absolute_claim" else "medium",
                                message=f"Unsupported {issue_type.replace('_', ' ')}: '{claim[:100]}'",
                                suggested_fix=self._suggest_fix(issue_type, claim),
                                location=paragraph_id,
                            )
                            issues.append(issue)
                    else:
                        issue = HallucinationIssue(
                            issue_type=issue_type,
                            claim=claim,
                            severity="medium",
                            message=f"Absolute claim detected: '{claim[:100]}'",
                            suggested_fix="Use hedging language or remove absolute statement",
                            location=paragraph_id,
                        )
                        issues.append(issue)

        self._issues.extend(issues)
        if issues:
            logger.warning(
                f"Found {len(issues)} hallucination issues in paragraph {paragraph_id}"
            )
        return issues

    def _is_supported_by_facts(self, claim: str, fact_store: FactStore,
                                required_types: Set[FactType]) -> bool:
        claim_lower = claim.lower()
        matched_facts = fact_store.search_by_value(claim_lower[:50])
        matched_types = set()
        for fact in matched_facts[:20]:
            if fact and fact.is_active:
                if any(phrase in claim_lower for phrase in fact.normalized_value.split()[:5]):
                    matched_types.add(fact.fact_type)
        supporting_types = matched_types & required_types
        if len(supporting_types) >= len(required_types):
            return True
        return False

    def check_section(self, fact_store: FactStore, section_text: str,
                       section_type: str = "") -> Dict:
        paragraphs = [p.strip() for p in section_text.split("\n\n") if p.strip()]
        all_issues = []
        for i, para in enumerate(paragraphs):
            para_id = f"{section_type}_p{i}" if section_type else f"p{i}"
            issues = self.check(fact_store, para, para_id)
            all_issues.extend(issues)

        unsupported_claims = [i for i in all_issues if i.severity == "high"]
        warnings = [i for i in all_issues if i.severity == "medium"]

        return {
            "total_issues": len(all_issues),
            "unsupported_claims": len(unsupported_claims),
            "warnings": len(warnings),
            "issues": all_issues,
            "has_hallucinations": len(unsupported_claims) > 0,
        }

    def check_report(self, fact_store: FactStore,
                      sections: Dict[str, str]) -> Dict:
        all_issues = []
        total = 0
        for section_type, section_text in sections.items():
            result = self.check_section(fact_store, section_text, section_type)
            all_issues.extend(result["issues"])
            total += result["total_issues"]

        return {
            "total_issues": total,
            "sections_checked": len(sections),
            "hallucination_free": total == 0,
            "issues": [i.to_dict() for i in all_issues],
            "recommendations": self._generate_recommendations(all_issues),
        }

    def _suggest_fix(self, issue_type: str, claim: str) -> str:
        fixes = {
            "unsupported_metric": "Verify metric value in source documents or remove",
            "unsupported_algorithm": "Check source code or documentation for this algorithm",
            "unsupported_dataset": "Verify dataset name in provided resources",
            "unsupported_technology": "Confirm technology usage in project files",
            "unsupported_architecture": "Verify architecture from technical documentation",
            "unsupported_citation": "Remove citation or provide actual reference",
            "absolute_claim": "Replace with qualified language",
        }
        return fixes.get(issue_type, "Verify claim against source evidence")

    def _generate_recommendations(self, issues: List[HallucinationIssue]) -> List[str]:
        recs = set()
        for issue in issues:
            if issue.issue_type == "unsupported_metric":
                recs.add("Verify all metrics against source data before export")
            elif issue.issue_type == "unsupported_citation":
                recs.add("Remove all citations not backed by provided references")
            elif issue.issue_type == "absolute_claim":
                recs.add("Replace absolute language with evidence-based qualifications")
            elif issue.severity == "high":
                recs.add(f"Review unsupported {issue.issue_type.replace('_', ' ')} claims")
        return list(recs)

    def rewrite_paragraph(self, text: str, issues: List[HallucinationIssue]) -> str:
        result = text
        for issue in sorted(issues, key=lambda x: -len(x.claim)):
            if issue.severity == "high":
                replacement = self._get_replacement(issue)
                result = result.replace(issue.claim, replacement, 1)
        return result

    def _get_replacement(self, issue: HallucinationIssue) -> str:
        if issue.issue_type == "unsupported_metric":
            return "[METRIC VALUE FROM SOURCE REQUIRED]"
        elif issue.issue_type == "unsupported_algorithm":
            return "[ALGORITHM NAME FROM SOURCE REQUIRED]"
        elif issue.issue_type == "unsupported_dataset":
            return "[DATASET NAME FROM SOURCE REQUIRED]"
        elif issue.issue_type == "unsupported_citation":
            return "[CITATION FROM SOURCE REQUIRED]"
        elif issue.issue_type in ("unsupported_technology", "unsupported_architecture"):
            return f"[{issue.issue_type.replace('unsupported_', '').upper()} FROM SOURCE REQUIRED]"
        return "[SOURCE MATERIAL REQUIRED]"

    def filter_sections(self, sections: List[SectionContent], issues: List[Dict]) -> int:
        filtered_count = 0
        for section in sections:
            section_issues = []
            for issue in issues:
                loc = issue.get("location", "") if isinstance(issue, dict) else getattr(issue, "location", "")
                prefix = f"{section.heading}_p"
                if loc.startswith(prefix):
                    try:
                        para_idx = int(loc.split("_p")[-1])
                        section_issues.append((para_idx, issue))
                    except ValueError:
                        continue
            if not section_issues:
                continue
            high_severity_indices = set()
            for idx, iss in section_issues:
                sev = iss.get("severity", "") if isinstance(iss, dict) else getattr(iss, "severity", "")
                if sev == "high" and 0 <= idx < len(section.blocks):
                    block = section.blocks[idx]
                    if hasattr(block, 'text') and getattr(block, 'text', ''):
                        high_severity_indices.add(idx)
            for idx in sorted(high_severity_indices, reverse=True):
                msg = "Insufficient source material available for this claim."
                section.blocks[idx] = SourceRequiredBlock(
                    query=section.heading,
                    message=msg,
                )
                filtered_count += 1
        if filtered_count:
            logger.info(f"Post-generation filtering replaced {filtered_count} hallucinated paragraphs")
        return filtered_count

    def get_all_issues(self) -> List[HallucinationIssue]:
        return list(self._issues)

    def get_statistics(self) -> Dict:
        if not self._issues:
            return {"total_issues": 0, "hallucination_free": True}
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for issue in self._issues:
            by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
        return {
            "total_issues": len(self._issues),
            "by_type": by_type,
            "by_severity": by_severity,
            "hallucination_free": len(self._issues) == 0,
        }

    def reset(self):
        self._issues.clear()
