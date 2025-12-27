"""
Context window management for AI Book Editor.

Handles:
- Token counting before LLM calls
- Context window limit checking
- Conversation summarization when threads get long
- Smart truncation that preserves important context

This ensures we never exceed model limits and handle long conversations
gracefully (like issue #33 with 25+ comments).
"""

from typing import Optional

import litellm
from pydantic import BaseModel, ConfigDict, Field

from .llm_client import (
    call_editorial,
    get_model,
    get_model_capabilities,
)


class ContextBudget(BaseModel):
    """Token budget allocation for a conversation."""

    model_config = ConfigDict(strict=True)

    model: str = Field(description="Model being used")
    context_window: int = Field(description="Total context window size")
    max_output: int = Field(description="Reserved for output tokens")
    available_input: int = Field(description="Available for input")

    # Allocations
    system_budget: int = Field(description="Tokens for system prompt")
    conversation_budget: int = Field(description="Tokens for conversation history")
    content_budget: int = Field(description="Tokens for current content")

    # Current usage
    system_tokens: int = Field(default=0, description="Actual system tokens")
    conversation_tokens: int = Field(default=0, description="Actual conversation tokens")
    content_tokens: int = Field(default=0, description="Actual content tokens")

    def total_used(self) -> int:
        """Total tokens currently used."""
        return self.system_tokens + self.conversation_tokens + self.content_tokens

    def remaining(self) -> int:
        """Tokens remaining in budget."""
        return self.available_input - self.total_used()

    def is_over_budget(self) -> bool:
        """Check if we're over the input budget."""
        return self.total_used() > self.available_input

    def needs_summarization(self) -> bool:
        """Check if conversation needs summarization."""
        # Summarize if conversation is over budget or we're at 80% capacity
        return (
            self.conversation_tokens > self.conversation_budget
            or self.total_used() > self.available_input * 0.8
        )


def count_tokens(text: str, model: Optional[str] = None) -> int:
    """
    Count tokens in text for a given model.

    Uses LiteLLM's token counter which handles different tokenizers.
    """
    model = model or get_model()
    try:
        return litellm.token_counter(model=model, text=text)
    except Exception:
        # Fallback: rough estimate of 4 chars per token
        return len(text) // 4


def count_messages_tokens(messages: list[dict], model: Optional[str] = None) -> int:
    """Count tokens in a list of messages."""
    model = model or get_model()
    try:
        return litellm.token_counter(model=model, messages=messages)
    except Exception:
        # Fallback
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += count_tokens(content, model)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total += count_tokens(part["text"], model)
        return total


def get_context_budget(
    model: Optional[str] = None,
    max_output: int = 16000,
    system_ratio: float = 0.3,
    conversation_ratio: float = 0.4,
    content_ratio: float = 0.3,
) -> ContextBudget:
    """
    Calculate context budget for a model.

    Default ratios:
    - 30% for system prompt (persona, guidelines, knowledge base)
    - 40% for conversation history
    - 30% for current content being processed

    These can be adjusted based on use case.
    """
    model = model or get_model()
    caps = get_model_capabilities(model)

    if caps:
        context_window = caps.context
    else:
        # Conservative default
        context_window = 128_000

    # Reserve tokens for output
    available_input = context_window - max_output

    # Allocate budgets
    system_budget = int(available_input * system_ratio)
    conversation_budget = int(available_input * conversation_ratio)
    content_budget = int(available_input * content_ratio)

    return ContextBudget(
        model=model,
        context_window=context_window,
        max_output=max_output,
        available_input=available_input,
        system_budget=system_budget,
        conversation_budget=conversation_budget,
        content_budget=content_budget,
    )


class ConversationSummary(BaseModel):
    """A summarized version of conversation history."""

    model_config = ConfigDict(strict=True)

    summary: str = Field(description="Summarized conversation")
    original_token_count: int = Field(description="Tokens in original")
    summary_token_count: int = Field(description="Tokens in summary")
    comments_summarized: int = Field(description="Number of comments summarized")
    savings_percent: float = Field(description="Percentage of tokens saved")


