"""
Research Agent
==============
Collects knowledge via RAG retrieval and source gathering.
"""

from typing import Any, Dict, Optional, List
from .base import BaseAgent, AgentResponse
from src.core.logger import get_logger

logger = get_logger(__name__)


class ResearchAgent(BaseAgent):
    """Agent responsible for knowledge retrieval and evidence gathering.

    Responsibilities:
    - RAG retrieval for section context
    - Source selection and relevance scoring
    - Evidence extraction from retrieval results
    """

    def __init__(self, provider=None, context_assembler=None):
        super().__init__("research", provider)
        self._context_assembler = context_assembler

    def set_context_assembler(self, context_assembler):
        self._context_assembler = context_assembler

    def execute(self, input_data: Any, **kwargs) -> AgentResponse:
        if not isinstance(input_data, dict):
            return self._create_response(False, error="Input must be a dict")

        query = input_data.get("query", "")
        if not query:
            return self._create_response(False, error="No query provided")

        top_k = input_data.get("top_k", 8)

        if not self._context_assembler or not self._context_assembler.is_ready():
            return self._create_response(True, data={
                "query": query,
                "chunks": [],
                "context_text": "",
                "sources": [],
                "total_chunks": 0,
                "note": "No knowledge base available",
            })

        result = self._context_assembler.retrieve_context(query, top_k=top_k)

        return self._create_response(
            True,
            data={
                "query": query,
                "chunks": result.get("chunks", []),
                "context_text": result.get("context_text", ""),
                "sources": result.get("sources", []),
                "total_chunks": result.get("total_chunks", 0),
                "avg_score": result.get("avg_score", 0.0),
            },
            chunk_count=result.get("total_chunks", 0),
            source_count=len(result.get("sources", [])),
        )

    def retrieve_for_section(self, topic: str, section_heading: str) -> Dict:
        query = f"{topic} {section_heading}"
        result = self.execute({"query": query, "top_k": 8})
        return result.data if result.success else {"context_text": "", "chunks": []}
