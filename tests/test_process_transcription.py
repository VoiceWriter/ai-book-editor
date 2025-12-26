"""Tests for process_transcription script."""

import os
from unittest.mock import MagicMock, patch

import pytest

from scripts.utils.phases import BookPhase


class TestSetOutput:
    """Tests for set_output function."""

    def test_writes_simple_output(self, tmp_path):
        """Should write simple key=value output."""
        from scripts.process_transcription import set_output

        output_file = tmp_path / "github_output"
        output_file.touch()

        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            set_output("success", "true")

        content = output_file.read_text()
        assert "success=true" in content

    def test_writes_multiline_output(self, tmp_path):
        """Should handle multiline values with heredoc."""
        from scripts.process_transcription import set_output

        output_file = tmp_path / "github_output"
        output_file.touch()

        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            set_output("comment", "Line 1\nLine 2\nLine 3")

        content = output_file.read_text()
        assert "comment<<" in content
        assert "Line 1\nLine 2\nLine 3" in content

    def test_noop_without_github_output(self):
        """Should do nothing when GITHUB_OUTPUT not set."""
        from scripts.process_transcription import set_output

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_OUTPUT", None)
            # Should not raise
            set_output("key", "value")


class TestProcessTranscription:
    """Integration tests for the main processing flow."""

    def test_requires_issue_number(self):
        """Should exit with error when ISSUE_NUMBER not set."""
        from scripts.process_transcription import main

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ISSUE_NUMBER", None)
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_handles_empty_transcript(self, mock_repo, tmp_path):
        """Should handle empty transcript gracefully."""
        from scripts.process_transcription import main

        # Create issue with empty body
        empty_issue = MagicMock()
        empty_issue.number = 1
        empty_issue.body = ""
        mock_repo.get_issue.return_value = empty_issue

        output_file = tmp_path / "github_output"
        output_file.touch()

        with patch.dict(
            os.environ,
            {
                "ISSUE_NUMBER": "1",
                "GITHUB_TOKEN": "test-token",
                "GITHUB_REPOSITORY": "test/repo",
                "GITHUB_OUTPUT": str(output_file),
            },
        ):
            with patch("scripts.process_transcription.get_github_client"):
                with patch("scripts.process_transcription.get_repo", return_value=mock_repo):
                    with patch("scripts.process_transcription.get_issue", return_value=empty_issue):
                        # Should create output directory in current dir
                        with patch("scripts.process_transcription.Path") as mock_path:
                            mock_path_instance = MagicMock()
                            mock_path.return_value = mock_path_instance
                            mock_path_instance.mkdir = MagicMock()
                            mock_path_instance.write_text = MagicMock()

                            with pytest.raises(SystemExit) as exc_info:
                                main()
                            assert exc_info.value.code == 1

    def test_successful_processing(self, mock_repo, sample_issue, mock_llm_response, tmp_path):
        """Should process transcript and write analysis output."""
        from scripts.process_transcription import main

        output_file = tmp_path / "github_output"
        output_file.touch()

        # Change to tmp_path so output/ is created there
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            with patch.dict(
                os.environ,
                {
                    "ISSUE_NUMBER": "1",
                    "GITHUB_TOKEN": "test-token",
                    "GITHUB_REPOSITORY": "test/repo",
                    "GITHUB_OUTPUT": str(output_file),
                },
            ):
                with patch("scripts.process_transcription.get_github_client"):
                    with patch("scripts.process_transcription.get_repo", return_value=mock_repo):
                        with patch(
                            "scripts.process_transcription.get_issue", return_value=sample_issue
                        ):
                            with patch(
                                "scripts.process_transcription.load_editorial_context"
                            ) as mock_context:
                                mock_context.return_value = {
                                    "persona": "Test persona",
                                    "guidelines": "Test guidelines",
                                    "glossary": None,
                                    "knowledge_formatted": None,
                                    "chapters": [],
                                }
                                with patch(
                                    "scripts.process_transcription.call_editorial"
                                ) as mock_call:
                                    mock_call.return_value = mock_llm_response

                                    main()

                                    # Check output file was created
                                    analysis_file = tmp_path / "output" / "analysis-comment.md"
                                    assert analysis_file.exists()

                                    # Check content
                                    content = analysis_file.read_text()
                                    assert "AI Editorial Analysis" in content
                                    assert mock_llm_response.content in content
        finally:
            os.chdir(original_cwd)


class TestAnalysisOutput:
    """Tests for the analysis output format."""

    def test_output_includes_next_steps(self, mock_llm_response, tmp_path):
        """Output should include next steps instructions."""
        # Create a sample output
        output = f"""## AI Editorial Analysis

{mock_llm_response}

---

### Next Steps

**To integrate this content:**
1. Reply with any feedback or answers to my questions above
2. Specify placement: `@margot-ai-editor place in chapter-name.md`
3. When ready: `@margot-ai-editor create PR`
"""
        assert "Next Steps" in output
        assert "@margot-ai-editor place in" in output
        assert "@margot-ai-editor create PR" in output


