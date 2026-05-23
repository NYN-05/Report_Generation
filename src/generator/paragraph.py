"""ParagraphGenerator — generates individual paragraphs with substantive templates."""

import random
from typing import List, Optional
from .base import BaseGenerator, GeneratorContext
from src.core.logger import get_logger

logger = get_logger(__name__)

_ANALYSIS_TEMPLATES = [
    "The analysis of {focus} within {topic} reveals several interacting dynamics that shape both "
    "current practices and future trajectories. A systematic examination of existing approaches "
    "shows that organizations must balance multiple competing priorities when addressing this area, "
    "including resource allocation, capability development, and strategic alignment with broader objectives.",
    "A multi-dimensional evaluation of {focus} in {topic} demonstrates that effectiveness depends on "
    "the interplay between technological infrastructure, organizational processes, and human expertise. "
    "Studies indicate that successful implementations typically achieve a coherent integration of these "
    "three dimensions rather than optimizing any single one in isolation.",
    "The landscape of {focus} in the context of {topic} continues to evolve rapidly, driven by "
    "advancements in both theoretical understanding and practical application. Key developments include "
    "the emergence of standardized frameworks, improved measurement methodologies, and growing evidence "
    "of what constitutes best practice across diverse operational contexts.",
]

_METHODOLOGY_TEMPLATES = [
    "The methodological approach to {focus} requires careful consideration of both quantitative and "
    "qualitative factors. Recent work has established that mixed-method frameworks offer the most "
    "comprehensive understanding, as they capture not only measurable outcomes but also the contextual "
    "factors that influence how {focus} manifests in real-world settings within {topic}.",
    "Implementing {focus} effectively demands a structured methodology that progresses from initial "
    "assessment through iterative refinement. Evidence from multiple case studies suggests that "
    "organizations benefit most from approaches that emphasize continuous feedback loops and adaptive "
    "management rather than rigid adherence to predetermined plans.",
]

_EVALUATION_TEMPLATES = [
    "Evaluating the impact of {focus} in {topic} requires metrics that capture both direct outcomes "
    "and indirect effects across related domains. Standard evaluation frameworks typically assess "
    "performance across dimensions of efficiency, effectiveness, and equity, though the relative "
    "importance of each dimension varies significantly by context and stakeholder perspective.",
    "A comprehensive assessment of {focus} reveals notable variations in outcomes across different "
    "implementation contexts. Factors such as organizational maturity, resource availability, and "
    "domain-specific expertise consistently emerge as significant moderators of success, suggesting "
    "that context-sensitive approaches to {focus} yield more reliable results than one-size-fits-all solutions.",
]

_IMPLICATION_TEMPLATES = [
    "The findings related to {focus} carry significant implications for practitioners working in "
    "{topic}. Organizations that proactively address the challenges identified in this analysis "
    "are better positioned to capitalize on emerging opportunities and mitigate potential risks "
    "associated with evolving industry standards and regulatory requirements.",
    "The broader implications of {focus} for {topic} extend beyond individual organizations to "
    "affect industry-wide practices and policy considerations. As the field matures, there is "
    "growing consensus around core principles that should guide decision-making in this area, "
    "though significant debates continue regarding optimal implementation strategies.",
]


class ParagraphGenerator(BaseGenerator):
    """Generates individual paragraphs with substantive, role-aware content."""

    def __init__(self, provider=None):
        super().__init__("paragraph")
        self._provider = provider

    def generate(self, context: GeneratorContext, **kwargs) -> str:
        focus = kwargs.get("focus", context.topic)
        index = kwargs.get("index", 0)
        role = kwargs.get("role", "analysis")

        if self._provider and self._provider.is_available():
            return self._generate_with_llm(context, focus, role)

        templates = self._pick_templates(role)
        template = templates[index % len(templates)]
        paragraph = template.format(topic=context.topic, focus=focus)

        if context.retrieval_context:
            evidence = self._extract_evidence(context.retrieval_context, focus)
            if evidence:
                paragraph += f" {evidence}"

        return paragraph

    def _generate_with_llm(self, context: GeneratorContext, focus: str,
                            role: str) -> str:
        from src.providers import Message, CompletionOptions
        try:
            prompt = (
                f"Write one formal academic paragraph about '{focus}' in the context of "
                f"{context.topic}. The paragraph should focus on the {role} aspect: "
                f"examine evidence, identify key patterns, or discuss implications.\n\n"
                f"Write 3-6 substantive sentences with specific claims, not generic filler."
            )
            if context.retrieval_context:
                prompt += f"\n\nReference Material:\n{context.retrieval_context[:2000]}"

            messages = [
                Message(role="system", content="You are an academic report writer."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.7, max_tokens=512, timeout=60)
            response = self._provider.chat(messages, options=opts)
            return response.content.strip()
        except Exception as e:
            logger.warning(f"LLM paragraph generation failed: {e}")
            templates = self._pick_templates(role)
            template = templates[0]
            return template.format(topic=context.topic, focus=focus)

    @staticmethod
    def _pick_templates(role: str) -> List[str]:
        role_map = {
            "analysis": _ANALYSIS_TEMPLATES,
            "methodology": _METHODOLOGY_TEMPLATES,
            "evaluation": _EVALUATION_TEMPLATES,
            "implication": _IMPLICATION_TEMPLATES,
        }
        return role_map.get(role, _ANALYSIS_TEMPLATES)

    def _extract_evidence(self, context_text: str, focus: str) -> str:
        lines = [l.strip() for l in context_text.split("\n") if l.strip()]
        relevant = [l for l in lines if focus.lower() in l.lower() or any(
            w in l.lower() for w in focus.lower().split()[:3]
        )]
        if relevant:
            return f"According to source material: {relevant[0][:300]}"
        return ""
