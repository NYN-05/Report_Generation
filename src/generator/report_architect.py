"""ReportArchitect — designs report structure from a KnowledgeModel.

Replaces ReportPlanner. Sections emerge from semantic clusters rather than
keyword matching against template headings.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import json
import re
from src.core.logger import get_logger
from src.facts.models import Fact
from src.facts.store import FactStore
from src.analysis.knowledge_model import KnowledgeModel, ConceptCluster, KnowledgeAnalyzer
from src.quality.unified_score import compute_pre_generation_score

logger = get_logger(__name__)


@dataclass
class SectionPlan:
    heading: str
    description: str
    facts: List[Fact] = field(default_factory=list)
    sub_themes: List[str] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)
    unified_score: float = 0.0
    meets_threshold: bool = False
    pruning_reason: str = ""
    is_appendices: bool = False


@dataclass
class ReportPlan:
    topic: str
    domain: str
    report_type: str
    report_goal: str
    audience: str
    sections: List[SectionPlan] = field(default_factory=list)
    executive_summary: str = ""
    total_facts_available: int = 0
    total_facts_assigned: int = 0

    @property
    def utilized_facts(self) -> int:
        return self.total_facts_assigned

    @property
    def utilization_rate(self) -> float:
        if not self.total_facts_available:
            return 0.0
        return round(self.utilized_facts / self.total_facts_available, 4)

    @property
    def active_sections(self) -> List[SectionPlan]:
        return [s for s in self.sections if s.meets_threshold and not s.is_appendices]


class ReportArchitect:
    """Designs report structure from a KnowledgeModel.

    Takes the semantic clusters discovered by KnowledgeAnalyzer and
    converts them into sections. Adds cross-cutting sections like
    executive summary and appendices.
    """

    def __init__(self, fact_store: FactStore, knowledge_model: KnowledgeModel, provider=None):
        self._store = fact_store
        self._model = knowledge_model
        self._provider = provider

    def design(self, min_facts: int = 3,
               gen_facts_per_section: int = 60) -> ReportPlan:
        model = self._model
        if not model.clusters:
            return ReportPlan(
                topic=model.topic,
                domain=model.domain,
                report_type=model.report_type,
                report_goal=model.report_goal,
                audience=model.audience,
                total_facts_available=model.total_facts,
            )

        sections = []
        all_assigned: set = set()
        for cluster in model.clusters:
            sub_sections = self._split_cluster(cluster, gen_facts_per_section)
            for sub_idx, (sub_name, sub_facts) in enumerate(sub_sections):
                gen_facts = sub_facts[:gen_facts_per_section]
                score = compute_pre_generation_score(gen_facts)
                meets = len(gen_facts) >= min_facts
                reason = "" if meets else f"Only {len(gen_facts)} facts (minimum {min_facts})"

                sub_themes = cluster.sub_themes
                if sub_idx > 0 and len(cluster.sub_themes) > sub_idx:
                    sub_themes = [cluster.sub_themes[sub_idx]]

                sections.append(SectionPlan(
                    heading=sub_name,
                    description=cluster.description,
                    facts=gen_facts,
                    sub_themes=sub_themes,
                    key_findings=cluster.key_findings,
                    unified_score=score,
                    meets_threshold=meets,
                    pruning_reason=reason,
                ))
                all_assigned.update(f.fact_id for f in gen_facts)

        exec_summary = self._generate_executive_summary(model, sections)

        total_assigned = len(set(
            f.fact_id for c in model.clusters for f in c.facts
        ))

        report_plan = ReportPlan(
            topic=model.topic,
            domain=model.domain,
            report_type=model.report_type,
            report_goal=model.report_goal,
            audience=model.audience,
            sections=sections,
            executive_summary=exec_summary,
            total_facts_available=model.total_facts,
            total_facts_assigned=total_assigned,
        )

        logger.info(
            f"ReportArchitect: {len(sections)} sections, "
            f"{report_plan.utilized_facts}/{model.total_facts} facts utilized "
            f"({report_plan.utilization_rate:.1%}), type={model.report_type}"
        )
        return report_plan

    def _split_cluster(self, cluster: ConceptCluster,
                       cap: int) -> List[Tuple[str, List[Fact]]]:
        if not cluster.facts:
            return [(cluster.name, [])]
        if len(cluster.facts) <= cap:
            return [(cluster.name, cluster.facts)]

        groups = []
        sub_themes = cluster.sub_themes if cluster.sub_themes else []
        for i in range(0, len(cluster.facts), cap):
            chunk = cluster.facts[i:i + cap]
            group_idx = i // cap

            if group_idx == 0:
                name = cluster.name
            elif sub_themes and group_idx <= len(sub_themes):
                name = f"{cluster.name} \u2013 {sub_themes[group_idx - 1]}"
            else:
                name = f"{cluster.name} \u2013 Part {group_idx + 1}"

            groups.append((name, chunk))

        return groups

    def _generate_executive_summary(self, model: KnowledgeModel,
                                     sections: List[SectionPlan]) -> str:
        if not self._provider or not self._provider.is_available():
            active = [s for s in sections if s.meets_threshold]
            summary = (
                f"This report examines {model.topic} across "
                f"{len(active)} key areas. "
                f"Based on {model.total_facts} facts from the available evidence, "
                f"it covers {', '.join(s.heading for s in active[:5])}."
            )
            return summary

        cluster_summaries = []
        for c in model.clusters[:7]:
            cluster_summaries.append(
                f"  - {c.name}: {c.description} ({len(c.facts)} facts)"
            )

        from src.providers.base import CompletionOptions, Message
        prompt = (
            f"Write a 2-3 sentence executive summary for a report on: {model.topic}\n\n"
            f"Domain: {model.domain}\n"
            f"Report Type: {model.report_type}\n"
            f"Report Goal: {model.report_goal}\n"
            f"Audience: {model.audience}\n\n"
            f"Sections based on available evidence:\n"
            + "\n".join(cluster_summaries) +
            "\n\nWrite a concise, professional executive summary. "
            "No markdown. No filler. Third person."
        )
        try:
            messages = [
                Message(role="system", content="You are a professional report writer. Write concisely and factually."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.3, max_tokens=512, timeout=60)
            response = self._provider.chat(messages, options=opts)
            return response.content.strip()
        except Exception as e:
            logger.warning(f"Executive summary generation failed: {e}")
            return f"This report presents a comprehensive analysis of {model.topic} based on available evidence."
