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


class AggregateStats(BaseModel):
    """Aggregated statistics across multiple files."""

    model_config = ConfigDict(strict=True)

    file_count: int = Field(description="Number of files analyzed")
    total_word_count: int = Field(description="Total words across all files")
    avg_flesch_reading_ease: float = Field(description="Average Flesch Reading Ease")
    avg_flesch_kincaid_grade: float = Field(description="Average grade level")
    avg_sentence_length: float = Field(description="Average sentence length")
    avg_lexical_diversity: float = Field(description="Average lexical diversity")
    avg_passive_voice_percent: float = Field(description="Average passive voice %")
    avg_adverb_percent: float = Field(description="Average adverb %")


class ImpactAnalysis(BaseModel):
    """Analysis of how new content impacts the corpus."""

    model_config = ConfigDict(strict=True)

    new_content: AggregateStats = Field(description="Stats for new/changed content")
    existing_corpus: AggregateStats = Field(description="Stats for existing content")
    combined: AggregateStats = Field(description="Stats after adding new content")
    impact_summary: list[str] = Field(description="Human-readable impact statements")


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


def aggregate_stats(stats_list: list[TextStats]) -> AggregateStats:
    """Compute aggregate statistics across multiple files."""
    if not stats_list:
        return AggregateStats(
            file_count=0,
            total_word_count=0,
            avg_flesch_reading_ease=0,
            avg_flesch_kincaid_grade=0,
            avg_sentence_length=0,
            avg_lexical_diversity=0,
            avg_passive_voice_percent=0,
            avg_adverb_percent=0,
        )

    n = len(stats_list)
    total_words = sum(s.word_count for s in stats_list)

    # Weight averages by word count for more accurate representation
    if total_words > 0:
        weighted_fre = sum(s.flesch_reading_ease * s.word_count for s in stats_list) / total_words
        weighted_fkg = sum(s.flesch_kincaid_grade * s.word_count for s in stats_list) / total_words
        weighted_sent = sum(s.avg_sentence_length * s.word_count for s in stats_list) / total_words
        weighted_lex = sum(s.lexical_diversity * s.word_count for s in stats_list) / total_words
        weighted_passive = sum(s.passive_voice_percent * s.word_count for s in stats_list) / total_words
        weighted_adverb = sum(s.adverb_percent * s.word_count for s in stats_list) / total_words
    else:
        weighted_fre = weighted_fkg = weighted_sent = weighted_lex = weighted_passive = weighted_adverb = 0

    return AggregateStats(
        file_count=n,
        total_word_count=total_words,
        avg_flesch_reading_ease=round(weighted_fre, 1),
        avg_flesch_kincaid_grade=round(weighted_fkg, 1),
        avg_sentence_length=round(weighted_sent, 1),
        avg_lexical_diversity=round(weighted_lex, 3),
        avg_passive_voice_percent=round(weighted_passive, 1),
        avg_adverb_percent=round(weighted_adverb, 1),
    )


def compute_impact(
    new_stats: list[TextStats],
    corpus_stats: list[TextStats],
) -> ImpactAnalysis:
    """Compute how new content impacts the overall corpus."""
    new_agg = aggregate_stats(new_stats)
    corpus_agg = aggregate_stats(corpus_stats)
    combined_agg = aggregate_stats(new_stats + corpus_stats)

    impact_summary = []

    # Compare key metrics and generate impact statements
    if corpus_agg.file_count > 0:
        # Readability impact
        fre_delta = combined_agg.avg_flesch_reading_ease - corpus_agg.avg_flesch_reading_ease
        if abs(fre_delta) > 2:
            direction = "easier" if fre_delta > 0 else "harder"
            impact_summary.append(
                f"Readability: New content makes the book {direction} to read "
                f"({corpus_agg.avg_flesch_reading_ease} → {combined_agg.avg_flesch_reading_ease})"
            )

        # Grade level impact
        grade_delta = combined_agg.avg_flesch_kincaid_grade - corpus_agg.avg_flesch_kincaid_grade
        if abs(grade_delta) > 0.5:
            direction = "higher" if grade_delta > 0 else "lower"
            impact_summary.append(
                f"Grade level: Moves {direction} "
                f"({corpus_agg.avg_flesch_kincaid_grade} → {combined_agg.avg_flesch_kincaid_grade})"
            )

        # Passive voice impact
        passive_delta = combined_agg.avg_passive_voice_percent - corpus_agg.avg_passive_voice_percent
        if abs(passive_delta) > 2:
            direction = "more" if passive_delta > 0 else "less"
            impact_summary.append(
                f"Passive voice: {direction} passive overall "
                f"({corpus_agg.avg_passive_voice_percent}% → {combined_agg.avg_passive_voice_percent}%)"
            )

        # Sentence length impact
        sent_delta = combined_agg.avg_sentence_length - corpus_agg.avg_sentence_length
        if abs(sent_delta) > 2:
            direction = "longer" if sent_delta > 0 else "shorter"
            impact_summary.append(
                f"Sentences: Average becomes {direction} "
                f"({corpus_agg.avg_sentence_length} → {combined_agg.avg_sentence_length} words)"
            )

        # Word count contribution
        if combined_agg.total_word_count > 0:
            contribution = (new_agg.total_word_count / combined_agg.total_word_count) * 100
            impact_summary.append(
                f"Volume: Adds {new_agg.total_word_count:,} words "
                f"({contribution:.1f}% of total)"
            )

    if not impact_summary:
        impact_summary.append("New content aligns well with existing corpus style")

    return ImpactAnalysis(
        new_content=new_agg,
        existing_corpus=corpus_agg,
        combined=combined_agg,
        impact_summary=impact_summary,
    )


