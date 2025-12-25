"""Tests for persona utilities."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))

from utils.persona import (
    Persona,
    PersonaRules,
    PersonaTraits,  # noqa: E402
    PersonaVoice,
    format_discovery_prompt,
    format_feedback_with_tiers,
    format_persona_for_prompt,
    format_persona_list,
    get_default_persona,
    get_persona_from_env,
    get_persona_from_labels,
    get_personas_dir,
    list_available_personas,
    load_persona,
    load_persona_config,
    parse_persona_command,
    resolve_persona,
)


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
        with patch("utils.github_client.read_file_content", return_value="persona: margot"):
            persona_id = load_persona_config(mock_repo)
        assert persona_id == "margot"

    def test_load_config_without_persona(self):
        """Test loading config without persona key."""
        mock_repo = MagicMock()
        with patch("utils.github_client.read_file_content", return_value="other_key: value"):
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


class TestParsePersonaCommand:
    """Tests for parse_persona_command function."""

    def test_use_command(self):
        """Test @margot-ai-editor use <persona> command."""
        persona_id, cmd_type, remaining = parse_persona_command("@margot-ai-editor use margot")
        assert persona_id == "margot"
        assert cmd_type == "use"
        assert remaining == ""

    def test_use_command_with_extra_text(self):
        """Test use command with additional text."""
        persona_id, cmd_type, remaining = parse_persona_command(
            "@margot-ai-editor use the-axe and be brutal"
        )
        assert persona_id == "the-axe"
        assert cmd_type == "use"
        assert remaining == "and be brutal"

    def test_as_command_simple(self):
        """Test @margot-ai-editor as <persona> command."""
        persona_id, cmd_type, remaining = parse_persona_command("@margot-ai-editor as sage")
        assert persona_id == "sage"
        assert cmd_type == "as"
        assert remaining == ""

    def test_as_command_with_colon(self):
        """Test @margot-ai-editor as <persona>: <request> command."""
        persona_id, cmd_type, remaining = parse_persona_command(
            "@margot-ai-editor as the-axe: review this chapter"
        )
        assert persona_id == "the-axe"
        assert cmd_type == "as"
        assert remaining == "review this chapter"

    def test_switch_to_command(self):
        """Test @margot-ai-editor switch to <persona> command."""
        persona_id, cmd_type, remaining = parse_persona_command(
            "@margot-ai-editor switch to sterling"
        )
        assert persona_id == "sterling"
        assert cmd_type == "use"

    def test_list_personas_command(self):
        """Test @margot-ai-editor list personas command."""
        persona_id, cmd_type, remaining = parse_persona_command("@margot-ai-editor list personas")
        assert persona_id is None
        assert cmd_type == "list"

    def test_no_command(self):
        """Test regular comment without persona command."""
        persona_id, cmd_type, remaining = parse_persona_command("@margot-ai-editor review this")
        assert persona_id is None
        assert cmd_type is None
        assert remaining == "@margot-ai-editor review this"


class TestGetPersonaFromLabels:
    """Tests for get_persona_from_labels function."""

    def test_string_labels(self):
        """Test with string labels."""
        labels = ["voice_transcription", "persona:margot", "ai-reviewed"]
        persona_id = get_persona_from_labels(labels)
        assert persona_id == "margot"

    def test_object_labels(self):
        """Test with label objects."""
        label1 = MagicMock()
        label1.name = "voice_transcription"
        label2 = MagicMock()
        label2.name = "persona:the-axe"
        labels = [label1, label2]
        persona_id = get_persona_from_labels(labels)
        assert persona_id == "the-axe"

    def test_no_persona_label(self):
        """Test when no persona label exists."""
        labels = ["voice_transcription", "ai-reviewed"]
        persona_id = get_persona_from_labels(labels)
        assert persona_id is None

    def test_invalid_persona_label(self):
        """Test with invalid persona in label."""
        labels = ["persona:nonexistent"]
        persona_id = get_persona_from_labels(labels)
        assert persona_id is None


class TestGetPersonaFromEnv:
    """Tests for get_persona_from_env function."""

    def test_valid_env_persona(self):
        """Test with valid EDITOR_PERSONA env var."""
        with patch.dict("os.environ", {"EDITOR_PERSONA": "margot"}):
            persona_id = get_persona_from_env()
        assert persona_id == "margot"

    def test_invalid_env_persona(self):
        """Test with invalid EDITOR_PERSONA env var."""
        with patch.dict("os.environ", {"EDITOR_PERSONA": "nonexistent"}):
            persona_id = get_persona_from_env()
        assert persona_id is None

    def test_no_env_persona(self):
        """Test when EDITOR_PERSONA is not set."""
        with patch.dict("os.environ", {}, clear=True):
            # Clear the env var if it exists
            import os

            if "EDITOR_PERSONA" in os.environ:
                del os.environ["EDITOR_PERSONA"]
            persona_id = get_persona_from_env()
        assert persona_id is None


class TestResolvePersona:
    """Tests for resolve_persona function."""

    def test_command_highest_priority(self):
        """Test that comment command has highest priority."""
        labels = ["persona:sage"]
        persona_id, source = resolve_persona(labels=labels, comment="@margot-ai-editor use the-axe")
        assert persona_id == "the-axe"
        assert source == "command"

    def test_label_over_env(self):
        """Test that label beats env var."""
        with patch.dict("os.environ", {"EDITOR_PERSONA": "margot"}):
            labels = ["persona:blueprint"]
            persona_id, source = resolve_persona(labels=labels)
        assert persona_id == "blueprint"
        assert source == "label"

    def test_env_when_no_label(self):
        """Test env var when no label."""
        with patch.dict("os.environ", {"EDITOR_PERSONA": "sterling"}):
            persona_id, source = resolve_persona(labels=[])
        assert persona_id == "sterling"
        assert source == "env"

    def test_default_when_nothing_set(self):
        """Test default when nothing is configured."""
        with patch.dict("os.environ", {}, clear=True):
            import os

            if "EDITOR_PERSONA" in os.environ:
                del os.environ["EDITOR_PERSONA"]
            persona_id, source = resolve_persona(labels=[])
        assert persona_id is None
        assert source == "default"


class TestFormatPersonaList:
    """Tests for format_persona_list function."""

    def test_includes_all_personas(self):
        """Test that list includes all available personas."""
        result = format_persona_list()
        assert "margot" in result
        assert "sage" in result
        assert "the-axe" in result
        assert "Available Personas" in result

    def test_includes_usage_instructions(self):
        """Test that list includes usage instructions."""
        result = format_persona_list()
        assert "@margot-ai-editor use" in result
        assert "persona:" in result


class TestFormatPersonaWithColleagues:
    """Tests for colleague awareness in persona formatting."""

    def test_includes_colleagues_section(self):
        """Test that formatted persona includes colleagues."""
        persona = load_persona("margot")
        formatted = format_persona_for_prompt(persona)
        assert "Your Colleagues" in formatted
        assert "Sage Holloway" in formatted
        assert "Maxwell Blueprint" in formatted

    def test_excludes_self_from_colleagues(self):
        """Test that persona doesn't list itself as colleague."""
        persona = load_persona("margot")
        formatted = format_persona_for_prompt(persona)
        # Margot should not appear in the colleagues section
        # (she's in the header but not in the colleagues list)
        colleagues_section = formatted.split("Your Colleagues")[1]
        assert "as margot" not in colleagues_section

    def test_includes_embodiment_instructions(self):
        """Test that persona includes character embodiment instructions."""
        persona = load_persona("the-axe")
        formatted = format_persona_for_prompt(persona)
        assert "You ARE" in formatted
        assert "Never break character" in formatted


