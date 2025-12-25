"""Editorial phases and configurable prompts for AI Book Editor.

This module defines:
1. BookPhase - Where is the whole project? (new/drafting/revising/polishing)
2. EditorialPhase - Where is this specific piece? (discovery/feedback/revision/complete)

BookPhase influences HOW the editor gives feedback:
- NEW: Extra encouraging, focus on capturing ideas, help with structure
- DRAFTING: Balance encouragement and feedback, track consistency
- REVISING: More rigorous, focus on structure and flow, identify gaps
- POLISHING: Line-level feedback, copyediting, final consistency checks

EditorialPhase tracks the workflow for individual content:
- DISCOVERY -> FEEDBACK -> REVISION -> POLISH -> COMPLETE

Key concept: Discovery questions can spawn their own issues, and
Q&A history feeds into the learning/RAG system.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# BOOK PROJECT PHASES
# =============================================================================


class BookPhase(str, Enum):
    """
    Book project lifecycle phases.

    These represent where the WHOLE PROJECT is, not individual pieces.
    The book phase influences how the editor behaves across all interactions.
    """

    NEW = "new"  # Just starting, capturing vision, building structure
    DRAFTING = "drafting"  # Writing first drafts, messy middle
    REVISING = "revising"  # Major structural revisions, second draft
    POLISHING = "polishing"  # Final cleanup, copyediting, pre-publish
    COMPLETE = "complete"  # Book is finished


# Book phase configuration - how the editor should behave at each phase
BOOK_PHASE_CONFIG: Dict[BookPhase, dict] = {
    BookPhase.NEW: {
        "name": "New Project",
        "description": "Capturing vision and building initial structure",
        "editor_focus": [
            "Help author articulate their vision",
            "Ask about target audience and goals",
            "Encourage every submission",
            "Avoid nitpicking or detailed critique",
            "Help develop initial outline/structure",
            "Celebrate momentum, not perfection",
        ],
        "feedback_style": "encouraging",
        "criticism_level": "minimal",
        "suggested_duration": "2-4 weeks",
        "transition_signals": [
            "Author has clear vision documented",
            "Basic chapter structure exists",
            "Several chapters are in progress",
        ],
    },
    BookPhase.DRAFTING: {
        "name": "Drafting",
        "description": "Writing first drafts, getting content on the page",
        "editor_focus": [
            "Balance encouragement with substantive feedback",
            "Focus on content and meaning over polish",
            "Track consistency across chapters",
            "Identify emerging themes",
            "Help author push through the messy middle",
            "Provide regular progress check-ins",
        ],
        "feedback_style": "balanced",
        "criticism_level": "moderate",
        "suggested_duration": "2-6 months",
        "transition_signals": [
            "All planned chapters have first drafts",
            "Author feels 'done' with initial pass",
            "Major content decisions are made",
        ],
    },
    BookPhase.REVISING: {
        "name": "Revising",
        "description": "Major structural revisions and second draft work",
        "editor_focus": [
            "More rigorous structural feedback",
            "Focus on flow, pacing, and consistency",
            "Identify gaps and redundancies",
            "Push for clarity and precision",
            "Challenge weak arguments or sections",
            "Suggest cuts, moves, and expansions",
        ],
        "feedback_style": "rigorous",
        "criticism_level": "high",
        "suggested_duration": "1-3 months",
        "transition_signals": [
            "Structure is solid",
            "No major content gaps remain",
            "Author ready for line-level work",
        ],
    },
    BookPhase.POLISHING: {
        "name": "Polishing",
        "description": "Final cleanup, copyediting, and pre-publish prep",
        "editor_focus": [
            "Line-level editing and prose refinement",
            "Grammar, punctuation, and style consistency",
            "Final consistency sweep across chapters",
            "Front/back matter review",
            "Help with blurb and marketing copy",
            "Final read-through for flow",
        ],
        "feedback_style": "precise",
        "criticism_level": "detailed",
        "suggested_duration": "2-4 weeks",
        "transition_signals": [
            "No remaining prose concerns",
            "Author confident in final product",
            "Ready for publication/submission",
        ],
    },
    BookPhase.COMPLETE: {
        "name": "Complete",
        "description": "Book is finished and ready for publication",
        "editor_focus": [
            "Celebrate completion!",
            "Provide summary of the journey",
            "Help with next steps (querying, publishing, etc.)",
            "Archive learnings for future projects",
        ],
        "feedback_style": "celebratory",
        "criticism_level": "none",
        "suggested_duration": "N/A",
        "transition_signals": [],
    },
}


def get_book_phase_guidance(phase: BookPhase) -> str:
    """
    Get editorial guidance for a book phase.

    Returns a formatted string that can be included in prompts to guide
    the editor's behavior based on where the project is in its lifecycle.
    """
    config = BOOK_PHASE_CONFIG[phase]
    lines = []

    lines.append(f"## Book Phase: {config['name']}")
    lines.append("")
    lines.append(f"*{config['description']}*")
    lines.append("")
    lines.append(f"**Feedback style:** {config['feedback_style']}")
    lines.append(f"**Criticism level:** {config['criticism_level']}")
    lines.append("")
    lines.append("**Your focus at this phase:**")
    for focus in config["editor_focus"]:
        lines.append(f"- {focus}")
    lines.append("")

    return "\n".join(lines)


def suggest_phase_transition(
    current_phase: BookPhase,
    chapters_drafted: int,
    chapters_planned: int,
    author_signals: List[str],
) -> Optional[BookPhase]:
    """
    Suggest whether it's time to transition to the next phase.

    Args:
        current_phase: Current book phase
        chapters_drafted: Number of chapters with first drafts
        chapters_planned: Total planned chapters
        author_signals: Phrases from recent author messages

    Returns:
        Suggested next phase, or None if no transition recommended
    """
    # Get config for current phase (not used directly but documents intent)
    _ = BOOK_PHASE_CONFIG[current_phase]

    # Check for author-expressed readiness
    author_text = " ".join(author_signals).lower()
    ready_phrases = [
        "ready for the next phase",
        "time to revise",
        "done with first draft",
        "ready to polish",
        "let's finish this",
    ]

    explicit_ready = any(phrase in author_text for phrase in ready_phrases)

    if current_phase == BookPhase.NEW:
        # Transition to drafting when structure exists and chapters started
        if chapters_drafted >= 2 or explicit_ready:
            return BookPhase.DRAFTING

    elif current_phase == BookPhase.DRAFTING:
        # Transition to revising when all chapters have first drafts
        if chapters_planned > 0 and chapters_drafted >= chapters_planned:
            return BookPhase.REVISING
        if explicit_ready:
            return BookPhase.REVISING

    elif current_phase == BookPhase.REVISING:
        # Transition to polishing when author is ready for line editing
        if explicit_ready or "polish" in author_text or "copyedit" in author_text:
            return BookPhase.POLISHING

    elif current_phase == BookPhase.POLISHING:
        # Transition to complete when author declares done
        if "done" in author_text or "finished" in author_text or "complete" in author_text:
            return BookPhase.COMPLETE

    return None


# =============================================================================
# EDITORIAL PHASES (per-issue workflow)
# =============================================================================


class EditorialPhase(str, Enum):
    """Editorial workflow phases tracked via GitHub labels."""

    DISCOVERY = "discovery"  # Asking questions, understanding intent
    FEEDBACK = "feedback"  # Providing editorial analysis
    REVISION = "revision"  # Author is revising based on feedback
    POLISH = "polish"  # Final refinements
    COMPLETE = "complete"  # Ready for publication
    HOLD = "hold"  # Waiting period (author reflection)


# GitHub label configuration for phases
PHASE_LABELS: Dict[EditorialPhase, dict] = {
    EditorialPhase.DISCOVERY: {
        "name": "phase:discovery",
        "color": "7057ff",  # Purple
        "description": "Editor is asking questions before giving feedback",
    },
    EditorialPhase.FEEDBACK: {
        "name": "phase:feedback",
        "color": "0075ca",  # Blue
        "description": "Editorial feedback being provided",
    },
    EditorialPhase.REVISION: {
        "name": "phase:revision",
        "color": "e4e669",  # Yellow
        "description": "Author is revising based on feedback",
    },
    EditorialPhase.POLISH: {
        "name": "phase:polish",
        "color": "0e8a16",  # Green
        "description": "Final polish and refinements",
    },
    EditorialPhase.COMPLETE: {
        "name": "phase:complete",
        "color": "1d7c1d",  # Dark green
        "description": "Editorial work complete",
    },
    EditorialPhase.HOLD: {
        "name": "phase:hold",
        "color": "d4c5f9",  # Light purple
        "description": "On hold for author reflection",
    },
}


class EmotionalState(str, Enum):
    """Detected emotional states that affect editorial approach."""

    VULNERABLE = "vulnerable"  # Early draft, needs encouragement
    CONFIDENT = "confident"  # Ready for rigorous feedback
    FRUSTRATED = "frustrated"  # Needs empathy first
    BLOCKED = "blocked"  # Needs help getting unstuck
    DEFENSIVE = "defensive"  # Needs to feel heard
    EXCITED = "excited"  # Riding momentum, support it
    UNCERTAIN = "uncertain"  # Needs clarity and direction


# Emotional state indicators (for detection)
EMOTIONAL_INDICATORS: Dict[EmotionalState, List[str]] = {
    EmotionalState.VULNERABLE: [
        "this is rough",
        "first draft",
        "not sure if",
        "probably bad",
        "be gentle",
        "nervous",
        "scared to share",
    ],
    EmotionalState.CONFIDENT: [
        "ready for feedback",
        "tear it apart",
        "don't hold back",
        "give me the hard truth",
        "almost done",
        "final draft",
    ],
    EmotionalState.FRUSTRATED: [
        "stuck",
        "frustrated",
        "can't figure out",
        "nothing works",
        "hate this",
        "ugh",
        "argh",
    ],
    EmotionalState.BLOCKED: [
        "blocked",
        "blank page",
        "can't start",
        "don't know where to begin",
        "paralyzed",
        "frozen",
    ],
    EmotionalState.DEFENSIVE: [
        "but i like it",
        "you don't understand",
        "that's intentional",
        "i disagree",
        "you're wrong",
    ],
    EmotionalState.EXCITED: [
        "i love this",
        "breakthrough",
        "finally",
        "it clicked",
        "so excited",
        "can't wait",
    ],
    EmotionalState.UNCERTAIN: [
        "not sure",
        "what do you think",
        "is this right",
        "confused",
        "lost",
        "help",
    ],
}


class DiscoveryQuestion(BaseModel):
    """A discovery question asked by the editor."""

    model_config = ConfigDict(strict=True)

    question: str = Field(description="The question text")
    category: str = Field(description="Category: intake, emotional, intent, socratic")
    persona_id: str = Field(description="Which persona asked this")
    context: Optional[str] = Field(default=None, description="Context about why this was asked")


class DiscoveryResponse(BaseModel):
    """Author's response to discovery questions."""

    model_config = ConfigDict(strict=True)

    questions_asked: List[DiscoveryQuestion] = Field(description="Questions that were asked")
    author_response: str = Field(description="Author's full response")
    extracted_insights: List[str] = Field(
        default_factory=list,
        description="Key insights extracted for knowledge base",
    )
    detected_emotional_state: Optional[EmotionalState] = Field(
        default=None, description="Detected emotional state"
    )
    ready_for_feedback: bool = Field(default=False, description="Whether discovery is complete")


