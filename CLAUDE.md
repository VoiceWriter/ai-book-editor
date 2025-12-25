# AI Book Editor - Project Guidelines

## Core Principles

### 1. Strict Typing - Pydantic DTOs Only

All data structures MUST use Pydantic models with strict validation:

```python
from pydantic import BaseModel, Field, ConfigDict

class MyModel(BaseModel):
    model_config = ConfigDict(strict=True)  # ALWAYS strict

    field: str = Field(description="Required description")
```

**ABSOLUTE RULES:**
- NO loose dictionaries for structured data
- NO TypedDicts - use Pydantic models
- NO dataclasses - use Pydantic models
- ALL fields must have `Field()` with descriptions
- ALL models must have `ConfigDict(strict=True)`
- Frozen models for immutable data: `ConfigDict(strict=True, frozen=True)`

### 2. Fail Hard, Fail Fast

NO FALLBACKS. If something is wrong, raise an exception immediately.

```python
# WRONG - silent fallback
try:
    result = parse_json(data)
except:
    result = {}  # NO! Don't hide errors

# RIGHT - fail hard
result = MyModel.model_validate(json.loads(data))  # Raises on invalid
```

**When try/except IS allowed:**
- Logging and observability (log error, then re-raise)
- Converting exceptions to domain-specific errors (catch, wrap, re-raise)
- NEVER for silent fallbacks or default values

**When if/else IS a smell:**
- Multiple branches checking for None/empty with fallbacks
- Defensive coding against invalid states
- If you need many if/else, the data model is wrong

### 3. Structured LLM Responses

Always use `call_editorial_structured()` with a Pydantic response model:

```python
from scripts.utils.llm_client import call_editorial_structured, EditorialReviewResponse

result, response = call_editorial_structured(prompt, EditorialReviewResponse)
# result is TYPED - IDE knows all fields
for issue in result.issues:
    print(issue.description)  # IDE autocomplete works
```

Never parse free-form text from LLMs. Always enforce a schema.

### 4. Reasoning-Capable Models Only

This project ONLY supports models with chain-of-thought reasoning:
- Claude Sonnet 4.5, Opus 4.5, Haiku 4.5
- OpenAI o3, o4-mini, o3-mini, o1
- DeepSeek Reasoner
- Gemini 2.5 Pro/Flash

Non-reasoning models (GPT-4o, GPT-4, Claude 3.x) will raise `ValueError`.

### 5. Prompt Caching for Cost Efficiency

Use cached calls for repeated editorial context:

```python
from scripts.utils.llm_client import (
    call_editorial_cached,
    build_editorial_system_prompt
)

# Build cacheable system context
system = build_editorial_system_prompt(persona, guidelines, ...)

# Call with caching - 90% cost reduction on cache hits
response = call_editorial_cached(system, task_prompt)
```

## Testing Guidelines

### Write Tests First

For every new Pydantic model:

```python
def test_my_model_validates_correct_data():
    data = {"field": "value"}
    result = MyModel.model_validate(data)
    assert result.field == "value"

def test_my_model_rejects_invalid_data():
    with pytest.raises(ValidationError):
        MyModel.model_validate({"wrong": "data"})
```

### Test Edge Cases

```python
def test_my_model_rejects_wrong_types():
    with pytest.raises(ValidationError):
        MyModel.model_validate({"field": 123})  # Should be str
```

## Book Project Lifecycle

### Philosophy: Invisible Infrastructure

The AI editor adapts automatically. Authors don't manage phases or config files.

**Key principles:**
1. **Zero-config start** - First voice memo triggers welcome + questions
2. **Auto-detect phases** - Based on chapter count, content maturity, author signals
3. **PR-based config** - AI proposes changes, author approves via merge
4. **Natural language overrides** - "be harsher" works, no forms needed

### BookPhase vs EditorialPhase

Two orthogonal concepts:

| Concept | Scope | Tracked By |
|---------|-------|------------|
| `BookPhase` | Whole project lifecycle | `.ai-context/book.yaml` |
| `EditorialPhase` | Single issue workflow | GitHub labels |

A book in `polishing` phase might still have new voice memos going through `discovery → feedback → revision`.

### Book Phase Affects Feedback Style

```python
from scripts.utils.phases import BookPhase, get_book_phase_guidance

# Get phase-specific editorial guidance
guidance = get_book_phase_guidance(BookPhase.REVISING)
# Returns: "More rigorous structural critique..."
```

### Configuration via PRs

Never mutate book.yaml directly. Always via PR:

```python
from scripts.setup_book import create_config_pr, BookConfigUpdate

update = BookConfigUpdate(
    phase="revising",
    core_themes=["AI accessibility", "human-machine collaboration"],
)

pr_url = create_config_pr(
    repo=repo,
    config=merge_config_update(existing, update),
    title="Update book configuration",
    body="Transitioning to revision phase based on conversation",
    branch_name="ai-editor/config-update-20251225",
    source_issue=42,
)
```

### New Project Detection

```python
# In process_transcription.py
context = load_editorial_context(repo)
is_new_project = context.get("book_config") is None

if is_new_project:
    # Include welcome message + questions
    # Treat as BookPhase.NEW for feedback style
```

## File Structure

```
.github/
  scripts/
    utils/
      llm_client.py      # LLM utilities with Pydantic DTOs
      github_client.py   # GitHub API helpers
      knowledge_base.py  # Knowledge base + book config loader
      phases.py          # BookPhase, EditorialPhase, phase detection
      persona.py         # Persona loading and formatting
    process_transcription.py
    setup_book.py        # PR-based book config updates
    review_pr.py
    respond_to_comment.py
    ...

.ai-context/
  book.yaml              # Book project config (auto-generated via PR)
  book.yaml.template     # Template for reference
  knowledge.jsonl        # Q&A pairs from conversations
  terminology.yaml       # Term preferences
  themes.yaml            # Book themes
  author-preferences.yaml

tests/
  test_llm_client.py
  test_github_client.py
  test_phases.py         # Phase detection tests
  conftest.py            # Shared fixtures
```

## Response Models

### LLM Response Models (`llm_client.py`)

- `EditorialIssue` - Single issue found in review
- `EditorialReviewResponse` - Full book review response
- `TranscriptAnalysis` - Voice memo analysis
- `PRReviewResponse` - PR editorial review
- `LLMResponse` - Complete response with content, reasoning, usage
- `LLMUsage` - Token counts and costs
- `ModelCapabilities` - Model feature flags

### GitHub Objects - Use PyGithub Directly

**DO NOT create custom DTOs for GitHub entities.** Use PyGithub's native objects:

```python
from github import Github

gh = Github(token)
repo = gh.get_repo("owner/repo")
issue = repo.get_issue(123)      # github.Issue.Issue
pr = repo.get_pull(456)          # github.PullRequest.PullRequest
issue.create_comment("text")     # Use native methods
```

PyGithub provides: `Issue`, `PullRequest`, `Repository`, `ContentFile`, `Label`, etc.

**Only create custom DTOs for:**
- LLM response schemas (our domain)
- Workflow-specific outputs
- Knowledge base entries (our format)

## Registry Updates

Model capability registry (`REASONING_MODEL_REGISTRY`) must be manually updated when providers release new models. Check provider docs monthly:

- Anthropic: https://docs.anthropic.com/en/docs/about-claude/models
- OpenAI: https://platform.openai.com/docs/models
- DeepSeek: https://api-docs.deepseek.com/
- Google: https://ai.google.dev/gemini-api/docs/models

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

All tests must pass before merging.
