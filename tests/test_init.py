"""Tests for the init script."""

from unittest.mock import MagicMock, patch

import pytest
from github import GithubException

# Import the module under test
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "seeds"))

from init import (  # noqa: E402
    AI_CONTEXT_FILES,
    ISSUE_TEMPLATES,
    LABELS,
    create_ai_context,
    create_issue_templates,
    create_labels,
    init_repository,
)


class TestLabelDefinitions:
    """Test that all required labels are defined."""

    def test_has_core_workflow_labels(self):
        """Core workflow labels exist."""
        names = {lbl["name"] for lbl in LABELS}
        assert "voice_transcription" in names
        assert "ai-reviewed" in names
        assert "pr-created" in names
        assert "awaiting-author" in names
        assert "ai-question" in names
        assert "ai-responded" in names

    def test_has_phase_labels(self):
        """All editorial phase labels exist."""
        names = {lbl["name"] for lbl in LABELS}
        assert "phase:discovery" in names
        assert "phase:feedback" in names
        assert "phase:revision" in names
        assert "phase:polish" in names
        assert "phase:complete" in names
        assert "phase:hold" in names

    def test_has_persona_labels(self):
        """All persona override labels exist."""
        names = {lbl["name"] for lbl in LABELS}
        assert "persona:margot" in names
        assert "persona:sage" in names
        assert "persona:blueprint" in names
        assert "persona:sterling" in names
        assert "persona:the-axe" in names
        assert "persona:cheerleader" in names
        assert "persona:ivory-tower" in names
        assert "persona:bestseller" in names

    def test_all_labels_have_required_fields(self):
        """Each label has name, color, description."""
        for label in LABELS:
            assert "name" in label, f"Label missing name: {label}"
            assert "color" in label, f"Label {label['name']} missing color"
            assert "description" in label, f"Label {label['name']} missing description"

    def test_label_colors_are_valid_hex(self):
        """Label colors are valid 6-char hex codes."""
        for label in LABELS:
            color = label["color"]
            assert len(color) == 6, f"Label {label['name']} has invalid color length"
            assert all(
                c in "0123456789ABCDEFabcdef" for c in color
            ), f"Label {label['name']} has invalid hex color: {color}"

    def test_no_duplicate_labels(self):
        """No duplicate label names."""
        names = [lbl["name"] for lbl in LABELS]
        assert len(names) == len(set(names)), "Duplicate label names found"


class TestIssueTemplateDefinitions:
    """Test issue template definitions."""

    def test_has_required_templates(self):
        """All required templates exist."""
        names = {t["name"] for t in ISSUE_TEMPLATES}
        assert "voice-transcription.md" in names
        assert "ask-the-editor.md" in names
        assert "ai-question.md" in names
        assert "whole-book-review.md" in names
        assert "editorial-hold.md" in names

    def test_templates_have_frontmatter(self):
        """Each template has YAML frontmatter."""
        for template in ISSUE_TEMPLATES:
            content = template["content"]
            assert content.startswith("---"), f"Template {template['name']} missing frontmatter"
            assert content.count("---") >= 2, f"Template {template['name']} has incomplete frontmatter"

    def test_templates_have_labels_in_frontmatter(self):
        """Each template specifies labels in frontmatter."""
        for template in ISSUE_TEMPLATES:
            content = template["content"]
            assert "labels:" in content, f"Template {template['name']} missing labels"


class TestAIContextFiles:
    """Test .ai-context file definitions."""

    def test_has_required_files(self):
        """All required context files exist."""
        assert "config.yaml" in AI_CONTEXT_FILES
        assert "knowledge.jsonl" in AI_CONTEXT_FILES
        assert "terminology.yaml" in AI_CONTEXT_FILES
        assert "themes.yaml" in AI_CONTEXT_FILES
        assert "author-preferences.yaml" in AI_CONTEXT_FILES

    def test_config_yaml_has_required_fields(self):
        """config.yaml template has key settings."""
        config = AI_CONTEXT_FILES["config.yaml"]
        assert "persona:" in config
        assert "phase:" in config
        assert "chapters:" in config


class TestCreateLabels:
    """Test create_labels function."""

    def test_creates_new_labels(self):
        """Creates labels that don't exist."""
        mock_repo = MagicMock()
        mock_repo.get_labels.return_value = []  # No existing labels

        stats = create_labels(mock_repo, dry_run=False, verbose=False)

        assert stats["created"] == len(LABELS)
        assert stats["existing"] == 0
        assert mock_repo.create_label.call_count == len(LABELS)

    def test_skips_existing_labels(self):
        """Skips labels that already exist with correct settings."""
        mock_label = MagicMock()
        mock_label.name = "voice_transcription"
        mock_label.color = "1D76DB"
        mock_label.description = "Voice memo to process"

        mock_repo = MagicMock()
        mock_repo.get_labels.return_value = [mock_label]

        stats = create_labels(mock_repo, dry_run=False, verbose=False)

        assert stats["existing"] == 1
        assert stats["created"] == len(LABELS) - 1

    def test_dry_run_creates_nothing(self):
        """Dry run doesn't create any labels."""
        mock_repo = MagicMock()
        mock_repo.get_labels.return_value = []

        stats = create_labels(mock_repo, dry_run=True, verbose=False)

        assert stats["created"] == len(LABELS)
        mock_repo.create_label.assert_not_called()

    def test_handles_creation_errors(self):
        """Handles errors when creating labels."""
        mock_repo = MagicMock()
        mock_repo.get_labels.return_value = []
        mock_repo.create_label.side_effect = GithubException(
            status=422, data={"message": "Validation Failed"}
        )

        stats = create_labels(mock_repo, dry_run=False, verbose=False)

        assert stats["failed"] == len(LABELS)
        assert stats["created"] == 0


