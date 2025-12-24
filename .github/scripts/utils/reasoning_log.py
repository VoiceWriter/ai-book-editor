"""
Reasoning log storage for AI Book Editor.

Records chain-of-thought reasoning for every AI decision, enabling:
1. Transparency - Users can see WHY the AI made decisions
2. Learning - System can analyze patterns in reasoning
3. Debugging - Trace back through decision history
4. Improvement - Identify where reasoning went wrong

Log entries are stored in .ai-context/reasoning-log.jsonl (JSON Lines format).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReasoningLogEntry(BaseModel):
    """A single reasoning log entry."""

    model_config = ConfigDict(strict=True)

    # Identifiers
    timestamp: str = Field(description="ISO format timestamp")
    issue_number: int = Field(description="GitHub issue number")
    comment_id: Optional[int] = Field(default=None, description="Triggering comment ID")

    # Input context
    author_message: str = Field(description="The author's message that triggered this")
    conversation_summary: str = Field(description="Brief summary of conversation history")

    # AI reasoning
    model_used: str = Field(description="LLM model used")
    reasoning: str = Field(description="Full chain-of-thought reasoning")
    thinking_blocks: List[str] = Field(
        default_factory=list, description="Structured thinking steps"
    )

    # Decision made
    inferred_intent: str = Field(description="What the AI understood the author wanted")
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence level")
    actions_proposed: List[str] = Field(description="Actions the AI proposed to take")
    confirmation_required: bool = Field(description="Whether confirmation was requested")

    # Outcome (updated later)
    actions_executed: List[str] = Field(
        default_factory=list, description="Actions actually executed"
    )
    outcome: Literal["pending", "confirmed", "rejected", "auto_executed"] = Field(
        default="pending", description="Final outcome of the decision"
    )
    author_feedback: Optional[str] = Field(
        default=None, description="Author's response if any"
    )

    # Cost tracking
    tokens_used: int = Field(default=0, description="Total tokens used")
    cost_usd: float = Field(default=0.0, description="Cost in USD")


class ReasoningLogger:
    """Handles reading and writing reasoning logs."""

    def __init__(self, repo_path: Optional[Path] = None):
        """Initialize logger with repository path."""
        self.repo_path = repo_path or Path.cwd()
        self.log_dir = self.repo_path / ".ai-context"
        self.log_file = self.log_dir / "reasoning-log.jsonl"

    def ensure_directory(self) -> None:
        """Create log directory if it doesn't exist."""
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_decision(
        self,
        issue_number: int,
        author_message: str,
        conversation_summary: str,
        model_used: str,
        reasoning: str,
        thinking_blocks: List[str],
        inferred_intent: str,
        confidence: str,
        actions_proposed: List[str],
        confirmation_required: bool,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        comment_id: Optional[int] = None,
    ) -> ReasoningLogEntry:
        """
        Log an AI decision with full reasoning.

        Returns the created log entry.
        """
        self.ensure_directory()

        entry = ReasoningLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            issue_number=issue_number,
            comment_id=comment_id,
            author_message=author_message,
            conversation_summary=conversation_summary,
            model_used=model_used,
            reasoning=reasoning,
            thinking_blocks=thinking_blocks,
            inferred_intent=inferred_intent,
            confidence=confidence,
            actions_proposed=actions_proposed,
            confirmation_required=confirmation_required,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )

        # Append to log file
        with open(self.log_file, "a") as f:
            f.write(entry.model_dump_json() + "\n")

        return entry

    def update_outcome(
        self,
        issue_number: int,
        outcome: str,
        actions_executed: Optional[List[str]] = None,
        author_feedback: Optional[str] = None,
    ) -> None:
        """
        Update the outcome of a previous decision.

        Finds the most recent entry for the issue and updates it.
        """
        if not self.log_file.exists():
            return

        # Read all entries
        entries = []
        with open(self.log_file, "r") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))

        # Find and update the most recent entry for this issue
        for i in range(len(entries) - 1, -1, -1):
            if entries[i]["issue_number"] == issue_number and entries[i]["outcome"] == "pending":
                entries[i]["outcome"] = outcome
                if actions_executed:
                    entries[i]["actions_executed"] = actions_executed
                if author_feedback:
                    entries[i]["author_feedback"] = author_feedback
                break

        # Rewrite file
        with open(self.log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    def get_recent_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent log entries."""
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file, "r") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))

        return entries[-limit:]

    def get_entries_for_issue(self, issue_number: int) -> List[Dict[str, Any]]:
        """Get all entries for a specific issue."""
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry["issue_number"] == issue_number:
                        entries.append(entry)

        return entries

    def get_rejected_decisions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get decisions that were rejected by the author."""
        if not self.log_file.exists():
            return []

        rejected = []
        with open(self.log_file, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry.get("outcome") == "rejected":
                        rejected.append(entry)

        return rejected[-limit:]

    def get_confirmation_patterns(self) -> Dict[str, Any]:
        """
        Analyze patterns in confirmations vs rejections.

        Returns stats useful for learning.
        """
        if not self.log_file.exists():
            return {"total": 0, "confirmed": 0, "rejected": 0, "auto_executed": 0}

        stats = {"total": 0, "confirmed": 0, "rejected": 0, "auto_executed": 0, "pending": 0}
        confidence_outcomes = {"high": [], "medium": [], "low": []}

        with open(self.log_file, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    stats["total"] += 1
                    outcome = entry.get("outcome", "pending")
                    if outcome in stats:
                        stats[outcome] += 1

                    confidence = entry.get("confidence", "medium")
                    if confidence in confidence_outcomes:
                        confidence_outcomes[confidence].append(outcome)

        # Calculate confirmation rates by confidence level
        stats["by_confidence"] = {}
        for conf, outcomes in confidence_outcomes.items():
            if outcomes:
                confirmed = outcomes.count("confirmed") + outcomes.count("auto_executed")
                stats["by_confidence"][conf] = {
                    "total": len(outcomes),
                    "success_rate": confirmed / len(outcomes) if outcomes else 0,
                }

        return stats


def create_logger(repo_path: Optional[Path] = None) -> ReasoningLogger:
    """Create a reasoning logger instance."""
    return ReasoningLogger(repo_path)


# Convenience function for GitHub Actions context
def get_actions_logger() -> ReasoningLogger:
    """Get a logger configured for GitHub Actions environment."""
    # In Actions, we're in the repo root
    return ReasoningLogger(Path.cwd())
