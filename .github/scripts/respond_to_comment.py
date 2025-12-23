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
                "Couldn't find my cleaned transcript. Using original content. "
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
            f"Creating PR to add content to `{target_path}`...")

        print(f"PR creation prepared for {target_path}")
        return

    # === Handle @ai-editor place in [file] ===
    if '@ai-editor place in' in comment_lower:
        match = re.search(r'place in (\S+\.md)', comment_lower)
        if match:
            filename = match.group(1)
            set_output('create_pr', 'false')
            set_output('response_comment',
                f"Got it! I'll target `chapters/{filename}` when creating the PR.\n\n"
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
- Answered your questions: acknowledge and confirm understanding
- Given direction: confirm you understand and ask if they want to proceed
- Asked a question: answer based on your analysis
- Said to create a PR: remind them to type "@ai-editor create PR"

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
