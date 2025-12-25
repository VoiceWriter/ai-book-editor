"""Tests for phases.py - editorial workflow phases and discovery."""

from scripts.utils.phases import (
    BOOK_PHASE_CONFIG,
    PHASE_LABELS,
    BookPhase,
    EditorialPhase,
    EmotionalState,
    detect_emotional_state,
    extract_knowledge_items,
    get_book_phase_guidance,
    get_phase_label,
    should_skip_discovery,
    suggest_phase_transition,
)


class TestBookPhase:
    """Test BookPhase enum and configuration."""

    def test_all_book_phases_exist(self):
        """All expected book phases should exist."""
        expected_phases = ["new", "drafting", "revising", "polishing", "complete"]
        for phase_value in expected_phases:
            phase = BookPhase(phase_value)
            assert phase.value == phase_value

    def test_all_book_phases_have_config(self):
        """Every book phase should have a configuration."""
        for phase in BookPhase:
            assert phase in BOOK_PHASE_CONFIG
            config = BOOK_PHASE_CONFIG[phase]
            assert "name" in config
            assert "description" in config
            assert "editor_focus" in config
            assert "feedback_style" in config
            assert "criticism_level" in config

    def test_book_phase_feedback_styles(self):
        """Book phases should have appropriate feedback styles."""
        assert BOOK_PHASE_CONFIG[BookPhase.NEW]["feedback_style"] == "encouraging"
        assert BOOK_PHASE_CONFIG[BookPhase.DRAFTING]["feedback_style"] == "balanced"
        assert BOOK_PHASE_CONFIG[BookPhase.REVISING]["feedback_style"] == "rigorous"
        assert BOOK_PHASE_CONFIG[BookPhase.POLISHING]["feedback_style"] == "precise"
        assert BOOK_PHASE_CONFIG[BookPhase.COMPLETE]["feedback_style"] == "celebratory"

    def test_book_phase_criticism_levels(self):
        """Criticism level should increase with phase progression."""
        assert BOOK_PHASE_CONFIG[BookPhase.NEW]["criticism_level"] == "minimal"
        assert BOOK_PHASE_CONFIG[BookPhase.DRAFTING]["criticism_level"] == "moderate"
        assert BOOK_PHASE_CONFIG[BookPhase.REVISING]["criticism_level"] == "high"
        assert BOOK_PHASE_CONFIG[BookPhase.POLISHING]["criticism_level"] == "detailed"
        assert BOOK_PHASE_CONFIG[BookPhase.COMPLETE]["criticism_level"] == "none"


class TestGetBookPhaseGuidance:
    """Test get_book_phase_guidance function."""

    def test_returns_formatted_guidance_for_new(self):
        """Should return formatted guidance for NEW phase."""
        result = get_book_phase_guidance(BookPhase.NEW)
        assert "## Book Phase: New Project" in result
        assert "encouraging" in result
        assert "minimal" in result

    def test_returns_formatted_guidance_for_revising(self):
        """Should return formatted guidance for REVISING phase."""
        result = get_book_phase_guidance(BookPhase.REVISING)
        assert "## Book Phase: Revising" in result
        assert "rigorous" in result
        assert "high" in result

    def test_includes_editor_focus_items(self):
        """Should include all editor focus items."""
        result = get_book_phase_guidance(BookPhase.DRAFTING)
        assert "Your focus at this phase" in result
        # Check for at least one focus item
        assert "Balance encouragement with substantive feedback" in result

    def test_all_phases_produce_valid_guidance(self):
        """All phases should produce non-empty guidance."""
        for phase in BookPhase:
            result = get_book_phase_guidance(phase)
            assert result
            assert "## Book Phase:" in result


class TestSuggestPhaseTransition:
    """Test suggest_phase_transition function."""

    def test_new_to_drafting_with_chapters(self):
        """Should suggest DRAFTING when enough chapters exist."""
        result = suggest_phase_transition(
            current_phase=BookPhase.NEW,
            chapters_drafted=2,
            chapters_planned=10,
            author_signals=[],
        )
        assert result == BookPhase.DRAFTING

    def test_new_to_drafting_explicit_ready(self):
        """Should suggest DRAFTING when author is ready."""
        result = suggest_phase_transition(
            current_phase=BookPhase.NEW,
            chapters_drafted=0,
            chapters_planned=10,
            author_signals=["I think I'm ready for the next phase"],
        )
        assert result == BookPhase.DRAFTING

    def test_drafting_to_revising_all_drafted(self):
        """Should suggest REVISING when all chapters drafted."""
        result = suggest_phase_transition(
            current_phase=BookPhase.DRAFTING,
            chapters_drafted=10,
            chapters_planned=10,
            author_signals=[],
        )
        assert result == BookPhase.REVISING

    def test_drafting_to_revising_explicit(self):
        """Should suggest REVISING when author says time to revise."""
        result = suggest_phase_transition(
            current_phase=BookPhase.DRAFTING,
            chapters_drafted=5,
            chapters_planned=10,
            author_signals=["Time to revise what I have"],
        )
        assert result == BookPhase.REVISING

    def test_revising_to_polishing(self):
        """Should suggest POLISHING when author ready for polish."""
        result = suggest_phase_transition(
            current_phase=BookPhase.REVISING,
            chapters_drafted=10,
            chapters_planned=10,
            author_signals=["Let's polish this up"],
        )
        assert result == BookPhase.POLISHING

    def test_polishing_to_complete(self):
        """Should suggest COMPLETE when author says done."""
        result = suggest_phase_transition(
            current_phase=BookPhase.POLISHING,
            chapters_drafted=10,
            chapters_planned=10,
            author_signals=["I think we're done!"],
        )
        assert result == BookPhase.COMPLETE

    def test_no_transition_when_not_ready(self):
        """Should return None when no transition is warranted."""
        result = suggest_phase_transition(
            current_phase=BookPhase.NEW,
            chapters_drafted=0,
            chapters_planned=10,
            author_signals=["Just getting started"],
        )
        assert result is None

    def test_complete_never_transitions(self):
        """COMPLETE phase should not transition anywhere."""
        result = suggest_phase_transition(
            current_phase=BookPhase.COMPLETE,
            chapters_drafted=10,
            chapters_planned=10,
            author_signals=["What's next?"],
        )
        assert result is None


