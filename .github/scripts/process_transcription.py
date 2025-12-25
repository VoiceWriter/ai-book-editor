#!/usr/bin/env python3
"""
Process voice memo transcriptions from GitHub Issues.

This script:
1. Reads the transcript from the issue body
2. Loads editorial context (persona, guidelines, knowledge base, book config)
3. Detects if this is a NEW PROJECT and adds welcome questions
4. Incorporates discovery context if available (from discovery phase)
5. Adjusts feedback based on book phase (new/drafting/revising/polishing)
6. Calls Claude to clean, analyze, and suggest placement
7. Outputs analysis to file for workflow to post as comment
8. Sets step outputs for workflow to use

DOES NOT: Make direct GitHub API calls for comments/labels (workflow handles that)
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.github_client import get_github_client, get_issue, get_repo  # noqa: E402
from scripts.utils.knowledge_base import load_editorial_context  # noqa: E402
from scripts.utils.llm_client import build_editorial_prompt, call_editorial  # noqa: E402
from scripts.utils.persona import load_persona  # noqa: E402
from scripts.utils.phases import BookPhase  # noqa: E402


def set_output(name: str, value: str):
    """Set a step output for the GitHub Actions workflow."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            # Handle multiline values
            if "\n" in value:
                import uuid

                delimiter = uuid.uuid4().hex
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")


def load_discovery_context() -> Optional[dict]:
    """
    Load discovery context from environment or file.

    Discovery context contains what was learned from the discovery phase:
    - questions_asked: Questions the editor asked
    - author_responses: How the author responded
    - knowledge_items: Extracted insights for personalization
    - emotional_state: Detected emotional state
    """
    # Try environment variable first (set by respond_to_comment.py)
    discovery_json = os.environ.get("DISCOVERY_CONTEXT")
    if discovery_json:
        try:
            return json.loads(discovery_json)
        except json.JSONDecodeError:
            print("Warning: Could not parse DISCOVERY_CONTEXT")

    return None


def build_new_project_welcome(persona_name: str) -> str:
    """Build welcome message for first-time submissions (no book.yaml exists)."""
    return f"""## Welcome! This is exciting.

I'm {persona_name}, and I'll be your editor for this project. This looks like your first submission - I'd love to learn more about what you're working on.

**A few questions to help me help you:**

1. **What's this book about?** Give me the elevator pitch.
2. **Who are you writing this for?** Who's your ideal reader?
3. **What do you want readers to feel or know after reading?**
4. **How polished is this piece?** First draft brain-dump, or something more refined?

*Just reply with whatever feels natural. I'll remember what you share and use it to give you better feedback.*

---

**In the meantime, here's my initial take on what you submitted:**

"""


def build_phase_aware_task(book_phase: Optional[BookPhase], book_context: Optional[str]) -> str:
    """
    Build the analysis task based on current book phase.

    Each phase gets different editorial focus:
    - NEW: Encouraging, focus on ideas, avoid nitpicking
    - DRAFTING: Balance encouragement with substance
    - REVISING: More rigorous, structural feedback
    - POLISHING: Line-level, copyediting focus
    """
    phase_instructions = ""

    if book_phase == BookPhase.NEW:
        phase_instructions = """
**PHASE: NEW PROJECT**
The author is just starting. Focus on:
- Celebrating their ideas and momentum
- Helping them articulate their vision
- Avoiding nitpicky criticism
- Asking about their goals, not fixing their prose
- Building their confidence to keep going
"""
    elif book_phase == BookPhase.DRAFTING:
        phase_instructions = """
**PHASE: DRAFTING**
The author is in the messy middle. Focus on:
- Balance encouragement with substantive feedback
- Content and meaning over polish
- Tracking consistency with what they've written before
- Helping them push through
- Noting emerging themes
"""
    elif book_phase == BookPhase.REVISING:
        phase_instructions = """
**PHASE: REVISING**
The author has first drafts done and wants structural feedback. Focus on:
- More rigorous structural critique
- Flow, pacing, and consistency issues
- Identify gaps and redundancies
- Push for clarity and precision
- Challenge weak sections
- Suggest cuts, moves, and expansions
"""
    elif book_phase == BookPhase.POLISHING:
        phase_instructions = """
**PHASE: POLISHING**
The author is in final cleanup mode. Focus on:
- Line-level editing and prose refinement
- Grammar, punctuation, and style consistency
- Word choice and sentence rhythm
- Final consistency checks
- This is close to done - help them cross the finish line
"""

    if book_context:
        phase_instructions += f"\n{book_context}\n"

    return phase_instructions


