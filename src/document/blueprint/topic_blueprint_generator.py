from typing import Dict, List, Optional, Any
from src.core.logger import get_logger
from .models import Blueprint, BlueprintSection, ReportPlan, PlanSection

logger = get_logger(__name__)


SECTION_STRUCTURE_TEMPLATES = {
    "introduction": {
        "subsections": [
            "Background and Context",
            "Problem Statement",
            "Motivation",
            "Objectives",
            "Scope and Limitations",
            "Report Organization",
        ],
        "description": "Establish research context, define the problem, and outline contributions",
        "min_paragraphs": 5,
    },
    "literature_review": {
        "subsections": [
            "Overview of Existing Approaches",
            "Comparative Analysis",
            "Strengths and Limitations",
            "Research Gap Identification",
        ],
        "description": "Survey related work, identify gaps, and position the research",
        "min_paragraphs": 6,
    },
    "methodology": {
        "subsections": [
            "System Architecture",
            "Design Principles",
            "Core Algorithms",
            "Implementation Strategy",
        ],
        "description": "Describe the proposed approach with technical depth",
        "min_paragraphs": 6,
    },
    "implementation": {
        "subsections": [
            "Technology Stack",
            "Development Environment",
            "Key Implementation Details",
            "Configuration and Parameters",
        ],
        "description": "Detail practical implementation choices and technical setup",
        "min_paragraphs": 4,
    },
    "results": {
        "subsections": [
            "Experimental Setup",
            "Quantitative Results",
            "Qualitative Analysis",
            "Comparative Evaluation",
        ],
        "description": "Present findings with evidence support and analysis",
        "min_paragraphs": 5,
    },
    "discussion": {
        "subsections": [
            "Interpretation of Results",
            "Comparison with Existing Work",
            "Advantages and Limitations",
            "Implications",
        ],
        "description": "Interpret findings, compare with literature, discuss implications",
        "min_paragraphs": 5,
    },
    "conclusion": {
        "subsections": [
            "Summary of Work",
            "Key Contributions",
            "Limitations",
            "Future Research Directions",
        ],
        "description": "Summarize contributions and outline future work",
        "min_paragraphs": 3,
    },
}


class TopicSpecificBlueprintGenerator:
    def __init__(self, provider=None):
        self._provider = provider

    def generate_blueprint(self, topic: str,
                            section_types: Optional[List[str]] = None) -> Blueprint:
        types = section_types or [
            "introduction", "literature_review", "methodology",
            "implementation", "results", "discussion", "conclusion",
        ]
        sections = []
        for stype in types:
            template = SECTION_STRUCTURE_TEMPLATES.get(stype, {
                "subsections": [],
                "description": f"Content for {stype}",
                "min_paragraphs": 3,
            })
            sub_sections = [
                BlueprintSection(
                    id=f"{stype}_{sub.lower().replace(' ', '_')[:20]}",
                    heading=sub,
                    level=2,
                    content_hint=self._generate_section_topics(topic, stype)[i]
                    if i < len(self._generate_section_topics(topic, stype)) else sub,
                )
                for i, sub in enumerate(template["subsections"])
            ]
            section = BlueprintSection(
                id=stype,
                heading=stype.replace("_", " ").title(),
                level=1,
                content_hint=template["description"],
                subsections=sub_sections,
            )
            sections.append(section)
        blueprint = Blueprint(
            id=f"blueprint_{topic.lower().replace(' ', '_')[:30]}",
            name=f"Blueprint: {topic}",
            description=f"Auto-generated report blueprint for: {topic}",
            sections=sections,
        )
        logger.info(f"Generated blueprint with {len(sections)} sections for '{topic}'")
        return blueprint

    def generate_plan(self, topic: str, title: Optional[str] = None,
                       author: str = "") -> ReportPlan:
        blueprint = self.generate_blueprint(topic)
        plan_sections = []
        for bs in blueprint.sections:
            plan_sections.append(PlanSection(
                blueprint_section_id=bs.id,
                heading=bs.heading,
                level=bs.level,
            ))
        plan = ReportPlan(
            blueprint_id=blueprint.id,
            blueprint_name=blueprint.name,
            title=title or topic,
            author=author,
            sections=plan_sections,
        )
        logger.info(f"Generated report plan: '{plan.title}' ({len(plan.sections)} sections)")
        return plan

    def _generate_section_topics(self, topic: str, section_type: str) -> List[str]:
        template = SECTION_STRUCTURE_TEMPLATES.get(section_type, {})
        subs = template.get("subsections", [])
        return [f"{topic} — {sub}" for sub in subs]
