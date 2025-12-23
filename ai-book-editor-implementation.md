# AI Book Editor: Complete Implementation Guide

> A GitHub-native AI editorial system for transforming voice memos and written fragments into polished books.

**Target Repositories:**
- Action Repository: `VoiceWriter/ai-book-editor`
- Test/Book Repository: `VoiceWriter/ai-book-editor-test`

**Architecture Principle:** 100% GitHub-native. No external servers, no databases. Just:
- GitHub Issues (input, discussion, state management)
- GitHub Actions (AI processing via Claude API)
- GitHub PRs (editorial output, traceability)
- GitHub repo (book content, knowledge base)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Repository Structures](#repository-structures)
3. [Phase 1: MVP Voice Memo Pipeline](#phase-1-mvp-voice-memo-pipeline)
4. [Phase 2: PR Editorial Review](#phase-2-pr-editorial-review)
5. [Phase 3: Knowledge Base System](#phase-3-knowledge-base-system)
6. [Phase 4: Scheduled Book Review](#phase-4-scheduled-book-review)
7. [Phase 5: AI Self-Improvement](#phase-5-ai-self-improvement)
8. [Editorial Configuration Files](#editorial-configuration-files)
9. [Issue and PR Templates](#issue-and-pr-templates)
10. [iOS Shortcut Setup](#ios-shortcut-setup)
11. [Testing with `act`](#testing-with-act)
12. [Traceability System](#traceability-system)

---

## Design Philosophy: Use Existing Actions

**Reference:** [sdras/awesome-actions](https://github.com/sdras/awesome-actions) — curated list of popular, well-maintained GitHub Actions.

**Principle:** Before writing custom code, check if a well-supported action already exists. Prefer battle-tested community actions over custom implementations.

### Recommended Actions to Use

| Task | Recommended Action | Notes |
|------|-------------------|-------|
| **PRs & Issues** | | |
| Create PRs | [peter-evans/create-pull-request](https://github.com/peter-evans/create-pull-request) | 5k+ stars, actively maintained |
| Create Issues | [peter-evans/create-issue-from-file](https://github.com/peter-evans/create-issue-from-file) | Same maintainer, reliable |
| Comment on Issues/PRs | [peter-evans/create-or-update-comment](https://github.com/peter-evans/create-or-update-comment) | Handles updates elegantly |
| Find linked issues | [peter-evans/find-comment](https://github.com/peter-evans/find-comment) | Find existing comments |
| **Labels & Projects** | | |
| Add Labels | [actions/github-script](https://github.com/actions/github-script) | Official, flexible |
| Auto-label PRs | [actions/labeler](https://github.com/actions/labeler) | Official auto-labeling |
| Manage Issues | [actions-cool/issues-helper](https://github.com/actions-cool/issues-helper) | Comprehensive issue ops |
| **Git Operations** | | |
| Commit Files | [stefanzweifel/git-auto-commit-action](https://github.com/stefanzweifel/git-auto-commit-action) | Clean file commits |
| Push Changes | [ad-m/github-push-action](https://github.com/ad-m/github-push-action) | Push to branches |
| **Workflow Utilities** | | |
| Setup Python | [actions/setup-python](https://github.com/actions/setup-python) | Official, always use |
| Cache Dependencies | [actions/cache](https://github.com/actions/cache) | Speed up pip installs |
| Checkout | [actions/checkout](https://github.com/actions/checkout) | Official checkout |
| **Notifications** | | |
| Slack Notify | [slackapi/slack-github-action](https://github.com/slackapi/slack-github-action) | Official Slack action |
| **Specialized** | | |
| Whisper Transcription | [appleboy/whisper-action](https://github.com/appleboy/whisper-action) | If processing audio directly |
| Release Notes | [release-drafter/release-drafter](https://github.com/release-drafter/release-drafter) | Auto changelog |

**Full List:** See [sdras/awesome-actions](https://github.com/sdras/awesome-actions) for the complete curated list.

### When to Write Custom Code

Only write custom Python scripts for:
1. **Claude API calls** — No existing action for this
2. **Complex prompt construction** — Needs editorial context loading
3. **Knowledge base operations** — Custom format and logic
4. **Response parsing** — Extracting structured data from Claude

### When to Use Existing Actions

Use existing actions for:
1. **All GitHub operations** — Creating PRs, issues, comments, labels
2. **File operations** — Committing, pushing, branch management
3. **Workflow utilities** — Caching, setup, checkout

This keeps our custom code focused on the AI editorial logic, not GitHub plumbing.

### The Handoff Pattern

**Critical Architecture Decision:** Python scripts should **output files and step outputs**, not make GitHub API calls directly. The workflow then uses existing actions to perform GitHub operations.

```
┌─────────────────────────────────────────────────────────────────┐
│  PYTHON SCRIPT                                                  │
│  - Load context (editorial files, knowledge base)               │
│  - Call Claude API                                              │
│  - Parse response                                               │
│  - Write output files (markdown, json)                          │
│  - Set step outputs (echo "key=value" >> $GITHUB_OUTPUT)        │
│  - NO direct GitHub API calls for PRs/issues/comments           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  EXISTING GITHUB ACTIONS                                        │
│  - peter-evans/create-pull-request (create PRs)                 │
│  - peter-evans/create-or-update-comment (post comments)         │
│  - peter-evans/create-issue-from-file (create issues)           │
│  - actions/github-script (add labels, other API calls)          │
└─────────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Battle-tested actions handle edge cases (rate limits, retries, permissions)
- Easier to debug (can see exactly what each step does)
- Simpler Python code (just AI logic, no GitHub SDK)
- Workflow files are self-documenting
- Can swap actions without changing Python code

**Example Python output pattern:**

```python
# In Python script
import os

# Write content to file for action to use
with open('output/comment.md', 'w') as f:
    f.write(ai_response)

# Set step outputs for workflow
with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
    f.write(f"has_content=true\n")
    f.write(f"target_file=chapters/03-workflow.md\n")
```

```yaml
# In workflow
- name: Run AI analysis
  id: analyze
  run: python analyze.py

- name: Post comment
  uses: peter-evans/create-or-update-comment@v4
  with:
    body-path: output/comment.md
```

---

## Architecture Overview

### The Three Workflows

```
┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW 1: Voice-to-AI-Editor                                 │
│  Voice memo → iOS Shortcut → GitHub Issue → AI processes →     │
│  Discussion → PR created → Review → Merge → Published          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW 2: Human-Text-to-AI-Editor                            │
│  Write in VS Code → Push to branch → AI reviews PR →           │
│  Iterate on feedback → Merge → Published                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW 3: Autonomous AI Editorial                            │
│  Scheduled review → AI analyzes full book → Creates issues →   │
│  Author responds → PR if approved → Merge → Published          │
└─────────────────────────────────────────────────────────────────┘
```

### State Management via GitHub Issues

**No markdown files for state.** GitHub Issues ARE the state:

| State | Meaning |
|-------|---------|
| Open issues | Work to do |
| Closed issues | Work complete |
| No open issues | Book done OR awaiting author content |

**Issue Labels:**

| Label | Color | Purpose |
|-------|-------|---------|
| `voice_transcription` | `#1D76DB` (blue) | Voice memo to process |
| `ai-reviewed` | `#0E8A16` (green) | AI has analyzed |
| `pr-created` | `#5319E7` (purple) | PR exists for this issue |
| `awaiting-author` | `#FBCA04` (yellow) | Blocked on author input |
| `ai-suggestion` | `#D4C5F9` (lavender) | AI-initiated suggestion |
| `ai-question` | `#F9D0C4` (peach) | AI question for author |
| `knowledge-extracted` | `#C2E0C6` (mint) | Answer stored in KB |
| `chapter` | `#BFD4F2` (light blue) | Chapter tracking |
| `structural` | `#D93F0B` (red-orange) | Structure issue |
| `draft` | `#E4E669` (lime) | First draft stage |
| `dev-edit` | `#BFDADC` (teal) | Developmental edit |
| `line-edit` | `#C5DEF5` (sky) | Line edit stage |
| `copy-edit` | `#D4C5F9` (lavender) | Copy edit stage |
| `final` | `#0E8A16` (green) | Ready for publication |

---

## Repository Structures

### Action Repository: `ai-book-editor/`

```
ai-book-editor/
├── .github/
│   ├── workflows/
│   │   └── test.yml                    # Self-test on push
│   └── scripts/
│       ├── __init__.py
│       ├── process_transcription.py    # Core: analyze voice memos
│       ├── respond_to_comment.py       # Handle @ai-editor commands
│       ├── review_pr.py                # Editorial review of PRs
│       ├── scheduled_review.py         # Full book analysis
│       ├── extract_knowledge.py        # Store answers in KB
│       ├── learn_from_feedback.py      # AI self-improvement
│       └── utils/
│           ├── __init__.py
│           ├── github_client.py        # GitHub API helpers
│           ├── claude_client.py        # Claude API helpers
│           └── knowledge_base.py       # KB loading/formatting
├── prompts/
│   ├── transcription_analysis.md       # Prompt for voice memos
│   ├── editorial_review.md             # Prompt for PR review
│   ├── full_book_review.md             # Prompt for scheduled review
│   └── knowledge_extraction.md         # Prompt for extracting answers
├── action.yml                          # Composite action definition
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
└── .actrc                              # Local testing config
```

### Book Repository: `ai-book-editor-test/` (or any book repo)

```
my-book/
├── .github/
│   ├── workflows/
│   │   ├── process-transcription.yml   # Voice memo pipeline
│   │   ├── respond-to-feedback.yml     # @ai-editor commands
│   │   ├── review-pr.yml               # PR editorial review
│   │   ├── scheduled-review.yml        # Weekly book review
│   │   ├── process-ai-question.yml     # Extract knowledge
│   │   └── learn-from-feedback.yml     # AI self-improvement
│   ├── ISSUE_TEMPLATE/
│   │   ├── voice-transcription.md
│   │   ├── chapter-tracking.md
│   │   └── ai-question.md
│   └── PULL_REQUEST_TEMPLATE.md
├── chapters/
│   └── *.md                            # Book content
├── .ai-context/
│   ├── knowledge.jsonl                 # Q&A pairs from author
│   ├── terminology.yaml                # Term preferences
│   ├── themes.yaml                     # Book themes
│   └── author-preferences.yaml         # Style preferences
├── EDITOR_PERSONA.md                   # AI personality (tunable)
├── EDITORIAL_GUIDELINES.md             # Hard rules (non-negotiable)
├── GLOSSARY.md                         # Terminology consistency
├── style-guide.md                      # Formatting, structure
├── outline.md                          # Book structure reference
├── README.md
└── .gitignore
```

---

## Phase 1: MVP Voice Memo Pipeline

**Goal:** Complete pipeline from voice memo to merged PR. This is the core workflow.

### Task 1.1: Create `requirements.txt`

**File:** `ai-book-editor/requirements.txt`

```
# AI/LLM
anthropic>=0.39.0

# GitHub API - for READING data (issues, files, comments)
# Note: WRITING operations (PRs, comments, labels) use existing Actions
# See: https://github.com/sdras/awesome-actions
PyGithub>=2.1.1

# Config/data handling
pyyaml>=6.0
```

> **Architecture Note:** We use PyGithub for *reading* GitHub data (issue content, repo files, comments). All *write* operations (creating PRs, posting comments, adding labels) use well-maintained existing actions like peter-evans/create-pull-request. This separation keeps our code focused on AI logic while leveraging battle-tested actions for GitHub operations.

### Task 1.2: Create `action.yml`

**File:** `ai-book-editor/action.yml`

```yaml
name: 'AI Book Editor'
description: 'GitHub-native AI editorial system for books'
author: 'VoiceWriter'

branding:
  icon: 'edit-3'
  color: 'purple'

inputs:
  anthropic-key:
    description: 'Anthropic API key for Claude'
    required: true
  github-token:
    description: 'GitHub token for API access'
    required: true
  mode:
    description: 'Operation mode: process-transcription, respond-comment, review-pr, scheduled-review'
    required: false
    default: 'process-transcription'
  style-guide:
    description: 'Path to style guide file'
    required: false
    default: './style-guide.md'
  issue-number:
    description: 'Issue number to process (for issue-based modes)'
    required: false
  pr-number:
    description: 'PR number to review (for PR mode)'
    required: false
  comment-body:
    description: 'Comment body (for respond-comment mode)'
    required: false

outputs:
  result:
    description: 'Result of the operation'
    value: ${{ steps.run.outputs.result }}

runs:
  using: 'composite'
  steps:
    - name: Setup Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install dependencies
      shell: bash
      run: pip install -r ${{ github.action_path }}/requirements.txt

    - name: Run AI Editor
      id: run
      shell: bash
      env:
        ANTHROPIC_API_KEY: ${{ inputs.anthropic-key }}
        GITHUB_TOKEN: ${{ inputs.github-token }}
        MODE: ${{ inputs.mode }}
        STYLE_GUIDE: ${{ inputs.style-guide }}
        ISSUE_NUMBER: ${{ inputs.issue-number }}
        PR_NUMBER: ${{ inputs.pr-number }}
        COMMENT_BODY: ${{ inputs.comment-body }}
        GITHUB_REPOSITORY: ${{ github.repository }}
      run: |
        case "$MODE" in
          process-transcription)
            python ${{ github.action_path }}/.github/scripts/process_transcription.py
            ;;
          respond-comment)
            python ${{ github.action_path }}/.github/scripts/respond_to_comment.py
            ;;
          review-pr)
            python ${{ github.action_path }}/.github/scripts/review_pr.py
            ;;
          scheduled-review)
            python ${{ github.action_path }}/.github/scripts/scheduled_review.py
            ;;
          *)
            echo "Unknown mode: $MODE"
            exit 1
            ;;
        esac
```

### Task 1.3: Create GitHub Client Utility

**File:** `ai-book-editor/.github/scripts/utils/github_client.py`

```python
"""GitHub API utilities for AI Book Editor."""

import os
from github import Github
from typing import Optional, List, Dict, Any


def get_github_client() -> Github:
    """Get authenticated GitHub client."""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable not set")
    return Github(token)


def get_repo(gh: Github, repo_name: Optional[str] = None):
    """Get repository object."""
    repo_name = repo_name or os.environ.get('GITHUB_REPOSITORY')
    if not repo_name:
        raise ValueError("Repository name not provided")
    return gh.get_repo(repo_name)


def get_issue(repo, issue_number: int):
    """Get issue by number."""
    return repo.get_issue(issue_number)


def get_pull_request(repo, pr_number: int):
    """Get PR by number."""
    return repo.get_pull(pr_number)


def read_file_content(repo, path: str, ref: str = None) -> Optional[str]:
    """Read file content from repo. Returns None if file doesn't exist."""
    try:
        kwargs = {'ref': ref} if ref else {}
        content = repo.get_contents(path, **kwargs)
        return content.decoded_content.decode('utf-8')
    except Exception:
        return None


def list_files_in_directory(repo, path: str, ref: str = None) -> List[str]:
    """List files in a directory."""
    try:
        kwargs = {'ref': ref} if ref else {}
        contents = repo.get_contents(path, **kwargs)
        return [c.name for c in contents if c.type == 'file']
    except Exception:
        return []


def create_branch(repo, branch_name: str, from_branch: str = None) -> bool:
    """Create a new branch. Returns True if created, False if exists."""
    from_branch = from_branch or repo.default_branch
    try:
        ref = repo.get_git_ref(f"heads/{from_branch}")
        repo.create_git_ref(f"refs/heads/{branch_name}", ref.object.sha)
        return True
    except Exception:
        return False  # Branch likely already exists


def create_or_update_file(
    repo,
    path: str,
    content: str,
    message: str,
    branch: str
) -> None:
    """Create or update a file in the repo."""
    try:
        # Try to get existing file
        file = repo.get_contents(path, ref=branch)
        repo.update_file(path, message, content, file.sha, branch=branch)
    except Exception:
        # File doesn't exist, create it
        repo.create_file(path, message, content, branch=branch)


def append_to_file(
    repo,
    path: str,
    content: str,
    message: str,
    branch: str,
    separator: str = "\n\n---\n\n"
) -> None:
    """Append content to an existing file."""
    try:
        file = repo.get_contents(path, ref=branch)
        existing = file.decoded_content.decode('utf-8')
        new_content = existing + separator + content
        repo.update_file(path, message, new_content, file.sha, branch=branch)
    except Exception:
        # File doesn't exist, create with just the new content
        repo.create_file(path, message, content, branch=branch)


def get_issue_comments(issue) -> List[Dict[str, Any]]:
    """Get all comments on an issue."""
    return [
        {
            'id': c.id,
            'body': c.body,
            'user': c.user.login,
            'created_at': c.created_at.isoformat()
        }
        for c in issue.get_comments()
    ]


def format_commit_message(
    type_: str,
    scope: str,
    description: str,
    body: str = None,
    source_issue: int = None,
    reviewed_by: str = "ai-editor",
    editorial_type: str = "addition"
) -> str:
    """Format a structured commit message."""
    msg = f"{type_}({scope}): {description}"
    
    if body:
        msg += f"\n\n{body}"
    
    msg += "\n"
    if source_issue:
        msg += f"\nSource: #{source_issue}"
    msg += f"\nReviewed-by: {reviewed_by}"
    msg += f"\nEditorial-type: {editorial_type}"
    
    return msg
```

### Task 1.4: Create Claude Client Utility

**File:** `ai-book-editor/.github/scripts/utils/claude_client.py`

```python
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
```

### Task 1.5: Create Knowledge Base Utility

**File:** `ai-book-editor/.github/scripts/utils/knowledge_base.py`

```python
"""Knowledge base utilities for AI Book Editor."""

import json
import yaml
from typing import Dict, List, Any, Optional
from .github_client import read_file_content


def load_knowledge_base(repo) -> Dict[str, Any]:
    """Load all knowledge base files from .ai-context/"""
    knowledge = {
        'qa_pairs': [],
        'terminology': {},
        'themes': [],
        'preferences': {}
    }
    
    # Load Q&A pairs
    qa_content = read_file_content(repo, '.ai-context/knowledge.jsonl')
    if qa_content:
        for line in qa_content.strip().split('\n'):
            if line.strip():
                try:
                    knowledge['qa_pairs'].append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    
    # Load terminology
    term_content = read_file_content(repo, '.ai-context/terminology.yaml')
    if term_content:
        try:
            knowledge['terminology'] = yaml.safe_load(term_content) or {}
        except yaml.YAMLError:
            pass
    
    # Load themes
    themes_content = read_file_content(repo, '.ai-context/themes.yaml')
    if themes_content:
        try:
            knowledge['themes'] = yaml.safe_load(themes_content) or []
        except yaml.YAMLError:
            pass
    
    # Load preferences
    prefs_content = read_file_content(repo, '.ai-context/author-preferences.yaml')
    if prefs_content:
        try:
            knowledge['preferences'] = yaml.safe_load(prefs_content) or {}
        except yaml.YAMLError:
            pass
    
    return knowledge


def format_knowledge_for_prompt(knowledge: Dict[str, Any]) -> Optional[str]:
    """Format knowledge base for inclusion in AI prompts."""
    sections = []
    
    if knowledge['qa_pairs']:
        qa_text = "\n".join([
            f"Q: {qa['question']}\nA: {qa['answer']}"
            for qa in knowledge['qa_pairs']
        ])
        sections.append(f"## Known Context (from author answers)\n\n{qa_text}")
    
    if knowledge['terminology']:
        terms = "\n".join([
            f"- Use '{v}' not '{k}'" if isinstance(v, str) else f"- {k}: {v}"
            for k, v in knowledge['terminology'].items()
        ])
        sections.append(f"## Terminology Preferences\n\n{terms}")
    
    if knowledge['themes']:
        if isinstance(knowledge['themes'], list):
            themes = "\n".join([f"- {t}" for t in knowledge['themes']])
        else:
            themes = str(knowledge['themes'])
        sections.append(f"## Central Themes\n\n{themes}")
    
    if knowledge['preferences']:
        prefs = yaml.dump(knowledge['preferences'], default_flow_style=False)
        sections.append(f"## Author Preferences\n\n{prefs}")
    
    return "\n\n".join(sections) if sections else None


def load_editorial_context(repo) -> Dict[str, Any]:
    """Load all editorial context files."""
    context = {}
    
    # Core editorial files
    context['persona'] = read_file_content(repo, 'EDITOR_PERSONA.md') or "No persona defined."
    context['guidelines'] = read_file_content(repo, 'EDITORIAL_GUIDELINES.md') or "No guidelines defined."
    context['glossary'] = read_file_content(repo, 'GLOSSARY.md')
    context['style_guide'] = read_file_content(repo, 'style-guide.md')
    
    # Knowledge base
    knowledge = load_knowledge_base(repo)
    context['knowledge'] = knowledge
    context['knowledge_formatted'] = format_knowledge_for_prompt(knowledge)
    
    # Chapter list
    from .github_client import list_files_in_directory
    chapters = list_files_in_directory(repo, 'chapters')
    context['chapters'] = [c for c in chapters if c.endswith('.md')]
    
    return context
```

### Task 1.6: Create `process_transcription.py`

**File:** `ai-book-editor/.github/scripts/process_transcription.py`

> **Note:** This script follows the handoff pattern — it outputs files and step outputs, letting the workflow use existing actions for GitHub operations.

```python
#!/usr/bin/env python3
"""
Process voice memo transcriptions from GitHub Issues.

This script:
1. Reads the transcript from the issue body
2. Loads editorial context (persona, guidelines, knowledge base)
3. Calls Claude to clean, analyze, and suggest placement
4. Outputs analysis to file for workflow to post as comment
5. Sets step outputs for workflow to use

DOES NOT: Make direct GitHub API calls for comments/labels (workflow handles that)
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import (
    get_github_client, get_repo, get_issue
)
from scripts.utils.claude_client import call_claude, build_editorial_prompt
from scripts.utils.knowledge_base import load_editorial_context


def set_output(name: str, value: str):
    """Set a step output for the GitHub Actions workflow."""
    output_file = os.environ.get('GITHUB_OUTPUT')
    if output_file:
        with open(output_file, 'a') as f:
            # Handle multiline values
            if '\n' in value:
                import uuid
                delimiter = uuid.uuid4().hex
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")


def main():
    # Get environment variables
    issue_number = int(os.environ.get('ISSUE_NUMBER', 0))
    if not issue_number:
        print("ERROR: ISSUE_NUMBER not set")
        sys.exit(1)
    
    # Initialize clients
    gh = get_github_client()
    repo = get_repo(gh)
    issue = get_issue(repo, issue_number)
    
    # Get transcript from issue body
    transcript = issue.body or ""
    if not transcript.strip():
        # Output error comment
        error_comment = "❌ No transcript found in issue body. Please add the voice memo transcript."
        Path('output').mkdir(exist_ok=True)
        Path('output/analysis-comment.md').write_text(error_comment)
        set_output('success', 'false')
        set_output('error', 'No transcript in issue body')
        sys.exit(1)
    
    # Load editorial context
    print("Loading editorial context...")
    context = load_editorial_context(repo)
    
    # Build the analysis prompt
    task = """Analyze this voice memo transcript and provide:

1. **Cleaned Transcript**: Fix grammar, punctuation, remove filler words (um, uh, like, you know), but preserve the author's voice and meaning exactly. Do not add new content or change the meaning.

2. **Content Analysis**: What is this about? What themes, topics, or ideas are present? How does it relate to the book's central themes?

3. **Suggested Placement**: Based on the existing chapters, where might this content fit?
   - Should it be added to an existing chapter? Which one and where?
   - Should it become a new chapter or section?
   - Is it notes/ideas for later development?

4. **Editorial Notes**: 
   - What's working well in this content?
   - What needs clarification or expansion?
   - Questions for the author about intent or meaning

5. **Ready for PR?**: Can this be integrated now, or does it need author input first?

Format your response with clear ### headers for each section."""

    prompt = build_editorial_prompt(
        persona=context['persona'],
        guidelines=context['guidelines'],
        glossary=context['glossary'],
        knowledge_base=context['knowledge_formatted'],
        chapter_list=context['chapters'],
        task=task,
        content=transcript
    )
    
    # Call Claude
    print("Calling Claude for analysis...")
    try:
        response = call_claude(prompt)
    except Exception as e:
        error_comment = f"❌ Error calling AI: {str(e)}"
        Path('output').mkdir(exist_ok=True)
        Path('output/analysis-comment.md').write_text(error_comment)
        set_output('success', 'false')
        set_output('error', str(e))
        sys.exit(1)
    
    # Format the comment
    comment = f"""## 🎙️ AI Editorial Analysis

{response}

---

### Next Steps

**To integrate this content:**
1. Reply with any feedback or answers to my questions above
2. Specify placement: `@ai-editor place in chapter-name.md`
3. When ready: `@ai-editor create PR`

**Or if this isn't ready:**
- Close this issue if you want to discard it
- Add `awaiting-author` label if you need to think about it
- Just reply with questions or direction

---
*This analysis was generated by AI Book Editor. I'm here to help, not to impose—your voice is what matters.*
"""
    
    # Output to file for workflow to use
    Path('output').mkdir(exist_ok=True)
    Path('output/analysis-comment.md').write_text(comment)
    
    # Set step outputs
    set_output('success', 'true')
    set_output('has_analysis', 'true')
    
    print(f"Successfully processed issue #{issue_number}")
    print(f"Analysis written to output/analysis-comment.md")


if __name__ == '__main__':
    main()
```

### Task 1.7: Create `respond_to_comment.py`

**File:** `ai-book-editor/.github/scripts/respond_to_comment.py`

> **Note:** This script outputs step outputs and files. The workflow uses peter-evans/create-pull-request for PR creation — we don't reinvent that wheel.

```python
#!/usr/bin/env python3
"""
Respond to @ai-editor commands in issue comments.

Handles:
- @ai-editor create PR - Signals workflow to create PR
- @ai-editor place in [file.md] - Sets target file
- @ai-editor [anything else] - Conversational response

OUTPUTS:
- create_pr: 'true' if PR should be created
- target_file: path to target file for PR
- scope: commit message scope
- pr_body: PR description content
- response_comment: comment to post (if not creating PR)
- cleaned_content: content for the PR (written to file)
"""

import os
import sys
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import (
    get_github_client, get_repo, get_issue, get_issue_comments
)
from scripts.utils.claude_client import call_claude
from scripts.utils.knowledge_base import load_editorial_context


def set_output(name: str, value: str):
    """Set a step output for the GitHub Actions workflow."""
    output_file = os.environ.get('GITHUB_OUTPUT')
    if output_file:
        with open(output_file, 'a') as f:
            if '\n' in value:
                import uuid
                delimiter = uuid.uuid4().hex
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")


def extract_cleaned_transcript(comments: list) -> str:
    """Extract the cleaned transcript from AI's previous analysis."""
    for comment in reversed(comments):
        body = comment.get('body', '')
        if '### Cleaned Transcript' in body:
            match = re.search(
                r'### Cleaned Transcript\s*\n(.*?)(?=###|\n---|\Z)',
                body,
                re.DOTALL
            )
            if match:
                return match.group(1).strip()
    return None


def extract_target_file(comments: list, issue_number: int) -> str:
    """Determine target file from comments or default."""
    for comment in reversed(comments):
        body = comment.get('body', '')
        match = re.search(r'place in (\S+\.md)', body.lower())
        if match:
            filename = match.group(1)
            if '/' not in filename:
                return filename
            return filename.split('/')[-1]
    return f"voice-memo-{issue_number}.md"


def main():
    issue_number = int(os.environ.get('ISSUE_NUMBER', 0))
    comment_body = os.environ.get('COMMENT_BODY', '')
    
    if not issue_number:
        print("ERROR: ISSUE_NUMBER not set")
        sys.exit(1)
    
    gh = get_github_client()
    repo = get_repo(gh)
    issue = get_issue(repo, issue_number)
    comments = get_issue_comments(issue)
    
    # Ensure output directory exists
    Path('output').mkdir(exist_ok=True)
    
    # Normalize command
    comment_lower = comment_body.lower()
    
    # === Handle @ai-editor create PR ===
    if '@ai-editor create pr' in comment_lower:
        print("Preparing PR creation...")
        
        # Get cleaned content
        cleaned_content = extract_cleaned_transcript(comments)
        if not cleaned_content:
            cleaned_content = issue.body  # Fallback to original
            set_output('response_comment', 
                "⚠️ Couldn't find my cleaned transcript. Using original content. "
                "You may want to edit the PR after it's created.")
        
        # Determine target file
        target_filename = extract_target_file(comments, issue_number)
        target_path = f"chapters/{target_filename}"
        
        # Write cleaned content to file for workflow
        Path('output/cleaned-content.md').write_text(cleaned_content)
        
        # Also write it to the actual target path (workflow will commit)
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file exists and append or create
        if Path(target_path).exists():
            existing = Path(target_path).read_text()
            Path(target_path).write_text(existing + "\n\n---\n\n" + cleaned_content)
        else:
            Path(target_path).write_text(cleaned_content)
        
        # Set outputs for workflow
        set_output('create_pr', 'true')
        set_output('target_file', target_path)
        set_output('scope', target_filename.replace('.md', ''))
        
        pr_body = f"""### Content Preview

{cleaned_content[:500]}{'...' if len(cleaned_content) > 500 else ''}

---

### Editorial Checklist

- [ ] Content flows naturally in context
- [ ] Formatting matches existing chapters
- [ ] No redundancy with other sections
- [ ] Voice is consistent"""
        
        set_output('pr_body', pr_body)
        
        # Response comment
        set_output('response_comment', 
            f"✅ Creating PR to add content to `{target_path}`...")
        
        print(f"PR creation prepared for {target_path}")
        return
    
    # === Handle @ai-editor place in [file] ===
    if '@ai-editor place in' in comment_lower:
        match = re.search(r'place in (\S+\.md)', comment_lower)
        if match:
            filename = match.group(1)
            set_output('create_pr', 'false')
            set_output('response_comment',
                f"📁 Got it! I'll target `chapters/{filename}` when creating the PR.\n\n"
                f"When you're ready, just say `@ai-editor create PR`.")
            print(f"Target file set to {filename}")
            return
    
    # === Handle general @ai-editor mention ===
    if '@ai-editor' in comment_lower:
        print("Generating conversational response...")
        
        # Build conversation history
        history = f"**Original transcript:**\n{issue.body}\n\n"
        for c in comments:
            role = "Author" if c['user'] != 'github-actions[bot]' else "AI Editor"
            history += f"**{role}:**\n{c['body'][:500]}\n\n"
        
        prompt = f"""You are an editorial assistant having a conversation about integrating a voice memo into a book.

{history}

**Latest message from author:**
{comment_body}

Respond helpfully and concisely. If they've:
- Answered your questions → acknowledge and confirm understanding
- Given direction → confirm you understand and ask if they want to proceed
- Asked a question → answer based on your analysis
- Said to create a PR → remind them to type "@ai-editor create PR"

Keep responses brief and focused. You're a collaborator, not a lecturer."""

        response = call_claude(prompt, max_tokens=1024)
        
        set_output('create_pr', 'false')
        set_output('response_comment', response)
        print("Conversational response generated")
        return
    
    # No @ai-editor mention found
    set_output('create_pr', 'false')
    set_output('response_comment', '')
    print("No @ai-editor command found, skipping.")


if __name__ == '__main__':
    main()
```

### Task 1.8: Create Workflow Files for Book Repository

**File:** `ai-book-editor-test/.github/workflows/process-transcription.yml`

> **Note:** This workflow uses [peter-evans/create-or-update-comment](https://github.com/peter-evans/create-or-update-comment) for posting comments and [actions/github-script](https://github.com/actions/github-script) for adding labels, rather than handling these in Python.

```yaml
name: Process Voice Transcription

on:
  issues:
    types: [opened, labeled]

jobs:
  process:
    # Only process open issues with voice_transcription label that haven't been reviewed
    if: |
      github.event.issue.state == 'open' &&
      contains(github.event.issue.labels.*.name, 'voice_transcription') &&
      !contains(github.event.issue.labels.*.name, 'ai-reviewed')
    
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout book repository
        uses: actions/checkout@v4
      
      - name: Checkout AI Book Editor action
        uses: actions/checkout@v4
        with:
          repository: VoiceWriter/ai-book-editor
          path: .ai-book-editor
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      # Cache pip dependencies for faster runs
      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('.ai-book-editor/requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-
      
      - name: Install dependencies
        run: pip install -r .ai-book-editor/requirements.txt
      
      - name: Process transcription with Claude
        id: process
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: |
          cd .ai-book-editor
          python .github/scripts/process_transcription.py
      
      # Use existing action for commenting instead of Python
      - name: Post analysis comment
        uses: peter-evans/create-or-update-comment@v4
        with:
          issue-number: ${{ github.event.issue.number }}
          body-path: .ai-book-editor/output/analysis-comment.md
      
      # Use existing action for labels instead of Python
      - name: Add ai-reviewed label
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.addLabels({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: ${{ github.event.issue.number }},
              labels: ['ai-reviewed']
            })
```

**File:** `ai-book-editor-test/.github/workflows/respond-to-feedback.yml`

> **Note:** This workflow uses [peter-evans/create-pull-request](https://github.com/peter-evans/create-pull-request) for PR creation — one of the most popular and well-maintained actions for this purpose.

```yaml
name: Respond to Feedback

on:
  issue_comment:
    types: [created]

jobs:
  respond:
    # Only respond to comments on voice_transcription issues that mention @ai-editor
    if: |
      contains(github.event.issue.labels.*.name, 'voice_transcription') &&
      contains(github.event.comment.body, '@ai-editor')
    
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout book repository
        uses: actions/checkout@v4
      
      - name: Checkout AI Book Editor action
        uses: actions/checkout@v4
        with:
          repository: VoiceWriter/ai-book-editor
          path: .ai-book-editor
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('.ai-book-editor/requirements.txt') }}
      
      - name: Install dependencies
        run: pip install -r .ai-book-editor/requirements.txt
      
      - name: Process comment and prepare content
        id: process
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
          COMMENT_BODY: ${{ github.event.comment.body }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: |
          cd .ai-book-editor
          python .github/scripts/respond_to_comment.py
      
      # Use peter-evans/create-pull-request for PR creation (if requested)
      - name: Create PR from voice memo
        if: steps.process.outputs.create_pr == 'true'
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          commit-message: |
            content(${{ steps.process.outputs.scope }}): Add content from voice memo (#${{ github.event.issue.number }})
            
            Source: #${{ github.event.issue.number }}
            Reviewed-by: ai-editor
            Editorial-type: addition
          branch: voice-memo/issue-${{ github.event.issue.number }}
          title: "📝 Voice memo: ${{ github.event.issue.title }}"
          body: |
            ## 📝 Voice Memo Integration
            
            **Source:** #${{ github.event.issue.number }}
            **Target:** `${{ steps.process.outputs.target_file }}`
            
            ---
            
            ${{ steps.process.outputs.pr_body }}
            
            ---
            
            Closes #${{ github.event.issue.number }}
          labels: |
            voice-memo
            ai-generated
      
      # Post response comment using existing action
      - name: Post response comment
        if: steps.process.outputs.response_comment != ''
        uses: peter-evans/create-or-update-comment@v4
        with:
          issue-number: ${{ github.event.issue.number }}
          body: ${{ steps.process.outputs.response_comment }}
      
      # Add pr-created label if PR was created
      - name: Add pr-created label
        if: steps.process.outputs.create_pr == 'true'
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.addLabels({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: ${{ github.event.issue.number }},
              labels: ['pr-created']
            })
```

---

## Phase 2: PR Editorial Review

**Goal:** AI reviews all PRs that modify chapter content.

### Task 2.1: Create `review_pr.py`

**File:** `ai-book-editor/.github/scripts/review_pr.py`

```python
#!/usr/bin/env python3
"""
Provide AI editorial review on pull requests.

This script:
1. Reads the PR diff and changed files
2. Loads full chapter content for context
3. Calls Claude for editorial review
4. Posts review as PR review (not just comment)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import (
    get_github_client, get_repo, get_pull_request, read_file_content
)
from scripts.utils.claude_client import call_claude, build_editorial_prompt
from scripts.utils.knowledge_base import load_editorial_context


def get_pr_files_content(repo, pr) -> list:
    """Get content of changed files in the PR."""
    files = []
    for f in pr.get_files():
        if f.filename.startswith('chapters/') and f.filename.endswith('.md'):
            # Get the new content from the PR branch
            content = read_file_content(repo, f.filename, ref=pr.head.sha)
            
            # Get the old content from base branch for comparison
            old_content = read_file_content(repo, f.filename, ref=pr.base.sha)
            
            files.append({
                'filename': f.filename,
                'status': f.status,  # added, modified, removed
                'patch': f.patch,    # The diff
                'new_content': content,
                'old_content': old_content,
                'additions': f.additions,
                'deletions': f.deletions
            })
    return files


def main():
    pr_number = int(os.environ.get('PR_NUMBER', 0))
    if not pr_number:
        print("ERROR: PR_NUMBER not set")
        sys.exit(1)
    
    gh = get_github_client()
    repo = get_repo(gh)
    pr = get_pull_request(repo, pr_number)
    
    # Get changed files
    changed_files = get_pr_files_content(repo, pr)
    
    if not changed_files:
        print("No chapter files changed, skipping review.")
        sys.exit(0)
    
    # Load editorial context
    context = load_editorial_context(repo)
    
    # Build review prompt
    files_summary = []
    for f in changed_files:
        files_summary.append(f"""
### File: {f['filename']}
**Status:** {f['status']} (+{f['additions']} -{f['deletions']})

**Changes (diff):**
```diff
{f['patch'][:2000] if f['patch'] else 'No diff available'}
```

**Full new content:**
{f['new_content'][:3000] if f['new_content'] else 'File deleted'}
""")
    
    task = f"""Review this pull request for editorial quality.

**PR Title:** {pr.title}
**PR Description:** 
{pr.body or 'No description provided'}

**Changed Files:**
{''.join(files_summary)}

Provide editorial feedback following these guidelines:

1. **What's Working Well** - Start positive. What's effective about these changes?

2. **Structural Feedback** - Does this fit well in the book's flow? Any organization issues?

3. **Line-Level Suggestions** - Specific improvements to prose, clarity, or style.
   Format as: `Line/section: "original text" → "suggested text" (reason)`

4. **Style Guide Compliance** - Any violations of the editorial guidelines?

5. **Questions for Author** - Anything unclear that needs clarification?

6. **Overall Assessment** - APPROVE, REQUEST_CHANGES, or COMMENT?
   - APPROVE: Good to merge as-is or with minor optional tweaks
   - REQUEST_CHANGES: Needs work before merging
   - COMMENT: Observations only, author decides

Remember: You work FOR the author. Enhance their voice, don't replace it."""

    prompt = build_editorial_prompt(
        persona=context['persona'],
        guidelines=context['guidelines'],
        glossary=context['glossary'],
        knowledge_base=context['knowledge_formatted'],
        chapter_list=context['chapters'],
        task=task,
        content=""  # Content is in the task
    )
    
    # Call Claude
    print("Calling Claude for PR review...")
    response = call_claude(prompt, max_tokens=4096)
    
    # Determine review action
    review_action = "COMMENT"  # Default
    response_lower = response.lower()
    if "overall assessment" in response_lower:
        if "approve" in response_lower.split("overall assessment")[-1][:100]:
            review_action = "APPROVE"
        elif "request_changes" in response_lower.split("overall assessment")[-1][:100]:
            review_action = "REQUEST_CHANGES"
    
    # Post as PR review
    review_body = f"""## 📝 AI Editorial Review

{response}

---
*This review was generated by AI Book Editor. Take what's useful, ignore what isn't.*
"""
    
    pr.create_review(body=review_body, event=review_action)
    print(f"Posted {review_action} review on PR #{pr_number}")


if __name__ == '__main__':
    main()
```

### Task 2.2: Create PR Review Workflow

**File:** `ai-book-editor-test/.github/workflows/review-pr.yml`

```yaml
name: AI Editorial Review

on:
  pull_request:
    types: [opened, synchronize]
    paths:
      - 'chapters/**'

jobs:
  review:
    runs-on: ubuntu-latest
    
    # Don't review PRs created by the bot itself
    if: github.actor != 'github-actions[bot]'
    
    steps:
      - name: Checkout book repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Need full history for diff
      
      - name: Checkout AI Book Editor action
        uses: actions/checkout@v4
        with:
          repository: VoiceWriter/ai-book-editor
          path: .ai-book-editor
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r .ai-book-editor/requirements.txt
      
      - name: Run AI Editorial Review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: |
          cd .ai-book-editor
          python .github/scripts/review_pr.py
```

---

## Phase 3: Knowledge Base System

**Goal:** AI asks questions, stores answers, and builds context over time.

### Task 3.1: Create `extract_knowledge.py`

**File:** `ai-book-editor/.github/scripts/extract_knowledge.py`

```python
#!/usr/bin/env python3
"""
Extract knowledge from closed AI question issues.

When an issue with 'ai-question' label is closed:
1. Extract the original question
2. Extract author's answer from comments
3. Use Claude to summarize the key information
4. Append to .ai-context/knowledge.jsonl
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import (
    get_github_client, get_repo, get_issue,
    get_issue_comments, read_file_content
)
from scripts.utils.claude_client import call_claude


def extract_question_from_body(body: str) -> str:
    """Extract the question from the issue body."""
    # Look for question after "## Question from AI Editor"
    if "## Question" in body:
        parts = body.split("## Question")
        if len(parts) > 1:
            question_part = parts[1].split("---")[0].strip()
            # Remove "from AI Editor" if present
            question_part = question_part.replace("from AI Editor", "").strip()
            return question_part
    return body.strip()


def get_author_responses(comments: list, repo_owner: str) -> list:
    """Get comments from the author (not the bot)."""
    author_comments = []
    for c in comments:
        if c['user'] != 'github-actions[bot]':
            author_comments.append(c['body'])
    return author_comments


def main():
    issue_number = int(os.environ.get('ISSUE_NUMBER', 0))
    if not issue_number:
        print("ERROR: ISSUE_NUMBER not set")
        sys.exit(1)
    
    gh = get_github_client()
    repo = get_repo(gh)
    issue = get_issue(repo, issue_number)
    
    # Extract question
    question = extract_question_from_body(issue.body or "")
    
    # Get author responses
    comments = get_issue_comments(issue)
    author_responses = get_author_responses(comments, repo.owner.login)
    
    if not author_responses:
        print("No author responses found, skipping extraction.")
        sys.exit(0)
    
    # Use Claude to extract the key answer
    prompt = f"""Extract the key information from this author response to store in a knowledge base.

**Original question:** {question}

**Author's response(s):**
{chr(10).join(author_responses)}

Provide a concise, factual summary of the answer that can be used as context for future editorial work. Focus on:
- Specific facts and decisions
- Preferences and style choices  
- Important context about the book or author's intent

Keep the summary under 200 words. Just provide the summary, no preamble."""

    extracted_answer = call_claude(prompt, max_tokens=500)
    
    # Create knowledge entry
    entry = {
        "id": f"q{issue_number:03d}",
        "question": question,
        "answer": extracted_answer.strip(),
        "source_issue": issue_number,
        "extracted_at": datetime.utcnow().isoformat() + "Z",
        "confidence": "explicit"
    }
    
    # Append to knowledge.jsonl
    kb_path = '.ai-context/knowledge.jsonl'
    try:
        existing = read_file_content(repo, kb_path) or ""
        new_content = existing.rstrip() + "\n" + json.dumps(entry) if existing.strip() else json.dumps(entry)
        
        # Use GitHub API to update file
        try:
            file = repo.get_contents(kb_path)
            repo.update_file(
                kb_path,
                f"Add knowledge from issue #{issue_number}",
                new_content,
                file.sha
            )
        except Exception:
            repo.create_file(
                kb_path,
                f"Initialize knowledge base with issue #{issue_number}",
                json.dumps(entry)
            )
    except Exception as e:
        print(f"Error updating knowledge base: {e}")
        sys.exit(1)
    
    # Add label to indicate extraction complete
    try:
        issue.add_to_labels('knowledge-extracted')
    except Exception:
        pass
    
    print(f"Extracted knowledge from issue #{issue_number}")


if __name__ == '__main__':
    main()
```

### Task 3.2: Create AI Question Workflow

**File:** `ai-book-editor-test/.github/workflows/process-ai-question.yml`

```yaml
name: Process AI Question

on:
  issues:
    types: [closed]

jobs:
  extract:
    # Only process closed issues with ai-question label
    if: |
      contains(github.event.issue.labels.*.name, 'ai-question') &&
      !contains(github.event.issue.labels.*.name, 'knowledge-extracted')
    
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout book repository
        uses: actions/checkout@v4
      
      - name: Checkout AI Book Editor action
        uses: actions/checkout@v4
        with:
          repository: VoiceWriter/ai-book-editor
          path: .ai-book-editor
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r .ai-book-editor/requirements.txt
      
      - name: Extract knowledge
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: |
          cd .ai-book-editor
          python .github/scripts/extract_knowledge.py
```

---

## Phase 4: Scheduled Book Review

**Goal:** Weekly autonomous analysis of the entire book.

### Task 4.1: Create `scheduled_review.py`

**File:** `ai-book-editor/.github/scripts/scheduled_review.py`

```python
#!/usr/bin/env python3
"""
Perform scheduled full-book editorial review.

This script:
1. Reads all chapters
2. Analyzes for structural issues, redundancy, gaps
3. Creates GitHub issues for discovered problems
4. Can generate AI questions for needed context
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import (
    get_github_client, get_repo, read_file_content, list_files_in_directory
)
from scripts.utils.claude_client import call_claude, build_editorial_prompt
from scripts.utils.knowledge_base import load_editorial_context
import json


def load_all_chapters(repo) -> dict:
    """Load all chapter content."""
    chapters = {}
    chapter_files = list_files_in_directory(repo, 'chapters')
    
    for filename in chapter_files:
        if filename.endswith('.md'):
            content = read_file_content(repo, f'chapters/{filename}')
            if content:
                chapters[filename] = content
    
    return chapters


def parse_issues_from_response(response: str) -> list:
    """Parse structured issues from Claude's response."""
    issues = []
    
    # Look for JSON block
    if '```json' in response:
        try:
            json_match = response.split('```json')[1].split('```')[0]
            issues = json.loads(json_match)
        except (IndexError, json.JSONDecodeError):
            pass
    
    return issues


def main():
    gh = get_github_client()
    repo = get_repo(gh)
    
    # Load all chapters
    print("Loading chapters...")
    chapters = load_all_chapters(repo)
    
    if not chapters:
        print("No chapters found.")
        sys.exit(0)
    
    # Load editorial context
    context = load_editorial_context(repo)
    
    # Build chapter summary for prompt
    chapters_text = ""
    for filename, content in sorted(chapters.items()):
        word_count = len(content.split())
        chapters_text += f"\n### {filename} ({word_count} words)\n{content[:2000]}...\n"
    
    task = f"""Perform a comprehensive editorial review of this book manuscript.

**Chapters ({len(chapters)} total, {sum(len(c.split()) for c in chapters.values())} words):**
{chapters_text}

Analyze for:

1. **Structural Issues**
   - Flow and organization problems
   - Chapters in wrong order
   - Missing transitions between sections

2. **Redundancy**
   - Content repeated across chapters
   - Ideas stated multiple times
   - Overlapping sections

3. **Content Gaps**
   - Missing explanations
   - Promised topics not covered
   - Logical jumps

4. **Consistency Issues**
   - Terminology inconsistencies
   - Voice/tone shifts
   - Contradictions

5. **Pacing Problems**
   - Sections too long or short
   - Rushed or dragging areas

For each issue found, provide:
- Type (structural/redundancy/gap/consistency/pacing)
- Location (which chapter(s))
- Description of the problem
- Suggested resolution

Also identify 1-3 questions you need answered to provide better feedback.

Return your findings as JSON:
```json
[
  {{"type": "structural", "location": "chapter-01.md", "title": "Brief title", "description": "...", "suggestion": "..."}},
  {{"type": "question", "question": "...", "why": "..."}}
]
```"""

    prompt = build_editorial_prompt(
        persona=context['persona'],
        guidelines=context['guidelines'],
        glossary=context['glossary'],
        knowledge_base=context['knowledge_formatted'],
        chapter_list=list(chapters.keys()),
        task=task,
        content=""
    )
    
    print("Calling Claude for full book analysis...")
    response = call_claude(prompt, max_tokens=8000)
    
    # Parse issues
    issues = parse_issues_from_response(response)
    
    if not issues:
        print("No issues parsed from response. Creating summary issue instead.")
        repo.create_issue(
            title="📚 Weekly Editorial Review Summary",
            body=f"## Full Book Analysis\n\n{response}\n\n---\n*Generated by AI Book Editor*",
            labels=['ai-suggestion']
        )
        sys.exit(0)
    
    # Create issues for each finding
    created_count = 0
    for item in issues:
        if item.get('type') == 'question':
            # Create AI question issue
            repo.create_issue(
                title=f"[AI Question] {item['question'][:60]}",
                body=f"""## Question from AI Editor

{item['question']}

---

**Why I'm asking:** {item.get('why', 'I need this context to provide better editorial feedback.')}

**How to respond:** Just reply to this issue. I'll extract the answer and remember it for future editing sessions.

---
*This question was automatically generated during weekly book review.*
""",
                labels=['ai-question', 'awaiting-author']
            )
            created_count += 1
        else:
            # Create editorial issue
            repo.create_issue(
                title=f"[{item['type'].title()}] {item.get('title', item['description'][:50])}",
                body=f"""## Editorial Issue

**Type:** {item['type']}
**Location:** {item.get('location', 'Multiple chapters')}

### Problem
{item['description']}

### Suggested Resolution
{item.get('suggestion', 'No specific suggestion provided.')}

---

**Next steps:**
- Comment if you want to discuss
- Add `approved` label if you want me to create a PR
- Close if this is intentional

---
*This issue was automatically generated during weekly book review.*
""",
                labels=['ai-suggestion', item['type']]
            )
            created_count += 1
    
    print(f"Created {created_count} issues from book review.")


if __name__ == '__main__':
    main()
```

### Task 4.2: Create Scheduled Review Workflow

**File:** `ai-book-editor-test/.github/workflows/scheduled-review.yml`

> **Note:** This workflow uses [peter-evans/create-issue-from-file](https://github.com/peter-evans/create-issue-from-file) for creating issues from the AI's analysis, and [stefanzweifel/git-auto-commit-action](https://github.com/stefanzweifel/git-auto-commit-action) for committing any knowledge base updates.

```yaml
name: Weekly Editorial Review

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9am UTC
  workflow_dispatch:  # Allow manual trigger

jobs:
  review:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout book repository
        uses: actions/checkout@v4
      
      - name: Checkout AI Book Editor action
        uses: actions/checkout@v4
        with:
          repository: VoiceWriter/ai-book-editor
          path: .ai-book-editor
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('.ai-book-editor/requirements.txt') }}
      
      - name: Install dependencies
        run: pip install -r .ai-book-editor/requirements.txt
      
      - name: Run scheduled review (outputs issue files)
        id: review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: |
          cd .ai-book-editor
          python .github/scripts/scheduled_review.py
      
      # Create issues from generated files using existing action
      - name: Create editorial issues
        if: steps.review.outputs.issue_count > 0
        uses: peter-evans/create-issue-from-file@v5
        with:
          title: ${{ steps.review.outputs.issue_title }}
          content-filepath: .ai-book-editor/output/issues/
          labels: |
            ai-suggestion
      
      # Alternative: Use actions-cool/issues-helper for batch issue creation
      - name: Create multiple issues (if needed)
        if: steps.review.outputs.issue_count > 1
        uses: actions-cool/issues-helper@v3
        with:
          actions: 'create-issue'
          token: ${{ secrets.GITHUB_TOKEN }}
          title: ${{ steps.review.outputs.batch_titles }}
          body: ${{ steps.review.outputs.batch_bodies }}
          labels: 'ai-suggestion'
```

---

## Phase 5: AI Self-Improvement

**Goal:** AI learns from author feedback and suggests guideline updates.

### Task 5.1: Create `learn_from_feedback.py`

**File:** `ai-book-editor/.github/scripts/learn_from_feedback.py`

```python
#!/usr/bin/env python3
"""
Learn from author feedback patterns.

This script:
1. Analyzes recent closed issues and merged PRs
2. Identifies repeated corrections and preferences
3. Suggests updates to EDITOR_PERSONA.md and EDITORIAL_GUIDELINES.md
4. Creates a PR with suggestions (author reviews before merge)
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import (
    get_github_client, get_repo, read_file_content,
    create_branch, create_or_update_file
)
from scripts.utils.claude_client import call_claude


def get_recent_feedback(repo, days: int = 7) -> dict:
    """Collect feedback from recent issues and PRs."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    feedback = {
        'issue_comments': [],
        'pr_reviews': [],
        'pr_comments': []
    }
    
    # Get recent closed issues
    for issue in repo.get_issues(state='closed', sort='updated', direction='desc'):
        if issue.updated_at < cutoff:
            break
        if issue.pull_request:
            continue  # Skip PRs in issue list
        
        for comment in issue.get_comments():
            if comment.user.login != 'github-actions[bot]':
                feedback['issue_comments'].append({
                    'issue': issue.number,
                    'title': issue.title,
                    'comment': comment.body,
                    'date': comment.created_at.isoformat()
                })
    
    # Get recent merged PRs
    for pr in repo.get_pulls(state='closed', sort='updated', direction='desc'):
        if pr.updated_at < cutoff:
            break
        if not pr.merged:
            continue
        
        for review in pr.get_reviews():
            if review.user.login != 'github-actions[bot]':
                feedback['pr_reviews'].append({
                    'pr': pr.number,
                    'title': pr.title,
                    'state': review.state,
                    'body': review.body,
                    'date': review.submitted_at.isoformat() if review.submitted_at else None
                })
        
        for comment in pr.get_review_comments():
            if comment.user.login != 'github-actions[bot]':
                feedback['pr_comments'].append({
                    'pr': pr.number,
                    'file': comment.path,
                    'comment': comment.body,
                    'date': comment.created_at.isoformat()
                })
    
    return feedback


def main():
    gh = get_github_client()
    repo = get_repo(gh)
    
    # Get recent feedback
    print("Collecting recent feedback...")
    feedback = get_recent_feedback(repo)
    
    total_items = (
        len(feedback['issue_comments']) + 
        len(feedback['pr_reviews']) + 
        len(feedback['pr_comments'])
    )
    
    if total_items < 3:
        print("Not enough feedback to analyze (minimum 3 items).")
        sys.exit(0)
    
    # Load current guidelines
    persona = read_file_content(repo, 'EDITOR_PERSONA.md') or ""
    guidelines = read_file_content(repo, 'EDITORIAL_GUIDELINES.md') or ""
    
    # Analyze with Claude
    prompt = f"""Analyze this author feedback to identify patterns and suggest improvements to the AI editor's guidelines.

## Current Editor Persona
{persona}

## Current Editorial Guidelines
{guidelines}

## Recent Author Feedback

### Issue Comments
{chr(10).join([f"- Issue #{f['issue']}: {f['comment'][:200]}" for f in feedback['issue_comments']][:20])}

### PR Reviews
{chr(10).join([f"- PR #{f['pr']} ({f['state']}): {f['body'][:200] if f['body'] else 'No comment'}" for f in feedback['pr_reviews']][:20])}

### PR Inline Comments
{chr(10).join([f"- PR #{f['pr']} on {f['file']}: {f['comment'][:200]}" for f in feedback['pr_comments']][:20])}

## Your Task

Identify patterns in the feedback:
1. **Repeated corrections** - What mistakes is the AI making that the author keeps fixing?
2. **Expressed preferences** - What has the author explicitly stated they want or don't want?
3. **Approval patterns** - What kinds of suggestions get accepted vs rejected?

Then suggest specific updates to:
1. EDITOR_PERSONA.md - Personality/approach adjustments
2. EDITORIAL_GUIDELINES.md - New rules or modifications

Format your response as:

### Summary of Learnings
[Brief overview of what you learned]

### Suggested Updates to EDITOR_PERSONA.md
```markdown
[Specific text to add/change, with context about where it goes]
```

### Suggested Updates to EDITORIAL_GUIDELINES.md
```markdown
[Specific text to add/change, with context about where it goes]
```

### Reasoning
[Why these changes will improve future interactions]

If there are no clear patterns or necessary changes, say so. Don't suggest changes for the sake of changes."""

    print("Analyzing feedback patterns...")
    response = call_claude(prompt, max_tokens=4000)
    
    # Check if there are actual suggestions
    if "no clear patterns" in response.lower() or "no necessary changes" in response.lower():
        print("No significant patterns found.")
        sys.exit(0)
    
    # Create a PR with the analysis
    branch_name = f"ai-learning/{datetime.utcnow().strftime('%Y%m%d')}"
    create_branch(repo, branch_name)
    
    # Create a learning report file
    report_content = f"""# AI Learning Report - {datetime.utcnow().strftime('%Y-%m-%d')}

## Feedback Analyzed
- Issue comments: {len(feedback['issue_comments'])}
- PR reviews: {len(feedback['pr_reviews'])}
- PR inline comments: {len(feedback['pr_comments'])}

{response}

---
*This report was automatically generated by AI Book Editor's learning system.*
"""
    
    create_or_update_file(
        repo,
        '.ai-context/learning-reports/report-' + datetime.utcnow().strftime('%Y%m%d') + '.md',
        report_content,
        "chore: Add AI learning report",
        branch_name
    )
    
    # Create PR
    pr = repo.create_pull(
        title="[AI Learning] Suggested guideline updates",
        body=f"""## 🧠 AI Self-Improvement Suggestions

Based on author feedback over the past week, I'm suggesting these updates to my guidelines.

{response}

---

### Your Role

1. **Review** these suggestions carefully
2. **Edit** anything that doesn't quite fit
3. **Add context** I might have missed
4. **Reject** suggestions you disagree with

**Note:** I will NOT make these changes until you merge this PR. You always have final say over how I behave.

---

### Feedback Analyzed
- Issue comments: {len(feedback['issue_comments'])}
- PR reviews: {len(feedback['pr_reviews'])}
- PR inline comments: {len(feedback['pr_comments'])}

---
*This PR was automatically generated by the AI editor's learning system.*
""",
        head=branch_name,
        base=repo.default_branch,
        labels=['ai-learning', 'awaiting-author']
    )
    
    print(f"Created learning PR #{pr.number}")


if __name__ == '__main__':
    main()
```

### Task 5.2: Create Learning Workflow

**File:** `ai-book-editor-test/.github/workflows/learn-from-feedback.yml`

> **Note:** This workflow demonstrates the preferred pattern: Python handles AI logic and outputs files, then [peter-evans/create-pull-request](https://github.com/peter-evans/create-pull-request) handles all Git/GitHub operations.

```yaml
name: Learn from Author Feedback

on:
  schedule:
    - cron: '0 0 * * 0'  # Every Sunday at midnight UTC
  workflow_dispatch:

jobs:
  learn:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout book repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Need history for feedback analysis
      
      - name: Checkout AI Book Editor action
        uses: actions/checkout@v4
        with:
          repository: VoiceWriter/ai-book-editor
          path: .ai-book-editor
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('.ai-book-editor/requirements.txt') }}
      
      - name: Install dependencies
        run: pip install -r .ai-book-editor/requirements.txt
      
      # Python script ONLY analyzes and outputs files - no GitHub API calls
      - name: Analyze feedback and generate suggestions
        id: learn
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: |
          cd .ai-book-editor
          python .github/scripts/learn_from_feedback.py
      
      # Use existing action for ALL Git/GitHub operations
      - name: Create PR with suggested updates
        if: steps.learn.outputs.has_suggestions == 'true'
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          commit-message: "chore: AI learning - suggested guideline updates"
          branch: ai-learning/${{ github.run_id }}
          delete-branch: true
          title: "[AI Learning] Suggested guideline updates"
          body: |
            ## 🧠 AI Self-Improvement Suggestions
            
            Based on author feedback over the past week, I'm suggesting these updates to my guidelines.
            
            ### What I Learned
            ${{ steps.learn.outputs.summary }}
            
            ### Suggested Changes
            ${{ steps.learn.outputs.changes }}
            
            ---
            
            ### Your Role
            
            1. **Review** these suggestions carefully
            2. **Edit** anything that doesn't quite fit
            3. **Add context** I might have missed
            4. **Reject** suggestions you disagree with
            
            **Note:** I will NOT make these changes until you merge this PR. 
            You always have final say over how I behave.
            
            ---
            
            *This PR was automatically generated by the AI editor's learning system.*
          labels: |
            ai-learning
            awaiting-author
```

---

## Editorial Configuration Files

These files define the AI's personality and rules. They live in the **book repository**.

### EDITOR_PERSONA.md

```markdown
# Editor Persona

## Who You Are

You are a developmental and line editor with 20 years of experience in non-fiction, particularly books for technical professionals. You've edited books for O'Reilly, Pragmatic Programmers, and A Book Apart. You're direct but kind, opinionated but open to the author's vision.

## Your Approach

- You work FOR the author, not against them
- Your job is to make their voice clearer, not to impose your own
- You're allergic to fluff, jargon, and hedging
- You believe every sentence should earn its place
- You ask questions rather than assume intent
- You trust the author's expertise on their subject matter

## How You Give Feedback

- Lead with what's working before critiquing
- Be specific: "This paragraph" not "some parts"
- Explain WHY something doesn't work, not just that it doesn't
- Offer alternatives when you critique
- Use the author's own successful passages as models
- Acknowledge when something is a style preference vs. a problem

## Your Editorial Philosophy

- Clarity beats cleverness
- Rhythm matters — vary sentence length
- Strong verbs, concrete nouns
- Delete ruthlessly, add sparingly
- Preserve the author's quirks — they're features, not bugs
- Structure serves the reader's journey

## Your Relationship with the Author

- You're a trusted collaborator, not a gatekeeper
- You push back when something isn't working
- You defer on matters of voice and opinion
- You're firm on matters of clarity and structure
- You celebrate wins and acknowledge progress
- You never condescend or lecture

## When You're Uncertain

- ASK rather than assume
- Propose options rather than mandates
- Acknowledge the limits of your knowledge
- Defer to the author's domain expertise
```

### EDITORIAL_GUIDELINES.md

```markdown
# Editorial Guidelines

These are non-negotiable rules for all editorial work.

## Voice & Tone Rules

- Use "you" for the reader, "I" for author anecdotes
- Contractions are encouraged (it's, don't, won't)
- No academic stiffness, no corporate jargon
- Authoritative but warm — like a knowledgeable friend
- Active voice preferred; passive only for strategic emphasis

## NEVER Do These

- Add emojis
- Use "In conclusion", "To summarize", "As mentioned"
- Add hedging language ("perhaps", "it could be argued", "some might say")
- Soften strong statements — the author means what they say
- Convert flowing prose to bullet lists without permission
- Add section headers the author didn't want
- Use "utilize" (always "use")
- Add "TL;DR" or summary boxes
- Use passive voice without clear reason
- Add transitional phrases ("Now let's look at...", "Moving on to...")
- Create content the author didn't write or explicitly request
- Make assumptions about technical accuracy

## ALWAYS Do These

- Preserve the author's metaphors (especially recurring ones)
- Maintain terminology consistency (see GLOSSARY.md)
- Flag unclear passages — ask, don't guess
- Link suggestions to specific guideline rules
- Check for redundancy with other chapters
- Explain the reasoning behind every suggestion
- Acknowledge what's working well before critiquing

## Terminology (Source of Truth: GLOSSARY.md)

Refer to GLOSSARY.md for preferred terms. When in doubt, maintain consistency with existing usage in the manuscript.

## Structure Rules

- Sections: 300-600 words optimal, 800 max
- Paragraphs: 3-5 sentences max
- No footnotes — integrate or cut
- Code examples use Python unless noted
- Headers should be descriptive, not clever

## Editorial Priority Order

1. **Clarity** — Can the reader understand this?
2. **Flow** — Does it read smoothly?
3. **Voice** — Does it sound like the author?
4. **Concision** — Can it be tighter?
5. **Grammar** — Standard usage, not pedantic

## Target Reader

Professional software developers, 5-15 years experience. Smart, busy, skeptical of fluff. Values practical over theoretical. Familiar with programming concepts but not necessarily the specific tools discussed.

## Key Themes to Reinforce

Refer to .ai-context/themes.yaml for the book's central themes. These should be reinforced consistently across chapters.
```

### GLOSSARY.md

```markdown
# Glossary

Consistent terminology across the manuscript.

## Preferred Terms

| Use This | Not This | Notes |
|----------|----------|-------|
| workflow | process | Author's preferred metaphor |
| friction | obstacles, barriers | Central concept |
| tool | application, software | Keep it concrete |
| capture | record, note-taking | For the initial phase |

## Capitalization

- Chapter, Part, Section — capitalize when referring to book structure
- markdown, git — lowercase (technical terms)
- VoiceWriter — one word, camel case

## Technical Terms

Define on first use, then use freely. Don't re-explain in every chapter.

## Avoid

- "leverage" (use "use")
- "utilize" (use "use")
- "synergy" (be specific)
- "optimize" without specifics
```

### style-guide.md

```markdown
# Style Guide

Quick reference for formatting and structural consistency.

## Formatting

- **Bold** for key terms on first use only
- `code` for technical terms, commands, filenames
- *Italics* for emphasis and book/article titles
- Blockquotes for external quotes only (not author asides)

## Structure

- Chapters: 2000-4000 words
- Sections: 300-600 words  
- Paragraphs: 3-5 sentences
- Use subheadings to break up long sections

## Code Examples

- Python is the default language
- Keep examples under 20 lines when possible
- Always include brief explanation of what code does
- Test all code examples before finalizing

## Lists

- Use sparingly — prose preferred
- When used, each item should be substantial (not one-word items)
- Parallel grammatical structure

## Numbers

- Spell out one through ten
- Use numerals for 11+
- Always use numerals for: percentages, measurements, code
```

---

## Issue and PR Templates

### Voice Transcription Issue Template

**File:** `ai-book-editor-test/.github/ISSUE_TEMPLATE/voice-transcription.md`

```markdown
---
name: Voice Transcription
about: Submit a voice memo transcript for editorial processing
labels: voice_transcription
---

## Transcript

<!-- Paste your voice memo transcript here -->



## Context (optional)

**Recording date:** 
**Topic/Theme:** 
**Intended placement:** 

---

*This issue will be automatically processed by the AI editor.*
```

### Chapter Tracking Issue Template

**File:** `ai-book-editor-test/.github/ISSUE_TEMPLATE/chapter-tracking.md`

```markdown
---
name: Chapter Tracking
about: Track editing progress for a chapter
labels: chapter, draft
---

## Chapter: [NUMBER] - [TITLE]

**File:** `chapters/[filename].md`

### Current Stage

- [ ] First draft complete
- [ ] Developmental edit
- [ ] Line edit  
- [ ] Copy edit
- [ ] Final review

### Checklist

- [ ] Opening hook is compelling
- [ ] Main argument is clear
- [ ] Supporting examples are relevant
- [ ] Transitions flow naturally
- [ ] Ending is satisfying
- [ ] No redundancy with other chapters
- [ ] Terminology matches GLOSSARY.md

### Known Issues

<!-- List any specific problems to address -->

### Related

<!-- Link to related issues, voice memos, etc. -->
```

### AI Question Issue Template

**File:** `ai-book-editor-test/.github/ISSUE_TEMPLATE/ai-question.md`

```markdown
---
name: AI Question
about: Question from the AI editor requiring author input
labels: ai-question, awaiting-author
---

## Question from AI Editor

<!-- AI will fill this in -->

---

**Why I'm asking:** <!-- AI explains context -->

**How to respond:** Just reply to this issue. I'll extract the answer and remember it for future editing sessions.

---

*This question was automatically generated by the AI editor.*
*When you close this issue, your answer will be stored in the knowledge base.*
```

### Pull Request Template

**File:** `ai-book-editor-test/.github/PULL_REQUEST_TEMPLATE.md`

```markdown
## Editorial Summary

**Type:** <!-- content | edit | fix | restructure | style -->
**Source:** <!-- #issue_number or "direct edit" -->
**Chapters affected:** <!-- list files -->

## What changed and why

<!-- Describe the editorial intent, not just what changed -->

## Original text (if editing)

<!-- Quote the original text being modified, or "N/A - new content" -->

## Editorial rationale

<!-- Why is this change being made? What problem does it solve? -->

## Checklist

- [ ] Follows style guide
- [ ] Terminology matches GLOSSARY.md
- [ ] Commit messages follow schema
- [ ] Linked to source issue (if applicable)

---

Closes #<!-- issue number if applicable -->
```

---

## iOS Shortcut Setup

### Overview

Apple Voice Memos now transcribes automatically. The workflow:

```
Record → Voice Memos transcribes → Copy transcript → Run Shortcut → GitHub Issue created
```

### Prerequisites

1. **GitHub Personal Access Token**
   - Go to github.com/settings/tokens
   - Generate new token (classic)
   - Name: `ios-shortcut`
   - Scope: `repo`
   - Copy the token (starts with `ghp_`)

### Shortcut Actions

Create a new Shortcut named "Send to Book":

1. **Get Clipboard** - Gets the copied transcript

2. **Set Variable** - Name: `transcript`, Value: Clipboard

3. **Date** - Current Date

4. **Format Date** - Custom format: `yyyy-MM-dd HH:mm`

5. **Set Variable** - Name: `dateString`

6. **Dictionary** - Create with:
   - `title`: "Voice memo [dateString]"
   - `body`: [transcript variable]
   - `labels`: Array with "voice_transcription"

7. **Get Contents of URL**
   - URL: `https://api.github.com/repos/YOUR_ORG/YOUR_REPO/issues`
   - Method: POST
   - Headers:
     - `Authorization`: `Bearer ghp_YOUR_TOKEN`
     - `Accept`: `application/vnd.github+json`
   - Request Body: JSON
   - Content: [Dictionary from step 6]

8. **Get Dictionary Value** - Key: `html_url`

9. **Show Notification** - "Issue created: [url]"

### Usage

1. Record voice memo
2. Open Voice Memos
3. Tap the memo → Copy Transcript
4. Run "Send to Book" shortcut
5. Issue appears in GitHub with `voice_transcription` label
6. AI processes automatically

---

## Testing with `act`

### Installation

```bash
# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

### Configuration

Create `.actrc` in the action repo:

```
-P ubuntu-latest=catthehacker/ubuntu:act-latest
--secret-file .secrets
```

Create `.secrets` (add to .gitignore!):

```
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
```

### Running Tests

```bash
# List available workflows
act -l

# Run a specific workflow
act push -W .github/workflows/test.yml

# Simulate an issue event
act issues -e test-events/new-issue.json

# Run with verbose output
act push -v
```

### Test Event Files

Create `test-events/new-issue.json`:

```json
{
  "action": "opened",
  "issue": {
    "number": 1,
    "title": "Test voice memo",
    "body": "This is a test transcript of a voice memo about writing workflow systems.",
    "state": "open",
    "labels": [{"name": "voice_transcription"}]
  },
  "repository": {
    "full_name": "VoiceWriter/ai-book-editor-test"
  }
}
```

---

## Traceability System

### Commit Message Schema

All commits must follow this format:

```
<type>(<scope>): <short description>

<body - editorial rationale>

Source: #<issue_number>
Reviewed-by: <human|ai-editor>
Editorial-type: <cleanup|restructure|addition|deletion|style>
```

**Types:**
- `content` — New content added
- `edit` — Existing content modified
- `fix` — Typo, grammar, factual correction
- `restructure` — Moving/reorganizing content
- `style` — Voice/tone adjustments

### Traceability Chain

Every piece of text is traceable:

```
Voice Memo (original recording)
       │
       ▼
GitHub Issue #N (transcript + discussion)
       │
       ▼
Pull Request #M (actual changes)
       │ └── "Closes #N"
       │
       ▼
Commit abc123 (in main branch)
       │ └── "Source: #N"
       │
       ▼
Published Book
```

### Querying History

```bash
# Find all commits from a specific issue
git log --grep="Source: #42"

# Find all AI-reviewed changes
git log --grep="Reviewed-by: ai-editor"

# See full history of a chapter
git log --follow -p chapters/03-workflow.md
```

---

## Implementation Checklist

### Phase 0: Repository Setup
- [ ] Create `VoiceWriter/ai-book-editor` repository
- [ ] Create `VoiceWriter/ai-book-editor-test` repository
- [ ] Add `ANTHROPIC_API_KEY` secret to both repos
- [ ] Create labels in test repo (see label list above)

### Phase 1: MVP Voice Memo Pipeline
- [ ] Create `requirements.txt`
- [ ] Create `action.yml`
- [ ] Create `utils/github_client.py`
- [ ] Create `utils/claude_client.py`
- [ ] Create `utils/knowledge_base.py`
- [ ] Create `process_transcription.py`
- [ ] Create `respond_to_comment.py`
- [ ] Create `process-transcription.yml` workflow
- [ ] Create `respond-to-feedback.yml` workflow
- [ ] Set up editorial config files (PERSONA, GUIDELINES, etc.)
- [ ] Test with a real voice memo
- [ ] Tag v0.1.0 release

### Phase 2: PR Editorial Review
- [ ] Create `review_pr.py`
- [ ] Create `review-pr.yml` workflow
- [ ] Test with sample PR

### Phase 3: Knowledge Base
- [ ] Create `extract_knowledge.py`
- [ ] Create `process-ai-question.yml` workflow
- [ ] Create `.ai-context/` directory structure
- [ ] Test knowledge extraction

### Phase 4: Scheduled Review
- [ ] Create `scheduled_review.py`
- [ ] Create `scheduled-review.yml` workflow
- [ ] Test with full book content

### Phase 5: AI Self-Improvement
- [ ] Create `learn_from_feedback.py`
- [ ] Create `learn-from-feedback.yml` workflow
- [ ] Test after accumulating feedback

---

## Quick Start Commands

```bash
# Clone the action repo
git clone https://github.com/VoiceWriter/ai-book-editor
cd ai-book-editor

# Create structure
mkdir -p .github/workflows .github/scripts/utils prompts

# Install dependencies locally for testing
pip install anthropic PyGithub pyyaml

# Test locally with act
act issues -e test-events/new-issue.json --secret-file .secrets
```

---

## Cost Estimates

| Service | Cost | Notes |
|---------|------|-------|
| GitHub Actions | Free (2000 min/mo) | Plenty for this workflow |
| Claude API | ~$0.01-0.15 per call | Depends on context size |
| Vercel | Free tier | For book hosting |

**Estimated monthly cost:** $5-20 (mostly Claude API)

---

## Summary

This system provides:

1. **Voice memos → Book content** via GitHub Issues + AI processing
2. **AI editorial review** on all PRs modifying chapters
3. **Knowledge accumulation** through AI questions and author answers
4. **Autonomous book review** on a weekly schedule
5. **Self-improvement** by learning from author feedback patterns
6. **Full traceability** from voice memo to published content

All built on free GitHub infrastructure with Claude AI as the intelligence layer.

The key insight: **GitHub already IS a collaborative editing platform.** You're just adding AI as a collaborator.
