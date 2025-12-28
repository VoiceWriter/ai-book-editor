#!/usr/bin/env python3
"""
Project-level state tracking for holistic editorial awareness.

This module answers: "What are we working on in this book right now?"

Unlike single-issue context, this tracks:
1. All open editorial threads (issues/PRs)
2. Chapter-level maturity states
3. Cross-thread relationships (e.g., "Chapter 2 PR open while Chapter 4 draft submitted")
4. Pending decisions and blockers

This enables the AI editor to have "peripheral vision" - understanding
the full editorial landscape, not just the current issue.
"""

import os
import sys
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ChapterState(str, Enum):
    """State of a single chapter in the book."""

    VOID = "void"  # Not yet started
    DRAFTED = "drafted"  # Initial draft submitted
    IN_DISCOVERY = "in_discovery"  # Editor asking questions
    IN_FEEDBACK = "in_feedback"  # Editor providing feedback
    IN_REVISION = "in_revision"  # Author revising based on feedback
    APPROVED = "approved"  # Chapter approved, ready for integration


class WorkItemType(str, Enum):
    """Type of work item being tracked."""

    VOICE_MEMO = "voice_memo"  # New content submission
    FEEDBACK_THREAD = "feedback_thread"  # Ongoing editorial discussion
    PULL_REQUEST = "pull_request"  # Content integration PR
    QUESTION = "question"  # Author question to editor


class WorkItemState(str, Enum):
    """State of an individual work item (issue/PR)."""

    OPEN = "open"
    IN_DISCOVERY = "in_discovery"
    AWAITING_AUTHOR = "awaiting_author"
    AWAITING_EDITOR = "awaiting_editor"
    PR_OPEN = "pr_open"
    MERGED = "merged"
    CLOSED = "closed"


class WorkItem(BaseModel):
    """A single work item (issue or PR) in the project."""

    model_config = ConfigDict(strict=True)

    number: int = Field(description="GitHub issue/PR number")
    title: str = Field(description="Issue/PR title")
    item_type: WorkItemType = Field(description="Type of work item")
    state: WorkItemState = Field(description="Current state")
    chapter: Optional[str] = Field(
        default=None, description="Associated chapter file if known"
    )
    created_at: str = Field(description="ISO timestamp of creation")
    updated_at: str = Field(description="ISO timestamp of last update")
    labels: list[str] = Field(default_factory=list, description="GitHub labels")
    last_actor: str = Field(description="Who acted last (author or editor)")
    summary: Optional[str] = Field(
        default=None, description="Brief summary of current state"
    )


class ChapterStatus(BaseModel):
    """Status of a single chapter."""

    model_config = ConfigDict(strict=True)

    path: str = Field(description="File path (e.g., chapters/01-intro.md)")
    title: Optional[str] = Field(default=None, description="Chapter title if known")
    state: ChapterState = Field(description="Current editorial state")
    word_count: int = Field(default=0, description="Current word count")
    active_issues: list[int] = Field(
        default_factory=list, description="Issue numbers discussing this chapter"
    )
    active_prs: list[int] = Field(
        default_factory=list, description="PR numbers modifying this chapter"
    )
    last_updated: Optional[str] = Field(
        default=None, description="ISO timestamp of last content change"
    )