class PhaseTransition(BaseModel):
    """Record of a phase transition for learning."""

    model_config = ConfigDict(strict=True)

    from_phase: EditorialPhase
    to_phase: EditorialPhase
    trigger: str = Field(description="What triggered the transition")
    issue_number: int
    persona_id: Optional[str] = None


class DiscoveryIssue(BaseModel):
    """A standalone discovery question issue."""

    model_config = ConfigDict(strict=True)

    title: str = Field(description="Issue title")
    body: str = Field(description="Question and context")
    parent_issue: Optional[int] = Field(
        default=None, description="Parent issue if spawned from another"
    )
    question_category: str = Field(description="intake, intent, socratic")
    persona_id: str


# Configurable prompt templates
PHASE_PROMPTS: Dict[EditorialPhase, dict] = {
    EditorialPhase.DISCOVERY: {
        "system_intro": """You are in DISCOVERY mode. Your job is to ASK, not TELL.

Before providing any editorial feedback, you must understand:
1. Where the author is emotionally
2. What they're trying to achieve
3. What feedback would actually help them right now

Ask questions. Listen. Understand. Only then can you truly help.""",
        "transition_prompt": """Based on the author's responses to your discovery questions,
you now have enough context to provide meaningful feedback.

Summarize what you learned:
- Author's emotional state:
- Author's goals for this piece:
- What kind of feedback they need:
- Key context that will shape your feedback:

Now transition to FEEDBACK mode.""",
    },
    EditorialPhase.FEEDBACK: {
        "system_intro": """You are in FEEDBACK mode. You've completed discovery and understand
the author's context, goals, and emotional state.

Structure your feedback with clear priority tiers:
1. CRITICAL: Must address before publishing
2. RECOMMENDED: Would strengthen the work
3. OPTIONAL: Style preferences, take or leave

Remember what you learned in discovery. Tailor your feedback accordingly.""",
        "with_discovery_context": """Based on your discovery conversation, you learned:

{discovery_summary}

Now provide feedback that honors what the author told you.""",
    },
    EditorialPhase.REVISION: {
        "system_intro": """The author is now REVISING based on your feedback.

Your role shifts:
- Answer questions about your feedback
- Clarify suggestions when asked
- Offer encouragement for good changes
- Gently redirect if they're going off track

Be responsive, not directive.""",
    },
    EditorialPhase.HOLD: {
        "system_intro": """This piece is on HOLD for author reflection.

The author needs time to sit with this work. Do not push for action.
If they return, ask how their thinking has evolved.""",
        "hold_message": """I'm placing this on hold for you to reflect. Take your time.

When you're ready to revisit, just comment here. I'll be curious to hear
what you've been thinking about.""",
    },
}


