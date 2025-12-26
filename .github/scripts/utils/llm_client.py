"""
LLM client utilities for AI Book Editor.

Uses LiteLLM for unified access to reasoning-capable models ONLY.
We require models that support chain-of-thought reasoning so the AI editor
can explain its editorial decisions transparently.

## Model Registry

We maintain an explicit capability registry because:
- No Python library reliably auto-discovers reasoning-capable LLMs
- "Reasoning" is not a stable, standardized property across providers
- Providers don't expose machine-readable capability flags

Registry must be manually updated when new models are released.
See: REASONING_MODEL_REGISTRY below.

## Refreshing the Registry

To update supported models:
1. Check provider docs (links in REASONING_MODEL_REGISTRY)
2. Verify model supports extended thinking / chain-of-thought
3. Add to registry with appropriate capabilities
4. Test with `litellm.supports_reasoning(model)` if available

Configure via environment:
    MODEL=claude-sonnet-4-5-20250929   (default - Claude Sonnet 4.5)
    MODEL=deepseek-reasoner            (DeepSeek V3.2)
    MODEL=o4-mini                      (OpenAI fast reasoning)
"""

import json
import os
from typing import Any, Dict, List, Literal, Optional, Tuple
from typing import Type as TypingType
from typing import TypeVar

import litellm
from pydantic import BaseModel, ConfigDict, Field

# Suppress LiteLLM's verbose logging
litellm.suppress_debug_info = True


# =============================================================================
# PYDANTIC MODELS - Strict typing for all data structures
# =============================================================================


class ThinkingBlock(BaseModel):
    """A single thinking/reasoning block from the model."""

    model_config = ConfigDict(strict=True, frozen=True)

    type: str = Field(description="Type of thinking block")
    thinking: str = Field(description="The reasoning/thinking content")
    signature: Optional[str] = Field(default=None, description="Optional signature")


class LLMUsage(BaseModel):
    """Token usage and cost information from an LLM call."""

    model_config = ConfigDict(strict=True, frozen=True)

    model: str = Field(description="Model identifier used for the call")
    prompt_tokens: int = Field(ge=0, description="Number of input tokens")
    completion_tokens: int = Field(ge=0, description="Number of output tokens")
    total_tokens: int = Field(ge=0, description="Total tokens (prompt + completion)")
    cost_usd: float = Field(ge=0.0, description="Estimated cost in USD")
    cache_read_tokens: int = Field(default=0, ge=0, description="Tokens read from cache")
    cache_creation_tokens: int = Field(default=0, ge=0, description="Tokens used to create cache")

    def format_summary(self) -> str:
        """Format a human-readable summary for comments/PRs."""
        base = (
            f"**AI Usage:** {self.total_tokens:,} tokens "
            f"({self.prompt_tokens:,} in / {self.completion_tokens:,} out) · "
            f"${self.cost_usd:.4f} · {self.model}"
        )
        if self.cache_read_tokens > 0:
            base += f" · 📦 {self.cache_read_tokens:,} cached"
        return base

    def format_compact(self) -> str:
        """Format a compact single-line summary."""
        return f"{self.total_tokens:,} tokens · ${self.cost_usd:.4f}"


class LLMResponse(BaseModel):
    """Complete response from an LLM call including reasoning."""

    model_config = ConfigDict(strict=True)

    content: str = Field(description="The main response content")
    reasoning: Optional[str] = Field(default=None, description="Extracted reasoning content")
    thinking_blocks: List[ThinkingBlock] = Field(
        default_factory=list, description="Structured thinking blocks"
    )
    usage: Optional[LLMUsage] = Field(default=None, description="Token usage and cost info")

    def has_reasoning(self) -> bool:
        """Check if the response includes reasoning content."""
        return bool(self.reasoning) or bool(self.thinking_blocks)

    def format_reasoning_summary(self) -> str:
        """Format reasoning for display in comments/PRs."""
        if not self.has_reasoning():
            return ""

        # Prefer thinking_blocks if available (more structured)
        if self.thinking_blocks:
            reasoning_text = "\n\n".join([block.thinking for block in self.thinking_blocks])
        else:
            reasoning_text = self.reasoning or ""

        return reasoning_text

    def format_editorial_explanation(self) -> str:
        """
        Format the reasoning as an editorial explanation.
        This is shown to users so they understand WHY the AI made decisions.
        """
        reasoning = self.format_reasoning_summary()
        if not reasoning:
            return ""

        # Truncate very long reasoning for readability
        max_length = 2000
        if len(reasoning) > max_length:
            reasoning = reasoning[:max_length] + "...\n\n*(reasoning truncated for brevity)*"

        return f"""<details>
<summary>🧠 <strong>Editorial Reasoning</strong> (click to expand)</summary>

{reasoning}

</details>"""


