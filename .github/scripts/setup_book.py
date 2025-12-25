#!/usr/bin/env python3
"""
Book configuration management via GitHub PRs.

This script handles:
1. Creating initial book.yaml from conversation insights
2. Updating book.yaml when new information is learned
3. Transitioning project phases

All changes are made via Pull Requests so the author can review and approve.
The AI proposes changes, the author has final say.
"""

import os
import sys
from datetime import datetime
from typing import Optional

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import BaseModel, ConfigDict, Field  # noqa: E402
from scripts.utils.github_client import get_github_client, get_repo  # noqa: E402


class BookConfigUpdate(BaseModel):
    """Proposed update to book configuration."""

    model_config = ConfigDict(strict=True)

    title: Optional[str] = Field(default=None, description="Book title if learned")
    author: Optional[str] = Field(default=None, description="Author name if learned")
    target_audience: Optional[str] = Field(default=None, description="Audience if learned")
    core_themes: Optional[list[str]] = Field(default=None, description="Themes if learned")
    author_goals: Optional[list[str]] = Field(default=None, description="Goals if learned")
    phase: Optional[str] = Field(default=None, description="New phase if transitioning")
    editorial_notes: Optional[str] = Field(default=None, description="Editorial notes if shared")
    new_chapter: Optional[dict] = Field(default=None, description="New chapter to add")
    chapter_status_update: Optional[dict] = Field(default=None, description="Chapter status change")


