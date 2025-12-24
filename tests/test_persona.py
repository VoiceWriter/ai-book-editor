"""Tests for persona utilities."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))

from utils.persona import (Persona, PersonaRules, PersonaTraits,  # noqa: E402
                           PersonaVoice, format_persona_for_prompt,
                           get_default_persona, get_personas_dir,
                           list_available_personas, load_persona,
                           load_persona_config)


class TestPersonaTraits:
    """Tests for PersonaTraits model."""

    def test_valid_traits(self):
        """Test valid trait values."""
        traits = PersonaTraits(
            directness=5,
            ruthlessness=7,
            voice_protection=9,
            structure_focus=3,
            market_awareness=6,
            praise_frequency=4,
            formality=2,
            challenge_level=8,
            specificity=7,
        )
        assert traits.directness == 5
        assert traits.ruthlessness == 7

    def test_invalid_trait_value_too_high(self):
        """Test that trait values above 10 fail."""
        with pytest.raises(ValueError):
            PersonaTraits(
                directness=11,  # Invalid
                ruthlessness=5,
                voice_protection=5,
                structure_focus=5,
                market_awareness=5,
                praise_frequency=5,
                formality=5,
                challenge_level=5,
                specificity=5,
            )

    def test_invalid_trait_value_negative(self):
        """Test that negative trait values fail."""
        with pytest.raises(ValueError):
            PersonaTraits(
                directness=-1,  # Invalid
                ruthlessness=5,
                voice_protection=5,
                structure_focus=5,
                market_awareness=5,
                praise_frequency=5,
                formality=5,
                challenge_level=5,
                specificity=5,
            )


class TestPersona:
    """Tests for Persona model."""

    def test_complete_persona(self):
        """Test loading a complete persona."""
        persona = Persona(
            id="test-editor",
            name="Test Editor",
            tagline="A test persona",
            description="For testing purposes",
            traits=PersonaTraits(
                directness=5,
                ruthlessness=5,
                voice_protection=5,
                structure_focus=5,
                market_awareness=5,
                praise_frequency=5,
                formality=5,
                challenge_level=5,
                specificity=5,
            ),
            rules=PersonaRules(
                always=["Be consistent"],
                never=["Be rude"],
            ),
            voice=PersonaVoice(
                tone="Professional",
                phrases=["Let's consider..."],
                avoids=["Actually..."],
            ),
            sample_feedback=["Good work on the structure."],
        )
        assert persona.id == "test-editor"
        assert persona.name == "Test Editor"
        assert len(persona.rules.always) == 1
        assert len(persona.voice.phrases) == 1


class TestLoadPersona:
    """Tests for load_persona function."""

    def test_load_margot(self):
        """Test loading the Margot persona."""
        persona = load_persona("margot")
        assert persona.id == "margot"
        assert persona.name == "Margot Fielding"
        assert persona.traits.directness >= 8
        assert persona.traits.ruthlessness >= 7

    def test_load_sage(self):
        """Test loading the Sage Holloway persona."""
        persona = load_persona("sage")
        assert persona.id == "sage"
        assert persona.traits.praise_frequency >= 8
        assert persona.traits.voice_protection == 10

    def test_load_blueprint(self):
        """Test loading the Maxwell Blueprint persona."""
        persona = load_persona("blueprint")
        assert persona.id == "blueprint"
        assert persona.traits.structure_focus == 10

    def test_load_sterling(self):
        """Test loading the Sterling Chase persona."""
        persona = load_persona("sterling")
        assert persona.id == "sterling"
        assert persona.traits.market_awareness == 10

    def test_load_the_axe(self):
        """Test loading The Axe persona (extreme)."""
        persona = load_persona("the-axe")
        assert persona.id == "the-axe"
        assert persona.traits.ruthlessness == 10
        assert persona.traits.praise_frequency == 1

    def test_load_cheerleader(self):
        """Test loading the Cheerleader persona (extreme)."""
        persona = load_persona("cheerleader")
        assert persona.id == "cheerleader"
        assert persona.traits.praise_frequency == 10
        assert persona.traits.ruthlessness == 1

    def test_load_ivory_tower(self):
        """Test loading the Ivory Tower persona (extreme)."""
        persona = load_persona("ivory-tower")
        assert persona.id == "ivory-tower"
        assert persona.traits.formality == 10
        assert persona.traits.market_awareness == 1

    def test_load_bestseller(self):
        """Test loading the Bestseller persona (extreme)."""
        persona = load_persona("bestseller")
        assert persona.id == "bestseller"
        assert persona.traits.market_awareness == 10
        assert persona.traits.voice_protection == 2

    def test_load_nonexistent_persona(self):
        """Test loading a persona that doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_persona("nonexistent-persona")
        assert "not found" in str(exc_info.value).lower()


