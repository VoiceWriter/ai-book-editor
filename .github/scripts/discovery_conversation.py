#!/usr/bin/env python3
"""
Discovery conversation handler for AI Book Editor.

This script implements the "ask before tell" philosophy:
1. When new content arrives, the editor asks questions first
2. Author responses are captured and feed into knowledge base
3. Only after discovery does the editor provide feedback

This creates a more collaborative, Perkins-style editorial relationship
where the editor understands the author's intent before critiquing.

OUTPUTS:
- discovery_comment: The discovery questions to post
- phase_label: The phase label to add (phase:discovery)
- emotional_state: Detected emotional state
- skip_discovery: Whether to skip discovery and go straight to feedback
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import BaseModel, ConfigDict, Field
from scripts.utils.github_client import (
    add_labels,  # noqa: E402
    get_github_client,
    get_issue,
    get_issue_comments,
    get_repo,
)
from scripts.utils.knowledge_base import load_editorial_context  # noqa: E402
from scripts.utils.llm_client import call_editorial_structured  # noqa: E402
from scripts.utils.persona import format_discovery_prompt, load_persona  # noqa: E402
from scripts.utils.phases import (
    PHASE_LABELS,
    EditorialPhase,  # noqa: E402
    detect_emotional_state,
    extract_knowledge_items,
    should_skip_discovery,
)


class DiscoveryQuestions(BaseModel):
    """Structured output for discovery questions."""

    model_config = ConfigDict(strict=True)

    questions: list[str] = Field(
        description="2-4 discovery questions tailored to this specific content"
    )
    emotional_observation: Optional[str] = Field(
        default=None,
        description="Optional observation about author's emotional state",
    )
    opening_line: str = Field(description="A warm, in-character opening before the questions")
    closing_line: str = Field(description="A closing that invites response without pressure")


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


def generate_discovery_questions(
    content: str,
    persona_id: str,
    emotional_state: Optional[str],
    context: dict,
) -> tuple[DiscoveryQuestions, dict]:
    """
    Generate discovery questions using the persona's question bank.

    Returns the questions and the LLM response for logging.
    """
    persona = load_persona(persona_id)
    discovery_prompt = format_discovery_prompt(persona, emotional_state)

    task_prompt = f"""{discovery_prompt}

## The Content to Review

{content[:4000]}

## Generate Your Discovery Questions

Based on this content, generate 2-4 discovery questions that:
1. Are specific to THIS piece (not generic)
2. Help you understand the author's intent
3. Are asked in YOUR voice ({persona.name})
4. Will make the author feel heard, not interrogated

