from typing import List, Dict, Optional
from .base import BaseChecker, ReviewResult
from .coherence import CoherenceChecker
from .style import StyleChecker
from .citations import CitationChecker
from .redundancy import RedundancyChecker
from .formatting import FormattingChecker
from src.core.logger import get_logger

logger = get_logger(__name__)


class ReviewPipeline:
    """Orchestrates all review passes over generated content."""

    def __init__(self):
        self._checkers: List[BaseChecker] = [
            CoherenceChecker(),
            StyleChecker(),
            CitationChecker(),
            RedundancyChecker(),
            FormattingChecker(),
        ]

    def review_sections(self, sections: List[Dict], **kwargs) -> Dict:
        results = {}
        for checker in self._checkers:
            try:
                result = checker.check(sections, **kwargs)
                results[checker.name] = result.to_dict()
            except Exception as e:
                logger.error(f"Checker '{checker.name}' failed: {e}")
                results[checker.name] = {
                    "checker": checker.name,
                    "passed": False,
                    "issue_count": 1,
                    "issues": [{"severity": "error", "message": str(e), "location": ""}],
                }

        total_issues = sum(r["issue_count"] for r in results.values())
        passed = all(r["passed"] for r in results.values())

        return {
            "passed": passed,
            "total_issues": total_issues,
            "results": results,
        }

    def review_plan(self, plan: Dict) -> Dict:
        sections = plan.get("sections", [])
        return self.review_sections(sections)

    def get_summary(self, report: Dict) -> str:
        lines = ["Review Results:"]
        for name, result in report.get("results", {}).items():
            status = "PASS" if result.get("passed") else "ISSUES"
            lines.append(f"  {name}: {status} ({result.get('issue_count', 0)} issues)")
        lines.append(f"  Total: {report.get('total_issues', 0)} issues")
        return "\n".join(lines)
