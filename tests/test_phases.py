"""Tests for phases.py - editorial workflow phases and discovery."""

from scripts.utils.phases import (
    PHASE_LABELS,
    EditorialPhase,
    EmotionalState,
    detect_emotional_state,
    extract_knowledge_items,
    get_phase_label,
    should_skip_discovery,
)


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
