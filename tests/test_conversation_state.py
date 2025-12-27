"""Tests for conversation state tracking."""

import pytest
from pydantic import ValidationError
from scripts.utils.conversation_state import (
    STATE_SECTION_END, STATE_SECTION_MARKER, ConversationState,
    EstablishedFact, OutstandingQuestion, Prerequisite,
    compact_state, extract_questions_from_response, format_closing_summary,
    format_outstanding_questions_reminder, format_prerequisite_blocker,
    format_state_markdown, get_context_references, get_default_prerequisites,
    parse_state_from_body, persist_to_knowledge_base, update_issue_body_with_state)


class TestEstablishedFact:
    """Tests for EstablishedFact model."""

    def test_validates_correct_data(self):
        """EstablishedFact accepts valid data."""
        fact = EstablishedFact(key="audience", value="Urban renters")
        assert fact.key == "audience"
        assert fact.value == "Urban renters"

    def test_optional_timestamp(self):
        """EstablishedFact works without timestamp."""
        fact = EstablishedFact(key="tone", value="Encouraging")
        assert fact.established_at is None


class TestOutstandingQuestion:
    """Tests for OutstandingQuestion model."""

    def test_validates_correct_data(self):
        """OutstandingQuestion accepts valid data."""
        q = OutstandingQuestion(
            question="What's your transformation arc?",
            asked_at="2025-12-26T23:40:00Z",
            answered=False,
        )
        assert q.question == "What's your transformation arc?"
        assert not q.answered

    def test_default_answered_false(self):
        """OutstandingQuestion defaults to not answered."""
        q = OutstandingQuestion(
            question="Test?",
            asked_at="2025-12-26T00:00:00Z",
        )
        assert not q.answered


class TestPrerequisite:
    """Tests for Prerequisite model."""

    def test_validates_correct_data(self):
        """Prerequisite accepts valid data."""
        p = Prerequisite(
            requirement="Content outline defined",
            met=False,
            blocks="pr_creation",
        )
        assert p.requirement == "Content outline defined"
        assert not p.met

    def test_default_blocks_pr_creation(self):
        """Prerequisite defaults to blocking PR creation."""
        p = Prerequisite(requirement="Test requirement", met=False)
        assert p.blocks == "pr_creation"


class TestConversationState:
    """Tests for ConversationState model."""

    def test_creates_empty_state(self):
        """ConversationState can be created with minimal data."""
        state = ConversationState(issue_number=42)
        assert state.issue_number == 42
        assert state.phase == "discovery"
        assert state.established == []
        assert state.outstanding_questions == []

    def test_has_unanswered_questions(self):
        """has_unanswered_questions returns True when questions exist."""
        state = ConversationState(issue_number=1)
        state.add_question("What's your goal?")
        assert state.has_unanswered_questions()

    def test_has_unanswered_questions_false_when_answered(self):
        """has_unanswered_questions returns False when all answered."""
        state = ConversationState(issue_number=1)
        state.add_question("What's your goal?")
        state.mark_question_answered("goal")
        assert not state.has_unanswered_questions()

    def test_add_question_prevents_duplicates(self):
        """add_question doesn't add duplicate questions."""
        state = ConversationState(issue_number=1)
        state.add_question("What's your goal?")
        state.add_question("What's your goal?")
        state.add_question("WHAT'S YOUR GOAL?")  # Case insensitive
        assert len(state.outstanding_questions) == 1

    def test_mark_question_answered_by_substring(self):
        """mark_question_answered matches by substring."""
        state = ConversationState(issue_number=1)
        state.add_question("What's your transformation arc for the reader?")
        result = state.mark_question_answered("transformation arc")
        assert result is True
        assert state.outstanding_questions[0].answered is True

    def test_establish_fact(self):
        """establish_fact adds new facts."""
        state = ConversationState(issue_number=1)
        state.establish_fact("audience", "Urban renters")
        assert len(state.established) == 1
        assert state.established[0].key == "audience"
        assert state.established[0].value == "Urban renters"

    def test_establish_fact_updates_existing(self):
        """establish_fact updates existing facts."""
        state = ConversationState(issue_number=1)
        state.establish_fact("audience", "Urban renters")
        state.establish_fact("audience", "Millennials in cities")
        assert len(state.established) == 1
        assert state.established[0].value == "Millennials in cities"

    def test_has_unmet_prerequisites(self):
        """has_unmet_prerequisites returns True when prerequisites unmet."""
        state = ConversationState(issue_number=1)
        state.add_prerequisite("Content written")
        assert state.has_unmet_prerequisites()

    def test_has_unmet_prerequisites_false_when_met(self):
        """has_unmet_prerequisites returns False when all met."""
        state = ConversationState(issue_number=1)
        state.add_prerequisite("Content written")
        state.mark_prerequisite_met("content")
        assert not state.has_unmet_prerequisites()

    def test_add_prerequisite_prevents_duplicates(self):
        """add_prerequisite doesn't add duplicates."""
        state = ConversationState(issue_number=1)
        state.add_prerequisite("Content written")
        state.add_prerequisite("Content written")
        assert len(state.prerequisites) == 1


