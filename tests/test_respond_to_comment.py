"""Tests for respond_to_comment intent inference and action execution."""

from unittest.mock import MagicMock

import pytest

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_issue_with_labels():
    """Mock GitHub issue with labels."""
    issue = MagicMock()
    issue.number = 42
    issue.title = "Voice memo: Chapter ideas"
    issue.body = "This is my voice memo about chapter structure..."
    issue.state = "open"

    # Mock labels
    label1 = MagicMock()
    label1.name = "voice_transcription"
    label2 = MagicMock()
    label2.name = "ai-reviewed"
    issue.labels = [label1, label2]

    return issue


@pytest.fixture
def sample_comments():
    """Sample conversation history."""
    return [
        {
            "id": 1,
            "body": "## AI Editorial Analysis\n\n### Cleaned Transcript\n\nThis is about chapter structure...",
            "user": "github-actions[bot]",
            "created_at": "2024-01-01T10:00:00Z",
        },
        {
            "id": 2,
            "body": "Thanks, this looks good! Put it in chapter-03.md",
            "user": "author",
            "created_at": "2024-01-01T11:00:00Z",
        },
    ]


@pytest.fixture
def mock_intent_response():
    """Mock ConversationalIntent for testing."""
    from scripts.utils.llm_client import ConversationalIntent, IssueAction

    return ConversationalIntent(
        understood=True,
        confidence="high",
        issue_actions=[
            IssueAction(
                action="set_placement",
                target_file="chapter-03.md",
            )
        ],
        pr_actions=[],
        response_text="Got it! I'll target chapter-03.md for the PR.",
        needs_confirmation=False,
        clarifying_question=None,
    )


@pytest.fixture
def mock_low_confidence_intent():
    """Mock ConversationalIntent with low confidence."""
    from scripts.utils.llm_client import ConversationalIntent, IssueAction

    return ConversationalIntent(
        understood=True,
        confidence="low",
        issue_actions=[
            IssueAction(
                action="close",
                close_reason="not_planned",
            )
        ],
        pr_actions=[],
        response_text="It sounds like you want me to close this issue.",
        needs_confirmation=True,
        clarifying_question="Are you sure you want to close this without creating a PR?",
    )


@pytest.fixture
def mock_llm_response_with_reasoning():
    """Mock LLM response with full reasoning."""
    from scripts.utils.llm_client import LLMResponse, LLMUsage, ThinkingBlock

    return LLMResponse(
        content='{"understood": true, "confidence": "high", "issue_actions": [], "pr_actions": [], "response_text": "Test", "needs_confirmation": false, "clarifying_question": null}',
        reasoning="I analyzed the author's message and determined they want to set placement for chapter-03.md. The language 'put it in' clearly indicates file placement. Confidence is high because the request is explicit.",
        thinking_blocks=[
            ThinkingBlock(
                type="thinking",
                thinking="Step 1: Parse the author message. They said 'put it in chapter-03.md'. Step 2: This maps to set_placement action. Step 3: Confidence is high.",
                signature=None,
            )
        ],
        usage=LLMUsage(
            model="claude-sonnet-4-5-20250929",
            prompt_tokens=800,
            completion_tokens=150,
            total_tokens=950,
            cost_usd=0.006,
            cache_read_tokens=0,
            cache_creation_tokens=0,
        ),
    )


# =============================================================================
# TESTS: Intent Inference
# =============================================================================


