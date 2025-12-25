"""Tests for knowledge_base utilities."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from scripts.utils.knowledge_base import (
    BookConfig,
    ChapterConfig,
    format_book_context_for_prompt,
    get_book_progress,
    load_book_config,
)
from scripts.utils.phases import BookPhase


class TestLoadKnowledgeBase:
    """Tests for load_knowledge_base function."""

    def test_loads_all_knowledge_files(self, mock_repo):
        """Should load all knowledge base files."""
        from scripts.utils.knowledge_base import load_knowledge_base

        result = load_knowledge_base(mock_repo)

        assert "qa_pairs" in result
        assert "terminology" in result
        assert "themes" in result
        assert "preferences" in result

    def test_handles_missing_files(self):
        """Should handle missing knowledge base files gracefully."""
        from scripts.utils.knowledge_base import load_knowledge_base

        repo = MagicMock()
        repo.get_contents.side_effect = Exception("Not found")

        result = load_knowledge_base(repo)

        assert result["qa_pairs"] == []
        assert result["terminology"] == {}
        assert result["themes"] == []
        assert result["preferences"] == {}


class TestFormatKnowledgeForPrompt:
    """Tests for format_knowledge_for_prompt function."""

    def test_formats_complete_knowledge(self, sample_knowledge_base):
        """Should format all knowledge sections."""
        from scripts.utils.knowledge_base import format_knowledge_for_prompt

        result = format_knowledge_for_prompt(sample_knowledge_base)

        assert "## Known Context" in result
        assert "Voice-to-text workflows" in result
        assert "## Terminology Preferences" in result
        assert "## Central Themes" in result
        assert "productivity" in result
        assert "## Author Preferences" in result
        assert "casual" in result

    def test_handles_empty_knowledge(self):
        """Should return None for empty knowledge base."""
        from scripts.utils.knowledge_base import format_knowledge_for_prompt

        empty_kb = {"qa_pairs": [], "terminology": {}, "themes": [], "preferences": {}}

        result = format_knowledge_for_prompt(empty_kb)
        assert result is None

    def test_partial_knowledge_base(self):
        """Should format only populated sections."""
        from scripts.utils.knowledge_base import format_knowledge_for_prompt

        partial_kb = {
            "qa_pairs": [],
            "terminology": {"voice memo": "voice memo"},
            "themes": ["writing"],
            "preferences": {},
        }

        result = format_knowledge_for_prompt(partial_kb)

        assert "## Known Context" not in result
        assert "## Terminology Preferences" in result
        assert "## Central Themes" in result
        assert "## Author Preferences" not in result


class TestLoadEditorialContext:
    """Tests for load_editorial_context function."""

    def test_loads_all_context(self, mock_repo):
        """Should load all editorial context files."""
        from scripts.utils.knowledge_base import load_editorial_context

        result = load_editorial_context(mock_repo)

        assert "persona" in result
        assert "guidelines" in result
        assert "glossary" in result
        assert "knowledge" in result
        assert "knowledge_formatted" in result
        assert "chapters" in result

    def test_provides_defaults_for_missing_files(self):
        """Should provide default text when files missing."""
        from scripts.utils.knowledge_base import load_editorial_context

        repo = MagicMock()
        repo.get_contents.side_effect = Exception("Not found")

        result = load_editorial_context(repo)

        # Default persona is now provided (not "No persona defined")
        assert "Editor Persona" in result["persona"]
        assert "No guidelines defined" in result["guidelines"]

    def test_lists_chapter_files(self, mock_repo):
        """Should list chapter files."""
        from scripts.utils.knowledge_base import load_editorial_context

        result = load_editorial_context(mock_repo)

        assert "chapter-01-intro.md" in result["chapters"]
        assert "chapter-02-capture.md" in result["chapters"]


class TestChapterConfig:
    """Tests for ChapterConfig Pydantic model."""

    def test_valid_chapter_config(self):
        """Should create valid chapter config."""
        chapter = ChapterConfig(name="Introduction", file="chapter-01.md", status="drafted")
        assert chapter.name == "Introduction"
        assert chapter.file == "chapter-01.md"
        assert chapter.status == "drafted"

    def test_chapter_config_defaults(self):
        """Should use default values for optional fields."""
        chapter = ChapterConfig(name="Outro")
        assert chapter.name == "Outro"
        assert chapter.file is None
        assert chapter.status == "planned"
        assert chapter.notes is None

    def test_chapter_config_with_notes(self):
        """Should accept notes field."""
        chapter = ChapterConfig(
            name="The Hook", file="chapter-01.md", status="in_progress", notes="Need more examples"
        )
        assert chapter.notes == "Need more examples"


class TestBookConfig:
    """Tests for BookConfig Pydantic model."""

    def test_valid_book_config(self):
        """Should create valid book config with all fields."""
        config = BookConfig(
            title="My Book",
            author="Jane Doe",
            phase=BookPhase.DRAFTING,
            target_audience="Technical writers",
            core_themes=["productivity", "writing"],
            author_goals=["Inspire readers", "Teach workflows"],
        )
        assert config.title == "My Book"
        assert config.author == "Jane Doe"
        assert config.phase == BookPhase.DRAFTING
        assert len(config.core_themes) == 2

    def test_book_config_defaults(self):
        """Should use defaults for minimal config."""
        config = BookConfig()
        assert config.title == ""
        assert config.author == ""
        assert config.phase == BookPhase.NEW
        assert config.core_themes == []
        assert config.chapters == []

    def test_book_config_with_chapters(self):
        """Should accept chapter list."""
        config = BookConfig(
            title="Test Book",
            chapters=[
                ChapterConfig(name="Intro", status="drafted"),
                ChapterConfig(name="Body", status="planned"),
            ],
        )
        assert len(config.chapters) == 2
        assert config.chapters[0].name == "Intro"
        assert config.chapters[1].name == "Body"

    def test_book_config_strict_validation(self):
        """Should reject invalid types due to strict mode."""
        with pytest.raises(ValidationError):
            BookConfig(title=123)  # title must be str


class TestLoadBookConfig:
    """Tests for load_book_config function."""

    def test_loads_valid_config(self):
        """Should load and parse valid book.yaml."""
        repo = MagicMock()
        yaml_content = """
