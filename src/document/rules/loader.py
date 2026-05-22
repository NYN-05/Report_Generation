import json
import os
import re
from typing import Dict, Optional, List

from .models import ReportRules, SectionRule, GlobalRules
from src.core.logger import get_logger

logger = get_logger(__name__)

SECTION_TYPE_ALIASES: Dict[str, List[str]] = {
    "introduction": ["introduction", "intro", "1. introduction", "chapter 1"],
    "literature_review": ["literature review", "literature survey", "lit review", "background", "related work"],
    "methodology": ["methodology", "method", "research method", "system design", "approach"],
    "implementation": ["implementation", "system implementation", "development", "coding"],
    "results": ["results", "findings", "experimental results", "outcomes"],
    "discussion": ["discussion", "analysis", "evaluation", "results and discussion"],
    "conclusion": ["conclusion", "summary", "conclusion and future work", "final"],
    "chapters": ["chapters", "chapter", "main body", "core content"],
    "certificate": ["certificate", "certification", "approval"],
    "declaration": ["declaration", "declaration by candidate"],
    "acknowledgement": ["acknowledgement", "acknowledgment", "acknowledgements"],
    "abstract": ["abstract", "summary", "executive summary"],
    "references": ["references", "bibliography", "works cited"],
    "appendices": ["appendices", "appendix", "appendix a"],
}


