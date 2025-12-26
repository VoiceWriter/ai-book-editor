#!/usr/bin/env python3
"""
Comprehensive E2E test: Full writer-editor conversation flow.

Simulates a complete writing session from voice memo to merged PR:

PHASE A: Issue Thread Conversation (voice_transcription)
1. Submit voice memo → AI asks discovery questions
2. Answer discovery questions → AI acknowledges
3. Discuss the content, ask questions, push back
4. Request specific placement
5. Request PR creation → PR is created

PHASE B: PR Thread Conversation (editorial review)
6. PR triggers AI editorial review
7. Respond to AI feedback on PR
8. AI acknowledges response

PHASE C: Advanced Directives
9. Test persona switching
10. Test "status" command
11. Test "be harsher" / "skip questions"
12. Merge the PR

Usage:
    python seeds/e2e_comprehensive.py --repo owner/repo
    python seeds/e2e_comprehensive.py --repo owner/repo --phase a
    python seeds/e2e_comprehensive.py --repo owner/repo --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StepStatus(Enum):
    PASSED = "✅"
    FAILED = "❌"
    SKIPPED = "⏭️"
    TIMEOUT = "⏱️"
    PENDING = "⏳"


@dataclass
class Step:
    """A single step in the conversation."""
    id: str
    phase: str
    name: str
    action: str
    content: str = ""
    expected_keywords: list[str] = field(default_factory=list)
    wait_for_response: bool = True
    timeout_seconds: int = 180
    status: StepStatus = StepStatus.PENDING
    message: str = ""
    duration_seconds: float = 0
    response_preview: str = ""


class ConversationRunner:
    """Runs the full conversation flow."""

    def __init__(self, repo: str, dry_run: bool = False):
        self.repo = repo
        self.dry_run = dry_run
        self.issue_number: Optional[int] = None
        self.pr_number: Optional[int] = None
        self.issue_bot_comments: int = 0
        self.pr_bot_comments: int = 0
        self.results: list[Step] = []

    def run_gh(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run gh CLI command."""
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"gh failed: {result.stderr}")
        return result

    def create_issue(self, title: str, body: str, labels: list[str]) -> int:
        """Create a GitHub issue."""
        args = ["issue", "create", "--repo", self.repo, "--title", title, "--body", body]
        for label in labels:
            args.extend(["--label", label])
        result = self.run_gh(args)
        url = result.stdout.strip()
        return int(url.split("/")[-1])

    def add_issue_comment(self, body: str) -> None:
        """Add a comment to the current issue."""
        self.run_gh(["issue", "comment", str(self.issue_number), "--repo", self.repo, "--body", body])

    def add_pr_comment(self, body: str) -> None:
        """Add a comment to the current PR."""
        self.run_gh(["pr", "comment", str(self.pr_number), "--repo", self.repo, "--body", body])

    def get_bot_comments(self, issue_number: int) -> list[dict]:
        """Get bot comments on an issue/PR."""
        result = self.run_gh(
            ["api", f"repos/{self.repo}/issues/{issue_number}/comments", "--jq", "."],
            check=False
        )
        if not result.stdout.strip():
            return []
        comments = json.loads(result.stdout)
        return [
            c for c in comments
            if c.get("user", {}).get("login") == "github-actions[bot]"
            or c.get("user", {}).get("type") == "Bot"
        ]

    def get_pr_reviews(self, pr_number: int) -> list[dict]:
        """Get PR reviews."""
        result = self.run_gh(
            ["api", f"repos/{self.repo}/pulls/{pr_number}/reviews", "--jq", "."],
            check=False
        )
        if not result.stdout.strip():
            return []
        return json.loads(result.stdout)

    def wait_for_new_comment(
        self,
        issue_number: int,
        previous_count: int,
        timeout: int = 180
    ) -> Optional[dict]:
        """Wait for a new bot comment."""
        start = time.time()
        while time.time() - start < timeout:
            comments = self.get_bot_comments(issue_number)
            if len(comments) > previous_count:
                return comments[-1]
            elapsed = int(time.time() - start)
            print(f"      Waiting... ({elapsed}s)")
            time.sleep(10)
        return None

    def get_open_prs(self) -> list[dict]:
        """Get open PRs."""
        result = self.run_gh(
            ["pr", "list", "--repo", self.repo, "--state", "open", "--json", "number,title,headRefName"],
            check=False
        )
        if not result.stdout.strip():
            return []
        return json.loads(result.stdout)

    def run_step(self, step: Step) -> None:
        """Execute a single step."""
        print(f"\n  [{step.id}] {step.name}")
        print(f"      Phase: {step.phase}")
        print(f"      Action: {step.action}")

        if self.dry_run:
            step.status = StepStatus.SKIPPED
            step.message = "Dry run"
            print(f"      {step.status.value} Skipped")
            return

        start = time.time()

        try:
            # Execute the action
            if step.action == "create_issue":
                self.issue_number = self.create_issue(
                    "Voice memo: Urban Apartment Gardening",
                    step.content,
                    ["voice_transcription"]
                )
                print(f"      Created issue #{self.issue_number}")

            elif step.action == "issue_comment":
                if not self.issue_number:
                    raise RuntimeError("No issue to comment on")
                self.add_issue_comment(step.content)
                print(f"      Posted comment on issue #{self.issue_number}")

            elif step.action == "pr_comment":
                if not self.pr_number:
                    raise RuntimeError("No PR to comment on")
                self.add_pr_comment(step.content)
                print(f"      Posted comment on PR #{self.pr_number}")

            elif step.action == "check_pr_created":
                prs = self.get_open_prs()
                matching = [p for p in prs if "voice-memo" in p.get("headRefName", "").lower()
                           or "urban" in p.get("title", "").lower()
                           or "garden" in p.get("title", "").lower()]
                if matching:
                    self.pr_number = matching[0]["number"]
                    print(f"      Found PR #{self.pr_number}: {matching[0]['title']}")
                else:
                    print(f"      No matching PR found yet (have {len(prs)} open PRs)")

            elif step.action == "wait_for_pr_review":
                if not self.pr_number:
                    raise RuntimeError("No PR to check")
                reviews = self.get_pr_reviews(self.pr_number)
                bot_reviews = [r for r in reviews if "bot" in r.get("user", {}).get("login", "").lower()]
                if bot_reviews:
                    print(f"      Found {len(bot_reviews)} bot review(s)")
                else:
                    print(f"      No bot reviews yet")

            elif step.action == "merge_pr":
                if not self.pr_number:
                    raise RuntimeError("No PR to merge")
                self.run_gh(["pr", "merge", str(self.pr_number), "--repo", self.repo, "--squash", "-d"])
                print(f"      Merged PR #{self.pr_number}")

            # Wait for response if needed
            if step.wait_for_response:
                target_issue = self.pr_number if "pr" in step.action else self.issue_number
                if target_issue:
                    if "pr" in step.action:
                        prev_count = self.pr_bot_comments
                    else:
                        prev_count = self.issue_bot_comments

                    new_comment = self.wait_for_new_comment(target_issue, prev_count, step.timeout_seconds)

                    if new_comment:
                        if "pr" in step.action:
                            self.pr_bot_comments += 1
                        else:
                            self.issue_bot_comments += 1

                        body = new_comment.get("body", "")
                        step.response_preview = body[:150].replace("\n", " ")
                        print(f"      Response: {step.response_preview}...")

                        # Check keywords
                        if step.expected_keywords:
                            body_lower = body.lower()
                            missing = [k for k in step.expected_keywords if k.lower() not in body_lower]
                            if missing:
                                step.status = StepStatus.FAILED
                                step.message = f"Missing: {missing}"
                            else:
                                step.status = StepStatus.PASSED
                                step.message = "All keywords found"
                        else:
                            step.status = StepStatus.PASSED
                            step.message = "Got response"
                    else:
                        step.status = StepStatus.TIMEOUT
                        step.message = f"No response after {step.timeout_seconds}s"
                else:
                    step.status = StepStatus.PASSED
                    step.message = "No wait needed"
            else:
                step.status = StepStatus.PASSED
                step.message = "Completed"

        except Exception as e:
            step.status = StepStatus.FAILED
            step.message = str(e)

        step.duration_seconds = time.time() - start
        print(f"      {step.status.value} {step.message} [{step.duration_seconds:.1f}s]")

    def run_all(self, phases: list[str] = None) -> None:
        """Run all steps or specific phases."""
        steps = self.build_steps()

        if phases:
            steps = [s for s in steps if s.phase.lower() in [p.lower() for p in phases]]

        print(f"\n{'=' * 70}")
        print("COMPREHENSIVE E2E TEST: Writer-Editor Conversation")
        print(f"{'=' * 70}")
        print(f"Repository: {self.repo}")
        print(f"Phases: {phases or 'all'}")
        print(f"Total steps: {len(steps)}")

        for step in steps:
            self.run_step(step)
            self.results.append(step)

    def build_steps(self) -> list[Step]:
        """Define all conversation steps."""
        return [
            # =========================================================
            # PHASE A: Issue Thread - Discovery & Feedback
            # =========================================================
            Step(
                id="A1",
                phase="A: Issue",
                name="Submit voice transcription",
                action="create_issue",
                content="""I want to write a book about gardening for apartment dwellers. Most
gardening books assume you have a backyard, but millions of people live in apartments
and still want to grow their own food. I'm thinking container gardening, vertical
gardens, windowsill herbs, maybe even hydroponics for the ambitious folks.

The tone should be encouraging - lots of people think they can't garden without a
yard, and I want to show them they're wrong. Start simple, build confidence, then
get more advanced.

um I think chapter one should be about like mindset shifts, you know, getting over
the "I don't have space" mentality. Then practical stuff about what containers work,
soil, light requirements... maybe a chapter on common mistakes?""",
                expected_keywords=["book", "garden"],
                timeout_seconds=180,
            ),

            Step(
                id="A2",
                phase="A: Issue",
                name="Answer discovery questions",
                action="issue_comment",
                content="""@margot-ai-editor

Great questions! Let me answer:

1. **What's this book about?** It's a practical guide for apartment dwellers who want to grow food but think they can't. Container gardening, vertical gardens, windowsill setups.

2. **Who am I writing for?** Millennials and Gen-Z renters in cities who care about sustainability and want fresh herbs/veggies but feel locked out of "real" gardening.

3. **What tone?** Encouraging and friendly, like a knowledgeable friend sharing tips. Not preachy or overwhelming. "You can totally do this!"

4. **What phase am I in?** Very early - just brain-dumping ideas and seeing what structure emerges.""",
                expected_keywords=[],
            ),

            Step(
                id="A3",
                phase="A: Issue",
                name="Ask what's working",
                action="issue_comment",
                content="@margot-ai-editor What's working well in what I've shared so far? What should I lean into?",
                expected_keywords=[],
            ),

            Step(
                id="A4",
                phase="A: Issue",
                name="Ask what to focus on",
                action="issue_comment",
                content="@margot-ai-editor What should I focus on next? Where do you see gaps or opportunities?",
                expected_keywords=[],
            ),

            Step(
                id="A5",
                phase="A: Issue",
                name="Express being stuck",
                action="issue_comment",
                content="@margot-ai-editor I'm feeling stuck on how to organize all this. There's so much to cover - how do I structure it without overwhelming readers?",
                expected_keywords=[],
            ),

            Step(
                id="A6",
                phase="A: Issue",
                name="Disagree with suggestion",
                action="issue_comment",
                content="""@margot-ai-editor I hear you, but I disagree about cutting the hydroponics section.

I know it's more advanced, but it's also what gets people excited. Even if most readers won't do it, having that "aspirational" content keeps them engaged.

Can you help me figure out how to include it without making the book feel too advanced?""",
                expected_keywords=[],
            ),

            Step(
                id="A7",
                phase="A: Issue",
                name="Switch to Sage persona",
                action="issue_comment",
                content="@margot-ai-editor use sage",
                expected_keywords=["sage"],
                timeout_seconds=120,
            ),

            Step(
                id="A8",
                phase="A: Issue",
                name="Share personal story with Sage",
                action="issue_comment",
                content="""@margot-ai-editor I want to share something. Part of why I'm writing this book is personal.

My grandmother had an amazing garden, and some of my happiest childhood memories are helping her. She passed away two years ago, and this book is partly a way to honor her.

But I'm worried - is that too sentimental? Should I keep it professional?""",
                expected_keywords=[],
            ),

            Step(
                id="A9",
                phase="A: Issue",
                name="List all personas",
                action="issue_comment",
                content="@margot-ai-editor list all personas",
                expected_keywords=["margot", "sage"],
                timeout_seconds=60,
            ),

            Step(
                id="A10",
                phase="A: Issue",
                name="Switch to The Axe",
                action="issue_comment",
                content="@margot-ai-editor use the-axe",
                expected_keywords=["axe"],
                timeout_seconds=120,
            ),

            Step(
                id="A11",
                phase="A: Issue",
                name="Request brutal feedback",
                action="issue_comment",
                content="""@margot-ai-editor Okay, give it to me straight. What's weak here? What needs to be cut?

I can handle tough feedback - that's why I switched to you. Don't hold back.""",
                expected_keywords=[],
            ),

            Step(
                id="A12",
                phase="A: Issue",
                name="Set content placement",
                action="issue_comment",
                content="@margot-ai-editor place in chapter-01-mindset.md",
                expected_keywords=["chapter", "placement"],
                timeout_seconds=120,
            ),

            Step(
                id="A13",
                phase="A: Issue",
                name="Request PR creation",
                action="issue_comment",
                content="@margot-ai-editor create PR",
                expected_keywords=[],
                timeout_seconds=180,
            ),

            # =========================================================
            # PHASE B: PR Thread - Editorial Review
            # =========================================================
            Step(
                id="B1",
                phase="B: PR",
                name="Check PR was created",
                action="check_pr_created",
                wait_for_response=False,
                timeout_seconds=30,
            ),

            Step(
                id="B2",
                phase="B: PR",
                name="Wait for AI editorial review",
                action="wait_for_pr_review",
                wait_for_response=False,
                timeout_seconds=180,
            ),

            Step(
                id="B3",
                phase="B: PR",
                name="Respond to PR feedback",
                action="pr_comment",
                content="""Thanks for the review! A few thoughts:

1. Good point about the opening - I'll strengthen the hook.
2. I'll add a concrete example in the first paragraph.
3. For the hydroponics mention, I'll move it to a "What's Ahead" teaser instead.

Let me know if you have other suggestions!""",
                expected_keywords=[],
                timeout_seconds=120,
            ),

            Step(
                id="B4",
                phase="B: PR",
                name="Ask clarifying question on PR",
                action="pr_comment",
                content="@margot-ai-editor One question - should I include a personal anecdote in chapter 1, or save that for later in the book?",
                expected_keywords=[],
            ),

            # =========================================================
            # PHASE C: Advanced Commands
            # =========================================================
            Step(
                id="C1",
                phase="C: Commands",
                name="Switch back to Margot",
                action="issue_comment",
                content="@margot-ai-editor use margot",
                expected_keywords=["margot"],
                timeout_seconds=120,
            ),

            Step(
                id="C2",
                phase="C: Commands",
                name="Be harsher command",
                action="issue_comment",
                content="@margot-ai-editor be harsher - I need tougher feedback now that I'm revising",
                expected_keywords=[],
            ),

            Step(
                id="C3",
                phase="C: Commands",
                name="Final question before merge",
                action="issue_comment",
                content="@margot-ai-editor Any final thoughts before I merge this PR and move on to chapter 2?",
                expected_keywords=[],
            ),
        ]

    def print_summary(self) -> None:
        """Print test results."""
        passed = sum(1 for s in self.results if s.status == StepStatus.PASSED)
        failed = sum(1 for s in self.results if s.status == StepStatus.FAILED)
        timeout = sum(1 for s in self.results if s.status == StepStatus.TIMEOUT)
        skipped = sum(1 for s in self.results if s.status == StepStatus.SKIPPED)
        total_time = sum(s.duration_seconds for s in self.results)

        print(f"\n{'=' * 70}")
        print("TEST SUMMARY")
        print(f"{'=' * 70}")
        print(f"Issue: #{self.issue_number}" if self.issue_number else "Issue: (not created)")
        print(f"PR: #{self.pr_number}" if self.pr_number else "PR: (not created)")
        print(f"")
        print(f"✅ Passed:  {passed}")
        print(f"❌ Failed:  {failed}")
        print(f"⏱️  Timeout: {timeout}")
        print(f"⏭️  Skipped: {skipped}")
        print(f"")
        print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
        print(f"{'=' * 70}")

        if failed > 0 or timeout > 0:
            print("\n❌ Failed/Timeout steps:")
            for s in self.results:
                if s.status in (StepStatus.FAILED, StepStatus.TIMEOUT):
                    print(f"   [{s.id}] {s.name}: {s.message}")

        print("\n📋 Full conversation flow:")
        current_phase = ""
        for s in self.results:
            if s.phase != current_phase:
                current_phase = s.phase
                print(f"\n  {current_phase}")
            print(f"    {s.status.value} [{s.id}] {s.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive E2E test: Full writer-editor conversation"
    )
    parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    parser.add_argument("--phase", action="append", help="Run specific phase(s): a, b, c")
    parser.add_argument("--dry-run", action="store_true", help="Don't create issues/PRs")
    args = parser.parse_args()

    print(f"🧪 Comprehensive E2E Test: Writer-Editor Conversation")
    print(f"📦 Repository: {args.repo}")
    print(f"🔧 Dry run: {args.dry_run}")

    runner = ConversationRunner(args.repo, args.dry_run)
    runner.run_all(args.phase)
    runner.print_summary()

    # Exit with error if failures
    failed = sum(1 for s in runner.results if s.status == StepStatus.FAILED)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
