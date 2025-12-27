"""Shared pytest fixtures for AI Book Editor tests."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add scripts path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / ".github" / "scripts"))


@pytest.fixture
def sample_transcript():
    """Sample voice memo transcript for testing."""
    return """Um, so I've been thinking about, you know, how to structure the opening chapter.
I think we should start with a story, like a real example of someone who struggled with
voice-to-text before discovering this workflow. It's important to hook the reader right away."""


@pytest.fixture
def sample_issue(sample_transcript):
    """Mock GitHub issue object."""
    issue = MagicMock()
    issue.number = 1
    issue.title = "Voice memo: Opening chapter ideas"
    issue.body = sample_transcript
    issue.labels = []
    return issue


@pytest.fixture
def sample_pr():
    """Mock GitHub PR object."""
    pr = MagicMock()
    pr.number = 1
    pr.title = "Add: Opening chapter content"
    pr.body = "Content from voice memo"
    pr.head.ref = "feature/voice-memo-1"
    pr.base.ref = "main"
    pr.get_files.return_value = []
    return pr


@pytest.fixture
def mock_repo(sample_issue):
    """Mock GitHub repository object."""
    repo = MagicMock()
    repo.name = "ai-book-editor-test"
    repo.full_name = "VoiceWriter/ai-book-editor-test"
    repo.default_branch = "main"
    repo.get_issue.return_value = sample_issue

    # Mock file content reading with side_effect so we can use assert_called_with
    def mock_get_contents(path, **kwargs):
        content = MagicMock()
        content.name = Path(path).name
        content.type = "file"

        # Return appropriate content based on path
        if path == "EDITOR_PERSONA.md":
            content.decoded_content = b"You are a supportive editor."
        elif path == "EDITORIAL_GUIDELINES.md":
            content.decoded_content = b"Always preserve the author's voice."
        elif path == "GLOSSARY.md":
            content.decoded_content = b"# Glossary\n\nTerm definitions here."
        elif path == "chapters":
            # Return list of chapter files
            chapter1 = MagicMock()
            chapter1.name = "chapter-01-intro.md"
            chapter1.type = "file"
            chapter2 = MagicMock()
            chapter2.name = "chapter-02-capture.md"
            chapter2.type = "file"
            return [chapter1, chapter2]
        elif path.startswith(".ai-context/"):
            if "knowledge.jsonl" in path:
                content.decoded_content = b'{"question": "What is the book about?", "answer": "Voice-to-text workflows"}'
            elif "terminology.yaml" in path:
                content.decoded_content = (
                    b"voice memo: voice memo\ntranscript: transcript"
                )
            elif "themes.yaml" in path:
                content.decoded_content = b"- productivity\n- writing workflows"
            elif "author-preferences.yaml" in path:
                content.decoded_content = b"tone: casual\nformality: low"
            else:
                raise Exception("File not found")
        else:
            content.decoded_content = b"Sample content"

        return content

    repo.get_contents = MagicMock(side_effect=mock_get_contents)
    return repo


@pytest.fixture
def mock_github_client(mock_repo):
    """Mock GitHub client."""
    client = MagicMock()
    client.get_repo.return_value = mock_repo
    return client


@pytest.fixture
def sample_knowledge_base():
    """Sample knowledge base data."""
    return {
        "qa_pairs": [
            {
                "question": "What is the book about?",
                "answer": "Voice-to-text workflows for writers",
            }
        ],
        "terminology": {"voice memo": "voice memo", "transcript": "transcript"},
        "themes": ["productivity", "writing workflows", "developer tools"],
        "preferences": {"tone": "casual", "formality": "low"},
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for editorial analysis."""
    from scripts.utils.llm_client import LLMResponse, LLMUsage

    content = """### Cleaned Transcript

I've been thinking about how to structure the opening chapter. I think we should start with a story—a real example of someone who struggled with voice-to-text before discovering this workflow. It's important to hook the reader right away.

### Content Analysis

This voice memo focuses on chapter structure and reader engagement. Key themes:
- Opening hooks and reader engagement
- Storytelling as a teaching tool
- Voice-to-text workflow struggles

### Suggested Placement

This content would fit well at the beginning of chapter-01-intro.md.

### Editorial Notes

**What's working:**
- Clear vision for the opening
- Reader-first approach

**Needs clarification:**
- Do you have a specific story in mind?

### Ready for PR?

Yes, this is ready to integrate with minor clarification."""

    return LLMResponse(
        content=content,
        reasoning="I analyzed the voice memo for structure and clarity.",
        usage=LLMUsage(
            model="claude-sonnet-4-5-20250929",
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            cost_usd=0.0045,
            cache_read_tokens=0,
            cache_creation_tokens=0,
        ),
    )


@pytest.fixture
def seed_data():
    """Load seed data for tests."""
    seed_file = Path(__file__).parent.parent / "seeds/issues.json"
    if seed_file.exists():
        with open(seed_file) as f:
            return json.load(f)
    return {"issues": [], "labels": []}
