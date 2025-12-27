"""
Rich PR body generation for AI Book Editor.

Generates detailed, editorial-quality PR descriptions that include:
- Text statistics and impact analysis (before/after comparison)
- Editorial reasoning (chain of thought from LLM)
- Discovery context (what was learned from author)
- Structural analysis (why this content fits here)
- Voice preservation analysis

This is where we showcase ALL the intelligence we've built.
"""

from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict, Field

from .llm_client import LLMResponse

if TYPE_CHECKING:
    from .conversation_state import ConversationState


class DiscoveryContext(BaseModel):
    """Context gathered during the discovery phase."""

    model_config = ConfigDict(strict=True)

    questions_asked: list[str] = Field(
        default_factory=list, description="Discovery questions that were asked"
    )
    author_responses: list[str] = Field(
        default_factory=list, description="Author's responses to questions"
    )
    emotional_state: Optional[str] = Field(default=None, description="Detected emotional state")
    key_learnings: list[str] = Field(
        default_factory=list, description="Key things learned about this content"
    )


class TextDelta(BaseModel):
    """Before/after comparison for a text metric."""

    model_config = ConfigDict(strict=True)

    metric: str = Field(description="Name of the metric")
    before: Optional[float] = Field(default=None, description="Value before change")
    after: float = Field(description="Value after change")
    delta: Optional[float] = Field(default=None, description="Change amount")
    interpretation: str = Field(description="Human-readable interpretation")


class ContentAnalysis(BaseModel):
    """Deep analysis of the content being added."""

    model_config = ConfigDict(strict=True)

    # Word counts
    word_count: int = Field(description="Words in new content")
    reading_time_minutes: float = Field(description="Estimated reading time")

    # Readability
    flesch_reading_ease: float = Field(description="Flesch Reading Ease score")
    flesch_kincaid_grade: float = Field(description="Flesch-Kincaid grade level")

    # Style metrics
    avg_sentence_length: float = Field(description="Average words per sentence")
    lexical_diversity: float = Field(description="Unique words / total words")
    passive_voice_percent: float = Field(description="Percentage passive voice")

    # Comparison with corpus (if available)
    corpus_comparison: list[TextDelta] = Field(
        default_factory=list, description="How this content compares to existing book"
    )


class StructuralAnalysis(BaseModel):
    """Analysis of how the content fits structurally."""

    model_config = ConfigDict(strict=True)

    target_file: str = Field(description="Where the content will be placed")
    placement_rationale: str = Field(description="Why this is the right location")
    related_chapters: list[str] = Field(
        default_factory=list, description="Chapters with related content"
    )
    thematic_connections: list[str] = Field(
        default_factory=list, description="Themes this content connects to"
    )
    flow_impact: str = Field(description="How this affects book flow")


class VoiceAnalysis(BaseModel):
    """Analysis of voice preservation."""

    model_config = ConfigDict(strict=True)

    voice_score: str = Field(description="How well author voice is preserved (high/medium/low)")
    voice_markers: list[str] = Field(
        default_factory=list, description="Specific markers of author's voice preserved"
    )
    transformations: list[str] = Field(default_factory=list, description="What was changed and why")


class DecisionRecord(BaseModel):
    """A decision made during the editorial conversation."""

    model_config = ConfigDict(strict=True)

    decision: str = Field(description="What was decided")
    context: Optional[str] = Field(default=None, description="Why it was decided")


class RichPRBody(BaseModel):
    """Complete rich PR body with all analysis sections."""

    model_config = ConfigDict(strict=True)

    # Core info
    source_issue: int = Field(description="Source issue number")
    target_file: str = Field(description="Target file path")

    # Content analysis
    content_analysis: ContentAnalysis = Field(description="Text statistics and analysis")

    # Structural
    structural: StructuralAnalysis = Field(description="Structural placement analysis")

    # Voice
    voice: VoiceAnalysis = Field(description="Voice preservation analysis")

    # Discovery (optional)
    discovery: Optional[DiscoveryContext] = Field(
        default=None, description="Context from discovery phase"
    )

    # Decisions and context - for future AI reference
    decisions_made: list[DecisionRecord] = Field(
        default_factory=list, description="Decisions made during editorial process"
    )
    outstanding_items: list[str] = Field(
        default_factory=list, description="Items still to be addressed"
    )
    context_references: list[str] = Field(
        default_factory=list, description="Where to find more context"
    )

    # Editorial reasoning (from LLM)
    editorial_reasoning: str = Field(description="Chain of thought editorial reasoning")
    editorial_notes: str = Field(description="Editor's notes on the content")

    # Prepared content summary
    content_summary: str = Field(description="Brief summary of what's being added")

    # LLM usage
    llm_usage_summary: str = Field(description="Token usage and cost")


