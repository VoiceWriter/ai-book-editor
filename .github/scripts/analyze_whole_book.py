#!/usr/bin/env python3
"""
Whole-book analysis for AI Book Editor.

This script reads ALL chapter files and provides holistic feedback:
- Cross-chapter consistency
- Thematic thread tracking
- Character arc analysis
- Repetition detection across chapters
- Promise/payoff tracking
- Structural overview

Great editors hold the entire book in mind. This script enables that.

OUTPUTS:
- analysis_comment: The full book analysis
- consistency_issues: List of cross-chapter issues
- themes: Detected themes
- repetition_warnings: Repeated content flagged
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import BaseModel, ConfigDict, Field
from scripts.utils.github_client import get_github_client  # noqa: E402
from scripts.utils.github_client import get_repo, list_files_in_directory, read_file_content
from scripts.utils.knowledge_base import load_editorial_context  # noqa: E402
from scripts.utils.llm_client import call_editorial, call_editorial_structured  # noqa: E402
from scripts.utils.persona import load_persona  # noqa: E402


class ThematicThread(BaseModel):
    """A thematic thread running through the book."""

    model_config = ConfigDict(strict=True)

    theme: str = Field(description="The theme or motif")
    chapters_present: list[str] = Field(description="Chapters where this appears")
    strength: str = Field(description="How well-developed: strong/moderate/weak")
    notes: Optional[str] = Field(default=None, description="Editorial notes")


class RepetitionWarning(BaseModel):
    """Detected repetition across chapters."""

    model_config = ConfigDict(strict=True)

    content_summary: str = Field(description="What is repeated")
    locations: list[str] = Field(description="Where it appears (chapter:paragraph)")
    recommendation: str = Field(description="Which to keep, which to cut")


class ConsistencyIssue(BaseModel):
    """Cross-chapter consistency issue."""

    model_config = ConfigDict(strict=True)

    issue_type: str = Field(description="Type: character, fact, timeline, terminology, tone")
    description: str = Field(description="What's inconsistent")
    locations: list[str] = Field(description="Where the inconsistency appears")
    severity: str = Field(description="critical/moderate/minor")


class PromisePayoff(BaseModel):
    """A promise made to the reader and its payoff."""

    model_config = ConfigDict(strict=True)

    promise: str = Field(description="What was promised/set up")
    promise_location: str = Field(description="Where the promise is made")
    payoff_location: Optional[str] = Field(
        default=None, description="Where it pays off (null if unfulfilled)"
    )
    status: str = Field(description="fulfilled/unfulfilled/partially_fulfilled")


class WholeBookAnalysis(BaseModel):
    """Complete whole-book analysis."""

    model_config = ConfigDict(strict=True)

    executive_summary: str = Field(description="2-3 sentence overview")
    structural_assessment: str = Field(description="How the book holds together")
    themes: list[ThematicThread] = Field(description="Major themes tracked")
    consistency_issues: list[ConsistencyIssue] = Field(
        description="Cross-chapter consistency problems"
    )
    repetition_warnings: list[RepetitionWarning] = Field(description="Repeated content detected")
    promise_payoffs: list[PromisePayoff] = Field(description="Setup/payoff tracking")
    chapter_by_chapter: list[str] = Field(description="One-line assessment of each chapter")
    recommended_reordering: Optional[str] = Field(
        default=None, description="Suggested chapter order changes"
    )
    next_steps: list[str] = Field(description="Prioritized list of what to address first")


def set_output(name: str, value: str):
    """Set a step output for the GitHub Actions workflow."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            if "\n" in value:
                import uuid

                delimiter = uuid.uuid4().hex
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")


def load_all_chapters(repo) -> dict[str, str]:
    """Load all chapter files from the repository."""
    chapters = {}

    try:
        files = list_files_in_directory(repo, "chapters")
        for file_info in files:
            if file_info["name"].endswith(".md"):
                content = read_file_content(repo, file_info["path"])
                if content:
                    chapters[file_info["name"]] = content
    except Exception as e:
        print(f"Error loading chapters: {e}")

    return chapters


