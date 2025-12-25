"""Knowledge base utilities for AI Book Editor."""

import json
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .github_client import list_files_in_directory, read_file_content
from .persona import format_persona_for_prompt, get_default_persona, load_persona, resolve_persona
from .phases import BookPhase, get_book_phase_guidance

# =============================================================================
# BOOK CONFIGURATION MODELS
# =============================================================================


class ChapterConfig(BaseModel):
    """Configuration for a single chapter."""

    model_config = ConfigDict(strict=True)

    name: str = Field(description="Chapter name/title")
    file: Optional[str] = Field(default=None, description="Filename in chapters/")
    status: str = Field(
        default="planned",
        description="Status: planned | in_progress | drafted | revised | polished",
    )
    notes: Optional[str] = Field(default=None, description="Author notes about this chapter")


class BookConfig(BaseModel):
    """Book project configuration from .ai-context/book.yaml."""

    model_config = ConfigDict(strict=True)

    # Identity
    title: str = Field(default="", description="Book title")
    subtitle: Optional[str] = Field(default=None, description="Book subtitle")
    author: str = Field(default="", description="Author name")

    # Audience & Purpose
    target_audience: Optional[str] = Field(default=None, description="Target reader description")
    core_themes: List[str] = Field(default_factory=list, description="Central themes")
    author_goals: List[str] = Field(
        default_factory=list, description="What author wants readers to feel/know/do"
    )

    # Project Phase
    phase: BookPhase = Field(default=BookPhase.NEW, description="Current project phase")

    # Structure
    target_word_count: Optional[int] = Field(default=None, description="Word count goal")
    target_chapters: Optional[int] = Field(default=None, description="Planned chapter count")
    chapters: List[ChapterConfig] = Field(default_factory=list, description="Chapter tracking")

    # Editorial
    default_persona: Optional[str] = Field(
        default=None, description="Default persona for this project"
    )
    editorial_notes: Optional[str] = Field(default=None, description="Specific guidance for editor")

    # Metadata
    created_at: Optional[str] = Field(default=None, description="When project was created")
    last_phase_change: Optional[str] = Field(default=None, description="When phase last changed")
    phase_history: List[dict] = Field(default_factory=list, description="Phase transition log")


def load_book_config(repo) -> Optional[BookConfig]:
    """
    Load book configuration from .ai-context/book.yaml.

    Returns None if no config exists (first-time setup needed).
    """
    content = read_file_content(repo, ".ai-context/book.yaml")
    if not content:
        return None

    try:
        data = yaml.safe_load(content)
        if not data:
            return None

        # Handle phase as string
        if "phase" in data and isinstance(data["phase"], str):
            data["phase"] = BookPhase(data["phase"])

        # Handle chapters as list of dicts
        if "chapters" in data:
            data["chapters"] = [
                ChapterConfig(**c) if isinstance(c, dict) else c for c in data["chapters"]
            ]

        return BookConfig(**data)
    except Exception as e:
        print(f"Warning: Could not parse book.yaml: {e}")
        return None


def get_book_progress(book_config: Optional[BookConfig], chapters_on_disk: List[str]) -> dict:
    """
    Calculate book progress metrics.

    Returns:
        dict with progress metrics: chapters_planned, chapters_drafted, completion_pct, etc.
    """
    if not book_config:
        return {
            "chapters_planned": 0,
            "chapters_drafted": len(chapters_on_disk),
            "chapters_revised": 0,
            "chapters_polished": 0,
            "completion_pct": 0,
            "has_config": False,
        }

    planned = len(book_config.chapters)
    drafted = sum(1 for c in book_config.chapters if c.status in ["drafted", "revised", "polished"])
    revised = sum(1 for c in book_config.chapters if c.status in ["revised", "polished"])
    polished = sum(1 for c in book_config.chapters if c.status == "polished")

    # Calculate completion based on phase
    if book_config.phase == BookPhase.NEW:
        # In NEW phase, completion is about having chapters planned
        completion = (
            (planned / book_config.target_chapters * 100) if book_config.target_chapters else 0
        )
    elif book_config.phase == BookPhase.DRAFTING:
        # In DRAFTING, completion is about first drafts
        completion = (drafted / planned * 100) if planned > 0 else 0
    elif book_config.phase == BookPhase.REVISING:
        # In REVISING, completion is about revised chapters
        completion = (revised / planned * 100) if planned > 0 else 0
    elif book_config.phase == BookPhase.POLISHING:
        # In POLISHING, completion is about polished chapters
        completion = (polished / planned * 100) if planned > 0 else 0
    else:
        completion = 100

    return {
        "chapters_planned": planned,
        "chapters_drafted": drafted,
        "chapters_revised": revised,
        "chapters_polished": polished,
        "chapters_on_disk": len(chapters_on_disk),
        "completion_pct": round(completion, 1),
        "has_config": True,
        "phase": book_config.phase.value,
    }


def format_book_context_for_prompt(book_config: Optional[BookConfig]) -> Optional[str]:
    """
    Format book configuration for inclusion in AI prompts.

    This gives the editor essential context about the book project.
    """
    if not book_config:
        return None

    lines = []

    lines.append("## Book Project Context")
    lines.append("")

    if book_config.title:
        lines.append(f"**Title:** {book_config.title}")
    if book_config.author:
        lines.append(f"**Author:** {book_config.author}")
    lines.append("")

    # Phase-specific guidance
    lines.append(get_book_phase_guidance(book_config.phase))

    if book_config.target_audience:
        lines.append("**Target Audience:**")
        lines.append(book_config.target_audience)
        lines.append("")

    if book_config.core_themes:
        lines.append("**Core Themes:**")
        for theme in book_config.core_themes:
            if theme:
                lines.append(f"- {theme}")
        lines.append("")

    if book_config.author_goals:
        lines.append("**Author's Goals:**")
        for goal in book_config.author_goals:
            if goal:
                lines.append(f"- {goal}")
        lines.append("")

    if book_config.editorial_notes:
        lines.append("**Author's Editorial Notes:**")
        lines.append(f"*{book_config.editorial_notes}*")
        lines.append("")

    return "\n".join(lines)


