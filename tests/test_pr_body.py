"""Tests for rich PR body generation."""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Add scripts path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))

from scripts.utils.pr_body import (
    ContentAnalysis,
    DecisionRecord,
    DiscoveryContext,
    RichPRBody,
    StructuralAnalysis,
    TextDelta,
    VoiceAnalysis,
    format_rich_pr_body,
)


class TestContentAnalysis:
    """Tests for ContentAnalysis Pydantic model."""

    def test_validates_correct_data(self):
        """ContentAnalysis accepts valid data."""
        data = {
            "word_count": 500,
            "reading_time_minutes": 2.5,
            "flesch_reading_ease": 65.0,
            "flesch_kincaid_grade": 8.0,
            "avg_sentence_length": 15.0,
            "lexical_diversity": 0.65,
            "passive_voice_percent": 10.0,
            "corpus_comparison": [],
        }
        result = ContentAnalysis.model_validate(data)
        assert result.word_count == 500
        assert result.flesch_reading_ease == 65.0

    def test_rejects_missing_required_fields(self):
        """ContentAnalysis fails on missing required fields."""
        with pytest.raises(ValidationError):
            ContentAnalysis.model_validate({"word_count": 500})

    def test_rejects_wrong_types(self):
        """ContentAnalysis fails on wrong types in strict mode."""
        with pytest.raises(ValidationError):
            ContentAnalysis.model_validate(
                {
                    "word_count": "not a number",  # Should be int
                    "reading_time_minutes": 2.5,
                    "flesch_reading_ease": 65.0,
                    "flesch_kincaid_grade": 8.0,
                    "avg_sentence_length": 15.0,
                    "lexical_diversity": 0.65,
                    "passive_voice_percent": 10.0,
                    "corpus_comparison": [],
                }
            )


class TestTextDelta:
    """Tests for TextDelta Pydantic model."""

    def test_validates_with_optional_fields(self):
        """TextDelta accepts data with optional before/delta."""
        delta = TextDelta(
            metric="Reading Ease",
            before=None,
            after=65.0,
            delta=None,
            interpretation="Moderate readability",
        )
        assert delta.metric == "Reading Ease"
        assert delta.before is None

    def test_validates_full_comparison(self):
        """TextDelta accepts full before/after comparison."""
        delta = TextDelta(
            metric="Word Count",
            before=1000.0,
            after=1500.0,
            delta=500.0,
            interpretation="Added 500 words",
        )
        assert delta.delta == 500.0


class TestStructuralAnalysis:
    """Tests for StructuralAnalysis Pydantic model."""

    def test_validates_correct_data(self):
        """StructuralAnalysis accepts valid data."""
        sa = StructuralAnalysis(
            target_file="chapters/chapter-01.md",
            placement_rationale="Fits thematically with introduction",
            related_chapters=["chapter-02.md"],
            thematic_connections=["identity", "growth"],
            flow_impact="Strengthens opening arc",
        )
        assert sa.target_file == "chapters/chapter-01.md"
        assert len(sa.related_chapters) == 1


class TestVoiceAnalysis:
    """Tests for VoiceAnalysis Pydantic model."""

    def test_validates_correct_data(self):
        """VoiceAnalysis accepts valid data."""
        va = VoiceAnalysis(
            voice_score="high",
            voice_markers=["conversational tone", "specific examples"],
            transformations=["cleaned filler words"],
        )
        assert va.voice_score == "high"


class TestDiscoveryContext:
    """Tests for DiscoveryContext Pydantic model."""

    def test_validates_with_defaults(self):
        """DiscoveryContext works with default empty lists."""
        dc = DiscoveryContext()
        assert dc.questions_asked == []
        assert dc.emotional_state is None

    def test_validates_full_context(self):
        """DiscoveryContext accepts full discovery data."""
        dc = DiscoveryContext(
            questions_asked=["What's your goal?", "Who's your audience?"],
            author_responses=["I want to inspire", "Urban renters"],
            emotional_state="excited",
            key_learnings=["Writing for beginners"],
        )
        assert len(dc.questions_asked) == 2


