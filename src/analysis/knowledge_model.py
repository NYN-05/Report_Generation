"""KnowledgeModel — LLM-driven analysis + exhaustive assignment of ALL facts to clusters."""

from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from collections import Counter, defaultdict
import re
import json
from src.core.logger import get_logger
from src.facts.models import Fact, FactType
from src.facts.store import FactStore

logger = get_logger(__name__)


@dataclass
class ConceptCluster:
    name: str
    description: str
    facts: List[Fact] = field(default_factory=list)
    sub_themes: List[str] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)

    @property
    def fact_count(self) -> int:
        return len(self.facts)

    @property
    def confidence(self) -> float:
        if not self.facts:
            return 0.0
        return sum(f.confidence for f in self.facts) / len(self.facts)


@dataclass
class KnowledgeModel:
    topic: str
    domain: str
    sub_domains: List[str] = field(default_factory=list)
    report_type: str = "knowledge_report"
    report_goal: str = ""
    audience: str = "general"
    total_facts: int = 0
    clusters: List[ConceptCluster] = field(default_factory=list)

    @property
    def utilized_facts(self) -> int:
        return len(set(
            f.fact_id for c in self.clusters for f in c.facts
        ))

    @property
    def utilization_rate(self) -> float:
        if not self.total_facts:
            return 0.0
        return round(self.utilized_facts / self.total_facts, 4)

    def summary(self) -> Dict:
        return {
            "domain": self.domain,
            "report_type": self.report_type,
            "total_clusters": len(self.clusters),
            "total_facts": self.total_facts,
            "utilized_facts": self.utilized_facts,
            "utilization_rate": self.utilization_rate,
            "clusters": [
                {"name": c.name, "fact_count": c.fact_count}
                for c in self.clusters
            ],
        }