class TestFormatStateMarkdown:
    """Tests for format_state_markdown function."""

    def test_includes_markers(self):
        """Formatted markdown includes section markers."""
        state = ConversationState(issue_number=42)
        md = format_state_markdown(state)
        assert STATE_SECTION_MARKER in md
        assert STATE_SECTION_END in md

    def test_includes_phase(self):
        """Formatted markdown includes phase."""
        state = ConversationState(issue_number=42, phase="feedback")
        md = format_state_markdown(state)
        assert "**Phase:** Feedback" in md

    def test_includes_established_facts(self):
        """Formatted markdown includes established facts."""
        state = ConversationState(issue_number=42)
        state.establish_fact("audience", "Urban renters")
        state.establish_fact("tone", "Encouraging")
        md = format_state_markdown(state)
        assert "### ✅ Established" in md
        assert "**audience:** Urban renters" in md
        assert "**tone:** Encouraging" in md

    def test_includes_outstanding_questions(self):
        """Formatted markdown includes outstanding questions as checkboxes."""
        state = ConversationState(issue_number=42)
        state.add_question("What's your transformation arc?")
        md = format_state_markdown(state)
        assert "### ⏳ Questions Awaiting Your Response" in md
        assert "- [ ] What's your transformation arc?" in md

    def test_includes_prerequisites(self):
        """Formatted markdown includes prerequisites as checkboxes."""
        state = ConversationState(issue_number=42)
        state.add_prerequisite("Content outline defined")
        state.add_prerequisite("First draft written")
        state.mark_prerequisite_met("outline")
        md = format_state_markdown(state)
        assert "### 🚧 Prerequisites for PR" in md
        assert "- [x] Content outline defined" in md
        assert "- [ ] First draft written" in md


class TestParseStateFromBody:
    """Tests for parse_state_from_body function."""

    def test_returns_empty_state_when_no_section(self):
        """Returns empty state when no state section exists."""
        body = "# Voice Memo\n\nSome content here."
        state = parse_state_from_body(body, issue_number=42)
        assert state.issue_number == 42
        assert state.established == []

    def test_parses_phase(self):
        """Parses phase from state section."""
        body = f"""# Voice Memo

{STATE_SECTION_MARKER}
## 📊 Editorial Progress

**Phase:** Feedback

{STATE_SECTION_END}
"""
        state = parse_state_from_body(body, issue_number=42)
        assert state.phase == "feedback"

    def test_parses_established_facts(self):
        """Parses established facts from state section."""
        body = f"""# Voice Memo

{STATE_SECTION_MARKER}
## 📊 Editorial Progress

**Phase:** Discovery

### ✅ Established
- **audience:** Urban renters
- **tone:** Encouraging

{STATE_SECTION_END}
"""
        state = parse_state_from_body(body, issue_number=42)
        assert len(state.established) == 2
        assert state.established[0].key == "audience"
        assert state.established[0].value == "Urban renters"

    def test_parses_outstanding_questions(self):
        """Parses outstanding questions with checkbox state."""
        body = f"""# Voice Memo

{STATE_SECTION_MARKER}
## 📊 Editorial Progress

**Phase:** Feedback

### ⏳ Questions Awaiting Your Response
- [ ] What's your transformation arc?
- [x] What's your audience?

{STATE_SECTION_END}
"""
        state = parse_state_from_body(body, issue_number=42)
        assert len(state.outstanding_questions) == 2
        assert not state.outstanding_questions[0].answered
        assert state.outstanding_questions[1].answered

    def test_parses_prerequisites(self):
        """Parses prerequisites with checkbox state."""
        body = f"""# Voice Memo

{STATE_SECTION_MARKER}
## 📊 Editorial Progress

**Phase:** Feedback

### 🚧 Prerequisites for PR
- [x] Content outline defined
- [ ] First draft written

*Updated by AI Editor*
{STATE_SECTION_END}
"""
        state = parse_state_from_body(body, issue_number=42)
        assert len(state.prerequisites) == 2
        assert state.prerequisites[0].met is True
        assert state.prerequisites[1].met is False