class TestDecisionRecord:
    """Tests for DecisionRecord Pydantic model."""

    def test_validates_minimal_decision(self):
        """DecisionRecord works with just decision text."""
        dr = DecisionRecord(decision="Use chapter-03 as target")
        assert dr.decision == "Use chapter-03 as target"
        assert dr.context is None

    def test_validates_full_decision(self):
        """DecisionRecord works with decision and context."""
        dr = DecisionRecord(
            decision="audience: Urban renters",
            context="Established in issue #33",
        )
        assert dr.decision == "audience: Urban renters"
        assert dr.context == "Established in issue #33"


class TestRichPRBody:
    """Tests for RichPRBody Pydantic model."""

    @pytest.fixture
    def content_analysis(self):
        """Create a valid ContentAnalysis for testing."""
        return ContentAnalysis(
            word_count=500,
            reading_time_minutes=2.5,
            flesch_reading_ease=65.0,
            flesch_kincaid_grade=8.0,
            avg_sentence_length=15.0,
            lexical_diversity=0.65,
            passive_voice_percent=10.0,
            corpus_comparison=[],
        )

    @pytest.fixture
    def structural_analysis(self):
        """Create a valid StructuralAnalysis for testing."""
        return StructuralAnalysis(
            target_file="chapters/chapter-01.md",
            placement_rationale="Test rationale",
            related_chapters=[],
            thematic_connections=[],
            flow_impact="Minimal",
        )

    @pytest.fixture
    def voice_analysis(self):
        """Create a valid VoiceAnalysis for testing."""
        return VoiceAnalysis(
            voice_score="high",
            voice_markers=["test marker"],
            transformations=["test transform"],
        )

    def test_validates_complete_pr_body(
        self, content_analysis, structural_analysis, voice_analysis
    ):
        """RichPRBody validates with all components."""
        pr = RichPRBody(
            source_issue=42,
            target_file="chapters/chapter-01.md",
            content_analysis=content_analysis,
            structural=structural_analysis,
            voice=voice_analysis,
            discovery=None,
            editorial_reasoning="Detailed reasoning here",
            editorial_notes="Notes for author",
            content_summary="Summary of content",
            llm_usage_summary="1000 tokens, $0.01",
        )
        assert pr.source_issue == 42
        assert pr.content_analysis.word_count == 500

    def test_validates_with_discovery_context(
        self, content_analysis, structural_analysis, voice_analysis
    ):
        """RichPRBody accepts optional discovery context."""
        dc = DiscoveryContext(
            questions_asked=["What's your goal?"],
            author_responses=["Inspire readers"],
        )
        pr = RichPRBody(
            source_issue=42,
            target_file="chapters/chapter-01.md",
            content_analysis=content_analysis,
            structural=structural_analysis,
            voice=voice_analysis,
            discovery=dc,
            editorial_reasoning="Reasoning",
            editorial_notes="Notes",
            content_summary="Summary",
            llm_usage_summary="Usage",
        )
        assert pr.discovery is not None
        assert len(pr.discovery.questions_asked) == 1