title: My Awesome Book
author: John Smith
phase: drafting
target_audience: Developers
core_themes:
  - AI
  - Productivity
chapters:
  - name: Introduction
    file: chapter-01.md
    status: drafted
"""
        content = MagicMock()
        content.decoded_content = yaml_content.encode("utf-8")
        repo.get_contents.return_value = content

        result = load_book_config(repo)

        assert result is not None
        assert result.title == "My Awesome Book"
        assert result.author == "John Smith"
        assert result.phase == BookPhase.DRAFTING
        assert len(result.chapters) == 1

    def test_returns_none_for_missing_config(self):
        """Should return None when book.yaml doesn't exist."""
        repo = MagicMock()
        repo.get_contents.side_effect = Exception("Not found")

        result = load_book_config(repo)

        assert result is None

    def test_returns_none_for_empty_config(self):
        """Should return None for empty YAML file."""
        repo = MagicMock()
        content = MagicMock()
        content.decoded_content = b""
        repo.get_contents.return_value = content

        result = load_book_config(repo)

        assert result is None

    def test_handles_invalid_yaml(self):
        """Should return None and print warning for invalid YAML."""
        repo = MagicMock()
        content = MagicMock()
        content.decoded_content = b"{{invalid yaml"
        repo.get_contents.return_value = content

        result = load_book_config(repo)

        assert result is None


