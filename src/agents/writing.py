"""
Writing Agent
=============
Generates section content with RAG evidence injection.
"""

from typing import Any, Dict, Optional, List
from .base import BaseAgent, AgentResponse
from src.core.logger import get_logger
from src.providers import Message, CompletionOptions

logger = get_logger(__name__)


class WritingAgent(BaseAgent):
    """Agent responsible for content generation with evidence from RAG.

    Responsibilities:
    - Generate section content using LLM with RAG context
    - Reference real sources from retrieval
    - Never fabricate citations
    """

    def __init__(self, provider=None, prompt_builder=None):
        super().__init__("writing", provider)
        self._prompt_builder = prompt_builder

    def set_prompt_builder(self, prompt_builder):
        self._prompt_builder = prompt_builder

    def execute(self, input_data: Any, **kwargs) -> AgentResponse:
        if not isinstance(input_data, dict):
            return self._create_response(False, error="Input must be a dict")

        topic = input_data.get("topic", "")
        section_heading = input_data.get("heading", "")
        section_type = input_data.get("section_type", "chapters")
        context_text = input_data.get("context_text", "")
        target_words = input_data.get("target_words", 500)
        report_type = input_data.get("report_type", "engineering project report")
        style_profile = input_data.get("style_profile")
        citation_instructions = input_data.get("citation_instructions", "")

        if not topic or not section_heading:
            return self._create_response(False, error="topic and heading required")

        prompt = self._build_prompt(
            topic, section_heading, section_type, context_text,
            target_words, report_type, style_profile, citation_instructions,
        )

        if not self.provider or not self.provider.is_available():
            return self._create_response(True, data={
                "content": f"[LLM unavailable] Generated content for: {section_heading}",
                "generated_via": "fallback",
            })

        try:
            messages = [
                Message(role="system", content="You are an academic report writer. Write in formal IEEE style. Never fabricate citations."),
                Message(role="user", content=prompt),
            ]
            opts = CompletionOptions(temperature=0.7, max_tokens=4096, timeout=120)
            response = self.provider.chat(messages, options=opts)

            return self._create_response(True, data={
                "content": response.content,
                "generated_via": "llm",
                "section_type": section_type,
                "word_count": len(response.content.split()),
            })

        except Exception as e:
            self._log_error("content generation", e)
            return self._create_response(True, data={
                "content": f"[Generation failed] Content for {section_heading}: "
                           f"Analyzing {topic} in the context of {section_heading}...",
                "generated_via": "error_fallback",
                "error": str(e),
            })

    def _build_prompt(self, topic, heading, section_type, context_text,
                      target_words, report_type, style_profile, citation_instructions) -> str:
        if self._prompt_builder:
            prompt = self._prompt_builder.build_prompt(
                section_type=section_type, topic=topic,
                report_type=report_type, target_words=target_words,
                retrieval_context=context_text,
                citation_instructions=citation_instructions,
                style_profile=style_profile,
            )
            if prompt:
                return prompt

        parts = [
            f"Write the {heading} section for a {report_type} on: {topic}",
            "",
            "Requirements:",
            "- IEEE academic tone",
            "- Third-person formal writing",
            f"- {target_words} words minimum",
            "- Use technical terminology",
            "- Never fabricate citations or references",
        ]
        if context_text:
            parts.append("")
            parts.append("Reference Material (use to support claims):")
            parts.append(context_text)
        return "\n".join(parts)

    def generate_section(self, topic: str, heading: str, section_type: str = "chapters",
                         context_text: str = "", target_words: int = 500,
                         report_type: str = "report") -> str:
        result = self.execute({
            "topic": topic, "heading": heading, "section_type": section_type,
            "context_text": context_text, "target_words": target_words,
            "report_type": report_type,
        })
        return result.data.get("content", "") if result.success else ""

    def generate_subsections(self, topic: str, section_heading: str,
                              count: int = 3, context_text: str = "") -> List[str]:
        results = []
        for i in range(count):
            sub_heading = f"{section_heading} - Subsection {i+1}"
            content = self.generate_section(
                topic=topic, heading=sub_heading, context_text=context_text,
                target_words=200, report_type="report",
            )
            results.append(content)
        return results
