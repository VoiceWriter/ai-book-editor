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

from scripts.utils.context_management import (  # noqa: E402
    count_tokens,
    prepare_conversation_context,
)
from scripts.utils.conversation_state import (  # noqa: E402
    ConversationState,
    compact_state,
    extract_questions_from_response,
    format_closing_summary,
    format_outstanding_questions_reminder,
    format_prerequisite_blocker,
    get_default_prerequisites,
    parse_state_from_body,
    persist_to_knowledge_base,
    update_issue_body_with_state,
)
from scripts.utils.github_client import close_issue  # noqa: E402
from scripts.utils.github_client import (
    add_labels,
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
from scripts.utils.llm_client import ConversationalIntent  # noqa: E402
from scripts.utils.llm_client import (
    LLMResponse,
    call_editorial,
    call_editorial_structured,
)
from scripts.utils.persona import format_persona_list  # noqa: E402
from scripts.utils.persona import parse_persona_command
from scripts.utils.phases import EditorialPhase  # noqa: E402
from scripts.utils.phases import (
    PHASE_LABELS,
    detect_emotional_state,
    extract_knowledge_items,
)
from scripts.utils.pr_body import build_rich_pr_body  # noqa: E402
from scripts.utils.pr_body import format_rich_pr_body
from scripts.utils.reasoning_log import get_actions_logger  # noqa: E402


def prepare_conversation_for_llm(
    issue_body: str,
    comments: list,
    system_prompt: str,
    established_facts: list[str] = None,
    max_output: int = 8000,
) -> tuple[str, int]:
    """
    Prepare conversation context with context window management.

    Returns (conversation_text, tokens_used).
    Automatically summarizes long conversations to fit within budget.
    """
    # Format comments for context management
    formatted_comments = [
        {"user": c.get("user", "unknown"), "body": c.get("body", "")} for c in comments
    ]

    # Get budget and prepare context
    try:
        _, conversation_text, budget = prepare_conversation_context(
            comments=formatted_comments,
            system_prompt=system_prompt,
            current_content=issue_body or "",
            established_facts=established_facts,
            max_output=max_output,
        )

        print(
            f"Context budget: {budget.total_used():,}/{budget.available_input:,} tokens "
            f"(system: {budget.system_tokens:,}, conv: {budget.conversation_tokens:,}, "
            f"content: {budget.content_tokens:,})"
        )

        return conversation_text, budget.conversation_tokens
    except Exception as e:
        # Fallback to simple formatting if context management fails
        print(f"Warning: Context management failed, using fallback: {e}")
        conv_text = "\n\n".join(
            f"**{c.get('user', 'unknown')}:** {c.get('body', '')[:800]}" for c in comments
        )
        return conv_text, count_tokens(conv_text)


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


def is_in_discovery_phase(labels: list) -> bool:
    """Check if the issue is currently in discovery phase."""
    discovery_label = PHASE_LABELS[EditorialPhase.DISCOVERY]["name"]
    label_names = [lbl if isinstance(lbl, str) else lbl.name for lbl in labels]
    return discovery_label in label_names


def is_discovery_response(comments: list, comment_body: str) -> bool:
    """
    Check if this comment is a response to discovery questions.

    Returns True if:
    - There's a previous comment with "Phase: Discovery"
    - This is a substantive response (not just a command)
    """
    has_discovery_comment = False
    for comment in comments:
        body = comment.get("body", "")
        if "Phase: Discovery" in body:
            has_discovery_comment = True
            break

    if not has_discovery_comment:
        return False

    # Check if this is a substantive response (not just a command)
    comment_lower = comment_body.lower().strip()
    command_indicators = [
        "@margot-ai-editor create pr",
        "@margot-ai-editor use",
        "@margot-ai-editor list",
        "@margot-ai-editor as ",
    ]

    # If it's ONLY a command, not a discovery response
    for indicator in command_indicators:
        if comment_lower.startswith(indicator.lower()):
            return False

    # If it's substantive (more than just a mention), it's a response
    cleaned = re.sub(r"@margot-ai-editor\s*", "", comment_body, flags=re.IGNORECASE)
    return len(cleaned.strip()) > 20


def extract_discovery_context(comments: list) -> dict:
    """
    Extract the full discovery context from previous comments.

    Returns dict with:
    - questions_asked: List of discovery questions
    - author_responses: List of author's responses
    - knowledge_items: Extracted knowledge for RAG
    - emotional_state: Detected emotional state
    """
    discovery_questions = []
    author_responses = []
    all_knowledge_items = []

    in_discovery = False
    for comment in comments:
        body = comment.get("body", "")
        user = comment.get("user", "")

        if "Phase: Discovery" in body:
            in_discovery = True
            # Extract questions from this comment
            for line in body.split("\n"):
                line = line.strip()
                if line.startswith("**") and "?" in line:
                    # Remove markdown formatting
                    q = re.sub(r"\*\*\d+\.\*\*\s*", "", line)
                    discovery_questions.append(q)

        elif in_discovery and user != "github-actions[bot]":
            # This is an author response
            author_responses.append(body)
            # Extract knowledge items
            items = extract_knowledge_items(body)
            all_knowledge_items.extend(items)

    # Detect emotional state from responses
    all_text = " ".join(author_responses)
    emotional_state = detect_emotional_state(all_text)

    return {
        "questions_asked": discovery_questions,
        "author_responses": author_responses,
        "knowledge_items": all_knowledge_items,
        "emotional_state": emotional_state.value if emotional_state else None,
    }


def build_discovery_transition_prompt(
    discovery_context: dict,
    original_content: str,
    persona_id: str,
) -> str:
    """
    Build the prompt for transitioning from discovery to feedback.

    This prompt incorporates what was learned from discovery.
    """
    lines = []

    lines.append("## Discovery Context")
    lines.append("")
    lines.append("You asked the following discovery questions:")
    for q in discovery_context.get("questions_asked", []):
        lines.append(f"- {q}")
    lines.append("")

    lines.append("The author responded:")
    for r in discovery_context.get("author_responses", []):
        lines.append(f"> {r[:500]}")
        lines.append("")

    if discovery_context.get("emotional_state"):
        lines.append(f"**Detected emotional state:** {discovery_context['emotional_state']}")
        lines.append("")

    lines.append("## Key Learnings")
    lines.append("")
    lines.append("Based on the author's discovery responses, you now know:")
    if discovery_context.get("knowledge_items"):
        for item in discovery_context["knowledge_items"]:
            lines.append(f"- {item['type']}: {item['content']}")
    else:
        lines.append("- (Extract insights from their responses)")
    lines.append("")

    lines.append("## Your Task")
    lines.append("")
    lines.append("Now that you understand the author's context, goals, and emotional state,")
    lines.append("provide feedback that is tailored to what they told you.")
    lines.append("")
    lines.append("Remember:")
    lines.append("- Honor what they shared in discovery")
    lines.append("- Adjust your tone based on their emotional state")
    lines.append("- Reference their goals when making suggestions")
    lines.append("")

    return "\n".join(lines)


def build_intent_prompt(
    issue,
    comments: list,
    comment_body: str,
    issue_number: int,
    editorial_context: dict = None,
    conversation_state: ConversationState = None,
) -> str:
    """Build prompt for inferring user intent from conversation."""
    # Build conversation history with context management
    system_prompt = "You are an AI book editor assistant."
    established_facts = []
    if conversation_state:
        established_facts = [f"{fact.key}: {fact.value}" for fact in conversation_state.established]

    conversation_text, tokens_used = prepare_conversation_for_llm(
        issue_body=issue.body or "",
        comments=comments,
        system_prompt=system_prompt,
        established_facts=established_facts,
    )

    history = (
        f"**Original transcript/issue body:**\n{issue.body[:2000]}...\n\n"
        if len(issue.body or "") > 2000
        else f"**Original transcript/issue body:**\n{issue.body}\n\n"
    )
    history += f"**Conversation history ({tokens_used:,} tokens):**\n{conversation_text}"

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
    conversation_state: ConversationState = None,
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
        conversation_state=conversation_state,
    )

    intent, llm_response = call_editorial_structured(
        prompt=prompt,
        response_model=ConversationalIntent,
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
                actions_proposed.append(f"close (reason: {action.close_reason or 'completed'})")
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
            confirmation_required=intent.needs_confirmation or intent.confidence != "high",
            tokens_used=llm_response.usage.total_tokens if llm_response.usage else 0,
            cost_usd=llm_response.usage.cost_usd if llm_response.usage else 0.0,
        )
        print("Reasoning logged to .ai-context/reasoning-log.jsonl")
    except Exception as e:
        print(f"Warning: Could not log reasoning: {e}")

    return intent, llm_response


