"""Persona utilities for AI Book Editor.

Loads and formats editor personas from JSON files for use in LLM prompts.
Personas define the AI editor's personality traits, voice, and rules.
"""

import json
import os
import re
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
BUILTIN_PERSONAS = {
    "margot",
    "sage",
    "blueprint",
    "sterling",
    "the-axe",
    "cheerleader",
    "ivory-tower",
    "bestseller",
}

# Label prefix for persona override
PERSONA_LABEL_PREFIX = "persona:"


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


def get_other_personas_summary(current_id: str) -> str:
    """Get a brief summary of other personas for cross-referral."""
    summaries = {
        "margot": ("Margot Fielding", "tough love, later drafts, cutting fluff"),
        "sage": ("Sage Holloway", "early drafts, building confidence, nurturing"),
        "blueprint": ("Maxwell Blueprint", "structure problems, pacing, organization"),
        "sterling": ("Sterling Chase", "market positioning, hooks, commercial appeal"),
        "the-axe": ("The Axe", "brutal cuts, bloated manuscripts, no mercy"),
        "cheerleader": (
            "Sunny Brightwell",
            "writer's block, encouragement, positivity",
        ),
        "ivory-tower": ("Professor Ashworth", "literary craft, academic rigor"),
        "bestseller": (
            "Chip Madison",
            "maximum reach, readability, commercial optimization",
        ),
    }

    lines = []
    for pid, (name, specialty) in summaries.items():
        if pid != current_id:
            lines.append(f"- **{name}** (`@margot-ai-editor as {pid}`): {specialty}")
    return "\n".join(lines)


def format_persona_for_prompt(persona: Persona) -> str:
    """
    Format a persona as text for inclusion in LLM system prompt.

    This becomes part of the cached editorial context.
    """
    lines = []

    # Identity and embodiment instruction
    lines.append(f"# You ARE {persona.name}")
    lines.append("")
    lines.append(
        f"You are not an AI pretending to be an editor. You ARE {persona.name}."
    )
    lines.append(f"Speak in first person. Have opinions. Be {persona.tagline.lower()}")
    lines.append(
        "Never break character. Never refer to yourself as an AI or assistant."
    )
    lines.append("")
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

    # Colleagues for second opinions
    lines.append("## Your Colleagues")
    lines.append("")
    lines.append(
        "If the author needs a different perspective, you can suggest they consult:"
    )
    lines.append("")
    lines.append(get_other_personas_summary(persona.id))
    lines.append("")
    lines.append(
        "You may suggest a colleague when their expertise better fits the author's needs."
    )
    lines.append(
        "For example: 'For the structural issues, you might want Maxwell Blueprint's take.'"
    )
    lines.append("")

    return "\n".join(lines)


def get_persona_from_env() -> Optional[str]:
    """
    Get persona override from environment variable.

    Set EDITOR_PERSONA in workflow or secrets to override config.yaml default.

    Returns:
        Persona ID if set, None otherwise
    """
    persona_id = os.environ.get("EDITOR_PERSONA")
    if persona_id:
        available = list_available_personas()
        if persona_id in available:
            return persona_id
        print(
            f"Warning: EDITOR_PERSONA='{persona_id}' not found. Available: {available}"
        )
    return None


def get_persona_from_labels(labels: list) -> Optional[str]:
    """
    Get persona override from issue/PR labels.

    Labels like 'persona:margot' or 'persona:the-axe' override the default.

    Args:
        labels: List of label names (strings) or label objects with .name

    Returns:
        Persona ID if found in labels, None otherwise
    """
    available = list_available_personas()

    for label in labels:
        # Handle both string labels and objects with .name
        label_name = (
            label if isinstance(label, str) else getattr(label, "name", str(label))
        )

        if label_name.startswith(PERSONA_LABEL_PREFIX):
            persona_id = label_name[len(PERSONA_LABEL_PREFIX) :]
            if persona_id in available:
                return persona_id
            print(
                f"Warning: Label '{label_name}' persona not found. Available: {available}"
            )

    return None