class TestGetBookProgress:
    """Tests for get_book_progress function."""

    def test_progress_with_no_config(self):
        """Should return basic progress when no config exists."""
        chapters_on_disk = ["chapter-01.md", "chapter-02.md"]

        result = get_book_progress(None, chapters_on_disk)

        assert result["has_config"] is False
        assert result["chapters_drafted"] == 2
        assert result["chapters_planned"] == 0

    def test_progress_new_phase(self):
        """Should calculate completion based on planned chapters in NEW phase."""
        config = BookConfig(
            phase=BookPhase.NEW,
            target_chapters=10,
            chapters=[
                ChapterConfig(name="Ch1", status="planned"),
                ChapterConfig(name="Ch2", status="planned"),
                ChapterConfig(name="Ch3", status="planned"),
            ],
        )

        result = get_book_progress(config, [])

        assert result["has_config"] is True
        assert result["chapters_planned"] == 3
        assert result["phase"] == "new"
        assert result["completion_pct"] == 30.0  # 3/10 * 100

    def test_progress_drafting_phase(self):
        """Should calculate completion based on drafted chapters in DRAFTING phase."""
        config = BookConfig(
            phase=BookPhase.DRAFTING,
            chapters=[
                ChapterConfig(name="Ch1", status="drafted"),
                ChapterConfig(name="Ch2", status="drafted"),
                ChapterConfig(name="Ch3", status="planned"),
                ChapterConfig(name="Ch4", status="planned"),
            ],
        )

        result = get_book_progress(config, ["ch1.md", "ch2.md"])

        assert result["chapters_drafted"] == 2
        assert result["completion_pct"] == 50.0  # 2/4 * 100

    def test_progress_revising_phase(self):
        """Should calculate completion based on revised chapters in REVISING phase."""
        config = BookConfig(
            phase=BookPhase.REVISING,
            chapters=[
                ChapterConfig(name="Ch1", status="revised"),
                ChapterConfig(name="Ch2", status="drafted"),
                ChapterConfig(name="Ch3", status="drafted"),
            ],
        )

        result = get_book_progress(config, [])

        assert result["chapters_revised"] == 1
        assert result["completion_pct"] == pytest.approx(33.3, rel=0.1)

    def test_progress_polishing_phase(self):
        """Should calculate completion based on polished chapters in POLISHING phase."""
        config = BookConfig(
            phase=BookPhase.POLISHING,
            chapters=[
                ChapterConfig(name="Ch1", status="polished"),
                ChapterConfig(name="Ch2", status="polished"),
                ChapterConfig(name="Ch3", status="revised"),
            ],
        )

        result = get_book_progress(config, [])

        assert result["chapters_polished"] == 2
        assert result["completion_pct"] == pytest.approx(66.7, rel=0.1)


class TestFormatBookContextForPrompt:
    """Tests for format_book_context_for_prompt function."""

    def test_returns_none_for_no_config(self):
        """Should return None when no config exists."""
        result = format_book_context_for_prompt(None)
        assert result is None

    def test_includes_title_and_author(self):
        """Should include title and author in output."""
        config = BookConfig(title="Test Book", author="Test Author")

        result = format_book_context_for_prompt(config)

        assert "**Title:** Test Book" in result
        assert "**Author:** Test Author" in result

    def test_includes_phase_guidance(self):
        """Should include phase-specific guidance."""
        config = BookConfig(title="Test", phase=BookPhase.REVISING)

        result = format_book_context_for_prompt(config)

        assert "Book Phase:" in result

    def test_includes_audience_and_themes(self):
        """Should include audience and themes when present."""
        config = BookConfig(
            title="Test",
            target_audience="Developers who want to learn",
            core_themes=["AI", "Productivity"],
        )

        result = format_book_context_for_prompt(config)

        assert "**Target Audience:**" in result
        assert "Developers who want to learn" in result
        assert "**Core Themes:**" in result
        assert "- AI" in result
        assert "- Productivity" in result

    def test_includes_author_goals(self):
        """Should include author goals when present."""
        config = BookConfig(
            title="Test",
            author_goals=["Inspire action", "Teach concepts"],
        )

        result = format_book_context_for_prompt(config)

        assert "**Author's Goals:**" in result
        assert "- Inspire action" in result

    def test_includes_editorial_notes(self):
        """Should include editorial notes when present."""
        config = BookConfig(
            title="Test",
            editorial_notes="Focus on practical examples",
        )

        result = format_book_context_for_prompt(config)

        assert "**Author's Editorial Notes:**" in result
        assert "Focus on practical examples" in result
