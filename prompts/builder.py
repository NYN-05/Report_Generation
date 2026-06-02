"""
Prompt Builder
==============
Dynamically constructs prompts from Jinja2 templates with injected context.

Architecture:
    Section Type + Template
        ↓
    Inject: Topic, Context, Citations, Style, Memory
        ↓
    Rendered Prompt String
"""

import os
from typing import Dict, Any, Optional
from src.core.logger import get_logger

logger = get_logger(__name__)

_here = os.path.dirname(os.path.abspath(__file__))
_TEMPLATE_DIR = os.path.join(os.path.dirname(_here), "prompts")

_PROMPT_VERSION = "2.0.0"
_PROMPT_VERSION_HISTORY = {
    "1.0.0": "Initial prompt templates",
    "2.0.0": "Added evidence-first instruction, strict no-hallucination enforcement, citation grounding",
}

_SECTION_VERSIONS = {
    "abstract": "2.0.0",
    "introduction": "2.0.0",
    "literature_review": "2.0.0",
    "methodology": "2.0.0",
    "implementation": "2.0.0",
    "results": "2.0.0",
    "discussion": "2.0.0",
    "conclusion": "2.0.0",
}


def get_prompt_version() -> str:
    return _PROMPT_VERSION


def get_prompt_version_history() -> dict:
    return dict(_PROMPT_VERSION_HISTORY)


def get_section_prompt_versions() -> dict:
    return dict(_SECTION_VERSIONS)


class PromptBuilder:
    """Builds section-specific prompts from Jinja2 templates.

    Supports:
    - Jinja2 template rendering with fallback to raw templates
    - Context injection (retrieval context, memory state, style profile)
    - Citation instructions injection
    - Chapter summary injection for cross-section coherence
    """

    SECTION_TEMPLATES = {
        "abstract": "abstract.jinja2",
        "introduction": "introduction.jinja2",
        "literature_review": "literature_review.jinja2",
        "methodology": "methodology.jinja2",
        "implementation": "implementation.jinja2",
        "results": "results.jinja2",
        "discussion": "discussion.jinja2",
        "conclusion": "conclusion.jinja2",
    }

    def __init__(self, template_dir: str = _TEMPLATE_DIR):
        self._template_dir = template_dir
        self._jinja2_available = False
        self._init_jinja2()

    def _init_jinja2(self):
        try:
            import jinja2
            self._env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(self._template_dir),
                autoescape=False,
            )
            self._jinja2_available = True
        except ImportError:
            logger.warning("jinja2 not available, using string templates")
        except Exception as e:
            logger.warning(f"Jinja2 init failed: {e}")

    def build_prompt(
        self,
        section_type: str,
        topic: str,
        report_type: str = "engineering project report",
        target_words: int = 500,
        retrieval_context: str = "",
        chapter_summary: str = "",
        citation_instructions: str = "",
        style_profile: Optional[Dict[str, Any]] = None,
        **extra_vars,
    ) -> Optional[str]:
        """Build a prompt for the given section type with injected context."""
        if section_type not in self.SECTION_TEMPLATES:
            logger.warning(f"No template for section type: {section_type}")
            return None

        if self._jinja2_available:
            return self._render_jinja2(
                section_type, topic, report_type, target_words,
                retrieval_context, chapter_summary,
                citation_instructions, style_profile, **extra_vars,
            )

        return self._fallback_render(
            section_type, topic, report_type, target_words,
            retrieval_context,
        )

    def _render_jinja2(
        self,
        section_type: str,
        topic: str,
        report_type: str,
        target_words: int,
        retrieval_context: str,
        chapter_summary: str,
        citation_instructions: str,
        style_profile: Optional[Dict[str, Any]] = None,
        **extra_vars,
    ) -> str:
        template_name = self.SECTION_TEMPLATES[section_type]
        section_version = _SECTION_VERSIONS.get(section_type, _PROMPT_VERSION)
        try:
            template = self._env.get_template(template_name)
            return template.render(
                topic=topic,
                report_type=report_type,
                target_words=target_words,
                retrieval_context=retrieval_context,
                chapter_summary=chapter_summary,
                citation_instructions=citation_instructions,
                style_profile=style_profile or {},
                prompt_version=section_version,
                **extra_vars,
            )
        except Exception as e:
            logger.warning(f"Jinja2 render failed for {template_name}: {e}")
            return self._fallback_render(
                section_type, topic, report_type, target_words, retrieval_context,
            )

    def _fallback_render(
        self,
        section_type: str,
        topic: str,
        report_type: str,
        target_words: int,
        retrieval_context: str,
    ) -> str:
        section_names = {
            "abstract": "abstract",
            "introduction": "introduction",
            "literature_review": "literature review",
            "methodology": "methodology",
            "implementation": "implementation",
            "results": "results",
            "discussion": "discussion",
            "conclusion": "conclusion",
        }
        section_label = section_names.get(section_type, section_type)

        prompt = (
            f"Write the {section_label} section for a {report_type} on: {topic}\n\n"
            f"Requirements:\n"
            f"- IEEE academic tone\n"
            f"- Third-person formal writing\n"
            f"- {target_words} words minimum\n"
            f"- Use technical terminology\n"
        )

        if retrieval_context:
            prompt += f"\nReference Material:\n{retrieval_context}\n"

        return prompt

    def list_available_templates(self) -> Dict[str, str]:
        """Return mapping of section type to template file path."""
        result = {}
        for section_type, filename in self.SECTION_TEMPLATES.items():
            full_path = os.path.join(self._template_dir, filename)
            exists = os.path.exists(full_path)
            result[section_type] = f"{filename} ({'exists' if exists else 'missing'})"
        return result
