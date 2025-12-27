"""
Conversation state tracking for AI Book Editor.

Maintains persistent state across the editorial conversation:
- What's been established (decisions made)
- Outstanding questions (awaiting author response)
- Prerequisites for major actions (PR creation gates)

State is stored in the issue body as a markdown section that can be:
- Read by the bot to inform responses
- Updated by the bot after each interaction
- Checked off by authors directly in GitHub

This gives the AI "working memory" - it remembers what it asked
and gently persists until questions are answered.
"""

import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EstablishedFact(BaseModel):
    """A fact that's been established in the conversation."""

    model_config = ConfigDict(strict=True)

    key: str = Field(description="What was established (e.g., 'audience', 'tone')")
    value: str = Field(description="The established value")
    established_at: Optional[str] = Field(default=None, description="When this was established")


class OutstandingQuestion(BaseModel):
    """A question the editor asked that hasn't been answered."""

    model_config = ConfigDict(strict=True)

    question: str = Field(description="The question text")
    asked_at: str = Field(description="When the question was asked")
    answered: bool = Field(default=False, description="Whether it's been answered")
    context: Optional[str] = Field(default=None, description="Why this question matters")


class Prerequisite(BaseModel):
    """A prerequisite that must be met before a major action."""

    model_config = ConfigDict(strict=True)

    requirement: str = Field(description="What needs to be done")
    met: bool = Field(default=False, description="Whether it's been satisfied")
    blocks: str = Field(default="pr_creation", description="What action this blocks")