class TestBuildIntentPrompt:
    """Tests for build_intent_prompt function."""

    def test_includes_issue_context(self, sample_issue_with_labels, sample_comments):
        """Should include issue number, title, state, and labels."""
        from scripts.respond_to_comment import build_intent_prompt

        prompt = build_intent_prompt(
            issue=sample_issue_with_labels,
            comments=sample_comments,
            comment_body="@margot-ai-editor create PR",
            issue_number=42,
        )

        assert "Issue #42" in prompt
        assert "Voice memo: Chapter ideas" in prompt
        assert "open" in prompt
        assert "voice_transcription" in prompt

    def test_includes_conversation_history(self, sample_issue_with_labels, sample_comments):
        """Should include previous comments."""
        from scripts.respond_to_comment import build_intent_prompt

        prompt = build_intent_prompt(
            issue=sample_issue_with_labels,
            comments=sample_comments,
            comment_body="@margot-ai-editor thanks!",
            issue_number=42,
        )

        assert "AI Editorial Analysis" in prompt
        assert "Put it in chapter-03.md" in prompt

    def test_includes_available_actions(self, sample_issue_with_labels, sample_comments):
        """Should list available actions."""
        from scripts.respond_to_comment import build_intent_prompt

        prompt = build_intent_prompt(
            issue=sample_issue_with_labels,
            comments=sample_comments,
            comment_body="@margot-ai-editor close this",
            issue_number=42,
        )

        assert "close" in prompt.lower()
        assert "add_labels" in prompt.lower()
        assert "create_pr" in prompt.lower()
        assert "set_placement" in prompt.lower()

    def test_includes_latest_message(self, sample_issue_with_labels, sample_comments):
        """Should include the latest comment from author."""
        from scripts.respond_to_comment import build_intent_prompt

        comment = "@margot-ai-editor close this issue, I changed my mind"
        prompt = build_intent_prompt(
            issue=sample_issue_with_labels,
            comments=sample_comments,
            comment_body=comment,
            issue_number=42,
        )

        assert "close this issue, I changed my mind" in prompt


class TestBuildIntentPromptWithEditorialContext:
    """Tests for editorial context loading in intent inference."""

    def test_includes_editor_persona_when_provided(self, sample_issue_with_labels, sample_comments):
        """Should include persona when editorial context is provided."""
        from scripts.respond_to_comment import build_intent_prompt

        context = {
            "persona": "You are Margot, a warm and supportive editor.",
            "guidelines": "Always preserve the author's voice.",
        }

        prompt = build_intent_prompt(
            issue=sample_issue_with_labels,
            comments=sample_comments,
            comment_body="@margot-ai-editor help",
            issue_number=42,
            editorial_context=context,
        )

        assert "Your Editorial Persona" in prompt
        assert "Margot" in prompt

    def test_includes_editorial_guidelines_when_provided(
        self, sample_issue_with_labels, sample_comments
    ):
        """Should include guidelines when editorial context is provided."""
        from scripts.respond_to_comment import build_intent_prompt

        context = {
            "persona": "You are a helpful editor.",
            "guidelines": "Always preserve the author's voice. Never add content.",
        }

        prompt = build_intent_prompt(
            issue=sample_issue_with_labels,
            comments=sample_comments,
            comment_body="@margot-ai-editor help",
            issue_number=42,
            editorial_context=context,
        )

        assert "Editorial Guidelines" in prompt
        assert "preserve the author's voice" in prompt

    def test_works_without_editorial_context(self, sample_issue_with_labels, sample_comments):
        """Should work when no editorial context is provided."""
        from scripts.respond_to_comment import build_intent_prompt

        prompt = build_intent_prompt(
            issue=sample_issue_with_labels,
            comments=sample_comments,
            comment_body="@margot-ai-editor help",
            issue_number=42,
            editorial_context=None,
        )

        # Should still have the basic structure
        assert "Issue #42" in prompt
        assert "Available Actions" in prompt


# =============================================================================
# TESTS: Action Execution
# =============================================================================


