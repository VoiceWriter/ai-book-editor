"""Tests for text statistics analysis."""

import pytest

# Import the module
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))

from analyze_text_stats import (
    TextStats,
    ChapterStats,
    AggregateStats,
    ImpactAnalysis,
    analyze_text,
    count_paragraphs,
    calculate_lexical_diversity,
    extract_text_from_markdown,
    interpret_stats,
    aggregate_stats,
    compute_impact,
    format_stats_comment,
    format_stats_for_ai,
    format_impact_comment,
)


class TestExtractTextFromMarkdown:
    """Test markdown text extraction."""

    def test_removes_code_blocks(self):
        md = "Hello\n```python\ncode here\n```\nWorld"
        result = extract_text_from_markdown(md)
        assert "code here" not in result
        assert "Hello" in result
        assert "World" in result

    def test_removes_inline_code(self):
        md = "Use `print()` to output"
        result = extract_text_from_markdown(md)
        assert "`" not in result
        assert "Use" in result
        assert "to output" in result

    def test_removes_links_keeps_text(self):
        md = "Check [this link](http://example.com) out"
        result = extract_text_from_markdown(md)
        assert "http" not in result
        assert "this link" in result

    def test_removes_images(self):
        md = "See ![alt text](image.png) here"
        result = extract_text_from_markdown(md)
        assert "alt text" not in result
        assert "See" in result
        assert "here" in result

    def test_removes_header_markers(self):
        md = "# Title\n## Subtitle\nContent"
        result = extract_text_from_markdown(md)
        assert "#" not in result
        assert "Title" in result
        assert "Content" in result

    def test_removes_emphasis(self):
        md = "This is **bold** and *italic* text"
        result = extract_text_from_markdown(md)
        assert "*" not in result
        assert "bold" in result
        assert "italic" in result

    def test_removes_blockquotes(self):
        md = "> This is a quote\nNormal text"
        result = extract_text_from_markdown(md)
        assert ">" not in result
        assert "This is a quote" in result

    def test_removes_list_markers(self):
        md = "- Item one\n* Item two\n1. Item three"
        result = extract_text_from_markdown(md)
        assert "Item one" in result
        assert "Item two" in result
        assert "Item three" in result


