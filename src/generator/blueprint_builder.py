from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter, defaultdict
import re
import math
from src.core.logger import get_logger
from src.facts.models import Fact, FactType
from src.facts.store import FactStore
from src.quality.unified_score import compute_pre_generation_score

logger = get_logger(__name__)

STOPWORDS = {
    "the", "a", "an", "this", "that", "these", "those", "in", "on", "at",
    "by", "for", "with", "from", "to", "of", "and", "or", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "can", "could", "may", "might",
    "shall", "should", "about", "into", "through", "during", "before",
    "after", "above", "below", "between", "out", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "also", "because", "as", "until",
    "while", "it", "its", "they", "them", "their", "we", "our", "you",
    "your", "he", "she", "his", "her", "him", "which", "using", "used",
    "based", "called", "known", "also", "within", "without", "across",
    "among", "including", "following", "per", "via", "due",
}

TECHNICAL_FACT_TYPES = {
    FactType.ALGORITHM, FactType.TECHNOLOGY, FactType.ARCHITECTURE,
    FactType.DATASET, FactType.RESULT, FactType.METRIC,
}

TECHNICAL_HEADINGS = {
    FactType.OBJECTIVE: "Introduction",
    FactType.GENERAL: "Background",
    FactType.ALGORITHM: "Algorithm Design",
    FactType.ARCHITECTURE: "System Architecture",
    FactType.TECHNOLOGY: "Technology Stack",
    FactType.DATASET: "Dataset Description",
    FactType.METRIC: "Evaluation Metrics",
    FactType.RESULT: "Experimental Results",
    FactType.CITATION: "Related Work",
    FactType.REQUIREMENT: "Requirements",
    FactType.METHODOLOGY: "Methodology",
    FactType.PROBLEM: "Problem Statement",
    FactType.MODULE: "System Components",
}

KNOWLEDGE_HEADINGS = {
    FactType.OBJECTIVE: "Introduction",
    FactType.GENERAL: "Overview",
    FactType.ALGORITHM: "Methodology",
    FactType.ARCHITECTURE: "Structural Overview",
    FactType.TECHNOLOGY: "Tools and Frameworks",
    FactType.DATASET: "Data Sources",
    FactType.METRIC: "Key Metrics",
    FactType.RESULT: "Key Findings",
    FactType.CITATION: "References",
    FactType.REQUIREMENT: "Requirements",
    FactType.METHODOLOGY: "Approach",
    FactType.PROBLEM: "Problem Context",
    FactType.MODULE: "Components",
}

MERGABLE_TYPES = {
    FactType.ALGORITHM: FactType.METHODOLOGY,
    FactType.MODULE: FactType.TECHNOLOGY,
    FactType.PROBLEM: FactType.OBJECTIVE,
}


@dataclass
class BlueprintSection:
    section_type: str
    heading: str
    facts: List[Fact]
    priority: int
    cluster_terms: List[str]
    unified_score: float
    meets_threshold: bool
    pruning_reason: str = ""

    @property
    def fact_count(self) -> int:
        return len(self.facts)