# =============================================================================
# EDITORIAL RESPONSE SCHEMAS - Pydantic models for structured LLM output
# =============================================================================


class EditorialIssue(BaseModel):
    """A single editorial issue found during review."""

    model_config = ConfigDict(strict=True)

    type: Literal["structural", "redundancy", "gap", "consistency", "pacing", "question"] = Field(
        description="Type of editorial issue"
    )
    location: Optional[str] = Field(default=None, description="Chapter or file location")
    title: Optional[str] = Field(default=None, description="Brief title of the issue")
    description: str = Field(description="Description of the problem")
    suggestion: Optional[str] = Field(default=None, description="Suggested resolution")
    question: Optional[str] = Field(
        default=None, description="Question for author (if type=question)"
    )
    why: Optional[str] = Field(default=None, description="Why the question is being asked")


class EditorialReviewResponse(BaseModel):
    """Structured response from a full editorial review."""

    model_config = ConfigDict(strict=True)

    issues: List[EditorialIssue] = Field(description="List of editorial issues found")
    summary: str = Field(description="Brief summary of the review")
    overall_assessment: Optional[str] = Field(
        default=None, description="Overall manuscript assessment"
    )


class TranscriptAnalysis(BaseModel):
    """Structured response from voice memo transcript analysis."""

    model_config = ConfigDict(strict=True)

    cleaned_transcript: str = Field(description="Cleaned version of the transcript")
    key_themes: List[str] = Field(description="Key themes identified")
    suggested_placement: Optional[str] = Field(
        default=None, description="Suggested chapter placement"
    )
    editorial_notes: str = Field(description="Editorial notes and observations")
    questions_for_author: List[str] = Field(
        default_factory=list, description="Clarifying questions"
    )
    ready_for_pr: bool = Field(description="Whether content is ready for PR")


class PRReviewResponse(BaseModel):
    """Structured response from PR editorial review."""

    model_config = ConfigDict(strict=True)

    verdict: Literal["approve", "request_changes", "comment"] = Field(description="Review verdict")
    summary: str = Field(description="Brief summary of the review")
    whats_working: List[str] = Field(
        default_factory=list, description="Things that are working well"
    )
    structural_feedback: List[str] = Field(
        default_factory=list, description="Structural suggestions"
    )
    line_suggestions: List[Dict[str, str]] = Field(
        default_factory=list, description="Line-level suggestions"
    )
    style_issues: List[str] = Field(
        default_factory=list, description="Style guide compliance issues"
    )
    questions: List[str] = Field(default_factory=list, description="Questions for the author")


# =============================================================================
# CONVERSATIONAL ACTION SCHEMAS - Inferred actions from natural language
# =============================================================================


class IssueAction(BaseModel):
    """An action to perform on an issue, inferred from conversation."""

    model_config = ConfigDict(strict=True)

    action: Literal[
        "close",
        "reopen",
        "add_labels",
        "remove_labels",
        "edit_title",
        "edit_body",
        "create_issue",
        "set_placement",
        "create_pr",
        "respond",
        "none",
    ] = Field(description="The action to take")

    # Parameters for specific actions
    labels: List[str] = Field(default_factory=list, description="Labels to add/remove")
    title: Optional[str] = Field(
        default=None, description="New title (for edit_title/create_issue)"
    )
    body: Optional[str] = Field(default=None, description="New body content")
    target_file: Optional[str] = Field(default=None, description="Target file for placement")
    close_reason: Optional[str] = Field(
        default=None, description="Reason for closing (completed, not_planned, duplicate)"
    )