class TestCreateIssueTemplates:
    """Test create_issue_templates function."""

    def test_creates_new_templates(self):
        """Creates templates that don't exist."""
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = GithubException(status=404, data={})

        stats = create_issue_templates(mock_repo, dry_run=False, verbose=False)

        assert stats["created"] == len(ISSUE_TEMPLATES)
        assert mock_repo.create_file.call_count == len(ISSUE_TEMPLATES)

    def test_skips_existing_templates(self):
        """Skips templates that already exist."""
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = MagicMock()  # File exists

        stats = create_issue_templates(mock_repo, dry_run=False, verbose=False)

        assert stats["existing"] == len(ISSUE_TEMPLATES)
        assert stats["created"] == 0
        mock_repo.create_file.assert_not_called()

    def test_dry_run_creates_nothing(self):
        """Dry run doesn't create any templates."""
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = GithubException(status=404, data={})

        stats = create_issue_templates(mock_repo, dry_run=True, verbose=False)

        assert stats["created"] == len(ISSUE_TEMPLATES)
        mock_repo.create_file.assert_not_called()


class TestCreateAIContext:
    """Test create_ai_context function."""

    def test_creates_new_files(self):
        """Creates .ai-context files that don't exist."""
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = GithubException(status=404, data={})

        stats = create_ai_context(mock_repo, dry_run=False, verbose=False)

        assert stats["created"] == len(AI_CONTEXT_FILES)
        assert mock_repo.create_file.call_count == len(AI_CONTEXT_FILES)

    def test_skips_existing_files(self):
        """Skips files that already exist."""
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = MagicMock()  # File exists

        stats = create_ai_context(mock_repo, dry_run=False, verbose=False)

        assert stats["existing"] == len(AI_CONTEXT_FILES)
        assert stats["created"] == 0

    def test_dry_run_creates_nothing(self):
        """Dry run doesn't create any files."""
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = GithubException(status=404, data={})

        stats = create_ai_context(mock_repo, dry_run=True, verbose=False)

        assert stats["created"] == len(AI_CONTEXT_FILES)
        mock_repo.create_file.assert_not_called()


class TestInitRepository:
    """Test the main init_repository function."""

    @patch("init.get_github_client")
    def test_initializes_all_by_default(self, mock_get_client):
        """Initializes labels, templates, and context by default."""
        mock_repo = MagicMock()
        mock_repo.get_labels.return_value = []
        mock_repo.get_contents.side_effect = GithubException(status=404, data={})

        mock_client = MagicMock()
        mock_client.get_repo.return_value = mock_repo
        mock_get_client.return_value = mock_client

        results = init_repository(
            "owner/repo",
            do_labels=True,
            do_templates=True,
            do_context=True,
            dry_run=True,
            verbose=False,
        )

        assert "labels" in results
        assert "templates" in results
        assert "context" in results

    @patch("init.get_github_client")
    def test_can_initialize_labels_only(self, mock_get_client):
        """Can initialize just labels."""
        mock_repo = MagicMock()
        mock_repo.get_labels.return_value = []

        mock_client = MagicMock()
        mock_client.get_repo.return_value = mock_repo
        mock_get_client.return_value = mock_client

        results = init_repository(
            "owner/repo",
            do_labels=True,
            do_templates=False,
            do_context=False,
            dry_run=True,
            verbose=False,
        )

        assert "labels" in results
        assert "templates" not in results
        assert "context" not in results


class TestLabelConsistencyWithCodebase:
    """Verify labels match what the codebase expects."""

    def test_phase_labels_match_phases_module(self):
        """Phase labels match PHASE_LABELS in phases.py."""
        # Import the actual phase labels from the codebase
        sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))
        from utils.phases import PHASE_LABELS as CODE_PHASE_LABELS

        init_phase_labels = {
            lbl["name"] for lbl in LABELS if lbl["name"].startswith("phase:")
        }
        code_phase_labels = {v["name"] for v in CODE_PHASE_LABELS.values()}

        assert init_phase_labels == code_phase_labels, (
            f"Mismatch: init has {init_phase_labels}, code expects {code_phase_labels}"
        )

    def test_persona_labels_match_persona_module(self):
        """Persona labels match BUILTIN_PERSONAS in persona.py."""
        sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))
        from utils.persona import BUILTIN_PERSONAS

        init_persona_labels = {
            lbl["name"].replace("persona:", "")
            for lbl in LABELS
            if lbl["name"].startswith("persona:")
        }

        assert init_persona_labels == BUILTIN_PERSONAS, (
            f"Mismatch: init has {init_persona_labels}, code expects {BUILTIN_PERSONAS}"
        )
