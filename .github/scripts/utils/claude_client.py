"""Claude API utilities for AI Book Editor."""

import os
import anthropic
from typing import Optional, Dict, Any


def get_claude_client() -> anthropic.Anthropic:
    """Get Claude API client."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    return anthropic.Anthropic(api_key=api_key)


def call_claude(
    prompt: str,
    system: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    temperature: float = 0.7
) -> str:
    """Call Claude and return the response text."""
    client = get_claude_client()

    kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }

    if system:
        kwargs["system"] = system

    message = client.messages.create(**kwargs)
    return message.content[0].text


def build_editorial_prompt(
    persona: str,
    guidelines: str,
    glossary: Optional[str],
    knowledge_base: Optional[str],
    chapter_list: list,
    task: str,
    content: str
) -> str:
    """Build a complete editorial prompt with all context."""

    sections = []

    sections.append(f"""# Your Persona
{persona}""")

    sections.append(f"""# Editorial Guidelines (MUST FOLLOW)
{guidelines}""")

    if glossary:
        sections.append(f"""# Glossary
{glossary}""")

    if knowledge_base:
        sections.append(f"""# Knowledge Base (What You Know About This Book)
{knowledge_base}""")

    if chapter_list:
        sections.append(f"""# Existing Chapters
{', '.join(chapter_list)}""")

    sections.append(f"""# Current Task
{task}""")

    sections.append(f"""# Content to Process
{content}""")

    sections.append("""# Important Reminders
- Follow EDITORIAL_GUIDELINES.md exactly
- Embody EDITOR_PERSONA.md in your responses
- Preserve the author's voice — enhance, don't replace
- Be specific: reference exact phrases, not vague generalities
- Explain WHY when you suggest changes
- If unsure about author intent, ASK rather than assume""")

    return "\n\n".join(sections)
