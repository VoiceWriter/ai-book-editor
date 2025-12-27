"""Tests for context window management."""

import pytest

from scripts.utils.context_management import (
    CompactedContext,
    ContextBudget,
    ConversationSummary,
    check_system_budget,
    compact_completed_items,
    count_tokens,
    get_context_budget,
    truncate_to_budget,
)


class TestContextBudget:
    """Tests for ContextBudget model."""

    def test_creates_valid_budget(self):
        """ContextBudget accepts valid data."""
        budget = ContextBudget(
            model="claude-sonnet-4-5-20250929",
            context_window=200_000,
            max_output=16_000,
            available_input=184_000,
            system_budget=55_200,
            conversation_budget=73_600,
            content_budget=55_200,
        )
        assert budget.context_window == 200_000
        assert budget.available_input == 184_000

    def test_total_used_calculation(self):
        """total_used() sums all token counts."""
        budget = ContextBudget(
            model="test",
            context_window=100_000,
            max_output=10_000,
            available_input=90_000,
            system_budget=30_000,
            conversation_budget=30_000,
            content_budget=30_000,
            system_tokens=5_000,
            conversation_tokens=10_000,
            content_tokens=3_000,
        )
        assert budget.total_used() == 18_000

    def test_remaining_calculation(self):
        """remaining() returns available minus used."""
        budget = ContextBudget(
            model="test",
            context_window=100_000,
            max_output=10_000,
            available_input=90_000,
            system_budget=30_000,
            conversation_budget=30_000,
            content_budget=30_000,
            system_tokens=5_000,
            conversation_tokens=10_000,
            content_tokens=3_000,
        )
        assert budget.remaining() == 72_000

    def test_is_over_budget(self):
        """is_over_budget() detects when total exceeds available."""
        budget = ContextBudget(
            model="test",
            context_window=100_000,
            max_output=10_000,
            available_input=10_000,  # Very tight
            system_budget=5_000,
            conversation_budget=3_000,
            content_budget=2_000,
            system_tokens=5_000,
            conversation_tokens=4_000,  # Over budget
            content_tokens=2_000,
        )
        assert budget.is_over_budget()

    def test_needs_summarization_when_over_budget(self):
        """needs_summarization() returns True when conversation over budget."""
        budget = ContextBudget(
            model="test",
            context_window=100_000,
            max_output=10_000,
            available_input=90_000,
            system_budget=30_000,
            conversation_budget=30_000,
            content_budget=30_000,
            system_tokens=5_000,
            conversation_tokens=35_000,  # Over conversation budget
            content_tokens=3_000,
        )
        assert budget.needs_summarization()

    def test_needs_summarization_at_80_percent(self):
        """needs_summarization() returns True at 80% capacity."""
        budget = ContextBudget(
            model="test",
            context_window=100_000,
            max_output=10_000,
            available_input=100_000,
            system_budget=30_000,
            conversation_budget=30_000,
            content_budget=30_000,
            system_tokens=30_000,
            conversation_tokens=30_000,
            content_tokens=25_000,  # Total 85k = 85%
        )
        assert budget.needs_summarization()


class TestConversationSummary:
    """Tests for ConversationSummary model."""

    def test_creates_valid_summary(self):
        """ConversationSummary accepts valid data."""
        summary = ConversationSummary(
            summary="The conversation was about gardening...",
            original_token_count=5000,
            summary_token_count=1000,
            comments_summarized=10,
            savings_percent=80.0,
        )
        assert summary.comments_summarized == 10
        assert summary.savings_percent == 80.0


class TestCountTokens:
    """Tests for count_tokens function."""

    def test_counts_short_text(self):
        """count_tokens handles short text."""
        # "Hello world" is typically 2-3 tokens
        tokens = count_tokens("Hello world")
        assert 1 <= tokens <= 10

    def test_counts_longer_text(self):
        """count_tokens handles longer text."""
        text = "This is a longer piece of text that should have more tokens. " * 10
        tokens = count_tokens(text)
        assert tokens > 50

    def test_handles_empty_string(self):
        """count_tokens handles empty string."""
        tokens = count_tokens("")
        assert tokens == 0


class TestGetContextBudget:
    """Tests for get_context_budget function."""

    def test_returns_budget_for_claude(self):
        """get_context_budget works for Claude model."""
        budget = get_context_budget(model="claude-sonnet-4-5-20250929")
        assert budget.context_window == 200_000
        assert budget.available_input == 200_000 - 16_000

    def test_uses_default_model(self):
        """get_context_budget uses default model when not specified."""
        budget = get_context_budget()
        assert budget.model is not None
        assert budget.context_window > 0

    def test_custom_output_reserve(self):
        """get_context_budget respects custom max_output."""
        budget = get_context_budget(model="claude-sonnet-4-5-20250929", max_output=8000)
        assert budget.max_output == 8000
        assert budget.available_input == 200_000 - 8000

    def test_custom_ratios(self):
        """get_context_budget respects custom ratios."""
        budget = get_context_budget(
            model="claude-sonnet-4-5-20250929",
            system_ratio=0.5,
            conversation_ratio=0.3,
            content_ratio=0.2,
        )
        # Check ratios are approximately correct
        total_budget = budget.system_budget + budget.conversation_budget + budget.content_budget
        assert abs(budget.system_budget / total_budget - 0.5) < 0.01
        assert abs(budget.conversation_budget / total_budget - 0.3) < 0.01


