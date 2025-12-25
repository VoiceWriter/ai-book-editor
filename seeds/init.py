#!/usr/bin/env python3
"""
Initialize a repository for AI Book Editor.

Usage:
    python seeds/init.py                        # Init with default repo
    python seeds/init.py --repo owner/repo      # Init specific repo
    python seeds/init.py --labels               # Create labels only
    python seeds/init.py --templates            # Create templates only
    python seeds/init.py --dry-run              # Show what would be created

This creates:
    1. All required GitHub labels (phases, personas, workflow states)
    2. Issue templates for voice memos, questions, reviews
    3. .ai-context directory structure

Authentication (in priority order):
    1. GitHub App: AI_EDITOR_APP_ID + AI_EDITOR_PRIVATE_KEY
    2. Personal token: GITHUB_TOKEN
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

# Add parent for imports if running directly
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from github import Auth, Github, GithubException, GithubIntegration
    from github.Repository import Repository
except ImportError:
    print("Install PyGithub: pip install PyGithub")
    sys.exit(1)


# Complete label definitions
LABELS = [
    # === Core Workflow Labels ===
    {"name": "voice_transcription", "color": "1D76DB", "description": "Voice memo to process"},
    {"name": "ai-reviewed", "color": "0E8A16", "description": "AI has analyzed this content"},
    {"name": "pr-created", "color": "5319E7", "description": "PR exists for this issue"},
    {"name": "awaiting-author", "color": "FBCA04", "description": "Blocked on author input"},
    {"name": "ai-question", "color": "F9D0C4", "description": "AI question for author"},
    {"name": "ai-suggestion", "color": "D4C5F9", "description": "AI-initiated suggestion"},
    {"name": "knowledge-extracted", "color": "C2E0C6", "description": "Answer stored in knowledge base"},
    {"name": "ai-generated", "color": "6F42C1", "description": "AI generated content"},
    {"name": "ai-learning", "color": "FBCA04", "description": "AI self-improvement"},
    {"name": "ai-responded", "color": "0E8A16", "description": "AI has responded to this issue"},
    # === Content Organization ===
    {"name": "chapter", "color": "BFD4F2", "description": "Chapter tracking"},
    {"name": "structural", "color": "D93F0B", "description": "Structural issue"},
    {"name": "voice-memo", "color": "0366D6", "description": "From voice memo"},
    {"name": "whole-book", "color": "C5DEF5", "description": "Whole manuscript analysis"},
    {"name": "ask-editor", "color": "B4D3FF", "description": "Question for AI editor"},
    {"name": "quick-review", "color": "E8E8E8", "description": "Quick review requested"},
    # === Editorial Phase Labels ===
    {
        "name": "phase:discovery",
        "color": "7057ff",
        "description": "Editor asking questions before feedback",
    },
    {"name": "phase:feedback", "color": "0075ca", "description": "Editorial feedback phase"},
    {"name": "phase:revision", "color": "e4e669", "description": "Author revising based on feedback"},
    {"name": "phase:polish", "color": "0e8a16", "description": "Final polish phase"},
    {"name": "phase:complete", "color": "1d7c1d", "description": "Editorial work complete"},
    {"name": "phase:hold", "color": "d4c5f9", "description": "On hold for author reflection"},
    # === Persona Override Labels ===
    {"name": "persona:margot", "color": "E11D48", "description": "Sharp, no-nonsense editor"},
    {"name": "persona:sage", "color": "10B981", "description": "Nurturing, encouraging editor"},
    {"name": "persona:blueprint", "color": "3B82F6", "description": "Structure-focused editor"},
    {"name": "persona:sterling", "color": "F59E0B", "description": "Market-aware, commercial editor"},
    {"name": "persona:the-axe", "color": "7C3AED", "description": "Brutal cutting specialist"},
    {"name": "persona:cheerleader", "color": "EC4899", "description": "Pure encouragement"},
    {"name": "persona:ivory-tower", "color": "6366F1", "description": "Academic, literary craft"},
    {"name": "persona:bestseller", "color": "F97316", "description": "Maximum readability focus"},
]


# Issue templates to create
ISSUE_TEMPLATES = [
    {
        "name": "voice-transcription.md",
        "content": """---
name: Voice Transcription
about: Submit a voice memo transcript for AI editorial review
title: "[Voice] "
labels: voice_transcription
assignees: ''
---

## Voice Memo Transcript

<!-- Paste your voice memo transcript below -->



---

## How are you feeling about this? (Optional)

<!--
Help your editor understand where you're at:
- Is this a rough first draft? Polished and ready for feedback?
- Any parts you're particularly proud of or unsure about?
- What kind of feedback would be most helpful?

Leave blank to let the editor ask you these questions.
-->



