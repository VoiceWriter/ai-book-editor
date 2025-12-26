# AI Book Editor - Development & Testing

.PHONY: help install test-issue test-comment test-pr test-scheduled lint clean seed seed-labels seed-clean init init-dry-run e2e e2e-quick e2e-dry-run

help:
	@echo "AI Book Editor - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install Python dependencies"
	@echo "  make setup-act      Install act for local GitHub Actions testing"
	@echo ""
	@echo "Unit Tests (pytest):"
	@echo "  make test           Run all unit tests"
	@echo "  make test-fast      Run tests, stop on first failure"
	@echo "  make test-cov       Run tests with coverage report"
	@echo ""
	@echo "Integration Tests (requires .env):"
	@echo "  make test-local     Run process_transcription.py directly"
	@echo ""
	@echo "GitHub Actions Simulation (requires act + .env):"
	@echo "  make test-issue     Simulate new voice transcription issue"
	@echo "  make test-comment   Simulate @margot-ai-editor comment"
	@echo "  make test-pr        Simulate PR opened event"
	@echo "  make test-scheduled Run scheduled review locally"
	@echo ""
	@echo "Repository Setup:"
	@echo "  make init           Initialize a repo (labels, templates, .ai-context)"
	@echo "  make init-dry-run   Preview what init would create"
	@echo ""
	@echo "E2E Tests (requires gh CLI):"
	@echo "  make e2e            Run full E2E test suite"
	@echo "  make e2e-quick      Run quick smoke test (phases 1, 9)"
	@echo "  make e2e-dry-run    Preview E2E tests without creating issues"
	@echo ""
	@echo "Seed Data (for testing):"
	@echo "  make seed           Create test issues/labels in test repo"
	@echo "  make seed-labels    Create only labels"
	@echo "  make seed-clean     Close all test issues"
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
	@echo "Now edit .env with your API keys:"
	@echo "  ANTHROPIC_API_KEY=sk-ant-..."
	@echo "  GITHUB_TOKEN=ghp_..."

# Check for .env file
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found."; \
		echo "Add your keys to .env:"; \
		echo "  ANTHROPIC_API_KEY=sk-ant-..."; \
		echo "  GITHUB_TOKEN=ghp_..."; \
		exit 1; \
	fi

# Local testing with act (runs in Docker, simulates GitHub Actions)
test-issue: check-env
	act issues -e test-events/new-issue.json -W .github/workflows/process-transcription.yml

test-comment: check-env
	act issue_comment -e test-events/issue-comment.json -W .github/workflows/respond-to-feedback.yml

test-pr: check-env
	act pull_request -e test-events/pull-request.json -W .github/workflows/review-pr.yml

test-scheduled: check-env
	act workflow_dispatch -W .github/workflows/scheduled-review.yml

# Run Python script directly (faster iteration, no Docker)
test-local: check-env
	@set -a && source .env && set +a && \
	ISSUE_NUMBER=1 python .github/scripts/process_transcription.py

# Unit tests with pytest
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=.github/scripts --cov-report=term-missing

test-fast:
	pytest tests/ -v -x --tb=short

lint:
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check .github/scripts/; \
	else \
		echo "Install ruff: pip install ruff"; \
	fi

# Seed test data
seed: check-env
	@source .venv/bin/activate 2>/dev/null || true && \
	set -a && source .env && set +a && \
	python seeds/seed.py

seed-labels: check-env
	@source .venv/bin/activate 2>/dev/null || true && \
	set -a && source .env && set +a && \
	python seeds/seed.py --labels

seed-clean: check-env
	@source .venv/bin/activate 2>/dev/null || true && \
	set -a && source .env && set +a && \
	python seeds/seed.py --clean

clean:
	rm -rf output/
	rm -rf __pycache__/
	rm -rf .github/scripts/__pycache__/
	rm -rf .github/scripts/utils/__pycache__/
	find . -name "*.pyc" -delete

# Initialize repository (create labels, templates, .ai-context)
init: check-env
	@echo "Initializing repository..."
	@source .venv/bin/activate 2>/dev/null || true && \
	set -a && source .env && set +a && \
	python seeds/init.py --repo $(REPO)

init-dry-run: check-env
	@echo "Previewing initialization (dry run)..."
	@source .venv/bin/activate 2>/dev/null || true && \
	set -a && source .env && set +a && \
	python seeds/init.py --repo $(REPO) --dry-run

# Default repo for init and E2E tests
REPO ?= VoiceWriter/ai-book-editor-test

# E2E tests using gh CLI
e2e:
	@echo "Running full E2E test suite..."
	python seeds/e2e_tests.py --repo $(REPO)

e2e-quick:
	@echo "Running quick E2E smoke test..."
	python seeds/e2e_tests.py --repo $(REPO) --quick

e2e-dry-run:
	@echo "Previewing E2E tests (dry run)..."
	python seeds/e2e_tests.py --repo $(REPO) --dry-run
