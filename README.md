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
- `.github/workflows/` - Example workflow files (see below)
- `.ai-context/` - Knowledge base (customize for your book)
- `EDITOR_PERSONA.md` - AI personality
- `EDITORIAL_GUIDELINES.md` - Editorial rules
- `GLOSSARY.md` - Terminology

**Or use the action directly:**

```yaml
- uses: VoiceWriter/ai-book-editor@main
  with:
    anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
    mode: process-transcription
    issue-number: ${{ github.event.issue.number }}
```

### 2. Create a GitHub App (for bot identity)

All AI actions will appear as `margot-ai-editor[bot]` instead of your personal account.

1. Go to **Settings → Developer settings → GitHub Apps → New GitHub App**
2. Fill in:
   - **Name:** `margot-ai-editor` (or your preferred name)
   - **Homepage URL:** Your repository URL
   - **Callback URL:** `https://example.com` (not used)
   - **Webhook:** Uncheck "Active" (not used)
3. **Permissions:**
   - **Repository permissions:**
     - Contents: Read & write
     - Issues: Read & write
     - Pull requests: Read & write
     - Metadata: Read-only
4. **Subscribe to events:** Leave all unchecked (GitHub Actions handles events)
5. Click **Create GitHub App**
6. Note the **App ID** from the app settings page
7. Scroll down and click **Generate a private key** - save the `.pem` file
8. Go to **Install App** (left sidebar) and install it on your book repository

### 3. Add secrets

In your repository settings (Settings → Secrets and variables → Actions), add:
- `AI_EDITOR_APP_ID` - The App ID from step 6 above
- `AI_EDITOR_PRIVATE_KEY` - Contents of the `.pem` file from step 7
- `ANTHROPIC_API_KEY` - Your Claude API key (or appropriate key for your model)

### 4. Create issue labels

Create these labels in your repository:

**Core labels:**
- `voice_transcription` (blue) - Voice memo to process
- `ai-reviewed` (green) - AI has analyzed
- `pr-created` (purple) - PR exists for this issue
- `awaiting-author` (yellow) - Blocked on author input
- `ai-question` (blue) - Question for the editor
- `whole-book` (purple) - Full manuscript analysis
- `quick-review` (orange) - Skip discovery, fast feedback

**Phase labels:**
- `phase:discovery` (purple) - Editor asking questions first
- `phase:feedback` (blue) - Feedback being provided
- `phase:revision` (yellow) - Author revising
- `phase:hold` (light purple) - On hold for reflection
- `phase:complete` (green) - Editorial work complete

**Persona labels (optional):**
- `persona:margot` - Sharp, market-aware
- `persona:sage` - Nurturing, encouraging
- `persona:blueprint` - Structure-focused
- `persona:the-axe` - Brutal cutting

### 5. Submit a voice memo

1. Create a new issue using the "Voice Transcription" template
2. Paste your transcript in the issue body
3. Add the `voice_transcription` label
4. The AI will analyze and comment within minutes

### 6. Interact with the AI

Use these commands in issue comments:
- `@margot-ai-editor create PR` - Create a PR with the cleaned content
- `@margot-ai-editor place in chapter-name.md` - Specify target file
- `@margot-ai-editor [any question]` - Have a conversation

## Workflows

### Voice-to-PR Pipeline (with Discovery)
```
Voice memo → Issue → Discovery Questions → Author Responds → Tailored Feedback → Discussion → PR → Review → Merge
```

**The Discovery Phase:**
1. Author submits voice transcript
2. Editor asks 2-4 personalized questions (based on persona)
3. Author responds with context, goals, emotional state
4. Editor provides feedback tailored to what they learned
5. Responses feed into knowledge base for future context

**Skip Discovery:** Check "Skip discovery" in the issue template or add `quick-review` label.

### Human Writing Pipeline
```
Write in VS Code -> Push branch -> AI reviews PR -> Iterate -> Merge
```

### Whole Book Analysis
```
Add `whole-book` label → AI reads all chapters → Cross-chapter analysis
```

Detects:
- Thematic threads across chapters
- Consistency issues (character, timeline, terminology)
- Repetition and redundancy
- Promise/payoff tracking
- Structural recommendations

## Editorial Phases

Issues progress through phases tracked by labels:

| Phase | Label | Description |
|-------|-------|-------------|
| Discovery | `phase:discovery` | Editor asking questions |
| Feedback | `phase:feedback` | Editorial analysis provided |
| Revision | `phase:revision` | Author revising based on feedback |
| Hold | `phase:hold` | On hold for author reflection |
| Complete | `phase:complete` | Ready for publication |

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

### Editor Personas

Choose from preset editor personalities, each with different approaches to feedback:

| Persona | Style | Best For |
|---------|-------|----------|
| **Margot Fielding** | Sharp, ruthless, market-aware | Later drafts, tough love |
| **Sage Holloway** | Nurturing mentor | Early drafts, building confidence |
| **Maxwell Blueprint** | Structure-obsessed | Pacing, chapter order |
| **Sterling Chase** | Commercially strategic | Positioning, hooks, audience |
| **The Axe** | Brutal, no mercy | Cutting 30%, bloated drafts |
| **Sunny Brightwell** | Pure encouragement | Writer's block, recovery |
| **Professor Ashworth** | Academic, literary | Elevating craft |
| **Chip Madison** | Commercial maximalist | Maximum reach |

**[See all personas and create your own →](PERSONAS.md)**

Configure in `.ai-context/config.yaml`:
```yaml
persona: margot
```

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
make test-comment    # Simulate @margot-ai-editor comment
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
