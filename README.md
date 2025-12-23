# AI Book Editor

A GitHub-native AI editorial system for transforming voice memos and written fragments into polished books.

## Architecture

100% GitHub-native. No external servers, no databases. Just:
- **GitHub Issues** - Input, discussion, state management
- **GitHub Actions** - AI processing via LLM API
- **GitHub PRs** - Editorial output, traceability
- **GitHub repo** - Book content, knowledge base

## Quick Start

### 1. Set up your repository

Copy these files to your book repository:
- `.github/workflows/` - The workflow files
- `.ai-context/` - Knowledge base (customize for your book)
- `EDITOR_PERSONA.md` - AI personality
- `EDITORIAL_GUIDELINES.md` - Editorial rules
- `GLOSSARY.md` - Terminology

### 2. Add secrets

In your repository settings, add:
- `ANTHROPIC_API_KEY` - Your Claude API key (or appropriate key for your model)

### 3. Create issue labels

Create these labels in your repository:
- `voice_transcription` (blue) - Voice memo to process
- `ai-reviewed` (green) - AI has analyzed
- `pr-created` (purple) - PR exists for this issue
- `awaiting-author` (yellow) - Blocked on author input

### 4. Submit a voice memo

1. Create a new issue using the "Voice Transcription" template
2. Paste your transcript in the issue body
3. Add the `voice_transcription` label
4. The AI will analyze and comment within minutes

### 5. Interact with the AI

Use these commands in issue comments:
- `@ai-editor create PR` - Create a PR with the cleaned content
- `@ai-editor place in chapter-name.md` - Specify target file
- `@ai-editor [any question]` - Have a conversation

## Workflows

### Voice-to-PR Pipeline
```
Voice memo -> Issue -> AI Analysis -> Discussion -> PR -> Review -> Merge
```

### Human Writing Pipeline
```
Write in VS Code -> Push branch -> AI reviews PR -> Iterate -> Merge
```

## Configuration

### LLM Model Selection

> **IMPORTANT: Reasoning Models Required**
>
> AI Book Editor **only supports models with chain-of-thought reasoning** (extended thinking).
> This is required so the AI can explain its editorial decisions transparently.
> Using a non-reasoning model will cause errors.

**Supported Models (December 2025):**

| Model | Provider | Notes |
|-------|----------|-------|
| `claude-sonnet-4-5-20250929` | Anthropic | **Default, recommended** |
| `claude-opus-4-5-20251101` | Anthropic | Most capable |
| `claude-haiku-4-5-20251201` | Anthropic | Fast & cheap with thinking |
| `deepseek-reasoner` | DeepSeek | DeepSeek V3.2 thinking mode |
| `o3` / `o4-mini` | OpenAI | Latest OpenAI reasoning |
| `gemini-2.5-flash` | Google | Gemini with thinking |
| `gemini-2.5-pro` | Google | Gemini Pro with thinking |

**NOT Supported (will fail):**
- `gpt-4o`, `gpt-4o-mini` - No reasoning support
- `gemini-1.5-*`, `gemini-2.0-flash-lite` - No thinking support
- `claude-3-*` (older models) - No extended thinking
- Any model without chain-of-thought capability

Configure via environment:

```bash
# Default: Claude Sonnet 4.5 (recommended)
MODEL=claude-sonnet-4-5-20250929

# Anthropic alternatives
MODEL=claude-haiku-4-5-20251201    # Fast & cheap
MODEL=claude-opus-4-5-20251101     # Most capable

# Other providers
MODEL=deepseek-reasoner            # DeepSeek V3.2
MODEL=o4-mini                       # OpenAI (fast)
MODEL=gemini-2.5-flash             # Google Gemini

# Aliases
MODEL=claude         # claude-sonnet-4-5-20250929
MODEL=claude-haiku   # claude-haiku-4-5-20251201
MODEL=cheap          # claude-haiku-4-5-20251201
MODEL=fast           # o4-mini
MODEL=powerful       # claude-opus-4-5-20251101
```

> **Note:** Model IDs change over time. Check the source files or provider docs
> for the latest. Last verified: December 2025.

### Why Reasoning Models?

Every AI editorial decision includes a collapsible "Editorial Reasoning" section that explains WHY the AI made its suggestions. This transparency helps authors:
- Understand the AI's thought process
- Accept or reject suggestions with full context
- Learn from the editorial feedback
- Trust the AI as a collaborator, not a black box

### EDITOR_PERSONA.md
Customize the AI's personality and approach. This is tunable - experiment to find what works for you.

### EDITORIAL_GUIDELINES.md
Hard rules the AI must follow. These are non-negotiable.