---

## Preferences (check any that apply)

- [ ] **Skip discovery** - Give me feedback immediately, don't ask questions first
- [ ] **Quick review** - Just catch obvious issues, no deep dive
- [ ] **Be gentle** - This is vulnerable material, please lead with encouragement
- [ ] **Be brutal** - Don't hold back, I can take it

---

## Editor Preference (optional)

<!-- Uncomment ONE line to request a specific editor persona: -->
<!-- persona:margot - Sharp, no-nonsense, later drafts -->
<!-- persona:sage - Nurturing, early drafts, encouragement -->
<!-- persona:blueprint - Structure-focused, pacing -->
<!-- persona:sterling - Market-aware, commercial strategy -->
<!-- persona:the-axe - Brutal cutting, bloated manuscripts -->
<!-- persona:cheerleader - Pure encouragement, writer's block -->
<!-- persona:ivory-tower - Academic rigor, literary craft -->
<!-- persona:bestseller - Maximum readability, commercial -->
""",
    },
    {
        "name": "ask-the-editor.md",
        "content": """---
name: Ask the Editor
about: Ask your AI editor a question about your writing
title: "[Question] "
labels: ask-editor
assignees: ''
---

## My Question

<!-- What do you want to ask your editor? -->



---

## Context

<!--
Optional: Provide any relevant context
- Which chapter or section this relates to
- What you've already tried
- What's making you unsure
-->



---

## Editor Preference (optional)

<!-- Uncomment ONE line to request a specific editor perspective: -->
<!-- persona:margot - Sharp, direct feedback -->
<!-- persona:sage - Gentle, encouraging guidance -->
<!-- persona:blueprint - Structure and organization focus -->
<!-- persona:sterling - Market and positioning insight -->
<!-- persona:ivory-tower - Craft and literary perspective -->
""",
    },
    {
        "name": "ai-question.md",
        "content": """---
name: AI Question
about: A question from the AI editor that needs author input
title: "[AI Question] "
labels: ai-question, awaiting-author
assignees: ''
---

## Question from AI Editor

<!-- The AI editor will fill in the question here -->

---

**Why I'm asking:** <!-- Context for why this information is needed -->

**How to respond:** Just reply to this issue with your answer. I'll extract the key information and remember it for future editing sessions.

---
*This question was automatically generated by AI Book Editor.*
""",
    },
    {
        "name": "whole-book-review.md",
        "content": """---
name: Whole Book Review
about: Request a complete manuscript analysis across all chapters
title: "[Review] Complete Manuscript Analysis"
labels: whole-book
assignees: ''
---

## Request Whole Book Analysis

I'd like a comprehensive analysis of the complete manuscript, including:

- [ ] **Thematic Threads** - What themes run through the book?
- [ ] **Consistency Check** - Any contradictions across chapters?
- [ ] **Repetition Detection** - Content that's repeated?
- [ ] **Promise/Payoff Tracking** - What setups pay off? What's dangling?
- [ ] **Structural Assessment** - Does the chapter order make sense?

---

## Specific Concerns (Optional)

<!-- Are there any specific areas you want the editor to focus on? -->



---

## Discovery Questions

Before diving in, my editor may ask:

1. What's the arc of your book in three sentences?
2. Which chapters feel strongest? Which feel wobbly?
3. What promise do you make in chapter one?

<!-- Feel free to answer these proactively, or wait for your editor to ask -->



---

## Editor Preference (optional)

<!-- Uncomment ONE line: -->
<!-- persona:margot - Sharp overview, market-aware -->
<!-- persona:blueprint - Deep structural analysis -->
<!-- persona:ivory-tower - Literary craft focus -->
""",
    },
    {
        "name": "editorial-hold.md",
        "content": """---
name: Editorial Hold
about: Put a piece on hold for reflection time
title: "[Hold] "
labels: phase:hold
assignees: ''
---

## Taking a Break

I'm putting this piece on hold to let it breathe.

**Piece:** <!-- Which issue/chapter is on hold -->

**Planned reflection time:** <!-- How long do you want to sit with it? -->

---

## What I'm Sitting With

<!--
Optional: What are you hoping to gain clarity on during this hold?
- A structural question?
- A voice decision?
- General marination?
-->



---

## Reminder

When you're ready to continue, comment on this issue or remove the `phase:hold` label.

*Sometimes the best editorial move is to wait.*
""",
    },
]


# .ai-context template files
AI_CONTEXT_FILES = {
    "config.yaml": """# AI Book Editor Configuration
# See: https://github.com/VoiceWriter/ai-book-editor

# Default editor persona (override per-issue with persona:* labels)
# Options: margot, sage, blueprint, sterling, the-axe, cheerleader, ivory-tower, bestseller
persona: margot