# Knowledge extraction patterns for RAG
KNOWLEDGE_PATTERNS = {
    "author_preference": {
        "indicators": [
            "i prefer",
            "i always",
            "i never",
            "i like to",
            "my style is",
        ],
        "extract_as": "preference",
    },
    "writing_goal": {
        "indicators": [
            "i want readers to",
            "the goal is",
            "i'm trying to",
            "this book should",
        ],
        "extract_as": "goal",
    },
    "audience": {
        "indicators": [
            "my readers are",
            "written for",
            "target audience",
            "people who",
        ],
        "extract_as": "audience",
    },
    "voice_choice": {
        "indicators": [
            "my voice",
            "i write like",
            "influenced by",
            "inspired by",
        ],
        "extract_as": "voice",
    },
    "correction": {
        "indicators": [
            "actually",
            "no, i meant",
            "that's not what i",
            "let me clarify",
        ],
        "extract_as": "correction",
    },
}


def get_phase_label(phase: EditorialPhase) -> str:
    """Get the GitHub label name for a phase."""
    return PHASE_LABELS[phase]["name"]


def detect_emotional_state(text: str) -> Optional[EmotionalState]:
    """
    Detect the author's emotional state from their text.

    Returns the most likely emotional state based on keyword matching.
    Returns None if no clear state is detected.
    """
    text_lower = text.lower()
    scores: Dict[EmotionalState, int] = {}

    for state, indicators in EMOTIONAL_INDICATORS.items():
        score = sum(1 for indicator in indicators if indicator in text_lower)
        if score > 0:
            scores[state] = score

    if not scores:
        return None

    return max(scores, key=scores.get)


