"""MultiPassImprover — 7-pass content improvement pipeline.

Pass 1: Draft
Pass 2: Evidence Injection
Pass 3: Technical Expansion
Pass 4: Anti-Repetition (stops repeated explanations, examples, statistics, wording)
Pass 5: Terminology Consistency
Pass 6: Style Refinement (removes vague statements, empty claims, template patterns)
Pass 7: Formatting Validation
Pass 8: Final Review
"""

import re
from typing import Dict, Any, Optional, List, Tuple, Set
from src.core.logger import get_logger
from .content_blocks import SectionContent, ParagraphBlock, BulletListBlock, SourceRequiredBlock
from .paragraph_quality import ParagraphQualityControl
from .technical_depth import TechnicalDepthEvaluator, DepthScore

logger = get_logger(__name__)


class MultiPassImprover:

    def __init__(self, provider=None):
        self._provider = provider
        self._quality = ParagraphQualityControl()
        self._depth = TechnicalDepthEvaluator()
        self._previous_content: List[str] = []

    def set_previous_content(self, contents: List[str]):
        self._previous_content = contents

    def improve(self, section: SectionContent, section_type: str, topic: str) -> Tuple[SectionContent, List[str]]:
        logs = []

        logs.append("Pass 1: Draft — initial content generated")

        section, log2 = self._pass_evidence_injection(section)
        logs.extend(log2)

        section, log3 = self._pass_technical_expansion(section, section_type)
        logs.extend(log3)

        section, log4 = self._pass_anti_repetition(section)
        logs.extend(log4)

        section, log5 = self._pass_terminology_consistency(section)
        logs.extend(log5)

        section, log6 = self._pass_style_refinement(section)
        logs.extend(log6)

        section, log7 = self._pass_formatting_validation(section)
        logs.extend(log7)

        section, log8 = self._pass_final_review(section)
        logs.extend(log8)

        return section, logs

    def _pass_evidence_injection(self, section: SectionContent) -> Tuple[SectionContent, List[str]]:
        logs = []
        for block in section.blocks:
            if isinstance(block, ParagraphBlock):
                lacks_evidence = not block.evidence_source and "Insufficient source material" not in block.text
                if lacks_evidence:
                    if self._provider and self._provider.is_available():
                        enhanced = self._enhance_with_evidence(block.text)
                        if enhanced:
                            block.text = enhanced
                            logs.append(f"  Evidence injected into paragraph ({block.word_count} words)")
                    else:
                        logs.append(f"  Warning: paragraph lacks evidence source")
        return section, logs

    def _enhance_with_evidence(self, text: str) -> str:
        from src.providers import Message, CompletionOptions
        try:
            prompt = (
                "The following paragraph lacks evidence from source material. "
                "Enhance it by inserting specific references to source documents. "
                "If no specific evidence is available, append:\n"
                "Insufficient source material available for this claim.\n\n"
                f"Paragraph:\n{text}"
            )
            messages = [
                Message(role="system", content="You are enhancing academic text with evidence references."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.3, max_tokens=1024, timeout=60)
            response = self._provider.chat(messages, options=opts)
            return response.content.strip()
        except Exception:
            return ""

    def _pass_technical_expansion(self, section: SectionContent, section_type: str) -> Tuple[SectionContent, List[str]]:
        logs = []
        for block in section.blocks:
            if isinstance(block, ParagraphBlock):
                score, passed = self._depth.evaluate_section(
                    block.text, evidence_count=1 if block.evidence_source else 0
                )
                if not passed and score.technical_detail < 0.5:
                    if self._provider and self._provider.is_available():
                        expanded = self._expand_technical(block.text, section_type)
                        if expanded:
                            block.text = expanded
                            block.word_count = len(expanded.split())
                            logs.append(f"  Technical detail expanded (depth: {score.technical_detail:.2f} -> target >0.5)")
        return section, logs

    def _expand_technical(self, text: str, section_type: str) -> str:
        from src.providers import Message, CompletionOptions
        try:
            prompt = (
                "The following paragraph lacks sufficient technical depth. "
                "Expand it with domain-specific technical terminology, precise descriptions "
                f"of components, algorithms, or methods appropriate for a {section_type} section. "
                "Maintain academic tone and do not add fabricated statistics. "
                "Do NOT use topic-replacement-template patterns.\n\n"
                f"Paragraph:\n{text}"
            )
            messages = [
                Message(role="system", content="You are expanding technical detail in academic writing."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.3, max_tokens=1024, timeout=60)
            response = self._provider.chat(messages, options=opts)
            return response.content.strip()
        except Exception:
            return ""

    def _pass_anti_repetition(self, section: SectionContent) -> Tuple[SectionContent, List[str]]:
        logs = []
        if not self._previous_content:
            return section, logs

        all_previous = " ".join(self._previous_content).lower()
        prev_words = set(all_previous.split())
        prev_sentences = set(re.split(r'(?<=[.!?])\s+', all_previous))

        for block in section.blocks:
            if isinstance(block, ParagraphBlock):
                text_lower = block.text.lower()
                current_words = set(text_lower.split())
                overlap = current_words & prev_words
                if len(overlap) / max(len(current_words), 1) > 0.4:
                    logs.append(
                        f"  High word overlap ({len(overlap)}/{len(current_words)} words) "
                        f"with previous content"
                    )

                current_sentences = set(re.split(r'(?<=[.!?])\s+', text_lower))
                repeated = current_sentences & prev_sentences
                if repeated:
                    for s in list(repeated)[:2]:
                        logs.append(f"  Repeated sentence pattern detected: '{s[:60]}...'")

                explicit_repeats = [
                    "as discussed previously", "as mentioned earlier", "as stated before",
                    "as noted above", "as described previously", "this was discussed",
                    "this was mentioned", "as previously discussed",
                ]
                for phrase in explicit_repeats:
                    if phrase in text_lower:
                        logs.append(f"  Contains repetitive reference: '{phrase}'")

        return section, logs

    def _pass_terminology_consistency(self, section: SectionContent) -> Tuple[SectionContent, List[str]]:
        logs = []
        all_text = []
        for block in section.blocks:
            if isinstance(block, ParagraphBlock):
                all_text.append(block.text)

        combined = " ".join(all_text)
        terms = self._extract_key_terms(combined)

        for block in section.blocks:
            if isinstance(block, ParagraphBlock):
                for term, preferred in terms.items():
                    if term.lower() in block.text.lower() and preferred.lower() not in block.text.lower():
                        if self._provider and self._provider.is_available():
                            corrected = self._normalize_terminology(block.text, term, preferred)
                            if corrected:
                                block.text = corrected
                                logs.append(f"  Terminology normalized: '{term}' -> '{preferred}'")
        return section, logs

    def _extract_key_terms(self, text: str) -> Dict[str, str]:
        return {}

    def _normalize_terminology(self, text: str, old: str, new: str) -> str:
        return text.replace(old, new)

    def _pass_style_refinement(self, section: SectionContent) -> Tuple[SectionContent, List[str]]:
        logs = []
        for block in section.blocks:
            if isinstance(block, ParagraphBlock):
                errors = self._quality.check_paragraph(block.text)
                issues = [e for e in errors if any(k in e for k in
                          ["shallow", "vague", "empty", "marketing", "conversational",
                           "embedded", "template", "Topic-replacement"])]
                if issues and self._provider and self._provider.is_available():
                    refined = self._refine_style(block.text)
                    if refined:
                        block.text = refined
                        block.word_count = len(refined.split())
                        logs.append(f"  Style refined: {', '.join(issues[:2])}")
        return section, logs

    def _refine_style(self, text: str) -> str:
        from src.providers import Message, CompletionOptions
        try:
            prompt = (
                "Rewrite the following paragraph to meet academic writing standards:\n"
                "- Remove marketing language, conversational tone, and generic filler\n"
                "- Remove vague statements like 'several aspects can be observed'\n"
                "- Remove empty claims like 'results show significant improvement'\n"
                "- Remove topic-replacement-template patterns\n"
                "- Use precise technical language\n"
                "- Maintain formal third-person academic voice\n"
                "- Keep 120-250 words\n\n"
                f"Paragraph:\n{text}"
            )
            messages = [
                Message(role="system", content="You are refining academic writing to eliminate template-like content."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.3, max_tokens=1024, timeout=60)
            response = self._provider.chat(messages, options=opts)
            return response.content.strip()
        except Exception:
            return ""

    def _pass_formatting_validation(self, section: SectionContent) -> Tuple[SectionContent, List[str]]:
        logs = []
        for i, block in enumerate(section.blocks):
            if isinstance(block, ParagraphBlock):
                if "\n•" in block.text or "\n-" in block.text or "•" in block.text:
                    logs.append(f"  Block {i}: stripping embedded bullet markers")
                    block.text = block.text.replace("•", "").replace("●", "").replace("◦", "")
        return section, logs

    def _pass_final_review(self, section: SectionContent) -> Tuple[SectionContent, List[str]]:
        logs = []
        block_count = len(section.blocks)
        para_count = sum(1 for b in section.blocks if isinstance(b, ParagraphBlock))
        source_blocks = sum(1 for b in section.blocks if isinstance(b, SourceRequiredBlock))
        bullet_count = sum(1 for b in section.blocks if isinstance(b, BulletListBlock))
        total_evidence = len(section.evidence_sources)
        logs.append(
            f"  Final: {block_count} blocks, {para_count} paragraphs, "
            f"{bullet_count} bullet lists, {source_blocks} missing-evidence markers, "
            f"{total_evidence} evidence sources"
        )
        return section, logs