# Book project phase
# Options: new, drafting, revising, polishing, complete
phase: new

# Chapter configuration (update as you write)
chapters:
  # - path: chapters/01-introduction.md
  #   title: Introduction
  #   status: draft  # draft, review, revised, complete
""",
    "knowledge.jsonl": """{"question": "What is this book about?", "answer": ""}
{"question": "Who is the target reader?", "answer": ""}
{"question": "What tone should the book have?", "answer": ""}
""",
    "terminology.yaml": """# Terminology preferences
# The AI editor will use these terms consistently

# Example:
# voice-to-text: preferred over "speech-to-text"
# AI editor: preferred over "AI assistant" or "bot"
""",
    "themes.yaml": """# Core themes of your book
# The AI editor will track these through your manuscript

themes: []
  # - name: "theme name"
  #   description: "What this theme means to you"
""",
    "author-preferences.yaml": """# Your writing preferences
# The AI editor will respect these

style:
  oxford_comma: true
  contractions: true  # I'm, don't, etc.
  em_dashes: true
  sentence_variety: true

avoid:
  - passive voice (when possible)
  - clichés
  # Add your pet peeves here
""",
}


def get_github_client(repo_name: str) -> Github:
    """Get authenticated GitHub client."""
    app_id = os.environ.get("AI_EDITOR_APP_ID")
    private_key = os.environ.get("AI_EDITOR_PRIVATE_KEY")

    private_key_path = os.environ.get("AI_EDITOR_PRIVATE_KEY_PATH")
    if private_key_path and os.path.exists(private_key_path):
        with open(private_key_path) as f:
            private_key = f.read()

    if app_id and private_key:
        try:
            if "\\n" in private_key:
                private_key = private_key.replace("\\n", "\n")

            auth = Auth.AppAuth(int(app_id), private_key)
            gi = GithubIntegration(auth=auth)

            owner = repo_name.split("/")[0]
            installation = gi.get_installations()[0]

            for inst in gi.get_installations():
                if inst.raw_data.get("account", {}).get("login") == owner:
                    installation = inst
                    break

            access_token = gi.get_access_token(installation.id)
            print(f"Using GitHub App authentication (installation {installation.id})")
            return Github(auth=Auth.Token(access_token.token))

        except Exception as e:
            print(f"GitHub App auth failed: {e}")
            print("Falling back to GITHUB_TOKEN...")

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: No authentication available")
        print("Set either:")
        print("  - AI_EDITOR_APP_ID + AI_EDITOR_PRIVATE_KEY (for bot identity)")
        print("  - GITHUB_TOKEN (for personal token)")
        sys.exit(1)

    print("Using personal access token authentication")
    return Github(auth=Auth.Token(token))


def create_labels(repo: Repository, dry_run: bool = False, verbose: bool = True) -> dict:
    """
    Create all required labels in repository.

    Returns:
        dict with 'created', 'existing', 'failed' counts
    """
    existing_labels = {lbl.name: lbl for lbl in repo.get_labels()}
    stats = {"created": 0, "existing": 0, "updated": 0, "failed": 0}

    for label in LABELS:
        name = label["name"]

        if name in existing_labels:
            existing = existing_labels[name]
            # Check if color/description needs update
            if existing.color != label["color"] or existing.description != label.get(
                "description", ""
            ):
                if dry_run:
                    if verbose:
                        print(f"  Would update: {name}")
                    stats["updated"] += 1
                else:
                    try:
                        existing.edit(
                            name=name,
                            color=label["color"],
                            description=label.get("description", ""),
                        )
                        if verbose:
                            print(f"  Updated: {name}")
                        stats["updated"] += 1
                    except GithubException as e:
                        print(f"  Failed to update {name}: {e}")
                        stats["failed"] += 1
            else:
                if verbose:
                    print(f"  Exists: {name}")
                stats["existing"] += 1
            continue

        if dry_run:
            if verbose:
                print(f"  Would create: {name}")
            stats["created"] += 1
        else:
            try:
                repo.create_label(
                    name=name,
                    color=label["color"],
                    description=label.get("description", ""),
                )
                if verbose:
                    print(f"  Created: {name}")
                stats["created"] += 1
            except GithubException as e:
                print(f"  Failed to create {name}: {e}")
                stats["failed"] += 1

    return stats


def create_issue_templates(
    repo: Repository, dry_run: bool = False, verbose: bool = True
) -> dict:
    """
    Create issue templates in repository.

    Returns:
        dict with 'created', 'existing', 'failed' counts
    """
    stats = {"created": 0, "existing": 0, "updated": 0, "failed": 0}

    for template in ISSUE_TEMPLATES:
        path = f".github/ISSUE_TEMPLATE/{template['name']}"

        try:
            existing = repo.get_contents(path)
            if verbose:
                print(f"  Exists: {path}")
            stats["existing"] += 1
            continue
        except GithubException as e:
            if e.status != 404:
                print(f"  Failed to check {path}: {e}")
                stats["failed"] += 1
                continue

        if dry_run:
            if verbose:
                print(f"  Would create: {path}")
            stats["created"] += 1
        else:
            try:
                repo.create_file(
                    path=path,
                    message=f"Add issue template: {template['name']}",
                    content=template["content"],
                )
                if verbose:
                    print(f"  Created: {path}")
                stats["created"] += 1
            except GithubException as e:
                print(f"  Failed to create {path}: {e}")
                stats["failed"] += 1

    return stats


def create_ai_context(repo: Repository, dry_run: bool = False, verbose: bool = True) -> dict:
    """
    Create .ai-context directory with template files.

    Returns:
        dict with 'created', 'existing', 'failed' counts
    """
    stats = {"created": 0, "existing": 0, "failed": 0}

    for filename, content in AI_CONTEXT_FILES.items():
        path = f".ai-context/{filename}"

        try:
            existing = repo.get_contents(path)
            if verbose:
                print(f"  Exists: {path}")
            stats["existing"] += 1
            continue
        except GithubException as e:
            if e.status != 404:
                print(f"  Failed to check {path}: {e}")
                stats["failed"] += 1
                continue

        if dry_run:
            if verbose:
                print(f"  Would create: {path}")
            stats["created"] += 1
        else:
            try:
                repo.create_file(
                    path=path,
                    message=f"Add AI context file: {filename}",
                    content=content,
                )
                if verbose:
                    print(f"  Created: {path}")
                stats["created"] += 1
            except GithubException as e:
                print(f"  Failed to create {path}: {e}")
                stats["failed"] += 1

    return stats


def init_repository(
    repo_name: str,
    do_labels: bool = True,
    do_templates: bool = True,
    do_context: bool = True,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Initialize a repository for AI Book Editor.

    Args:
        repo_name: Repository in owner/repo format
        do_labels: Create labels
        do_templates: Create issue templates
        do_context: Create .ai-context files
        dry_run: Show what would be created without making changes
        verbose: Print progress

    Returns:
        dict with stats for each category
    """
    if verbose:
        action = "Checking" if dry_run else "Initializing"
        print(f"{action} {repo_name}...")

    gh = get_github_client(repo_name)
    repo = gh.get_repo(repo_name)

    results = {}

    if do_labels:
        if verbose:
            print("\nLabels:")
        results["labels"] = create_labels(repo, dry_run, verbose)

    if do_templates:
        if verbose:
            print("\nIssue Templates:")
        results["templates"] = create_issue_templates(repo, dry_run, verbose)

    if do_context:
        if verbose:
            print("\n.ai-context Files:")
        results["context"] = create_ai_context(repo, dry_run, verbose)

    return results


