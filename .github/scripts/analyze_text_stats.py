#!/usr/bin/env python3
"""
Analyze text files and compute readability/writing statistics.

Outputs stats that can be:
1. Posted as a PR comment
2. Fed to the AI editor as context
3. Tracked over time

Usage:
    python analyze_text_stats.py                    # Analyze all chapters
    python analyze_text_stats.py --file path.md    # Analyze specific file
    python analyze_text_stats.py --changed-only    # Only files changed in PR
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# Defer heavy imports until needed
textstat = None


def get_textstat():
    """Lazy load textstat."""
    global textstat
    if textstat is None:
        import textstat as ts
        textstat = ts
    return textstat


class TextStats(BaseModel):
    """Statistics for a single text file."""

    model_config = ConfigDict(strict=True)

    file_path: str = Field(description="Path to the analyzed file")
    word_count: int = Field(description="Total word count")
    sentence_count: int = Field(description="Number of sentences")
    paragraph_count: int = Field(description="Number of paragraphs")

    # Readability
    flesch_reading_ease: float = Field(description="Flesch Reading Ease (0-100, higher=easier)")
    flesch_kincaid_grade: float = Field(description="Flesch-Kincaid Grade Level")
    reading_time_minutes: float = Field(description="Estimated reading time in minutes")

    # Complexity
    avg_sentence_length: float = Field(description="Average words per sentence")
    avg_word_length: float = Field(description="Average syllables per word")
    lexical_diversity: float = Field(description="Unique words / total words (0-1)")

    # Style
    passive_voice_percent: float = Field(description="Percentage of sentences with passive voice")
    adverb_percent: float = Field(description="Percentage of words that are adverbs")


class ChapterStats(BaseModel):
    """Stats for a chapter with context."""

    model_config = ConfigDict(strict=True)

    stats: TextStats
    interpretation: str = Field(description="Human-readable interpretation")
    suggestions: list[str] = Field(default_factory=list, description="Potential improvements")


def extract_text_from_markdown(content: str) -> str:
    """Extract plain text from markdown, removing code blocks and formatting."""
    # Remove code blocks
    content = re.sub(r"```[\s\S]*?```", "", content)
    content = re.sub(r"`[^`]+`", "", content)

    # Remove HTML tags
    content = re.sub(r"<[^>]+>", "", content)

    # Remove images (must be before links since images are ![...](...))
    content = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", content)

    # Remove markdown links but keep text
    content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)

    # Remove headers markers but keep text
    content = re.sub(r"^#+\s*", "", content, flags=re.MULTILINE)

    # Remove emphasis markers
    content = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
    content = re.sub(r"\*([^*]+)\*", r"\1", content)
    content = re.sub(r"__([^_]+)__", r"\1", content)
    content = re.sub(r"_([^_]+)_", r"\1", content)

    # Remove blockquotes
    content = re.sub(r"^>\s*", "", content, flags=re.MULTILINE)

    # Remove horizontal rules
    content = re.sub(r"^[-*_]{3,}\s*$", "", content, flags=re.MULTILINE)

    # Remove list markers
    content = re.sub(r"^\s*[-*+]\s+", "", content, flags=re.MULTILINE)
    content = re.sub(r"^\s*\d+\.\s+", "", content, flags=re.MULTILINE)

    return content.strip()


def count_paragraphs(text: str) -> int:
    """Count paragraphs (blocks of text separated by blank lines)."""
    paragraphs = re.split(r"\n\s*\n", text)
    return len([p for p in paragraphs if p.strip()])


def calculate_lexical_diversity(words: list[str]) -> float:
    """Calculate type-token ratio (unique words / total words)."""
    if not words:
        return 0.0
    # Normalize to lowercase for comparison
    lower_words = [w.lower() for w in words]
    return len(set(lower_words)) / len(lower_words)


def detect_passive_voice(text: str) -> float:
    """Detect percentage of sentences with passive voice using heuristics.

    Looks for patterns like "was/were/been/being + past participle"
    """
    # Simple sentence splitting
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return 0.0

    # Passive voice patterns: be-verb + optional adverb + past participle (-ed, -en, irregular)
    passive_patterns = [
        r'\b(is|are|was|were|been|being|be)\b\s+\w*\s*(ed|en)\b',
        r'\b(is|are|was|were|been|being)\b\s+(\w+ly\s+)?(made|done|given|taken|written|shown|known|seen|found|told|said|called|used|asked|left|put|set|kept|held|brought|thought|felt|become|begun|broken|chosen|driven|eaten|fallen|forgotten|frozen|gotten|grown|hidden|known|lain|ridden|risen|shaken|spoken|stolen|sworn|torn|woken|worn|written)\b',
    ]

    passive_count = 0
    for sentence in sentences:
        sentence_lower = sentence.lower()
        for pattern in passive_patterns:
            if re.search(pattern, sentence_lower):
                passive_count += 1
                break

    return (passive_count / len(sentences)) * 100


def count_adverbs(text: str) -> float:
    """Count percentage of words that are adverbs (words ending in -ly).

    Simple heuristic - not all -ly words are adverbs, but good enough.
    """
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

    if not words:
        return 0.0

    # Words ending in -ly (excluding common non-adverbs)
    non_adverbs = {'only', 'family', 'early', 'likely', 'lovely', 'lonely', 'ugly',
                   'holy', 'daily', 'weekly', 'monthly', 'yearly', 'friendly',
                   'elderly', 'lively', 'costly', 'deadly', 'silly', 'reply',
                   'apply', 'supply', 'fly', 'july', 'italy', 'ally', 'bully', 'belly'}

    adverb_count = sum(1 for w in words if w.endswith('ly') and w not in non_adverbs and len(w) > 3)

    return (adverb_count / len(words)) * 100


def analyze_text(content: str, file_path: str = "") -> TextStats:
    """Analyze text and return statistics."""
    ts = get_textstat()

    # Extract plain text from markdown
    text = extract_text_from_markdown(content)

    if not text.strip():
        return TextStats(
            file_path=file_path,
            word_count=0,
            sentence_count=0,
            paragraph_count=0,
            flesch_reading_ease=0,
            flesch_kincaid_grade=0,
            reading_time_minutes=0,
            avg_sentence_length=0,
            avg_word_length=0,
            lexical_diversity=0,
            passive_voice_percent=0,
            adverb_percent=0,
        )

    # Basic counts
    word_count = ts.lexicon_count(text, removepunct=True)
    sentence_count = ts.sentence_count(text)
    paragraph_count = count_paragraphs(text)

    # Readability scores
    flesch_reading_ease = ts.flesch_reading_ease(text)
    flesch_kincaid_grade = ts.flesch_kincaid_grade(text)

    # Reading time (average 200 words per minute)
    reading_time_minutes = round(word_count / 200, 1)

    # Complexity metrics
    avg_sentence_length = round(word_count / max(sentence_count, 1), 1)
    avg_word_length = ts.avg_syllables_per_word(text)

    # Lexical diversity
    words = text.split()
    lexical_diversity = round(calculate_lexical_diversity(words), 3)

    # Style metrics (these use spaCy, so they're slower)
    passive_voice_percent = round(detect_passive_voice(text), 1)
    adverb_percent = round(count_adverbs(text), 1)

    return TextStats(
        file_path=file_path,
        word_count=word_count,
        sentence_count=sentence_count,
        paragraph_count=paragraph_count,
        flesch_reading_ease=round(flesch_reading_ease, 1),
        flesch_kincaid_grade=round(flesch_kincaid_grade, 1),
        reading_time_minutes=reading_time_minutes,
        avg_sentence_length=avg_sentence_length,
        avg_word_length=round(avg_word_length, 2),
        lexical_diversity=lexical_diversity,
        passive_voice_percent=passive_voice_percent,
        adverb_percent=adverb_percent,
    )


def interpret_stats(stats: TextStats) -> ChapterStats:
    """Generate human-readable interpretation and suggestions."""
    suggestions = []
    interpretations = []

    # Readability interpretation
    fre = stats.flesch_reading_ease
    if fre >= 80:
        interpretations.append("Very easy to read (conversational)")
    elif fre >= 60:
        interpretations.append("Easy to read (plain English)")
    elif fre >= 40:
        interpretations.append("Moderate difficulty (some complexity)")
    elif fre >= 20:
        interpretations.append("Difficult to read (academic level)")
    else:
        interpretations.append("Very difficult to read")
        suggestions.append("Consider simplifying sentence structure")

    # Grade level
    grade = stats.flesch_kincaid_grade
    interpretations.append(f"Grade level: {grade:.0f} (readable by ~{grade:.0f}th graders)")

    # Sentence length
    if stats.avg_sentence_length > 25:
        suggestions.append(f"Avg sentence length is {stats.avg_sentence_length} words - consider shorter sentences")
    elif stats.avg_sentence_length < 10:
        suggestions.append("Sentences are quite short - consider varying length for rhythm")

    # Passive voice
    if stats.passive_voice_percent > 20:
        suggestions.append(f"Passive voice at {stats.passive_voice_percent}% - consider more active constructions")

    # Lexical diversity
    if stats.lexical_diversity < 0.4:
        suggestions.append(f"Lexical diversity is {stats.lexical_diversity:.0%} - vocabulary may be repetitive")
    elif stats.lexical_diversity > 0.7:
        interpretations.append("Rich vocabulary variety")

    # Adverbs
    if stats.adverb_percent > 5:
        suggestions.append(f"Adverb usage at {stats.adverb_percent}% - consider stronger verbs instead")

    interpretation = ". ".join(interpretations)

    return ChapterStats(
        stats=stats,
        interpretation=interpretation,
        suggestions=suggestions,
    )


def format_stats_comment(chapters: list[ChapterStats]) -> str:
    """Format stats as a GitHub comment."""
    lines = ["## 📊 Text Statistics\n"]

    for chapter in chapters:
        s = chapter.stats
        lines.append(f"### `{s.file_path}`\n")

        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Words | {s.word_count:,} |")
        lines.append(f"| Reading time | {s.reading_time_minutes} min |")
        lines.append(f"| Flesch Reading Ease | {s.flesch_reading_ease} |")
        lines.append(f"| Grade Level | {s.flesch_kincaid_grade} |")
        lines.append(f"| Avg Sentence Length | {s.avg_sentence_length} words |")
        lines.append(f"| Lexical Diversity | {s.lexical_diversity:.0%} |")
        lines.append(f"| Passive Voice | {s.passive_voice_percent}% |")
        lines.append(f"| Adverbs | {s.adverb_percent}% |")
        lines.append("")

        lines.append(f"**Interpretation:** {chapter.interpretation}\n")

        if chapter.suggestions:
            lines.append("**Suggestions:**")
            for suggestion in chapter.suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

    lines.append("---")
    lines.append("*Stats generated by AI Book Editor*")

    return "\n".join(lines)


def format_stats_for_ai(chapters: list[ChapterStats]) -> str:
    """Format stats as context for AI editor."""
    lines = ["## Pre-computed Text Statistics\n"]
    lines.append("Use these objective metrics to inform your feedback:\n")

    for chapter in chapters:
        s = chapter.stats
        lines.append(f"### {s.file_path}")
        lines.append(f"- Word count: {s.word_count:,}")
        lines.append(f"- Flesch Reading Ease: {s.flesch_reading_ease} (0-100, higher=easier)")
        lines.append(f"- Grade level: {s.flesch_kincaid_grade}")
        lines.append(f"- Avg sentence length: {s.avg_sentence_length} words")
        lines.append(f"- Lexical diversity: {s.lexical_diversity:.0%}")
        lines.append(f"- Passive voice: {s.passive_voice_percent}%")
        lines.append(f"- Adverbs: {s.adverb_percent}%")
        lines.append("")

    return "\n".join(lines)


def get_changed_files() -> list[str]:
    """Get list of changed markdown files in the PR."""
    import subprocess

    # Get the base branch
    base = os.environ.get("GITHUB_BASE_REF", "main")

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"origin/{base}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.strip().split("\n")
        # Filter for markdown files in chapters/
        return [f for f in files if f.startswith("chapters/") and f.endswith(".md")]
    except subprocess.CalledProcessError:
        return []


def main():
    parser = argparse.ArgumentParser(description="Analyze text statistics")
    parser.add_argument("--file", help="Specific file to analyze")
    parser.add_argument("--changed-only", action="store_true", help="Only analyze changed files")
    parser.add_argument("--output", choices=["comment", "json", "ai"], default="comment",
                        help="Output format")
    parser.add_argument("--chapters-dir", default="chapters", help="Directory containing chapters")
    args = parser.parse_args()

    # Determine which files to analyze
    if args.file:
        files = [args.file]
    elif args.changed_only:
        files = get_changed_files()
        if not files:
            print("No chapter files changed in this PR")
            return
    else:
        # Analyze all chapters
        chapters_dir = Path(args.chapters_dir)
        if chapters_dir.exists():
            files = sorted([str(f) for f in chapters_dir.glob("**/*.md")])
        else:
            files = []

    if not files:
        print("No files to analyze")
        return

    print(f"Analyzing {len(files)} file(s)...")

    chapters = []
    for file_path in files:
        print(f"  Processing: {file_path}")
        try:
            with open(file_path) as f:
                content = f.read()
            stats = analyze_text(content, file_path)
            chapter = interpret_stats(stats)
            chapters.append(chapter)
        except Exception as e:
            print(f"  Error processing {file_path}: {e}")

    if not chapters:
        print("No chapters analyzed successfully")
        return

    # Output results
    if args.output == "json":
        output = [c.model_dump() for c in chapters]
        print(json.dumps(output, indent=2))
    elif args.output == "ai":
        output = format_stats_for_ai(chapters)
        print(output)
        # Also save for workflow
        Path("output").mkdir(exist_ok=True)
        Path("output/text-stats-ai.md").write_text(output)
    else:
        output = format_stats_comment(chapters)
        print(output)
        # Save for workflow to post as comment
        Path("output").mkdir(exist_ok=True)
        Path("output/text-stats-comment.md").write_text(output)

    print(f"\nAnalyzed {len(chapters)} file(s)")


if __name__ == "__main__":
    main()
