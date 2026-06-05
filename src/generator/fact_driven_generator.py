from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger
from src.facts.models import Fact
from src.facts.store import FactStore
from src.generator.content_blocks import SectionContent, ParagraphBlock, SourceRequiredBlock, HeadingBlock
from src.quality.unified_score import compute_pre_generation_score

logger = get_logger(__name__)


class FactDrivenGenerator:
    def __init__(self, fact_store: FactStore, provider=None):
        self._fact_store = fact_store
        self._provider = provider

    def generate_section(self, section_type: str, heading: str, facts: List[Fact], topic: str) -> SectionContent:
        section = SectionContent(heading=heading)
        section.add_block(HeadingBlock(text=heading, level=1))

        if not facts:
            section.add_block(SourceRequiredBlock(
                query=section_type,
                message=f"Insufficient source material available for this claim. No evidence found for {heading}."
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
                section.add_block(ParagraphBlock(text=f.value, word_count=len(f.value.split()), evidence_source=f.source.file_name))
            return section

        prompt = self._build_fact_prompt(section_type, heading, facts, pre_score, topic)
        raw = self._call_llm(prompt)
        if not raw:
            for f in facts:
                section.add_block(ParagraphBlock(text=f.value, word_count=len(f.value.split()), evidence_source=f.source.file_name))
            return section

        self._parse_into_section(section, raw, facts, section_type)
        return section

    def _build_fact_prompt(self, section_type: str, heading: str, facts: List[Fact], score: float, topic: str) -> str:
        n_facts = len(facts)
        if n_facts <= 1:
            max_paras = 1
        elif n_facts <= 3:
            max_paras = 2
        else:
            max_paras = min(4, n_facts)

        lines = [
            f"Generate the {heading} section for a report on: {topic}",
            "",
            "ABSOLUTE RULES (violation will invalidate the response):",
            "1. You MUST write EXACTLY 1 to {max_paras} paragraphs — no more than {max_paras}.",
            "2. Use ONLY the facts listed below. NEVER add external knowledge.",
            "3. Every sentence MUST reference a fact by its FACT NUMBER (FACT 1, FACT 2, etc.).",
            "4. NEVER generate: metrics, accuracy values, dataset names, algorithm names,",
            "   technology names, citations, architecture details, or results unless",
            "   they appear verbatim in a provided fact below.",
            "5. If the facts are insufficient for a complete paragraph,",
            "   write exactly: '[Insufficient source material available for this claim.]'",
            "   and NOTHING else for that paragraph.",
            "6. Academic tone, third-person, technical precision. No filler sentences.",
            "",
            f"AVAILABLE FACTS ({n_facts} total):",
        ]
        for i, f in enumerate(facts):
            source_info = f.source.file_name
            if f.source.page_number:
                source_info += f" (p.{f.source.page_number})"
            lines.append(f"  FACT {i+1} [{f.fact_type.value}] {f.value}")
            lines.append(f"         Source: {source_info}")
        lines.extend([
            "",
            "OUTPUT FORMAT:",
            "[Paragraph 1: topic sentence referencing FACT X. Supporting detail from FACT Y.]",
            "",
            "[Paragraph 2: ...]",
            "",
            "If no facts can support any paragraph, output ONLY:",
            "[Insufficient source material available for this claim.]",
        ])
        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        try:
            from src.providers.base import CompletionOptions, Message
            messages = [
                Message(role="system", content="You are a domain expert writing a technical report. Base every claim on provided facts. Never invent information."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.1, max_tokens=4096, timeout=180)
            response = self._provider.chat(messages, options=opts)
            return response.content.strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def _parse_into_section(self, section: SectionContent, raw: str, facts: List[Fact], section_type: str = ""):
        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
        for para in paragraphs:
            if "Insufficient source material" in para:
                section.add_block(SourceRequiredBlock(query=section_type, message=para))
                continue
            text = " ".join(para.splitlines()).strip()
            if len(text.split()) < 30:
                continue
            matched_facts = self._find_facts_in_text(text, facts)
            evidence_source = matched_facts[0].source.file_name if matched_facts else ""
            block = ParagraphBlock(
                text=text,
                word_count=len(text.split()),
                topic_sentence=text.split(".")[0] if "." in text else text[:80],
                evidence_source=evidence_source,
            )
            section.add_block(block)

    def _find_facts_in_text(self, text: str, facts: List[Fact]) -> List[Fact]:
        text_lower = text.lower()
        matched = []
        for f in facts:
            if f.normalized_value[:40] in text_lower:
                matched.append(f)
            elif any(c.lower() in text_lower for c in f.concepts):
                matched.append(f)
        return matched[:3]