class ConversationState(BaseModel):
    """
    Complete state of an editorial conversation.

    This is the "working memory" of the AI editor.
    """

    model_config = ConfigDict(strict=True)

    issue_number: int = Field(description="The issue this state belongs to")
    phase: str = Field(default="discovery", description="Current editorial phase")

    # What we've learned/decided
    established: list[EstablishedFact] = Field(
        default_factory=list, description="Facts established in conversation"
    )

    # Questions awaiting response
    outstanding_questions: list[OutstandingQuestion] = Field(
        default_factory=list, description="Questions not yet answered"
    )

    # Gates for major actions
    prerequisites: list[Prerequisite] = Field(
        default_factory=list, description="Prerequisites for PR creation"
    )

    # Metadata
    last_updated: Optional[str] = Field(default=None, description="When state was last updated")

    def has_unanswered_questions(self) -> bool:
        """Check if there are questions awaiting response."""
        return any(not q.answered for q in self.outstanding_questions)

    def get_unanswered_questions(self) -> list[OutstandingQuestion]:
        """Get all unanswered questions."""
        return [q for q in self.outstanding_questions if not q.answered]

    def has_unmet_prerequisites(self, action: str = "pr_creation") -> bool:
        """Check if there are unmet prerequisites for an action."""
        return any(not p.met and p.blocks == action for p in self.prerequisites)

    def get_unmet_prerequisites(self, action: str = "pr_creation") -> list[Prerequisite]:
        """Get all unmet prerequisites for an action."""
        return [p for p in self.prerequisites if not p.met and p.blocks == action]

    def add_question(self, question: str, context: Optional[str] = None) -> None:
        """Add a new outstanding question."""
        # Don't add duplicates
        for q in self.outstanding_questions:
            if q.question.lower().strip() == question.lower().strip():
                return

        self.outstanding_questions.append(
            OutstandingQuestion(
                question=question,
                asked_at=datetime.now(timezone.utc).isoformat(),
                answered=False,
                context=context,
            )
        )

    def mark_question_answered(self, question_substring: str) -> bool:
        """Mark a question as answered by matching substring."""
        for q in self.outstanding_questions:
            if question_substring.lower() in q.question.lower():
                q.answered = True
                return True
        return False

    def establish_fact(self, key: str, value: str) -> None:
        """Establish or update a fact."""
        # Update if exists
        for fact in self.established:
            if fact.key.lower() == key.lower():
                fact.value = value
                fact.established_at = datetime.now(timezone.utc).isoformat()
                return

        # Add new
        self.established.append(
            EstablishedFact(
                key=key,
                value=value,
                established_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    def add_prerequisite(self, requirement: str, blocks: str = "pr_creation") -> None:
        """Add a prerequisite for an action."""
        # Don't add duplicates
        for p in self.prerequisites:
            if p.requirement.lower() == requirement.lower():
                return

        self.prerequisites.append(Prerequisite(requirement=requirement, met=False, blocks=blocks))

    def mark_prerequisite_met(self, requirement_substring: str) -> bool:
        """Mark a prerequisite as met by matching substring."""
        for p in self.prerequisites:
            if requirement_substring.lower() in p.requirement.lower():
                p.met = True
                return True
        return False


# =============================================================================
# MARKDOWN SERIALIZATION
# =============================================================================

STATE_SECTION_MARKER = "<!-- AI_EDITOR_STATE -->"
STATE_SECTION_END = "<!-- /AI_EDITOR_STATE -->"


def format_state_markdown(state: ConversationState) -> str:
    """
    Format conversation state as markdown for the issue body.

    This creates a human-readable, checkable section.
    """
    lines = [
        "",
        "---",
        "",
        STATE_SECTION_MARKER,
        "## 📊 Editorial Progress",
        "",
        f"**Phase:** {state.phase.title()}",
        "",
    ]

    # Established facts
    if state.established:
        lines.append("### ✅ Established")
        for fact in state.established:
            lines.append(f"- **{fact.key}:** {fact.value}")
        lines.append("")

    # Outstanding questions
    unanswered = state.get_unanswered_questions()
    if unanswered:
        lines.append("### ⏳ Questions Awaiting Your Response")
        for q in unanswered:
            # Format as checkbox so author can check it off
            lines.append(f"- [ ] {q.question}")
        lines.append("")

    # Prerequisites
    if state.prerequisites:
        lines.append("### 🚧 Prerequisites for PR")
        for p in state.prerequisites:
            checkbox = "[x]" if p.met else "[ ]"
            lines.append(f"- {checkbox} {p.requirement}")
        lines.append("")

    # Footer
    now = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    lines.append(f"*Updated by AI Editor · {now}*")
    lines.append(STATE_SECTION_END)
    lines.append("")

    return "\n".join(lines)


def parse_state_from_body(issue_body: str, issue_number: int) -> ConversationState:
    """
    Parse conversation state from issue body markdown.

    Extracts the state section and parses checkboxes to determine status.
    """
    state = ConversationState(issue_number=issue_number)

    # Find the state section
    if STATE_SECTION_MARKER not in issue_body:
        return state

    # Extract section
    start = issue_body.find(STATE_SECTION_MARKER)
    end = issue_body.find(STATE_SECTION_END)
    if end == -1:
        end = len(issue_body)

    section = issue_body[start:end]

    # Parse phase
    phase_match = re.search(r"\*\*Phase:\*\*\s*(\w+)", section)
    if phase_match:
        state.phase = phase_match.group(1).lower()

    # Parse established facts
    established_section = re.search(r"### ✅ Established\n(.*?)(?=###|\Z)", section, re.DOTALL)
    if established_section:
        for line in established_section.group(1).strip().split("\n"):
            match = re.match(r"-\s+\*\*(.+?):\*\*\s+(.+)", line)
            if match:
                state.established.append(EstablishedFact(key=match.group(1), value=match.group(2)))

    # Parse outstanding questions (checkboxes)
    questions_section = re.search(r"### ⏳ Questions.*?\n(.*?)(?=###|\Z)", section, re.DOTALL)
    if questions_section:
        for line in questions_section.group(1).strip().split("\n"):
            # Match checkbox: - [ ] or - [x]
            match = re.match(r"-\s+\[([ x])\]\s+(.+)", line)
            if match:
                answered = match.group(1) == "x"
                state.outstanding_questions.append(
                    OutstandingQuestion(
                        question=match.group(2),
                        asked_at="",  # Unknown from markdown
                        answered=answered,
                    )
                )

    # Parse prerequisites (checkboxes)
    prereq_section = re.search(
        r"### 🚧 Prerequisites.*?\n(.*?)(?=###|\*Updated|\Z)", section, re.DOTALL
    )
    if prereq_section:
        for line in prereq_section.group(1).strip().split("\n"):
            match = re.match(r"-\s+\[([ x])\]\s+(.+)", line)
            if match:
                met = match.group(1) == "x"
                state.prerequisites.append(Prerequisite(requirement=match.group(2), met=met))

    return state


def update_issue_body_with_state(current_body: str, state: ConversationState) -> str:
    """
    Update issue body with new state, preserving other content.

    If state section exists, replaces it. Otherwise appends it.
    """
    state_markdown = format_state_markdown(state)

    if STATE_SECTION_MARKER in current_body:
        # Replace existing section
        start = current_body.find(STATE_SECTION_MARKER)

        # Find the --- before the marker
        pre_marker = current_body.rfind("---", 0, start)
        if pre_marker != -1 and current_body[pre_marker:start].strip() == "---":
            start = pre_marker

        end = current_body.find(STATE_SECTION_END)
        if end != -1:
            end = end + len(STATE_SECTION_END)
            # Include any trailing newlines
            while end < len(current_body) and current_body[end] == "\n":
                end += 1

        return current_body[:start] + state_markdown + current_body[end:]
    else:
        # Append to body
        return current_body.rstrip() + "\n" + state_markdown


# =============================================================================
# RESPONSE HELPERS
# =============================================================================


def format_outstanding_questions_reminder(state: ConversationState) -> str:
    """
    Format a reminder about unanswered questions for inclusion in response.

    Returns empty string if no outstanding questions.
    """
    unanswered = state.get_unanswered_questions()
    if not unanswered:
        return ""

    lines = [
        "",
        "---",
        "",
        "📋 **Still waiting for your thoughts on:**",
    ]
    for q in unanswered[:3]:  # Limit to top 3
        lines.append(f"- {q.question}")

    if len(unanswered) > 3:
        lines.append(f"- *(and {len(unanswered) - 3} more)*")

    lines.append("")

    return "\n".join(lines)


def format_prerequisite_blocker(state: ConversationState, action: str = "pr_creation") -> str:
    """
    Format a message explaining why an action is blocked.

    Returns empty string if action is not blocked.
    """
    unmet = state.get_unmet_prerequisites(action)
    unanswered = state.get_unanswered_questions()

    if not unmet and not unanswered:
        return ""

    lines = ["Before I can create a PR, we need to address a few things:", ""]

    if unanswered:
        lines.append("**📋 Questions awaiting your response:**")
        for q in unanswered[:3]:
            lines.append(f"- {q.question}")
        lines.append("")

    if unmet:
        lines.append("**🚧 Prerequisites not yet met:**")
        for p in unmet:
            lines.append(f"- {p.requirement}")
        lines.append("")

    lines.append("Let's tackle these first. Which would you like to address?")

    return "\n".join(lines)


def get_default_prerequisites() -> list[Prerequisite]:
    """Get the default prerequisites for PR creation."""
    return [
        Prerequisite(
            requirement="Content outline or structure defined",
            met=False,
            blocks="pr_creation",
        ),
        Prerequisite(
            requirement="Actual chapter content written (not just ideas)",
            met=False,
            blocks="pr_creation",
        ),
    ]


def extract_questions_from_response(response_text: str) -> list[str]:
    """
    Extract questions from an AI response that should be tracked.

    Looks for lines ending with ? that seem like substantive questions.
    """
    questions = []

    # Look for bold questions (often the important ones)
    bold_questions = re.findall(r"\*\*([^*]+\?)\*\*", response_text)
    questions.extend(bold_questions)

    # Look for numbered questions
    numbered = re.findall(r"\d+\.\s+\*\*([^*]+\?)\*\*", response_text)
    questions.extend(numbered)

    # Filter out rhetorical/short questions
    filtered = []
    for q in questions:
        # Skip very short questions (likely rhetorical)
        if len(q) < 20:
            continue
        # Skip questions that are just confirmations
        if q.lower().startswith(("does that", "sound good", "make sense")):
            continue
        filtered.append(q.strip())

    return list(set(filtered))  # Dedupe


# =============================================================================
# CROSS-ISSUE KNOWLEDGE PROPAGATION
# =============================================================================


def persist_to_knowledge_base(
    state: ConversationState,
    knowledge_path: str = ".ai-context/knowledge.jsonl",
) -> int:
    """
    Persist established facts to project-wide knowledge base.

    This enables cross-issue memory - facts established in Issue #33
    become available to Issue #34.

    Returns number of facts written.
    """
    import json
    from pathlib import Path

    if not state.established:
        return 0

    path = Path(knowledge_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing knowledge to avoid duplicates
    existing_keys = set()
    if path.exists():
        with open(path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "established_fact":
                        existing_keys.add(entry.get("key", "").lower())
                except json.JSONDecodeError:
                    continue

    # Write new facts
    written = 0
    with open(path, "a") as f:
        for fact in state.established:
            if fact.key.lower() in existing_keys:
                continue  # Skip duplicates

            entry = {
                "type": "established_fact",
                "key": fact.key,
                "value": fact.value,
                "source_issue": state.issue_number,
                "established_at": fact.established_at,
            }
            f.write(json.dumps(entry) + "\n")
            written += 1
            existing_keys.add(fact.key.lower())

    if written > 0:
        print(f"Persisted {written} facts to knowledge base from issue #{state.issue_number}")

    return written


def compact_state(state: ConversationState) -> ConversationState:
    """
    Compact a conversation state by removing completed items.

    Answered questions and met prerequisites are removed from active tracking.
    They can always be retrieved from:
    - The knowledge base (for facts)
    - Closed issues/PRs (for history)
    - Git log (for changes)

    Returns a new compacted state.
    """
    # Keep only unanswered questions
    active_questions = [q for q in state.outstanding_questions if not q.answered]

    # Keep only unmet prerequisites
    active_prerequisites = [p for p in state.prerequisites if not p.met]

    # Count what we're removing
    removed_questions = len(state.outstanding_questions) - len(active_questions)
    removed_prerequisites = len(state.prerequisites) - len(active_prerequisites)

    if removed_questions > 0 or removed_prerequisites > 0:
        print(
            f"Compacted state: removed {removed_questions} answered questions, "
            f"{removed_prerequisites} met prerequisites"
        )

    return ConversationState(
        issue_number=state.issue_number,
        phase=state.phase,
        established=state.established,  # Keep all established facts
        outstanding_questions=active_questions,
        prerequisites=active_prerequisites,
        last_updated=state.last_updated,
    )


def get_context_references(issue_number: int, repo=None) -> list[str]:
    """
    Get references to where additional context can be found.

    Returns list of references like:
    - "Issue #33 (closed) - initial voice memo discussion"
    - "PR #34 (merged) - chapter integration"
    - "git log chapters/chapter-03.md - change history"
    """
    references = []

    # If we have repo access, we could query for related issues/PRs
    # For now, return a generic reference
    references.append(f"Issue #{issue_number} comments - full conversation history")
    references.append("git log --oneline -- chapters/ - chapter change history")
    references.append(".ai-context/knowledge.jsonl - established facts from all issues")

    return references


def format_closing_summary(
    state: ConversationState,
    reason: str = "completed",
    related_pr: int = None,
) -> str:
    """
    Format a summary comment for when an issue is closed.

    This creates a permanent record in the issue for future AI reference.
    """
    lines = ["## 📋 Issue Summary\n"]

    # Reason for closing
    if reason == "completed":
        lines.append("**Status:** ✅ Completed\n")
    elif reason == "not_planned":
        lines.append("**Status:** ⏭️ Not planned\n")
    elif reason == "duplicate":
        lines.append("**Status:** 🔄 Duplicate\n")
    else:
        lines.append(f"**Status:** {reason}\n")

    # Related PR
    if related_pr:
        lines.append(f"**Related PR:** #{related_pr}\n")

    # Decisions made
    if state.established:
        lines.append("### Decisions Made\n")
        for fact in state.established:
            lines.append(f"- **{fact.key}:** {fact.value}")
        lines.append("")

    # Questions that were answered
    answered = [q for q in state.outstanding_questions if q.answered]
    if answered:
        lines.append("### Questions Resolved\n")
        for q in answered[:5]:  # Limit to 5
            lines.append(f"- ✅ {q.question}")
        if len(answered) > 5:
            lines.append(f"- *(+{len(answered) - 5} more)*")
        lines.append("")

    # Any remaining questions (for transparency)
    unanswered = [q for q in state.outstanding_questions if not q.answered]
    if unanswered:
        lines.append("### Deferred Questions\n")
        for q in unanswered[:3]:
            lines.append(f"- ⏳ {q.question}")
        lines.append("")

    # Context references
    lines.append("### For Future Reference\n")
    lines.append("- Facts persisted to `.ai-context/knowledge.jsonl`")
    if related_pr:
        lines.append(f"- Content integrated via PR #{related_pr}")
    lines.append("- Full conversation in this issue's comments")
    lines.append("")

    lines.append("---\n*Summary generated by AI Editor*")

    return "\n".join(lines)