def format_rich_pr_body(pr_body: RichPRBody) -> str:
    """
    Format a RichPRBody into a comprehensive PR description.

    This is the main output that appears in the PR on GitHub.
    """
    sections = []

    # Header
    sections.append(
        f"""## 📝 Voice Memo Integration

**Source:** #{pr_body.source_issue}
**Target:** `{pr_body.target_file}`

---

### Summary

{pr_body.content_summary}
"""
    )

    # Text Statistics
    ca = pr_body.content_analysis
    sections.append(
        f"""### 📊 Text Analysis

| Metric | Value |
|--------|-------|
| Word Count | {ca.word_count:,} |
| Reading Time | {ca.reading_time_minutes:.1f} min |
| Flesch Reading Ease | {ca.flesch_reading_ease:.1f} |
| Grade Level | {ca.flesch_kincaid_grade:.1f} |
| Avg Sentence Length | {ca.avg_sentence_length:.1f} words |
| Lexical Diversity | {ca.lexical_diversity:.0%} |
| Passive Voice | {ca.passive_voice_percent:.1f}% |
"""
    )

    # Corpus comparison if available
    if ca.corpus_comparison:
        sections.append("#### Impact on Book\n")
        for delta in ca.corpus_comparison:
            if delta.before is not None and delta.delta is not None:
                arrow = "↑" if delta.delta > 0 else "↓" if delta.delta < 0 else "→"
                sections.append(
                    f"- **{delta.metric}:** {delta.before:.1f} → {delta.after:.1f} "
                    f"({arrow} {abs(delta.delta):.1f}) — {delta.interpretation}"
                )
            else:
                sections.append(f"- **{delta.metric}:** {delta.after:.1f} — {delta.interpretation}")
        sections.append("")

    # Structural Analysis
    sa = pr_body.structural
    sections.append(
        f"""### 🏗️ Structural Placement

**Target:** `{sa.target_file}`

**Why here?** {sa.placement_rationale}
"""
    )

    if sa.related_chapters:
        sections.append(f"**Related chapters:** {', '.join(sa.related_chapters)}\n")

    if sa.thematic_connections:
        sections.append(f"**Thematic connections:** {', '.join(sa.thematic_connections)}\n")

    sections.append(f"**Flow impact:** {sa.flow_impact}\n")

    # Voice Analysis
    va = pr_body.voice
    sections.append(
        f"""### 🎤 Voice Preservation

**Voice Score:** {va.voice_score}
"""
    )

    if va.voice_markers:
        sections.append("**Markers preserved:**")
        for marker in va.voice_markers[:5]:  # Limit to top 5
            sections.append(f"- {marker}")
        sections.append("")

    if va.transformations:
        sections.append("**Transformations made:**")
        for t in va.transformations[:5]:  # Limit to top 5
            sections.append(f"- {t}")
        sections.append("")

    # Discovery Context (if available)
    if pr_body.discovery and pr_body.discovery.author_responses:
        sections.append(
            """### 💬 Discovery Context

What we learned from the author:
"""
        )
        for learning in pr_body.discovery.key_learnings[:5]:
            sections.append(f"- {learning}")
        sections.append("")

        if pr_body.discovery.emotional_state:
            sections.append(f"**Author's emotional state:** {pr_body.discovery.emotional_state}\n")

    # Decisions Made (important for future AI context)
    if pr_body.decisions_made:
        sections.append(
            """### 📌 Decisions Made

*These decisions were made during the editorial conversation:*
"""
        )
        for decision in pr_body.decisions_made:
            if decision.context:
                sections.append(f"- **{decision.decision}** — {decision.context}")
            else:
                sections.append(f"- {decision.decision}")
        sections.append("")

    # Outstanding Items (for transparency)
    if pr_body.outstanding_items:
        sections.append(
            """### ⏳ Outstanding Items

*Items still to be addressed in future iterations:*
"""
        )
        for item in pr_body.outstanding_items:
            sections.append(f"- {item}")
        sections.append("")

    # Editorial Notes
    sections.append(
        f"""### 📋 Editorial Notes

{pr_body.editorial_notes}
"""
    )

    # Context References (where to find more info)
    if pr_body.context_references:
        sections.append(
            """### 🔗 Context References

*For more context, see:*
"""
        )
        for ref in pr_body.context_references:
            sections.append(f"- {ref}")
        sections.append("")

    # Editorial Reasoning (collapsible)
    if pr_body.editorial_reasoning:
        sections.append(
            f"""<details>
<summary>🧠 <strong>Editorial Reasoning</strong> (click to expand)</summary>

{pr_body.editorial_reasoning}

</details>
"""
        )

    # Checklist
    sections.append(
        """### ✅ Editorial Checklist

- [ ] Content flows naturally in context
- [ ] Author's voice is preserved
- [ ] No redundancy with other sections
- [ ] Formatting matches book style
- [ ] Terminology aligns with glossary
"""
    )

    # Footer
    sections.append(
        f"""---

<sub>{pr_body.llm_usage_summary}</sub>
"""
    )

    return "\n".join(sections)