def print_summary(results: dict, dry_run: bool = False):
    """Print summary of initialization."""
    print("\n" + "=" * 40)
    action = "Would be" if dry_run else ""
    print(f"Summary{' (dry run)' if dry_run else ''}:")

    for category, stats in results.items():
        created = stats.get("created", 0)
        existing = stats.get("existing", 0)
        updated = stats.get("updated", 0)
        failed = stats.get("failed", 0)

        parts = []
        if created:
            parts.append(f"{created} {'would be ' if dry_run else ''}created")
        if updated:
            parts.append(f"{updated} {'would be ' if dry_run else ''}updated")
        if existing:
            parts.append(f"{existing} existing")
        if failed:
            parts.append(f"{failed} failed")

        print(f"  {category}: {', '.join(parts)}")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize repository for AI Book Editor"
    )
    parser.add_argument(
        "--repo",
        default="VoiceWriter/ai-book-editor-test",
        help="Target repository (owner/repo)",
    )
    parser.add_argument("--labels", action="store_true", help="Create labels only")
    parser.add_argument("--templates", action="store_true", help="Create templates only")
    parser.add_argument("--context", action="store_true", help="Create .ai-context only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    args = parser.parse_args()

    verbose = not args.quiet

    # Default: do everything if no specific flags
    do_all = not (args.labels or args.templates or args.context)
    do_labels = args.labels or do_all
    do_templates = args.templates or do_all
    do_context = args.context or do_all

    results = init_repository(
        repo_name=args.repo,
        do_labels=do_labels,
        do_templates=do_templates,
        do_context=do_context,
        dry_run=args.dry_run,
        verbose=verbose,
    )

    if verbose:
        print_summary(results, args.dry_run)
        print("\nDone!")


if __name__ == "__main__":
    main()
