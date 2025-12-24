"""Tests for process_transcription script."""

import os
from unittest.mock import MagicMock, patch

import pytest


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