class ProjectState(BaseModel):
    """
    Complete state of the editorial project.

    This is the "peripheral vision" model - everything the editor
    needs to understand what's happening across the whole book.
    """

    model_config = ConfigDict(strict=True)

    # Metadata
    repo_name: str = Field(description="Repository name (owner/repo)")
    generated_at: str = Field(description="ISO timestamp when state was captured")

    # Book-level
    book_phase: str = Field(
        default="drafting",
        description="Overall book phase (new/drafting/revising/polishing/complete)",
    )
    total_chapters: int = Field(default=0, description="Total chapter count")
    chapters_approved: int = Field(default=0, description="Chapters in approved state")

    # Chapter tracking
    chapters: list[ChapterStatus] = Field(
        default_factory=list, description="Status of each chapter"
    )

    # Work items
    open_issues: list[WorkItem] = Field(
        default_factory=list, description="All open issues"
    )
    open_prs: list[WorkItem] = Field(
        default_factory=list, description="All open pull requests"
    )

    # Cross-thread awareness
    awaiting_author: list[int] = Field(
        default_factory=list, description="Issue numbers waiting for author response"
    )
    awaiting_editor: list[int] = Field(
        default_factory=list, description="Issue numbers waiting for editor response"
    )

    # Pending decisions
    pending_decisions: list[str] = Field(
        default_factory=list,
        description="Decisions that need author input before proceeding",
    )

    def get_active_summary(self) -> str:
        """
        Generate a natural language summary of current project state.

        This is what gets injected into the editor's system prompt
        for holistic awareness.
        """
        lines = []

        # Book progress
        if self.total_chapters > 0:
            progress = f"{self.chapters_approved}/{self.total_chapters}"
            lines.append(
                f"Book progress: {progress} chapters approved ({self.book_phase} phase)"
            )
        else:
            lines.append(f"Book phase: {self.book_phase} (no chapters yet)")

        # Open threads
        if self.open_issues:
            lines.append(f"\nOpen editorial threads ({len(self.open_issues)}):")
            for item in self.open_issues[:5]:  # Limit to 5 most relevant
                status = (
                    "⏳ awaiting author"
                    if item.number in self.awaiting_author
                    else "📝 awaiting editor"
                )
                chapter_note = f" (Chapter: {item.chapter})" if item.chapter else ""
                lines.append(
                    f"  - #{item.number}: {item.title}{chapter_note} [{status}]"
                )
            if len(self.open_issues) > 5:
                lines.append(f"  ... and {len(self.open_issues) - 5} more")

        # Open PRs
        if self.open_prs:
            lines.append(f"\nOpen PRs ({len(self.open_prs)}):")
            for pr in self.open_prs[:3]:
                chapter_note = f" (Chapter: {pr.chapter})" if pr.chapter else ""
                lines.append(f"  - PR #{pr.number}: {pr.title}{chapter_note}")

        # Chapters in active work
        active_chapters = [
            c
            for c in self.chapters
            if c.state not in (ChapterState.VOID, ChapterState.APPROVED)
        ]
        if active_chapters:
            lines.append("\nChapters in active editorial work:")
            for chapter in active_chapters:
                lines.append(f"  - {chapter.path}: {chapter.state.value}")

        # Pending decisions
        if self.pending_decisions:
            lines.append("\nPending author decisions:")
            for decision in self.pending_decisions[:3]:
                lines.append(f"  - {decision}")

        return "\n".join(lines)


def _detect_work_item_state(issue, labels: list[str]) -> WorkItemState:
    """Detect work item state from labels and issue state."""
    label_names = [lbl.lower() for lbl in labels]

    if issue.state == "closed":
        return WorkItemState.CLOSED

    if "phase:discovery" in label_names:
        return WorkItemState.IN_DISCOVERY
    if "awaiting-author" in label_names or "waiting-for-author" in label_names:
        return WorkItemState.AWAITING_AUTHOR
    if "awaiting-editor" in label_names or "ai-reviewed" in label_names:
        return WorkItemState.AWAITING_EDITOR

    return WorkItemState.OPEN


def _detect_work_item_type(labels: list[str]) -> WorkItemType:
    """Detect work item type from labels."""
    label_names = [lbl.lower() for lbl in labels]

    if "voice_transcription" in label_names or "voice-memo" in label_names:
        return WorkItemType.VOICE_MEMO
    if "question" in label_names:
        return WorkItemType.QUESTION

    return WorkItemType.FEEDBACK_THREAD