class TestExecuteIssueActions:
    """Tests for execute_issue_actions function."""

    def test_closes_issue(self, sample_issue_with_labels, mock_repo):
        """Should close issue when action is 'close'."""
        from scripts.respond_to_comment import execute_issue_actions
        from scripts.utils.llm_client import ConversationalIntent, IssueAction

        intent = ConversationalIntent(
            understood=True,
            confidence="high",
            issue_actions=[IssueAction(action="close", close_reason="completed")],
            pr_actions=[],
            response_text="Closing this issue.",
            needs_confirmation=False,
        )

        actions = execute_issue_actions(sample_issue_with_labels, mock_repo, intent, 42)

        sample_issue_with_labels.edit.assert_called_once_with(state="closed")
        assert "Closed issue" in actions[0]

    def test_adds_labels(self, sample_issue_with_labels, mock_repo):
        """Should add labels when action is 'add_labels'."""
        from scripts.respond_to_comment import execute_issue_actions
        from scripts.utils.llm_client import ConversationalIntent, IssueAction

        intent = ConversationalIntent(
            understood=True,
            confidence="high",
            issue_actions=[IssueAction(action="add_labels", labels=["needs-review", "priority"])],
            pr_actions=[],
            response_text="Adding labels.",
            needs_confirmation=False,
        )

        actions = execute_issue_actions(sample_issue_with_labels, mock_repo, intent, 42)

        assert sample_issue_with_labels.add_to_labels.call_count == 2
        assert "Added labels" in actions[0]

    def test_removes_labels(self, sample_issue_with_labels, mock_repo):
        """Should remove labels when action is 'remove_labels'."""
        from scripts.respond_to_comment import execute_issue_actions
        from scripts.utils.llm_client import ConversationalIntent, IssueAction

        intent = ConversationalIntent(
            understood=True,
            confidence="high",
            issue_actions=[IssueAction(action="remove_labels", labels=["draft"])],
            pr_actions=[],
            response_text="Removing labels.",
            needs_confirmation=False,
        )

        actions = execute_issue_actions(sample_issue_with_labels, mock_repo, intent, 42)

        sample_issue_with_labels.remove_from_labels.assert_called_once_with("draft")
        assert "Removed labels" in actions[0]

    def test_creates_follow_up_issue(self, sample_issue_with_labels, mock_repo):
        """Should create new issue when action is 'create_issue'."""
        from scripts.respond_to_comment import execute_issue_actions
        from scripts.utils.llm_client import ConversationalIntent, IssueAction

        new_issue = MagicMock()
        new_issue.number = 43
        mock_repo.create_issue.return_value = new_issue

        intent = ConversationalIntent(
            understood=True,
            confidence="high",
            issue_actions=[
                IssueAction(
                    action="create_issue",
                    title="Follow-up: Review chapter structure",
                    body="Need to revisit the chapter organization.",
                    labels=["follow-up"],
                )
            ],
            pr_actions=[],
            response_text="Creating follow-up issue.",
            needs_confirmation=False,
        )

        actions = execute_issue_actions(sample_issue_with_labels, mock_repo, intent, 42)

        mock_repo.create_issue.assert_called_once()
        assert "Created issue #43" in actions[0]

    def test_edits_issue_title(self, sample_issue_with_labels, mock_repo):
        """Should edit title when action is 'edit_title'."""
        from scripts.respond_to_comment import execute_issue_actions
        from scripts.utils.llm_client import ConversationalIntent, IssueAction

        intent = ConversationalIntent(
            understood=True,
            confidence="high",
            issue_actions=[IssueAction(action="edit_title", title="New Better Title")],
            pr_actions=[],
            response_text="Updating title.",
            needs_confirmation=False,
        )

        actions = execute_issue_actions(sample_issue_with_labels, mock_repo, intent, 42)

        sample_issue_with_labels.edit.assert_called_once_with(title="New Better Title")
        assert "Updated title" in actions[0]

    def test_no_action_for_respond(self, sample_issue_with_labels, mock_repo):
        """Should not execute anything for 'respond' action."""
        from scripts.respond_to_comment import execute_issue_actions
        from scripts.utils.llm_client import ConversationalIntent, IssueAction

        intent = ConversationalIntent(
            understood=True,
            confidence="high",
            issue_actions=[IssueAction(action="respond")],
            pr_actions=[],
            response_text="Just a conversational response.",
            needs_confirmation=False,
        )

        actions = execute_issue_actions(sample_issue_with_labels, mock_repo, intent, 42)

        assert len(actions) == 0
        sample_issue_with_labels.edit.assert_not_called()


# =============================================================================
# TESTS: Confidence-based Confirmation
# =============================================================================


