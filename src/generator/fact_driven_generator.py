"""SynthesisGenerator — cluster-level synthesis writing.

Instead of expanding individual facts into paragraphs, synthesizes
all facts in a cluster into coherent, expert-level prose.
"""

from typing import Dict, List, Optional, Tuple
from collections import Counter
from src.core.logger import get_logger
from src.facts.models import Fact
from src.facts.store import FactStore
from src.generator.content_blocks import (
    SectionContent, ParagraphBlock, SourceRequiredBlock,
    HeadingBlock, BulletListBlock, BulletItem, Citation,
)
from src.quality.unified_score import compute_pre_generation_score
from src.analysis.knowledge_model import ConceptCluster

logger = get_logger(__name__)


class SynthesisGenerator:
    def __init__(self, fact_store: FactStore, provider=None):
        self._store = fact_store
        self._provider = provider

    def generate_section(self, section_type: str, heading: str,
                          facts: List[Fact], topic: str,
                          sub_themes: Optional[List[str]] = None,
                          key_findings: Optional[List[str]] = None) -> SectionContent:
        section = SectionContent(heading=heading)
        section.add_block(HeadingBlock(text=heading, level=1))

        if not facts:
            section.add_block(SourceRequiredBlock(
                query=section_type,
                message=f"Insufficient source material available for {heading}."
            ))
            return section

        pre_score = compute_pre_generation_score(facts)
        if pre_score < 0.1:
            section.add_block(SourceRequiredBlock(
                query=section_type,
                message=f"Insufficient source material available for this section."
            ))
            return section

        if not self._provider or not self._provider.is_available():
            for f in facts:
                section.add_block(ParagraphBlock(
                    text=f.value,
                    word_count=len(f.value.split()),
                    evidence_source=f.source.file_name,
                ))
            return section

        prompt = self._build_synthesis_prompt(
            section_type, heading, facts, topic,
            sub_themes or [], key_findings or [],
            pre_score,
        )
        raw = self._call_llm(prompt)
        if not raw:
            for f in facts:
                section.add_block(ParagraphBlock(
                    text=f.value,
                    word_count=len(f.value.split()),
                    evidence_source=f.source.file_name,
                ))
            return section

        self._parse_into_section(section, raw, facts, section_type)
        return section

    def _build_synthesis_prompt(
        self, section_type: str, heading: str, facts: List[Fact],
        topic: str, sub_themes: List[str], key_findings: List[str],
        score: float,
    ) -> str:
        n_facts = len(facts)
        max_paras = min(max(2, n_facts // 3), 8)

        fact_types = Counter(f.fact_type.value for f in facts)
        type_dist = ", ".join(f"{k}={v}" for k, v in fact_types.most_common())

        lines = [
            f"Write the \"{heading}\" section of a report on: {topic}",
            "",
            "=== WRITING INSTRUCTIONS ===",
            "",
            "You are a domain expert. Write like one.",
            "",
            "Write {max_paras} paragraphs. Each paragraph must:",
            "- Start with a strong topic sentence",
            "- Synthesize MULTIPLE facts (not just repeat them one by one)",
            "- Explain, analyze, or interpret — do not just list",
            "- Reference facts naturally using [FACT X] citations",
            "- Stay strictly within the provided facts — NEVER invent information",
            "",
            f"FACT TYPE DISTRIBUTION: {type_dist}",
        ]

        if sub_themes:
            lines.extend([
                "",
                "SUB-THEMES to cover:",
            ] + [f"  - {st}" for st in sub_themes[:5]])

        if key_findings:
            lines.extend([
                "",
                "KEY FINDINGS:",
            ] + [f"  - {kf}" for kf in key_findings[:3]])

        lines.extend([
            "",
            f"AVAILABLE FACTS ({n_facts} total):",
        ])
        for i, f in enumerate(facts):
            lines.append(f"  FACT {i+1} [{f.fact_type.value}] {f.value}")

        lines.extend([
            "",
            "=== OUTPUT FORMAT ===",
            f"Write exactly {max_paras} paragraphs separated by blank lines.",
            "Every paragraph must reference at least 2 facts.",
            "Use natural integration — do not force citations.",
            "If facts are insufficient for a paragraph, write:",
            "[Insufficient source material available for this claim.]",
            "",
            "ACADEMIC TONE. THIRD PERSON. NO FILLER. NO REPETITION.",
        ])

        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        try:
            from src.providers.base import CompletionOptions, Message
            messages = [
                Message(
                    role="system",
                    content="You are a domain expert writing a technical report. "
                            "Synthesize facts into coherent analysis. "
                            "Never invent information. Always cite facts.",
                ),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.15, max_tokens=4096, timeout=180)
            response = self._provider.chat(messages, options=opts)
            return response.content.strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def _parse_into_section(self, section: SectionContent, raw: str,
                              facts: List[Fact], section_type: str = ""):
        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
        for para in paragraphs:
            if "Insufficient source material" in para:
                section.add_block(SourceRequiredBlock(
                    query=section_type, message=para
                ))
                continue

            text = " ".join(para.splitlines()).strip()
            if len(text.split()) < 30:
                continue

            matched = self._find_cited_facts(text, facts)
            evidence_source = (
                matched[0].source.file_name if matched else
                facts[0].source.file_name if facts else ""
            )

            citations = [
                Citation(source=f.source.file_name, reference=f.fact_id)
                for f in matched[:3]
            ]

            block = ParagraphBlock(
                text=text,
                word_count=len(text.split()),
                topic_sentence=text.split(".")[0] if "." in text else text[:80],
                evidence_source=evidence_source,
                citations=citations,
            )
            section.add_block(block)

    def _find_cited_facts(self, text: str, facts: List[Fact]) -> List[Fact]:
        text_lower = text.lower()
        matched = []
        for f in facts:
            pattern = f"fact {facts.index(f) + 1}"
            if f"fact {facts.index(f) + 1}" in text_lower:
                matched.append(f)
            elif f.normalized_value[:60].lower() in text_lower:
                matched.append(f)
        return matched[:5]

    def generate_key_findings_section(self, clusters: List[ConceptCluster],
                                       max_findings: int = 10) -> SectionContent:
        section = SectionContent(heading="Key Findings and Insights")
        section.add_block(HeadingBlock(text="Key Findings and Insights", level=1))

        all_findings = []
        for cluster in clusters:
            for i, f in enumerate(cluster.facts[:5]):
                all_findings.append((cluster.name, f))

        if not all_findings:
            section.add_block(ParagraphBlock(
                text="No significant findings available from the collected evidence.",
                word_count=10,
            ))
            return section

        items = []
        seen = set()
        for cname, f in all_findings[:max_findings]:
            if f.value[:100] in seen:
                continue
            seen.add(f.value[:100])
            items.append(BulletItem(
                title=f"Finding: {cname}",
                description=f.value[:300],
                evidence_source=f.source.file_name,
            ))

        section.add_block(BulletListBlock(
            title="Summary of Key Findings",
            items=items,
            lead_in=f"The following key findings emerged from analysis of {sum(len(c.facts) for c in clusters)} facts:",
        ))
        return section
