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

## File Structure

```
.github/
  scripts/
    utils/
      llm_client.py      # LLM utilities with Pydantic DTOs
      github_client.py   # GitHub API helpers
      knowledge_base.py  # Knowledge base loader
    process_transcription.py
    review_pr.py
    respond_to_comment.py
    ...

tests/
  test_llm_client.py
  test_github_client.py
  conftest.py           # Shared fixtures
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
