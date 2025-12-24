"""GitHub API utilities for AI Book Editor."""

import os
from typing import Any, Dict, List, Optional

from github import Github


def get_github_client() -> Github:
    """Get authenticated GitHub client."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable not set")
    return Github(token)


def get_repo(gh: Github, repo_name: Optional[str] = None):
    """Get repository object."""
    repo_name = repo_name or os.environ.get("GITHUB_REPOSITORY")
    if not repo_name:
        raise ValueError("Repository name not provided")
    return gh.get_repo(repo_name)


def get_issue(repo, issue_number: int):
    """Get issue by number."""
    return repo.get_issue(issue_number)


def get_pull_request(repo, pr_number: int):
    """Get PR by number."""
    return repo.get_pull(pr_number)


def read_file_content(repo, path: str, ref: str = None) -> Optional[str]:
    """Read file content from repo. Returns None if file doesn't exist."""
    try:
        kwargs = {"ref": ref} if ref else {}
        content = repo.get_contents(path, **kwargs)
        return content.decoded_content.decode("utf-8")
    except Exception:
        return None


def list_files_in_directory(repo, path: str, ref: str = None) -> List[str]:
    """List files in a directory."""
    try:
        kwargs = {"ref": ref} if ref else {}
        contents = repo.get_contents(path, **kwargs)
        return [c.name for c in contents if c.type == "file"]
    except Exception:
        return []


def create_branch(repo, branch_name: str, from_branch: str = None) -> bool:
    """Create a new branch. Returns True if created, False if exists."""
    from_branch = from_branch or repo.default_branch
    try:
        ref = repo.get_git_ref(f"heads/{from_branch}")
        repo.create_git_ref(f"refs/heads/{branch_name}", ref.object.sha)
        return True
    except Exception:
        return False  # Branch likely already exists


def create_or_update_file(repo, path: str, content: str, message: str, branch: str) -> None:
    """Create or update a file in the repo."""
    try:
        # Try to get existing file
        file = repo.get_contents(path, ref=branch)
        repo.update_file(path, message, content, file.sha, branch=branch)
    except Exception:
        # File doesn't exist, create it
        repo.create_file(path, message, content, branch=branch)


def append_to_file(
    repo, path: str, content: str, message: str, branch: str, separator: str = "\n\n---\n\n"
) -> None:
    """Append content to an existing file."""
    try:
        file = repo.get_contents(path, ref=branch)
        existing = file.decoded_content.decode("utf-8")
        new_content = existing + separator + content
        repo.update_file(path, message, new_content, file.sha, branch=branch)
    except Exception:
        # File doesn't exist, create with just the new content
        repo.create_file(path, message, content, branch=branch)


def get_issue_comments(issue) -> List[Dict[str, Any]]:
    """Get all comments on an issue."""
    return [
        {"id": c.id, "body": c.body, "user": c.user.login, "created_at": c.created_at.isoformat()}
        for c in issue.get_comments()
    ]


def format_commit_message(
    type_: str,
    scope: str,
    description: str,
    body: str = None,
    source_issue: int = None,
    reviewed_by: str = "ai-editor",
    editorial_type: str = "addition",
) -> str:
    """Format a structured commit message."""
    msg = f"{type_}({scope}): {description}"

    if body:
        msg += f"\n\n{body}"

    msg += "\n"
    if source_issue:
        msg += f"\nSource: #{source_issue}"
    msg += f"\nReviewed-by: {reviewed_by}"
    msg += f"\nEditorial-type: {editorial_type}"

    return msg


# === CRUD Operations for Issues ===


def close_issue(issue, comment: Optional[str] = None) -> None:
    """Close an issue with optional comment."""
    if comment:
        issue.create_comment(comment)
    issue.edit(state="closed")


def reopen_issue(issue) -> None:
    """Reopen a closed issue."""
    issue.edit(state="open")


def add_labels(issue, labels: List[str]) -> None:
    """Add labels to an issue."""
    for lbl in labels:
        issue.add_to_labels(lbl)


def remove_labels(issue, labels: List[str]) -> None:
    """Remove labels from an issue."""
    for lbl in labels:
        try:
            issue.remove_from_labels(lbl)
        except Exception:
            pass  # Label might not exist


def edit_issue(issue, title: Optional[str] = None, body: Optional[str] = None) -> None:
    """Edit issue title and/or body."""
    kwargs = {}
    if title is not None:
        kwargs["title"] = title
    if body is not None:
        kwargs["body"] = body
    if kwargs:
        issue.edit(**kwargs)


def create_issue(repo, title: str, body: str, labels: Optional[List[str]] = None):
    """Create a new issue."""
    kwargs = {"title": title, "body": body}
    if labels:
        kwargs["labels"] = labels
    return repo.create_issue(**kwargs)


def add_comment(issue, body: str) -> None:
    """Add a comment to an issue."""
    issue.create_comment(body)


# === CRUD Operations for Pull Requests ===


def close_pr(pr, comment: Optional[str] = None) -> None:
    """Close a PR without merging."""
    if comment:
        pr.create_issue_comment(comment)
    pr.edit(state="closed")


def approve_pr(pr, body: str = "LGTM") -> None:
    """Approve a PR."""
    pr.create_review(body=body, event="APPROVE")


def request_changes_pr(pr, body: str) -> None:
    """Request changes on a PR."""
    pr.create_review(body=body, event="REQUEST_CHANGES")


def comment_pr(pr, body: str) -> None:
    """Add a review comment (neither approve nor request changes)."""
    pr.create_review(body=body, event="COMMENT")


def merge_pr(pr, commit_title: Optional[str] = None, merge_method: str = "squash") -> bool:
    """Merge a PR. Returns True if successful."""
    try:
        kwargs = {"merge_method": merge_method}
        if commit_title:
            kwargs["commit_title"] = commit_title
        pr.merge(**kwargs)
        return True
    except Exception:
        return False


def get_pr_for_issue(repo, issue_number: int):
    """Find a PR that closes/references an issue, if any."""
    # Check if there's a branch for this issue
    try:
        branch_name = f"voice-memo/issue-{issue_number}"
        pulls = list(repo.get_pulls(state="open", head=f"{repo.owner.login}:{branch_name}"))
        if pulls:
            return pulls[0]
    except Exception:
        pass
    return None