def load_knowledge_base(repo) -> Dict[str, Any]:
    """Load all knowledge base files from .ai-context/"""
    knowledge = {"qa_pairs": [], "terminology": {}, "themes": [], "preferences": {}}

    # Load Q&A pairs
    qa_content = read_file_content(repo, ".ai-context/knowledge.jsonl")
    if qa_content:
        for line in qa_content.strip().split("\n"):
            if line.strip():
                try:
                    knowledge["qa_pairs"].append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    # Load terminology
    term_content = read_file_content(repo, ".ai-context/terminology.yaml")
    if term_content:
        try:
            knowledge["terminology"] = yaml.safe_load(term_content) or {}
        except yaml.YAMLError:
            pass

    # Load themes
    themes_content = read_file_content(repo, ".ai-context/themes.yaml")
    if themes_content:
        try:
            knowledge["themes"] = yaml.safe_load(themes_content) or []
        except yaml.YAMLError:
            pass

    # Load preferences
    prefs_content = read_file_content(repo, ".ai-context/author-preferences.yaml")
    if prefs_content:
        try:
            knowledge["preferences"] = yaml.safe_load(prefs_content) or {}
        except yaml.YAMLError:
            pass

    return knowledge


def format_knowledge_for_prompt(knowledge: Dict[str, Any]) -> Optional[str]:
    """Format knowledge base for inclusion in AI prompts."""
    sections = []

    if knowledge["qa_pairs"]:
        qa_text = "\n".join(
            [f"Q: {qa['question']}\nA: {qa['answer']}" for qa in knowledge["qa_pairs"]]
        )
        sections.append(f"## Known Context (from author answers)\n\n{qa_text}")

    if knowledge["terminology"]:
        terms = "\n".join(
            [
                f"- Use '{v}' not '{k}'" if isinstance(v, str) else f"- {k}: {v}"
                for k, v in knowledge["terminology"].items()
            ]
        )
        sections.append(f"## Terminology Preferences\n\n{terms}")

    if knowledge["themes"]:
        if isinstance(knowledge["themes"], list):
            themes = "\n".join([f"- {t}" for t in knowledge["themes"]])
        else:
            themes = str(knowledge["themes"])
        sections.append(f"## Central Themes\n\n{themes}")

    if knowledge["preferences"]:
        prefs = yaml.dump(knowledge["preferences"], default_flow_style=False)
        sections.append(f"## Author Preferences\n\n{prefs}")

    return "\n\n".join(sections) if sections else None


def load_editorial_context(
    repo,
    labels: Optional[list] = None,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Load all editorial context files.

    Persona loading priority (highest to lowest):
    1. Comment command (@margot-ai-editor use/as)
    2. Issue label (persona:margot)
    3. Environment variable (EDITOR_PERSONA)
    4. Config file (.ai-context/config.yaml)
    5. EDITOR_PERSONA.md (legacy/custom persona)
    6. Default built-in persona

    Args:
        repo: PyGithub Repository object
        labels: Optional list of issue/PR labels for persona override
        comment: Optional comment text for persona command parsing
    """
    context = {}

    # Resolve persona using cascading priority
    persona_id, persona_source = resolve_persona(
        repo=repo,
        labels=labels,
        comment=comment,
    )
    context["persona_id"] = persona_id
    context["persona_source"] = persona_source

    if persona_id:
        try:
            persona = load_persona(persona_id)
            context["persona"] = format_persona_for_prompt(persona)
            context["persona_object"] = persona
        except (FileNotFoundError, ValueError) as e:
            # Fall back to EDITOR_PERSONA.md
            print(f"Warning: Could not load persona '{persona_id}': {e}")
            context["persona"] = (
                read_file_content(repo, "EDITOR_PERSONA.md") or get_default_persona()
            )
            context["persona_object"] = None
    else:
        # No persona configured - use EDITOR_PERSONA.md or default
        context["persona"] = read_file_content(repo, "EDITOR_PERSONA.md") or get_default_persona()
        context["persona_object"] = None

    # Core editorial files
    context["guidelines"] = (
        read_file_content(repo, "EDITORIAL_GUIDELINES.md") or "No guidelines defined."
    )
    context["glossary"] = read_file_content(repo, "GLOSSARY.md")
    context["style_guide"] = read_file_content(repo, "style-guide.md")

    # Knowledge base
    knowledge = load_knowledge_base(repo)
    context["knowledge"] = knowledge
    context["knowledge_formatted"] = format_knowledge_for_prompt(knowledge)

    # Chapter list
    chapters = list_files_in_directory(repo, "chapters")
    context["chapters"] = [c for c in chapters if c.endswith(".md")]

    # Book configuration (project-level context)
    book_config = load_book_config(repo)
    context["book_config"] = book_config
    context["book_context"] = format_book_context_for_prompt(book_config)
    context["book_progress"] = get_book_progress(book_config, context["chapters"])

    # Book phase affects overall editorial approach
    if book_config:
        context["book_phase"] = book_config.phase
        # Use book's default persona if set and no other persona specified
        if book_config.default_persona and persona_source == "default":
            try:
                persona = load_persona(book_config.default_persona)
                context["persona"] = format_persona_for_prompt(persona)
                context["persona_object"] = persona
                context["persona_id"] = book_config.default_persona
                context["persona_source"] = "book_config"
            except Exception:
                pass
    else:
        context["book_phase"] = None

    return context