class TestTruncateToBudget:
    """Tests for truncate_to_budget function."""

    def test_returns_unchanged_if_under_budget(self):
        """truncate_to_budget returns original if under budget."""
        text = "Short text"
        result = truncate_to_budget(text, max_tokens=1000)
        assert result == text

    def test_truncates_from_end_by_default(self):
        """truncate_to_budget removes end by default."""
        text = "A" * 10000  # Long text
        result = truncate_to_budget(text, max_tokens=100)
        assert len(result) < len(text)
        assert "truncated" in result.lower()
        assert result.startswith("A")

    def test_truncates_from_beginning_when_keep_end(self):
        """truncate_to_budget removes beginning when keep_end=True."""
        text = "A" * 5000 + "IMPORTANT_END"
        result = truncate_to_budget(text, max_tokens=100, keep_end=True)
        assert "IMPORTANT_END" in result
        assert "truncated" in result.lower()


class TestCheckSystemBudget:
    """Tests for check_system_budget function."""

    def test_no_warning_under_threshold(self, capsys):
        """check_system_budget doesn't warn when under threshold."""
        budget = ContextBudget(
            model="test",
            context_window=100_000,
            max_output=10_000,
            available_input=90_000,
            system_budget=30_000,
            conversation_budget=30_000,
            content_budget=30_000,
            system_tokens=20_000,  # 67% - under 90% threshold
        )

        check_system_budget(budget)

        captured = capsys.readouterr()
        assert "WARNING" not in captured.out

    def test_warns_over_threshold(self, capsys):
        """check_system_budget warns when system tokens exceed threshold."""
        budget = ContextBudget(
            model="test",
            context_window=100_000,
            max_output=10_000,
            available_input=90_000,
            system_budget=30_000,
            conversation_budget=30_000,
            content_budget=30_000,
            system_tokens=28_000,  # 93% - over 90% threshold
        )

        check_system_budget(budget)

        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "93%" in captured.out

    def test_critical_when_over_budget(self, capsys):
        """check_system_budget shows critical when over total budget."""
        budget = ContextBudget(
            model="test",
            context_window=100_000,
            max_output=10_000,
            available_input=50_000,
            system_budget=20_000,
            conversation_budget=20_000,
            content_budget=10_000,
            system_tokens=20_000,
            conversation_tokens=20_000,
            content_tokens=15_000,  # Total 55k > 50k available
        )

        check_system_budget(budget)

        captured = capsys.readouterr()
        assert "CRITICAL" in captured.out


class TestCompactedContext:
    """Tests for CompactedContext model."""

    def test_creates_valid_compacted_context(self):
        """CompactedContext accepts valid data."""
        ctx = CompactedContext(
            summary="Previously completed: 5 questions answered.",
            items_compacted=5,
            references=["Issue #33 (closed)"],
            original_tokens=1000,
            compacted_tokens=50,
        )
        assert ctx.items_compacted == 5
        assert len(ctx.references) == 1


class TestCompactCompletedItems:
    """Tests for compact_completed_items function."""

    def test_returns_empty_for_no_items(self):
        """compact_completed_items returns empty summary for no items."""
        result = compact_completed_items(
            completed_questions=[],
            completed_prerequisites=[],
        )
        assert result.summary == ""
        assert result.items_compacted == 0

    def test_keeps_small_items_uncompacted(self):
        """compact_completed_items keeps small lists mostly intact."""
        result = compact_completed_items(
            completed_questions=["Q1?", "Q2?"],
            completed_prerequisites=[],
        )
        assert result.items_compacted == 2
        assert "Q1?" in result.summary or "Completed:" in result.summary

    def test_compacts_large_lists(self):
        """compact_completed_items summarizes large lists."""
        questions = [f"Question {i} about the book?" for i in range(10)]
        prerequisites = [f"Requirement {i}" for i in range(5)]

        result = compact_completed_items(
            completed_questions=questions,
            completed_prerequisites=prerequisites,
        )

        assert result.items_compacted == 15
        assert "10 questions answered" in result.summary
        assert "5 prerequisites met" in result.summary
        assert result.compacted_tokens < result.original_tokens

    def test_includes_references(self):
        """compact_completed_items includes issue/PR references."""
        result = compact_completed_items(
            completed_questions=["Q1?"] * 10,
            completed_prerequisites=[],
            closed_issues=[33, 34],
            merged_prs=[35],
        )

        assert any("Issue #33" in ref for ref in result.references)
        assert any("PR #35" in ref for ref in result.references)


class TestIntegration:
    """Integration tests for context management."""

    def test_budget_workflow(self):
        """Test typical budget calculation workflow."""
        # Get budget
        budget = get_context_budget(model="claude-sonnet-4-5-20250929")

        # Simulate counting tokens
        system_text = "You are an editor. " * 100
        conversation_text = "User said this. AI said that. " * 200
        content_text = "Chapter content here. " * 50

        budget.system_tokens = count_tokens(system_text)
        budget.conversation_tokens = count_tokens(conversation_text)
        budget.content_tokens = count_tokens(content_text)

        # Check we're within limits
        assert not budget.is_over_budget()
        assert budget.total_used() < budget.available_input
