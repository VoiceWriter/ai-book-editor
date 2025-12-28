"""Tests for project_state module - holistic editorial awareness."""

from scripts.utils.project_state import (
    ChapterState,
    ChapterStatus,
    ProjectState,
    WorkItem,
    WorkItemState,
    WorkItemType,
)


class TestWorkItemModel:
    """Test WorkItem Pydantic model."""

    def test_work_item_creation(self):
        """Test creating a work item with all required fields."""
        item = WorkItem(
            number=42,
            title="Voice memo about chapter 3",
            item_type=WorkItemType.VOICE_MEMO,
            state=WorkItemState.OPEN,
            created_at="2025-12-28T10:00:00Z",
            updated_at="2025-12-28T11:00:00Z",
            labels=["voice_transcription"],
            last_actor="author",
        )

        assert item.number == 42
        assert item.title == "Voice memo about chapter 3"
        assert item.item_type == WorkItemType.VOICE_MEMO
        assert item.state == WorkItemState.OPEN
        assert item.last_actor == "author"
        assert item.chapter is None  # Optional
        assert item.summary is None  # Optional

    def test_work_item_with_chapter(self):
        """Test work item with chapter reference."""
        item = WorkItem(
            number=43,
            title="Feedback on intro",
            item_type=WorkItemType.FEEDBACK_THREAD,
            state=WorkItemState.IN_DISCOVERY,
            chapter="chapters/01-intro.md",
            created_at="2025-12-28T10:00:00Z",
            updated_at="2025-12-28T11:00:00Z",
            labels=["phase:discovery"],
            last_actor="editor",
            summary="Discussing the opening hook",
        )

        assert item.chapter == "chapters/01-intro.md"
        assert item.summary == "Discussing the opening hook"


class TestChapterStatusModel:
    """Test ChapterStatus Pydantic model."""

    def test_chapter_status_creation(self):
        """Test creating a chapter status."""
        chapter = ChapterStatus(
            path="chapters/01-intro.md",
            state=ChapterState.DRAFTED,
            word_count=1500,
        )

        assert chapter.path == "chapters/01-intro.md"
        assert chapter.state == ChapterState.DRAFTED
        assert chapter.word_count == 1500
        assert chapter.active_issues == []
        assert chapter.active_prs == []

    def test_chapter_with_active_work(self):
        """Test chapter with active issues and PRs."""
        chapter = ChapterStatus(
            path="chapters/02-methodology.md",
            title="Research Methodology",
            state=ChapterState.IN_FEEDBACK,
            word_count=3200,
            active_issues=[42, 45],
            active_prs=[12],
            last_updated="2025-12-27T15:00:00Z",
        )

        assert chapter.title == "Research Methodology"
        assert len(chapter.active_issues) == 2
        assert 42 in chapter.active_issues


