import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .models import Blueprint, BlueprintSection, ReportPlan, PlanSection
from src.core.logger import get_logger
from src.providers import get_default_provider, Message
from src.document.rules import RulesEngine, ReportRules

logger = get_logger(__name__)

DEFAULT_CHAPTER_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "engineering_project": [
        {"heading": "1. Introduction", "hint": "Project background, problem statement, objectives, scope, methodology overview, report organization"},
        {"heading": "2. Literature Review", "hint": "Review of existing systems, technologies used, gap analysis, theoretical framework"},
        {"heading": "3. System Design", "hint": "System architecture, design methodology, hardware/software requirements, design diagrams"},
        {"heading": "4. Implementation", "hint": "Implementation details, algorithms used, code structure, screenshots, testing approach"},
        {"heading": "5. Results and Discussion", "hint": "Results analysis, performance evaluation, comparison with existing systems, discussion"},
        {"heading": "6. Conclusion and Future Work", "hint": "Summary of work done, contributions, limitations, future enhancements"},
    ],
    "research_paper": [
        {"heading": "1. Introduction", "hint": "Research context, problem statement, research questions, objectives, paper organization"},
        {"heading": "2. Literature Survey", "hint": "Review of prior work, theoretical foundations, research gap, contributions"},
        {"heading": "3. Methodology", "hint": "Research methodology, data collection, experimental setup, evaluation metrics"},
        {"heading": "4. Results", "hint": "Experimental results, data analysis, statistical tests, observations"},
        {"heading": "5. Discussion", "hint": "Interpretation of results, comparison with prior work, implications, limitations"},
        {"heading": "6. Conclusion", "hint": "Summary of contributions, key findings, future research directions"},
    ],
    "internship_report": [
        {"heading": "1. Company Overview", "hint": "Company profile, organizational structure, products/services, industry context"},
        {"heading": "2. Work Done", "hint": "Tasks performed, projects contributed to, technologies used, daily responsibilities"},
        {"heading": "3. Key Learnings", "hint": "Technical skills acquired, professional development, challenges faced, solutions"},
        {"heading": "4. Contributions", "hint": "Specific contributions, project outcomes, impact on the organization"},
        {"heading": "5. Conclusion", "hint": "Summary of internship experience, skills gained, future career implications"},
    ],
}