def parse_persona_command(comment: str) -> tuple[Optional[str], Optional[str], str]:
    """
    Parse persona switching commands from a comment.

    Supported formats:
    - '@margot-ai-editor use margot' - Switch persona for this issue (sticky)
    - '@margot-ai-editor as the-axe' - One-shot persona for this response
    - '@margot-ai-editor as sage: review this' - One-shot with inline request
    - '@margot-ai-editor list personas' - Show available personas

    Args:
        comment: The comment text

    Returns:
        Tuple of (persona_id, command_type, remaining_text)
        - persona_id: The requested persona, or None
        - command_type: 'use' (sticky), 'as' (one-shot), 'list', or None
        - remaining_text: Text after the command (for inline requests)
    """
    # Normalize whitespace
    text = comment.strip()

    # Pattern: @margot-ai-editor use <persona>
    use_match = re.search(r"@margot-ai-editor\s+use\s+(\S+)", text, re.IGNORECASE)
    if use_match:
        persona_id = use_match.group(1).lower().strip()
        remaining = text[use_match.end() :].strip()
        return persona_id, "use", remaining

    # Pattern: @margot-ai-editor as <persona>: <request> or @margot-ai-editor as <persona>
    as_match = re.search(
        r"@margot-ai-editor\s+as\s+(\S+?)(?:\s*[,:]\s*(.*))?$", text, re.IGNORECASE | re.DOTALL
    )
    if as_match:
        persona_id = as_match.group(1).lower().strip()
        remaining = (as_match.group(2) or "").strip()
        return persona_id, "as", remaining

    # Pattern: @margot-ai-editor list personas
    if re.search(r"@margot-ai-editor\s+list\s+personas?", text, re.IGNORECASE):
        return None, "list", ""

    # Pattern: @margot-ai-editor switch to <persona>
    switch_match = re.search(r"@margot-ai-editor\s+switch\s+to\s+(\S+)", text, re.IGNORECASE)
    if switch_match:
        persona_id = switch_match.group(1).lower().strip()
        remaining = text[switch_match.end() :].strip()
        return persona_id, "use", remaining

    return None, None, text


def format_persona_list() -> str:
    """
    Format a markdown table of available personas for display.

    Returns:
        Markdown formatted persona list
    """
    lines = ["## Available Personas", ""]
    lines.append("| ID | Name | Style |")
    lines.append("|:---|:-----|:------|")

    for persona_id in list_available_personas():
        try:
            persona = load_persona(persona_id)
            lines.append(f"| `{persona_id}` | {persona.name} | {persona.tagline} |")
        except (FileNotFoundError, ValueError):
            pass

    lines.append("")
    lines.append("**Usage:**")
    lines.append("- `@margot-ai-editor use margot` - Switch to this persona")
    lines.append("- `@margot-ai-editor as the-axe: review this` - One-shot with persona")
    lines.append("- Add label `persona:sage` to issue for per-issue override")

    return "\n".join(lines)


def resolve_persona(
    repo=None,
    labels: Optional[list] = None,
    comment: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """
    Resolve which persona to use with cascading priority.

    Priority (highest to lowest):
    1. Comment command (@margot-ai-editor use/as)
    2. Issue label (persona:margot)
    3. Environment variable (EDITOR_PERSONA)
    4. Config file (.ai-context/config.yaml)

    Args:
        repo: PyGithub Repository object (for config.yaml)
        labels: List of issue/PR labels
        comment: Current comment text (for command parsing)

    Returns:
        Tuple of (persona_id, source) where source is one of:
        'command', 'label', 'env', 'config', 'default'
    """
    # 1. Check comment command (highest priority)
    if comment:
        persona_id, cmd_type, _ = parse_persona_command(comment)
        if persona_id and cmd_type in ("use", "as"):
            available = list_available_personas()
            if persona_id in available:
                return persona_id, "command"

    # 2. Check labels
    if labels:
        persona_id = get_persona_from_labels(labels)
        if persona_id:
            return persona_id, "label"

    # 3. Check environment variable
    persona_id = get_persona_from_env()
    if persona_id:
        return persona_id, "env"

    # 4. Check config file
    if repo:
        persona_id = load_persona_config(repo)
        if persona_id:
            available = list_available_personas()
            if persona_id in available:
                return persona_id, "config"

    # 5. Default
    return None, "default"


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