def summarize_conversation(
    comments: list[dict],
    established_facts: list[str],
    model: Optional[str] = None,
    target_tokens: int = 2000,
) -> ConversationSummary:
    """
    Summarize a conversation to fit within token budget.

    Preserves:
    - Established facts/decisions
    - Most recent 3 exchanges
    - Key questions asked

    Summarizes:
    - Older back-and-forth
    - Verbose explanations
    """
    model = model or get_model()

    # Count original tokens
    original_text = "\n\n".join(
        f"{c.get('user', 'unknown')}: {c.get('body', '')}" for c in comments
    )
    original_tokens = count_tokens(original_text, model)

    # If already under target, no summarization needed
    if original_tokens <= target_tokens:
        return ConversationSummary(
            summary=original_text,
            original_token_count=original_tokens,
            summary_token_count=original_tokens,
            comments_summarized=0,
            savings_percent=0.0,
        )

    # Keep most recent 3 comments in full
    recent_comments = comments[-3:] if len(comments) > 3 else comments
    older_comments = comments[:-3] if len(comments) > 3 else []

    # Format recent comments
    recent_text = "\n\n".join(
        f"**{c.get('user', 'unknown')}:** {c.get('body', '')}" for c in recent_comments
    )

    if not older_comments:
        return ConversationSummary(
            summary=recent_text,
            original_token_count=original_tokens,
            summary_token_count=count_tokens(recent_text, model),
            comments_summarized=0,
            savings_percent=0.0,
        )

    # Format older comments for summarization
    older_text = "\n\n".join(
        f"{c.get('user', 'unknown')}: {c.get('body', '')}" for c in older_comments
    )

    # Build summarization prompt
    established_section = ""
    if established_facts:
        established_section = "**Already established:**\n" + "\n".join(
            f"- {f}" for f in established_facts
        )

    summary_prompt = f"""Summarize this editorial conversation history concisely.

PRESERVE:
- All decisions made
- All questions asked by the editor
- Author's key responses
- Any established facts about the book

{established_section}

CONVERSATION TO SUMMARIZE:
{older_text}

OUTPUT FORMAT:
Write a brief summary (under 500 words) capturing:
1. What was discussed
2. What was decided
3. What questions were asked
4. What answers were given

Do NOT include any preamble. Start directly with the summary."""

    # Call LLM for summarization
    # Note: max_tokens must be > thinking.budget_tokens for extended thinking models
    response = call_editorial(
        summary_prompt,
        system="You are a precise summarizer. Extract only the essential information.",
        max_tokens=16000,
    )

    # HARD FACT EXTRACTION: Re-inject established facts explicitly
    # Don't trust the LLM summary alone - facts go at the top
    facts_section = ""
    if established_facts:
        facts_section = "## Established Facts (PRESERVE THESE)\n"
        facts_section += "\n".join(f"- {fact}" for fact in established_facts)
        facts_section += "\n\n"

    # Combine: facts first, then summary, then recent comments
    full_summary = f"""{facts_section}## Conversation Summary (earlier discussion)

{response.content}

## Recent Discussion

{recent_text}"""

    summary_tokens = count_tokens(full_summary, model)

    return ConversationSummary(
        summary=full_summary,
        original_token_count=original_tokens,
        summary_token_count=summary_tokens,
        comments_summarized=len(older_comments),
        savings_percent=round((1 - summary_tokens / original_tokens) * 100, 1),
    )


def prepare_conversation_context(
    comments: list[dict],
    system_prompt: str,
    current_content: str,
    established_facts: Optional[list[str]] = None,
    model: Optional[str] = None,
    max_output: int = 16000,
) -> tuple[str, str, ContextBudget]:
    """
    Prepare conversation context that fits within model limits.

    Returns:
        Tuple of (system_prompt, conversation_context, budget)

    The conversation_context may be summarized if the original
    exceeds the budget.
    """
    model = model or get_model()
    budget = get_context_budget(model, max_output)

    # Count system tokens
    budget.system_tokens = count_tokens(system_prompt, model)

    # Count content tokens
    budget.content_tokens = count_tokens(current_content, model)

    # Format conversation
    conversation_text = "\n\n".join(
        f"**{c.get('user', 'unknown')}:** {c.get('body', '')}" for c in comments
    )
    budget.conversation_tokens = count_tokens(conversation_text, model)

    # Check if we need to summarize
    if budget.needs_summarization():
        print(
            f"Context budget exceeded ({budget.total_used():,} / {budget.available_input:,}). "
            f"Summarizing conversation..."
        )

        summary = summarize_conversation(
            comments,
            established_facts or [],
            model,
            target_tokens=budget.conversation_budget,
        )

        conversation_text = summary.summary
        budget.conversation_tokens = summary.summary_token_count

        print(
            f"Summarized {summary.comments_summarized} comments. "
            f"Saved {summary.savings_percent}% tokens."
        )

    # System budget monitoring
    check_system_budget(budget)

    return system_prompt, conversation_text, budget


def check_system_budget(budget: ContextBudget, threshold: float = 0.9) -> None:
    """
    Check if system prompt is approaching budget limits.

    Logs warnings when system tokens exceed threshold of budget.
    """
    if budget.system_tokens > budget.system_budget * threshold:
        usage_pct = budget.system_tokens / budget.system_budget * 100
        print(
            f"WARNING: System prompt at {usage_pct:.0f}% of budget "
            f"({budget.system_tokens:,}/{budget.system_budget:,} tokens). "
            f"Consider reducing persona/guidelines/knowledge base size."
        )

    if budget.is_over_budget():
        print(
            f"CRITICAL: Context is over budget! "
            f"Total: {budget.total_used():,}, Available: {budget.available_input:,}. "
            f"Responses may be truncated or fail."
        )