class TestEditorialPhase:
    """Test EditorialPhase enum and labels."""

    def test_all_phases_have_labels(self):
        """Every phase should have a label configuration."""
        for phase in EditorialPhase:
            assert phase in PHASE_LABELS
            assert "name" in PHASE_LABELS[phase]
            assert "color" in PHASE_LABELS[phase]
            assert "description" in PHASE_LABELS[phase]

    def test_get_phase_label(self):
        """get_phase_label returns correct label name."""
        assert get_phase_label(EditorialPhase.DISCOVERY) == "phase:discovery"
        assert get_phase_label(EditorialPhase.FEEDBACK) == "phase:feedback"
        assert get_phase_label(EditorialPhase.REVISION) == "phase:revision"


class TestEmotionalStateDetection:
    """Test emotional state detection from text."""

    def test_detect_vulnerable(self):
        """Detects vulnerable emotional state."""
        text = "This is a rough first draft, I'm not sure if it's any good."
        result = detect_emotional_state(text)
        assert result == EmotionalState.VULNERABLE

    def test_detect_confident(self):
        """Detects confident emotional state."""
        text = "This is my final draft, ready for feedback. Don't hold back."
        result = detect_emotional_state(text)
        assert result == EmotionalState.CONFIDENT

    def test_detect_frustrated(self):
        """Detects frustrated emotional state."""
        text = "Ugh, I'm so stuck on this. Nothing works, I hate this chapter."
        result = detect_emotional_state(text)
        assert result == EmotionalState.FRUSTRATED

    def test_detect_blocked(self):
        """Detects blocked emotional state."""
        text = "I'm completely blocked. Can't start, blank page syndrome."
        result = detect_emotional_state(text)
        assert result == EmotionalState.BLOCKED

    def test_detect_excited(self):
        """Detects excited emotional state."""
        text = "I love this! Finally had a breakthrough, so excited to share."
        result = detect_emotional_state(text)
        assert result == EmotionalState.EXCITED

    def test_no_clear_state(self):
        """Returns None when no clear emotional state detected."""
        text = "Here is my chapter about machine learning algorithms."
        result = detect_emotional_state(text)
        assert result is None


class TestShouldSkipDiscovery:
    """Test discovery skip detection."""

    def test_skip_explicit_phrase(self):
        """Skips when author explicitly says 'skip discovery'."""
        text = "Please skip discovery and just review this."
        assert should_skip_discovery(text, []) is True

    def test_skip_just_review(self):
        """Skips when author says 'just review'."""
        text = "Just review this for me."
        assert should_skip_discovery(text, []) is True

    def test_skip_confident_language(self):
        """Skips when author uses confident language."""
        text = "Tear it apart, I'm ready for brutal feedback."
        assert should_skip_discovery(text, []) is True

    def test_skip_quick_review_label(self):
        """Skips when quick-review label is present."""
        text = "Here's my draft."
        labels = ["voice_transcription", "quick-review"]
        assert should_skip_discovery(text, labels) is True

    def test_skip_feedback_phase_label(self):
        """Skips when already in feedback phase."""
        text = "Here's my draft."
        labels = ["voice_transcription", "phase:feedback"]
        assert should_skip_discovery(text, labels) is True

    def test_no_skip_normal_text(self):
        """Doesn't skip for normal submission text."""
        text = "Here's my voice memo from this morning."
        labels = ["voice_transcription"]
        assert should_skip_discovery(text, labels) is False


class TestKnowledgeExtraction:
    """Test knowledge item extraction from author text."""

    def test_extract_preference(self):
        """Extracts author preferences."""
        text = "I prefer to write in first person. I always start with dialogue."
        items = extract_knowledge_items(text)
        assert len(items) >= 1
        assert any(item["type"] == "preference" for item in items)

    def test_extract_goal(self):
        """Extracts writing goals."""
        text = "I want readers to feel empowered. The goal is to make AI accessible."
        items = extract_knowledge_items(text)
        assert len(items) >= 1
        assert any(item["type"] == "goal" for item in items)

    def test_extract_audience(self):
        """Extracts audience information."""
        text = "My readers are tech-savvy professionals who want to learn."
        items = extract_knowledge_items(text)
        assert len(items) >= 1
        assert any(item["type"] == "audience" for item in items)

    def test_extract_correction(self):
        """Extracts author corrections."""
        text = "Actually, that's not what I meant. Let me clarify."
        items = extract_knowledge_items(text)
        assert len(items) >= 1
        assert any(item["type"] == "correction" for item in items)

    def test_no_extraction_plain_text(self):
        """Returns empty list for plain text without patterns."""
        text = "The quick brown fox jumps over the lazy dog."
        items = extract_knowledge_items(text)
        assert items == []