class BlueprintBuilder:
    def __init__(self, fact_store: FactStore):
        self._store = fact_store

    def build(self, topic: str, min_facts: int = 3,
              max_facts_per_section: int = 20) -> List[BlueprintSection]:
        all_facts = self._store.get_verified_facts()
        if not all_facts:
            all_facts = self._store.get_all_facts()
        if not all_facts:
            return []

        type_groups = self._group_by_type(all_facts)
        clusters = self._merge_small_groups(type_groups)
        expanded = self._split_large_groups(clusters, max_facts_per_section)
        is_technical = self._is_technical(all_facts)

        sections = []
        for i, (ft, fact_list, sub_term) in enumerate(expanded):
            heading = self._derive_heading(fact_list, ft, is_technical, topic, sub_term)
            terms = self._extract_terms(fact_list)
            score = compute_pre_generation_score(fact_list)
            meets = len(fact_list) >= min_facts
            reason = "" if meets else f"Only {len(fact_list)} facts (minimum {min_facts})"

            sections.append(BlueprintSection(
                section_type=ft.value,
                heading=heading,
                facts=fact_list,
                priority=i + 1,
                cluster_terms=terms[:3],
                unified_score=score,
                meets_threshold=meets,
                pruning_reason=reason,
            ))

        logger.info(
            f"Blueprint: {len(sections)} sections from {len(all_facts)} facts "
            f"({sum(1 for s in sections if not s.meets_threshold)} below threshold) for '{topic}'"
        )
        return sections

    def _split_large_groups(
        self,
        clusters: List[Tuple[FactType, List[Fact]]],
        max_size: int = 20,
    ) -> List[Tuple[FactType, List[Fact], str]]:
        result = []
        for ft, fact_list in clusters:
            if len(fact_list) <= max_size:
                result.append((ft, fact_list, ""))
                continue
            word_counts = Counter()
            for f in fact_list:
                for token in re.findall(r'[A-Za-z][a-zA-Z]{3,}', f.value):
                    lower = token.lower()
                    if lower not in STOPWORDS:
                        word_counts[lower] += 1
            generic_terms = {"system", "model", "method", "approach", "study",
                             "research", "data", "information", "result",
                             "process", "analysis", "overview", "summary",
                             "use", "using", "based", "set", "type", "value",
                             "number", "part", "way", "different", "important",
                             "significant", "specific", "common", "general"}
            min_count = max(3, int(len(fact_list) * 0.05))
            max_count = int(len(fact_list) * 0.80)
            top_terms = [w for w, _ in word_counts.most_common(8)
                         if w not in generic_terms
                         and min_count <= word_counts[w] <= max_count][:4]
            if not top_terms:
                result.append((ft, fact_list, ""))
                continue
            assigned = set()
            for term in top_terms:
                group = [f for f in fact_list
                         if term in f.value.lower() and id(f) not in assigned]
                if len(group) >= 3:
                    for f in group:
                        assigned.add(id(f))
                    result.append((ft, group, term.capitalize()))
            remaining = [f for f in fact_list if id(f) not in assigned]
            if remaining:
                label = "Additional" if assigned else ""
                result.append((ft, remaining, label))
            logger.info(
                f"Split {ft.value} ({len(fact_list)} facts) into "
                f"{len(result[-len(top_terms):]) + (1 if remaining else 0)} sub-sections"
            )
        return result

    def _group_by_type(self, facts: List[Fact]) -> Dict[FactType, List[Fact]]:
        groups = defaultdict(list)
        for f in facts:
            groups[f.fact_type].append(f)
        return dict(groups)

    def _merge_small_groups(self, groups: Dict[FactType, List[Fact]]) -> List[Tuple[FactType, List[Fact]]]:
        merged = {}
        small = []
        for ft, flist in groups.items():
            if len(flist) >= 3:
                merged[ft] = flist
            else:
                small.append((ft, flist))
        for ft, flist in small:
            target = MERGABLE_TYPES.get(ft)
            if target and target in merged:
                merged[target].extend(flist)
            else:
                merged[ft] = flist
        return sorted(merged.items(), key=lambda x: -len(x[1]))

    @staticmethod
    def _is_technical(facts: List[Fact]) -> bool:
        return any(f.fact_type in TECHNICAL_FACT_TYPES for f in facts)

    @staticmethod
    def _derive_heading(facts: List[Fact], fact_type: FactType,
                        is_technical: bool, topic: str,
                        sub_term: str = "") -> str:
        heading_map = TECHNICAL_HEADINGS if is_technical else KNOWLEDGE_HEADINGS
        base = heading_map.get(fact_type, "Overview")
        if sub_term and sub_term.lower() not in {"additional", ""}:
            qualified = f"{base}: {sub_term}"
            if len(qualified) <= 60:
                return qualified
        if not facts:
            return base
        terms = BlueprintBuilder._extract_terms(facts)
        if not terms:
            return base
        primary = terms[0]
        generic = {"system", "model", "method", "approach", "study",
                   "research", "data", "information", "result",
                   "process", "analysis", "overview", "summary"}
        if primary.lower() not in generic:
            qualified = f"{base}: {primary}"
            if len(qualified) <= 60:
                return qualified
        return base

    @staticmethod
    def _extract_terms(facts: List[Fact]) -> List[str]:
        word_counts = Counter()
        for f in facts:
            for token in re.findall(r'[A-Za-z][a-zA-Z]{2,}', f.value):
                lower = token.lower()
                if lower not in STOPWORDS and len(lower) > 2:
                    word_counts[lower] += 1
        return [w for w, _ in word_counts.most_common(5) if word_counts[w] >= 2]