def build_whole_book_prompt(chapters: dict[str, str], context: dict) -> str:
    """Build the analysis prompt with all chapter content."""
    lines = []

    lines.append("# Whole Book Analysis")
    lines.append("")
    lines.append("You are reviewing the ENTIRE manuscript. Your job is to see patterns")
    lines.append("that only become visible when holding the whole book in mind.")
    lines.append("")

    # Editorial context
    if context.get("persona"):
        lines.append("## Your Editorial Persona")
        lines.append(context["persona"])
        lines.append("")

    if context.get("guidelines"):
        lines.append("## Editorial Guidelines")
        lines.append(context["guidelines"])
        lines.append("")

    # All chapters
    lines.append("## The Complete Manuscript")
    lines.append("")

    for chapter_name, content in sorted(chapters.items()):
        lines.append(f"### {chapter_name}")
        lines.append("")
        # Truncate very long chapters for token limits
        if len(content) > 8000:
            lines.append(content[:8000])
            lines.append(f"\n[...truncated, {len(content)} chars total...]")
        else:
            lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Your Analysis Task")
    lines.append("")
    lines.append("Analyze the complete manuscript for:")
    lines.append("")
    lines.append("1. **Thematic Threads**: What themes run through the book?")
    lines.append("   - Which chapters develop each theme?")
    lines.append("   - Are any themes introduced but abandoned?")
    lines.append("")
    lines.append("2. **Consistency Issues**: What contradicts across chapters?")
    lines.append("   - Character details that change")
    lines.append("   - Facts that conflict")
    lines.append("   - Timeline problems")
    lines.append("   - Terminology shifts")
    lines.append("   - Tone inconsistencies")
    lines.append("")
    lines.append("3. **Repetition**: What's said more than once?")
    lines.append("   - Same point made in multiple chapters")
    lines.append("   - Similar anecdotes or examples")
    lines.append("   - Redundant explanations")
    lines.append("   - Which version to keep, which to cut")
    lines.append("")
    lines.append("4. **Promise/Payoff**: What setups pay off? What's left dangling?")
    lines.append("   - Questions raised that get answered")
    lines.append("   - Tensions introduced that get resolved")
    lines.append("   - Promises made to readers that aren't kept")
    lines.append("")
    lines.append("5. **Structural Assessment**: Does the order make sense?")
    lines.append("   - Does information come when readers need it?")
    lines.append("   - Would reordering help?")
    lines.append("   - What's the emotional arc across chapters?")
    lines.append("")
    lines.append("Be specific. Reference exact chapters and quotes.")

    return "\n".join(lines)


