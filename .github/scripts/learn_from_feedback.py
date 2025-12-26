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
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import get_github_client, get_repo, read_file_content  # noqa: E402
from scripts.utils.llm_client import call_editorial  # noqa: E402
from scripts.utils.reasoning_log import get_actions_logger  # noqa: E402


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


def get_reasoning_patterns() -> dict:
    """Analyze patterns from the AI's reasoning logs."""
    logger = get_actions_logger()

    patterns = {
        "rejected_decisions": [],
        "low_confidence_outcomes": [],
        "reasoning_samples": [],
        "stats": logger.get_confirmation_patterns(),
    }

    # Get rejected decisions - these are learning opportunities
    rejected = logger.get_rejected_decisions(limit=20)
    for entry in rejected:
        patterns["rejected_decisions"].append(
            {
                "issue": entry["issue_number"],
                "author_said": entry["author_message"][:200],
                "ai_understood": entry["inferred_intent"],
                "ai_reasoning": entry["reasoning"][:500] if entry.get("reasoning") else "",
                "ai_proposed": entry["actions_proposed"],
                "author_feedback": entry.get("author_feedback", ""),
            }
        )

    # Get recent entries to sample reasoning
    recent = logger.get_recent_entries(limit=10)
    for entry in recent:
        if entry.get("reasoning"):
            patterns["reasoning_samples"].append(
                {
                    "issue": entry["issue_number"],
                    "confidence": entry["confidence"],
                    "reasoning_excerpt": entry["reasoning"][:300],
                    "outcome": entry["outcome"],
                }
            )

    return patterns


def get_recent_feedback(repo, days: int = 7) -> dict:
    """Collect feedback from recent issues and PRs."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    feedback = {"issue_comments": [], "pr_reviews": [], "pr_comments": []}

    # Get recent closed issues
    for issue in repo.get_issues(state="closed", sort="updated", direction="desc"):
        if issue.updated_at < cutoff:
            break
        if issue.pull_request:
            continue  # Skip PRs in issue list

        for comment in issue.get_comments():
            if comment.user.login != "github-actions[bot]":
                feedback["issue_comments"].append(
                    {
                        "issue": issue.number,
                        "title": issue.title,
                        "comment": comment.body,
                        "date": comment.created_at.isoformat(),
                    }
                )

    # Get recent merged PRs
    for pr in repo.get_pulls(state="closed", sort="updated", direction="desc"):
        if pr.updated_at < cutoff:
            break
        if not pr.merged:
            continue

        for review in pr.get_reviews():
            if review.user.login != "github-actions[bot]":
                feedback["pr_reviews"].append(
                    {
                        "pr": pr.number,
                        "title": pr.title,
                        "state": review.state,
                        "body": review.body,
                        "date": review.submitted_at.isoformat() if review.submitted_at else None,
                    }
                )

        for comment in pr.get_review_comments():
            if comment.user.login != "github-actions[bot]":
                feedback["pr_comments"].append(
                    {
                        "pr": pr.number,
                        "file": comment.path,
                        "comment": comment.body,
                        "date": comment.created_at.isoformat(),
                    }
                )

    return feedback


def main():
    gh = get_github_client()
    repo = get_repo(gh)

    # Get recent feedback from GitHub
    print("Collecting recent feedback...")
    feedback = get_recent_feedback(repo)

    # Get reasoning patterns from logs
    print("Analyzing AI reasoning patterns...")
    reasoning_patterns = get_reasoning_patterns()

    total_items = (
        len(feedback["issue_comments"])
        + len(feedback["pr_reviews"])
        + len(feedback["pr_comments"])
        + len(reasoning_patterns["rejected_decisions"])
    )

    if total_items < 3:
        print("Not enough feedback to analyze (minimum 3 items).")
        set_output("has_suggestions", "false")
        sys.exit(0)

    # Load current guidelines
    persona = read_file_content(repo, "EDITOR_PERSONA.md") or ""
    guidelines = read_file_content(repo, "EDITORIAL_GUIDELINES.md") or ""

    # Build reasoning analysis section
    reasoning_section = ""
    if reasoning_patterns["rejected_decisions"]:
        reasoning_section = "\n### AI Reasoning Analysis (from chain-of-thought logs)\n\n"
        reasoning_section += f"**Stats:** {reasoning_patterns['stats']}\n\n"
        reasoning_section += "**Rejected Decisions (learning opportunities):**\n"
        for rej in reasoning_patterns["rejected_decisions"][:5]:
            reasoning_section += f"""
- Issue #{rej['issue']}:
  - Author said: "{rej['author_said'][:100]}..."
  - AI understood: "{rej['ai_understood']}"
  - AI proposed: {rej['ai_proposed']}
  - AI reasoning: "{rej['ai_reasoning'][:200]}..."
  - Author feedback: "{rej['author_feedback'][:100] if rej['author_feedback'] else 'None'}"
"""

    # Analyze with Claude
    prompt = f"""Analyze this author feedback AND the AI's reasoning patterns to identify improvements.

**IMPORTANT**: Pay special attention to the AI Reasoning Analysis section. When the AI's reasoning
led to rejected decisions, this is a direct learning opportunity. Identify what the AI got wrong
in its chain-of-thought and suggest how to improve.

Analyze this author feedback to identify patterns and suggest improvements to the AI editor's guidelines.

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
{reasoning_section}

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

    print("Analyzing feedback patterns (with chain-of-thought reasoning)...")
    llm_response = call_editorial(prompt, max_tokens=16384)
    response = llm_response.content

    # Log the learning analysis reasoning
    if llm_response.has_reasoning():
        print(f"Learning analysis reasoning captured ({len(llm_response.reasoning or '')} chars)")

    # Check if there are actual suggestions
    if "no clear patterns" in response.lower() or "no necessary changes" in response.lower():
        print("No significant patterns found.")
        set_output("has_suggestions", "false")
        sys.exit(0)

    # Create output directory
    Path("output").mkdir(exist_ok=True)

    # Write learning report
    report_content = f"""# AI Learning Report - {datetime.utcnow().strftime('%Y-%m-%d')}

## Feedback Analyzed
- Issue comments: {len(feedback['issue_comments'])}
- PR reviews: {len(feedback['pr_reviews'])}
- PR inline comments: {len(feedback['pr_comments'])}

{response}

---
*This report was automatically generated by AI Book Editor's learning system.*
"""

    Path("output/learning-report.md").write_text(report_content)

    # Set outputs for workflow
    set_output("has_suggestions", "true")

    # Extract summary for PR body
    summary = ""
    if "### Summary of Learnings" in response:
        summary_part = response.split("### Summary of Learnings")[1]
        summary = summary_part.split("###")[0].strip()[:500]

    set_output("summary", summary)
    set_output("changes", response)

    print("Learning analysis complete. Suggestions generated.")


if __name__ == "__main__":
    main()