class PRAction(BaseModel):
    """An action to perform on a PR, inferred from conversation."""

    model_config = ConfigDict(strict=True)

    action: Literal[
        "approve",
        "request_changes",
        "comment",
        "close",
        "merge",
        "add_labels",
        "remove_labels",
        "respond",
        "none",
    ] = Field(description="The action to take")

    # Parameters
    review_body: Optional[str] = Field(default=None, description="Review comment body")
    labels: List[str] = Field(default_factory=list, description="Labels to add/remove")
    merge_method: Optional[Literal["merge", "squash", "rebase"]] = Field(
        default=None, description="Merge method if merging"
    )


class ConversationalIntent(BaseModel):
    """Parsed intent from a natural language comment."""

    model_config = ConfigDict(strict=True)

    understood: bool = Field(description="Whether the intent was understood clearly")
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence in understanding")

    # What actions to take
    issue_actions: List[IssueAction] = Field(
        default_factory=list, description="Actions to perform on issues"
    )
    pr_actions: List[PRAction] = Field(
        default_factory=list, description="Actions to perform on PRs"
    )

    # Response to send
    response_text: str = Field(description="Natural language response to send to the user")
    needs_confirmation: bool = Field(
        default=False, description="Whether to ask for confirmation before acting"
    )
    clarifying_question: Optional[str] = Field(
        default=None, description="Question to ask if intent is unclear"
    )


# =============================================================================
# MODEL CAPABILITY REGISTRY
# =============================================================================
#
# This registry must be MANUALLY UPDATED when new models are released.
# There is no reliable auto-discovery for reasoning-capable models.
#
# Last updated: December 2025
#
# Provider docs for updates:
# - Anthropic: https://docs.anthropic.com/en/docs/about-claude/models
# - OpenAI: https://platform.openai.com/docs/models
# - DeepSeek: https://api-docs.deepseek.com/
# - Google: https://ai.google.dev/gemini-api/docs/models
# =============================================================================


class ModelCapabilities(BaseModel):
    """Capability metadata for a reasoning-capable model."""

    model_config = ConfigDict(strict=True, frozen=True)

    reasoning: bool = Field(description="Supports chain-of-thought / extended thinking")
    tools: bool = Field(description="Supports tool/function calling")
    vision: bool = Field(description="Supports image input")
    context: int = Field(ge=0, description="Context window size")
    provider: str = Field(description="Provider name for config lookup")
    reasoning_param: Optional[str] = Field(
        default=None, description="Parameter name to enable reasoning"
    )
    reasoning_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Config value for reasoning parameter"
    )


# Explicit capability registry - THE source of truth for supported models
REASONING_MODEL_REGISTRY: Dict[str, ModelCapabilities] = {
    # =========================================================================
    # ANTHROPIC - https://docs.anthropic.com/en/docs/about-claude/models
    # Extended thinking via: thinking={"type": "enabled", "budget_tokens": N}
    # =========================================================================
    "claude-sonnet-4-5-20250929": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=200_000,
        provider="anthropic",
        reasoning_param="thinking",
        reasoning_config={"type": "enabled", "budget_tokens": 10000},
    ),
    "claude-opus-4-5-20251101": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=200_000,
        provider="anthropic",
        reasoning_param="thinking",
        reasoning_config={"type": "enabled", "budget_tokens": 16000},
    ),
    "claude-haiku-4-5-20251201": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=200_000,
        provider="anthropic",
        reasoning_param="thinking",
        reasoning_config={"type": "enabled", "budget_tokens": 8000},
    ),
    "claude-sonnet-4-20250514": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=200_000,
        provider="anthropic",
        reasoning_param="thinking",
        reasoning_config={"type": "enabled", "budget_tokens": 10000},
    ),
    "claude-opus-4-20250514": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=200_000,
        provider="anthropic",
        reasoning_param="thinking",
        reasoning_config={"type": "enabled", "budget_tokens": 16000},
    ),
    # =========================================================================
    # DEEPSEEK - https://api-docs.deepseek.com/
    # Reasoning enabled by default with deepseek-reasoner model
    # =========================================================================
    "deepseek-reasoner": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=False,
        context=64_000,
        provider="deepseek",
        reasoning_param=None,
        reasoning_config=None,
    ),
    # =========================================================================
    # OPENAI - https://platform.openai.com/docs/models
    # Reasoning via: reasoning_effort="low|medium|high"
    # =========================================================================
    "o3": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=200_000,
        provider="openai",
        reasoning_param="reasoning_effort",
        reasoning_config={"effort": "medium"},
    ),
    "o4-mini": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=200_000,
        provider="openai",
        reasoning_param="reasoning_effort",
        reasoning_config={"effort": "medium"},
    ),
    "o3-mini": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=False,
        context=200_000,
        provider="openai",
        reasoning_param="reasoning_effort",
        reasoning_config={"effort": "medium"},
    ),
    "o1": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=200_000,
        provider="openai",
        reasoning_param="reasoning_effort",
        reasoning_config={"effort": "medium"},
    ),
    # =========================================================================
    # GOOGLE GEMINI - https://ai.google.dev/gemini-api/docs/models
    # Thinking via: thinking={"type": "enabled", "budget_tokens": N}
    # =========================================================================
    "gemini-2.5-flash": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=1_000_000,
        provider="gemini",
        reasoning_param="thinking",
        reasoning_config={"type": "enabled", "budget_tokens": 8000},
    ),
    "gemini-2.5-pro": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=1_000_000,
        provider="gemini",
        reasoning_param="thinking",
        reasoning_config={"type": "enabled", "budget_tokens": 10000},
    ),
    "gemini-2.5-flash-lite": ModelCapabilities(
        reasoning=True,
        tools=True,
        vision=True,
        context=1_000_000,
        provider="gemini",
        reasoning_param="thinking",
        reasoning_config={"type": "enabled", "budget_tokens": 6000},
    ),
}

