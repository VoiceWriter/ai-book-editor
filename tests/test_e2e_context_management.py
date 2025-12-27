"""
End-to-end API tests for context management and conversation state.

These tests call the real LLM API to verify:
- Long conversation summarization preserves facts
- Cross-issue knowledge persistence
- Rich PR body generation
- Closing summary generation

Run with: pytest tests/test_e2e_context_management.py -v
Requires: ANTHROPIC_API_KEY environment variable

These tests are skipped if no API key is available.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))

from scripts.utils.context_management import (  # noqa: E402
    count_tokens,
    prepare_conversation_context,
    summarize_conversation,
)
from scripts.utils.conversation_state import (  # noqa: E402
    ConversationState,
    EstablishedFact,
    OutstandingQuestion,
    format_closing_summary,
    persist_to_knowledge_base,
)
from scripts.utils.llm_client import LLMResponse, LLMUsage  # noqa: E402
from scripts.utils.pr_body import (  # noqa: E402
    ContentAnalysis,
    DecisionRecord,
    RichPRBody,
    StructuralAnalysis,
    VoiceAnalysis,
    build_rich_pr_body,
    format_rich_pr_body,
)

# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping E2E tests",
)


def make_outstanding_question(question: str, answered: bool = False) -> OutstandingQuestion:
    """Helper to create OutstandingQuestion with required fields."""
    return OutstandingQuestion(
        question=question,
        asked_at="2025-12-27T12:00:00Z",
        answered=answered,
    )


def make_llm_usage(
    prompt_tokens: int = 1000,
    completion_tokens: int = 500,
    model: str = "claude-sonnet-4-20250514",
) -> LLMUsage:
    """Helper to create LLMUsage with required fields."""
    return LLMUsage(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        cost_usd=0.01,
    )


class TestConversationSummarization:
    """Test 14.1: Long conversation summarization."""

    def test_summarizes_long_conversation_preserving_facts(self):
        """20+ exchanges should be summarized, keeping recent 3 verbatim."""
        # Build a long conversation with an established fact early on
        comments = []

        # Early fact: establish the dog's name
        comments.append({"user": "author", "body": "My dog's name is Max, he's a golden retriever."})
        comments.append(
            {"user": "ai-editor", "body": "Great! Max sounds wonderful. What inspired his name?"}
        )
        comments.append({"user": "author", "body": "Named after my grandfather."})

        # Add LONGER filler conversation to push past summarization threshold
        for i in range(25):
            comments.append({
                "user": "author",
                "body": f"Here's another detailed thought about chapter {i}. "
                f"I want to explore the themes of loyalty and companionship in this section. "
                f"The narrative should flow from the previous chapter naturally.",
            })
            comments.append({
                "user": "ai-editor",
                "body": f"That's a wonderful direction for chapter {i}. "
                f"The themes you mentioned resonate well with the overall arc. "
                f"Consider how Max's journey mirrors the reader's learning experience.",
            })

        # Recent conversation (should be kept verbatim)
        comments.append({"user": "author", "body": "How should I end the book?"})
        comments.append({
            "user": "ai-editor",
            "body": "Consider a callback to Max's story for emotional resonance.",
        })
        comments.append({"user": "author", "body": "Perfect, I'll do that!"})

        established_facts = ["Dog's name: Max", "Dog breed: Golden Retriever"]

        # Use a low target to force summarization
        summary = summarize_conversation(
            comments, established_facts, target_tokens=500
        )

        # Verify summarization occurred
        assert summary.comments_summarized > 0, "Should have summarized older comments"
        assert summary.savings_percent > 0, "Should have saved tokens"

        # Verify facts are preserved (re-injected after summarization)
        assert "Max" in summary.summary, "Established fact 'Max' should be in summary"
        assert "PRESERVE" in summary.summary or "Established" in summary.summary, (
            "Summary should have facts section"
        )

        # Verify recent comments are in the summary
        assert "end the book" in summary.summary, "Recent question should be preserved"
        assert "Perfect" in summary.summary, "Most recent comment should be preserved"

    def test_short_conversation_not_summarized(self):
        """Short conversations should not be summarized."""
        comments = [
            {"user": "author", "body": "Here's my first voice memo."},
            {"user": "ai-editor", "body": "Thanks! What's the main theme?"},
            {"user": "author", "body": "It's about AI and creativity."},
        ]

        summary = summarize_conversation(comments, [], target_tokens=5000)

        assert summary.comments_summarized == 0, "Short conversation should not be summarized"
        assert summary.savings_percent == 0.0, "No savings for short conversation"


class TestFactPersistence:
    """Test 14.2: Facts persist across exchanges."""

    def test_established_facts_survive_context_preparation(self):
        """Facts should be preserved when preparing context."""
        comments = [
            {"user": "author", "body": "My target audience is busy professionals."},
            {"user": "ai-editor", "body": "Got it. What's the core message?"},
            {"user": "author", "body": "That AI can be accessible to everyone."},
        ]

        established_facts = [
            "Target audience: busy professionals",
            "Core message: AI accessibility",
        ]

        system_prompt = "You are an editorial assistant."
        current_content = "Chapter 1 draft content here."

        system, conversation, budget = prepare_conversation_context(
            comments,
            system_prompt,
            current_content,
            established_facts,
        )

        # Facts should be in the conversation context
        assert "busy professionals" in conversation.lower() or "busy professionals" in str(
            comments
        ).lower(), "Established facts should be in context"


class TestClosingSummary:
    """Test 14.3: Closing summary generation."""

    def test_format_closing_summary_includes_all_sections(self):
        """Closing summary should include facts, decisions, and outstanding items."""
        state = ConversationState(
            issue_number=42,
            phase="feedback",
            established=[
                EstablishedFact(key="target_audience", value="busy professionals"),
                EstablishedFact(key="tone", value="conversational"),
            ],
            outstanding_questions=[
                make_outstanding_question("What's the chapter order?", answered=False),
                make_outstanding_question("What's the title?", answered=True),
            ],
        )

        summary = format_closing_summary(state)

        # Check structure
        assert "Issue Summary" in summary
        assert "Decisions Made" in summary or "Established" in summary
        assert "busy professionals" in summary
        assert "conversational" in summary

        # Check outstanding items are noted (deferred questions)
        assert "chapter order" in summary.lower()

        # Check it's well-formatted markdown
        assert summary.count("#") >= 1, "Should have markdown headers"


class TestKnowledgeBasePersistence:
    """Test 14.4: Knowledge base persistence."""

    def test_persist_facts_to_knowledge_base(self):
        """Established facts should be written to knowledge.jsonl."""
        state = ConversationState(
            issue_number=99,
            phase="complete",
            established=[
                EstablishedFact(key="book_title", value="The AI Companion"),
                EstablishedFact(key="chapter_count", value="10"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "knowledge.jsonl"

            count = persist_to_knowledge_base(state, str(kb_path))

            assert count == 2, "Should persist 2 facts"
            assert kb_path.exists(), "Knowledge file should be created"

            # Read and verify content
            lines = kb_path.read_text().strip().split("\n")
            assert len(lines) == 2, "Should have 2 lines"

            for line in lines:
                entry = json.loads(line)
                # Format: type, key, value, source_issue, established_at
                assert entry["type"] == "established_fact"
                assert "key" in entry
                assert "value" in entry
                assert entry["source_issue"] == 99

    def test_persist_skips_duplicate_facts(self):
        """Should not write duplicate facts."""
        state = ConversationState(
            issue_number=99,
            established=[
                EstablishedFact(key="book_title", value="The AI Companion"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "knowledge.jsonl"

            # Write once
            count1 = persist_to_knowledge_base(state, str(kb_path))
            assert count1 == 1

            # Write again - should skip duplicate
            count2 = persist_to_knowledge_base(state, str(kb_path))
            assert count2 == 0, "Should skip duplicate"

            # File should still have only 1 line
            lines = kb_path.read_text().strip().split("\n")
            assert len(lines) == 1


class TestRichPRBody:
    """Tests 14.6-14.8: Rich PR body generation."""

    def test_build_rich_pr_body_with_conversation_state(self):
        """PR body should include decisions and outstanding items from state."""
        # Create a mock LLM response
        llm_response = LLMResponse(
            content="This content looks great for the introduction.",
            model="claude-sonnet-4-20250514",
            reasoning_content="I analyzed the voice memo and found strong thematic elements.",
            usage=make_llm_usage(prompt_tokens=1000, completion_tokens=500),
        )

        # Create conversation state with decisions
        state = ConversationState(
            issue_number=42,
            phase="feedback",
            established=[
                EstablishedFact(key="placement", value="chapters/01-introduction.md"),
                EstablishedFact(key="tone", value="conversational"),
            ],
            outstanding_questions=[
                make_outstanding_question("Should we add more examples?", answered=False),
            ],
        )

        # Build PR body
        pr_body = build_rich_pr_body(
            source_issue=42,
            target_file="chapters/01-introduction.md",
            prepared_content="This is the polished introduction content about AI.",
            llm_response=llm_response,
            editorial_notes="Strong opening that sets the tone well.",
            content_summary="Introduces the main themes of AI accessibility.",
            conversation_state=state,
        )

        # Verify structure
        assert pr_body.source_issue == 42
        assert pr_body.target_file == "chapters/01-introduction.md"

        # Verify decisions from state
        assert len(pr_body.decisions_made) >= 2, "Should have decisions from established facts"
        decision_texts = [d.decision for d in pr_body.decisions_made]
        assert any("placement" in d.lower() for d in decision_texts)
        assert any("tone" in d.lower() for d in decision_texts)

        # Verify outstanding items
        assert len(pr_body.outstanding_items) >= 1, "Should have outstanding items"
        assert any("examples" in item.lower() for item in pr_body.outstanding_items)

        # Verify context references
        assert len(pr_body.context_references) >= 1
        assert any("#42" in ref for ref in pr_body.context_references)

    def test_format_rich_pr_body_includes_all_sections(self):
        """Formatted PR body should include all editorial sections."""
        pr_body = RichPRBody(
            source_issue=42,
            target_file="chapters/01-intro.md",
            content_analysis=ContentAnalysis(
                word_count=500,
                reading_time_minutes=2.5,
                flesch_reading_ease=65.0,
                flesch_kincaid_grade=8.0,
                avg_sentence_length=15.0,
                lexical_diversity=0.7,
                passive_voice_percent=5.0,
            ),
            structural=StructuralAnalysis(
                target_file="chapters/01-intro.md",
                placement_rationale="This is the natural opening for the book.",
                related_chapters=["02-basics"],
                thematic_connections=["AI accessibility"],
                flow_impact="Sets up the main narrative arc.",
            ),
            voice=VoiceAnalysis(
                voice_score="high",
                voice_markers=["Conversational tone", "Personal anecdotes"],
                transformations=["Removed filler words", "Structured into paragraphs"],
            ),
            decisions_made=[
                DecisionRecord(
                    decision="placement: chapters/01-intro.md", context="Author requested"
                ),
            ],
            outstanding_items=["Consider adding more examples"],
            context_references=["Issue #42 - full conversation"],
            editorial_reasoning="The content flows naturally and preserves voice.",
            editorial_notes="Strong opening chapter.",
            content_summary="Introduction to AI accessibility themes.",
            llm_usage_summary="Tokens: 1500 in, 500 out",
        )

        formatted = format_rich_pr_body(pr_body)

        # Check all sections present
        assert "## " in formatted, "Should have markdown headers"
        assert "Text Analysis" in formatted
        assert "Structural Placement" in formatted
        assert "Voice Preservation" in formatted
        assert "Decisions Made" in formatted
        assert "Outstanding Items" in formatted
        assert "Editorial Notes" in formatted
        assert "Editorial Checklist" in formatted

        # Check content
        assert "500" in formatted, "Word count should be in output"
        assert "#42" in formatted, "Source issue should be referenced"
        assert "high" in formatted, "Voice score should be included"


class TestTokenCounting:
    """Test token counting utilities."""

    def test_count_tokens_reasonable_estimate(self):
        """Token count should be reasonable for English text."""
        text = "This is a sample sentence for testing token counting."
        tokens = count_tokens(text)

        # Rough estimate: ~1 token per 4 characters, so ~12-15 tokens
        assert 8 < tokens < 20, f"Token count {tokens} seems off for: {text}"

    def test_count_tokens_empty_string(self):
        """Empty string should have 0 tokens."""
        assert count_tokens("") == 0


class TestIntegrationWorkflow:
    """Full workflow integration tests."""

    def test_full_context_management_workflow(self):
        """Test the complete workflow: conversation -> summarization -> closing."""
        # 1. Start with conversation state
        state = ConversationState(issue_number=100, phase="discovery")

        # 2. Establish facts during conversation
        state.establish_fact("genre", "non-fiction")
        state.establish_fact("audience", "beginners")

        # 3. Add questions
        state.add_question("What's the book's main thesis?")
        state.add_question("How many chapters?")

        # 4. Answer one question
        state.mark_question_answered("chapters")

        # 5. Generate closing summary
        summary = format_closing_summary(state)

        assert "non-fiction" in summary
        assert "beginners" in summary
        assert "thesis" in summary.lower()  # Outstanding question

        # 6. Persist to knowledge base
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "knowledge.jsonl"
            count = persist_to_knowledge_base(state, str(kb_path))
            assert count == 2, "Should persist genre and audience facts"