class TestProjectStateModel:
    """Test ProjectState Pydantic model."""

    def test_empty_project_state(self):
        """Test creating an empty project state."""
        state = ProjectState(
            repo_name="owner/repo",
            generated_at="2025-12-28T12:00:00Z",
        )

        assert state.repo_name == "owner/repo"
        assert state.book_phase == "drafting"  # Default
        assert state.total_chapters == 0
        assert state.chapters_approved == 0
        assert state.open_issues == []
        assert state.open_prs == []

    def test_project_state_with_chapters(self):
        """Test project state with chapter tracking."""
        chapters = [
            ChapterStatus(
                path="chapters/01-intro.md",
                state=ChapterState.APPROVED,
                word_count=2000,
            ),
            ChapterStatus(
                path="chapters/02-main.md",
                state=ChapterState.IN_FEEDBACK,
                word_count=3500,
                active_issues=[42],
            ),
            ChapterStatus(
                path="chapters/03-conclusion.md",
                state=ChapterState.VOID,
                word_count=0,
            ),
        ]

        state = ProjectState(
            repo_name="owner/book",
            generated_at="2025-12-28T12:00:00Z",
            book_phase="revising",
            total_chapters=3,
            chapters_approved=1,
            chapters=chapters,
        )

        assert state.total_chapters == 3
        assert state.chapters_approved == 1
        assert len(state.chapters) == 3

    def test_project_state_summary_empty(self):
        """Test summary generation for empty project."""
        state = ProjectState(
            repo_name="owner/repo",
            generated_at="2025-12-28T12:00:00Z",
        )

        summary = state.get_active_summary()
        assert "drafting" in summary.lower()
        assert "no chapters" in summary.lower()

    def test_project_state_summary_with_progress(self):
        """Test summary generation with project progress."""
        state = ProjectState(
            repo_name="owner/book",
            generated_at="2025-12-28T12:00:00Z",
            book_phase="revising",
            total_chapters=5,
            chapters_approved=2,
            open_issues=[
                WorkItem(
                    number=42,
                    title="Voice memo for chapter 3",
                    item_type=WorkItemType.VOICE_MEMO,
                    state=WorkItemState.AWAITING_AUTHOR,
                    chapter="chapters/03",
                    created_at="2025-12-28T10:00:00Z",
                    updated_at="2025-12-28T11:00:00Z",
                    labels=[],
                    last_actor="editor",
                ),
            ],
            awaiting_author=[42],
        )

        summary = state.get_active_summary()
        assert "2/5" in summary
        assert "revising phase" in summary.lower()
        assert "#42" in summary
        assert "awaiting author" in summary.lower()

    def test_project_state_summary_with_prs(self):
        """Test summary generation with open PRs."""
        state = ProjectState(
            repo_name="owner/book",
            generated_at="2025-12-28T12:00:00Z",
            open_prs=[
                WorkItem(
                    number=15,
                    title="Add chapter 2 content",
                    item_type=WorkItemType.PULL_REQUEST,
                    state=WorkItemState.PR_OPEN,
                    chapter="chapters/02-main.md",
                    created_at="2025-12-27T10:00:00Z",
                    updated_at="2025-12-28T09:00:00Z",
                    labels=[],
                    last_actor="editor",
                ),
            ],
        )

        summary = state.get_active_summary()
        assert "PR #15" in summary
        assert "chapter" in summary.lower()


class TestChapterStateEnum:
    """Test ChapterState enum values."""

    def test_chapter_states(self):
        """Test all chapter states are defined."""
        assert ChapterState.VOID.value == "void"
        assert ChapterState.DRAFTED.value == "drafted"
        assert ChapterState.IN_DISCOVERY.value == "in_discovery"
        assert ChapterState.IN_FEEDBACK.value == "in_feedback"
        assert ChapterState.IN_REVISION.value == "in_revision"
        assert ChapterState.APPROVED.value == "approved"


class TestWorkItemStateEnum:
    """Test WorkItemState enum values."""

    def test_work_item_states(self):
        """Test all work item states are defined."""
        assert WorkItemState.OPEN.value == "open"
        assert WorkItemState.IN_DISCOVERY.value == "in_discovery"
        assert WorkItemState.AWAITING_AUTHOR.value == "awaiting_author"
        assert WorkItemState.AWAITING_EDITOR.value == "awaiting_editor"
        assert WorkItemState.PR_OPEN.value == "pr_open"
        assert WorkItemState.MERGED.value == "merged"
        assert WorkItemState.CLOSED.value == "closed"


class TestWorkItemTypeEnum:
    """Test WorkItemType enum values."""

    def test_work_item_types(self):
        """Test all work item types are defined."""
        assert WorkItemType.VOICE_MEMO.value == "voice_memo"
        assert WorkItemType.FEEDBACK_THREAD.value == "feedback_thread"
        assert WorkItemType.PULL_REQUEST.value == "pull_request"
        assert WorkItemType.QUESTION.value == "question"
