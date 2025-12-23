"""Tests for github_client utilities."""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestGetGithubClient:
    """Tests for get_github_client function."""

    def test_requires_token(self):
        """Should raise error when GITHUB_TOKEN not set."""
        from scripts.utils.github_client import get_github_client

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_TOKEN", None)
            with pytest.raises(ValueError, match="GITHUB_TOKEN"):
                get_github_client()

    def test_creates_client_with_token(self):
        """Should create Github client with token."""
        from scripts.utils.github_client import get_github_client

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            with patch("scripts.utils.github_client.Github") as MockGithub:
                get_github_client()
                MockGithub.assert_called_once_with("test-token")


class TestGetRepo:
    """Tests for get_repo function."""

    def test_uses_provided_repo_name(self, mock_github_client):
        """Should use explicitly provided repo name."""
        from scripts.utils.github_client import get_repo

        get_repo(mock_github_client, "owner/custom-repo")
        mock_github_client.get_repo.assert_called_once_with("owner/custom-repo")

    def test_uses_env_repo_name(self, mock_github_client):
        """Should use GITHUB_REPOSITORY env var as fallback."""
        from scripts.utils.github_client import get_repo

        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/env-repo"}):
            get_repo(mock_github_client)
            mock_github_client.get_repo.assert_called_once_with("owner/env-repo")

    def test_raises_without_repo_name(self, mock_github_client):
        """Should raise error when no repo name available."""
        from scripts.utils.github_client import get_repo

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_REPOSITORY", None)
            with pytest.raises(ValueError, match="Repository name"):
                get_repo(mock_github_client)


class TestGetIssue:
    """Tests for get_issue function."""

    def test_gets_issue_by_number(self, mock_repo):
        """Should retrieve issue by number."""
        from scripts.utils.github_client import get_issue

        _ = get_issue(mock_repo, 1)
        mock_repo.get_issue.assert_called_once_with(1)


class TestReadFileContent:
    """Tests for read_file_content function."""

    def test_reads_existing_file(self, mock_repo):
        """Should read and decode file content."""
        from scripts.utils.github_client import read_file_content

        result = read_file_content(mock_repo, "EDITOR_PERSONA.md")
        assert result == "You are a supportive editor."

    def test_returns_none_for_missing_file(self):
        """Should return None when file doesn't exist."""
        from scripts.utils.github_client import read_file_content

        repo = MagicMock()
        repo.get_contents.side_effect = Exception("Not found")

        result = read_file_content(repo, "nonexistent.md")
        assert result is None

    def test_supports_ref_parameter(self, mock_repo):
        """Should pass ref parameter for specific branch/commit."""
        from scripts.utils.github_client import read_file_content

        read_file_content(mock_repo, "file.md", ref="feature-branch")
        mock_repo.get_contents.assert_called_with("file.md", ref="feature-branch")


class TestListFilesInDirectory:
    """Tests for list_files_in_directory function."""

    def test_lists_files(self, mock_repo):
        """Should list files in directory."""
        from scripts.utils.github_client import list_files_in_directory

        result = list_files_in_directory(mock_repo, "chapters")
        assert "chapter-01-intro.md" in result
        assert "chapter-02-capture.md" in result

    def test_returns_empty_for_missing_directory(self):
        """Should return empty list for missing directory."""
        from scripts.utils.github_client import list_files_in_directory

        repo = MagicMock()
        repo.get_contents.side_effect = Exception("Not found")

        result = list_files_in_directory(repo, "nonexistent")
        assert result == []


class TestFormatCommitMessage:
    """Tests for format_commit_message function."""

    def test_formats_basic_message(self):
        """Should format basic commit message."""
        from scripts.utils.github_client import format_commit_message

        result = format_commit_message(
            type_="content", scope="chapter-01", description="Add opening section"
        )

        assert result.startswith("content(chapter-01): Add opening section")
        assert "Reviewed-by: ai-editor" in result
        assert "Editorial-type: addition" in result

    def test_includes_source_issue(self):
        """Should include source issue reference."""
        from scripts.utils.github_client import format_commit_message

        result = format_commit_message(
            type_="content", scope="chapter-01", description="Add content", source_issue=42
        )

        assert "Source: #42" in result

    def test_includes_body(self):
        """Should include body text."""
        from scripts.utils.github_client import format_commit_message

        result = format_commit_message(
            type_="fix",
            scope="typo",
            description="Fix spelling",
            body="Fixed 'recieve' -> 'receive' throughout",
        )

        assert "Fixed 'recieve' -> 'receive'" in result
