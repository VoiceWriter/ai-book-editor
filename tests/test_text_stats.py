"""Tests for text statistics analysis."""

import pytest

# Import the module
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))

from analyze_text_stats import (
    TextStats,
    ChapterStats,
    analyze_text,
    count_paragraphs,
    calculate_lexical_diversity,
    extract_text_from_markdown,
    interpret_stats,
    format_stats_comment,
    format_stats_for_ai,
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
