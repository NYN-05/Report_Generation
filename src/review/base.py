from typing import List, Dict, Any
from src.core.logger import get_logger

logger = get_logger(__name__)


class ReviewResult:
    def __init__(self, checker_name: str):
        self.checker_name = checker_name
        self.issues: List[Dict[str, Any]] = []
        self.passed: bool = True

    def add_issue(self, severity: str, message: str, location: str = ""):
        self.issues.append({
            "severity": severity,
            "message": message,
            "location": location,
        })
        self.passed = False

    def to_dict(self) -> Dict:
        return {
            "checker": self.checker_name,
            "passed": self.passed,
            "issue_count": len(self.issues),
            "issues": self.issues,
        }


class BaseChecker:
    def __init__(self, name: str):
        self.name = name

    def check(self, sections: List[Dict], **kwargs) -> ReviewResult:
        raise NotImplementedError
