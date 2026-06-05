from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from src.core.logger import get_logger
from src.facts.models import Fact, FactType
from src.facts.store import FactStore
from src.generator.content_blocks import SectionContent, ParagraphBlock, SourceRequiredBlock, HeadingBlock

logger = get_logger(__name__)

EVIDENCE_SECTION_MAP: Dict[str, Dict] = {
    "introduction": {"required_types": [FactType.OBJECTIVE], "heading": "Introduction", "priority": 1},
    "methodology": {"required_types": [FactType.ALGORITHM, FactType.ARCHITECTURE], "heading": "Methodology", "priority": 2},
    "implementation": {"required_types": [FactType.TECHNOLOGY], "heading": "Implementation", "priority": 3},
    "experimental_setup": {"required_types": [FactType.DATASET, FactType.METRIC], "heading": "Experimental Setup", "priority": 4},
    "results": {"required_types": [FactType.RESULT, FactType.METRIC], "heading": "Results", "priority": 5},
    "discussion": {"required_types": [FactType.RESULT], "heading": "Discussion", "priority": 6},
    "related_work": {"required_types": [FactType.CITATION], "heading": "Related Work", "priority": 7},
    "conclusion": {"required_types": [FactType.OBJECTIVE, FactType.RESULT], "heading": "Conclusion", "priority": 8},
}


@dataclass
class SectionConfidence:
    section_type: str
    heading: str
    coverage: float
    confidence: float
    supporting_facts: int
    source_count: int
    generation_mode: str
    paragraphs: int = 0
    traced_paragraphs: int = 0


class FactDrivenGenerator:
    def __init__(self, fact_store: FactStore, provider=None):
        self._fact_store = fact_store
        self._provider = provider

    def build_blueprint(self, title: str) -> List[Dict]:
        all_facts = self._fact_store.get_all_facts()
        sections = []
        for stype, config in EVIDENCE_SECTION_MAP.items():
            matching = [f for f in all_facts if f.fact_type in config["required_types"]]
            if not matching:
                continue
            sections.append({
                "section_type": stype,
                "heading": config["heading"],
                "facts": matching,
                "priority": config["priority"],
                "required_types": [ft.value for ft in config["required_types"]],
            })
        sections.sort(key=lambda s: s["priority"])
        logger.info(f"Blueprint: {len(sections)} sections from evidence for '{title}'")
        return sections

    def generate_section(self, section_type: str, heading: str, facts: List[Fact], topic: str) -> SectionContent:
        section = SectionContent(heading=heading)
        section.add_block(HeadingBlock(text=heading, level=1))

        if not facts:
            section.add_block(SourceRequiredBlock(
                query=section_type,
                message=f"Insufficient source material available for this claim. No evidence found for {heading}."
            ))
            return section

        generation_mode = self._compute_mode(facts)

        if generation_mode == "not_possible":
            section.add_block(SourceRequiredBlock(
                query=section_type,
                message=f"Insufficient source material available for this section."
            ))
            return section

        if not self._provider or not self._provider.is_available():
            for f in facts:
                section.add_block(ParagraphBlock(text=f.value, word_count=len(f.value.split()), evidence_source=f.source.file_name))
            return section

        prompt = self._build_fact_prompt(section_type, heading, facts, generation_mode, topic)
        raw = self._call_llm(prompt)
        if not raw:
            for f in facts:
                section.add_block(ParagraphBlock(text=f.value, word_count=len(f.value.split()), evidence_source=f.source.file_name))
            return section

        self._parse_into_section(section, raw, facts, section_type)
        return section

    def _build_fact_prompt(self, section_type: str, heading: str, facts: List[Fact], mode: str, topic: str) -> str:
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

    def _compute_mode(self, facts: List[Fact]) -> str:
        if not facts:
            return "not_possible"
        avg_conf = sum(f.confidence for f in facts) / len(facts)
        type_diversity = min(len(set(f.fact_type for f in facts)) / 3.0, 1.0)
        score = avg_conf * 0.6 + type_diversity * 0.4
        if score >= 0.8:
            return "normal"
        elif score >= 0.5:
            return "cautious"
        elif score >= 0.1:
            return "insufficient_evidence"
        return "not_possible"

    def compute_confidence(self, section_type: str, facts: List[Fact], paragraphs: List[ParagraphBlock]) -> SectionConfidence:
        if not facts or not paragraphs:
            return SectionConfidence(
                section_type=section_type,
                heading=section_type.replace("_", " ").title(),
                coverage=0.0, confidence=0.0,
                supporting_facts=0, source_count=0,
                generation_mode=self._compute_mode(facts),
            )
        traced = 0
        fact_ids_used = set()
        sources_used = set()
        for p in paragraphs:
            matched = self._find_facts_in_text(p.text, facts)
            if matched:
                traced += 1
                for m in matched:
                    fact_ids_used.add(m.fact_id)
                    sources_used.add(m.source.file_name)
        coverage = traced / len(paragraphs) if paragraphs else 0.0
        avg_conf = sum(f.confidence for f in facts) / len(facts) if facts else 0.0
        return SectionConfidence(
            section_type=section_type,
            heading=section_type.replace("_", " ").title(),
            coverage=round(coverage, 3),
            confidence=round(avg_conf, 3),
            supporting_facts=len(fact_ids_used),
            source_count=len(sources_used),
            generation_mode=self._compute_mode(facts),
            paragraphs=len(paragraphs),
            traced_paragraphs=traced,
        )
