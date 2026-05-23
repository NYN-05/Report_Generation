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
- CHAPTER UNIQUENESS REQUIREMENTS
- ANTI-REPETITION REQUIREMENTS
"""

import os
from typing import Dict, Any, Optional, List
from src.core.logger import get_logger

logger = get_logger(__name__)


class PromptBuilderV2:

    SECTION_STRUCTURES = {
        "introduction": {
            "purpose": "Establish the foundation: background context, problem statement, motivation, objectives, scope, and contribution. This chapter must NOT discuss methodology, results, or prior work in detail.",
            "sections": ["Background", "Problem Statement", "Motivation", "Objectives", "Scope", "Contribution"],
        },
        "literature_review": {
            "purpose": "Survey and critically compare existing research. Identify strengths, limitations, and research gaps. This chapter must NOT describe the system methodology or present results.",
            "sections": ["Research Area", "Existing Work", "Strengths", "Limitations", "Research Gap"],
        },
        "methodology": {
            "purpose": "Describe the technical approach: system architecture, workflow, algorithms, models, implementation strategy. This chapter must NOT review literature or present results.",
            "sections": ["System Architecture", "Workflow", "Algorithms", "Models", "Implementation Strategy"],
        },
        "implementation": {
            "purpose": "Detail the actual development: environment, components, integration, testing. This chapter must NOT re-describe the methodology or present evaluation results.",
            "sections": ["Development Environment", "Core Components", "Integration", "Testing"],
        },
        "results": {
            "purpose": "Present experimental findings: setup, observations, metrics, analysis. This chapter must NOT introduce background, review literature, or describe methodology. Focus on what was observed.",
            "sections": ["Experimental Setup", "Observations", "Metrics", "Analysis"],
        },
        "discussion": {
            "purpose": "Interpret results: what they mean, advantages, limitations, future work. This chapter must NOT re-present raw results or re-state the methodology.",
            "sections": ["Interpretation", "Advantages", "Limitations", "Future Improvements"],
        },
        "conclusion": {
            "purpose": "Synthesize the report: summary of findings, contributions, limitations, future work. This chapter must NOT repeat the introduction or re-present detailed results.",
            "sections": ["Summary", "Major Findings", "Contributions", "Limitations", "Future Work"],
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
        existing_chapter_summaries: Optional[List[str]] = None,
        facts: Optional[List] = None,
        evidence_map: Optional[Dict] = None,
        citations: Optional[List] = None,
        **extra_vars,
    ) -> str:
        structure = self.SECTION_STRUCTURES.get(section_type, {})
        sub_sections = structure.get("sections", [])
        purpose = structure.get("purpose", "")

        prompt_parts = [
            "=" * 60,
            "REPORT OBJECTIVE",
            "=" * 60,
            f"Write the {section_type.replace('_', ' ')} section for a {report_type} on: {topic}",
            "",
            "=" * 60,
            "CHAPTER PURPOSE (DO NOT VIOLATE)",
            "=" * 60,
            purpose,
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
            "CHAPTER UNIQUENESS REQUIREMENTS",
            "=" * 60,
            "This chapter MUST have a distinct purpose from all other chapters.",
            "Introduction: ONLY background, problem, motivation, objectives, scope.",
            "Literature Review: ONLY existing work, comparisons, research gaps.",
            "Methodology: ONLY architecture, workflow, algorithms, models.",
            "Implementation: ONLY development details, components, integration.",
            "Results: ONLY experimental findings, observations, metrics, analysis.",
            "Discussion: ONLY interpretation, implications, limitations.",
            "Conclusion: ONLY summary, contributions, future work.",
            "",
            "DO NOT mix content from other chapters.",
            "DO NOT repeat explanations from previous chapters.",
            "If a concept was already explained, reference it briefly, do not re-explain.",
            "",
            "=" * 60,
            "ANTI-REPETITION REQUIREMENTS",
            "=" * 60,
            "Before writing any paragraph, check that it is not semantically similar",
            "to content already written in previous chapters.",
            "Avoid:",
            "- repeated explanations of the same concept",
            "- repeated examples",
            "- repeated statistics or metrics",
            "- repeated sentence patterns",
            "- repeated wording or phrasing",
            "",
            "Every paragraph must contain NEW information, analysis, or perspective.",
            "Maximum allowed similarity to any previous chapter: 20%.",
        ])

        if existing_chapter_summaries:
            prompt_parts.extend([
                "",
                "=" * 60,
                "EXISTING CHAPTER SUMMARIES (AVOID REPETITION)",
                "=" * 60,
            ])
            for i, summary in enumerate(existing_chapter_summaries):
                prompt_parts.append(f"--- Previous Chapter {i+1} ---")
                prompt_parts.append(summary[:400])

        prompt_parts.extend([
            "",
            "=" * 60,
            "RETRIEVED EVIDENCE",
            "=" * 60,
        ])

        if facts:
            prompt_parts.extend([
                "",
                "=" * 60,
                "STRUCTURED FACTS FROM EVIDENCE (PRIMARY SOURCE OF CLAIMS)",
                "=" * 60,
                "Each fact below was extracted from source documents with a confidence score.",
                "You MUST base every claim on these facts. Do NOT invent claims outside these facts.\n",
            ])
            for i, fact in enumerate(facts):
                f_text = getattr(fact, "text", str(fact))
                f_conf = getattr(fact, "confidence", 0.5)
                f_cat = getattr(fact, "category", "general")
                prompt_parts.append(f"FACT {i+1} [confidence: {f_conf}, category: {f_cat}]")
                prompt_parts.append(f"  {f_text[:200]}")
                prompt_parts.append("")

        if evidence_map:
            prompt_parts.extend([
                "=" * 60,
                "CLAIM-EVIDENCE MAP",
                "=" * 60,
                "The following claims are directly supported by the extracted facts.\n",
            ])
            for claim, mapped_facts in list(evidence_map.items())[:10]:
                prompt_parts.append(f"Claim: {claim[:150]}")
                for mf in mapped_facts[:3]:
                    mf_text = getattr(mf, "text", str(mf))[:120]
                    prompt_parts.append(f"  → Supported by: {mf_text}")
                prompt_parts.append("")

        if citations:
            prompt_parts.extend([
                "=" * 60,
                "STRUCTURED CITATIONS",
                "=" * 60,
                "Use these citation indices when referencing evidence from sources.\n",
            ])
            for i, cit in enumerate(citations):
                cit_str = str(cit)[:150]
                prompt_parts.append(f"  [{i+1}] {cit_str}")

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
                "Do NOT invent statistics, percentages, performance metrics, "
                "datasets, or references not found in this evidence.\n"
            )
            prompt_parts.append(retrieval_context)
        else:
            prompt_parts.append(
                "[NO EVIDENCE AVAILABLE] No source documents were retrieved for this section. "
                "DO NOT fabricate facts, statistics, references, or data. "
                "If the section requires specific evidence, write exactly: "
                "Insufficient source material available for this claim."
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
                "Each paragraph should cite at least one evidence source. "
                "Never generate fake authors, fake journals, fake conferences, fake DOIs, or fake URLs."
            )

        prompt_parts.extend([
            "",
            "=" * 60,
            "FACT-FIRST WRITING MANDATE (CRITICAL)",
            "=" * 60,
            "Workflow for EVERY paragraph:",
            "  1. Select a FACT from the structured facts above",
            "  2. Explain what the fact means in context",
            "  3. Analyze its significance",
            "  4. Transition to the next fact-driven paragraph",
            "",
            "DO NOT:",
            "  - Write a paragraph starting from the topic (topic-first writing is forbidden)",
            "  - Use topic-insertion patterns like 'The application of [Topic] in [Field]'",
            "  - Begin with 'This section discusses...' or 'This chapter presents...'",
            "  - Repeat the same fact across multiple paragraphs",
            "  - Invent facts, statistics, or references not in the provided facts",
            "",
            "If a paragraph does not originate from at least one FACT above, it will be rejected.",
            "",
            "=" * 60,
            "STYLE REQUIREMENTS",
            "=" * 60,
            "- IEEE academic tone throughout",
            "- Third-person formal writing only",
            "- No conversational language (no \"let's\", \"we'll\", \"you may\", \"imagine\")",
            "- No marketing language (no \"cutting-edge\", \"robust\", \"seamless\", \"game-changer\")",
            "- No generic filler or shallow statements",
            "- Each paragraph must have: core idea, explanation, supporting detail, analysis, transition",
            "- Minimum 150 words per paragraph, maximum 300 words",
            "- Average sentence length: 15-25 words",
            "- Use domain-specific terminology appropriately",
            "- Forbidden phrases (meaningless unless followed by specific evidence):",
            '  "Several important aspects can be observed."',
            '  "This topic has gained significant attention."',
            '  "Research indicates many benefits."',
            '  "Various studies have shown improvements."',
            '  "This field is rapidly growing."',
            '  "Many researchers have focused on."',
            '  "Current trends demonstrate."',
            '  "It is important to note/consider/understand."',
            '  "Over the past few years/decades."',
            '  "A wide range of."',
            '  "There are many/several/various ways/approaches."',
            "",
            "=" * 60,
            "FORMATTING REQUIREMENTS",
            "=" * 60,
            "- Use proper paragraph breaks between distinct ideas",
            "- NEVER embed bullet points or list markers inside paragraphs",
            "- Bullet lists must be structured as: lead-in sentence, list with title+description, lead-out sentence",
            "- Each bullet item must have a bold title followed by a description",
            "- Tables must have clear headers and rows",
            "- No markdown formatting inside paragraphs",
            "- Use the most appropriate format: paragraphs for narrative, bullet lists for lists, tables for comparisons",
            "",
            "=" * 60,
            "TECHNICAL DEPTH REQUIREMENTS",
            "=" * 60,
            "Every section must answer these 7 questions:",
            "1. What? — What is being presented or discussed?",
            "2. Why? — Why is it important or relevant?",
            "3. How? — How does it work or how was it done?",
            "4. Impact? — What is the effect or significance?",
            "5. Limitations? — What constraints or weaknesses exist?",
            "6. Applications? — Where can it be applied?",
            "7. Future implications? — What are the next steps?",
            "",
            "Do not stop at definitions. Provide explanation and analysis.",
            "- Use domain-specific terminology appropriately",
            "- Reference specific components, algorithms, or methods from the evidence",
            "- Include precise technical descriptions, not vague generalities",
            "- Maintain academic rigor in all explanations",
            "- If evidence provides specific numbers, use them; otherwise, DO NOT invent numbers",
            "",
            "=" * 60,
            "EVIDENCE USAGE RULES",
            "=" * 60,
            "RULE 1: Every paragraph MUST reference at least one FACT by number (FACT 1, FACT 2, etc.)",
            "RULE 2: Every major claim MUST trace directly to an extracted fact above",
            "RULE 3: Never invent statistics, percentages, or performance metrics",
            "RULE 4: Never invent citations or references to papers not in evidence",
            "RULE 5: Never invent dataset names or sizes",
            "RULE 6: If evidence is missing a necessary fact, write:",
            '     "Insufficient source material available for this claim."',
            "RULE 7: All technical claims must cite the source document",
            "RULE 8: Never write topic-name-replacement templates",
            "     Bad: 'This section discusses the applications of [Topic] in [Domain].'",
            '     Good: "The application of random forest classifiers for detecting anomalous network traffic patterns has been extensively documented."',
            "RULE 9: Never repeat the same fact across multiple paragraphs — each fact used once",
            "RULE 10: Information density per paragraph must be high — every sentence should add value",
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
                f"Establish the background context for {topic}, clearly articulate the "
                "problem being addressed, explain why this problem matters, define specific "
                "objectives, delimit the scope of work, and state the contribution of this report. "
                "Do NOT describe methodology or results."
            ),
            "literature_review": (
                f"Survey existing research related to {topic}. Critically compare different "
                "approaches, identify their strengths and limitations, and establish the specific "
                "research gap that this report addresses. Must include comparative analysis, "
                "not just generic descriptions of prior work."
            ),
            "methodology": (
                f"Describe the system architecture, workflow, algorithms, models, and "
                "implementation strategy used. Provide sufficient technical detail for reproducibility. "
                "Justify design choices. Do NOT review literature or present results."
            ),
            "implementation": (
                f"Detail the actual development process: environment setup, core component "
                "implementation, integration approach, and testing methodology. Focus on the "
                "implementation decisions, trade-offs, and practical considerations. "
                "Do NOT re-describe the methodology."
            ),
            "results": (
                f"Present experimental findings objectively. Describe the setup, report observations, "
                "present metrics, and provide analysis of what the data shows. "
                "Do NOT introduce background, review literature, or describe methodology. "
                "Focus on observations and findings, not interpretation."
            ),
            "discussion": (
                f"Interpret the results presented in the previous chapter. Discuss advantages "
                "and limitations of the approach, compare with existing work, and outline "
                "implications and future improvements. Do NOT re-present raw results."
            ),
            "conclusion": (
                f"Synthesize the entire report. Summarize key findings, state contributions, "
                "acknowledge limitations, and suggest future research directions. "
                "Do NOT repeat the introduction or re-present detailed results."
            ),
        }
        return objectives.get(section_type, f"Write the {section_type} section for {topic}.")
