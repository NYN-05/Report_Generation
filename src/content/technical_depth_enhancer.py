"""TechnicalDepthEnhancer — enforces What/How/Why/Impact/Limitations/Applications/Future answers per paragraph."""

from typing import Dict, List, Optional
import re
from src.core.logger import get_logger

logger = get_logger(__name__)


DIMENSIONS = {
    "what": {
        "triggers": [r"\bis\b", r"\bdefined as\b", r"\brefers to\b", r"\bconsists of\b",
                     r"\binvolves\b", r"\bcomprises\b", r"\bcharacterized by\b",
                     r"\bdescribes\b", r"\brepresents\b", r"\bdenotes\b"],
        "weight": 1.0,
    },
    "how": {
        "triggers": [r"\bby\b", r"\busing\b", r"\bvia\b", r"\bthrough\b",
                     r"\bemploys\b", r"\butilizes\b", r"\bimplements\b",
                     r"\boperates\b", r"\bworks by\b", r"\bmethod\b",
                     r"\bapproach\b", r"\btechnique\b"],
        "weight": 1.0,
    },
    "why": {
        "triggers": [r"\bbecause\b", r"\btherefore\b", r"\bhence\b", r"\bthus\b",
                     r"\bmotivated by\b", r"\bdue to\b", r"\bas a result\b",
                     r"\bthe reason\b", r"\bjustification\b", r"\brationale\b"],
        "weight": 1.0,
    },
    "impact": {
        "triggers": [r"\bimpact\b", r"\beffect\b", r"\binfluence\b", r"\bresult\b",
                     r"\bconsequence\b", r"\boutcome\b", r"\bimproved\b",
                     r"\benhanced\b", r"\bperformance\b", r"\baccuracy\b",
                     r"\befficiency\b", r"\breduction\b"],
        "weight": 1.0,
    },
    "limitations": {
        "triggers": [r"\blimitation\b", r"\bdrawback\b", r"\bweakness\b",
                     r"\bchallenge\b", r"\bconstraint\b", r"\btrade-off\b",
                     r"\bhowever\b", r"\bbut\b", r"\bnegative\b",
                     r"\bdisadvantage\b", r"\bdifficulty\b", r"\bissue\b"],
        "weight": 0.8,
    },
    "applications": {
        "triggers": [r"\bapplication\b", r"\buse case\b", r"\bdeployed\b",
                     r"\bapplied to\b", r"\bused in\b", r"\bpractical\b",
                     r"\breal.world\b", r"\bindustry\b", r"\bdomain\b",
                     r"\bscenario\b"],
        "weight": 0.8,
    },
    "future": {
        "triggers": [r"\bfuture\b", r"\bnext steps\b", r"\bfurther\b",
                     r"\bupcoming\b", r"\bpotential\b", r"\bprospect\b",
                     r"\bdirection\b", r"\bongoing\b", r"\bopen question\b",
                     r"\bunresolved\b"],
        "weight": 0.6,
    },
}

MIN_DIMENSIONS_COVERED = 4


class TechnicalDepthEnhancer:

    def score(self, text: str) -> Dict[str, any]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return {"overall": 0.0, "dimensions_covered": 0, "needs_expansion": True}

        para_scores = []
        total_expansions_needed = 0
        for para in paragraphs:
            pd = self._score_paragraph(para)
            para_scores.append(pd)
            if pd["covered"] < MIN_DIMENSIONS_COVERED:
                total_expansions_needed += 1

        avg_covered = sum(p["covered"] for p in para_scores) / len(para_scores)
        overall = avg_covered / len(DIMENSIONS)

        return {
            "overall": round(overall, 3),
            "dimensions_covered": round(avg_covered, 1),
            "max_dimensions": len(DIMENSIONS),
            "needs_expansion": total_expansions_needed > 0,
            "paragraphs_needing_expansion": total_expansions_needed,
            "total_paragraphs": len(paragraphs),
            "paragraph_scores": para_scores,
        }

    def _score_paragraph(self, text: str) -> Dict:
        text_lower = text.lower()
        dimensions = {}
        covered = 0
        missing = []
        for dim_name, dim_info in DIMENSIONS.items():
            found = any(re.search(pat, text_lower) for pat in dim_info["triggers"])
            dimensions[dim_name] = found
            if found:
                covered += 1
            else:
                missing.append(dim_name)
        return {
            "covered": covered,
            "dimensions": dimensions,
            "missing": missing,
            "needs_expansion": covered < MIN_DIMENSIONS_COVERED,
            "words": len(text.split()),
        }
