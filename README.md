# AI Book Editor

A GitHub-native AI editorial system for transforming voice memos and written fragments into polished books.

## Architecture

100% GitHub-native. No external servers, no databases. Just:
- **GitHub Issues** - Input, discussion, state management
- **GitHub Actions** - AI processing via Claude API
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
- `ANTHROPIC_API_KEY` - Your Claude API key

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

## License

MIT
