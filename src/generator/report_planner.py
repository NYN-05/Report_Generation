from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import Counter, defaultdict
import re
import json
from src.core.logger import get_logger
from src.facts.models import Fact, FactType
from src.facts.store import FactStore
from src.quality.unified_score import compute_pre_generation_score

logger = get_logger(__name__)

PLANNER_STOPWORDS = {
    "the", "and", "this", "that", "these", "those", "its", "are", "was",
    "were", "been", "have", "has", "had", "will", "would", "can", "could",
    "may", "might", "shall", "should", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "also", "because", "as",
    "until", "while", "for", "with", "from", "to", "of", "in", "on", "at",
    "by", "is", "be", "section", "includes", "including", "related",
}


@dataclass
class SectionPlan:
    heading: str
    description: str
    facts: List[Fact] = field(default_factory=list)
    expected_fact_types: List[str] = field(default_factory=list)
    unified_score: float = 0.0
    meets_threshold: bool = False
    pruning_reason: str = ""


@dataclass
class ReportPlan:
    topic: str
    domain: str
    report_type: str
    report_goal: str
    sections: List[SectionPlan] = field(default_factory=list)

    @property
    def total_facts(self) -> int:
        return sum(len(s.facts) for s in self.sections)

    @property
    def utilized_facts(self) -> int:
        return len(set(
            f.fact_id for s in self.sections for f in s.facts
        ))

    @property
    def utilization_rate(self) -> float:
        if not self.total_facts:
            return 0.0
        return round(self.utilized_facts / max(self.total_facts, 1), 3)


