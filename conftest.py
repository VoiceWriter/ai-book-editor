"""Pytest configuration for AI Book Editor tests."""

import sys
from pathlib import Path

# Add .github directory to path so tests can import from scripts.utils
github_dir = Path(__file__).parent / ".github"
sys.path.insert(0, str(github_dir))
