"""IterativeRefinementLoop — score, improve, repeat until all scores >= 8.5."""

from typing import Dict, List, Optional, Callable
from src.core.logger import get_logger

logger = get_logger(__name__)


TARGET_SCORE = 8.5
MAX_ITERATIONS = 5


class IterativeRefinementLoop:

    def __init__(self):
        self._iteration_logs: List[Dict] = []

    def refine(self, text: str, scorer: Callable[[str], Dict[str, float]],
               improver: Callable[[str, Dict[str, float]], str],
               target: float = TARGET_SCORE,
               max_iterations: int = MAX_ITERATIONS) -> tuple:
        self._iteration_logs = []
        current_text = text
        iteration = 0

        while iteration < max_iterations:
            scores = scorer(current_text)
            overall = scores.get("overall", 0.0) * 10.0
            passed = overall >= target

            log_entry = {
                "iteration": iteration,
                "overall_score": round(overall, 2),
                "target": target,
                "passed": passed,
                "scores": {k: round(v * 10, 2) if isinstance(v, float) else v
                          for k, v in scores.items()},
            }
            self._iteration_logs.append(log_entry)
            logger.info(
                f"Refinement iter {iteration}: overall={overall:.2f}/{target} "
                f"passed={passed}"
            )

            if passed:
                logger.info(f"Target reached at iteration {iteration}")
                return current_text, self._iteration_logs

            current_text = improver(current_text, scores)
            iteration += 1

        logger.warning(f"Max iterations ({max_iterations}) reached without meeting target")
        return current_text, self._iteration_logs

    def get_logs(self) -> List[Dict]:
        return list(self._iteration_logs)