class TestBuildNewProjectWelcome:
    """Tests for build_new_project_welcome function."""

    def test_includes_persona_name(self):
        """Should include the persona name in welcome."""
        from scripts.process_transcription import build_new_project_welcome

        result = build_new_project_welcome("Margot")

        assert "I'm Margot" in result
        assert "Let's get to know your project" in result

    def test_includes_discovery_questions(self):
        """Should include key discovery questions."""
        from scripts.process_transcription import build_new_project_welcome

        result = build_new_project_welcome("Test Editor")

        assert "What's this book about?" in result
        assert "Who are you writing this for?" in result
        assert "What tone are you going for?" in result
        assert "What phase are you in?" in result


class TestBuildPhaseAwareTask:
    """Tests for build_phase_aware_task function."""

    def test_new_phase_is_encouraging(self):
        """NEW phase should have encouraging focus."""
        from scripts.process_transcription import build_phase_aware_task

        result = build_phase_aware_task(BookPhase.NEW, None)

        assert "PHASE: NEW PROJECT" in result
        assert "Celebrating" in result or "celebrating" in result.lower()
        assert "nitpick" in result.lower()

    def test_drafting_phase_is_balanced(self):
        """DRAFTING phase should balance encouragement and feedback."""
        from scripts.process_transcription import build_phase_aware_task

        result = build_phase_aware_task(BookPhase.DRAFTING, None)

        assert "PHASE: DRAFTING" in result
        assert "Balance" in result or "balance" in result.lower()

    def test_revising_phase_is_rigorous(self):
        """REVISING phase should focus on structural feedback."""
        from scripts.process_transcription import build_phase_aware_task

        result = build_phase_aware_task(BookPhase.REVISING, None)

        assert "PHASE: REVISING" in result
        assert "rigorous" in result.lower()
        assert "structural" in result.lower()

    def test_polishing_phase_is_precise(self):
        """POLISHING phase should focus on line-level editing."""
        from scripts.process_transcription import build_phase_aware_task

        result = build_phase_aware_task(BookPhase.POLISHING, None)

        assert "PHASE: POLISHING" in result
        assert "Line-level" in result or "line-level" in result.lower()

    def test_includes_book_context_when_provided(self):
        """Should include book context when provided."""
        from scripts.process_transcription import build_phase_aware_task

        book_context = "This is a book about AI and productivity."
        result = build_phase_aware_task(BookPhase.DRAFTING, book_context)

        assert "PHASE: DRAFTING" in result
        assert book_context in result

    def test_no_phase_returns_empty_string(self):
        """Should return empty string when phase is None."""
        from scripts.process_transcription import build_phase_aware_task

        result = build_phase_aware_task(None, None)

        assert result == ""


class TestBuildDiscoveryAwareTask:
    """Tests for build_discovery_aware_task function."""

    def test_without_discovery_returns_base_task(self):
        """Should return base task when no discovery context."""
        from scripts.process_transcription import build_discovery_aware_task

        result = build_discovery_aware_task(
            discovery_context=None,
            persona_id="margot",
            book_phase=BookPhase.NEW,
            book_context=None,
        )

        assert "Cleaned Transcript" in result
        assert "Content Analysis" in result
        assert "Suggested Placement" in result
        assert "Editorial Notes" in result
        assert "Ready for PR?" in result

    def test_with_discovery_includes_questions(self):
        """Should include questions asked during discovery."""
        from scripts.process_transcription import build_discovery_aware_task

        discovery_context = {
            "questions_asked": ["What's this book about?", "Who is your reader?"],
            "author_responses": ["It's about AI writing workflows."],
        }

        result = build_discovery_aware_task(
            discovery_context=discovery_context,
            persona_id="margot",
            book_phase=None,
            book_context=None,
        )

        assert "What You Learned in Discovery" in result
        assert "What's this book about?" in result
        assert "Who is your reader?" in result

    def test_with_discovery_includes_emotional_state(self):
        """Should include emotional state guidance when detected."""
        from scripts.process_transcription import build_discovery_aware_task

        discovery_context = {
            "questions_asked": [],
            "author_responses": [],
            "emotional_state": "vulnerable",
        }

        result = build_discovery_aware_task(
            discovery_context=discovery_context,
            persona_id="margot",
            book_phase=None,
            book_context=None,
        )

        assert "emotional state" in result.lower()
        assert "vulnerable" in result
        assert "encouragement" in result.lower()

    def test_with_discovery_includes_knowledge_items(self):
        """Should include extracted knowledge items."""
        from scripts.process_transcription import build_discovery_aware_task

        discovery_context = {
            "questions_asked": [],
            "author_responses": [],
            "knowledge_items": [
                {"type": "preference", "content": "I like short chapters"},
                {"type": "goal", "content": "Help readers save time"},
            ],
        }

        result = build_discovery_aware_task(
            discovery_context=discovery_context,
            persona_id="margot",
            book_phase=None,
            book_context=None,
        )

        assert "Key insights from discovery" in result
        assert "preference" in result
        assert "goal" in result

    def test_combines_phase_and_discovery(self):
        """Should combine phase guidance with discovery context."""
        from scripts.process_transcription import build_discovery_aware_task

        discovery_context = {
            "questions_asked": ["Question 1"],
            "author_responses": ["Response 1"],
        }

        result = build_discovery_aware_task(
            discovery_context=discovery_context,
            persona_id="margot",
            book_phase=BookPhase.DRAFTING,
            book_context=None,
        )

        # Should have both phase and discovery content
        assert "PHASE: DRAFTING" in result
        assert "What You Learned in Discovery" in result
