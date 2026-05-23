"""FactDrivenParagraphGenerator — generates paragraphs from extracted facts, not from topic.

Workflow: Evidence → Facts → Explanation → Analysis → Paragraph
"""

from typing import Dict, List, Optional
from src.core.logger import get_logger
from src.research.fact_extractor import AtomicFact

logger = get_logger(__name__)


class FactDrivenParagraphGenerator:

    def build_fact_context(self, facts: List[AtomicFact],
                           section_type: str) -> str:
        if not facts:
            return "[NO FACTS AVAILABLE]"

        parts = ["EXTRACTED FACTS (use these as the sole source of claims):\n"]
        for i, fact in enumerate(facts, 1):
            parts.append(
                f"FACT {i} [confidence: {fact.confidence}, "
                f"category: {fact.category}]"
            )
            parts.append(f"  Statement: {fact.text}")
            if fact.concepts:
                parts.append(f"  Concepts: {', '.join(fact.concepts[:5])}")
            if fact.source_meta:
                source = fact.source_meta.get("source", "unknown")
                parts.append(f"  Source: {source}")
            parts.append("")

        return "\n".join(parts)

    def build_evidence_section_prompt(self, section_type: str, topic: str,
                                       facts: List[AtomicFact],
                                       evidence_map: Dict,
                                       citations: List,
                                       context_text: str) -> str:
        parts = [
            "=" * 60,
            f"GENERATE: {section_type.replace('_', ' ').upper()}",
            "=" * 60,
            "",
            "CRITICAL INSTRUCTION: Every paragraph MUST originate from the extracted facts below.",
            "Do NOT write generic descriptions. Do NOT topic-expand.",
            "Each paragraph workflow: Fact → Explanation → Analysis → Next fact.",
            "",
            "AVAILABLE FACTS (structured evidence):",
            self.build_fact_context(facts, section_type),
        ]

        if evidence_map:
            parts.extend([
                "",
                "CLAIM-EVIDENCE MAP (which facts support which claims):",
            ])
            for claim, mapped_facts in evidence_map.items():
                if isinstance(claim, str) and isinstance(mapped_facts, list):
                    parts.append(f"  Claim: {claim[:100]}")
                    for mf in mapped_facts[:3]:
                        parts.append(f"    → Fact: {str(mf)[:80]}")
                    parts.append("")

        if citations:
            parts.extend([
                "",
                "STRUCTURED CITATIONS (map to [1], [2], etc.):",
            ])
            for i, cit in enumerate(citations, 1):
                parts.append(f"  [{i}] {str(cit)[:120]}")
            parts.append("")
            parts.append(
                "Use these citation numbers [1], [2] etc. when referencing evidence."
            )

        if context_text:
            parts.extend([
                "",
                "RAW RETRIEVED TEXT (supplementary):",
                context_text[:2000],
            ])

        parts.extend([
            "",
            "=" * 60,
            "WRITING CONSTRAINTS",
            "=" * 60,
            "1. Every paragraph must cite at least one Fact by number (FACT 1, FACT 2, etc.)",
            "2. Never write topic-replacement filler: 'This section discusses X...'",
            "3. Never use generic academic filler phrases",
            "4. Each paragraph: topic sentence → fact → explanation → analysis",
            "5. Minimum 150 words per paragraph, maximum 300 words",
            "6. Use proper academic tone throughout",
            "7. DO NOT embed bullet points inside paragraphs",
            "8. DO NOT repeat the same fact across multiple paragraphs",
            "9. DO NOT write about topics not covered by the facts",
            "10. If facts are insufficient for a claim, write exactly: "
            "'Insufficient source material available for this claim.'",
        ])

        return "\n".join(parts)