def set_output(name: str, value: str):
    """Set a step output for GitHub Actions."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            if "\n" in value:
                import uuid

                delimiter = uuid.uuid4().hex
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")


def load_existing_config(repo) -> Optional[dict]:
    """Load existing book.yaml if it exists."""
    try:
        content = repo.get_contents(".ai-context/book.yaml")
        return yaml.safe_load(content.decoded_content.decode("utf-8"))
    except Exception:
        return None


def create_initial_config(insights: dict) -> dict:
    """Create initial book.yaml from conversation insights."""
    now = datetime.now().isoformat()

    config = {
        "title": insights.get("title", "Untitled Book"),
        "subtitle": None,
        "author": insights.get("author", ""),
        "target_audience": insights.get("target_audience"),
        "core_themes": insights.get("core_themes", []),
        "author_goals": insights.get("author_goals", []),
        "phase": "new",
        "target_word_count": insights.get("target_word_count"),
        "target_chapters": insights.get("target_chapters"),
        "chapters": [],
        "default_persona": insights.get("default_persona"),
        "editorial_notes": insights.get("editorial_notes"),
        "created_at": now,
        "last_phase_change": now,
        "phase_history": [{"phase": "new", "started": now}],
    }

    return config


def merge_config_update(existing: dict, update: BookConfigUpdate) -> dict:
    """Merge an update into existing config."""
    config = existing.copy()
    now = datetime.now().isoformat()

    # Update simple fields if provided
    if update.title:
        config["title"] = update.title
    if update.author:
        config["author"] = update.author
    if update.target_audience:
        config["target_audience"] = update.target_audience
    if update.editorial_notes:
        config["editorial_notes"] = update.editorial_notes

    # Merge list fields
    if update.core_themes:
        existing_themes = set(config.get("core_themes", []))
        config["core_themes"] = list(existing_themes | set(update.core_themes))
    if update.author_goals:
        existing_goals = set(config.get("author_goals", []))
        config["author_goals"] = list(existing_goals | set(update.author_goals))

    # Handle phase transition
    if update.phase and update.phase != config.get("phase"):
        config["phase"] = update.phase
        config["last_phase_change"] = now
        if "phase_history" not in config:
            config["phase_history"] = []
        config["phase_history"].append({"phase": update.phase, "started": now})

    # Handle new chapter
    if update.new_chapter:
        if "chapters" not in config:
            config["chapters"] = []
        config["chapters"].append(update.new_chapter)

    # Handle chapter status update
    if update.chapter_status_update:
        chapter_name = update.chapter_status_update.get("name")
        new_status = update.chapter_status_update.get("status")
        for chapter in config.get("chapters", []):
            if chapter.get("name") == chapter_name:
                chapter["status"] = new_status
                break

    return config


def create_config_pr(
    repo,
    config: dict,
    title: str,
    body: str,
    branch_name: str,
    source_issue: Optional[int] = None,
) -> str:
    """
    Create a PR to update book.yaml.

    Returns the PR URL.
    """
    # Get default branch
    default_branch = repo.default_branch

    # Create new branch from default
    ref = repo.get_git_ref(f"heads/{default_branch}")
    repo.create_git_ref(f"refs/heads/{branch_name}", ref.object.sha)

    # Format YAML
    yaml_content = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Check if file exists
    try:
        existing = repo.get_contents(".ai-context/book.yaml", ref=default_branch)
        # Update existing file
        repo.update_file(
            ".ai-context/book.yaml",
            f"chore: update book configuration\n\n{body[:200]}",
            yaml_content,
            existing.sha,
            branch=branch_name,
        )
    except Exception:
        # Create new file (and directory if needed)
        repo.create_file(
            ".ai-context/book.yaml",
            f"chore: initialize book configuration\n\n{body[:200]}",
            yaml_content,
            branch=branch_name,
        )

    # Create PR
    pr_body = body
    if source_issue:
        pr_body += f"\n\n---\nSource: #{source_issue}"

    pr = repo.create_pull(
        title=title,
        body=pr_body,
        head=branch_name,
        base=default_branch,
    )

    return pr.html_url


def format_config_diff(old: Optional[dict], new: dict) -> str:
    """Format a human-readable diff of config changes."""
    lines = []

    if not old:
        lines.append("## New Book Configuration")
        lines.append("")
        lines.append("I've learned enough about your project to create an initial configuration:")
        lines.append("")
        if new.get("title"):
            lines.append(f"- **Title:** {new['title']}")
        if new.get("target_audience"):
            lines.append(f"- **Audience:** {new['target_audience'][:100]}...")
        if new.get("core_themes"):
            lines.append(f"- **Themes:** {', '.join(new['core_themes'][:3])}")
        if new.get("phase"):
            lines.append(f"- **Phase:** {new['phase']}")
    else:
        lines.append("## Configuration Update")
        lines.append("")
        lines.append("Based on our conversation, I'd like to update your book configuration:")
        lines.append("")

        # Show what changed
        for key in ["title", "author", "target_audience", "phase"]:
            if new.get(key) != old.get(key):
                lines.append(f"- **{key}:** {old.get(key)} → {new.get(key)}")

        # Show added themes
        old_themes = set(old.get("core_themes", []))
        new_themes = set(new.get("core_themes", []))
        added_themes = new_themes - old_themes
        if added_themes:
            lines.append(f"- **New themes:** {', '.join(added_themes)}")

    lines.append("")
    lines.append("Review the PR and merge when you're happy with it.")

    return "\n".join(lines)


def main():
    """
    Create or update book configuration via PR.

    Environment variables:
    - GITHUB_TOKEN: Required
    - GITHUB_REPOSITORY: Required
    - UPDATE_JSON: JSON string with BookConfigUpdate fields
    - SOURCE_ISSUE: Optional issue number that triggered this
    - PR_TITLE: Optional custom PR title
    """
    import json

    update_json = os.environ.get("UPDATE_JSON", "{}")
    source_issue = int(os.environ.get("SOURCE_ISSUE", 0)) or None
    pr_title = os.environ.get("PR_TITLE", "Update book configuration")

    try:
        update_data = json.loads(update_json)
        update = BookConfigUpdate(**update_data)
    except Exception as e:
        print(f"ERROR: Invalid UPDATE_JSON: {e}")
        sys.exit(1)

    gh = get_github_client()
    repo = get_repo(gh)

    # Load existing config
    existing = load_existing_config(repo)

    # Create or merge config
    if existing:
        new_config = merge_config_update(existing, update)
    else:
        # Convert update to initial config format
        new_config = create_initial_config(update.model_dump(exclude_none=True))

    # Generate diff description
    diff_text = format_config_diff(existing, new_config)

    # Create unique branch name
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"ai-editor/config-update-{timestamp}"

    # Create PR
    try:
        pr_url = create_config_pr(
            repo=repo,
            config=new_config,
            title=pr_title,
            body=diff_text,
            branch_name=branch_name,
            source_issue=source_issue,
        )
        print(f"Created PR: {pr_url}")
        set_output("pr_url", pr_url)
        set_output("success", "true")
    except Exception as e:
        print(f"ERROR creating PR: {e}")
        set_output("success", "false")
        set_output("error", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