class TestUpdateIssueBodyWithState:
    """Tests for update_issue_body_with_state function."""

    def test_appends_to_body_without_state(self):
        """Appends state section to body without existing state."""
        body = "# Voice Memo\n\nContent here."
        state = ConversationState(issue_number=42)
        state.establish_fact("audience", "Testers")

        result = update_issue_body_with_state(body, state)

        assert body in result
        assert STATE_SECTION_MARKER in result
        assert "**audience:** Testers" in result

    def test_replaces_existing_state(self):
        """Replaces existing state section."""
        body = f"""# Voice Memo

Content here.

---

{STATE_SECTION_MARKER}
## 📊 Editorial Progress

**Phase:** Discovery

{STATE_SECTION_END}

Footer content.
"""
        state = ConversationState(issue_number=42, phase="feedback")
        state.establish_fact("audience", "Updated audience")

        result = update_issue_body_with_state(body, state)

        # Should have new phase
        assert "**Phase:** Feedback" in result
        # Should have new fact
        assert "**audience:** Updated audience" in result
        # Should preserve other content
        assert "# Voice Memo" in result
        assert "Content here." in result
        # Should only have one state section
        assert result.count(STATE_SECTION_MARKER) == 1


class TestFormatOutstandingQuestionsReminder:
    """Tests for format_outstanding_questions_reminder function."""

    def test_returns_empty_when_no_questions(self):
        """Returns empty string when no unanswered questions."""
        state = ConversationState(issue_number=42)
        result = format_outstanding_questions_reminder(state)
        assert result == ""

    def test_formats_questions(self):
        """Formats unanswered questions as reminder."""
        state = ConversationState(issue_number=42)
        state.add_question("What's your goal?")
        state.add_question("Who's your audience?")

        result = format_outstanding_questions_reminder(state)

        assert "Still waiting for your thoughts on:" in result
        assert "What's your goal?" in result
        assert "Who's your audience?" in result

    def test_limits_to_three_questions(self):
        """Limits reminder to top 3 questions."""
        state = ConversationState(issue_number=42)
        for i in range(5):
            state.add_question(f"Question {i}?")

        result = format_outstanding_questions_reminder(state)

        assert "Question 0?" in result
        assert "Question 1?" in result
        assert "Question 2?" in result
        assert "and 2 more" in result


class TestFormatPrerequisiteBlocker:
    """Tests for format_prerequisite_blocker function."""

    def test_returns_empty_when_no_blockers(self):
        """Returns empty string when nothing blocks."""
        state = ConversationState(issue_number=42)
        result = format_prerequisite_blocker(state)
        assert result == ""

    def test_formats_unmet_prerequisites(self):
        """Formats unmet prerequisites as blocker message."""
        state = ConversationState(issue_number=42)
        state.add_prerequisite("Content outline defined")
        state.add_prerequisite("First draft written")

        result = format_prerequisite_blocker(state)

        assert "Before I can create a PR" in result
        assert "Content outline defined" in result
        assert "First draft written" in result

    def test_includes_unanswered_questions(self):
        """Includes unanswered questions in blocker message."""
        state = ConversationState(issue_number=42)
        state.add_question("What's your transformation arc?")

        result = format_prerequisite_blocker(state)

        assert "Questions awaiting your response" in result
        assert "transformation arc" in result


class TestExtractQuestionsFromResponse:
    """Tests for extract_questions_from_response function."""

    def test_extracts_bold_questions(self):
        """Extracts questions in bold formatting."""
        response = """Here's my feedback.

**What's the transformation arc for your reader?**

And another point.

**What does success look like at the end?**
"""
        questions = extract_questions_from_response(response)
        assert len(questions) == 2
        assert any("transformation arc" in q for q in questions)

    def test_filters_short_questions(self):
        """Filters out short/rhetorical questions."""
        response = """**Sound good?**

**What's your detailed plan for the chapter structure?**
"""
        questions = extract_questions_from_response(response)
        # "Sound good?" should be filtered
        assert len(questions) == 1
        assert "chapter structure" in questions[0]

    def test_deduplicates_questions(self):
        """Removes duplicate questions."""
        response = """
**What's your transformation arc for your reader?**

Let me repeat: **What's your transformation arc for your reader?**
"""
        questions = extract_questions_from_response(response)
        assert len(questions) == 1


class TestGetDefaultPrerequisites:
    """Tests for get_default_prerequisites function."""

    def test_returns_prerequisites(self):
        """Returns list of default prerequisites."""
        prereqs = get_default_prerequisites()
        assert len(prereqs) >= 2
        assert all(isinstance(p, Prerequisite) for p in prereqs)
        assert all(not p.met for p in prereqs)


