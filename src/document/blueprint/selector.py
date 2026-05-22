import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from .models import Blueprint
from .loader import BlueprintLoader
from src.core.logger import get_logger

logger = get_logger(__name__)


class BlueprintSelector:
    """Selects the best blueprint for a given query."""

    def __init__(self, loader: Optional[BlueprintLoader] = None):
        self.loader = loader or BlueprintLoader()

    def select(self, query: str) -> Optional[Blueprint]:
        query_lower = query.strip().lower()

        blueprints = self.loader.load_all()
        if not blueprints:
            logger.warning("No blueprints available for selection")
            return None

        candidates = self._rank(query_lower, blueprints)
        if not candidates:
            logger.warning(f"No blueprint matched query: {query}")
            return None

        best_id, best_score = candidates[0]
        logger.info(f"Selected blueprint '{best_id}' (score={best_score:.2f}) for query: {query}")
        return blueprints[best_id]

    def select_with_fallback(self, query: str) -> Blueprint:
        result = self.select(query)
        if result is not None:
            return result
        blueprints = self.loader.load_all()
        if blueprints:
            fallback_id = list(blueprints.keys())[0]
            logger.info(f"Falling back to default blueprint: {fallback_id}")
            return blueprints[fallback_id]
        raise RuntimeError("No blueprints available")

    def suggest(self, query: str, top_n: int = 3) -> List[Tuple[str, str, float]]:
        query_lower = query.strip().lower()
        blueprints = self.loader.load_all()
        candidates = self._rank(query_lower, blueprints)
        return [
            (bp_id, blueprints[bp_id].name, score)
            for bp_id, score in candidates[:top_n]
        ]

    def list_blueprints(self) -> Dict[str, str]:
        return self.loader.get_available()

    def _rank(self, query: str, blueprints: Dict[str, Blueprint]
              ) -> List[Tuple[str, float]]:
        scores: List[Tuple[str, float]] = []

        for bp_id, bp in blueprints.items():
            score = self._match_score(query, bp)
            scores.append((bp_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _match_score(self, query: str, blueprint: Blueprint) -> float:
        max_score = 0.0

        name_lower = blueprint.name.lower()
        desc_lower = blueprint.description.lower()

        bp_text = f"{name_lower} {desc_lower}"

        keywords = re.findall(r'\w+', query)
        matched_keywords = 0
        for kw in keywords:
            if kw in bp_text:
                matched_keywords += 1
        if keywords:
            max_score = max(max_score, matched_keywords / len(keywords) * 0.8)

        id_ratio = SequenceMatcher(None, query, blueprint.id).ratio()
        name_ratio = SequenceMatcher(None, query, name_lower).ratio()
        max_score = max(max_score, id_ratio, name_ratio)

        if blueprint.id in query or query in blueprint.id:
            max_score = max(max_score, 0.9)

        common_patterns = {
            r'\bfinal\s*year\b': "engineering_project",
            r'\bengineering\b': "engineering_project",
            r'\bproject\b': "engineering_project",
            r'\bb\.?tech\b': "engineering_project",
            r'\bresearch\b': "research_paper",
            r'\bpaper\b': "research_paper",
            r'\bjournal\b': "research_paper",
            r'\bconference\b': "research_paper",
            r'\binternship\b': "internship_report",
            r'\btraining\b': "internship_report",
            r'\bindustrial\b': "internship_report",
        }

        for pattern, target_id in common_patterns.items():
            if re.search(pattern, query):
                if blueprint.id == target_id:
                    max_score = max(max_score, 0.85)

        return max_score
