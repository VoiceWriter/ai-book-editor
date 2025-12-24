#!/usr/bin/env python3
"""
Respond to @margot-ai-editor commands in issue comments.

This script uses LLM to infer the author's intent from natural conversation
and executes appropriate CRUD actions on issues/PRs.

Supported actions (inferred from conversation):
- Create PR from voice memo content
- Set target file placement
- Close/reopen issues
- Add/remove labels
- Edit issue title/body
- Create follow-up issues
- Approve/request changes on PRs
- Merge PRs
- General conversational responses

OUTPUTS:
- create_pr: 'true' if PR should be created
- target_file: path to target file for PR
- scope: commit message scope
- pr_body: PR description content
- response_comment: comment to post
- cleaned_content: content for the PR (written to file)
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import (  # noqa: E402
    add_labels,
    close_issue,
    create_issue,
    edit_issue,
    get_github_client,
    get_issue,
    get_issue_comments,
    get_repo,
    remove_labels,
    reopen_issue,
)
from scripts.utils.knowledge_base import load_editorial_context  # noqa: E402
from scripts.utils.llm_client import (
    ConversationalIntent,  # noqa: E402
    LLMResponse,
    call_editorial,
    call_editorial_structured,
)
from scripts.utils.persona import (
    format_persona_list,  # noqa: E402
    parse_persona_command,
)
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


def extract_cleaned_transcript(comments: list) -> str:
    """Extract the cleaned transcript from AI's previous analysis."""
    for comment in reversed(comments):
        body = comment.get("body", "")
        if "### Cleaned Transcript" in body:
            match = re.search(
                r"### Cleaned Transcript\s*\n(.*?)(?=###|\n---|\Z)", body, re.DOTALL
            )
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


def build_intent_prompt(
    issue,
    comments: list,
    comment_body: str,
    issue_number: int,
    editorial_context: dict = None,
) -> str:
    """Build prompt for inferring user intent from conversation."""
    # Build conversation history
    history = f"**Original transcript/issue body:**\n{issue.body}\n\n"
    for c in comments:
        role = "Author" if c["user"] != "github-actions[bot]" else "AI Editor"
        history += f"**{role}:**\n{c['body'][:800]}\n\n"

    # Get current issue state
    labels = [lbl.name for lbl in issue.labels]
    state = issue.state

    # Build editorial context section if available
    persona_section = ""
    guidelines_section = ""
    if editorial_context:
        if editorial_context.get("persona"):
            persona_section = f"""
## Your Editorial Persona
{editorial_context['persona']}
"""
        if editorial_context.get("guidelines"):
            guidelines_section = f"""
## Editorial Guidelines (Follow These)
{editorial_context['guidelines']}
"""

    return f"""You are an AI book editor assistant. Analyze this conversation and determine what action(s) the author wants you to take.
{persona_section}{guidelines_section}

## Current Issue State
- Issue #{issue_number}: "{issue.title}"
- State: {state}
- Labels: {', '.join(labels) if labels else 'none'}

## Conversation History
{history}

## Latest Message from Author
{comment_body}

## Available Actions

For issues, you can:
- `close` - Close the issue (with optional reason: completed, not_planned, duplicate)
- `reopen` - Reopen a closed issue
- `add_labels` - Add labels (specify which ones)
- `remove_labels` - Remove labels (specify which ones)
- `edit_title` - Change the issue title
- `edit_body` - Update the issue body
- `create_issue` - Create a new follow-up issue
- `set_placement` - Set target file for PR (e.g., "chapter-03.md")
- `create_pr` - Create a PR to integrate the content
- `respond` - Just respond conversationally (no action)
- `none` - No action needed

## Instructions

1. Infer the author's intent from their message
2. If they want an action taken, specify it clearly
3. If they're asking a question or chatting, use `respond` action
4. If unclear, ask a clarifying question
5. For destructive actions (close, edit_body), ask for confirmation unless they're very explicit
6. Be helpful and proactive - if they say "looks good, go ahead" after discussing placement, that probably means `create_pr`

Return a structured response with the action(s) to take and a natural language response to send."""