class TestPersonaDiscovery:
    """Tests for discovery questions in personas."""

    def test_all_personas_have_discovery(self):
        """Test that all personas have discovery sections."""
        for persona_id in list_available_personas():
            persona = load_persona(persona_id)
            assert persona.discovery is not None, f"{persona_id} missing discovery"

    def test_discovery_has_intake_questions(self):
        """Test that personas have intake questions."""
        persona = load_persona("margot")
        assert len(persona.discovery.intake_questions) >= 2

    def test_discovery_has_socratic_prompts(self):
        """Test that personas have Socratic prompts."""
        persona = load_persona("sage")
        assert len(persona.discovery.socratic_prompts) >= 2

    def test_discovery_has_philosophy(self):
        """Test that personas have discovery philosophy."""
        persona = load_persona("blueprint")
        assert persona.discovery.philosophy
        assert len(persona.discovery.philosophy) > 10

    def test_discovery_questions_match_personality(self):
        """Test that discovery questions match persona personality."""
        # The Axe should have direct, harsh questions
        axe = load_persona("the-axe")
        questions = " ".join(axe.discovery.intake_questions)
        assert "cut" in questions.lower() or "willing" in questions.lower()

        # Sage should have gentle, nurturing questions
        sage = load_persona("sage")
        questions = " ".join(sage.discovery.intake_questions)
        assert "feeling" in questions.lower() or "support" in questions.lower()


