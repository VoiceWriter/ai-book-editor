"""Tests for llm_client utilities."""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestGetModel:
    """Tests for get_model function."""

    def test_default_model(self):
        """Should return default model when no env var set."""
        from scripts.utils.llm_client import DEFAULT_MODEL, get_model

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MODEL", None)
            result = get_model()
            assert result == DEFAULT_MODEL

    def test_custom_reasoning_model_from_env(self):
        """Should return reasoning model from environment variable."""
        from scripts.utils.llm_client import get_model

        with patch.dict(os.environ, {"MODEL": "o3"}):
            result = get_model()
            assert result == "o3"

    def test_non_reasoning_model_raises_error(self):
        """Should raise error for non-reasoning models."""
        from scripts.utils.llm_client import get_model

        with patch.dict(os.environ, {"MODEL": "gpt-4o"}):
            with pytest.raises(ValueError, match="does not support reasoning"):
                get_model()

    def test_model_alias_resolution(self):
        """Should resolve model aliases."""
        from scripts.utils.llm_client import MODEL_ALIASES, get_model

        with patch.dict(os.environ, {"MODEL": "cheap"}):
            result = get_model()
            assert result == MODEL_ALIASES["cheap"]

        with patch.dict(os.environ, {"MODEL": "claude"}):
            result = get_model()
            assert result == MODEL_ALIASES["claude"]


class TestModelCapabilities:
    """Tests for model capability registry."""

    def test_get_capabilities_for_known_model(self):
        """Should return capabilities for registered models."""
        from scripts.utils.llm_client import get_model_capabilities

        caps = get_model_capabilities("claude-sonnet-4-5-20250929")
        assert caps is not None
        assert caps.reasoning is True
        assert caps.provider == "anthropic"

    def test_get_capabilities_for_alias(self):
        """Should resolve alias and return capabilities."""
        from scripts.utils.llm_client import get_model_capabilities

        caps = get_model_capabilities("claude")
        assert caps is not None
        assert caps.reasoning is True

    def test_get_capabilities_for_unknown_model(self):
        """Should return None for unknown models."""
        from scripts.utils.llm_client import get_model_capabilities

        caps = get_model_capabilities("unknown-model-xyz")
        assert caps is None


class TestSupportsReasoning:
    """Tests for supports_reasoning function."""

    def test_registered_model_supports_reasoning(self):
        """Registered models should support reasoning."""
        from scripts.utils.llm_client import supports_reasoning

        assert supports_reasoning("claude-sonnet-4-5-20250929") is True
        assert supports_reasoning("o3") is True
        assert supports_reasoning("deepseek-reasoner") is True

    def test_alias_supports_reasoning(self):
        """Aliases should resolve and support reasoning."""
        from scripts.utils.llm_client import supports_reasoning

        assert supports_reasoning("claude") is True
        assert supports_reasoning("cheap") is True


class TestBuildEditorialPrompt:
    """Tests for build_editorial_prompt function."""

    def test_builds_complete_prompt(self):
        """Should build prompt with all sections."""
        from scripts.utils.llm_client import build_editorial_prompt

        result = build_editorial_prompt(
            persona="You are a helpful editor.",
            guidelines="Follow these rules.",
            glossary="Term definitions.",
            knowledge_base="Q&A pairs here.",
            chapter_list=["chapter-01.md", "chapter-02.md"],
            task="Analyze this content.",
            content="Sample voice memo.",
        )

        assert "# Your Persona" in result
        assert "You are a helpful editor." in result
        assert "# Editorial Guidelines" in result
        assert "# Glossary" in result
        assert "# Knowledge Base" in result
        assert "# Existing Chapters" in result
        assert "chapter-01.md, chapter-02.md" in result
        assert "# Current Task" in result
        assert "# Content to Process" in result
        assert "# Important Reminders" in result

    def test_omits_empty_sections(self):
        """Should omit sections when values are None/empty."""
        from scripts.utils.llm_client import build_editorial_prompt

        result = build_editorial_prompt(
            persona="Editor persona",
            guidelines="Guidelines",
            glossary=None,
            knowledge_base=None,
            chapter_list=[],
            task="Task here",
            content="Content here",
        )

        assert "# Glossary" not in result
        assert "# Knowledge Base" not in result
        assert "# Existing Chapters" not in result


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_has_reasoning_with_reasoning_content(self):
        """Should detect reasoning content."""
        from scripts.utils.llm_client import LLMResponse

        response = LLMResponse(
            content="Analysis here",
            reasoning="I thought about this carefully...",
        )
        assert response.has_reasoning() is True

    def test_has_reasoning_without_reasoning(self):
        """Should return False when no reasoning."""
        from scripts.utils.llm_client import LLMResponse

        response = LLMResponse(content="Just the answer")
        assert response.has_reasoning() is False

    def test_format_editorial_explanation(self):
        """Should format reasoning as collapsible section."""
        from scripts.utils.llm_client import LLMResponse

        response = LLMResponse(
            content="Analysis", reasoning="Step 1: Read carefully. Step 2: Analyze."
        )
        formatted = response.format_editorial_explanation()

        assert "<details>" in formatted
        assert "Editorial Reasoning" in formatted
        assert "Step 1" in formatted