class CompactedContext(BaseModel):
    """A compacted version of completed/archived items."""

    model_config = ConfigDict(strict=True)

    summary: str = Field(description="Brief summary of completed work")
    items_compacted: int = Field(description="Number of items compacted")
    references: list[str] = Field(
        default_factory=list,
        description="References to where details can be found (issues, PRs, commits)",
    )
    original_tokens: int = Field(description="Tokens before compacting")
    compacted_tokens: int = Field(description="Tokens after compacting")


def compact_completed_items(
    completed_questions: list[str],
    completed_prerequisites: list[str],
    closed_issues: list[int] = None,
    merged_prs: list[int] = None,
    model: str = None,
) -> CompactedContext:
    """
    Compact completed/archived items into a brief reference.

    Instead of keeping full text of completed items, replace with:
    - Brief summary of what was done
    - References to where details live (issues, PRs, git log)

    This keeps active context lean while preserving ability to
    look up details when needed.
    """
    model = model or get_model()

    items = []
    references = []

    if completed_questions:
        items.extend(completed_questions)
    if completed_prerequisites:
        items.extend(completed_prerequisites)

    if not items:
        return CompactedContext(
            summary="",
            items_compacted=0,
            references=[],
            original_tokens=0,
            compacted_tokens=0,
        )

    # Count original tokens
    original_text = "\n".join(items)
    original_tokens = count_tokens(original_text, model)

    # Build references
    if closed_issues:
        for issue_num in closed_issues:
            references.append(f"Issue #{issue_num} (closed)")
    if merged_prs:
        for pr_num in merged_prs:
            references.append(f"PR #{pr_num} (merged)")

    # For small amounts, don't bother compacting
    if len(items) <= 3 and original_tokens < 500:
        return CompactedContext(
            summary=f"Completed: {'; '.join(items[:3])}",
            items_compacted=len(items),
            references=references,
            original_tokens=original_tokens,
            compacted_tokens=original_tokens,
        )

    # Compact into brief summary
    summary_parts = []
    if completed_questions:
        summary_parts.append(f"{len(completed_questions)} questions answered")
    if completed_prerequisites:
        summary_parts.append(f"{len(completed_prerequisites)} prerequisites met")
    if closed_issues:
        summary_parts.append(f"{len(closed_issues)} issues resolved")
    if merged_prs:
        summary_parts.append(f"{len(merged_prs)} PRs merged")

    summary = f"Previously completed: {', '.join(summary_parts)}."
    if references:
        summary += f" See: {', '.join(references[:5])}"
        if len(references) > 5:
            summary += f" (+{len(references) - 5} more)"

    compacted_tokens = count_tokens(summary, model)

    return CompactedContext(
        summary=summary,
        items_compacted=len(items),
        references=references,
        original_tokens=original_tokens,
        compacted_tokens=compacted_tokens,
    )


def truncate_to_budget(
    text: str, max_tokens: int, model: Optional[str] = None, keep_end: bool = False
) -> str:
    """
    Truncate text to fit within token budget.

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens allowed
        model: Model for tokenization
        keep_end: If True, keep the end of text (truncate beginning)

    Returns:
        Truncated text with indicator
    """
    model = model or get_model()
    current_tokens = count_tokens(text, model)

    if current_tokens <= max_tokens:
        return text

    # Binary search for the right length
    # Rough estimate: 4 chars per token
    target_chars = (max_tokens * 4) - 50  # Leave room for truncation indicator

    if keep_end:
        truncated = "...(earlier content truncated)...\n\n" + text[-target_chars:]
    else:
        truncated = text[:target_chars] + "\n\n...(content truncated)..."

    return truncated


# =============================================================================
# LITELLM RESPONSE CACHING (different from prompt caching)
# =============================================================================


def enable_litellm_caching(cache_type: str = "local") -> None:
    """
    Enable LiteLLM's response caching.

    This caches RESPONSES, not prompts. Useful when:
    - Same exact query might be repeated
    - Testing/development to avoid repeated API calls

    Args:
        cache_type: "local" for in-memory, "redis" for Redis, "s3" for S3
    """
    if cache_type == "local":
        # In-memory cache - good for single-process apps
        litellm.cache = litellm.Cache()
    elif cache_type == "redis":
        # Redis cache - good for multi-process/distributed
        import os

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        litellm.cache = litellm.Cache(type="redis", host=redis_url)
    elif cache_type == "s3":
        # S3 cache - good for serverless
        import os

        litellm.cache = litellm.Cache(
            type="s3",
            s3_bucket_name=os.environ.get("LITELLM_CACHE_BUCKET"),
            s3_region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )

    print(f"LiteLLM response caching enabled: {cache_type}")


def disable_litellm_caching() -> None:
    """Disable LiteLLM response caching."""
    litellm.cache = None
    print("LiteLLM response caching disabled")
