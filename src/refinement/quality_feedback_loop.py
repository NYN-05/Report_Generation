from typing import Dict, List, Optional, Tuple, Callable
from src.core.logger import get_logger

logger = get_logger(__name__)


class QualityFeedbackLoop:
    def __init__(self, max_iterations: int = 3,
                 improvement_threshold: float = 0.05):
        self._max_iterations = max_iterations
        self._improvement_threshold = improvement_threshold
        self._iteration_history: List[Dict] = []

    def run(self, scorer_fn: Callable[[], Dict[str, float]],
            refiner_fn: Callable[[Dict[str, float]], bool],
            section_type: str) -> Tuple[bool, List[Dict]]:
        self._iteration_history = []
        for i in range(self._max_iterations):
            scores = scorer_fn()
            iteration = {
                "iteration": i + 1,
                "scores": scores,
                "improved": False,
            }
            all_passing = all(v >= 0.5 for v in scores.values())
            if all_passing:
                iteration["status"] = "passed"
                self._iteration_history.append(iteration)
                logger.info(f"Quality loop passed at iteration {i + 1} for '{section_type}'")
                return True, self._iteration_history
            if i == self._max_iterations - 1:
                iteration["status"] = "max_iterations_reached"
                self._iteration_history.append(iteration)
                logger.info(f"Quality loop max iterations ({self._max_iterations}) reached for '{section_type}'")
                return False, self._iteration_history
            refined = refiner_fn(scores)
            if i > 0:
                prev = self._iteration_history[-1]["scores"]
                improvements = {}
                for k in scores:
                    delta = scores[k] - prev.get(k, 0)
                    improvements[k] = delta
                iteration["improvements"] = improvements
                iteration["improved"] = any(
                    v >= self._improvement_threshold for v in improvements.values()
                )
            self._iteration_history.append(iteration)
        return False, self._iteration_history

    def get_history(self) -> List[Dict]:
        return list(self._iteration_history)

    def get_best_scores(self) -> Optional[Dict[str, float]]:
        if not self._iteration_history:
            return None
        best = max(self._iteration_history, key=lambda x: sum(x["scores"].values()))
        return best["scores"]

    def reset(self):
        self._iteration_history.clear()