def format_impact_comment(impact: ImpactAnalysis, new_chapters: list[ChapterStats]) -> str:
    """Format impact analysis as a GitHub comment."""
    lines = ["## 📊 Text Statistics & Impact Analysis\n"]

    # New content details
    lines.append("### New/Changed Content\n")
    for chapter in new_chapters:
        s = chapter.stats
        lines.append(f"**`{s.file_path}`** — {s.word_count:,} words, "
                     f"Flesch {s.flesch_reading_ease}, Grade {s.flesch_kincaid_grade}")

    lines.append("")

    # Comparison table
    lines.append("### Comparison\n")
    lines.append("| Metric | New Content | Existing Corpus | After Adding |")
    lines.append("|--------|-------------|-----------------|--------------|")

    n = impact.new_content
    c = impact.existing_corpus
    a = impact.combined

    def delta_arrow(new_val: float, old_val: float) -> str:
        if old_val == 0:
            return ""
        diff = new_val - old_val
        if abs(diff) < 0.1:
            return ""
        return " ↑" if diff > 0 else " ↓"

    lines.append(f"| Words | {n.total_word_count:,} | {c.total_word_count:,} | "
                 f"**{a.total_word_count:,}** |")
    lines.append(f"| Flesch Reading Ease | {n.avg_flesch_reading_ease} | "
                 f"{c.avg_flesch_reading_ease} | **{a.avg_flesch_reading_ease}**"
                 f"{delta_arrow(a.avg_flesch_reading_ease, c.avg_flesch_reading_ease)} |")
    lines.append(f"| Grade Level | {n.avg_flesch_kincaid_grade} | "
                 f"{c.avg_flesch_kincaid_grade} | **{a.avg_flesch_kincaid_grade}**"
                 f"{delta_arrow(a.avg_flesch_kincaid_grade, c.avg_flesch_kincaid_grade)} |")
    lines.append(f"| Avg Sentence Length | {n.avg_sentence_length} | "
                 f"{c.avg_sentence_length} | **{a.avg_sentence_length}**"
                 f"{delta_arrow(a.avg_sentence_length, c.avg_sentence_length)} |")
    lines.append(f"| Lexical Diversity | {n.avg_lexical_diversity:.0%} | "
                 f"{c.avg_lexical_diversity:.0%} | **{a.avg_lexical_diversity:.0%}** |")
    lines.append(f"| Passive Voice | {n.avg_passive_voice_percent}% | "
                 f"{c.avg_passive_voice_percent}% | **{a.avg_passive_voice_percent}%**"
                 f"{delta_arrow(a.avg_passive_voice_percent, c.avg_passive_voice_percent)} |")
    lines.append(f"| Adverbs | {n.avg_adverb_percent}% | "
                 f"{c.avg_adverb_percent}% | **{a.avg_adverb_percent}%** |")

    lines.append("")

    # Impact summary
    lines.append("### Impact Summary\n")
    for statement in impact.impact_summary:
        lines.append(f"- {statement}")

    lines.append("")

    # Per-chapter suggestions
    all_suggestions = []
    for chapter in new_chapters:
        for suggestion in chapter.suggestions:
            all_suggestions.append(f"**{chapter.stats.file_path}**: {suggestion}")

    if all_suggestions:
        lines.append("### Suggestions\n")
        for s in all_suggestions:
            lines.append(f"- {s}")
        lines.append("")

    lines.append("---")
    lines.append("*Stats generated by AI Book Editor*")

    return "\n".join(lines)


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