class TestPersonaFeedbackTiers:
    """Tests for feedback tier labels in personas."""

    def test_all_personas_have_feedback_tiers(self):
        """Test that all personas have feedback tier labels."""
        for persona_id in list_available_personas():
            persona = load_persona(persona_id)
            assert persona.feedback_tiers is not None, f"{persona_id} missing feedback_tiers"

    def test_feedback_tiers_have_all_levels(self):
        """Test that feedback tiers have all three levels."""
        persona = load_persona("margot")
        assert persona.feedback_tiers.critical_label
        assert persona.feedback_tiers.recommended_label
        assert persona.feedback_tiers.optional_label

    def test_feedback_tiers_match_personality(self):
        """Test that tier labels match persona personality."""
        # The Axe should have blunt labels
        axe = load_persona("the-axe")
        assert "cut" in axe.feedback_tiers.critical_label.lower()

        # Cheerleader should have positive labels
        cheerleader = load_persona("cheerleader")
        assert "!" in cheerleader.feedback_tiers.critical_label


class TestFormatDiscoveryPrompt:
    """Tests for format_discovery_prompt function."""

    def test_includes_persona_name(self):
        """Test that discovery prompt includes persona name."""
        persona = load_persona("margot")
        formatted = format_discovery_prompt(persona)
        assert "Margot" in formatted
        assert "Discovery Mode" in formatted

    def test_includes_questions(self):
        """Test that discovery prompt includes question types."""
        persona = load_persona("sage")
        formatted = format_discovery_prompt(persona)
        assert "Intake questions" in formatted
        assert "Socratic prompts" in formatted

    def test_includes_emotional_state_guidance(self):
        """Test that emotional state affects prompt."""
        persona = load_persona("sage")
        formatted = format_discovery_prompt(persona, emotional_state="vulnerable")
        assert "vulnerable" in formatted
        assert "Emotional check-in" in formatted or "emotional" in formatted.lower()

    def test_includes_task_instructions(self):
        """Test that prompt includes task instructions."""
        persona = load_persona("margot")
        formatted = format_discovery_prompt(persona)
        assert "Read the content" in formatted
        assert "Choose 2-4 questions" in formatted


class TestFormatFeedbackWithTiers:
    """Tests for format_feedback_with_tiers function."""

    def test_formats_all_tiers(self):
        """Test that all feedback tiers are formatted."""
        persona = load_persona("margot")
        items = [
            {"tier": "critical", "content": "Fix this structure issue"},
            {"tier": "recommended", "content": "Consider tightening the prose"},
            {"tier": "optional", "content": "You might try a different metaphor"},
        ]
        formatted = format_feedback_with_tiers(persona, items)
        assert persona.feedback_tiers.critical_label in formatted
        assert "Fix this structure issue" in formatted

    def test_groups_by_tier(self):
        """Test that items are grouped by tier."""
        persona = load_persona("sage")
        items = [
            {"tier": "critical", "content": "Item 1"},
            {"tier": "optional", "content": "Item 2"},
            {"tier": "critical", "content": "Item 3"},
        ]
        formatted = format_feedback_with_tiers(persona, items)
        # Both critical items should appear before optional
        critical_pos = formatted.find("Item 1")
        optional_pos = formatted.find("Item 2")
        assert critical_pos < optional_pos

    def test_handles_missing_tiers(self):
        """Test that missing tiers are handled gracefully."""
        persona = load_persona("blueprint")
        items = [{"tier": "critical", "content": "Only critical item"}]
        formatted = format_feedback_with_tiers(persona, items)
        assert "Only critical item" in formatted
        # Should not error on missing recommended/optional


class TestPersonaDiscoveryIntegration:
    """Integration tests for persona discovery in prompts."""

    def test_full_prompt_includes_discovery(self):
        """Test that full persona prompt includes discovery section."""
        persona = load_persona("margot")
        formatted = format_persona_for_prompt(persona)
        assert "Discovery Approach" in formatted
        assert "ASK questions" in formatted

    def test_full_prompt_includes_feedback_tiers(self):
        """Test that full persona prompt includes feedback tiers."""
        persona = load_persona("margot")
        formatted = format_persona_for_prompt(persona)
        assert "Feedback Priority Labels" in formatted
        assert persona.feedback_tiers.critical_label in formatted