class RulesLoader:
    """Loads report writing rules from JSON or Markdown files."""

    def __init__(self, rules_dir: Optional[str] = None):
        self._rules_dir = rules_dir or os.path.join(
            os.path.dirname(__file__), ""
        )

    def load_default(self) -> ReportRules:
        path = os.path.join(self._rules_dir, "default_rules.json")
        if os.path.exists(path):
            return self.load_json(path)
        logger.warning("default_rules.json not found, using built-in defaults")
        return self._builtin_defaults()

    def load_json(self, path: str) -> ReportRules:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Rules file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ReportRules.from_dict(data)

    def load_markdown(self, path: str) -> ReportRules:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Rules file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return self._parse_markdown(text)

    def load(self, path: str) -> ReportRules:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":
            return self.load_json(path)
        elif ext in (".md", ".markdown"):
            return self.load_markdown(path)
        else:
            raise ValueError(f"Unsupported rules file format: {ext}")

    def parse_rules_text(self, text: str, fmt: str = "auto") -> ReportRules:
        text = text.strip()
        if fmt == "json" or text.startswith("{"):
            return ReportRules.from_dict(json.loads(text))
        return self._parse_markdown(text)

    def _parse_markdown(self, text: str) -> ReportRules:
        global_rules: Dict[str, list] = {}
        section_rules: Dict[str, Dict[str, list]] = {}
        current_category: str = ""
        current_section: str = ""
        current_rules: list = []

        for line in text.split("\n"):
            stripped = line.strip()

            if stripped.startswith("## ") and "global" in stripped.lower():
                current_category = "global"
                current_section = ""
                if current_rules and current_section:
                    section_rules.setdefault(current_section, {})["rules"] = current_rules
                current_rules = []
                continue

            h2_match = re.match(r"^##\s+(.+)$", stripped)
            if h2_match:
                if current_rules and current_section:
                    section_rules.setdefault(current_section, {})["rules"] = current_rules
                current_category = h2_match.group(1).strip().lower()
                current_section = ""
                current_rules = []

                if "section" in current_category or "type" in current_category:
                    pass
                elif current_category != "global":
                    current_category = ""
                continue

            h3_match = re.match(r"^###\s+(.+)$", stripped)
            if h3_match:
                if current_rules and current_section:
                    section_rules.setdefault(current_section, {})["rules"] = current_rules
                current_section = h3_match.group(1).strip()
                current_rules = []
                continue

            if stripped.startswith("- ") or stripped.startswith("* "):
                rule_text = stripped[2:].strip()
                current_rules.append(rule_text)

        if current_rules and current_section:
            section_rules.setdefault(current_section, {})["rules"] = current_rules

        return self._build_rules_from_parsed(global_rules, section_rules)

    def _build_rules_from_parsed(
        self,
        global_rules: dict,
        section_rules: Dict[str, Dict[str, list]],
    ) -> ReportRules:
        global_data = self._extract_global_values(global_rules.get("rules", []))
        glob = GlobalRules(**{k: v for k, v in global_data.items() if k in GlobalRules.__dataclass_fields__})

        section_types: Dict[str, SectionRule] = {}
        for name, data in section_rules.items():
            raw_rules = data.get("rules", [])
            section_id = self._resolve_section_id(name)
            if section_id is None:
                section_id = name.lower().replace(" ", "_")
            parsed = self._parse_section_bullets(raw_rules)
            if parsed:
                section_types[section_id] = SectionRule(**parsed)

        return ReportRules(
            rules_version="1.0",
            global_=glob,
            section_types=section_types,
            metadata={"source": "markdown"},
        )

    def _resolve_section_id(self, name: str) -> Optional[str]:
        name_lower = name.lower().strip()
        for section_id, aliases in SECTION_TYPE_ALIASES.items():
            for alias in aliases:
                if alias in name_lower or name_lower in alias:
                    return section_id
        return None

    def _extract_global_values(self, rules: List[str]) -> dict:
        result: dict = {}
        for rule in rules:
            rule_lower = rule.lower()
            m = re.search(r"(\d+)\s+paragraph", rule_lower)
            if m:
                result["min_paragraphs_per_section"] = max(
                    result.get("min_paragraphs_per_section", 0), int(m.group(1))
                )
            m = re.search(r"(\d+)\s+word", rule_lower)
            if m:
                result["min_words_per_section"] = max(
                    result.get("min_words_per_section", 0), int(m.group(1))
                )
            if "data point" in rule_lower or "statistic" in rule_lower:
                result["require_data_points"] = True
            if "example" in rule_lower:
                result["require_examples"] = True
            if "active voice" in rule_lower:
                result["use_active_voice"] = True
        return result

    def _parse_section_bullets(self, rules: List[str]) -> dict:
        result: dict = {}
        structure_items: List[str] = []

        for rule in rules:
            rule_lower = rule.lower()

            m = re.search(r"(\d+)\s+paragraph", rule_lower)
            if m:
                result["min_paragraphs"] = max(result.get("min_paragraphs", 0), int(m.group(1)))

            m = re.search(r"(\d+)\s+word", rule_lower)
            if m:
                result["min_words"] = max(result.get("min_words", 0), int(m.group(1)))

            m = re.search(r"(\d+)\s+reference", rule_lower)
            if m:
                result["require_references"] = max(result.get("require_references", 0), int(m.group(1)))

            if "subsections" in rule_lower and "minimum" in rule_lower:
                m = re.search(r"(\d+)", rule_lower)
                if m:
                    result["min_subsections"] = int(m.group(1))
                    result["require_subsections"] = True

            if "cover" in rule_lower or "must include" in rule_lower or "covering" in rule_lower:
                after_cover = re.split(r"(?:cover|must include|covering)[:\s]", rule, flags=re.IGNORECASE)
                if len(after_cover) > 1:
                    items = [x.strip().rstrip(".") for x in re.split(r"[,;]", after_cover[1])]
                    structure_items.extend(x for x in items if x and len(x) > 3)

            if "data" in rule_lower or "statistic" in rule_lower:
                if "require" in rule_lower:
                    result["require_data_points"] = True

            if "example" in rule_lower and "require" in rule_lower:
                result["require_examples"] = True

        if structure_items:
            result["structure"] = structure_items

        return result

    def _builtin_defaults(self) -> ReportRules:
        glob = GlobalRules()
        section_types = {
            "introduction": SectionRule(
                min_paragraphs=6, min_words=700,
                structure=["background", "problem statement", "objectives", "scope", "methodology overview", "report organization"],
                require_data_points=True, require_examples=True,
            ),
            "literature_review": SectionRule(
                min_paragraphs=6, min_words=800,
                structure=["existing work", "gap analysis", "theoretical framework"],
                require_references=8, require_data_points=True,
            ),
            "methodology": SectionRule(
                min_paragraphs=5, min_words=600,
                structure=["research design", "data collection", "experimental setup", "evaluation metrics"],
                require_data_points=True,
            ),
            "chapters": SectionRule(
                min_paragraphs=5, min_words=600,
                require_subsections=True, min_subsections=3,
                require_data_points=True, require_examples=True,
            ),
            "conclusion": SectionRule(
                min_paragraphs=4, min_words=400,
                structure=["summary of findings", "contributions", "limitations", "future work"],
                require_data_points=True,
            ),
            "abstract": SectionRule(
                min_paragraphs=3, min_words=300,
                structure=["background context", "approach", "key findings"],
            ),
        }
        return ReportRules(global_=glob, section_types=section_types, metadata={"source": "builtin_defaults"})
