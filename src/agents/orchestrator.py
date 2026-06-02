"""
Orchestrator Agent Module
=========================
Main orchestration agent that coordinates task execution.
"""

import re
from typing import Dict, Any, List, Optional
from .base import BaseAgent, AgentResponse
from src.providers import BaseProvider, Message
from src.skills import SkillRegistry, Skill
from src.memory import ContextManager
from src.core.logger import get_logger
from src.core.constants import ExecutionMode

logger = get_logger(__name__)


class OrchestratorAgent(BaseAgent):
    """Main orchestrator for intelligent task execution."""

    def __init__(
        self,
        provider: Optional[BaseProvider] = None,
        execution_mode: ExecutionMode = ExecutionMode.SCRATCH,
        template_path: Optional[str] = None
    ):
        super().__init__("orchestrator", provider)
        self.execution_mode = execution_mode
        self.template_path = template_path
        self.skill_registry = SkillRegistry()
        self.context_manager = ContextManager()
        self._init_skills()

    def _init_skills(self):
        """Initialize skill registry."""
        count = self.skill_registry.initialize()
        self._log_info(f"Initialized {count} skills")

    def execute(self, input_data: Any, **kwargs) -> AgentResponse:
        """Execute orchestration workflow."""
        if isinstance(input_data, str):
            task = input_data
        elif isinstance(input_data, dict):
            task = input_data.get('task', '')
        else:
            return self._create_response(False, error="Invalid input format")

        if not task:
            return self._create_response(False, error="No task provided")

        self._log_info(f"Starting orchestration for: {task}")
        self._log_info(f"Execution mode: {self.execution_mode.value}")

        try:
            understanding = self._understand_task(task)
            if not understanding['success']:
                return self._create_response(False, error=understanding['error'])

            skills_query = self._build_skills_query(understanding['data'])
            skills = self.skill_registry.find_for_task(skills_query)
            self._log_info(f"Selected {len(skills)} skills: {[s.name for s in skills]} (query: {skills_query})")
            
            content = self._generate_with_skills(task, skills)

            session = self.context_manager.get_context()
            self.context_manager.update_context(
                session.session_id,
                task=task,
                skills_used=[s.name for s in skills]
            )

            return self._create_response(
                success=True,
                data={
                    'task': task,
                    'skills_used': [s.name for s in skills],
                    'content': content,
                    'mode': self.execution_mode.value,
                    'template_path': self.template_path,
                    'understanding': understanding['data']
                },
                metadata={'skill_count': len(skills)}
            )

        except Exception as e:
            self._log_error("orchestration", e)
            return self._create_response(False, error=str(e), data={'task': task})

    def _understand_task(self, task: str) -> Dict:
        """Use LLM to understand the task."""
        prompt = f"""Analyze this user request and extract key information:

Request: {task}

Provide a JSON response with:
- "intent": The main intent (create, analyze, modify, edit, extract, convert)
- "domain": The domain/topic
- "format": Expected output format (docx, pdf, html, etc.)
- "complexity": simple/medium/complex
- "requires_template": Does this need an existing template? (true/false)

Return ONLY valid JSON, no other text."""

        if not self.provider or not self.provider.is_available():
            return {
                'success': True,
                'data': {
                    'intent': 'create',
                    'domain': task,
                    'format': 'docx',
                    'complexity': 'medium',
                    'requires_template': self.template_path is not None
                }
            }

        try:
            messages = [
                Message(role="system", content="You analyze user requests and extract structured information."),
                Message(role="user", content=prompt)
            ]

            response = self.provider.chat(messages)

            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                data['requires_template'] = data.get('requires_template', self.template_path is not None)
                return {'success': True, 'data': data}

            return {
                'success': True,
                'data': {
                    'intent': 'unknown',
                    'domain': task,
                    'format': 'docx',
                    'complexity': 'medium',
                    'requires_template': self.template_path is not None
                }
            }

        except Exception as e:
            self._log_error("task understanding", e)
            return {'success': False, 'error': str(e)}

    def _build_skills_query(self, understanding: Dict) -> str:
        intent = understanding.get('intent', 'create')
        fmt = understanding.get('format', 'docx') or 'docx'
        complexity = understanding.get('complexity', 'medium') or 'medium'
        mode = self.execution_mode.value

        parts = [intent, fmt, mode, complexity]

        if understanding.get('requires_template'):
            parts.append('template')

        action_keywords = {
            'create': ['generate', 'build', 'write', 'produce', 'generate report', 'document creation'],
            'analyze': ['extract', 'read', 'parse', 'inspect', 'analyze document'],
            'modify': ['edit', 'update', 'change', 'revise', 'edit document'],
            'convert': ['transform', 'export', 'render', 'convert format'],
            'extract': ['read', 'parse', 'analyze', 'extract content'],
        }

        for kw in action_keywords.get(intent, []):
            parts.append(kw)

        if fmt == 'docx':
            parts.append('.docx')
        elif fmt == 'pdf':
            parts.append('.pdf')

        return ' '.join(p for p in parts if p)

    def _generate_with_skills(self, task: str, skills: List[Skill]) -> Dict:
        """Generate content with skill context."""
        skill_context = ""
        if skills:
            skill_parts = []
            for skill in skills:
                content = self.skill_registry.get_skill_content(skill.name, 1500)
                if content:
                    skill_parts.append(f"## {skill.name}\n{content}")
            skill_context = "\n\n---\n\n".join(skill_parts)

        template_instruction = ""
        if self.execution_mode == ExecutionMode.TEMPLATE and self.template_path:
            template_instruction = f"""
You are editing an existing document template at: {self.template_path}
Generate content that fits within the existing template structure.
Preserve formatting and structure from the template.
"""

        prompt = f"""Generate a comprehensive, substantive report based on this request: {task}
{template_instruction}
Use the following skill guidelines if relevant:
{skill_context}

Requirements:
- Write in a professional, analytical tone suitable for business/technical audiences
- Each section should have 3-6 detailed paragraphs with specific analysis, examples, and insights
- Include concrete details, data points, and practical observations — avoid generic filler
- Use active voice and varied sentence structure
- Sections should flow logically from one to the next

Generate a JSON response with:
- "title": Report title (descriptive and specific)
- "subtitle": Report subtitle
- "author": Author name(s) — use "AI Report Generator"
- "date": Current date (Month Year)
- "toc_entries": Array of 4-6 section titles
- "executive_summary": 3-5 sentence overview of the entire report
- "introduction": 2-3 paragraph introduction setting context
- "sections": Array of 4-6 section objects with "heading" and "content" (each content should be 3-6 paragraphs)
- "conclusion": 2-3 paragraph conclusion with key takeaways

Return ONLY valid JSON."""

        if not self.provider or not self.provider.is_available():
            return self._generate_fallback_content(task, skills)

        try:
            messages = [
                Message(
                    role="system",
                    content="You generate comprehensive, well-structured reports based on user requests."
                ),
                Message(role="user", content=prompt)
            ]

            response = self.provider.chat(messages)

            from src.core.utils import extract_json
            content = extract_json(response.content)
            if content is not None:
                self._log_info(f"Generated content with {len(skills)} skills")
                return content

            raise ValueError("No valid JSON in response")

        except Exception as e:
            self._log_error("content generation", e)
            return self._generate_fallback_content(task, skills)

    def _generate_fallback_content(self, task: str, skills: List[Skill] = None) -> Dict:
        """Return a clear error when LLM is unavailable, with no fabricated content."""
        from datetime import datetime
        current_date = datetime.now().strftime("%B %Y")
        title = task.title()
        
        return {
            "title": f"LLM Unavailable: {title}",
            "subtitle": "Report generation requires a running LLM provider (Ollama)",
            "author": "AI Report Generator",
            "date": current_date,
            "toc_entries": ["Error: LLM Not Available"],
            "executive_summary": (
                f"Report generation for '{task}' could not be completed because no LLM provider "
                f"is available. The system requires Ollama (or another configured provider) to be "
                f"running and accessible. Please ensure Ollama is installed and running, then retry."
            ),
            "introduction": (
                f"LLM Provider Unavailable\n\n"
                f"The report generation pipeline could not proceed because it requires a running "
                f"LLM provider. Currently only Ollama is supported. Please:\n"
                f"1. Install Ollama from https://ollama.ai\n"
                f"2. Start the Ollama service\n"
                f"3. Pull the required model: ollama pull llama3.2:3b\n"
                f"4. Retry generating the report"
            ),
            "sections": [
                {
                    "heading": "Next Steps",
                    "content": (
                        f"To generate a report on '{task}', please:\n"
                        f"- Ensure Ollama is running (http://localhost:11434)\n"
                        f"- Verify the model 'llama3.2:3b' is available\n"
                        f"- Run the pipeline again once the provider is accessible"
                    )
                }
            ],
            "conclusion": (
                f"The system is designed to produce evidence-based, knowledge-driven reports. "
                f"Without an LLM provider, it cannot generate meaningful content. "
                f"No fabricated or placeholder content has been inserted."
            )
        }

    def set_mode(self, mode: ExecutionMode, template_path: Optional[str] = None):
        """Set execution mode."""
        self.execution_mode = mode
        self.template_path = template_path
        self._log_info(f"Mode set to: {mode.value}")

    def get_available_skills(self) -> List[Dict]:
        """Get all available skills."""
        return self.skill_registry.list_skills()

    def explain_selection(self, task: str) -> str:
        """Explain why certain skills were selected."""
        skills = self.skill_registry.find_for_task(task)
        return self.skill_registry.explain_selection(task, skills)


def create_orchestrator(
    mode: ExecutionMode = ExecutionMode.SCRATCH,
    template_path: Optional[str] = None,
    provider: Optional[BaseProvider] = None
) -> OrchestratorAgent:
    """Factory function to create orchestrator."""
    return OrchestratorAgent(
        provider=provider,
        execution_mode=mode,
        template_path=template_path
    )