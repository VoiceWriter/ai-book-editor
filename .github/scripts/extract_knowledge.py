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


def get_author_responses(comments: list) -> list:
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
    author_responses = get_author_responses(comments)

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