# Build REASONING_MODELS set from registry for quick lookup
REASONING_MODELS = set(REASONING_MODEL_REGISTRY.keys())

# Add prefixed versions for LiteLLM compatibility
for model_id, caps in list(REASONING_MODEL_REGISTRY.items()):
    prefixed = f"{caps.provider}/{model_id}"
    if prefixed not in REASONING_MODEL_REGISTRY:
        REASONING_MODEL_REGISTRY[prefixed] = caps
        REASONING_MODELS.add(prefixed)


# Default model - MUST be in REASONING_MODEL_REGISTRY
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


# Model aliases for convenience - ALL must resolve to registry entries
MODEL_ALIASES = {
    # Anthropic
    "claude": "claude-sonnet-4-5-20250929",
    "claude-sonnet": "claude-sonnet-4-5-20250929",
    "claude-sonnet-4": "claude-sonnet-4-20250514",
    "claude-sonnet-4.5": "claude-sonnet-4-5-20250929",
    "claude-opus": "claude-opus-4-5-20251101",
    "claude-opus-4": "claude-opus-4-20250514",
    "claude-opus-4.5": "claude-opus-4-5-20251101",
    "claude-haiku": "claude-haiku-4-5-20251201",
    "claude-haiku-4.5": "claude-haiku-4-5-20251201",
    # DeepSeek
    "deepseek": "deepseek-reasoner",
    "deepseek-r1": "deepseek-reasoner",
    # OpenAI
    "o3": "o3",
    "o4-mini": "o4-mini",
    "o3-mini": "o3-mini",
    "o1": "o1",
    # Google Gemini
    "gemini": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.5-pro",
    "gemini-flash": "gemini-2.5-flash",
    # Cost/speed tiers
    "cheap": "claude-haiku-4-5-20251201",
    "fast": "o4-mini",
    "default": "claude-sonnet-4-5-20250929",
    "powerful": "claude-opus-4-5-20251101",
}


def get_model_capabilities(model: str) -> Optional[ModelCapabilities]:
    """Get capabilities for a model from the registry."""
    # Direct lookup
    if model in REASONING_MODEL_REGISTRY:
        return REASONING_MODEL_REGISTRY[model]

    # Check if it's an alias
    resolved = MODEL_ALIASES.get(model)
    if resolved and resolved in REASONING_MODEL_REGISTRY:
        return REASONING_MODEL_REGISTRY[resolved]

    return None


def supports_reasoning(model: str) -> bool:
    """Check if a model supports reasoning/thinking content."""
    caps = get_model_capabilities(model)
    if caps is not None and caps.reasoning:
        return True

    # Check LiteLLM registry (may know about newer models not in our registry)
    return bool(litellm.supports_reasoning(model=model))


