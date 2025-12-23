"""Tests for knowledge_base utilities."""

from unittest.mock import MagicMock


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

        assert "No persona defined" in result["persona"]
        assert "No guidelines defined" in result["guidelines"]

    def test_lists_chapter_files(self, mock_repo):
        """Should list chapter files."""
        from scripts.utils.knowledge_base import load_editorial_context

        result = load_editorial_context(mock_repo)

        assert "chapter-01-intro.md" in result["chapters"]
        assert "chapter-02-capture.md" in result["chapters"]
