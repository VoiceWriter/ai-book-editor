# Test Seeds

Test data for ai-book-editor development and testing.

## Files

- `issues.json` - Sample issues and labels for testing
- `seed.py` - Script to create test data in GitHub

## Usage

### Seed all test data
```bash
# From repo root
source .venv/bin/activate
source .env
python seeds/seed.py
```

### Seed specific data
```bash
python seeds/seed.py --labels    # Only labels
python seeds/seed.py --issues    # Only issues
```

### Clean up test data
```bash
python seeds/seed.py --clean     # Close all test issues
```

### Use different repo
```bash
python seeds/seed.py --repo thoughtpunch/babyman
```

## Test Issues

The seed data includes:

1. **Voice memo: Opening chapter ideas** - Basic voice memo for chapter intro
2. **Voice memo: The capture phase deep dive** - Technical content about capture
3. **Voice memo: Editing workflow** - Process-focused content
4. **Voice memo: Addressing impostor syndrome** - Meta/emotional content
5. **[AI Question] What's the target word count?** - Sample AI question

## Labels

All required labels are included with proper colors:
- `voice_transcription` - Blue
- `ai-reviewed` - Green
- `pr-created` - Purple
- `awaiting-author` - Yellow
- `ai-question` - Peach
- `ai-suggestion` - Lavender
- And more...

## Using with act

The `test-events/` directory contains JSON files that simulate GitHub webhook events:

```bash
# Run locally with act
make test-issue      # Uses test-events/new-issue.json
make test-comment    # Uses test-events/issue-comment.json
```

## Using with pytest

```python
import json
from pathlib import Path

def load_test_issues():
    seeds = Path(__file__).parent.parent / "seeds/issues.json"
    with open(seeds) as f:
        return json.load(f)["issues"]

def test_process_transcription():
    issues = load_test_issues()
    # Use issues[0] for testing...
```