### .ai-context/
Knowledge base files that help the AI understand your book:
- `knowledge.jsonl` - Q&A pairs from your conversations
- `terminology.yaml` - Term preferences
- `themes.yaml` - Book themes
- `author-preferences.yaml` - Style preferences

---

## Development & Testing

This section covers how to test and develop the AI Book Editor.

### Prerequisites

```bash
# Clone the repo
git clone https://github.com/VoiceWriter/ai-book-editor.git
cd ai-book-editor

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
make install
# or: pip install -r requirements.txt
```

### Environment Setup

Create a `.env` file with your credentials:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-api03-...
GITHUB_TOKEN=ghp_...
GITHUB_REPOSITORY=VoiceWriter/ai-book-editor-test

# Optional: Choose your LLM (default: claude-sonnet-4-20250514)
MODEL=claude-sonnet-4-20250514
```

---

## Testing Options

### A. Unit Tests (pytest) - No API calls

Fast, isolated tests that mock external dependencies.

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Stop on first failure
make test-fast

# Run specific test file
pytest tests/test_llm_client.py -v
```

**What's tested:**
- `test_llm_client.py` - LLM utilities, prompt building
- `test_github_client.py` - GitHub API utilities
- `test_knowledge_base.py` - Knowledge base loading/formatting
- `test_process_transcription.py` - Main processing script
- `test_seeds.py` - Seed data integrity

### B. Integration Tests - Real API calls

Test against real GitHub and LLM APIs (costs money, be mindful).

```bash
# Prerequisites: .env file with valid credentials
source .venv/bin/activate

# Run process_transcription against a real issue
make test-local

# Or manually:
set -a && source .env && set +a
ISSUE_NUMBER=1 python .github/scripts/process_transcription.py
```

### C. GitHub Actions Simulation (act) - Full workflow

Simulate the complete GitHub Actions workflow locally using [act](https://github.com/nektos/act).

```bash
# Install act (macOS)
brew install act

# Or (other platforms)
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run workflows (requires .env and Docker)
make test-issue      # Simulate voice_transcription issue
make test-comment    # Simulate @ai-editor comment
make test-pr         # Simulate PR opened
make test-scheduled  # Simulate scheduled review
```

**Note:** act runs workflows in Docker containers, which is slower but more accurate than direct script testing.

---

## Seed Data

Create test data in the test repository:

```bash
# Create all test issues and labels
make seed

# Create only labels
make seed-labels

# Clean up (close all test issues)
make seed-clean

# Use different repo
python seeds/seed.py --repo owner/other-repo
```

**Included seed data:**
- 4 voice memo issues with sample transcripts
- 1 AI question issue
- 12 labels with proper colors

---

## Project Structure

```
ai-book-editor/
├── .github/
│   ├── scripts/           # Python processing scripts
│   │   ├── process_transcription.py
│   │   ├── respond_to_comment.py
│   │   ├── review_pr.py
│   │   ├── extract_knowledge.py
│   │   ├── scheduled_review.py
│   │   ├── learn_from_feedback.py
│   │   └── utils/
│   │       ├── llm_client.py       # LLM utilities (LiteLLM)
│   │       ├── github_client.py    # GitHub API utilities
│   │       └── knowledge_base.py   # Knowledge base utilities
│   └── workflows/         # GitHub Actions workflows
├── seeds/                 # Test seed data
│   ├── issues.json
│   └── seed.py
├── tests/                 # pytest test suite
├── test-events/          # act event simulation files
├── Makefile              # Development commands
├── pytest.ini            # pytest configuration
├── requirements.txt      # Python dependencies
└── README.md
```

---

## Makefile Commands Reference

```bash
make help          # Show all commands

# Setup
make install       # Install dependencies
make setup-act     # Install act

# Unit tests
make test          # Run all tests
make test-fast     # Stop on first failure
make test-cov      # With coverage report

# Integration tests
make test-local    # Run against real APIs

# act simulation
make test-issue    # Simulate issue creation
make test-comment  # Simulate comment
make test-pr       # Simulate PR
make test-scheduled # Simulate scheduled run

# Seed data
make seed          # Create test data
make seed-labels   # Create only labels
make seed-clean    # Clean up test issues

# Quality
make lint          # Run linter
make clean         # Remove generated files
```

---

## Troubleshooting

### "GITHUB_TOKEN not set"
```bash
# Make sure to export env vars
set -a && source .env && set +a
```

### "externally-managed-environment" (pip error)
```bash
# Use a virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Tests fail with import errors
```bash
# Make sure you're in the project root
cd /path/to/ai-book-editor
# And have activated venv
source .venv/bin/activate
```

### act is slow
act runs in Docker, which adds overhead. For faster iteration, use:
```bash
make test-local  # Direct Python execution
```

---

## License

MIT
