#!/usr/bin/env python3
"""
Answer questions from the author about their book.

This script responds to "Ask the Editor" issues where the author
has a question about their manuscript, writing process, or editorial decisions.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import (  # noqa: E402
    get_github_client,
    get_issue,
    get_repo,
    read_file_content,
)
from scripts.utils.knowledge_base import load_editorial_context  # noqa: E402
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


def main():
    issue_number = int(os.environ.get("ISSUE_NUMBER", 0))
    if not issue_number:
        print("ERROR: ISSUE_NUMBER not set")
        sys.exit(1)

    gh = get_github_client()
    repo = get_repo(gh)
    issue = get_issue(repo, issue_number)

    # Get the question from issue body
    question = issue.body or ""
    if not question.strip():
        set_output(
            "response",
            "I don't see a question in this issue. Could you add your question to the issue body?",
        )
        return

    # Load editorial context
    print("Loading editorial context...")
    context = load_editorial_context(repo)

    # Check if a specific chapter is mentioned
    chapter_content = ""
    if "chapter" in question.lower():
        # Try to find mentioned chapter
        import re

        match = re.search(r"chapter[- ]?(\d+)", question.lower())
        if match:
            chapter_num = match.group(1).zfill(2)
            # Try to read the chapter
            for pattern in [
                f"chapters/chapter-{chapter_num}.md",
                f"chapters/chapter-{chapter_num}-*.md",
            ]:
                from scripts.utils.github_client import list_files_in_directory

                chapters = list_files_in_directory(repo, "chapters")
                for ch in chapters:
                    if f"chapter-{chapter_num}" in ch:
                        content = read_file_content(repo, f"chapters/{ch}")
                        if content:
                            chapter_content = (
                                f"\n\n## Referenced Chapter Content ({ch})\n{content[:3000]}..."
                            )
                        break

    # Build prompt
    prompt = f"""You are the author's AI editor. They have a question for you.

## Your Editorial Persona
{context.get('persona', 'You are a helpful and supportive editor.')}

## Editorial Guidelines
{context.get('guidelines', 'Be helpful and preserve the author voice.')}

## Knowledge Base (What you know about this book)
{context.get('knowledge_formatted', 'No specific knowledge yet.')}

## Existing Chapters
{', '.join(context.get('chapters', []))}
{chapter_content}

## The Author's Question
{question}

---

Please answer the author's question thoughtfully. Consider:
- What you know about their book and writing style
- The editorial guidelines you follow
- Any relevant context from the chapters

Be conversational and helpful. If you need more context to answer well, say so.
If their question relates to a specific part of the manuscript, reference it specifically."""

    print("Generating response...")
    llm_response = call_editorial(prompt, max_tokens=4000)
    print(f"Response generated: {llm_response.usage.format_compact()}")

    # Format response with reasoning
    reasoning_section = llm_response.format_editorial_explanation()

    response = f"""## My Thoughts

{llm_response.content}

---

{reasoning_section}

<sub>{llm_response.usage.format_summary()}</sub>

---

*Feel free to ask follow-up questions by commenting on this issue, or open a new "Ask the Editor" issue for a different topic.*
"""

    set_output("response", response)
    print(f"Response ready for issue #{issue_number}")


if __name__ == "__main__":
    main()
