from typing import List, Tuple

from .models import Blueprint, ReportPlan
from src.core.logger import get_logger

logger = get_logger(__name__)


class BlueprintValidator:
    """Validates report plans against their blueprints."""

    def validate(self, plan: ReportPlan, blueprint: Blueprint) -> List[str]:
        errors: List[str] = []

        errors.extend(self._check_mandatory_sections(plan, blueprint))
        errors.extend(self._check_section_order(plan, blueprint))
        errors.extend(self._check_references(plan, blueprint))
        errors.extend(self._check_numbering(plan))
        errors.extend(self._check_pages(plan))

        if errors:
            logger.warning(f"Blueprint validation found {len(errors)} issues")
        else:
            logger.info("Blueprint validation passed")

        return errors

    def validate_with_warnings(self, plan: ReportPlan, blueprint: Blueprint
                                ) -> Tuple[List[str], List[str]]:
        errors = self.validate(plan, blueprint)
        warnings = self._get_warnings(plan, blueprint)
        return errors, warnings

    def _check_mandatory_sections(self, plan: ReportPlan,
                                   blueprint: Blueprint) -> List[str]:
        errors = []
        mandatory_ids = {s.id for s in blueprint.sections if s.mandatory}
        plan_ids = {s.blueprint_section_id for s in plan.sections}

        for mid in mandatory_ids:
            if mid not in plan_ids and mid not in ("cover_page", "table_of_contents",
                                                    "list_of_figures", "list_of_tables"):
                errors.append(f"Mandatory section missing: '{mid}'")

        return errors

    def _check_section_order(self, plan: ReportPlan,
                              blueprint: Blueprint) -> List[str]:
        errors = []
        bp_order = [s.id for s in blueprint.sections
                    if s.id not in ("cover_page", "table_of_contents",
                                    "list_of_figures", "list_of_tables")]
        plan_ids = [s.blueprint_section_id for s in plan.sections]

        seen = set()
        last_bp_idx = -1
        for pid in plan_ids:
            if pid not in bp_order:
                continue
            if pid not in seen:
                seen.add(pid)
                bp_idx = bp_order.index(pid)
                if bp_idx < last_bp_idx:
                    errors.append(f"Section '{pid}' appears out of order "
                                  f"(expected after previous sections)")
                last_bp_idx = bp_idx

        return errors

    def _check_references(self, plan: ReportPlan, blueprint: Blueprint) -> List[str]:
        errors = []
        has_refs_section = any(s.blueprint_section_id == "references" for s in plan.sections)
        if has_refs_section and blueprint.references_style and plan.total_references <= 0:
            errors.append("No references planned (blueprint expects references)")
        if plan.references and len(plan.references) != plan.total_references:
            errors.append(f"Reference count mismatch: planned {plan.total_references}, "
                          f"provided {len(plan.references)}")
        return errors

    def _check_numbering(self, plan: ReportPlan) -> List[str]:
        errors = []
        chapter_count = 0
        for s in plan.sections:
            if s.level == 1 and s.blueprint_section_id not in (
                    "certificate", "declaration", "acknowledgement", "abstract",
                    "references", "appendices"):
                chapter_count += 1

        seen_numbers = set()
        for s in plan.sections:
            import re
            num_match = re.match(r'^(\d+)\.', s.heading)
            if num_match:
                num = int(num_match.group(1))
                if num in seen_numbers:
                    errors.append(f"Duplicate chapter number {num}: '{s.heading}'")
                seen_numbers.add(num)

        return errors

    def _check_pages(self, plan: ReportPlan) -> List[str]:
        errors = []
        if plan.total_pages <= 0:
            errors.append("Total pages must be greater than 0")
        return errors

    def _get_warnings(self, plan: ReportPlan, blueprint: Blueprint) -> List[str]:
        warnings = []

        for s in plan.sections:
            if s.allocated_pages <= 0 and s.content:
                warnings.append(f"Section '{s.heading}' has content but 0 pages allocated")

        if plan.total_figures <= 0 and blueprint.requires_lof:
            warnings.append("Blueprint requires List of Figures but no figures planned")

        if plan.total_tables <= 0 and blueprint.requires_lot:
            warnings.append("Blueprint requires List of Tables but no tables planned")

        return warnings

    def is_valid(self, plan: ReportPlan, blueprint: Blueprint) -> bool:
        return len(self.validate(plan, blueprint)) == 0