class TestListAvailablePersonas:
    """Tests for list_available_personas function."""

    def test_list_personas(self):
        """Test that all expected personas are listed."""
        personas = list_available_personas()
        # Core personas
        assert "margot" in personas
        assert "sage" in personas
        assert "blueprint" in personas
        assert "sterling" in personas
        # Extreme personas
        assert "the-axe" in personas
        assert "cheerleader" in personas
        assert "ivory-tower" in personas
        assert "bestseller" in personas
        # schema.json should not be included
        assert "schema" not in personas
        # Old names should not be present
        assert "gentle-guide" not in personas
        assert "structure-architect" not in personas
        assert "market-realist" not in personas


class TestFormatPersonaForPrompt:
    """Tests for format_persona_for_prompt function."""

    def test_format_includes_key_sections(self):
        """Test that formatting includes all key sections."""
        persona = load_persona("margot")
        formatted = format_persona_for_prompt(persona)

        assert "Margot Fielding" in formatted
        assert "Personality Traits" in formatted
        assert "Editorial Rules" in formatted
        assert "Voice & Tone" in formatted
        assert "Always:" in formatted
        assert "Never:" in formatted

    def test_format_includes_trait_values(self):
        """Test that trait values are included."""
        persona = load_persona("margot")
        formatted = format_persona_for_prompt(persona)

        # Should include trait interpretations
        assert "Directness" in formatted
        assert "Ruthlessness" in formatted
        assert "/10" in formatted


class TestLoadPersonaConfig:
    """Tests for load_persona_config function."""

    def test_load_config_with_persona(self):
        """Test loading config that has a persona."""
        mock_repo = MagicMock()
        with patch(
            "utils.github_client.read_file_content", return_value="persona: margot"
        ):
            persona_id = load_persona_config(mock_repo)
        assert persona_id == "margot"

    def test_load_config_without_persona(self):
        """Test loading config without persona key."""
        mock_repo = MagicMock()
        with patch(
            "utils.github_client.read_file_content", return_value="other_key: value"
        ):
            persona_id = load_persona_config(mock_repo)
        assert persona_id is None

    def test_load_config_no_file(self):
        """Test when config file doesn't exist."""
        mock_repo = MagicMock()
        with patch("utils.github_client.read_file_content", return_value=None):
            persona_id = load_persona_config(mock_repo)
        assert persona_id is None

    def test_load_config_invalid_yaml(self):
        """Test handling invalid YAML."""
        mock_repo = MagicMock()
        with patch(
            "utils.github_client.read_file_content",
            return_value="invalid: yaml: content: [",
        ):
            persona_id = load_persona_config(mock_repo)
        assert persona_id is None


class TestGetDefaultPersona:
    """Tests for get_default_persona function."""

    def test_default_persona_content(self):
        """Test that default persona has expected content."""
        default = get_default_persona()
        assert "Editor Persona" in default
        assert "voice" in default.lower()
        assert "author" in default.lower()


class TestGetPersonasDir:
    """Tests for get_personas_dir function."""

    def test_personas_dir_exists(self):
        """Test that personas directory exists."""
        personas_dir = get_personas_dir()
        assert personas_dir.exists()
        assert personas_dir.is_dir()

    def test_personas_dir_has_json_files(self):
        """Test that personas directory contains JSON files."""
        personas_dir = get_personas_dir()
        json_files = list(personas_dir.glob("*.json"))
        assert len(json_files) >= 8  # At least 8 personas (4 core + 4 extreme)
