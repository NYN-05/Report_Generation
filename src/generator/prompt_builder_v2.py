"""PromptBuilderV2 — builds prompts with strict evidence-based requirements.

Every prompt must include:
- REPORT OBJECTIVE
- SECTION OBJECTIVE
- RETRIEVED EVIDENCE
- PREVIOUS SECTION SUMMARY
- STYLE REQUIREMENTS
- FORMATTING REQUIREMENTS
- CITATION REQUIREMENTS
- TECHNICAL DEPTH REQUIREMENTS

Never allow generation without retrieved evidence.
"""

import os
from typing import Dict, Any, Optional, List
from src.core.logger import get_logger

logger = get_logger(__name__)


class PromptBuilderV2:

    SECTION_STRUCTURES = {
        "introduction": {
            "sections": ["Background", "Problem Statement", "Motivation", "Objectives", "Scope", "Contribution"],
        },
        "literature_review": {
            "sections": ["Research Area", "Existing Work", "Strengths", "Limitations", "Research Gap"],
        },
        "methodology": {
            "sections": ["System Architecture", "Workflow", "Algorithms", "Models", "Implementation Strategy"],
        },
        "implementation": {
            "sections": ["Development Environment", "Core Components", "Integration", "Testing"],
        },
        "results": {
            "sections": ["Experimental Setup", "Observations", "Metrics", "Analysis"],
        },
        "discussion": {
            "sections": ["Interpretation", "Advantages", "Limitations", "Future Improvements"],
        },
        "conclusion": {
            "sections": ["Summary", "Achievements", "Future Work"],
        },
    }

    def build_prompt(
        self,
        section_type: str,
        topic: str,
        report_type: str = "engineering project report",
        retrieval_context: str = "",
        chapter_summary: str = "",
        previous_section_summary: str = "",
        citation_instructions: str = "",
        target_words: int = 500,
        **extra_vars,
    ) -> str:
        structure = self.SECTION_STRUCTURES.get(section_type, {})
        sub_sections = structure.get("sections", [])

        prompt_parts = [
            "=" * 60,
            "REPORT OBJECTIVE",
            "=" * 60,
            f"Write the {section_type.replace('_', ' ')} section for a {report_type} on: {topic}",
            "",
            "=" * 60,
            "SECTION OBJECTIVE",
            "=" * 60,
            self._get_section_objective(section_type, topic),
            "",
            "=" * 60,
            "REQUIRED SUB-SECTIONS",
            "=" * 60,
        ]

        for i, ss in enumerate(sub_sections, 1):
            prompt_parts.append(f"{i}. {ss}")

        prompt_parts.extend([
            "",
            "=" * 60,
            "RETRIEVED EVIDENCE",
            "=" * 60,
        ])

        if retrieval_context:
            prompt_parts.append(
                "The following evidence was retrieved from uploaded documents. "
                "You MUST use this evidence to support every claim. "
                "Do NOT invent statistics, performance values, accuracy percentages, "
                "datasets, or references not found in this evidence.\n"
            )
            prompt_parts.append(retrieval_context)
        else:
            prompt_parts.append(
                "[NO EVIDENCE AVAILABLE] No source documents were retrieved for this section. "
                "DO NOT fabricate facts, statistics, references, or data. "
                "If the section requires specific evidence, insert the placeholder: "
                "[Source Material Required]"
            )

        if previous_section_summary:
            prompt_parts.extend([
                "",
                "=" * 60,
                "PREVIOUS SECTION SUMMARY",
                "=" * 60,
                previous_section_summary,
            ])

        prompt_parts.extend([
            "",
            "=" * 60,
            "CITATION REQUIREMENTS",
            "=" * 60,
        ])
        if citation_instructions:
            prompt_parts.append(citation_instructions)
        else:
            prompt_parts.append(
                "Cite sources using IEEE format [1], [2], etc. "
                "Reference the source document for each claim. "
                "Each paragraph should cite at least one evidence source."
            )

        prompt_parts.extend([
            "",
            "=" * 60,
            "STYLE REQUIREMENTS",
            "=" * 60,
            "- IEEE academic tone throughout",
            "- Third-person formal writing only",
            "- No conversational language (no \"let's\", \"we'll\", \"you may\")",
            "- No marketing language (no \"cutting-edge\", \"robust\", \"seamless\")",
            "- No generic filler or shallow statements",
            "- Each paragraph must have: topic sentence, supporting explanation, technical details, concluding transition",
            "- Minimum 120 words per paragraph, maximum 250 words",
            "- Average sentence length: 15-25 words",
            "",
            "=" * 60,
            "FORMATTING REQUIREMENTS",
            "=" * 60,
            "- Use proper paragraph breaks between distinct ideas",
            "- NEVER embed bullet points or list markers inside paragraphs",
            "- Bullet lists must be structured as: lead-in sentence, list with title+description, lead-out sentence",
            "- Each bullet item must have a bold title followed by a description on a new line",
            "- Tables must have clear headers and rows",
            "- No markdown formatting inside paragraphs",
            "",
            "=" * 60,
            "TECHNICAL DEPTH REQUIREMENTS",
            "=" * 60,
            "- Use domain-specific terminology appropriately",
            "- Reference specific components, algorithms, or methods from the evidence",
            "- Include precise technical descriptions, not vague generalities",
            "- Maintain academic rigor in all explanations",
            "- If evidence provides specific numbers, use them; otherwise, DO NOT invent numbers",
            "",
            "=" * 60,
            "EVIDENCE USAGE RULES",
            "=" * 60,
            "RULE 1: Every claim MUST trace back to retrieved evidence",
            "RULE 2: Never invent statistics, percentages, or performance metrics",
            "RULE 3: Never invent citations or references to papers not in evidence",
            "RULE 4: Never invent dataset names or sizes",
            "RULE 5: If evidence is missing a necessary fact, write [Source Material Required]",
            "RULE 6: All technical claims must cite the source document",
            "",
            "=" * 60,
            "OUTPUT FORMAT",
            "=" * 60,
            "Write the section content below. Use clear paragraph structure.",
            "For bullet lists, format as:",
            "Lead-in sentence.",
            "",
            "Item Title: Description text here.",
            "",
            "Lead-out sentence.",
            "",
            "For tables, format as:",
            "[Table: Caption]",
            "| Header1 | Header2 |",
            "|---------|---------|",
            "| Cell1   | Cell2   |",
        ])

        return "\n".join(prompt_parts)

    def _get_section_objective(self, section_type: str, topic: str) -> str:
        objectives = {
            "introduction": (
                f"Establish the background, problem statement, and motivation for studying {topic}. "
                "Define clear objectives, scope, and the contribution of this report."
            ),
            "literature_review": (
                f"Survey existing research and approaches related to {topic}. "
                "Identify strengths and limitations of current work, and establish "
                "the research gap that this report addresses."
            ),
            "methodology": (
                f"Describe the system architecture, workflow, algorithms, models, and "
                "implementation strategy used to address the problem of {topic}. "
                "Provide sufficient technical detail for reproducibility."
            ),
            "implementation": (
                f"Detail the development environment, core components, integration approach, "
                "and testing methodology for the system addressing {topic}."
            ),
            "results": (
                f"Present experimental setup, observations, metrics, and analysis of results "
                f"for the {topic} system. Base all numerical claims on evidence."
            ),
            "discussion": (
                f"Interpret the results, discuss advantages and limitations of the approach, "
                f"and outline future improvements for work on {topic}."
            ),
            "conclusion": (
                f"Summarize the key achievements of this report on {topic}, "
                "reiterate contributions, and suggest directions for future work."
            ),
        }
        return objectives.get(section_type, f"Write the {section_type} section for {topic}.")