def execute_issue_actions(
    issue,
    repo,
    intent: ConversationalIntent,
    issue_number: int,
    conversation_state: ConversationState = None,
) -> list[str]:
    """Execute issue actions and return list of actions taken."""
    actions_taken = []

    for action in intent.issue_actions:
        if action.action == "close":
            # Post summary comment before closing
            if conversation_state:
                reason = action.close_reason or "completed"
                summary = format_closing_summary(conversation_state, reason=reason)
                try:
                    issue.create_comment(summary)
                    print("Posted closing summary comment")
                except Exception as e:
                    print(f"Warning: Could not post summary comment: {e}")

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
                actions_taken.append(f"Created issue #{new_issue.number}: {action.title}")

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

    # Load conversation state from issue body
    conversation_state = parse_state_from_body(issue.body or "", issue_number)
    print(
        f"Loaded state: {len(conversation_state.outstanding_questions)} questions, "
        f"{len(conversation_state.prerequisites)} prerequisites"
    )

    # Initialize default prerequisites if this is a new conversation
    if not conversation_state.prerequisites:
        for prereq in get_default_prerequisites():
            conversation_state.add_prerequisite(prereq.requirement)

    # Ensure output directory exists
    Path("output").mkdir(exist_ok=True)

    # Get labels for phase checking
    labels = [lbl.name for lbl in issue.labels]

    # === Handle discovery response (author replying to discovery questions) ===
    if is_in_discovery_phase(labels) and is_discovery_response(comments, comment_body):
        print("Author responding to discovery questions, transitioning to feedback...")

        # Extract discovery context
        discovery_context = extract_discovery_context(comments)

        # Save knowledge items for learning
        if discovery_context.get("knowledge_items"):
            knowledge_path = Path(".ai-context/discovery-knowledge.jsonl")
            knowledge_path.parent.mkdir(parents=True, exist_ok=True)
            import json

            with open(knowledge_path, "a") as f:
                for item in discovery_context["knowledge_items"]:
                    item["issue_number"] = issue_number
                    f.write(json.dumps(item) + "\n")
            print(f"Saved {len(discovery_context['knowledge_items'])} knowledge items")

        # Transition to feedback phase
        try:
            # Remove discovery label, add feedback label
            remove_labels(issue, [PHASE_LABELS[EditorialPhase.DISCOVERY]["name"]])
            add_labels(issue, [PHASE_LABELS[EditorialPhase.FEEDBACK]["name"]])
            print("Transitioned from discovery to feedback phase")
        except Exception as e:
            print(f"Warning: Could not update phase labels: {e}")

        # Set output to trigger feedback processing
        set_output("phase_transition", "discovery_to_feedback")
        set_output("trigger_feedback", "true")
        set_output("discovery_context", json.dumps(discovery_context))

        # Acknowledge the response
        response = "Thank you for sharing that context. Let me now give you feedback that's tailored to what you've told me...\n\n---\n\n"
        response += "*Transitioning to feedback phase...*"
        set_output("response_comment", response)
        set_output("create_pr", "false")

        print("Discovery response processed, triggering feedback phase")
        return

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

    # Use LLM to infer intent (with editorial context and conversation state)
    try:
        intent, llm_response = infer_intent(
            issue,
            comments,
            comment_body,
            issue_number,
            repo=repo,
            conversation_state=conversation_state,
        )
        print(f"Intent inferred: confidence={intent.confidence}, understood={intent.understood}")
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
            question = intent.clarifying_question or "Should I proceed with these actions?"

            confidence_note = ""
            if intent.confidence == "low":
                confidence_note = (
                    "\n\n*I'm not entirely sure I understood correctly. Please confirm or clarify.*"
                )
            elif intent.confidence == "medium":
                confidence_note = "\n\n*Just want to make sure I got this right before proceeding.*"

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
    actions_taken = execute_issue_actions(issue, repo, intent, issue_number, conversation_state)
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

        # Auto-detect if prerequisites are met based on conversation
        # Check for cleaned transcript (indicates content has been written)
        cleaned_transcript = extract_cleaned_transcript(comments)
        if cleaned_transcript and len(cleaned_transcript) > 200:
            conversation_state.mark_prerequisite_met("content written")
            conversation_state.mark_prerequisite_met("outline")  # Implied by having content
            print("Auto-marking prerequisites met: substantial content found")

        # Check for established facts (indicates discovery is complete)
        if len(conversation_state.established) >= 2:
            conversation_state.mark_prerequisite_met("outline")
            print("Auto-marking outline met: sufficient context established")

        # Check prerequisites before allowing PR creation
        blocker_message = format_prerequisite_blocker(conversation_state)
        if blocker_message:
            print("PR creation blocked by prerequisites")
            set_output("create_pr", "false")
            set_output("response_comment", blocker_message)

            # Persist facts and compact state before updating issue
            try:
                persist_to_knowledge_base(conversation_state)
            except Exception as e:
                print(f"Warning: Could not persist to knowledge base: {e}")

            conversation_state = compact_state(conversation_state)

            # Update state in issue body
            try:
                new_body = update_issue_body_with_state(issue.body or "", conversation_state)
                issue.edit(body=new_body)
                print("Updated issue body with conversation state")
            except Exception as e:
                print(f"Warning: Could not update issue body: {e}")

            return

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
            read_file_content(repo, target_path) if target_filename != "uncategorized.md" else None
        )

        # Build conversation history with context management
        # Use established facts to help summarization preserve important context
        established_facts = [f"{fact.key}: {fact.value}" for fact in conversation_state.established]
        conversation_history, conv_tokens = prepare_conversation_for_llm(
            issue_body=issue.body or "",
            comments=comments,
            system_prompt="You are a professional book editor preparing content.",
            established_facts=established_facts,
            max_output=16000,  # Higher for content generation
        )
        history = (
            f"**Original voice memo:**\n{issue.body[:3000]}\n\n"
            if len(issue.body or "") > 3000
            else f"**Original voice memo:**\n{issue.body}\n\n"
        )
        history += f"**Conversation history ({conv_tokens:,} tokens):**\n{conversation_history}"

        # Call LLM to prepare editorial-quality content
        print(f"Calling LLM to prepare editorial content (conversation: {conv_tokens:,} tokens)...")

        # Build prompt sections
        persona_section = (
            "**Editor Persona:** " + context["persona"] if context.get("persona") else ""
        )
        guidelines_section = (
            "**Editorial Guidelines:** " + context["guidelines"]
            if context.get("guidelines")
            else ""
        )
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

        llm_response = call_editorial(editorial_prompt)
        print(f"LLM call complete: {llm_response.usage.format_compact()}")

        # Extract the prepared content
        response_text = llm_response.content
        if "### Prepared Content" in response_text:
            content_match = re.search(
                r"### Prepared Content\s*\n(.*?)(?=### Editorial Notes|### Integration|\Z)",
                response_text,
                re.DOTALL,
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

        # Extract editorial notes from LLM response
        editorial_notes = ""
        if "### Editorial Notes" in response_text:
            notes_match = re.search(
                r"### Editorial Notes\s*\n(.*?)(?=### Integration|\Z)",
                response_text,
                re.DOTALL,
            )
            if notes_match:
                editorial_notes = notes_match.group(1).strip()

        # Extract integration recommendation
        content_summary = ""
        if "### Integration Recommendation" in response_text:
            rec_match = re.search(
                r"### Integration Recommendation\s*\n(.*?)(?=###|\Z)",
                response_text,
                re.DOTALL,
            )
            if rec_match:
                content_summary = rec_match.group(1).strip()
        if not content_summary:
            # Fallback: first 200 chars of prepared content
            content_summary = (
                prepared_content[:200] + "..." if len(prepared_content) > 200 else prepared_content
            )

        # Build rich PR body with all analysis
        try:
            rich_pr = build_rich_pr_body(
                source_issue=issue_number,
                target_file=target_path,
                prepared_content=prepared_content,
                llm_response=llm_response,
                editorial_notes=editorial_notes or "Content prepared for integration.",
                content_summary=content_summary,
                discovery_context=None,  # TODO: Pass discovery context when available
                existing_chapter_content=existing_chapter,
                chapters_list=context.get("chapters", []),
                conversation_state=conversation_state,  # Include decisions & outstanding items
            )
            pr_body = format_rich_pr_body(rich_pr)
        except Exception as e:
            # Fallback to simple format if rich body fails
            print(f"Warning: Rich PR body generation failed: {e}")
            reasoning_section = llm_response.format_editorial_explanation()
            pr_body = f"""## Editorial Integration

**Target:** `{target_path}`
**Source:** Issue #{issue_number}

---

{response_text}

---

{reasoning_section}

<sub>{llm_response.usage.format_summary()}</sub>"""

        # Write PR body to file for reliable multiline handling
        Path("output/pr-body.md").write_text(pr_body + f"\n\n---\n\nCloses #{issue_number}")
        set_output("pr_body", pr_body)

        # Response comment with summary
        reasoning_section = llm_response.format_editorial_explanation()
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

        # Extract questions from response and add to state
        new_questions = extract_questions_from_response(intent.response_text)
        for q in new_questions:
            conversation_state.add_question(q)
            print(f"Tracking new question: {q[:50]}...")

    # Check if the author's comment answers any outstanding questions
    # Simple heuristic: if they answer in depth (>100 chars), mark related questions
    if len(comment_body) > 100:
        for q in conversation_state.outstanding_questions:
            # Check if any key words from the question appear in the response
            key_words = [w.lower() for w in q.question.split() if len(w) > 4]
            if any(kw in comment_body.lower() for kw in key_words[:3]):
                q.answered = True
                print(f"Marking question as answered: {q.question[:50]}...")

    # Add outstanding questions reminder if any remain
    reminder = format_outstanding_questions_reminder(conversation_state)
    if reminder:
        response_parts.append(reminder)

    # Add usage info
    reasoning_section = llm_response.format_editorial_explanation()
    if reasoning_section:
        response_parts.append(reasoning_section)

    response_parts.append(f"<sub>{llm_response.usage.format_summary()}</sub>")

    full_response = "\n\n".join(response_parts)

    # Persist established facts to project-wide knowledge base
    # This enables cross-issue memory
    try:
        facts_written = persist_to_knowledge_base(conversation_state)
        if facts_written > 0:
            print(f"Cross-issue memory: {facts_written} facts now available to other issues")
    except Exception as e:
        print(f"Warning: Could not persist to knowledge base: {e}")

    # Compact state: remove answered questions and met prerequisites
    # They're archived in git history and can be retrieved if needed
    conversation_state = compact_state(conversation_state)

    # Update state in issue body
    try:
        new_body = update_issue_body_with_state(issue.body or "", conversation_state)
        issue.edit(body=new_body)
        print("Updated issue body with conversation state")
    except Exception as e:
        print(f"Warning: Could not update issue body: {e}")

    set_output("create_pr", "false")
    set_output("response_comment", full_response)
    print("Response generated from intent inference")


if __name__ == "__main__":
    main()
