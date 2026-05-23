"""QualityGate — blocks export when overall quality < 8.5, triggers auto-regeneration."""

from typing import Dict, List, Optional, Callable
from src.core.logger import get_logger

logger = get_logger(__name__)


TARGET_OVERALL = 8.5
SCORE_WEIGHTS = {
    "technical_depth": 0.20,
    "evidence_score": 0.20,
    "coherence_score": 0.15,
    "academic_score": 0.15,
    "uniqueness_score": 0.10,
    "formatting_score": 0.10,
    "filler_score": 0.10,
}


class QualityGate:

    def evaluate(self, scores: Dict[str, float]) -> Dict[str, any]:
        missing = [k for k in SCORE_WEIGHTS if k not in scores]
        if missing:
            logger.warning(f"QualityGate: missing scores: {missing}")

        weighted = 0.0
        detail = {}
        for metric, weight in SCORE_WEIGHTS.items():
            val = scores.get(metric, 0.0)
            weighted += val * weight
            detail[metric] = {
                "score": round(val, 3),
                "weight": weight,
                "contribution": round(val * weight, 3),
            }

        overall = min(weighted / sum(SCORE_WEIGHTS.values()), 1.0) * 10.0
        passed = overall >= TARGET_OVERALL

        return {
            "overall": round(overall, 2),
            "target": TARGET_OVERALL,
            "passed": passed,
            "detail": detail,
            "weakest_metrics": sorted(
                [(k, v["score"]) for k, v in detail.items()],
                key=lambda x: x[1],
            )[:3],
        }

    def evaluate_sections(self,
                          sections: Dict[str, Dict[str, float]]
                          ) -> Dict[str, any]:
        results = {}
        all_passed = True
        weak_sections = []

        for section_name, scores in sections.items():
            result = self.evaluate(scores)
            results[section_name] = result
            if not result["passed"]:
                all_passed = False
                weak_sections.append({
                    "section": section_name,
                    "overall": result["overall"],
                    "weakest": result["weakest_metrics"],
                })

        return {
            "sections": results,
            "all_passed": all_passed,
            "weak_sections": weak_sections,
            "total_sections": len(sections),
            "weak_count": len(weak_sections),
        }