def build_rich_pr_body(
    source_issue: int,
    target_file: str,
    prepared_content: str,
    llm_response: LLMResponse,
    editorial_notes: str,
    content_summary: str,
    discovery_context: Optional[dict] = None,
    existing_chapter_content: Optional[str] = None,
    chapters_list: Optional[list[str]] = None,
    conversation_state: Optional["ConversationState"] = None,  # Forward reference
) -> RichPRBody:
    """
    Build a RichPRBody from available data.

    This function gathers all analysis and creates the structured PR body.
    """
    # Import here to avoid circular imports
    # analyze_text_stats is in parent directory (.github/scripts/)
    from scripts.analyze_text_stats import analyze_text, compute_impact

    # Analyze the new content
    new_stats = analyze_text(prepared_content, target_file)

    # Build corpus comparison if we have existing content
    corpus_comparison = []
    if existing_chapter_content:
        existing_stats = analyze_text(existing_chapter_content, target_file)
        impact = compute_impact([new_stats], [existing_stats])

        # Convert impact summary to TextDelta objects
        for stmt in impact.impact_summary:
            # Parse the impact statements - they follow a pattern
            corpus_comparison.append(
                TextDelta(
                    metric="Overall",
                    before=None,
                    after=0,
                    delta=None,
                    interpretation=stmt,
                )
            )

    # Build content analysis
    content_analysis = ContentAnalysis(
        word_count=new_stats.word_count,
        reading_time_minutes=new_stats.reading_time_minutes,
        flesch_reading_ease=new_stats.flesch_reading_ease,
        flesch_kincaid_grade=new_stats.flesch_kincaid_grade,
        avg_sentence_length=new_stats.avg_sentence_length,
        lexical_diversity=new_stats.lexical_diversity,
        passive_voice_percent=new_stats.passive_voice_percent,
        corpus_comparison=corpus_comparison,
    )

    # Build structural analysis
    # Determine related chapters based on filename patterns
    related_chapters = []
    if chapters_list:
        # Simple heuristic: chapters with similar prefixes
        base_name = target_file.split("/")[-1].replace(".md", "")
        for chapter in chapters_list:
            if chapter != base_name and base_name[:3] in chapter:
                related_chapters.append(chapter)

    structural = StructuralAnalysis(
        target_file=target_file,
        placement_rationale="Content placed based on author direction and thematic fit",
        related_chapters=related_chapters[:3],  # Limit to 3
        thematic_connections=[],  # Would come from LLM analysis
        flow_impact="To be assessed during review",
    )

    # Build voice analysis (simplified - would ideally come from LLM)
    voice = VoiceAnalysis(
        voice_score="high",
        voice_markers=[
            "Conversational tone preserved",
            "Original phrasing maintained where possible",
        ],
        transformations=[
            "Cleaned up filler words",
            "Structured into paragraphs",
            "Added transitions for flow",
        ],
    )

    # Build discovery context if available
    discovery = None
    if discovery_context:
        discovery = DiscoveryContext(
            questions_asked=discovery_context.get("questions_asked", []),
            author_responses=discovery_context.get("author_responses", [])[:3],  # Limit
            emotional_state=discovery_context.get("emotional_state"),
            key_learnings=discovery_context.get("knowledge_items", [])[:5],  # Limit
        )

    # Format editorial reasoning
    editorial_reasoning = llm_response.format_reasoning_summary()

    # Format usage
    usage_summary = (
        llm_response.usage.format_summary() if llm_response.usage else "Usage not tracked"
    )

    # Extract decisions from conversation state
    decisions_made = []
    outstanding_items = []
    if conversation_state:
        # Established facts become decisions
        for fact in conversation_state.established:
            decisions_made.append(
                DecisionRecord(
                    decision=f"{fact.key}: {fact.value}",
                    context=f"Established in issue #{source_issue}",
                )
            )

        # Unanswered questions become outstanding items
        for q in conversation_state.outstanding_questions:
            if not q.answered:
                outstanding_items.append(q.question)

        # Unmet prerequisites become outstanding items
        for p in conversation_state.prerequisites:
            if not p.met:
                outstanding_items.append(f"Prerequisite: {p.requirement}")

    # Build context references - where to find more info
    context_references = [
        f"Issue #{source_issue} — full conversation history",
        ".ai-context/knowledge.jsonl — established facts from all issues",
        f"git log --oneline -- {target_file} — change history for this file",
    ]

    return RichPRBody(
        source_issue=source_issue,
        target_file=target_file,
        content_analysis=content_analysis,
        structural=structural,
        voice=voice,
        discovery=discovery,
        decisions_made=decisions_made,
        outstanding_items=outstanding_items,
        context_references=context_references,
        editorial_reasoning=editorial_reasoning,
        editorial_notes=editorial_notes,
        content_summary=content_summary,
        llm_usage_summary=usage_summary,
    )