def should_skip_discovery(text: str, labels: List[str]) -> bool:
    """
    Check if discovery phase should be skipped.

    Skip discovery when:
    - Author explicitly says "skip discovery" or "just review"
    - Phase label is already feedback or later
    - Issue has "quick-review" label
    """
    skip_phrases = [
        "skip discovery",
        "just review",
        "skip the questions",
        "don't ask",
        "give me feedback",
        "tear it apart",  # Confident = ready for feedback
    ]

    text_lower = text.lower()
    if any(phrase in text_lower for phrase in skip_phrases):
        return True

    # Check labels
    skip_labels = ["quick-review", "phase:feedback", "phase:revision", "phase:polish"]
    if any(lbl in labels for lbl in skip_labels):
        return True

    return False


def extract_knowledge_items(text: str) -> List[dict]:
    """
    Extract knowledge items from author text for RAG/learning.

    Returns a list of dicts with 'type' and 'content' keys.
    """
    items = []
    text_lower = text.lower()

    for pattern_name, pattern_config in KNOWLEDGE_PATTERNS.items():
        for indicator in pattern_config["indicators"]:
            if indicator in text_lower:
                # Find the sentence containing the indicator
                sentences = text.split(".")
                for sentence in sentences:
                    if indicator in sentence.lower():
                        items.append(
                            {
                                "type": pattern_config["extract_as"],
                                "pattern": pattern_name,
                                "content": sentence.strip(),
                                "indicator": indicator,
                            }
                        )
                        break  # Only extract once per pattern

    return items