def format_analysis_comment(analysis: WholeBookAnalysis, persona_name: str) -> str:
    """Format the analysis as a detailed GitHub comment."""
    lines = []

    lines.append("# Whole Book Analysis")
    lines.append("")
    lines.append(f"*A complete manuscript review by {persona_name}*")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append("")
    lines.append(analysis.executive_summary)
    lines.append("")

    lines.append("## Structural Assessment")
    lines.append("")
    lines.append(analysis.structural_assessment)
    lines.append("")

    # Themes
    if analysis.themes:
        lines.append("## Thematic Threads")
        lines.append("")
        for theme in analysis.themes:
            strength_icon = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}.get(
                theme.strength, "⚪"
            )
            lines.append(f"### {strength_icon} {theme.theme}")
            lines.append(f"**Appears in:** {', '.join(theme.chapters_present)}")
            if theme.notes:
                lines.append(f"*{theme.notes}*")
            lines.append("")

    # Consistency issues
    if analysis.consistency_issues:
        lines.append("## Consistency Issues")
        lines.append("")
        for issue in analysis.consistency_issues:
            severity_icon = {"critical": "🚨", "moderate": "⚠️", "minor": "📝"}.get(
                issue.severity, "📝"
            )
            lines.append(f"### {severity_icon} {issue.issue_type.title()}")
            lines.append(issue.description)
            lines.append(f"**Found in:** {', '.join(issue.locations)}")
            lines.append("")

    # Repetition
    if analysis.repetition_warnings:
        lines.append("## Repetition Warnings")
        lines.append("")
        for rep in analysis.repetition_warnings:
            lines.append(f"### {rep.content_summary}")
            lines.append(f"**Appears in:** {', '.join(rep.locations)}")
            lines.append(f"**Recommendation:** {rep.recommendation}")
            lines.append("")

    # Promise/Payoff
    if analysis.promise_payoffs:
        lines.append("## Promise/Payoff Tracking")
        lines.append("")
        fulfilled = [p for p in analysis.promise_payoffs if p.status == "fulfilled"]
        unfulfilled = [p for p in analysis.promise_payoffs if p.status == "unfulfilled"]

        if unfulfilled:
            lines.append("### ⚠️ Unfulfilled Promises")
            for p in unfulfilled:
                lines.append(f"- **{p.promise}** (introduced in {p.promise_location})")
            lines.append("")

        if fulfilled:
            lines.append("### ✅ Fulfilled Promises")
            for p in fulfilled:
                lines.append(f"- **{p.promise}**: {p.promise_location} → {p.payoff_location}")
            lines.append("")

    # Chapter assessments
    if analysis.chapter_by_chapter:
        lines.append("## Chapter-by-Chapter")
        lines.append("")
        for assessment in analysis.chapter_by_chapter:
            lines.append(f"- {assessment}")
        lines.append("")

    # Reordering
    if analysis.recommended_reordering:
        lines.append("## Suggested Reordering")
        lines.append("")
        lines.append(analysis.recommended_reordering)
        lines.append("")

    # Next steps
    if analysis.next_steps:
        lines.append("## Recommended Next Steps")
        lines.append("")
        for i, step in enumerate(analysis.next_steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("")

    lines.append("---")
    lines.append(f"*— {persona_name}*")

    return "\n".join(lines)


def main():
    # ISSUE_NUMBER not currently used but may be needed for issue-specific analysis
    _ = int(os.environ.get("ISSUE_NUMBER", 0))

    gh = get_github_client()
    repo = get_repo(gh)

    # Load all chapters
    print("Loading all chapter files...")
    chapters = load_all_chapters(repo)

    if not chapters:
        print("No chapters found in chapters/ directory")
        set_output("analysis_comment", "No chapters found to analyze.")
        return

    print(f"Loaded {len(chapters)} chapters: {list(chapters.keys())}")

    # Load editorial context
    context = load_editorial_context(repo)
    persona_id = context.get("persona_id", "margot")
    persona = load_persona(persona_id)

    # Build and send prompt
    print("Building whole-book analysis prompt...")
    prompt = build_whole_book_prompt(chapters, context)

    print("Calling LLM for whole-book analysis (this may take a while)...")

    try:
        analysis, llm_response = call_editorial_structured(
            prompt=prompt,
            response_model=WholeBookAnalysis,
        )
        print(f"Analysis complete: {llm_response.usage.format_compact()}")
    except Exception as e:
        print(f"Structured analysis failed, falling back to freeform: {e}")
        # Fallback to unstructured
        llm_response = call_editorial(prompt)
        # Create a simple analysis comment from the freeform response
        analysis_comment = f"# Whole Book Analysis\n\n{llm_response.content}"
        set_output("analysis_comment", analysis_comment)

        Path("output").mkdir(exist_ok=True)
        Path("output/whole-book-analysis.md").write_text(analysis_comment)
        return

    # Format the analysis
    analysis_comment = format_analysis_comment(analysis, persona.name)

    # Set outputs
    set_output("analysis_comment", analysis_comment)
    set_output("themes", json.dumps([t.theme for t in analysis.themes]))
    set_output(
        "consistency_issues",
        json.dumps([i.model_dump() for i in analysis.consistency_issues]),
    )
    set_output(
        "repetition_warnings",
        json.dumps([r.model_dump() for r in analysis.repetition_warnings]),
    )

    # Save to file
    Path("output").mkdir(exist_ok=True)
    Path("output/whole-book-analysis.md").write_text(analysis_comment)

    print("Whole-book analysis complete:")
    print(f"  - {len(analysis.themes)} themes tracked")
    print(f"  - {len(analysis.consistency_issues)} consistency issues")
    print(f"  - {len(analysis.repetition_warnings)} repetition warnings")
    print(f"  - {len(analysis.promise_payoffs)} promise/payoffs tracked")


if __name__ == "__main__":
    main()