Return a structured response with:
- An opening line (warm, in character)
- 2-4 questions
- A closing line (invites response without pressure)
"""

    result, llm_response = call_editorial_structured(
        prompt=task_prompt,
        response_model=DiscoveryQuestions,
        max_tokens=2000,
    )

    return result, {
        "reasoning": llm_response.reasoning,
        "usage": llm_response.usage.model_dump() if llm_response.usage else None,
    }


def format_discovery_comment(
    questions: DiscoveryQuestions,
    persona_name: str,
    emotional_state: Optional[str],
) -> str:
    """Format the discovery questions as a GitHub comment."""
    lines = []

    # Opening
    lines.append(questions.opening_line)
    lines.append("")

    # Emotional observation if present
    if questions.emotional_observation:
        lines.append(f"*{questions.emotional_observation}*")
        lines.append("")

    # Questions
    lines.append("---")
    lines.append("")
    for i, question in enumerate(questions.questions, 1):
        lines.append(f"**{i}.** {question}")
        lines.append("")

    # Closing
    lines.append("---")
    lines.append("")
    lines.append(questions.closing_line)
    lines.append("")
    lines.append(f"*— {persona_name}*")

    # Phase indicator
    lines.append("")
    lines.append("<sub>Phase: Discovery | Reply to continue the conversation</sub>")

    return "\n".join(lines)


def check_for_existing_discovery(comments: list) -> bool:
    """Check if discovery questions have already been asked."""
    for comment in comments:
        body = comment.get("body", "")
        if "Phase: Discovery" in body:
            return True
    return False


def extract_discovery_context(comments: list) -> Optional[dict]:
    """
    Extract context from previous discovery Q&A.

    Returns dict with questions asked and author responses.
    """
    discovery_questions = []
    author_responses = []

    in_discovery = False
    for comment in comments:
        body = comment.get("body", "")
        user = comment.get("user", "")

        if "Phase: Discovery" in body:
            in_discovery = True
            # Extract questions from this comment
            for line in body.split("\n"):
                if line.strip().startswith("**") and "?" in line:
                    discovery_questions.append(line.strip())

        elif in_discovery and user != "github-actions[bot]":
            # This is an author response to discovery
            author_responses.append(body)

            # Extract knowledge items from the response
            knowledge_items = extract_knowledge_items(body)
            if knowledge_items:
                print(f"Extracted {len(knowledge_items)} knowledge items from response")

    if not discovery_questions:
        return None

    return {
        "questions": discovery_questions,
        "responses": author_responses,
        "knowledge_items": extract_knowledge_items(" ".join(author_responses)),
    }


def main():
    issue_number = int(os.environ.get("ISSUE_NUMBER", 0))
    if not issue_number:
        print("ERROR: ISSUE_NUMBER not set")
        sys.exit(1)

    gh = get_github_client()
    repo = get_repo(gh)
    issue = get_issue(repo, issue_number)
    comments = get_issue_comments(issue)

    # Get issue content
    content = issue.body or ""
    labels = [lbl.name for lbl in issue.labels]

    # Detect emotional state
    emotional_state = detect_emotional_state(content)
    if emotional_state:
        print(f"Detected emotional state: {emotional_state.value}")
        set_output("emotional_state", emotional_state.value)

    # Check if we should skip discovery
    if should_skip_discovery(content, labels):
        print("Author requested to skip discovery, proceeding to feedback")
        set_output("skip_discovery", "true")
        set_output("discovery_comment", "")
        return

    # Check if discovery already happened
    if check_for_existing_discovery(comments):
        print("Discovery already completed, checking for responses")

        # Extract context from discovery
        discovery_context = extract_discovery_context(comments)
        if discovery_context and discovery_context["responses"]:
            print("Found discovery responses, ready for feedback phase")
            set_output("skip_discovery", "true")
            set_output("discovery_context", json.dumps(discovery_context))

            # Save knowledge items for learning
            if discovery_context.get("knowledge_items"):
                knowledge_path = Path(".ai-context/discovery-knowledge.jsonl")
                knowledge_path.parent.mkdir(parents=True, exist_ok=True)
                with open(knowledge_path, "a") as f:
                    for item in discovery_context["knowledge_items"]:
                        item["issue_number"] = issue_number
                        f.write(json.dumps(item) + "\n")
                print(f"Saved {len(discovery_context['knowledge_items'])} knowledge items")

            return
        else:
            print("Discovery questions asked but no response yet, waiting")
            set_output("skip_discovery", "false")
            set_output("waiting_for_response", "true")
            return

    # Load editorial context to get persona
    context = load_editorial_context(repo, labels=labels)
    persona_id = context.get("persona_id", "margot")

    print(f"Generating discovery questions with persona: {persona_id}")

    # Generate discovery questions
    questions, llm_info = generate_discovery_questions(
        content=content,
        persona_id=persona_id,
        emotional_state=emotional_state.value if emotional_state else None,
        context=context,
    )

    # Load persona for name
    persona = load_persona(persona_id)

    # Format the comment
    discovery_comment = format_discovery_comment(
        questions=questions,
        persona_name=persona.name,
        emotional_state=emotional_state.value if emotional_state else None,
    )

    # Set outputs
    set_output("skip_discovery", "false")
    set_output("discovery_comment", discovery_comment)
    set_output("phase_label", PHASE_LABELS[EditorialPhase.DISCOVERY]["name"])

    # Add phase label to issue
    try:
        add_labels(issue, [PHASE_LABELS[EditorialPhase.DISCOVERY]["name"]])
        print(f"Added {PHASE_LABELS[EditorialPhase.DISCOVERY]['name']} label")
    except Exception as e:
        print(f"Warning: Could not add phase label: {e}")

    # Ensure output directory exists
    Path("output").mkdir(exist_ok=True)

    # Save discovery comment to file
    Path("output/discovery-comment.md").write_text(discovery_comment)

    print(f"Generated {len(questions.questions)} discovery questions")
    print("Discovery comment saved to output/discovery-comment.md")

    # Log reasoning if available
    if llm_info.get("reasoning"):
        print(f"LLM reasoning available ({len(llm_info['reasoning'])} chars)")


if __name__ == "__main__":
    main()