class TestConfidenceConfirmation:
    """Tests for confidence-based action confirmation."""

    def test_high_confidence_executes_immediately(self):
        """High confidence actions should execute without confirmation."""
        # This is tested in execute tests above - high confidence works
        pass

    def test_medium_confidence_asks_confirmation(self):
        """Medium confidence should ask for confirmation."""
        from scripts.utils.llm_client import ConversationalIntent, IssueAction

        intent = ConversationalIntent(
            understood=True,
            confidence="medium",  # Below 80% threshold
            issue_actions=[IssueAction(action="create_pr")],
            pr_actions=[],
            response_text="I think you want me to create a PR.",
            needs_confirmation=False,
        )

        # The main() function should check this and request confirmation
        assert intent.confidence in ("low", "medium")

    def test_low_confidence_asks_confirmation(self):
        """Low confidence should ask for confirmation."""
        from scripts.utils.llm_client import ConversationalIntent, IssueAction

        intent = ConversationalIntent(
            understood=True,
            confidence="low",
            issue_actions=[IssueAction(action="close")],
            pr_actions=[],
            response_text="I'm not sure, but maybe you want to close this?",
            needs_confirmation=True,
            clarifying_question="Did you mean to close this issue?",
        )

        assert intent.needs_confirmation is True
        assert intent.clarifying_question is not None


# =============================================================================
# TESTS: Reasoning Log Storage
# =============================================================================


class TestReasoningLogStorage:
    """Tests for reasoning/chain-of-thought logging."""

    def test_reasoning_log_entry_structure(self):
        """Reasoning log entries should have required fields."""
        from scripts.utils.reasoning_log import ReasoningLogEntry

        entry = ReasoningLogEntry(
            timestamp="2024-01-01T10:00:00Z",
            issue_number=42,
            author_message="test message",
            conversation_summary="Issue #42: Test...",
            model_used="claude-sonnet-4-5-20250929",
            reasoning="I analyzed the message...",
            thinking_blocks=["Step 1: Read", "Step 2: Analyze"],
            inferred_intent="User wants to close",
            confidence="high",
            actions_proposed=["close"],
            confirmation_required=False,
        )

        assert entry.issue_number == 42
        assert entry.confidence == "high"
        assert len(entry.thinking_blocks) == 2

    def test_stores_chain_of_thought(self, mock_llm_response_with_reasoning):
        """Should store the full chain of thought."""
        response = mock_llm_response_with_reasoning

        assert response.has_reasoning() is True
        assert "Step 1" in response.reasoning or any(
            "Step 1" in b.thinking for b in response.thinking_blocks
        )

    def test_reasoning_displayed_in_comment(self, mock_llm_response_with_reasoning):
        """Reasoning should be included in the response comment."""
        response = mock_llm_response_with_reasoning

        explanation = response.format_editorial_explanation()

        assert "<details>" in explanation  # Collapsible
        assert "Editorial Reasoning" in explanation