def _extract_chapter_from_issue(issue) -> Optional[str]:
    """Try to extract chapter reference from issue title/body."""
    import re

    # Check title for chapter patterns
    title = issue.title.lower()
    body = (issue.body or "").lower()
    text = title + " " + body

    # Pattern: "chapter X", "ch X", "chapters/XX-"
    patterns = [
        r"chapter\s*(\d+)",
        r"ch\s*(\d+)",
        r"chapters/(\d+)-",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            chapter_num = match.group(1).zfill(2)
            return f"chapters/{chapter_num}"

    return None


def _detect_last_actor(issue) -> str:
    """Determine who acted last on an issue."""
    # Check most recent comment
    comments = list(issue.get_comments())
    if comments:
        last_comment = comments[-1]
        if last_comment.user.login == "github-actions[bot]":
            return "editor"
        return "author"

    # No comments, check if issue was just created
    return "author"


def build_project_state(repo, book_config: Optional[dict] = None) -> ProjectState:
    """
    Build complete project state from GitHub repository.

    Args:
        repo: PyGithub Repository object
        book_config: Optional book.yaml config if already loaded

    Returns:
        ProjectState with full editorial context
    """
    from scripts.utils.github_client import get_repo_file
    from scripts.utils.knowledge_base import load_book_config

    now = datetime.now(timezone.utc).isoformat()

    # Load book config if not provided
    if book_config is None:
        book_config = load_book_config(repo) or {}

    # Initialize state
    state = ProjectState(
        repo_name=repo.full_name,
        generated_at=now,
        book_phase=book_config.get("phase", "drafting"),
    )

    # Get chapters
    chapters = []
    try:
        contents = repo.get_contents("chapters")
        if isinstance(contents, list):
            for item in contents:
                if item.name.endswith(".md"):
                    # Get file content to count words
                    content = get_repo_file(repo, item.path) or ""
                    word_count = len(content.split())

                    # Determine chapter state based on content
                    chapter_state = ChapterState.VOID
                    if word_count > 100:
                        chapter_state = ChapterState.DRAFTED
                    if word_count > 1000:
                        chapter_state = ChapterState.APPROVED  # Simplified heuristic

                    chapters.append(
                        ChapterStatus(
                            path=item.path,
                            state=chapter_state,
                            word_count=word_count,
                        )
                    )
    except Exception:
        pass  # No chapters directory yet

    state.chapters = chapters
    state.total_chapters = len(chapters)
    state.chapters_approved = len(
        [c for c in chapters if c.state == ChapterState.APPROVED]
    )

    # Get open issues
    open_issues = []
    awaiting_author = []
    awaiting_editor = []

    for issue in repo.get_issues(state="open"):
        if issue.pull_request:
            continue  # Skip PRs, handle separately

        labels = [lbl.name for lbl in issue.labels]
        item_state = _detect_work_item_state(issue, labels)
        item_type = _detect_work_item_type(labels)
        chapter = _extract_chapter_from_issue(issue)
        last_actor = _detect_last_actor(issue)

        work_item = WorkItem(
            number=issue.number,
            title=issue.title,
            item_type=item_type,
            state=item_state,
            chapter=chapter,
            created_at=issue.created_at.isoformat(),
            updated_at=issue.updated_at.isoformat(),
            labels=labels,
            last_actor=last_actor,
        )
        open_issues.append(work_item)

        # Track who we're waiting on
        if item_state == WorkItemState.AWAITING_AUTHOR:
            awaiting_author.append(issue.number)
        elif item_state in (WorkItemState.AWAITING_EDITOR, WorkItemState.OPEN):
            awaiting_editor.append(issue.number)

        # Link chapter to issue
        if chapter:
            for ch in state.chapters:
                if ch.path.startswith(chapter):
                    ch.active_issues.append(issue.number)

    state.open_issues = open_issues
    state.awaiting_author = awaiting_author
    state.awaiting_editor = awaiting_editor

    # Get open PRs
    open_prs = []
    for pr in repo.get_pulls(state="open"):
        labels = [lbl.name for lbl in pr.labels]

        # Detect chapter from PR files
        chapter = None
        try:
            for file in pr.get_files():
                if file.filename.startswith("chapters/"):
                    chapter = file.filename
                    break
        except Exception:
            pass

        work_item = WorkItem(
            number=pr.number,
            title=pr.title,
            item_type=WorkItemType.PULL_REQUEST,
            state=WorkItemState.PR_OPEN,
            chapter=chapter,
            created_at=pr.created_at.isoformat(),
            updated_at=pr.updated_at.isoformat(),
            labels=labels,
            last_actor="author" if pr.user.login != "github-actions[bot]" else "editor",
        )
        open_prs.append(work_item)

        # Link chapter to PR
        if chapter:
            for ch in state.chapters:
                if ch.path == chapter:
                    ch.active_prs.append(pr.number)

    state.open_prs = open_prs

    return state


def get_project_context_for_prompt(repo, max_tokens: int = 500) -> str:
    """
    Get project state formatted for inclusion in LLM prompts.

    This is the main entry point for adding holistic awareness
    to editorial prompts.

    Args:
        repo: PyGithub Repository object
        max_tokens: Approximate max tokens for the context

    Returns:
        Formatted string for system prompt injection
    """
    state = build_project_state(repo)
    summary = state.get_active_summary()

    # Truncate if needed (rough approximation: 1 token ≈ 4 chars)
    max_chars = max_tokens * 4
    if len(summary) > max_chars:
        summary = summary[:max_chars] + "\n... (truncated)"

    return f"""## Current Project State

{summary}

Use this context to understand what else is happening in this book project.
If the author is discussing something related to another open thread, acknowledge it.
"""


if __name__ == "__main__":
    # Test with environment
    from scripts.utils.github_client import get_github_client, get_repo

    gh = get_github_client()
    repo = get_repo(gh)

    state = build_project_state(repo)
    print(state.get_active_summary())