def get_model() -> str:
    """
    Get the configured model from environment.

    Raises:
        ValueError: If the model doesn't support reasoning
    """
    model = os.environ.get("MODEL", DEFAULT_MODEL)
    # Resolve aliases
    resolved = MODEL_ALIASES.get(model, model)

    # Validate reasoning support
    if not supports_reasoning(resolved):
        supported = sorted([m for m in REASONING_MODEL_REGISTRY.keys() if "/" not in m])
        raise ValueError(
            f"Model '{resolved}' does not support reasoning/thinking content. "
            f"AI Book Editor requires reasoning-capable models for transparent editorial decisions. "
            f"Supported models: {', '.join(supported)}"
        )

    return resolved


def _build_reasoning_kwargs(model: str) -> Dict[str, Any]:
    """Build the kwargs needed to enable reasoning for a model."""
    caps = get_model_capabilities(model)
    if caps is None:
        return {}

    if caps.reasoning_param and caps.reasoning_config:
        return {caps.reasoning_param: caps.reasoning_config}
    return {}


def _extract_reasoning(message) -> Tuple[Optional[str], List[ThinkingBlock]]:
    """Extract reasoning content from LLM response message."""
    reasoning_content = None
    thinking_blocks = []

    # Get reasoning_content (standardized by LiteLLM)
    if hasattr(message, "reasoning_content") and message.reasoning_content:
        reasoning_content = message.reasoning_content

    # Get thinking_blocks (Anthropic-specific, more structured)
    if hasattr(message, "thinking_blocks") and message.thinking_blocks:
        for block in message.thinking_blocks:
            thinking_blocks.append(
                ThinkingBlock(
                    type=getattr(block, "type", "thinking"),
                    thinking=getattr(block, "thinking", ""),
                    signature=getattr(block, "signature", None),
                )
            )

    return reasoning_content, thinking_blocks


def call_editorial(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 16000,
) -> LLMResponse:
    """
    Call LLM with reasoning enabled for editorial tasks.

    This is the PRIMARY function for editorial work. It:
    - Enables extended thinking/reasoning
    - Returns both content AND reasoning
    - Tracks token usage and cost

    Returns:
        LLMResponse with content, reasoning, and usage

    Examples:
        response = call_editorial("Analyze this transcript...")
        print(response.content)  # The editorial analysis
        print(response.format_editorial_explanation())  # Collapsible reasoning
        print(response.usage.format_summary())  # Token/cost info
    """
    model = model or get_model()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Build reasoning-specific kwargs
    reasoning_kwargs = _build_reasoning_kwargs(model)

    response = litellm.completion(
        model=model, messages=messages, max_tokens=max_tokens, **reasoning_kwargs
    )

    message = response.choices[0].message

    # Extract reasoning
    reasoning_content, thinking_blocks = _extract_reasoning(message)

    # Extract usage
    usage_data = response.usage
    prompt_tokens = getattr(usage_data, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage_data, "completion_tokens", 0) or 0
    total_tokens = getattr(usage_data, "total_tokens", 0) or (prompt_tokens + completion_tokens)

    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:
        cost = 0.0

    usage = LLMUsage(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
    )

    return LLMResponse(
        content=message.content or "",
        reasoning=reasoning_content,
        thinking_blocks=thinking_blocks,
        usage=usage,
    )


