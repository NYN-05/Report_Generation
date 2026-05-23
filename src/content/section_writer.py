"""SectionSpecificWriter — enforces chapter-distinct writing with per-chapter fact requirements."""

from typing import Dict, List, Optional
from src.core.logger import get_logger

logger = get_logger(__name__)


CHAPTER_REQUIREMENTS = {
    "introduction": {
        "allowed_topics": {"background", "motivation", "problem_statement",
                           "objectives", "scope", "contribution"},
        "forbidden_topics": {"methodology_detail", "implementation_detail",
                             "result_values", "literature_comparison"},
        "required_sections": ["Background", "Problem Statement", "Motivation",
                              "Objectives", "Scope", "Contribution"],
        "fact_categories": {"general", "problem"},
        "style": "establishing — set context, define problem, state goals",
        "forbidden_phrases": [
            "the methodology", "our approach", "the system architecture",
            "we implemented", "the results show", "the experiment",
            "as shown in table", "figure",
        ],
    },
    "literature_review": {
        "allowed_topics": {"prior_work", "comparison", "research_gap",
                           "existing_approaches", "limitations_of_prior"},
        "forbidden_topics": {"own_methodology", "own_results", "future_work"},
        "required_sections": ["Research Area", "Existing Work", "Strengths",
                              "Limitations", "Research Gap"],
        "fact_categories": {"general", "methodology", "result", "problem"},
        "style": "critical comparison — evaluate, contrast, identify gaps",
        "forbidden_phrases": [
            "in this paper", "our methodology", "we propose",
            "our approach", "we implemented", "the results of our",
        ],
    },
    "methodology": {
        "allowed_topics": {"architecture", "workflow", "algorithms",
                           "models", "implementation_strategy", "design_choices"},
        "forbidden_topics": {"background", "literature_review", "result_analysis",
                             "future_work", "introduction_to_field"},
        "required_sections": ["System Architecture", "Workflow", "Algorithms",
                              "Models", "Implementation Strategy"],
        "fact_categories": {"methodology", "architecture"},
        "style": "technical specification — precise, reproducible, detailed",
        "forbidden_phrases": [
            "background information", "overview of the field",
            "this topic has gained", "research shows",
            "various studies", "in recent years",
        ],
    },
    "implementation": {
        "allowed_topics": {"environment", "components", "integration",
                           "testing", "configuration", "deployment"},
        "forbidden_topics": {"architecture_overview", "algorithm_explanation",
                             "literature_citation", "background"},
        "required_sections": ["Development Environment", "Core Components",
                              "Integration", "Testing"],
        "fact_categories": {"methodology", "architecture"},
        "style": "practical report — development decisions, trade-offs, engineering considerations",
        "forbidden_phrases": [
            "review of literature", "previous work on",
            "the algorithm works by", "mathematical formulation",
            "as discussed in the introduction",
        ],
    },
    "results": {
        "allowed_topics": {"observations", "metrics", "analysis",
                           "experimental_setup", "findings", "data"},
        "forbidden_topics": {"background", "methodology_design",
                             "literature_review", "future_implications"},
        "required_sections": ["Experimental Setup", "Observations",
                              "Metrics", "Analysis"],
        "fact_categories": {"result", "dataset"},
        "style": "objective reporting — present data, describe observations, analyze metrics",
        "forbidden_phrases": [
            "background information", "introduction to",
            "literature review", "research gap",
            "future research directions", "overview of the field",
        ],
    },
    "discussion": {
        "allowed_topics": {"interpretation", "implications", "strengths",
                           "weaknesses", "limitations", "comparison",
                           "future_directions"},
        "forbidden_topics": {"raw_results", "methodology_description",
                             "background", "introduction"},
        "required_sections": ["Interpretation", "Advantages",
                              "Limitations", "Future Improvements"],
        "fact_categories": {"general", "problem", "result"},
        "style": "analytical interpretation — explain significance, contextualize, critique",
        "forbidden_phrases": [
            "the architecture consists of", "the algorithm works by",
            "the system comprises", "background of",
            "introduction to the field",
        ],
    },
    "conclusion": {
        "allowed_topics": {"summary", "contributions", "findings",
                           "limitations", "future_work", "implications"},
        "forbidden_topics": {"new_background", "new_literature",
                             "new_methodology", "new_results"},
        "required_sections": ["Summary", "Major Findings", "Contributions",
                              "Limitations", "Future Work"],
        "fact_categories": {"general"},
        "style": "synthesis — consolidate findings, state contributions, outline next steps",
        "forbidden_phrases": [
            "this chapter discusses", "this section presents",
            "the methodology used", "as shown in the results",
            "detailed analysis of",
        ],
    },
}

CHAPTER_TYPES = set(CHAPTER_REQUIREMENTS.keys())


class SectionSpecificWriter:

    def get_requirements(self, section_type: str) -> Dict:
        return CHAPTER_REQUIREMENTS.get(section_type, {})

    def get_section_prompt_extra(self, section_type: str) -> str:
        req = self.get_requirements(section_type)
        if not req:
            return ""

        parts = [
            f"=== {section_type.upper()} — STRICT CONTENT RULES ===",
            "",
            "ALLOWED TOPICS (write ONLY about these):",
        ]
        for t in req.get("allowed_topics", set()):
            parts.append(f"  ✓ {t.replace('_', ' ')}")
        parts.append("")
        parts.append("FORBIDDEN TOPICS (DO NOT write about these):")
        for t in req.get("forbidden_topics", set()):
            parts.append(f"  ✗ {t.replace('_', ' ')}")
        parts.append("")
        parts.append("REQUIRED SUB-SECTIONS (must include each):")
        for s in req.get("required_sections", []):
            parts.append(f"  • {s}")
        parts.append("")
        parts.append("WRITING STYLE:")
        parts.append(f"  {req.get('style', 'standard academic')}")
        parts.append("")
        parts.append("FORBIDDEN PHRASES (do not use any of these):")
        for p in req.get("forbidden_phrases", []):
            parts.append(f"  ✗ \"{p}\"")
        parts.append("")
        parts.append("FACT CATEGORIES TO FOCUS ON:")
        for c in req.get("fact_categories", set()):
            parts.append(f"  • {c}")
        parts.append("")

        return "\n".join(parts)

    def validate(self, text: str, section_type: str) -> Dict[str, any]:
        req = self.get_requirements(section_type)
        if not req:
            return {"passed": True, "issues": []}

        text_lower = text.lower()
        issues = []

        for phrase in req.get("forbidden_phrases", []):
            if phrase.lower() in text_lower:
                issues.append(f"forbidden_phrase: '{phrase}'")

        allowed = {t.replace("_", " ") for t in req.get("allowed_topics", set())}
        forbidden = {t.replace("_", " ") for t in req.get("forbidden_topics", set())}
        forbidden_found = []
        for f in forbidden:
            if f in text_lower:
                forbidden_found.append(f)
        if forbidden_found:
            issues.append(f"forbidden_topics_found: {forbidden_found}")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }
