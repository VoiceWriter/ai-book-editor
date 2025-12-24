#!/usr/bin/env python3
"""
Respond to /ai-editor commands in issue comments.

Handles:
- /ai-editor create PR - Signals workflow to create PR
- /ai-editor place in [file.md] - Sets target file
- /ai-editor [anything else] - Conversational response

OUTPUTS:
- create_pr: 'true' if PR should be created
- target_file: path to target file for PR
- scope: commit message scope
- pr_body: PR description content
- response_comment: comment to post (if not creating PR)
- cleaned_content: content for the PR (written to file)
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import (  # noqa: E402
    get_github_client,
    get_issue,
    get_issue_comments,
    get_repo,
)
from scripts.utils.llm_client import call_editorial  # noqa: E402


def set_output(name: str, value: str):
    """Set a step output for the GitHub Actions workflow."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            if "\n" in value:
                import uuid

                delimiter = uuid.uuid4().hex
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")


def extract_cleaned_transcript(comments: list) -> str:
    """Extract the cleaned transcript from AI's previous analysis."""
    for comment in reversed(comments):
        body = comment.get("body", "")
        if "### Cleaned Transcript" in body:
            match = re.search(r"### Cleaned Transcript\s*\n(.*?)(?=###|\n---|\Z)", body, re.DOTALL)
            if match:
                return match.group(1).strip()
    return None


def extract_target_file(comments: list, issue_number: int) -> tuple[str, bool]:
    """
    Determine target file from comments.
    Returns (filename, was_explicitly_set).
    """
    for comment in reversed(comments):
        body = comment.get("body", "")
        match = re.search(r"place in (\S+\.md)", body.lower())
        if match:
            filename = match.group(1)
            if "/" not in filename:
                return filename, True
            return filename.split("/")[-1], True
    # No explicit placement - return None
    return None, False