def call_llm(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """
    Simple LLM call returning just text. Use call_editorial() for editorial tasks.

    This is a convenience wrapper for simple tasks that don't need reasoning.
    """
    response = call_editorial(prompt, system, model, max_tokens)
    return response.content


def call_llm_with_usage(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> Tuple[str, LLMUsage]:
    """
    Call LLM and return both response text and usage information.

    DEPRECATED: Use call_editorial() instead for full reasoning support.

    Returns:
        Tuple of (response_text, LLMUsage)
    """
    response = call_editorial(prompt, system, model, max_tokens)
    return response.content, response.usage


# Backwards compatibility alias
def call_claude(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Backwards-compatible alias for call_llm."""
    return call_llm(prompt, system, model, max_tokens, temperature)


T = TypeVar("T", bound=BaseModel)


def call_editorial_structured(
    prompt: str,
    response_model: TypingType[T],
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 16000,
) -> Tuple[T, LLMResponse]:
    """
    Call LLM with structured Pydantic output. FAILS HARD if response doesn't conform.

    This enforces a typed response matching the Pydantic model schema.
    NO FALLBACKS - if the response doesn't validate, we raise an exception.

    Args:
        prompt: The user prompt
        response_model: Pydantic model class to parse response into
        system: Optional system message
        model: Model to use (defaults to configured model)
        max_tokens: Maximum tokens in response

    Returns:
        Tuple of (validated_model_instance, LLMResponse)

    Raises:
        pydantic.ValidationError: If response doesn't match schema
        json.JSONDecodeError: If response isn't valid JSON

    Example:
        result, response = call_editorial_structured(prompt, EditorialReviewResponse)
        for issue in result.issues:  # Typed! IDE knows issue is EditorialIssue
            print(issue.description)
    """
    model = model or get_model()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Build reasoning-specific kwargs
    reasoning_kwargs = _build_reasoning_kwargs(model)

    # Generate JSON schema from Pydantic model
    json_schema = response_model.model_json_schema()

    # Anthropic requires additionalProperties: false for all object types
    def fix_schema_for_anthropic(schema: dict) -> dict:
        """Recursively add additionalProperties: false to all objects."""
        if isinstance(schema, dict):
            if schema.get("type") == "object":
                schema["additionalProperties"] = False
            for key, value in schema.items():
                if isinstance(value, dict):
                    fix_schema_for_anthropic(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            fix_schema_for_anthropic(item)
            # Handle $defs (Pydantic's referenced definitions)
            if "$defs" in schema:
                for def_name, def_schema in schema["$defs"].items():
                    fix_schema_for_anthropic(def_schema)
        return schema

    json_schema = fix_schema_for_anthropic(json_schema)

    # Add structured output format
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": response_model.__name__, "strict": True, "schema": json_schema},
    }

    response = litellm.completion(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        response_format=response_format,
        **reasoning_kwargs,
    )

    message = response.choices[0].message

    # Extract reasoning
    reasoning_content, thinking_blocks = _extract_reasoning(message)

    # Extract usage
    usage_data = response.usage
    prompt_tokens = getattr(usage_data, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage_data, "completion_tokens", 0) or 0
    total_tokens = getattr(usage_data, "total_tokens", 0) or (prompt_tokens + completion_tokens)

    # Cache tokens
    cache_read = getattr(usage_data, "cache_read_input_tokens", 0) or 0
    cache_creation = getattr(usage_data, "cache_creation_input_tokens", 0) or 0

    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:
        cost = 0.0

    usage = LLMUsage(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_creation,
    )

    llm_response = LLMResponse(
        content=message.content or "",
        reasoning=reasoning_content,
        thinking_blocks=thinking_blocks,
        usage=usage,
    )

    # Parse and validate with Pydantic - NO FALLBACK, FAIL HARD
    raw_json = json.loads(message.content)  # Raises JSONDecodeError if invalid
    validated = response_model.model_validate(raw_json)  # Raises ValidationError if invalid

    return validated, llm_response


def build_cached_messages(
    system_prompt: str, user_prompt: str, cache_system: bool = True
) -> List[Dict[str, Any]]:
    """
    Build messages with prompt caching enabled.

    Prompt caching can reduce costs by 90% when repeatedly using the same
    system context (persona, guidelines, knowledge base).

    Works with:
    - Anthropic: cache_control with ephemeral breakpoints
    - OpenAI: Automatic caching for prompts > 1024 tokens

    Args:
        system_prompt: The system message (editorial context)
        user_prompt: The user message (specific task)
        cache_system: Whether to enable caching on system message

    Returns:
        List of messages with appropriate cache control
    """
    messages = []

    if cache_system:
        # Anthropic-style cache control
        # Cache the expensive editorial context (persona, guidelines, knowledge base)
        messages.append(
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
                ],
            }
        )
    else:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": user_prompt})
    return messages


def call_editorial_cached(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    max_tokens: int = 16000,
) -> LLMResponse:
    """
    Call LLM with prompt caching enabled for the system context.

    Use this for repeated editorial tasks where the persona, guidelines,
    and knowledge base remain constant across many calls.

    Cost savings:
    - Cache hits reduce input token cost by 90%
    - First call creates the cache (slightly higher cost)
    - Subsequent calls with same system context hit cache

    Args:
        system_prompt: Editorial context (will be cached)
        user_prompt: Specific task (not cached)
        model: Model to use
        max_tokens: Maximum response tokens

    Returns:
        LLMResponse with content, reasoning, and usage
    """
    model = model or get_model()

    messages = build_cached_messages(system_prompt, user_prompt, cache_system=True)

    # Build reasoning-specific kwargs
    reasoning_kwargs = _build_reasoning_kwargs(model)

    response = litellm.completion(
        model=model, messages=messages, max_tokens=max_tokens, **reasoning_kwargs
    )

    message = response.choices[0].message

    # Extract reasoning
    reasoning_content, thinking_blocks = _extract_reasoning(message)

    # Extract usage - check for cache-specific tokens
    usage_data = response.usage
    prompt_tokens = getattr(usage_data, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage_data, "completion_tokens", 0) or 0
    total_tokens = getattr(usage_data, "total_tokens", 0) or (prompt_tokens + completion_tokens)

    # Cache-specific usage (Anthropic)
    cache_read = getattr(usage_data, "cache_read_input_tokens", 0) or 0
    cache_creation = getattr(usage_data, "cache_creation_input_tokens", 0) or 0

    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:
        cost = 0.0

    usage = LLMUsage(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_creation,
    )

    return LLMResponse(
        content=message.content or "",
        reasoning=reasoning_content,
        thinking_blocks=thinking_blocks,
        usage=usage,
    )


def build_editorial_prompt(
    persona: str,
    guidelines: str,
    glossary: Optional[str],
    knowledge_base: Optional[str],
    chapter_list: list,
    task: str,
    content: str,
) -> str:
    """Build a complete editorial prompt with all context."""

    sections = []

    sections.append(
        f"""# Your Persona
{persona}"""
    )

    sections.append(
        f"""# Editorial Guidelines (MUST FOLLOW)
{guidelines}"""
    )

    if glossary:
        sections.append(
            f"""# Glossary
{glossary}"""
        )

    if knowledge_base:
        sections.append(
            f"""# Knowledge Base (What You Know About This Book)
{knowledge_base}"""
        )

    if chapter_list:
        sections.append(
            f"""# Existing Chapters
{', '.join(chapter_list)}"""
        )

    sections.append(
        f"""# Current Task
{task}"""
    )

    sections.append(
        f"""# Content to Process
{content}"""
    )

    sections.append(
        """# Important Reminders
- Follow EDITORIAL_GUIDELINES.md exactly
- Embody EDITOR_PERSONA.md in your responses
- Preserve the author's voice — enhance, don't replace
- Be specific: reference exact phrases, not vague generalities
- Explain WHY when you suggest changes
- If unsure about author intent, ASK rather than assume"""
    )

    return "\n\n".join(sections)


def build_editorial_system_prompt(
    persona: str,
    guidelines: str,
    glossary: Optional[str] = None,
    knowledge_base: Optional[str] = None,
    chapter_list: Optional[list] = None,
) -> str:
    """
    Build the CACHEABLE system prompt containing editorial context.

    This separates the static context (persona, guidelines, knowledge) from
    the dynamic task. The system prompt can then be cached for cost savings.

    Usage with caching:
        system = build_editorial_system_prompt(persona, guidelines, ...)
        response = call_editorial_cached(system, task_prompt)

    Returns:
        System prompt suitable for caching
    """
    sections = []

    sections.append(
        f"""# Your Persona
{persona}"""
    )

    sections.append(
        f"""# Editorial Guidelines (MUST FOLLOW)
{guidelines}"""
    )

    if glossary:
        sections.append(
            f"""# Glossary
{glossary}"""
        )

    if knowledge_base:
        sections.append(
            f"""# Knowledge Base (What You Know About This Book)
{knowledge_base}"""
        )

    if chapter_list:
        sections.append(
            f"""# Existing Chapters
{', '.join(chapter_list)}"""
        )

    sections.append(
        """# Important Reminders
- Follow EDITORIAL_GUIDELINES.md exactly
- Embody EDITOR_PERSONA.md in your responses
- Preserve the author's voice — enhance, don't replace
- Be specific: reference exact phrases, not vague generalities
- Explain WHY when you suggest changes
- If unsure about author intent, ASK rather than assume"""
    )

    return "\n\n".join(sections)
