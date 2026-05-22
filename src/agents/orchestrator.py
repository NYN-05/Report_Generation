"""
Orchestrator Agent Module
=========================
Main orchestration agent that coordinates task execution.
"""

import json
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

            content = self._extract_json(response.content)
            if content is not None:
                self._log_info(f"Generated content with {len(skills)} skills")
                return content

            raise ValueError("No valid JSON in response")

        except Exception as e:
            self._log_error("content generation", e)
            return self._generate_fallback_content(task, skills)

    def _extract_json(self, text: str) -> Optional[Dict]:
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*```$', '', text)

        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if not json_match:
            return None

        raw = json_match.group()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        fixed = re.sub(r"(?<!\\)'(.*?)'(?=\s*:)", r'"\1"', raw)
        fixed = re.sub(r":\s*'(.*?)'(?=[\s,}])", r': "\1"', fixed)
        fixed = re.sub(r",\s*}", "}", fixed)
        fixed = re.sub(r",\s*]", "]", fixed)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        fixed2 = re.sub(r'//[^\n]*', '', fixed)
        try:
            return json.loads(fixed2)
        except json.JSONDecodeError:
            return None

    def _generate_fallback_content(self, task: str, skills: List[Skill] = None) -> Dict:
        """Generate content guided by selected skill knowledge when LLM is unavailable."""
        from datetime import datetime
        import re as _re
        current_date = datetime.now().strftime("%B %Y")
        title = task.title()

        skill_terms = set()
        skill_descriptions = []
        skill_section = None
        if skills:
            for skill in skills:
                if skill.description:
                    skill_descriptions.append(skill.description)
                    words = _re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', skill.description)
                    skill_terms.update(w.lower() for w in words if len(w) > 3)
                    skill_terms.update(t.lower() for t in skill.tags if len(t) > 2)
                    skill_terms.update(k.lower() for k in skill.keywords if len(k) > 2)

                    full = self.skill_registry.get_full_content(skill.name)
                    if full:
                        lines = [l.strip() for l in full.split('\n') if l.strip() and not l.startswith('---')]
                        body = ' '.join(lines[:30])
                        key_phrases = _re.findall(r'\*\*([^*]+)\*\*', body)
                        skill_terms.update(p.lower().strip() for p in key_phrases if len(p.strip()) > 3)

            if skill_descriptions:
                combined = ' '.join(skill_descriptions)
                first_skill = skills[0]
                skill_section = {
                    "heading": f"Application of {first_skill.name.title()} Principles",
                    "content": (
                        f"The {first_skill.name} framework provides structured guidance relevant to {task}. "
                        f"{first_skill.description[:300]}\n\n"
                        f"Applying these principles to {task} requires careful consideration of "
                        f"best practices and established methodologies in this domain. "
                        f"The key areas covered include understanding core concepts, "
                        f"implementing effective solutions, and following industry standards.\n\n"
                        f"By leveraging the knowledge embedded in this skill, practitioners can "
                        f"approach {task} with a structured methodology that has been refined "
                        f"through practical application and community feedback. This ensures "
                        f"that implementations are both robust and aligned with current best practices."
                    )
                }

        term_list = list(skill_terms)[:12]
        term_context = ", ".join(term_list[:6]) if term_list else "key concepts"

        sections = [
            {
                "heading": "Current Landscape and Key Developments",
                "content": (
                    f"The current landscape of {task} is characterized by several concurrent "
                    f"trends that are reshaping how organizations approach this domain. "
                    f"Adoption rates have accelerated significantly, with both early adopters "
                    f"and mainstream organizations investing substantial resources.\n\n"
                    f"One of the most significant developments is the increasing convergence of "
                    f"previously disparate technologies and methodologies in areas such as "
                    f"{term_context}. This convergence is creating new capabilities that were "
                    f"not feasible just a few years ago, enabling organizations to tackle "
                    f"complex challenges with integrated solutions.\n\n"
                    f"Market leaders are investing heavily in research and development, pushing "
                    f"the boundaries of what is possible. At the same time, a vibrant ecosystem "
                    f"of startups and open-source initiatives is democratizing access and driving "
                    f"innovation from multiple directions."
                )
            },
            {
                "heading": "Detailed Analysis",
                "content": (
                    f"A deeper examination of {task} reveals several important patterns and "
                    f"dynamics that merit careful consideration. First, the rate of change "
                    f"continues to accelerate, with new developments emerging on a weekly "
                    f"rather than monthly or yearly basis. This rapid pace creates both "
                    f"opportunities and challenges for organizations trying to stay current.\n\n"
                    f"Second, the barriers to entry are shifting. While some aspects of the "
                    f"domain are becoming more accessible through improved tools and platforms, "
                    f"other areas are requiring deeper expertise and more sophisticated infrastructure. "
                    f"This dual dynamic is reshaping the competitive landscape in significant ways.\n\n"
                    f"Third, we observe a growing emphasis on practical, real-world applications "
                    f"over theoretical exploration. Organizations are increasingly focused on "
                    f"deploying solutions that deliver measurable business value, driving a shift "
                    f"toward more pragmatic approaches.\n\n"
                    f"Key technical areas such as {term_context} are central to this evolution, "
                    f"representing critical focus areas for organizations seeking to build "
                    f"competitive advantage in the {task} space."
                )
            },
            {
                "heading": "Challenges and Opportunities",
                "content": (
                    f"Organizations operating in the {task} space face several significant "
                    f"challenges that must be addressed to realize the full potential of "
                    f"their initiatives. Talent acquisition and development remains a critical "
                    f"concern, with demand for skilled practitioners far outstripping supply. "
                    f"Organizations must invest in training and development programs to build "
                    f"internal capabilities.\n\n"
                    f"Technical debt and legacy system integration pose another major challenge. "
                    f"Many organizations struggle to modernize existing infrastructure while "
                    f"simultaneously adopting new approaches. A phased, strategic approach to "
                    f"modernization is essential to manage risk while maintaining momentum.\n\n"
                    f"However, these challenges are matched by significant opportunities. "
                    f"Early movers who successfully navigate the current landscape can "
                    f"establish substantial competitive advantages. The potential for "
                    f"innovation remains high, with numerous unexplored areas and applications "
                    f"within {term_context} and related fields."
                )
            },
            {
                "heading": "Strategic Recommendations",
                "content": (
                    f"Based on our analysis of {task}, we offer the following strategic "
                    f"recommendations for organizations seeking to maximize their effectiveness "
                    f"in this domain.\n\n"
                    f"First, invest in building foundational capabilities before pursuing advanced "
                    f"applications. Organizations that rush to implement cutting-edge solutions "
                    f"without solid foundations often encounter setbacks that could have been "
                    f"avoided with more measured approaches.\n\n"
                    f"Second, adopt a portfolio approach to investment in this space. Rather than "
                    f"betting on a single technology or approach, maintain a balanced portfolio "
                    f"that includes both incremental improvements and transformative initiatives. "
                    f"This approach manages risk while maintaining the potential for breakthrough results.\n\n"
                    f"Third, prioritize continuous learning and adaptation. Given the rapid pace "
                    f"of change, organizations must build learning into their operational DNA. "
                    f"This includes formal training programs, participation in professional communities, "
                    f"and dedicated time for experimentation and exploration.\n\n"
                    f"Finally, emphasize measurement and evaluation. Establish clear metrics for "
                    f"success and regularly assess progress against these benchmarks. "
                    f"Data-driven decision-making is essential for navigating the complexities "
                    f"of this evolving landscape."
                )
            }
        ]

        if skill_section:
            sections.insert(2, skill_section)

        return {
            "title": f"Comprehensive Report on {title}",
            "subtitle": "In-Depth Analysis and Strategic Insights",
            "author": "AI Report Generator",
            "date": current_date,
            "toc_entries": [
                "Executive Summary",
                "Introduction and Background",
                *(s["heading"] for s in sections),
                "Conclusion"
            ],
            "executive_summary": (
                f"This report provides a comprehensive analysis of {task}, examining its current state, "
                f"key developments, and future trajectory. Drawing on domain expertise in "
                f"{term_context}, we identify critical challenges and opportunities that shape "
                f"decision-making in this area. The analysis offers actionable insights for "
                f"practitioners and stakeholders navigating this evolving landscape."
            ),
            "introduction": (
                f"The domain of {task} has undergone substantial transformation in recent years, "
                f"driven by rapid technological advancement, evolving market dynamics, and shifting "
                f"regulatory frameworks. Understanding these changes is essential for organizations "
                f"seeking to maintain competitive advantage and make informed strategic decisions.\n\n"
                f"This report aims to provide a thorough examination of the current state of {task}, "
                f"tracing its evolution and identifying the key forces shaping its trajectory. "
                f"We explore the technical, economic, and organizational dimensions that define "
                f"this space, offering readers a holistic perspective on where things stand today "
                f"and where they are heading.\n\n"
                f"Drawing on relevant expertise in {term_context}, this analysis is structured to "
                f"first establish foundational context, then examine specific developments in detail, "
                f"and finally synthesize findings into actionable recommendations for practitioners "
                f"and decision-makers."
            ),
            "sections": sections,
            "conclusion": (
                f"The landscape of {task} continues to evolve rapidly, presenting both significant "
                f"opportunities and formidable challenges. Organizations that approach this domain "
                f"with strategic foresight, balanced investment, and a commitment to continuous "
                f"learning will be best positioned to succeed.\n\n"
                f"The key takeaway from this analysis is that success in {task} requires more than "
                f"simply adopting the latest technologies or methodologies. It demands a holistic "
                f"approach that considers technical, organizational, and strategic dimensions in "
                f"an integrated fashion.\n\n"
                f"As the domain continues to mature, we expect to see further convergence, "
                f"increased standardization, and growing emphasis on practical, measurable outcomes. "
                f"Organizations that position themselves accordingly will be well-prepared for "
                f"the opportunities that lie ahead."
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