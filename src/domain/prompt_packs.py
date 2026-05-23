from typing import Dict, List, Optional
from src.core.logger import get_logger
from .classifier import DomainClassifier

logger = get_logger(__name__)


DOMAIN_PROMPT_INSTRUCTIONS = {
    "computer_science": (
        "Write with technical precision. Use domain-specific terminology "
        "from computer science (algorithms, data structures, computational complexity, "
        "system architecture). Reference specific methods, frameworks, and techniques. "
        "Include technical metrics where evidence supports them."
    ),
    "engineering": (
        "Write with engineering rigor. Reference standards, specifications, and "
        "design principles. Use quantitative analysis and technical parameters. "
        "Discuss trade-offs, constraints, and optimization criteria."
    ),
    "biomedical": (
        "Write with scientific precision. Use proper medical/scientific terminology. "
        "Reference clinical studies, experimental protocols, and statistical measures. "
        "Maintain appropriate caution in causal claims."
    ),
    "business": (
        "Write with analytical business focus. Use strategic frameworks and "
        "management terminology. Reference market dynamics, competitive analysis, "
        "and business metrics where evidence permits."
    ),
    "social_science": (
        "Write with methodological rigor. Reference research design, sampling methods, "
        "and statistical analysis. Maintain appropriate caveats about generalizability "
        "and correlation vs causation."
    ),
    "natural_science": (
        "Write with scientific objectivity. Reference experimental methods, "
        "observational data, and theoretical frameworks. Use appropriate scientific "
        "notation and maintain precision in quantitative claims."
    ),
}

SECTION_DOMAIN_FOCUS = {
    "introduction": {
        "computer_science": "Emphasize research problems, computational challenges, and technical motivation.",
        "engineering": "Emphasize design challenges, performance requirements, and engineering constraints.",
        "biomedical": "Emphasize clinical need, biological mechanisms, and medical significance.",
        "business": "Emphasize market problems, strategic importance, and organizational context.",
        "social_science": "Emphasize social phenomena, research questions, and theoretical context.",
        "natural_science": "Emphasize scientific questions, natural phenomena, and theoretical foundations.",
    },
    "methodology": {
        "computer_science": "Detail system architecture, algorithmic choices, and implementation decisions.",
        "engineering": "Detail design methodology, component selection, and validation approach.",
        "biomedical": "Detail experimental protocol, sample selection, and measurement methods.",
        "business": "Detail analytical framework, data sources, and evaluation criteria.",
        "social_science": "Detail research design, sampling strategy, and analytical methods.",
        "natural_science": "Detail experimental setup, measurement techniques, and data collection.",
    },
}


class DomainSpecificPromptPacks:
    def __init__(self):
        self._domain = "computer_science"

    def set_domain(self, domain: str):
        self._domain = domain

    def get_system_instruction(self, domain: Optional[str] = None) -> str:
        d = domain or self._domain
        return DOMAIN_PROMPT_INSTRUCTIONS.get(d, DOMAIN_PROMPT_INSTRUCTIONS["computer_science"])

    def get_section_instruction(self, section_type: str,
                                 domain: Optional[str] = None) -> str:
        d = domain or self._domain
        section_focus = SECTION_DOMAIN_FOCUS.get(section_type, {})
        return section_focus.get(d, "Write with academic rigor appropriate to the domain.")

    def get_evidence_instruction(self, domain: Optional[str] = None) -> str:
        d = domain or self._domain
        if d == "computer_science":
            return "Ground every technical claim in specific evidence from retrieved sources."
        elif d == "engineering":
            return "Support all design decisions and performance claims with evidence from references."
        elif d == "biomedical":
            return "Cite specific studies and clinical evidence for all medical/scientific claims."
        elif d == "business":
            return "Base all market claims and strategic analysis on provided evidence."
        return "Every claim must be directly supported by the provided evidence chunks."

    def get_domain_terminology(self, domain: Optional[str] = None) -> List[str]:
        from .classifier import DOMAIN_KEYWORDS
        d = domain or self._domain
        return DOMAIN_KEYWORDS.get(d, DOMAIN_KEYWORDS["computer_science"])