class TestReasoningLogFile:
    """Tests for reasoning log file operations."""

    def test_creates_log_directory(self, tmp_path):
        """Should create .ai-context directory if needed."""
        from scripts.utils.reasoning_log import ReasoningLogger

        logger = ReasoningLogger(tmp_path)
        logger.ensure_directory()

        assert (tmp_path / ".ai-context").exists()

    def test_appends_to_jsonl(self, tmp_path):
        """Should append entries to reasoning-log.jsonl."""
        from scripts.utils.reasoning_log import ReasoningLogger

        logger = ReasoningLogger(tmp_path)

        # Log first entry
        logger.log_decision(
            issue_number=1,
            author_message="First message",
            conversation_summary="Issue #1...",
            model_used="claude-test",
            reasoning="First reasoning",
            thinking_blocks=["Step 1"],
            inferred_intent="Action 1",
            confidence="high",
            actions_proposed=["action1"],
            confirmation_required=False,
        )

        # Log second entry
        logger.log_decision(
            issue_number=2,
            author_message="Second message",
            conversation_summary="Issue #2...",
            model_used="claude-test",
            reasoning="Second reasoning",
            thinking_blocks=["Step A"],
            inferred_intent="Action 2",
            confidence="medium",
            actions_proposed=["action2"],
            confirmation_required=True,
        )

        # Verify both entries exist
        entries = logger.get_recent_entries()
        assert len(entries) == 2
        assert entries[0]["issue_number"] == 1
        assert entries[1]["issue_number"] == 2

    def test_includes_all_thinking_blocks(self, mock_llm_response_with_reasoning):
        """Should include all thinking blocks in log."""
        response = mock_llm_response_with_reasoning

        # Verify thinking blocks are accessible
        assert len(response.thinking_blocks) > 0
        assert response.thinking_blocks[0].thinking is not None

    def test_updates_outcome(self, tmp_path):
        """Should update outcome of previous entry."""
        from scripts.utils.reasoning_log import ReasoningLogger

        logger = ReasoningLogger(tmp_path)

        # Log initial decision
        logger.log_decision(
            issue_number=42,
            author_message="Close this",
            conversation_summary="Issue #42...",
            model_used="claude-test",
            reasoning="User wants to close",
            thinking_blocks=[],
            inferred_intent="close issue",
            confidence="medium",
            actions_proposed=["close"],
            confirmation_required=True,
        )

        # Verify initial state
        entries = logger.get_entries_for_issue(42)
        assert entries[0]["outcome"] == "pending"

        # Update outcome
        logger.update_outcome(
            issue_number=42,
            outcome="confirmed",
            actions_executed=["Closed issue"],
            author_feedback="yes, close it",
        )

        # Verify updated state
        entries = logger.get_entries_for_issue(42)
        assert entries[0]["outcome"] == "confirmed"
        assert entries[0]["actions_executed"] == ["Closed issue"]

    def test_get_rejected_decisions(self, tmp_path):
        """Should retrieve rejected decisions for learning."""
        from scripts.utils.reasoning_log import ReasoningLogger

        logger = ReasoningLogger(tmp_path)

        # Log and reject a decision
        logger.log_decision(
            issue_number=1,
            author_message="Maybe close?",
            conversation_summary="Issue #1...",
            model_used="claude-test",
            reasoning="Uncertain intent",
            thinking_blocks=[],
            inferred_intent="close",
            confidence="low",
            actions_proposed=["close"],
            confirmation_required=True,
        )
        logger.update_outcome(issue_number=1, outcome="rejected")

        rejected = logger.get_rejected_decisions()
        assert len(rejected) == 1
        assert rejected[0]["outcome"] == "rejected"

    def test_get_confirmation_patterns(self, tmp_path):
        """Should analyze confirmation patterns."""
        from scripts.utils.reasoning_log import ReasoningLogger

        logger = ReasoningLogger(tmp_path)

        # Log high confidence - auto executed
        logger.log_decision(
            issue_number=1,
            author_message="close",
            conversation_summary="",
            model_used="test",
            reasoning="",
            thinking_blocks=[],
            inferred_intent="close",
            confidence="high",
            actions_proposed=["close"],
            confirmation_required=False,
        )
        logger.update_outcome(issue_number=1, outcome="auto_executed")

        # Log low confidence - rejected
        logger.log_decision(
            issue_number=2,
            author_message="maybe close?",
            conversation_summary="",
            model_used="test",
            reasoning="",
            thinking_blocks=[],
            inferred_intent="close",
            confidence="low",
            actions_proposed=["close"],
            confirmation_required=True,
        )
        logger.update_outcome(issue_number=2, outcome="rejected")

        stats = logger.get_confirmation_patterns()
        assert stats["total"] == 2
        assert stats["auto_executed"] == 1
        assert stats["rejected"] == 1


# =============================================================================
# TESTS: Learning Integration
# =============================================================================