class KnowledgeAnalyzer:
    def __init__(self, fact_store: FactStore, provider=None):
        self._store = fact_store
        self._provider = provider

    def analyze(self, topic: str) -> KnowledgeModel:
        all_facts = self._store.get_verified_facts()
        if not all_facts:
            all_facts = self._store.get_all_facts()
        if not all_facts:
            return KnowledgeModel(topic=topic, domain="", total_facts=0)

        total = len(all_facts)
        cluster_defs = self._discover_clusters(topic, all_facts)

        if not cluster_defs:
            return self._fallback_model(topic, all_facts)

        domain = cluster_defs.get("domain", "General")
        sub_domains = cluster_defs.get("sub_domains", [])
        report_type = cluster_defs.get("report_type", "knowledge_report")
        report_goal = cluster_defs.get("report_goal", f"Report on {topic}")
        audience = cluster_defs.get("audience", "general")
        raw_clusters = cluster_defs.get("clusters", [])

        if not raw_clusters:
            return self._fallback_model(topic, all_facts)

        clusters = []
        assignments = self._exhaustive_assign(all_facts, raw_clusters)

        for rc in raw_clusters:
            cname = rc.get("name", "Unnamed")
            cdesc = rc.get("description", "")
            sub_themes = rc.get("sub_themes", [])
            assigned = assignments.get(cname, [])
            findings = self._generate_findings(cname, assigned)
            clusters.append(ConceptCluster(
                name=cname,
                description=cdesc,
                facts=assigned,
                sub_themes=sub_themes,
                key_findings=findings,
            ))

        assigned_ids = {f.fact_id for c in clusters for f in c.facts}
        unassigned = [f for f in all_facts if f.fact_id not in assigned_ids]
        if unassigned:
            clusters.append(ConceptCluster(
                name="Additional Context",
                description="Supplementary information",
                facts=unassigned,
            ))

        return KnowledgeModel(
            topic=topic,
            domain=domain,
            sub_domains=sub_domains,
            report_type=report_type,
            report_goal=report_goal,
            audience=audience,
            total_facts=total,
            clusters=clusters,
        )

    def _exhaustive_assign(
        self,
        all_facts: List[Fact],
        raw_clusters: List[Dict],
    ) -> Dict[str, List[Fact]]:
        cluster_queries = {}
        for rc in raw_clusters:
            cname = rc.get("name", "")
            cdesc = rc.get("description", "")
            keywords = rc.get("keywords", [])
            sub_themes = rc.get("sub_themes", [])

            query_terms = set()
            for t in [cname, cdesc] + keywords + sub_themes:
                for w in re.split(r'[\s\-_/:,;.()\[\]{}]+', t.lower()):
                    w = w.strip("'\".,;:!?")
                    if len(w) > 2 and w not in _STOP:
                        query_terms.add(w)
            cluster_queries[cname] = query_terms

        assignments: Dict[str, List[Fact]] = {rc["name"]: [] for rc in raw_clusters}
        zero_score: List[Fact] = []

        for f in all_facts:
            f_text = (f.value + " " + " ".join(f.concepts)).lower()
            f_words = {
                w.strip("'\".,;:!?")
                for w in re.split(r'[\s\-_/:,;.()\[\]{}]+', f_text)
                if len(w) > 2 and w not in _STOP
            }

            best_cluster = None
            best_score = 0

            for rc in raw_clusters:
                cname = rc["name"]
                terms = cluster_queries[cname]
                if not terms:
                    continue

                overlap = f_words & terms
                if not overlap:
                    continue

                score = sum(len(t) for t in overlap)
                if cname.lower() in f_text:
                    score += 10
                for concept in f.concepts:
                    if concept.lower() in " ".join(terms):
                        score += 5

                if score > best_score:
                    best_score = score
                    best_cluster = cname

            if best_cluster:
                assignments[best_cluster].append(f)
            else:
                zero_score.append(f)

        for f in zero_score:
            best_cluster = None
            best_score = 0
            f_text = (f.value + " " + " ".join(f.concepts)).lower()

            for rc in raw_clusters:
                cname = rc["name"]
                cname_words = cname.lower().split()
                cdesc = rc.get("description", "").lower()
                score = 0
                for w in cname_words:
                    if len(w) > 2 and w in f_text:
                        score += 3
                for w in cdesc.split():
                    if len(w) > 3 and w in f_text:
                        score += 1
                if score > best_score:
                    best_score = score
                    best_cluster = cname

            if best_cluster:
                assignments[best_cluster].append(f)
            else:
                cname = raw_clusters[0]["name"]
                assignments[cname].append(f)

        return assignments

    def _generate_findings(self, cluster_name: str, facts: List[Fact]) -> List[str]:
        if not facts:
            return []
        fact_types = Counter(f.fact_type.value for f in facts)
        top_types = [t for t, _ in fact_types.most_common(3)]
        sources = {f.source.file_name for f in facts if f.source.file_name}
        confidence = sum(f.confidence for f in facts) / len(facts)
        return [
            f"Based on {len(facts)} facts from {len(sources)} sources",
            f"Types: {', '.join(top_types)}",
            f"Avg confidence: {confidence:.0%}",
        ]

    def _discover_clusters(self, topic: str, facts: List[Fact]) -> Optional[Dict]:
        if not self._provider or not self._provider.is_available():
            return None

        type_counts = Counter(f.fact_type.value for f in facts)
        type_summary = ", ".join(f"{k}={v}" for k, v in sorted(type_counts.items()))

        sample_size = min(60, len(facts))
        step = max(1, len(facts) // sample_size)
        samples = facts[::step][:sample_size]

        from src.providers.base import CompletionOptions, Message

        prompt_lines = [
            "You are a knowledge analysis expert. Analyze these facts about a topic.",
            "",
            f"TOPIC: {topic}",
            f"FACT TYPES: {type_summary}",
            f"TOTAL FACTS: {len(facts)}",
            "",
            "FACT SAMPLES:",
        ]
        for i, f in enumerate(samples):
            prompt_lines.append(f"  [{f.fact_type.value}] {f.value[:200]}")

        prompt_lines.extend([
            "",
            "Return ONLY valid JSON:",
            "{",
            '  "domain": "primary domain",',
            '  "sub_domains": [...],',
            '  "report_type": "knowledge_report | technical_documentation | research_survey | comparative_analysis | project_report",',
            '  "report_goal": "one sentence",',
            '  "audience": "target audience",',
            '  "clusters": [',
            "    {",
            '      "name": "section heading",',
            '      "description": "what this covers",',
            '      "keywords": ["relevant", "terms", "from", "facts"],',
            '      "sub_themes": ["subtopic1", "subtopic2"]',
            "    }",
            "  ]",
            "}",
            "RULES:",
            "- 4-10 clusters covering ALL key topics in the facts",
            "- keywords must include words that appear IN the actual facts",
            "- Cluster names must be topic-specific headings",
            "- Return ONLY valid JSON, no explanations.",
        ])
        prompt = "\n".join(prompt_lines)

        try:
            messages = [
                Message(role="system", content="You are a knowledge analysis expert. Output only valid JSON."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.2, max_tokens=4096, timeout=120)
            response = self._provider.chat(messages, options=opts)
            raw = response.content.strip()
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)
            parsed = json.loads(raw)
            if parsed.get("clusters"):
                return parsed
            return None
        except Exception as e:
            logger.warning(f"Knowledge analysis failed: {e}")
            return None

    def _fallback_model(self, topic: str, facts: List[Fact]) -> KnowledgeModel:
        type_groups = defaultdict(list)
        for f in facts:
            type_groups[f.fact_type].append(f)

        clusters = []
        assigned: Set[str] = set()
        type_map = {
            FactType.OBJECTIVE: ("Overview", "Core objectives"),
            FactType.GENERAL: ("Fundamental Concepts", "Foundational knowledge"),
            FactType.ARCHITECTURE: ("Architecture", "Structural organization"),
            FactType.METHODOLOGY: ("Methods", "Approaches used"),
            FactType.TECHNOLOGY: ("Technologies", "Tools involved"),
            FactType.RESULT: ("Key Results", "Outcomes"),
            FactType.DATASET: ("Data", "Datasets available"),
            FactType.ALGORITHM: ("Algorithms", "Computational techniques"),
            FactType.METRIC: ("Metrics", "Evaluation criteria"),
            FactType.CITATION: ("References", "Related work"),
            FactType.REQUIREMENT: ("Requirements", "Constraints"),
            FactType.PROBLEM: ("Challenges", "Open questions"),
            FactType.MODULE: ("Components", "System modules"),
        }
        for ft, ft_facts in type_groups.items():
            sname, sdesc = type_map.get(ft, (ft.value.title(), ""))
            available = [f for f in ft_facts if f.fact_id not in assigned]
            if not available:
                continue
            assigned.update(f.fact_id for f in available)
            clusters.append(ConceptCluster(name=sname, description=sdesc, facts=available))

        return KnowledgeModel(
            topic=topic, domain="General", report_type="knowledge_report",
            total_facts=len(facts), clusters=clusters,
        )


_STOP = {
    "the", "and", "for", "are", "was", "were", "been", "have", "has", "had",
    "will", "would", "can", "could", "may", "might", "shall", "should",
    "about", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "also", "because", "as", "until", "while", "for", "with", "from", "to",
    "of", "in", "on", "at", "by", "is", "be", "this", "that", "these", "those",
    "its", "but", "or", "if", "do", "done", "doing", "does", "did", "has",
    "have", "having", "had", "get", "got", "getting", "use", "used", "using",
    "make", "made", "making", "take", "took", "taking", "see", "seen",
    "seeing", "know", "knew", "known", "think", "thought", "thinking",
    "give", "gave", "given", "find", "found", "finding", "tell", "told",
    "become", "became", "leave", "left", "put", "putting", "bring", "brought",
    "set", "setting", "study", "studies", "studied", "shows", "shown",
    "showing", "include", "includes", "including", "related", "based",
    "called", "known", "referred", "regarded", "considered", "describe",
    "described", "such", "also", "well", "within", "without", "across",
    "among", "along", "around", "down", "up", "back", "still", "already",
    "yet", "away", "off", "much", "many",
}