def infer_intent(
    issue,
    comments: list,
    comment_body: str,
    issue_number: int,
    repo=None,
) -> tuple[ConversationalIntent, LLMResponse]:
    """
    Use LLM to infer user intent from conversation.

    Loads editorial context (persona, guidelines) to ensure the AI
    responds in character and follows the established rules.

    Returns (intent, llm_response) - llm_response contains reasoning.
    """
    # Load editorial context for consistent persona
    # Pass labels and comment for persona resolution
    editorial_context = None
    if repo:
        try:
            labels = [lbl.name for lbl in issue.labels]
            editorial_context = load_editorial_context(
                repo,
                labels=labels,
                comment=comment_body,
            )
            persona_info = ""
            if editorial_context.get("persona_id"):
                persona_info = f" (persona: {editorial_context['persona_id']} via {editorial_context['persona_source']})"
            print(f"Loaded editorial context{persona_info}")
        except Exception as e:
            print(f"Warning: Could not load editorial context: {e}")

    prompt = build_intent_prompt(
        issue=issue,
        comments=comments,
        comment_body=comment_body,
        issue_number=issue_number,
        editorial_context=editorial_context,
    )

    intent, llm_response = call_editorial_structured(
        prompt=prompt,
        response_model=ConversationalIntent,
        max_tokens=4000,
    )

    # Log the reasoning for learning and transparency
    try:
        logger = get_actions_logger()

        # Build conversation summary
        summary = f"Issue #{issue_number}: {issue.title[:50]}..."
        if comments:
            summary += f" ({len(comments)} comments)"

        # Extract reasoning
        reasoning_text = llm_response.reasoning or ""
        thinking_blocks = [b.thinking for b in llm_response.thinking_blocks]

        # Build list of proposed actions
        actions_proposed = []
        for action in intent.issue_actions:
            if action.action == "close":
                actions_proposed.append(
                    f"close (reason: {action.close_reason or 'completed'})"
                )
            elif action.action == "create_pr":
                actions_proposed.append("create PR")
            elif action.action == "add_labels":
                actions_proposed.append(f"add labels: {', '.join(action.labels)}")
            elif action.action == "set_placement":
                actions_proposed.append(f"set placement: {action.target_file}")
            elif action.action not in ("none", "respond"):
                actions_proposed.append(action.action)

        logger.log_decision(
            issue_number=issue_number,
            author_message=comment_body[:500],
            conversation_summary=summary,
            model_used=llm_response.usage.model if llm_response.usage else "unknown",
            reasoning=reasoning_text,
            thinking_blocks=thinking_blocks,
            inferred_intent=intent.response_text[:200],
            confidence=intent.confidence,
            actions_proposed=actions_proposed,
            confirmation_required=intent.needs_confirmation
            or intent.confidence != "high",
            tokens_used=llm_response.usage.total_tokens if llm_response.usage else 0,
            cost_usd=llm_response.usage.cost_usd if llm_response.usage else 0.0,
        )
        print("Reasoning logged to .ai-context/reasoning-log.jsonl")
    except Exception as e:
        print(f"Warning: Could not log reasoning: {e}")

    return intent, llm_response


