# AI Book Editor - Development & Testing

.PHONY: help install test-issue test-comment test-pr test-scheduled lint clean

help:
	@echo "AI Book Editor - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install Python dependencies"
	@echo "  make setup-act      Install act for local GitHub Actions testing"
	@echo ""
	@echo "Local Testing (requires .secrets file):"
	@echo "  make test-issue     Simulate new voice transcription issue"
	@echo "  make test-comment   Simulate @ai-editor comment"
	@echo "  make test-pr        Simulate PR opened event"
	@echo "  make test-scheduled Run scheduled review locally"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run Python linter"
	@echo "  make clean          Remove generated files"

install:
	pip install -r requirements.txt

setup-act:
	@echo "Installing act..."
	@if command -v brew >/dev/null 2>&1; then \
		brew install act; \
	else \
		curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash; \
	fi
	@echo ""
	@echo "Create .secrets file from .secrets.example:"
	@echo "  cp .secrets.example .secrets"
	@echo "  # Edit .secrets with your API keys"

test-issue:
	@if [ ! -f .secrets ]; then echo "Error: .secrets file not found. Run: cp .secrets.example .secrets"; exit 1; fi
	act issues -e test-events/new-issue.json -W .github/workflows/process-transcription.yml

test-comment:
	@if [ ! -f .secrets ]; then echo "Error: .secrets file not found"; exit 1; fi
	act issue_comment -e test-events/issue-comment.json -W .github/workflows/respond-to-feedback.yml

test-pr:
	@if [ ! -f .secrets ]; then echo "Error: .secrets file not found"; exit 1; fi
	act pull_request -e test-events/pull-request.json -W .github/workflows/review-pr.yml

test-scheduled:
	@if [ ! -f .secrets ]; then echo "Error: .secrets file not found"; exit 1; fi
	act workflow_dispatch -W .github/workflows/scheduled-review.yml

# Run Python script directly for faster iteration
test-process-local:
	@if [ -z "$$ANTHROPIC_API_KEY" ]; then echo "Error: ANTHROPIC_API_KEY not set"; exit 1; fi
	@if [ -z "$$GITHUB_TOKEN" ]; then echo "Error: GITHUB_TOKEN not set"; exit 1; fi
	ISSUE_NUMBER=1 GITHUB_REPOSITORY=VoiceWriter/ai-book-editor-test \
		python .github/scripts/process_transcription.py

lint:
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check .github/scripts/; \
	else \
		echo "Install ruff: pip install ruff"; \
	fi

clean:
	rm -rf output/
	rm -rf __pycache__/
	rm -rf .github/scripts/__pycache__/
	rm -rf .github/scripts/utils/__pycache__/
	find . -name "*.pyc" -delete
