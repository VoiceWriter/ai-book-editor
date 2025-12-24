"""Knowledge base utilities for AI Book Editor."""

import json
from typing import Any, Dict, Optional

import yaml

from .github_client import list_files_in_directory, read_file_content
from .persona import (format_persona_for_prompt, get_default_persona,
                      load_persona, load_persona_config)


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


def load_editorial_context(repo) -> Dict[str, Any]:
    """
    Load all editorial context files.

    Persona loading priority:
    1. JSON persona from personas/ if configured in .ai-context/config.yaml
    2. EDITOR_PERSONA.md (legacy/custom persona)
    3. Default built-in persona
    """
    context = {}

    # Load persona - check for JSON persona first
    persona_id = load_persona_config(repo)
    context["persona_id"] = persona_id

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
        context["persona"] = (
            read_file_content(repo, "EDITOR_PERSONA.md") or get_default_persona()
        )
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

    return context