def execute_issue_actions(
    issue, repo, intent: ConversationalIntent, issue_number: int
) -> list[str]:
    """Execute issue actions and return list of actions taken."""
    actions_taken = []

    for action in intent.issue_actions:
        if action.action == "close":
            close_issue(issue)
            reason = action.close_reason or "completed"
            actions_taken.append(f"Closed issue (reason: {reason})")

        elif action.action == "reopen":
            reopen_issue(issue)
            actions_taken.append("Reopened issue")

        elif action.action == "add_labels":
            if action.labels:
                add_labels(issue, action.labels)
                actions_taken.append(f"Added labels: {', '.join(action.labels)}")

        elif action.action == "remove_labels":
            if action.labels:
                remove_labels(issue, action.labels)
                actions_taken.append(f"Removed labels: {', '.join(action.labels)}")

        elif action.action == "edit_title":
            if action.title:
                edit_issue(issue, title=action.title)
                actions_taken.append(f"Updated title to: {action.title}")

        elif action.action == "edit_body":
            if action.body:
                edit_issue(issue, body=action.body)
                actions_taken.append("Updated issue body")

        elif action.action == "create_issue":
            if action.title:
                new_issue = create_issue(
                    repo,
                    title=action.title,
                    body=action.body or "",
                    labels=action.labels if action.labels else None,
                )
                actions_taken.append(
                    f"Created issue #{new_issue.number}: {action.title}"
                )

    return actions_taken


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

    # Check if @margot-ai-editor is mentioned at all (support both @ and / prefix)
    if (
        "@margot-ai-editor" not in comment_body.lower()
        and "@margot-ai-editor" not in comment_body.lower()
    ):
        # No ai-editor mention found
        set_output("create_pr", "false")
        set_output("response_comment", "")
        print("No @margot-ai-editor command found, skipping.")
        return

    # === Handle persona commands first (before intent inference) ===
    persona_id, cmd_type, remaining = parse_persona_command(comment_body)

    # Handle "list personas" command
    if cmd_type == "list":
        persona_list = format_persona_list()
        set_output("create_pr", "false")
        set_output("response_comment", persona_list)
        print("Returned persona list")
        return

    # Handle "use <persona>" command (sticky - adds label)
    if cmd_type == "use" and persona_id:
        # Add persona label to issue
        new_label = f"persona:{persona_id}"
        try:
            add_labels(issue, [new_label])
            response = f"Switching to **{persona_id}** persona for this issue.\n\n"
            response += "All future responses will use this persona until you switch again.\n\n"
            response += f"*Label `{new_label}` added to issue.*"

            # If there's remaining text, note we'll process it
            if remaining.strip():
                response += f"\n\n---\n\nProcessing your request: *{remaining.strip()}*"
                # Continue to process the remaining request with the new persona
            else:
                set_output("create_pr", "false")
                set_output("response_comment", response)
                print(f"Switched to persona: {persona_id}")
                return
        except Exception as e:
            print(f"Warning: Could not add persona label: {e}")
            # Continue anyway - the persona will still be used via comment parsing

    print("Inferring user intent from conversation...")

    # Use LLM to infer intent (with editorial context)
    try:
        intent, llm_response = infer_intent(
            issue, comments, comment_body, issue_number, repo=repo
        )
        print(
            f"Intent inferred: confidence={intent.confidence}, understood={intent.understood}"
        )
        print(f"LLM usage: {llm_response.usage.format_compact()}")
    except Exception as e:
        print(f"Error inferring intent: {e}")
        set_output("create_pr", "false")
        set_output(
            "response_comment",
            f"Sorry, I had trouble understanding that request. Could you rephrase? Error: {str(e)}",
        )
        return

    # Check if we need confirmation or clarification
    # Require confirmation for low/medium confidence (< 80% certainty)
    needs_confirmation = (
        intent.needs_confirmation
        or intent.clarifying_question
        or intent.confidence in ("low", "medium")
    )

    # Check if there are any significant actions that would need confirmation
    has_significant_actions = any(
        a.action in ("close", "edit_body", "create_pr", "create_issue")
        for a in intent.issue_actions
    )

    if needs_confirmation and has_significant_actions:
        # Build confirmation message
        proposed_actions = []
        for action in intent.issue_actions:
            if action.action == "close":
                proposed_actions.append(
                    f"Close this issue (reason: {action.close_reason or 'completed'})"
                )
            elif action.action == "create_pr":
                proposed_actions.append("Create a PR to integrate this content")
            elif action.action == "create_issue":
                proposed_actions.append(f"Create new issue: {action.title}")
            elif action.action == "edit_body":
                proposed_actions.append("Edit the issue body")
            elif action.action == "add_labels":
                proposed_actions.append(f"Add labels: {', '.join(action.labels)}")
            elif action.action == "remove_labels":
                proposed_actions.append(f"Remove labels: {', '.join(action.labels)}")
            elif action.action == "set_placement":
                proposed_actions.append(f"Set target file to: {action.target_file}")

        if proposed_actions:
            actions_list = "\n".join(f"- {a}" for a in proposed_actions)
            question = (
                intent.clarifying_question or "Should I proceed with these actions?"
            )

            confidence_note = ""
            if intent.confidence == "low":
                confidence_note = "\n\n*I'm not entirely sure I understood correctly. Please confirm or clarify.*"
            elif intent.confidence == "medium":
                confidence_note = (
                    "\n\n*Just want to make sure I got this right before proceeding.*"
                )

            response = f"""{intent.response_text}

**I understood you want me to:**
{actions_list}

**{question}**{confidence_note}

Reply with:
- "yes" or "go ahead" to confirm
- "no" or specific corrections to clarify

<sub>{llm_response.usage.format_summary()}</sub>"""

            set_output("create_pr", "false")
            set_output("response_comment", response)
            print(f"Requesting confirmation (confidence: {intent.confidence})")
            return

    # Execute non-PR actions first
    actions_taken = execute_issue_actions(issue, repo, intent, issue_number)
    if actions_taken:
        print(f"Actions executed: {', '.join(actions_taken)}")

        # Log outcome for learning
        try:
            logger = get_actions_logger()
            logger.update_outcome(
                issue_number=issue_number,
                outcome="auto_executed",
                actions_executed=actions_taken,
            )
        except Exception as e:
            print(f"Warning: Could not log outcome: {e}")

    # Check for create_pr action
    has_create_pr = any(a.action == "create_pr" for a in intent.issue_actions)
    has_set_placement = any(a.action == "set_placement" for a in intent.issue_actions)

    # Get target file from set_placement action or existing conversation
    target_file_from_intent = None
    for action in intent.issue_actions:
        if action.action == "set_placement" and action.target_file:
            target_file_from_intent = action.target_file

    # Normalize command for explicit commands (backwards compatibility)
    comment_lower = comment_body.lower()

    # === Handle explicit @margot-ai-editor create PR or inferred create_pr ===
    if "@margot-ai-editor create pr" in comment_lower or has_create_pr:
        print("Preparing PR creation...")

        # Determine target file - from intent, conversation, or ask
        target_filename = target_file_from_intent
        was_explicit = bool(target_file_from_intent)

        if not was_explicit:
            target_filename, was_explicit = extract_target_file(comments, issue_number)

        if not was_explicit:
            # No explicit placement - ask the author instead of dumping to generic file
            set_output("create_pr", "false")
            set_output(
                "response_comment",
                "**I need to know where to put this content.**\n\n"
                "Please specify the target by saying one of:\n"
                "- `@margot-ai-editor place in chapter-03.md` - to add to an existing chapter\n"
                "- `@margot-ai-editor place in new-chapter.md` - to create a new chapter\n"
                "- `@margot-ai-editor place in uncategorized.md` - if you're not sure yet\n\n"
                "Then say `@margot-ai-editor create PR` again.",
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

        existing_chapter = (
            read_file_content(repo, target_path)
            if target_filename != "uncategorized.md"
            else None
        )

        # Build conversation history for context
        history = f"**Original voice memo:**\n{issue.body}\n\n"
        for c in comments:
            history += f"**{c['user']}:** {c['body'][:1000]}\n\n"

        # Call LLM to prepare editorial-quality content
        print("Calling LLM to prepare editorial content...")

        # Build prompt sections
        persona_section = (
            "**Editor Persona:** " + context["persona"]
            if context.get("persona")
            else ""
        )
        guidelines_section = (
            "**Editorial Guidelines:** " + context["guidelines"]
            if context.get("guidelines")
            else ""
        )
        if existing_chapter:
            existing_section = (
                "**Existing chapter content:**\n" + existing_chapter[:2000] + "..."
            )
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
                re.DOTALL,
            )
            prepared_content = (
                content_match.group(1).strip() if content_match else response_text
            )
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

    # === Handle @margot-ai-editor place in [file] (explicit command still supported) ===
    if "@margot-ai-editor place in" in comment_lower and has_set_placement:
        # Already handled by intent inference above
        pass

    # === Use intent's response for all other cases ===
    # Build response with any actions that were taken
    response_parts = []

    if actions_taken:
        actions_summary = "\n".join(f"- {a}" for a in actions_taken)
        response_parts.append(f"**Actions taken:**\n{actions_summary}")

    if intent.response_text:
        response_parts.append(intent.response_text)

    # Add usage info
    reasoning_section = llm_response.format_editorial_explanation()
    if reasoning_section:
        response_parts.append(reasoning_section)

    response_parts.append(f"<sub>{llm_response.usage.format_summary()}</sub>")

    full_response = "\n\n".join(response_parts)

    set_output("create_pr", "false")
    set_output("response_comment", full_response)
    print("Response generated from intent inference")


if __name__ == "__main__":
    main()