def main():
    issue_number = int(os.environ.get("ISSUE_NUMBER", 0))
    comment_body = os.environ.get("COMMENT_BODY", "")

    if not issue_number:
        print("ERROR: ISSUE_NUMBER not set")
        sys.exit(1)

    gh = get_github_client()
    repo = get_repo(gh)
    issue = get_issue(repo, issue_number)
    comments = get_issue_comments(issue)

    # Ensure output directory exists
    Path("output").mkdir(exist_ok=True)

    # Normalize command
    comment_lower = comment_body.lower()

    # === Handle /ai-editor create PR ===
    if "/ai-editor create pr" in comment_lower:
        print("Preparing PR creation...")

        # Determine target file - REQUIRE explicit placement
        target_filename, was_explicit = extract_target_file(comments, issue_number)

        if not was_explicit:
            # No explicit placement - ask the author instead of dumping to generic file
            set_output("create_pr", "false")
            set_output(
                "response_comment",
                "**I need to know where to put this content.**\n\n"
                "Please specify the target by saying one of:\n"
                "- `/ai-editor place in chapter-03.md` - to add to an existing chapter\n"
                "- `/ai-editor place in new-chapter.md` - to create a new chapter\n"
                "- `/ai-editor place in uncategorized.md` - if you're not sure yet\n\n"
                "Then say `/ai-editor create PR` again.",
            )
            print("No target specified, asking author for placement")
            return

        # Determine the path based on whether it's uncategorized
        if target_filename == "uncategorized.md":
            target_path = f"uncategorized/voice-memo-{issue_number}.md"
        else:
            target_path = f"chapters/{target_filename}"

        # Load editorial context for proper editorial voice
        from scripts.utils.knowledge_base import load_editorial_context
        context = load_editorial_context(repo)

        # Get existing chapter content if appending
        from scripts.utils.github_client import read_file_content
        existing_chapter = read_file_content(repo, target_path) if target_filename != "uncategorized.md" else None

        # Build conversation history for context
        history = f"**Original voice memo:**\n{issue.body}\n\n"
        for c in comments:
            history += f"**{c['user']}:** {c['body'][:1000]}\n\n"

        # Call LLM to prepare editorial-quality content
        print("Calling LLM to prepare editorial content...")

        # Build prompt sections
        persona_section = "**Editor Persona:** " + context['persona'] if context.get('persona') else ""
        guidelines_section = "**Editorial Guidelines:** " + context['guidelines'] if context.get('guidelines') else ""
        if existing_chapter:
            existing_section = "**Existing chapter content:**\n" + existing_chapter[:2000] + "..."
        else:
            existing_section = "**This will be a new file.**"

        editorial_prompt = f"""You are a professional book editor preparing content for integration into a manuscript.

{persona_section}

{guidelines_section}

**Conversation so far:**
{history}

**Target file:** `{target_path}`

{existing_section}

**Your task:**
1. Take the cleaned transcript from our conversation and prepare it for integration
2. Polish the prose while preserving the author's voice exactly
3. Add any necessary transitions if appending to existing content
4. Format appropriately for the book's style
5. Note any concerns or suggestions for the author

Return your response in this format:

### Prepared Content
[The polished content ready for the chapter]

### Editorial Notes
[Your notes on what you changed and why, any concerns, suggestions for the author]

### Integration Recommendation
[How this content should fit - beginning/middle/end of chapter, or as new section]"""

        llm_response = call_editorial(editorial_prompt, max_tokens=4000)
        print(f"LLM call complete: {llm_response.usage.format_compact()}")

        # Extract the prepared content
        response_text = llm_response.content
        if "### Prepared Content" in response_text:
            content_match = re.search(
                r"### Prepared Content\s*\n(.*?)(?=### Editorial Notes|### Integration|\Z)",
                response_text,
                re.DOTALL
            )
            prepared_content = content_match.group(1).strip() if content_match else response_text
        else:
            prepared_content = response_text

        # Write prepared content to file for workflow
        Path("output/cleaned-content.md").write_text(prepared_content)

        # Also write it to the actual target path (workflow will commit)
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists and append or create
        if Path(target_path).exists():
            existing = Path(target_path).read_text()
            Path(target_path).write_text(existing + "\n\n---\n\n" + prepared_content)
        else:
            Path(target_path).write_text(prepared_content)

        # Set outputs for workflow
        set_output("create_pr", "true")
        set_output("target_file", target_path)
        set_output("scope", target_filename.replace(".md", ""))

        # Format reasoning section
        reasoning_section = llm_response.format_editorial_explanation()

        pr_body = f"""## Editorial Integration

**Target:** `{target_path}`
**Source:** Issue #{issue_number}

---

{response_text}

---

{reasoning_section}

### Editorial Checklist

- [ ] Content flows naturally in context
- [ ] Author's voice is preserved
- [ ] No redundancy with other sections
- [ ] Formatting matches book style

---

<sub>{llm_response.usage.format_summary()}</sub>"""

        set_output("pr_body", pr_body)

        # Response comment with full editorial info
        response_comment = f"""Creating PR to integrate content into `{target_path}`.

{reasoning_section}

<sub>{llm_response.usage.format_summary()}</sub>"""

        set_output("response_comment", response_comment)

        print(f"PR creation prepared for {target_path}")
        return

    # === Handle /ai-editor place in [file] ===
    if "/ai-editor place in" in comment_lower:
        match = re.search(r"place in (\S+\.md)", comment_lower)
        if match:
            filename = match.group(1)
            set_output("create_pr", "false")
            set_output(
                "response_comment",
                f"Got it! I'll target `chapters/{filename}` when creating the PR.\n\n"
                f"When you're ready, just say `/ai-editor create PR`.",
            )
            print(f"Target file set to {filename}")
            return

    # === Handle general /ai-editor mention ===
    if "/ai-editor" in comment_lower:
        print("Generating conversational response...")

        # Build conversation history
        history = f"**Original transcript:**\n{issue.body}\n\n"
        for c in comments:
            role = "Author" if c["user"] != "github-actions[bot]" else "AI Editor"
            history += f"**{role}:**\n{c['body'][:500]}\n\n"

        prompt = f"""You are an editorial assistant having a conversation about integrating a voice memo into a book.

{history}

**Latest message from author:**
{comment_body}

Respond helpfully and concisely. If they've:
- Answered your questions: acknowledge and confirm understanding
- Given direction: confirm you understand and ask if they want to proceed
- Asked a question: answer based on your analysis
- Said to create a PR: remind them to type "/ai-editor create PR"

Keep responses brief and focused. You're a collaborator, not a lecturer."""

        llm_response = call_editorial(prompt, max_tokens=2000)
        print(f"LLM call complete: {llm_response.usage.format_compact()}")

        # Add reasoning and usage info to response
        reasoning_section = llm_response.format_editorial_explanation()
        response_with_info = f"{llm_response.content}\n\n{reasoning_section}\n\n<sub>{llm_response.usage.format_summary()}</sub>"

        set_output("create_pr", "false")
        set_output("response_comment", response_with_info)
        print("Conversational response generated")
        return

    # No /ai-editor mention found
    set_output("create_pr", "false")
    set_output("response_comment", "")
    print("No /ai-editor command found, skipping.")


if __name__ == "__main__":
    main()
