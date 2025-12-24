"""Persona utilities for AI Book Editor.

Loads and formats editor personas from JSON files for use in LLM prompts.
Personas define the AI editor's personality traits, voice, and rules.
"""

import json
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field


class PersonaTraits(BaseModel):
    """Numeric personality traits on a 0-10 scale."""

    model_config = ConfigDict(strict=True, frozen=True)

    directness: int = Field(ge=0, le=10, description="0=diplomatic, 10=blunt")
    ruthlessness: int = Field(
        ge=0, le=10, description="0=preserve everything, 10=cut ruthlessly"
    )
    voice_protection: int = Field(
        ge=0, le=10, description="0=polish to standard, 10=protect quirks"
    )
    structure_focus: int = Field(
        ge=0, le=10, description="0=organic flow, 10=strict arcs"
    )
    market_awareness: int = Field(
        ge=0, le=10, description="0=art for art's sake, 10=commercial"
    )
    praise_frequency: int = Field(
        ge=0, le=10, description="0=critique only, 10=celebrate often"
    )
    formality: int = Field(ge=0, le=10, description="0=casual/profane, 10=academic")
    challenge_level: int = Field(
        ge=0, le=10, description="0=gentle suggestions, 10=hard questions"
    )
    specificity: int = Field(
        ge=0, le=10, description="0=general direction, 10=line-level"
    )


class PersonaRules(BaseModel):
    """What the persona always/never does."""

    model_config = ConfigDict(strict=True)

    always: List[str] = Field(
        default_factory=list, description="Things this editor always does"
    )
    never: List[str] = Field(
        default_factory=list, description="Things this editor never does"
    )


class PersonaVoice(BaseModel):
    """How the persona communicates."""

    model_config = ConfigDict(strict=True)

    tone: str = Field(description="Description of communication style")
    phrases: List[str] = Field(
        default_factory=list, description="Characteristic things they say"
    )
    avoids: List[str] = Field(default_factory=list, description="Things they don't say")


class Persona(BaseModel):
    """Complete persona definition."""

    model_config = ConfigDict(strict=True)

    id: str = Field(description="Unique identifier")
    name: str = Field(description="Display name")
    tagline: str = Field(description="One-line description")
    description: Optional[str] = Field(default=None, description="Full description")
    traits: PersonaTraits
    rules: PersonaRules
    voice: PersonaVoice
    sample_feedback: List[str] = Field(
        default_factory=list, description="Example feedback"
    )


# Built-in persona IDs
BUILTIN_PERSONAS = {"margot", "gentle-guide", "structure-architect", "market-realist"}


def get_personas_dir() -> Path:
    """Get the personas directory (relative to project root)."""
    # When running from .github/scripts/, personas is at project root
    script_dir = Path(__file__).parent.parent.parent.parent  # Up to project root
    return script_dir / "personas"


def load_persona(persona_id: str) -> Persona:
    """
    Load a persona by ID.

    Raises:
        FileNotFoundError: If persona file doesn't exist
        ValueError: If persona JSON is invalid
    """
    personas_dir = get_personas_dir()
    persona_file = personas_dir / f"{persona_id}.json"

    if not persona_file.exists():
        available = list_available_personas()
        raise FileNotFoundError(
            f"Persona '{persona_id}' not found. Available: {', '.join(available)}"
        )

    with open(persona_file) as f:
        data = json.load(f)

    return Persona.model_validate(data)


def list_available_personas() -> List[str]:
    """List all available persona IDs."""
    personas_dir = get_personas_dir()
    if not personas_dir.exists():
        return []

    return sorted([f.stem for f in personas_dir.glob("*.json") if f.stem != "schema"])


def load_persona_config(repo) -> Optional[str]:
    """
    Load persona configuration from .ai-context/config.yaml.

    Args:
        repo: PyGithub Repository object

    Returns:
        Persona ID if configured, None otherwise
    """
    from .github_client import read_file_content

    config_content = read_file_content(repo, ".ai-context/config.yaml")
    if not config_content:
        return None

    try:
        config = yaml.safe_load(config_content)
        return config.get("persona") if config else None
    except yaml.YAMLError:
        return None


def format_persona_for_prompt(persona: Persona) -> str:
    """
    Format a persona as text for inclusion in LLM system prompt.

    This becomes part of the cached editorial context.
    """
    lines = []

    # Identity
    lines.append(f"# Editor: {persona.name}")
    lines.append(f"*{persona.tagline}*")
    lines.append("")

    if persona.description:
        lines.append(persona.description)
        lines.append("")

    # Traits as behavioral guidance
    lines.append("## Personality Traits")
    lines.append("")
    trait_descriptions = {
        "directness": ("Diplomatic", "Blunt and direct"),
        "ruthlessness": ("Preserve content", "Cut ruthlessly"),
        "voice_protection": (
            "Polish toward standard",
            "Fiercely protect author's quirks",
        ),
        "structure_focus": (
            "Let it flow organically",
            "Demand clear structure and arcs",
        ),
        "market_awareness": ("Art for art's sake", "Commercially aware"),
        "praise_frequency": ("Focus on critique", "Celebrate what works"),
        "formality": ("Casual, profane okay", "Academic, professional"),
        "challenge_level": ("Gentle suggestions", "Ask hard questions"),
        "specificity": ("General direction", "Line-level precision"),
    }

    for trait_name, (low_desc, high_desc) in trait_descriptions.items():
        value = getattr(persona.traits, trait_name)
        if value <= 3:
            desc = low_desc
        elif value >= 7:
            desc = high_desc
        else:
            desc = f"Balance of {low_desc.lower()} and {high_desc.lower()}"
        lines.append(
            f"- **{trait_name.replace('_', ' ').title()}** ({value}/10): {desc}"
        )

    lines.append("")

    # Rules
    if persona.rules.always or persona.rules.never:
        lines.append("## Editorial Rules")
        lines.append("")
        if persona.rules.always:
            lines.append("**Always:**")
            for rule in persona.rules.always:
                lines.append(f"- {rule}")
            lines.append("")
        if persona.rules.never:
            lines.append("**Never:**")
            for rule in persona.rules.never:
                lines.append(f"- {rule}")
            lines.append("")

    # Voice
    lines.append("## Voice & Tone")
    lines.append("")
    lines.append(f"**Tone:** {persona.voice.tone}")
    lines.append("")
    if persona.voice.phrases:
        lines.append("**Characteristic phrases:**")
        for phrase in persona.voice.phrases:
            lines.append(f'- "{phrase}"')
        lines.append("")
    if persona.voice.avoids:
        lines.append("**Avoid saying:**")
        for avoid in persona.voice.avoids:
            lines.append(f'- "{avoid}"')
        lines.append("")

    # Sample feedback as examples
    if persona.sample_feedback:
        lines.append("## Example Feedback (for reference)")
        lines.append("")
        for i, feedback in enumerate(persona.sample_feedback[:2], 1):  # Limit to 2
            lines.append(f'*Example {i}:* "{feedback}"')
            lines.append("")

    return "\n".join(lines)


def get_default_persona() -> str:
    """Get the default persona content when no persona is configured."""
    return """# Editor Persona

You are a professional book editor. Your role is to help authors improve their writing
while preserving their unique voice.

## Approach

- Be direct but constructive in feedback
- Protect the author's voice while enhancing clarity
- Focus on structure and flow
- Ask clarifying questions when intent is unclear
- Celebrate what's working, then address what needs work

## Guidelines

- Never rewrite the author's content — suggest, don't dictate
- Reference specific phrases when giving feedback
- Explain the "why" behind every suggestion
- Be honest about market considerations when relevant
"""
