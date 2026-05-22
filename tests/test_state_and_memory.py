"""Tests for DocumentState, Workspace, and extended memory types."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestDocumentState:
    """Verify DocumentState as a single source of truth."""

    def test_create_document_state(self):
        from src.core.state import DocumentState
        ds = DocumentState(
            title="Test Report",
            abstract="This is a test.",
            chapters=["Intro", "Methods", "Results"],
        )
        assert ds.title == "Test Report"
        assert ds.abstract == "This is a test."
        assert len(ds.chapters) == 3

    def test_to_dict(self):
        from src.core.state import DocumentState
        ds = DocumentState(title="Test")
        d = ds.to_dict()
        assert d["title"] == "Test"
        assert d["section_count"] == 0
        assert d["reference_count"] == 0

    def test_generation_event(self):
        from src.core.state import DocumentState
        ds = DocumentState()
        ds.add_generation_event("draft", {"section": "Introduction"})
        assert len(ds.generation_history) == 1
        assert ds.generation_history[0]["phase"] == "draft"

    def test_review_result(self):
        from src.core.state import DocumentState
        ds = DocumentState()
        ds.add_review_result("coherence", True, 0)
        assert len(ds.review_history) == 1
        assert ds.review_history[0]["passed"] is True


class TestWorkspace:
    """Verify Workspace artifact separation."""

    def test_workspace_creation(self):
        from src.core.state import Workspace
        ws = Workspace()
        assert ws.document is not None
        assert ws.conversation is not None
        assert ws.execution is not None

    def test_separate_states(self):
        from src.core.state import Workspace
        ws = Workspace()
        ws.document.title = "Doc Title"
        ws.conversation.session_id = "session-123"
        assert ws.document.title == "Doc Title"
        assert ws.conversation.session_id == "session-123"

    def test_reset_document_preserves_conversation(self):
        from src.core.state import Workspace
        ws = Workspace()
        ws.document.title = "Old Title"
        ws.conversation.session_id = "my-session"
        ws.reset_document()
        assert ws.document.title == ""
        assert ws.conversation.session_id == "my-session"

    def test_to_dict(self):
        from src.core.state import Workspace
        ws = Workspace()
        d = ws.to_dict()
        assert "document" in d
        assert "conversation" in d
        assert "execution" in d


class TestConversationState:
    """Verify ConversationState remains separate."""

    def test_conversation_state(self):
        from src.core.state import ConversationState
        cs = ConversationState(session_id="abc")
        cs.user_instructions.append("Write a report on AI")
        assert cs.to_dict()["instruction_count"] == 1
        assert cs.to_dict()["correction_count"] == 0


class TestStyleMemory:
    """Test style tracking for consistency."""

    def test_analyze_and_profile(self):
        from src.memory import StyleMemory
        sm = StyleMemory()
        sm.analyze("This study examines the impact of AI. The results demonstrate significant improvement. The proposed method achieves high accuracy.")
        profile = sm.get_profile()
        assert profile["avg_sentence_length"] > 0
        assert 0 <= profile["passive_ratio"] <= 1
        assert profile["unique_terms"] > 0

    def test_first_person_detection(self):
        from src.memory import StyleMemory
        sm = StyleMemory()
        sm.analyze("We propose a new method. I think this is important. Our results show improvement.")
        assert sm._first_person_count > 0

    def test_clear(self):
        from src.memory import StyleMemory
        sm = StyleMemory()
        sm.analyze("This is a test sentence for analysis.")
        sm.clear()
        assert sm.avg_sentence_length == 0.0


class TestTopicMemory:
    """Test topic drift prevention."""

    def test_report_objective(self):
        from src.memory import TopicMemory
        tm = TopicMemory()
        tm.set_report_objective("Analyze deepfake detection methods")
        summary = tm.get_summary()
        assert "deepfake" in summary

    def test_coverage_tracking(self):
        from src.memory import TopicMemory
        tm = TopicMemory()
        tm.register_coverage("Introduction", "Deepfake detection is an important problem in computer vision.")
        tm.register_coverage("Methods", "We propose a CNN-based deepfake detector.")
        overlap = tm.is_already_covered("Deepfake detection using convolutional neural networks")
        assert len(overlap) > 0

    def test_clear(self):
        from src.memory import TopicMemory
        tm = TopicMemory()
        tm.set_report_objective("Test")
        tm.clear()
        assert tm.get_summary() == ""


class TestFigureMemory:
    """Test figure tracking and duplicate prevention."""

    def test_register_and_count(self):
        from src.memory import FigureMemory
        fm = FigureMemory()
        n1 = fm.register_figure("System Architecture", section="Design")
        n2 = fm.register_figure("Results Graph", section="Results")
        assert n1 == 1
        assert n2 == 2
        assert fm.count() == 2

    def test_duplicate_detection(self):
        from src.memory import FigureMemory
        fm = FigureMemory()
        fm.register_figure("Architecture Diagram")
        assert fm.is_duplicate("Architecture Diagram")
        assert not fm.is_duplicate("Different Figure")

    def test_summary(self):
        from src.memory import FigureMemory
        fm = FigureMemory()
        fm.register_figure("Fig A", section="Intro")
        fm.register_figure("Fig B", section="Methods")
        summary = fm.get_summary()
        assert "2 figures" in summary


class TestContextCompressor:
    """Test chapter summary compression."""

    def test_summarize_and_retrieve(self):
        from src.memory import ContextCompressor
        cc = ContextCompressor(max_summary_length=500)
        cc.summarize_chapter("Introduction", "This chapter introduces the topic. We cover background. The key findings are presented. This is important for understanding.")
        summary = cc.get_summary("Introduction")
        assert len(summary) > 0
        assert "Introduction" in summary or len(summary) > 0

    def test_get_all_summaries(self):
        from src.memory import ContextCompressor
        cc = ContextCompressor()
        cc.summarize_chapter("Ch1", "Content of chapter one.")
        cc.summarize_chapter("Ch2", "Content of chapter two.")
        all_s = cc.get_all_summaries()
        assert len(all_s) == 2

    def test_context_for_chapter(self):
        from src.memory import ContextCompressor
        cc = ContextCompressor()
        cc.summarize_chapter("Introduction", "Introduction content.")
        cc.summarize_chapter("Literature Review", "Literature content.")
        cc.summarize_chapter("Methodology", "Methodology content.")
        context = cc.get_context_for("Methodology")
        assert "Literature" in context or "Introduction" in context

    def test_clear(self):
        from src.memory import ContextCompressor
        cc = ContextCompressor()
        cc.summarize_chapter("Ch1", "Content.")
        cc.clear()
        assert len(cc.get_all_summaries()) == 0


class TestPromptBuilder:
    """Test the prompt building system."""

    def test_build_introduction(self):
        from prompts import PromptBuilder
        pb = PromptBuilder()
        prompt = pb.build_prompt("introduction", "Artificial Intelligence",
                                 report_type="research paper", target_words=500)
        assert prompt is not None
        assert "Artificial Intelligence" in prompt
        assert "introduction" in prompt.lower()

    def test_build_with_context(self):
        from prompts import PromptBuilder
        pb = PromptBuilder()
        prompt = pb.build_prompt("methodology", "Deep Learning",
                                 retrieval_context="Key references about CNN architectures.")
        assert prompt is not None
        assert "Deep Learning" in prompt

    def test_unknown_section_returns_none(self):
        from prompts import PromptBuilder
        pb = PromptBuilder()
        prompt = pb.build_prompt("nonexistent", "Topic")
        assert prompt is None

    def test_list_templates(self):
        from prompts import PromptBuilder
        pb = PromptBuilder()
        templates = pb.list_available_templates()
        assert "introduction" in templates
        assert "exists" in templates["introduction"]