def analyze_files(files: list[str]) -> tuple[list[ChapterStats], list[TextStats]]:
    """Analyze a list of files and return chapters and raw stats."""
    chapters = []
    stats_list = []

    for file_path in files:
        try:
            with open(file_path) as f:
                content = f.read()
            stats = analyze_text(content, file_path)
            chapter = interpret_stats(stats)
            chapters.append(chapter)
            stats_list.append(stats)
        except Exception as e:
            print(f"  Error processing {file_path}: {e}")

    return chapters, stats_list


def main():
    parser = argparse.ArgumentParser(description="Analyze text statistics")
    parser.add_argument("--file", help="Specific file to analyze")
    parser.add_argument("--changed-only", action="store_true", help="Only analyze changed files")
    parser.add_argument("--compare", action="store_true",
                        help="Compare new content against existing corpus")
    parser.add_argument("--output", choices=["comment", "json", "ai"], default="comment",
                        help="Output format")
    parser.add_argument("--chapters-dir", default="chapters", help="Directory containing chapters")
    args = parser.parse_args()

    chapters_dir = Path(args.chapters_dir)

    # Determine which files to analyze
    if args.file:
        new_files = [args.file]
        do_compare = args.compare
    elif args.changed_only:
        new_files = get_changed_files()
        if not new_files:
            print("No chapter files changed in this PR")
            return
        # Auto-enable comparison for PRs
        do_compare = True
    else:
        # Analyze all chapters (no comparison needed)
        if chapters_dir.exists():
            new_files = sorted([str(f) for f in chapters_dir.glob("**/*.md")])
        else:
            new_files = []
        do_compare = False

    if not new_files:
        print("No files to analyze")
        return

    print(f"Analyzing {len(new_files)} new/changed file(s)...")
    new_chapters, new_stats = analyze_files(new_files)

    if not new_chapters:
        print("No chapters analyzed successfully")
        return

    # If comparing, also analyze existing corpus
    if do_compare and chapters_dir.exists():
        all_chapter_files = sorted([str(f) for f in chapters_dir.glob("**/*.md")])
        corpus_files = [f for f in all_chapter_files if f not in new_files]

        if corpus_files:
            print(f"Analyzing {len(corpus_files)} existing corpus file(s)...")
            _, corpus_stats = analyze_files(corpus_files)
        else:
            corpus_stats = []

        # Compute impact
        impact = compute_impact(new_stats, corpus_stats)

        # Output with impact analysis
        Path("output").mkdir(exist_ok=True)

        if args.output == "json":
            output = {
                "new_chapters": [c.model_dump() for c in new_chapters],
                "impact": impact.model_dump(),
            }
            print(json.dumps(output, indent=2))
        elif args.output == "ai":
            # Format for AI context
            lines = ["## Pre-computed Text Statistics with Corpus Comparison\n"]
            lines.append("Use these metrics to inform your feedback:\n")
            lines.append(f"**New content:** {impact.new_content.total_word_count:,} words, "
                         f"Flesch {impact.new_content.avg_flesch_reading_ease}")
            lines.append(f"**Existing corpus:** {impact.existing_corpus.total_word_count:,} words, "
                         f"Flesch {impact.existing_corpus.avg_flesch_reading_ease}")
            lines.append(f"**After adding:** Flesch {impact.combined.avg_flesch_reading_ease}")
            lines.append("\n**Impact:**")
            for stmt in impact.impact_summary:
                lines.append(f"- {stmt}")
            output = "\n".join(lines)
            print(output)
            Path("output/text-stats-ai.md").write_text(output)
        else:
            output = format_impact_comment(impact, new_chapters)
            print(output)
            Path("output/text-stats-comment.md").write_text(output)

    else:
        # Simple output without comparison
        Path("output").mkdir(exist_ok=True)

        if args.output == "json":
            output = [c.model_dump() for c in new_chapters]
            print(json.dumps(output, indent=2))
        elif args.output == "ai":
            output = format_stats_for_ai(new_chapters)
            print(output)
            Path("output/text-stats-ai.md").write_text(output)
        else:
            output = format_stats_comment(new_chapters)
            print(output)
            Path("output/text-stats-comment.md").write_text(output)

    print(f"\nAnalyzed {len(new_chapters)} file(s)")


if __name__ == "__main__":
    main()