class TestCountParagraphs:
    """Test paragraph counting."""

    def test_single_paragraph(self):
        text = "This is one paragraph with multiple sentences. Another sentence here."
        assert count_paragraphs(text) == 1

    def test_multiple_paragraphs(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        assert count_paragraphs(text) == 3

    def test_empty_text(self):
        assert count_paragraphs("") == 0
        assert count_paragraphs("   \n\n   ") == 0


class TestLexicalDiversity:
    """Test lexical diversity calculation."""

    def test_all_unique_words(self):
        words = ["the", "quick", "brown", "fox"]
        result = calculate_lexical_diversity(words)
        assert result == 1.0

    def test_all_same_word(self):
        words = ["the", "the", "the", "the"]
        result = calculate_lexical_diversity(words)
        assert result == 0.25

    def test_mixed_case_treated_same(self):
        words = ["The", "the", "THE"]
        result = calculate_lexical_diversity(words)
        assert result == pytest.approx(0.333, rel=0.01)

    def test_empty_list(self):
        assert calculate_lexical_diversity([]) == 0.0


class TestAnalyzeText:
    """Test the main analyze_text function."""

    def test_basic_text_analysis(self):
        text = """
        The quick brown fox jumps over the lazy dog.
        This is a simple sentence. Here is another one.
        Short sentences are easy to read.
        """
        stats = analyze_text(text, "test.md")

        assert stats.file_path == "test.md"
        assert stats.word_count > 0
        assert stats.sentence_count >= 3
        assert stats.flesch_reading_ease > 0
        assert 0 <= stats.lexical_diversity <= 1

    def test_empty_text_returns_zeros(self):
        stats = analyze_text("", "empty.md")

        assert stats.word_count == 0
        assert stats.sentence_count == 0
        assert stats.flesch_reading_ease == 0
        assert stats.lexical_diversity == 0

    def test_markdown_is_cleaned(self):
        md = "# Title\n\nThis is **bold** text with a [link](url)."
        stats = analyze_text(md, "test.md")

        # Should analyze the plain text, not markdown
        assert stats.word_count > 0


class TestTextStatsModel:
    """Test TextStats Pydantic model."""

    def test_valid_stats_creation(self):
        stats = TextStats(
            file_path="test.md",
            word_count=100,
            sentence_count=5,
            paragraph_count=2,
            flesch_reading_ease=65.0,
            flesch_kincaid_grade=8.0,
            reading_time_minutes=0.5,
            avg_sentence_length=20.0,
            avg_word_length=1.5,
            lexical_diversity=0.6,
            passive_voice_percent=10.0,
            adverb_percent=3.0,
        )
        assert stats.word_count == 100
        assert stats.flesch_reading_ease == 65.0


class TestInterpretStats:
    """Test stats interpretation."""

    def test_easy_reading_interpretation(self):
        stats = TextStats(
            file_path="test.md",
            word_count=100,
            sentence_count=5,
            paragraph_count=2,
            flesch_reading_ease=85.0,
            flesch_kincaid_grade=5.0,
            reading_time_minutes=0.5,
            avg_sentence_length=15.0,
            avg_word_length=1.3,
            lexical_diversity=0.6,
            passive_voice_percent=5.0,
            adverb_percent=2.0,
        )
        chapter = interpret_stats(stats)

        assert "easy" in chapter.interpretation.lower()
        assert len(chapter.suggestions) == 0  # No issues

    def test_difficult_reading_gets_suggestions(self):
        stats = TextStats(
            file_path="test.md",
            word_count=100,
            sentence_count=3,
            paragraph_count=1,
            flesch_reading_ease=15.0,
            flesch_kincaid_grade=16.0,
            reading_time_minutes=0.5,
            avg_sentence_length=33.0,
            avg_word_length=2.5,
            lexical_diversity=0.3,
            passive_voice_percent=30.0,
            adverb_percent=8.0,
        )
        chapter = interpret_stats(stats)

        assert "difficult" in chapter.interpretation.lower()
        assert len(chapter.suggestions) > 0
        # Should suggest shorter sentences
        assert any("sentence" in s.lower() for s in chapter.suggestions)
        # Should flag passive voice
        assert any("passive" in s.lower() for s in chapter.suggestions)

    def test_high_lexical_diversity_noted(self):
        stats = TextStats(
            file_path="test.md",
            word_count=100,
            sentence_count=5,
            paragraph_count=2,
            flesch_reading_ease=60.0,
            flesch_kincaid_grade=8.0,
            reading_time_minutes=0.5,
            avg_sentence_length=20.0,
            avg_word_length=1.5,
            lexical_diversity=0.75,
            passive_voice_percent=5.0,
            adverb_percent=2.0,
        )
        chapter = interpret_stats(stats)

        assert "vocabulary" in chapter.interpretation.lower()


class TestAggregateStats:
    """Test aggregate statistics calculation."""

    def test_empty_list_returns_zeros(self):
        result = aggregate_stats([])
        assert result.file_count == 0
        assert result.total_word_count == 0

    def test_single_file_matches_original(self):
        stats = TextStats(
            file_path="test.md",
            word_count=100,
            sentence_count=5,
            paragraph_count=2,
            flesch_reading_ease=65.0,
            flesch_kincaid_grade=8.0,
            reading_time_minutes=0.5,
            avg_sentence_length=20.0,
            avg_word_length=1.5,
            lexical_diversity=0.6,
            passive_voice_percent=10.0,
            adverb_percent=3.0,
        )
        result = aggregate_stats([stats])

        assert result.file_count == 1
        assert result.total_word_count == 100
        assert result.avg_flesch_reading_ease == 65.0

    def test_weighted_average_by_word_count(self):
        # Short file with high readability
        short = TextStats(
            file_path="short.md",
            word_count=100,
            sentence_count=5,
            paragraph_count=2,
            flesch_reading_ease=80.0,
            flesch_kincaid_grade=6.0,
            reading_time_minutes=0.5,
            avg_sentence_length=20.0,
            avg_word_length=1.3,
            lexical_diversity=0.6,
            passive_voice_percent=5.0,
            adverb_percent=2.0,
        )
        # Long file with lower readability
        long = TextStats(
            file_path="long.md",
            word_count=900,
            sentence_count=45,
            paragraph_count=10,
            flesch_reading_ease=50.0,
            flesch_kincaid_grade=10.0,
            reading_time_minutes=4.5,
            avg_sentence_length=20.0,
            avg_word_length=1.8,
            lexical_diversity=0.5,
            passive_voice_percent=15.0,
            adverb_percent=4.0,
        )
        result = aggregate_stats([short, long])

        # Long file should dominate (900 vs 100 words)
        # Weighted avg: (80*100 + 50*900) / 1000 = 53
        assert result.avg_flesch_reading_ease == 53.0
        assert result.total_word_count == 1000


class TestComputeImpact:
    """Test impact analysis computation."""

    def test_no_corpus_shows_contribution(self):
        new_stats = [TextStats(
            file_path="new.md",
            word_count=500,
            sentence_count=25,
            paragraph_count=5,
            flesch_reading_ease=65.0,
            flesch_kincaid_grade=8.0,
            reading_time_minutes=2.5,
            avg_sentence_length=20.0,
            avg_word_length=1.5,
            lexical_diversity=0.55,
            passive_voice_percent=10.0,
            adverb_percent=3.0,
        )]

        impact = compute_impact(new_stats, [])

        assert impact.new_content.total_word_count == 500
        assert impact.existing_corpus.total_word_count == 0
        assert impact.combined.total_word_count == 500

    def test_detects_readability_impact(self):
        # New content is much harder to read
        new_stats = [TextStats(
            file_path="new.md",
            word_count=500,
            sentence_count=15,
            paragraph_count=3,
            flesch_reading_ease=30.0,  # Very hard
            flesch_kincaid_grade=14.0,
            reading_time_minutes=2.5,
            avg_sentence_length=33.0,
            avg_word_length=2.0,
            lexical_diversity=0.5,
            passive_voice_percent=25.0,
            adverb_percent=5.0,
        )]
        corpus_stats = [TextStats(
            file_path="existing.md",
            word_count=500,
            sentence_count=25,
            paragraph_count=5,
            flesch_reading_ease=70.0,  # Easy
            flesch_kincaid_grade=7.0,
            reading_time_minutes=2.5,
            avg_sentence_length=20.0,
            avg_word_length=1.4,
            lexical_diversity=0.6,
            passive_voice_percent=8.0,
            adverb_percent=2.0,
        )]

        impact = compute_impact(new_stats, corpus_stats)

        # Should detect the readability drop
        assert any("harder" in s.lower() for s in impact.impact_summary)

    def test_no_negative_impact_when_similar(self):
        """When new content matches corpus style, no warnings are raised."""
        new_stats = [TextStats(
            file_path="new.md",
            word_count=500,
            sentence_count=25,
            paragraph_count=5,
            flesch_reading_ease=65.0,
            flesch_kincaid_grade=8.0,
            reading_time_minutes=2.5,
            avg_sentence_length=20.0,
            avg_word_length=1.5,
            lexical_diversity=0.55,
            passive_voice_percent=10.0,
            adverb_percent=3.0,
        )]
        corpus_stats = [TextStats(
            file_path="existing.md",
            word_count=500,
            sentence_count=25,
            paragraph_count=5,
            flesch_reading_ease=66.0,
            flesch_kincaid_grade=8.0,
            reading_time_minutes=2.5,
            avg_sentence_length=20.0,
            avg_word_length=1.5,
            lexical_diversity=0.56,
            passive_voice_percent=9.0,
            adverb_percent=3.0,
        )]

        impact = compute_impact(new_stats, corpus_stats)

        # Should only show volume, no warnings about readability/etc
        assert not any("harder" in s.lower() for s in impact.impact_summary)
        assert not any("passive" in s.lower() for s in impact.impact_summary)
        # Should show volume contribution
        assert any("volume" in s.lower() for s in impact.impact_summary)


class TestFormatImpactComment:
    """Test impact comment formatting."""

    def test_includes_comparison_table(self):
        new_stats = TextStats(
            file_path="new.md",
            word_count=500,
            sentence_count=25,
            paragraph_count=5,
            flesch_reading_ease=65.0,
            flesch_kincaid_grade=8.0,
            reading_time_minutes=2.5,
            avg_sentence_length=20.0,
            avg_word_length=1.5,
            lexical_diversity=0.55,
            passive_voice_percent=10.0,
            adverb_percent=3.0,
        )
        chapter = interpret_stats(new_stats)
        impact = compute_impact([new_stats], [])

        comment = format_impact_comment(impact, [chapter])

        assert "New Content" in comment
        assert "Existing Corpus" in comment
        assert "After Adding" in comment
        assert "Impact Summary" in comment


class TestFormatOutput:
    """Test output formatting functions."""

    def test_format_comment_includes_table(self):
        stats = TextStats(
            file_path="chapters/01.md",
            word_count=500,
            sentence_count=25,
            paragraph_count=5,
            flesch_reading_ease=65.0,
            flesch_kincaid_grade=8.0,
            reading_time_minutes=2.5,
            avg_sentence_length=20.0,
            avg_word_length=1.5,
            lexical_diversity=0.55,
            passive_voice_percent=10.0,
            adverb_percent=3.0,
        )
        chapter = interpret_stats(stats)
        comment = format_stats_comment([chapter])

        assert "## 📊 Text Statistics" in comment
        assert "chapters/01.md" in comment
        assert "| Words | 500 |" in comment
        assert "| Flesch Reading Ease | 65.0 |" in comment

    def test_format_for_ai_is_concise(self):
        stats = TextStats(
            file_path="chapters/01.md",
            word_count=500,
            sentence_count=25,
            paragraph_count=5,
            flesch_reading_ease=65.0,
            flesch_kincaid_grade=8.0,
            reading_time_minutes=2.5,
            avg_sentence_length=20.0,
            avg_word_length=1.5,
            lexical_diversity=0.55,
            passive_voice_percent=10.0,
            adverb_percent=3.0,
        )
        chapter = interpret_stats(stats)
        ai_context = format_stats_for_ai([chapter])

        assert "Pre-computed Text Statistics" in ai_context
        assert "Word count: 500" in ai_context
        assert "Flesch Reading Ease: 65.0" in ai_context
        # Should explain the metric
        assert "higher=easier" in ai_context
