"""
Chapter Generator Module
========================
Generates chapter content.
"""

from typing import Dict, Any, Optional
from src.core.logger import get_logger
from src.providers import get_default_provider, Message

logger = get_logger(__name__)


class ChapterGenerator:
    """Generates chapter content using LLM."""

    def __init__(self, provider=None):
        self.provider = provider or get_default_provider()

    def generate_chapter(
        self,
        title: str,
        topic: str,
        previous_content: Optional[str] = None
    ) -> str:
        """Generate content for a chapter."""
        if not self.provider or not self.provider.is_available():
            return self._fallback_chapter(title, topic)

        prompt = f"""Generate a chapter section for:

Title: {title}
Topic: {topic}
Previous context: {previous_content or "None"}

Write a comprehensive paragraph suitable for a professional report chapter.
Include relevant details and analysis.
Return ONLY the chapter content, no introduction or summary."""

        try:
            messages = [
                Message(role="system", content="You write professional report chapters."),
                Message(role="user", content=prompt)
            ]

            response = self.provider.chat(messages)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Chapter generation failed: {e}")
            return self._fallback_chapter(title, topic)

    def generate_introduction(self, title: str, topic: str) -> str:
        """Generate an introduction section."""
        return self.generate_chapter(f"Introduction to {title}", topic)

    def generate_conclusion(self, topic: str) -> str:
        """Generate a conclusion section."""
        if not self.provider or not self.provider.is_available():
            return f"In conclusion, this report has addressed key aspects of {topic}."

        prompt = f"""Write a conclusion for a report on: {topic}

Summarize the key points and provide final thoughts.
Return ONLY the conclusion, 2-3 paragraphs."""

        try:
            messages = [
                Message(role="system", content="You write professional conclusions."),
                Message(role="user", content=prompt)
            ]

            response = self.provider.chat(messages)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Conclusion generation failed: {e}")
            return f"In conclusion, this report has addressed key aspects of {topic}."

    def expand_section(
        self,
        original_content: str,
        expansion_topic: str
    ) -> str:
        """Expand an existing section with more detail."""
        if not self.provider or not self.provider.is_available():
            return original_content + "\n\n" + f"Additional information on {expansion_topic}."

        prompt = f"""Expand the following content with more detail on: {expansion_topic}

Original content:
{original_content}

Return the expanded content that adds relevant detail while maintaining flow."""

        try:
            messages = [
                Message(role="system", content="You expand report sections with relevant detail."),
                Message(role="user", content=prompt)
            ]

            response = self.provider.chat(messages)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Section expansion failed: {e}")
            return original_content

    def _fallback_chapter(self, title: str, topic: str) -> str:
        """Generate fallback chapter content."""
        return f"This chapter covers {title} related to {topic}. " \
               f"The following sections provide detailed analysis and insights."


class SectionFactory:
    """Factory for creating different section types."""

    @staticmethod
    def create_chapter(title: str, content: str) -> Dict[str, str]:
        """Create a chapter section."""
        return {
            "type": "chapter",
            "heading": title,
            "content": content
        }

    @staticmethod
    def create_intro(title: str, content: str) -> Dict[str, str]:
        """Create an introduction section."""
        return {
            "type": "introduction",
            "heading": title,
            "content": content
        }

    @staticmethod
    def create_conclusion(content: str) -> Dict[str, str]:
        """Create a conclusion section."""
        return {
            "type": "conclusion",
            "heading": "Conclusion",
            "content": content
        }

    @staticmethod
    def create_summary(content: str) -> Dict[str, str]:
        """Create an executive summary."""
        return {
            "type": "summary",
            "heading": "Executive Summary",
            "content": content
        }