class AIReportPlanner:
    """Plans report structure using an LLM, with fallback to template chapters."""

    def __init__(self, provider=None, rules_engine: Optional[RulesEngine] = None,
                 rules_path: Optional[str] = None):
        self.provider = provider or get_default_provider()
        self._rules_engine = rules_engine or (
            RulesEngine(rules_path=rules_path) if rules_path else RulesEngine()
        )

    def plan(self, topic: str, blueprint: Blueprint,
             title: str = "", author: str = "", date: str = "",
             use_llm: bool = False, llm_timeout: int = 30
             ) -> ReportPlan:
        if use_llm and self.provider and self.provider.is_available():
            try:
                return self._plan_with_llm(topic, blueprint, title, author, date)
            except Exception as e:
                logger.warning(f"LLM planning failed, using fallback: {e}")

        return self._plan_fallback(topic, blueprint, title, author, date)

    def _plan_with_llm(self, topic: str, blueprint: Blueprint,
                       title: str, author: str, date: str) -> ReportPlan:
        sections_json = json.dumps([
            {"id": s.id, "heading": s.heading, "level": s.level,
             "mandatory": s.mandatory, "content_hint": s.content_hint,
             "has_subsections": len(s.subsections) > 0 or s.id == "chapters"}
            for s in blueprint.sections
        ], indent=2)

        prompt = f"""You are an academic report planner. Plan the structure of a report.

Blueprint: {blueprint.name}
Topic: {topic}
Title: {title or topic}

Blueprint sections:
{sections_json}

For each section, provide:
1. The actual heading text to use (for chapters, include numbering like "1. Introduction")
2. Content (1-2 paragraphs of the actual report text)
3. For chapters, also provide subsections with headings and content
4. Estimated pages per section
5. Number of references needed
6. Whether the section needs figures or tables

For the "chapters" section, generate appropriate chapters based on the topic.
For engineering projects, use: Introduction, Literature Review, System Design, Implementation, Results, Conclusion.
Adjust based on the topic.

Output ONLY valid JSON in this format:
{{
  "sections": [
    {{
      "blueprint_section_id": "introduction",
      "heading": "1. Introduction",
      "level": 1,
      "content": "Full paragraph content here...",
      "allocated_pages": 3,
      "subsections": [
        {{"blueprint_section_id": "introduction", "heading": "1.1 Background", "level": 2, "content": "Background content..."}}
      ],
      "requires_figure": false,
      "figure_description": "",
      "requires_table": false,
      "table_headers": [],
      "table_rows": []
    }}
  ],
  "total_pages": 30,
  "total_references": 15,
  "total_figures": 5,
  "total_tables": 3,
  "references": ["[1] Author, Title, Journal, Year", "[2] ..."]
}}
Do not include sections with id "cover_page", "table_of_contents", "list_of_figures", "list_of_tables" in the sections array — those are auto-generated.
Do not include "certificate", "declaration", "acknowledgement", "abstract" unless the blueprint has them.
Only include sections that are in the blueprint above."""

        messages = [
            Message(role="system", content="You are an academic report planning assistant. Output only valid JSON."),
            Message(role="user", content=prompt),
        ]

        response = self.provider.chat(messages)
        data = self._parse_json(response.content)

        sections = []
        for s_data in data.get("sections", []):
            subsections = []
            for sub in s_data.get("subsections", []):
                subsections.append(PlanSection(
                    blueprint_section_id=sub.get("blueprint_section_id", s_data.get("blueprint_section_id", "")),
                    heading=sub.get("heading", ""),
                    level=sub.get("level", 2),
                    content=sub.get("content", ""),
                    allocated_pages=sub.get("allocated_pages", 0),
                    requires_figure=sub.get("requires_figure", False),
                    requires_table=sub.get("requires_table", False),
                ))
            sections.append(PlanSection(
                blueprint_section_id=s_data.get("blueprint_section_id", ""),
                heading=s_data.get("heading", ""),
                level=s_data.get("level", 1),
                content=s_data.get("content", ""),
                subsections=subsections,
                allocated_pages=s_data.get("allocated_pages", 0),
                requires_figure=s_data.get("requires_figure", False),
                figure_description=s_data.get("figure_description", ""),
                requires_table=s_data.get("requires_table", False),
                table_headers=s_data.get("table_headers", []),
                table_rows=s_data.get("table_rows", []),
            ))

        return ReportPlan(
            blueprint_id=blueprint.id,
            blueprint_name=blueprint.name,
            title=title or topic,
            subtitle="",
            author=author,
            date=date,
            sections=sections,
            total_pages=data.get("total_pages", 30),
            total_references=data.get("total_references", 10),
            total_figures=data.get("total_figures", 0),
            total_tables=data.get("total_tables", 0),
            references=data.get("references", []),
        )

    def _plan_fallback(self, topic: str, blueprint: Blueprint,
                       title: str = "", author: str = "",
                       date: str = "") -> ReportPlan:
        sections: List[PlanSection] = []
        chapter_templates = DEFAULT_CHAPTER_TEMPLATES.get(blueprint.id, [])

        for bp_section in blueprint.sections:
            bp_id = bp_section.id

            if bp_id in ("cover_page", "table_of_contents", "list_of_figures", "list_of_tables"):
                continue

            if bp_id == "chapters":
                for ch in chapter_templates:
                    content = self._rules_engine.generate_section_content(
                        topic=topic, heading=ch["heading"],
                        blueprint_section_id="chapters", allocated_pages=4,
                    )
                    sec = PlanSection(
                        blueprint_section_id="chapters",
                        heading=ch["heading"],
                        level=bp_section.level,
                        content=content,
                        allocated_pages=4,
                    )
                    subs_data = self._rules_engine.generate_subsections(
                        topic=topic, section_heading=ch["heading"],
                        blueprint_section_id="chapters", count=3,
                    )
                    subs = [
                        PlanSection(
                            blueprint_section_id="chapters",
                            heading=sub_h,
                            level=sub_lvl,
                            content=sub_c,
                            allocated_pages=2,
                        )
                        for sub_h, sub_c, sub_lvl in subs_data
                    ]
                    sec.subsections = subs
                    sections.append(sec)
            elif bp_id == "certificate":
                cert_text = (
                    f"This is to certify that the project titled \"{title or topic}\" "
                    f"has been satisfactorily completed by "
                    f"{author or 'the candidate'} under our supervision. "
                    f"The work is found to be worthy of acceptance as a "
                    f"{blueprint.name.replace('_', ' ')} fulfillment."
                )
                sections.append(PlanSection(
                    blueprint_section_id="certificate", heading="Certificate",
                    content=cert_text,
                    allocated_pages=1,
                ))
            elif bp_id == "declaration":
                decl_text = (
                    f"I, {author or 'the undersigned'}, hereby declare that the work "
                    f"presented in this {blueprint.name.replace('_', ' ')} titled "
                    f"\"{title or topic}\" is my own original work. "
                    f"It has not been submitted elsewhere for any degree or qualification."
                )
                sections.append(PlanSection(
                    blueprint_section_id="declaration", heading="Declaration",
                    content=decl_text,
                    allocated_pages=1,
                ))
            elif bp_id == "acknowledgement":
                ack_text = (
                    f"I would like to express my sincere gratitude to all who supported me "
                    f"in completing this work on \"{title or topic}\". "
                    f"I am especially thankful to my advisors, colleagues, and family "
                    f"for their guidance, encouragement, and support throughout this project."
                )
                sections.append(PlanSection(
                    blueprint_section_id="acknowledgement", heading="Acknowledgement",
                    content=ack_text,
                    allocated_pages=1,
                ))
            elif bp_id == "abstract":
                abstract_text = self._rules_engine.generate_section_content(
                    topic=topic, heading="Abstract",
                    blueprint_section_id="abstract", allocated_pages=1,
                )
                sections.append(PlanSection(
                    blueprint_section_id="abstract", heading="Abstract",
                    content=abstract_text,
                    allocated_pages=1,
                ))
            elif bp_id in ("references",):
                sections.append(PlanSection(
                    blueprint_section_id="references", heading="References",
                    content="",
                    allocated_pages=2,
                ))
            elif bp_id in ("appendices",):
                sections.append(PlanSection(
                    blueprint_section_id="appendices", heading="Appendices",
                    content="",
                    allocated_pages=2,
                ))
            else:
                content = self._rules_engine.generate_section_content(
                    topic=topic, heading=bp_section.heading,
                    blueprint_section_id=bp_id, allocated_pages=2,
                )
                sections.append(PlanSection(
                    blueprint_section_id=bp_id,
                    heading=bp_section.heading,
                    level=bp_section.level,
                    content=content,
                    allocated_pages=2,
                ))

        total_pages = sum(s.allocated_pages for s in sections)

        topic_words = topic.split()[:3]
        topic_short = " ".join(topic_words) if topic_words else topic
        domain_keywords = {
            "engineering": "Engineering", "computer": "Computer Science",
            "data": "Data Science", "machine": "Machine Learning",
            "ai": "Artificial Intelligence", "network": "Networking",
            "security": "Cybersecurity", "web": "Web Technology",
        }
        domain = "Engineering"
        for kw, label in domain_keywords.items():
            if kw in topic.lower():
                domain = label
                break

        ref_count = 10
        references = [
            f"[{i+1}] J. Smith, \"Advances in {domain}: A Comprehensive Review,\" "
            f"International Journal of {domain}, vol. {i+10}, no. {i+2}, pp. {100+i*10}-{109+i*10}, 202{i%5+1}."
            for i in range(ref_count)
        ]

        return ReportPlan(
            blueprint_id=blueprint.id,
            blueprint_name=blueprint.name,
            title=title or topic,
            subtitle="",
            author=author,
            date=date,
            sections=sections,
            total_pages=total_pages,
            total_references=ref_count,
            total_figures=3,
            total_tables=2,
            references=references,
        )

    def _parse_json(self, text: str) -> Dict[str, Any]:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON")
            return {"sections": [], "total_pages": 0}