def build_discovery_prompt(
    persona_discovery: dict,
    content: str,
    emotional_state: Optional[EmotionalState] = None,
) -> str:
    """
    Build the discovery prompt for a persona.

    Args:
        persona_discovery: The discovery section from persona JSON
        content: The content being submitted
        emotional_state: Detected emotional state (if any)

    Returns:
        Formatted discovery prompt
    """
    lines = []

    # Philosophy
    lines.append("## Your Discovery Approach")
    lines.append("")
    lines.append(persona_discovery.get("philosophy", "Ask before you tell."))
    lines.append("")

    # Emotional adjustment
    if emotional_state:
        lines.append(f"**Detected emotional state:** {emotional_state.value}")
        if emotional_state in [
            EmotionalState.VULNERABLE,
            EmotionalState.FRUSTRATED,
            EmotionalState.BLOCKED,
        ]:
            lines.append("")
            lines.append(persona_discovery.get("emotional_check", ""))
            lines.append("")
        lines.append("")

    # Questions to ask
    lines.append("## Questions to Consider Asking")
    lines.append("")
    lines.append("**Intake questions** (understand their goals):")
    for q in persona_discovery.get("intake_questions", []):
        lines.append(f"- {q}")
    lines.append("")

    lines.append("**Intent questions** (understand their choices):")
    for q in persona_discovery.get("intent_questions", []):
        lines.append(f"- {q}")
    lines.append("")

    lines.append("**Socratic prompts** (help them see issues themselves):")
    for q in persona_discovery.get("socratic_prompts", []):
        lines.append(f"- {q}")
    lines.append("")

    lines.append("## Instructions")
    lines.append("")
    lines.append("1. Read the content carefully")
    lines.append("2. Choose 2-4 questions most relevant to THIS piece")
    lines.append("3. Ask them in YOUR voice (stay in character)")
    lines.append("4. Wait for the author's response before giving feedback")
    lines.append("5. Make the author feel heard, not interrogated")
    lines.append("")

    return "\n".join(lines)


def format_discovery_questions_for_issue(
    questions: List[str],
    persona_name: str,
    philosophy: str,
) -> str:
    """Format discovery questions for posting as an issue comment."""
    lines = []

    lines.append("## Before I dive in...")
    lines.append("")
    lines.append(f"*{philosophy}*")
    lines.append("")

    for i, question in enumerate(questions, 1):
        lines.append(f"**{i}.** {question}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Take your time with these. Reply when you're ready, "
        "and I'll give you feedback that actually fits what you need."
    )
    lines.append("")
    lines.append(f"*— {persona_name}*")

    return "\n".join(lines)


# Issue templates for different phase-related issues
ISSUE_TEMPLATES = {
    "discovery_question": {
        "title": "[Discovery] {question_summary}",
        "labels": ["ai-question", "phase:discovery"],
        "body": """## Question for the Author

{question}

---

**Context:** This question was spawned from Issue #{parent_issue} to explore a specific aspect that will help inform editorial feedback.

**Persona:** {persona_name}

Reply to this issue with your thoughts. Your answer will be incorporated into the editorial knowledge base.
""",
    },
    "editorial_hold": {
        "title": "[Hold] {piece_title} - Reflection Period",
        "labels": ["phase:hold"],
        "body": """## On Hold for Reflection

{persona_name} has placed this piece on hold to give you time to reflect.

**Hold reason:** {hold_reason}

**Suggested reflection time:** {hold_duration}

---

When you're ready to continue, comment on this issue and remove the `phase:hold` label.
""",
    },
    "whole_book_review": {
        "title": "[Review] Full Manuscript Analysis",
        "labels": ["phase:discovery", "whole-book"],
        "body": """## Whole Book Discovery

Before providing comprehensive feedback, I need to understand the full scope:

{discovery_questions}

---

This analysis will read across all chapters to identify:
- Cross-chapter consistency
- Thematic threads
- Character arcs
- Repetition patterns
- Promise/payoff tracking
""",
    },
}


def create_discovery_issue_body(
    question: str,
    parent_issue: int,
    persona_name: str,
    context: Optional[str] = None,
) -> str:
    """Create the body for a standalone discovery question issue."""
    template = ISSUE_TEMPLATES["discovery_question"]["body"]
    return template.format(
        question=question,
        parent_issue=parent_issue,
        persona_name=persona_name,
    )
