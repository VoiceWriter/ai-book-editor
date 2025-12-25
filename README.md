# AI Book Editor

**Write your book. The AI handles the rest.**

Talk into your phone, create a GitHub issue, and get editorial feedback in minutes. No setup forms, no configuration wizards. Just write.

## How It Works

```
📱 Record voice memo → 📝 Paste in GitHub Issue → 🤖 AI gives feedback → 📖 Merge to book
```

**That's it.** The AI:
- Cleans up your transcript (removes ums, fixes punctuation)
- Analyzes what you're saying and suggests where it fits
- Adjusts feedback based on how far along your book is
- Learns your preferences over time

## 5-Minute Quickstart

### 1. Use this template (or fork this repo)

Click **"Use this template"** to create your book repository.

### 2. Add your API key

Go to **Settings → Secrets → Actions** and add:
- `ANTHROPIC_API_KEY` - Your Claude API key

That's it for secrets. The workflows use the built-in `GITHUB_TOKEN`.

### 3. Start writing

Create a new issue with the `voice_transcription` label:

```markdown
Title: Voice memo - morning thoughts on chapter 1

So I've been thinking about how to open this book, and I think we should
start with a story. Like, a real example of someone who struggled with
this before they found the solution. You know, hook the reader right away...
```

Within minutes, you'll get a comment with:
- ✨ Cleaned transcript
- 📍 Suggested placement
- 💡 Editorial feedback
- ❓ Questions to help clarify your intent

### 4. Interact naturally

Reply to the AI like you'd reply to a human editor:

```
@margot-ai-editor I want this in chapter 1, near the beginning

@margot-ai-editor actually, what if we made this the book's opening?

@margot-ai-editor create PR
```

The AI creates a PR. You review and merge. Your book grows.

---

## The AI Adapts to You

The more you write, the smarter your editor gets:

| Your Progress | AI Behavior | Why |
|---------------|-------------|-----|
| **Day 1** - First voice memo | Welcomes you, asks about your vision | You're just starting—celebrate momentum |
| **Week 4** - Several chapters in | Tracks consistency, notes themes | You have material to compare against |
| **Month 3** - First draft done | Rigorous structural critique | Time for real revision work |
| **Month 4** - Polishing | Line edits, grammar, style | Almost there—make it shine |

**Override anytime:** Say `@margot-ai-editor be harsher` or `I'm ready for tough love`.

### How the AI Learns

Every time you answer a question or give feedback, the AI remembers:

1. AI learns something → Creates a PR to update `.ai-context/book.yaml`
2. You review the PR → Merge if correct, close if wrong
3. Next time → AI uses what it learned

Your book's "memory" lives in git. Version-controlled. Reviewable. You have final say.

---

## Commands

Talk naturally, or use shortcuts:

| Say This | AI Does This |
|----------|--------------|
| `@margot-ai-editor create PR` | Creates a PR with cleaned content |
| `@margot-ai-editor place in chapter-3.md` | Sets target file |
| `@margot-ai-editor status` | Shows project progress |
| `@margot-ai-editor be harsher` | Turns up the criticism |
| `@margot-ai-editor use the-axe` | Switches to brutal editing persona |
| `@margot-ai-editor skip the questions` | Fast feedback, no discovery |
| Any question or comment | Just responds conversationally |

---

## Editor Personas

Different editors for different moods:

| Persona | Style | Use When |
|---------|-------|----------|
| **Margot** (default) | Sharp, market-aware | General feedback |
| **Sage** | Nurturing mentor | Early drafts, need encouragement |
| **The Axe** | Brutal, no mercy | Cutting bloat |
| **Blueprint** | Structure-obsessed | Pacing problems |
| **Sterling** | Commercial strategist | Positioning, hooks |

Switch anytime: `@margot-ai-editor use sage` or add label `persona:the-axe`

---

## Labels You'll Actually Use

**Start here:**
- `voice_transcription` - "This is a voice memo, process it"
- `quick-review` - "Skip questions, just give feedback"

**For bigger analysis:**
- `whole-book` - "Read everything, give cross-chapter feedback"

**The AI manages these automatically:**
- `phase:*` labels - Tracks where you are in the process
- `ai-reviewed` - AI has seen this

---

## Advanced: Custom Configuration

Most users don't need to touch this. The defaults work great.

### Files You Can Customize

| File | What It Does |
|------|--------------|
| `EDITORIAL_GUIDELINES.md` | Hard rules the AI must follow (non-negotiable) |
| `.ai-context/config.yaml` | Default persona, project settings |
| `.ai-context/terminology.yaml` | "Use X not Y" preferences |
| `.ai-context/book.yaml` | Auto-managed by AI via PRs |

### Choosing a Different LLM

Default is Claude Sonnet 4.5. To use a different model, add a `MODEL` secret:

```bash
MODEL=claude-haiku-4-5-20251201   # Cheaper, faster
MODEL=claude-opus-4-5-20251101    # Most capable
MODEL=deepseek-reasoner           # DeepSeek alternative
MODEL=gemini-2.5-flash            # Google alternative
```

> **Note:** Only reasoning models work (ones with "thinking" capability). GPT-4o won't work.

### Creating a Bot Identity (Optional)

Want AI comments to appear as `margot-ai-editor[bot]` instead of `github-actions[bot]`?

1. Create a GitHub App (Settings → Developer settings → GitHub Apps)
2. Give it Contents, Issues, and Pull requests permissions
3. Install it on your repo
4. Add `AI_EDITOR_APP_ID` and `AI_EDITOR_PRIVATE_KEY` secrets

This is purely cosmetic—everything works without it.

---

## For Contributors: Development & Testing

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
