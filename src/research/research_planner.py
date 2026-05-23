from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger

logger = get_logger(__name__)


class ResearchPlan:
    def __init__(self, section_type: str, queries: List[str],
                 required_concepts: List[str] = None,
                 evidence_goal: str = ""):
        self.section_type = section_type
        self.queries = queries
        self.required_concepts = required_concepts or []
        self.evidence_goal = evidence_goal

    def to_dict(self) -> Dict:
        return {
            "section_type": self.section_type,
            "queries": self.queries,
            "required_concepts": self.required_concepts,
            "evidence_goal": self.evidence_goal,
        }


SECTION_RESEARCH_PLANS = {
    "introduction": {
        "queries": ["background", "problem definition", "current challenges", "motivation"],
        "concepts": ["background", "problem", "motivation", "scope", "objectives"],
        "goal": "Establish research context, problem significance, and paper contributions",
    },
    "literature_review": {
        "queries": ["existing approaches", "related work", "state of the art", "limitations"],
        "concepts": ["existing work", "approaches", "limitations", "research gap", "comparison"],
        "goal": "Survey existing solutions, identify their strengths and limitations, establish research gap",
    },
    "methodology": {
        "queries": ["proposed method", "system architecture", "algorithm design", "implementation"],
        "concepts": ["architecture", "algorithm", "design", "implementation", "workflow"],
        "goal": "Describe proposed solution with technical depth and architectural decisions",
    },
    "implementation": {
        "queries": ["implementation details", "tools used", "configuration", "technical setup"],
        "concepts": ["implementation", "tools", "configuration", "setup", "environment"],
        "goal": "Detail practical implementation choices, tools, and technical configuration",
    },
    "results": {
        "queries": ["experimental results", "performance evaluation", "findings", "metrics"],
        "concepts": ["experiments", "results", "performance", "evaluation", "metrics"],
        "goal": "Present quantitative and qualitative findings with evidence support",
    },
    "discussion": {
        "queries": ["analysis", "interpretation", "comparison", "implications"],
        "concepts": ["analysis", "interpretation", "comparison", "implications", "limitations"],
        "goal": "Interpret results, compare with existing work, discuss limitations and implications",
    },
    "conclusion": {
        "queries": ["summary", "contributions", "future work", "conclusion"],
        "concepts": ["summary", "contributions", "future work", "conclusion", "significance"],
        "goal": "Summarize contributions, highlight significance, outline future research directions",
    },
}


class ResearchPlanner:
    def __init__(self):
        self._plans: Dict[str, ResearchPlan] = {}

    def plan_for_section(self, section_type: str, topic: str,
                         custom_queries: Optional[List[str]] = None) -> ResearchPlan:
        preset = SECTION_RESEARCH_PLANS.get(section_type, {
            "queries": [section_type.replace("_", " ")],
            "concepts": [],
            "goal": f"Research for {section_type} section",
        })
        queries = custom_queries or [
            f"{topic} {q}" for q in preset["queries"]
        ]
        plan = ResearchPlan(
            section_type=section_type,
            queries=queries,
            required_concepts=preset["concepts"],
            evidence_goal=preset["goal"],
        )
        self._plans[section_type] = plan
        return plan

    def plan_all_sections(self, topic: str) -> Dict[str, ResearchPlan]:
        plans = {}
        for stype in SECTION_RESEARCH_PLANS:
            plan = self.plan_for_section(stype, topic)
            plans[stype] = plan
        logger.info(f"Created research plans for {len(plans)} sections")
        return plans

    def get_plan(self, section_type: str) -> Optional[ResearchPlan]:
        return self._plans.get(section_type)

    def get_all_queries(self, section_types: Optional[List[str]] = None) -> List[str]:
        types = section_types or list(self._plans.keys())
        queries = []
        for st in types:
            plan = self._plans.get(st)
            if plan:
                queries.extend(plan.queries)
        return queries

    def reset(self):
        self._plans.clear()
