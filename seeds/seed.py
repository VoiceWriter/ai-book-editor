#!/usr/bin/env python3
"""
Seed test data into ai-book-editor-test repository.

Usage:
    python seeds/seed.py                    # Seed all data
    python seeds/seed.py --issues           # Seed only issues
    python seeds/seed.py --labels           # Seed only labels
    python seeds/seed.py --clean            # Delete all test issues
    python seeds/seed.py --repo owner/repo  # Use different repo
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add parent for imports if running directly
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from github import Github
except ImportError:
    print("Install PyGithub: pip install PyGithub")
    sys.exit(1)


def load_seeds() -> dict:
    """Load seed data from JSON file."""
    seed_file = Path(__file__).parent / "issues.json"
    with open(seed_file) as f:
        return json.load(f)


def get_github_client() -> Github:
    """Get authenticated GitHub client."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN not set")
        print("Run: export GITHUB_TOKEN=ghp_...")
        sys.exit(1)
    return Github(token)


def seed_labels(repo, labels: list, verbose: bool = True):
    """Create labels in repository."""
    existing = {lbl.name for lbl in repo.get_labels()}

    for label in labels:
        if label["name"] in existing:
            if verbose:
                print(f"  Label exists: {label['name']}")
            continue

        try:
            repo.create_label(
                name=label["name"], color=label["color"], description=label.get("description", "")
            )
            if verbose:
                print(f"  Created label: {label['name']}")
        except Exception as e:
            print(f"  Error creating {label['name']}: {e}")


def seed_issues(repo, issues: list, verbose: bool = True):
    """Create issues in repository."""
    created = []

    for issue_data in issues:
        try:
            # Get label objects
            labels = []
            for label_name in issue_data.get("labels", []):
                try:
                    labels.append(repo.get_label(label_name))
                except Exception:
                    pass  # Label doesn't exist, skip

            issue = repo.create_issue(
                title=issue_data["title"], body=issue_data["body"], labels=labels
            )
            created.append(issue)
            if verbose:
                print(f"  Created issue #{issue.number}: {issue.title}")
        except Exception as e:
            print(f"  Error creating issue: {e}")

    return created


def clean_test_issues(repo, verbose: bool = True):
    """Close all test issues (those starting with 'Voice memo:' or '[AI')."""
    closed = 0
    for issue in repo.get_issues(state="open"):
        if issue.title.startswith("Voice memo:") or issue.title.startswith("[AI"):
            issue.edit(state="closed")
            closed += 1
            if verbose:
                print(f"  Closed issue #{issue.number}: {issue.title}")

    if verbose:
        print(f"  Closed {closed} test issues")


def main():
    parser = argparse.ArgumentParser(description="Seed test data")
    parser.add_argument(
        "--repo", default="VoiceWriter/ai-book-editor-test", help="Target repository (owner/repo)"
    )
    parser.add_argument("--issues", action="store_true", help="Seed only issues")
    parser.add_argument("--labels", action="store_true", help="Seed only labels")
    parser.add_argument("--clean", action="store_true", help="Clean test issues")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    args = parser.parse_args()

    verbose = not args.quiet

    if verbose:
        print(f"Connecting to {args.repo}...")

    gh = get_github_client()
    repo = gh.get_repo(args.repo)

    seeds = load_seeds()

    if args.clean:
        if verbose:
            print("Cleaning test issues...")
        clean_test_issues(repo, verbose)
        return

    # Default: seed everything
    do_labels = args.labels or (not args.issues and not args.labels)
    do_issues = args.issues or (not args.issues and not args.labels)

    if do_labels:
        if verbose:
            print("Seeding labels...")
        seed_labels(repo, seeds["labels"], verbose)

    if do_issues:
        if verbose:
            print("Seeding issues...")
        seed_issues(repo, seeds["issues"], verbose)

    if verbose:
        print("Done!")


if __name__ == "__main__":
    main()