class TestFormatRichPRBody:
    """Tests for format_rich_pr_body function."""

    @pytest.fixture
    def rich_pr_body(self):
        """Create a complete RichPRBody for formatting tests."""
        return RichPRBody(
            source_issue=33,
            target_file="chapters/apartment-gardening.md",
            content_analysis=ContentAnalysis(
                word_count=1250,
                reading_time_minutes=6.25,
                flesch_reading_ease=72.5,
                flesch_kincaid_grade=6.8,
                avg_sentence_length=14.2,
                lexical_diversity=0.58,
                passive_voice_percent=8.3,
                corpus_comparison=[
                    TextDelta(
                        metric="Readability",
                        before=68.0,
                        after=72.5,
                        delta=4.5,
                        interpretation="Slightly easier to read",
                    )
                ],
            ),
            structural=StructuralAnalysis(
                target_file="chapters/apartment-gardening.md",
                placement_rationale="Opening chapter to set the mindset",
                related_chapters=["chapter-02-containers.md"],
                thematic_connections=["accessibility", "empowerment"],
                flow_impact="Strong opening hook for the book",
            ),
            voice=VoiceAnalysis(
                voice_score="high",
                voice_markers=["encouraging tone", "practical examples"],
                transformations=["removed filler words", "structured into paragraphs"],
            ),
            discovery=DiscoveryContext(
                questions_asked=["What's your goal?"],
                author_responses=["Help apartment dwellers grow food"],
                emotional_state="excited",
                key_learnings=["Focus on beginners", "Start simple"],
            ),
            editorial_reasoning="The content establishes a strong emotional connection...",
            editorial_notes="Consider adding specific container recommendations.",
            content_summary="Introduction to apartment gardening mindset shift.",
            llm_usage_summary="**AI Usage:** 5,000 tokens · $0.0175",
        )

    def test_format_includes_header(self, rich_pr_body):
        """Formatted body includes proper header."""
        body = format_rich_pr_body(rich_pr_body)
        assert "## 📝 Voice Memo Integration" in body
        assert "**Source:** #33" in body
        assert "**Target:** `chapters/apartment-gardening.md`" in body

    def test_format_includes_text_analysis(self, rich_pr_body):
        """Formatted body includes text statistics table."""
        body = format_rich_pr_body(rich_pr_body)
        assert "### 📊 Text Analysis" in body
        assert "| Word Count | 1,250 |" in body
        assert "| Flesch Reading Ease | 72.5 |" in body

    def test_format_includes_structural_placement(self, rich_pr_body):
        """Formatted body includes structural analysis."""
        body = format_rich_pr_body(rich_pr_body)
        assert "### 🏗️ Structural Placement" in body
        assert "Opening chapter to set the mindset" in body

    def test_format_includes_voice_analysis(self, rich_pr_body):
        """Formatted body includes voice preservation."""
        body = format_rich_pr_body(rich_pr_body)
        assert "### 🎤 Voice Preservation" in body
        assert "**Voice Score:** high" in body
        assert "encouraging tone" in body

    def test_format_includes_discovery_context(self, rich_pr_body):
        """Formatted body includes discovery when present."""
        body = format_rich_pr_body(rich_pr_body)
        assert "### 💬 Discovery Context" in body
        assert "Focus on beginners" in body

    def test_format_includes_editorial_reasoning(self, rich_pr_body):
        """Formatted body includes collapsible reasoning."""
        body = format_rich_pr_body(rich_pr_body)
        assert "<details>" in body
        assert "Editorial Reasoning" in body
        assert "emotional connection" in body

    def test_format_includes_checklist(self, rich_pr_body):
        """Formatted body includes editorial checklist."""
        body = format_rich_pr_body(rich_pr_body)
        assert "### ✅ Editorial Checklist" in body
        assert "- [ ] Content flows naturally" in body

    def test_format_includes_usage_footer(self, rich_pr_body):
        """Formatted body includes usage summary in footer."""
        body = format_rich_pr_body(rich_pr_body)
        assert "5,000 tokens" in body
        assert "$0.0175" in body

    def test_format_without_discovery(self):
        """Formatted body handles missing discovery gracefully."""
        pr = RichPRBody(
            source_issue=1,
            target_file="test.md",
            content_analysis=ContentAnalysis(
                word_count=100,
                reading_time_minutes=0.5,
                flesch_reading_ease=70.0,
                flesch_kincaid_grade=7.0,
                avg_sentence_length=12.0,
                lexical_diversity=0.5,
                passive_voice_percent=5.0,
                corpus_comparison=[],
            ),
            structural=StructuralAnalysis(
                target_file="test.md",
                placement_rationale="Test",
                related_chapters=[],
                thematic_connections=[],
                flow_impact="None",
            ),
            voice=VoiceAnalysis(
                voice_score="medium",
                voice_markers=[],
                transformations=[],
            ),
            discovery=None,
            editorial_reasoning="",
            editorial_notes="None",
            content_summary="Test",
            llm_usage_summary="Test",
        )
        body = format_rich_pr_body(pr)
        # Should not include discovery section
        assert "### 💬 Discovery Context" not in body

    def test_format_corpus_comparison(self, rich_pr_body):
        """Formatted body includes corpus comparison when present."""
        body = format_rich_pr_body(rich_pr_body)
        assert "Impact on Book" in body
        assert "Slightly easier to read" in body

    def test_format_includes_decisions_made(self):
        """Formatted body includes decisions when present."""
        pr = RichPRBody(
            source_issue=42,
            target_file="test.md",
            content_analysis=ContentAnalysis(
                word_count=100,
                reading_time_minutes=0.5,
                flesch_reading_ease=70.0,
                flesch_kincaid_grade=7.0,
                avg_sentence_length=12.0,
                lexical_diversity=0.5,
                passive_voice_percent=5.0,
                corpus_comparison=[],
            ),
            structural=StructuralAnalysis(
                target_file="test.md",
                placement_rationale="Test",
                related_chapters=[],
                thematic_connections=[],
                flow_impact="None",
            ),
            voice=VoiceAnalysis(
                voice_score="medium",
                voice_markers=[],
                transformations=[],
            ),
            decisions_made=[
                DecisionRecord(decision="audience: Urban renters", context="From issue #42"),
                DecisionRecord(decision="tone: Encouraging"),
            ],
            outstanding_items=["What's the transformation arc?"],
            context_references=["Issue #42 — full conversation"],
            editorial_reasoning="",
            editorial_notes="Notes",
            content_summary="Test",
            llm_usage_summary="Test",
        )
        body = format_rich_pr_body(pr)
        assert "### 📌 Decisions Made" in body
        assert "audience: Urban renters" in body
        assert "From issue #42" in body

    def test_format_includes_outstanding_items(self):
        """Formatted body includes outstanding items when present."""
        pr = RichPRBody(
            source_issue=42,
            target_file="test.md",
            content_analysis=ContentAnalysis(
                word_count=100,
                reading_time_minutes=0.5,
                flesch_reading_ease=70.0,
                flesch_kincaid_grade=7.0,
                avg_sentence_length=12.0,
                lexical_diversity=0.5,
                passive_voice_percent=5.0,
                corpus_comparison=[],
            ),
            structural=StructuralAnalysis(
                target_file="test.md",
                placement_rationale="Test",
                related_chapters=[],
                thematic_connections=[],
                flow_impact="None",
            ),
            voice=VoiceAnalysis(
                voice_score="medium",
                voice_markers=[],
                transformations=[],
            ),
            outstanding_items=[
                "What's the transformation arc?",
                "Prerequisite: First draft written",
            ],
            editorial_reasoning="",
            editorial_notes="Notes",
            content_summary="Test",
            llm_usage_summary="Test",
        )
        body = format_rich_pr_body(pr)
        assert "### ⏳ Outstanding Items" in body
        assert "transformation arc" in body

    def test_format_includes_context_references(self):
        """Formatted body includes context references when present."""
        pr = RichPRBody(
            source_issue=42,
            target_file="test.md",
            content_analysis=ContentAnalysis(
                word_count=100,
                reading_time_minutes=0.5,
                flesch_reading_ease=70.0,
                flesch_kincaid_grade=7.0,
                avg_sentence_length=12.0,
                lexical_diversity=0.5,
                passive_voice_percent=5.0,
                corpus_comparison=[],
            ),
            structural=StructuralAnalysis(
                target_file="test.md",
                placement_rationale="Test",
                related_chapters=[],
                thematic_connections=[],
                flow_impact="None",
            ),
            voice=VoiceAnalysis(
                voice_score="medium",
                voice_markers=[],
                transformations=[],
            ),
            context_references=[
                "Issue #42 — full conversation history",
                ".ai-context/knowledge.jsonl — established facts",
            ],
            editorial_reasoning="",
            editorial_notes="Notes",
            content_summary="Test",
            llm_usage_summary="Test",
        )
        body = format_rich_pr_body(pr)
        assert "### 🔗 Context References" in body
        assert "Issue #42" in body
        assert "knowledge.jsonl" in body