class TestCompactState:
    """Tests for compact_state function."""

    def test_removes_answered_questions(self):
        """compact_state removes answered questions."""
        state = ConversationState(issue_number=42)
        state.add_question("Question 1?")
        state.add_question("Question 2?")
        state.mark_question_answered("Question 1")

        compacted = compact_state(state)

        assert len(compacted.outstanding_questions) == 1
        assert compacted.outstanding_questions[0].question == "Question 2?"

    def test_removes_met_prerequisites(self):
        """compact_state removes met prerequisites."""
        state = ConversationState(issue_number=42)
        state.add_prerequisite("Requirement A")
        state.add_prerequisite("Requirement B")
        state.mark_prerequisite_met("Requirement A")

        compacted = compact_state(state)

        assert len(compacted.prerequisites) == 1
        assert compacted.prerequisites[0].requirement == "Requirement B"

    def test_preserves_established_facts(self):
        """compact_state keeps all established facts."""
        state = ConversationState(issue_number=42)
        state.establish_fact("audience", "Urban renters")
        state.establish_fact("tone", "Encouraging")

        compacted = compact_state(state)

        assert len(compacted.established) == 2

    def test_preserves_phase_and_issue_number(self):
        """compact_state preserves metadata."""
        state = ConversationState(issue_number=42, phase="feedback")

        compacted = compact_state(state)

        assert compacted.issue_number == 42
        assert compacted.phase == "feedback"


class TestPersistToKnowledgeBase:
    """Tests for persist_to_knowledge_base function."""

    def test_writes_facts_to_file(self, tmp_path):
        """persist_to_knowledge_base writes facts to JSONL file."""
        import json

        knowledge_path = tmp_path / "knowledge.jsonl"
        state = ConversationState(issue_number=42)
        state.establish_fact("audience", "Urban renters")
        state.establish_fact("tone", "Encouraging")

        written = persist_to_knowledge_base(state, str(knowledge_path))

        assert written == 2
        assert knowledge_path.exists()

        lines = knowledge_path.read_text().strip().split("\n")
        assert len(lines) == 2

        entry = json.loads(lines[0])
        assert entry["type"] == "established_fact"
        assert entry["source_issue"] == 42

    def test_skips_duplicates(self, tmp_path):
        """persist_to_knowledge_base doesn't write duplicate keys."""
        import json

        knowledge_path = tmp_path / "knowledge.jsonl"

        # Write initial fact
        state1 = ConversationState(issue_number=42)
        state1.establish_fact("audience", "Urban renters")
        persist_to_knowledge_base(state1, str(knowledge_path))

        # Try to write same key from different issue
        state2 = ConversationState(issue_number=43)
        state2.establish_fact("audience", "Different value")
        written = persist_to_knowledge_base(state2, str(knowledge_path))

        assert written == 0  # Duplicate key not written

        lines = knowledge_path.read_text().strip().split("\n")
        assert len(lines) == 1  # Still only one entry

    def test_returns_zero_for_empty_state(self, tmp_path):
        """persist_to_knowledge_base returns 0 for empty state."""
        knowledge_path = tmp_path / "knowledge.jsonl"
        state = ConversationState(issue_number=42)

        written = persist_to_knowledge_base(state, str(knowledge_path))

        assert written == 0


class TestGetContextReferences:
    """Tests for get_context_references function."""

    def test_returns_references(self):
        """get_context_references returns list of reference strings."""
        refs = get_context_references(issue_number=42)

        assert len(refs) >= 1
        assert any("42" in ref for ref in refs)
        assert any("knowledge.jsonl" in ref for ref in refs)


class TestFormatClosingSummary:
    """Tests for format_closing_summary function."""

    def test_includes_status(self):
        """format_closing_summary includes status."""
        state = ConversationState(issue_number=42)
        summary = format_closing_summary(state, reason="completed")

        assert "## 📋 Issue Summary" in summary
        assert "✅ Completed" in summary

    def test_includes_related_pr(self):
        """format_closing_summary includes related PR when provided."""
        state = ConversationState(issue_number=42)
        summary = format_closing_summary(state, related_pr=43)

        assert "**Related PR:** #43" in summary

    def test_includes_decisions_made(self):
        """format_closing_summary includes established facts as decisions."""
        state = ConversationState(issue_number=42)
        state.establish_fact("audience", "Urban renters")
        state.establish_fact("tone", "Encouraging")

        summary = format_closing_summary(state)

        assert "### Decisions Made" in summary
        assert "audience" in summary
        assert "Urban renters" in summary

    def test_includes_answered_questions(self):
        """format_closing_summary shows resolved questions."""
        state = ConversationState(issue_number=42)
        state.add_question("What's the transformation arc?")
        state.mark_question_answered("transformation")

        summary = format_closing_summary(state)

        assert "### Questions Resolved" in summary
        assert "✅" in summary

    def test_includes_deferred_questions(self):
        """format_closing_summary shows unanswered questions as deferred."""
        state = ConversationState(issue_number=42)
        state.add_question("What's the transformation arc?")
        # Don't mark as answered

        summary = format_closing_summary(state)

        assert "### Deferred Questions" in summary
        assert "⏳" in summary

    def test_includes_context_references(self):
        """format_closing_summary includes future reference section."""
        state = ConversationState(issue_number=42)
        summary = format_closing_summary(state)

        assert "### For Future Reference" in summary
        assert "knowledge.jsonl" in summary