def build_discovery_aware_task(
    discovery_context: Optional[dict],
    persona_id: str,
    book_phase: Optional[BookPhase] = None,
    book_context: Optional[str] = None,
) -> str:
    """
    Build the analysis task, incorporating discovery context and book phase.

    When discovery context is present, the task is personalized based on
    what the author shared during discovery.
    """
    # Start with phase-specific instructions
    phase_section = build_phase_aware_task(book_phase, book_context)

    base_task = """Analyze this voice memo transcript and provide:

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

    # Combine phase instructions with base task
    full_task = phase_section + base_task if phase_section else base_task

    if not discovery_context:
        return full_task

    # Build discovery-aware task
    lines = []

    lines.append("## What You Learned in Discovery")
    lines.append("")

    if discovery_context.get("questions_asked"):
        lines.append("You asked:")
        for q in discovery_context["questions_asked"]:
            lines.append(f"- {q}")
        lines.append("")

    if discovery_context.get("author_responses"):
        lines.append("The author responded:")
        for r in discovery_context["author_responses"]:
            lines.append(f"> {r[:300]}...")
        lines.append("")

    if discovery_context.get("emotional_state"):
        state = discovery_context["emotional_state"]
        lines.append(f"**Author's emotional state:** {state}")
        lines.append("")

        # Adjust approach based on emotional state
        if state in ["vulnerable", "frustrated", "blocked"]:
            lines.append("*Approach with extra encouragement. Lead with what's working.*")
        elif state == "confident":
            lines.append("*Author is ready for rigorous feedback. Don't hold back.*")
        elif state == "defensive":
            lines.append("*Author may be protective of this work. Be respectful but honest.*")
        lines.append("")

    if discovery_context.get("knowledge_items"):
        lines.append("**Key insights from discovery:**")
        for item in discovery_context["knowledge_items"]:
            lines.append(f"- {item.get('type', 'insight')}: {item.get('content', '')}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**Now, using what you learned, analyze this transcript:**")
    lines.append("")
    lines.append(full_task)
    lines.append("")
    lines.append("**Remember:** Tailor your feedback to what the author told you during discovery.")
    lines.append("Honor their goals, respect their emotional state, reference their intent.")

    return "\n".join(lines)


def main():
    # Get environment variables
    issue_number = int(os.environ.get("ISSUE_NUMBER", 0))
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
        error_comment = "No transcript found in issue body. Please add the voice memo transcript."
        Path("output").mkdir(exist_ok=True)
        Path("output/analysis-comment.md").write_text(error_comment)
        set_output("success", "false")
        set_output("error", "No transcript in issue body")
        sys.exit(1)

    # Load editorial context
    print("Loading editorial context...")
    labels = [lbl.name for lbl in issue.labels]
    context = load_editorial_context(repo, labels=labels)
    persona_id = context.get("persona_id", "margot")

    # Detect new project (no book.yaml exists)
    is_new_project = context.get("book_config") is None
    book_phase = context.get("book_phase")
    book_context = context.get("book_context")

    if is_new_project:
        print("NEW PROJECT DETECTED - will include welcome message")
        # Treat as NEW phase for feedback style
        book_phase = BookPhase.NEW

    if book_phase:
        print(f"Book phase: {book_phase.value}")

    # Check for discovery context (from discovery phase)
    discovery_context = load_discovery_context()
    if discovery_context:
        print(
            f"Discovery context found: {len(discovery_context.get('author_responses', []))} responses"
        )
        if discovery_context.get("emotional_state"):
            print(f"Author emotional state: {discovery_context['emotional_state']}")

    # Build the analysis prompt (discovery-aware and phase-aware)
    task = build_discovery_aware_task(
        discovery_context=discovery_context,
        persona_id=persona_id,
        book_phase=book_phase,
        book_context=book_context,
    )

    prompt = build_editorial_prompt(
        persona=context["persona"],
        guidelines=context["guidelines"],
        glossary=context["glossary"],
        knowledge_base=context["knowledge_formatted"],
        chapter_list=context["chapters"],
        task=task,
        content=transcript,
    )

    # Call LLM with reasoning enabled
    print("Calling LLM for editorial analysis (with reasoning)...")
    try:
        llm_response = call_editorial(prompt)
        print(f"LLM call complete: {llm_response.usage.format_compact()}")
        if llm_response.has_reasoning():
            print("Editorial reasoning captured for transparency")
    except Exception as e:
        error_comment = f"Error calling AI: {str(e)}"
        Path("output").mkdir(exist_ok=True)
        Path("output/analysis-comment.md").write_text(error_comment)
        set_output("success", "false")
        set_output("error", str(e))
        sys.exit(1)

    # Format the comment with reasoning explanation
    reasoning_section = llm_response.format_editorial_explanation()

    # Get persona name for signature
    try:
        persona = load_persona(persona_id)
        persona_name = persona.name
    except Exception:
        persona_name = "AI Editor"

    # Build welcome section for new projects
    welcome_section = ""
    if is_new_project:
        welcome_section = build_new_project_welcome(persona_name)

    # Note if discovery was used
    discovery_note = ""
    if discovery_context:
        discovery_note = "\n*This feedback is tailored based on our discovery conversation.*\n"

    # Phase indicator
    phase_note = ""
    if book_phase and not is_new_project:
        phase_note = f"\n*Current phase: {book_phase.value}*\n"

    comment = f"""{welcome_section}## AI Editorial Analysis
{discovery_note}{phase_note}
{llm_response.content}

---

### Next Steps

**To integrate this content:**
1. Reply with any feedback or answers to my questions above
2. Specify placement: `@margot-ai-editor place in chapter-name.md`
3. When ready: `@margot-ai-editor create PR`

**Or if this isn't ready:**
- Close this issue if you want to discard it
- Add `awaiting-author` label if you need to think about it
- Just reply with questions or direction

{reasoning_section}

---
*— {persona_name}*

*I'm here to help, not to impose—your voice is what matters.*

<sub>{llm_response.usage.format_summary()} | Phase: Feedback</sub>
"""

    # Output to file for workflow to use
    Path("output").mkdir(exist_ok=True)
    Path("output/analysis-comment.md").write_text(comment)

    # Set step outputs
    set_output("success", "true")
    set_output("has_analysis", "true")
    set_output("is_new_project", str(is_new_project).lower())
    if book_phase:
        set_output("book_phase", book_phase.value)

    print(f"Successfully processed issue #{issue_number}")
    print("Analysis written to output/analysis-comment.md")
    if is_new_project:
        print("New project detected - welcome message included")


if __name__ == "__main__":
    main()