class ReportPlanner:
    REPORT_TYPE_PROMPTS = {
        "knowledge_topic": (
            "Educational overview of a subject. "
            "Sections should cover: fundamentals, key concepts, components, "
            "functions, applications, and future directions."
        ),
        "research_paper": (
            "Academic research paper. "
            "Sections should cover: abstract, literature review, methodology, "
            "experimental setup, results, discussion, conclusion."
        ),
        "project_report": (
            "Technical project documentation. "
            "Sections should cover: introduction, requirements, architecture, "
            "implementation, testing, results, conclusion."
        ),
        "business_report": (
            "Business or strategic analysis. "
            "Sections should cover: executive summary, market analysis, "
            "strategy, implementation plan, risks, recommendations."
        ),
    }

    def __init__(self, fact_store: FactStore, provider=None):
        self._store = fact_store
        self._provider = provider

    def plan(self, topic: str, min_facts: int = 3) -> ReportPlan:
        all_facts = self._store.get_verified_facts()
        if not all_facts:
            all_facts = self._store.get_all_facts()
        if not all_facts:
            return ReportPlan(topic=topic, domain="", report_type="", report_goal="")

        llm_plan = self._llm_design_plan(topic, all_facts)
        if not llm_plan:
            return self._fallback_plan(topic, all_facts)

        domain = llm_plan.get("domain", "General")
        report_type = llm_plan.get("report_type", "knowledge_topic")
        report_goal = llm_plan.get("report_goal", "")
        sections_data = llm_plan.get("sections", [])

        if not sections_data:
            return self._fallback_plan(topic, all_facts)

        sections = []
        for i, sd in enumerate(sections_data):
            heading = sd.get("heading", f"Section {i+1}")
            description = sd.get("description", "")
            expected_types = sd.get("expected_fact_types", [])
            assigned = self._assign_facts_to_section(
                heading, description, expected_types, all_facts, sections
            )
            already_used = set()
            for s in sections:
                for f in s.facts:
                    already_used.add(f.fact_id)
            assigned = [f for f in assigned if f.fact_id not in already_used]

            score = compute_pre_generation_score(assigned)
            meets = len(assigned) >= min_facts
            reason = "" if meets else f"Only {len(assigned)} facts (minimum {min_facts})"

            sections.append(SectionPlan(
                heading=heading,
                description=description,
                facts=assigned,
                expected_fact_types=expected_types,
                unified_score=score,
                meets_threshold=meets,
                pruning_reason=reason,
            ))

        report_plan = ReportPlan(
            topic=topic,
            domain=domain,
            report_type=report_type,
            report_goal=report_goal,
            sections=sections,
        )

        total = len(all_facts)
        used = report_plan.utilized_facts
        pruned = sum(1 for s in sections if not s.meets_threshold)
        logger.info(
            f"ReportPlan: {len(sections)} sections, "
            f"{used}/{total} facts utilized, "
            f"{pruned} below threshold, "
            f"type={report_type}, domain={domain}"
        )
        return report_plan

    def _llm_design_plan(self, topic: str, facts: List[Fact]) -> Optional[Dict]:
        if not self._provider or not self._provider.is_available():
            return None

        type_counts = Counter(f.fact_type.value for f in facts)
        type_summary = ", ".join(f"{k}={v}" for k, v in sorted(type_counts.items()))
        samples = []
        for ft in sorted(type_counts, key=lambda t: -type_counts[t]):
            matching = [f for f in facts if f.fact_type.value == ft]
            for f in matching[:3]:
                samples.append(f"  [{ft}] {f.value[:150]}")

        prompt = self._build_planning_prompt(topic, type_summary, samples)
        raw = self._call_llm(prompt)
        if not raw:
            return None
        return self._parse_plan(raw)

    def _build_planning_prompt(self, topic: str,
                                type_summary: str,
                                samples: List[str]) -> str:
        lines = [
            "You are a report planning expert. Analyze this topic and design a report structure.",
            "",
            f"TOPIC: {topic}",
            "",
            "AVAILABLE FACT TYPES:",
            f"  {type_summary}",
            "",
            "KEY FACTS:",
        ]
        lines.extend(samples[:15])
        lines.extend([
            "",
            "First, determine the report characteristics:",
            "  - domain (e.g., Neuroscience, Computer Science, Climate Science, Medicine)",
            "  - report_type: one of knowledge_topic, research_paper, project_report, business_report",
            "  - report_goal: one sentence describing what this report should accomplish",
            "",
            "Then design 4-8 sections. Each section MUST have:",
            "  - A specific, topic-relevant heading (not generic like 'Background')",
            "  - A one-sentence description of what this section covers",
            "  - expected_fact_types (which fact types belong here)",
            "",
            "IMPORTANT:",
            "  - Only create sections that the available facts can support",
            "  - Section headings must be directly relevant to the topic",
            "  - Do NOT include sections about Methodology, Dataset, or Metrics for",
            "    knowledge topics like Human Brain, Cloud Computing, etc.",
            "  - For knowledge topics, use: Introduction, Fundamentals, Key Concepts,",
            "    Structure, Functions, Applications, Recent Developments, Conclusion",
            "",
            "Return ONLY valid JSON with this structure:",
            "{",
            '  "domain": "string",',
            '  "report_type": "knowledge_topic|research_paper|project_report|business_report",',
            '  "report_goal": "string",',
            '  "sections": [',
            '    {',
            '      "heading": "string",',
            '      "description": "string",',
            '      "expected_fact_types": ["string"]',
            '    }',
            "  ]",
            "}",
            "",
            "JSON:",
        ])
        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        try:
            from src.providers.base import CompletionOptions, Message
            messages = [
                Message(
                    role="system",
                    content="You are a report planning expert. "
                            "Output only valid JSON. No explanations."
                ),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.2, max_tokens=2048, timeout=60)
            response = self._provider.chat(messages, options=opts)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Report planning LLM call failed: {e}")
            return ""

    def _parse_plan(self, raw: str) -> Optional[Dict]:
        try:
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)
            parsed = json.loads(raw)
            sections = parsed.get("sections", [])
            if not sections:
                logger.warning("LLM returned plan with no sections")
                return None
            for s in sections:
                if not s.get("heading") or not s.get("description"):
                    logger.warning(f"Section missing heading/description: {s}")
                    return None
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM plan: {e}")
            return None

    def _assign_facts_to_section(
        self,
        heading: str,
        description: str,
        expected_types: List[str],
        all_facts: List[Fact],
        existing_sections: List[SectionPlan],
    ) -> List[Fact]:
        search_text = (heading + " " + description).lower()
        heading_words = {
            w for w in re.findall(r'[a-z]{4,}', search_text)
            if w not in PLANNER_STOPWORDS
        }
        scored = []
        for f in all_facts:
            score = 0.0
            f_text = (f.value + " " + " ".join(f.concepts)).lower()
            fact_words = {
                w for w in re.findall(r'[a-z]{4,}', f_text)
                if w not in PLANNER_STOPWORDS
            }

            overlap = heading_words & fact_words
            if overlap:
                score += min(len(overlap) * 0.25, 1.0)

            if expected_types and f.fact_type.value in expected_types:
                score += 0.3

            for concept in f.concepts:
                if concept.lower() in search_text:
                    score += 0.2

            if score > 0.05:
                scored.append((score, f))

        scored.sort(key=lambda x: -x[0])
        return [f for _, f in scored[:20]]

    def _fallback_plan(self, topic: str, facts: List[Fact]) -> ReportPlan:
        from src.generator.blueprint_builder import BlueprintBuilder
        builder = BlueprintBuilder(self._store)
        blueprint = builder.build(topic, min_facts=3)
        sections = []
        for bs in blueprint:
            sections.append(SectionPlan(
                heading=bs.heading,
                description="",
                facts=bs.facts,
                expected_fact_types=[],
                unified_score=bs.unified_score,
                meets_threshold=bs.meets_threshold,
                pruning_reason=bs.pruning_reason,
            ))
        return ReportPlan(
            topic=topic,
            domain="General",
            report_type="knowledge_topic",
            report_goal=f"Report on {topic}",
            sections=sections,
        )