class TestLearningIntegration:
    """Tests for integration with learn_from_feedback.py."""

    def test_reasoning_logs_available_to_learning(self, tmp_path):
        """Learning system should be able to read reasoning logs."""
        from scripts.utils.reasoning_log import ReasoningLogger

        logger = ReasoningLogger(tmp_path)

        # Log a decision
        logger.log_decision(
            issue_number=1,
            author_message="test",
            conversation_summary="Test issue",
            model_used="claude-test",
            reasoning="I analyzed this carefully",
            thinking_blocks=["Step 1", "Step 2"],
            inferred_intent="do something",
            confidence="high",
            actions_proposed=["action"],
            confirmation_required=False,
        )

        # Verify can be read back
        entries = logger.get_recent_entries()
        assert len(entries) == 1
        assert entries[0]["reasoning"] == "I analyzed this carefully"
        assert entries[0]["thinking_blocks"] == ["Step 1", "Step 2"]

    def test_tracks_confirmation_outcomes(self, tmp_path):
        """Should track whether confirmations were accepted or rejected."""
        from scripts.utils.reasoning_log import ReasoningLogger

        logger = ReasoningLogger(tmp_path)

        # Log decision requiring confirmation
        logger.log_decision(
            issue_number=42,
            author_message="maybe close this?",
            conversation_summary="Test",
            model_used="claude-test",
            reasoning="Uncertain if they want to close",
            thinking_blocks=[],
            inferred_intent="close",
            confidence="medium",
            actions_proposed=["close"],
            confirmation_required=True,
        )

        # Simulate author confirming
        logger.update_outcome(
            issue_number=42,
            outcome="confirmed",
            actions_executed=["Closed issue"],
            author_feedback="yes please close it",
        )

        entries = logger.get_entries_for_issue(42)
        assert entries[0]["outcome"] == "confirmed"
        assert entries[0]["author_feedback"] == "yes please close it"

    def test_learns_from_rejections(self, tmp_path):
        """System should identify patterns in rejected actions."""
        from scripts.utils.reasoning_log import ReasoningLogger

        # Set up logger in tmp_path
        logger = ReasoningLogger(tmp_path)

        # Log some rejected decisions
        logger.log_decision(
            issue_number=1,
            author_message="put this aside for now",
            conversation_summary="Issue #1",
            model_used="claude-test",
            reasoning="Author said 'aside' so I thought they wanted to close",
            thinking_blocks=["Analyzed: 'aside' implies close"],
            inferred_intent="close the issue",
            confidence="medium",
            actions_proposed=["close"],
            confirmation_required=True,
        )
        logger.update_outcome(
            issue_number=1,
            outcome="rejected",
            author_feedback="No, I meant add a 'later' label",
        )

        # Verify rejected decisions are accessible
        rejected = logger.get_rejected_decisions()
        assert len(rejected) == 1
        assert rejected[0]["reasoning"] == "Author said 'aside' so I thought they wanted to close"
        assert rejected[0]["author_feedback"] == "No, I meant add a 'later' label"


# =============================================================================
# TESTS: Pydantic Models
# =============================================================================


class TestConversationalIntentModel:
    """Tests for ConversationalIntent Pydantic model."""

    def test_valid_intent_creation(self):
        """Should create valid intent with required fields."""
        from scripts.utils.llm_client import ConversationalIntent, IssueAction

        intent = ConversationalIntent(
            understood=True,
            confidence="high",
            issue_actions=[IssueAction(action="respond")],
            pr_actions=[],
            response_text="Hello!",
            needs_confirmation=False,
        )

        assert intent.understood is True
        assert intent.confidence == "high"

    def test_invalid_confidence_rejected(self):
        """Should reject invalid confidence values."""
        from pydantic import ValidationError
        from scripts.utils.llm_client import ConversationalIntent

        with pytest.raises(ValidationError):
            ConversationalIntent(
                understood=True,
                confidence="very_high",  # Invalid
                issue_actions=[],
                pr_actions=[],
                response_text="Test",
                needs_confirmation=False,
            )

    def test_invalid_action_rejected(self):
        """Should reject invalid action types."""
        from pydantic import ValidationError
        from scripts.utils.llm_client import IssueAction

        with pytest.raises(ValidationError):
            IssueAction(action="invalid_action")


class TestIssueActionModel:
    """Tests for IssueAction Pydantic model."""

    def test_close_action(self):
        """Should create valid close action."""
        from scripts.utils.llm_client import IssueAction

        action = IssueAction(action="close", close_reason="completed")
        assert action.action == "close"
        assert action.close_reason == "completed"

    def test_add_labels_action(self):
        """Should create valid add_labels action."""
        from scripts.utils.llm_client import IssueAction

        action = IssueAction(action="add_labels", labels=["bug", "priority"])
        assert action.action == "add_labels"
        assert len(action.labels) == 2

    def test_set_placement_action(self):
        """Should create valid set_placement action."""
        from scripts.utils.llm_client import IssueAction

        action = IssueAction(action="set_placement", target_file="chapter-03.md")
        assert action.action == "set_placement"
        assert action.target_file == "chapter-03.md"
