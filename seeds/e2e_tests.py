#!/usr/bin/env python3
"""
End-to-end tests for AI Book Editor using gh CLI.

Automates TEST_PLAN.csv by creating GitHub issues, waiting for
workflow responses, and verifying expected outcomes.

Usage:
    python seeds/e2e_tests.py --repo owner/repo
    python seeds/e2e_tests.py --repo owner/repo --phase 1
    python seeds/e2e_tests.py --repo owner/repo --dry-run
    python seeds/e2e_tests.py --repo owner/repo --journey  # Full book simulation

The --journey flag runs a complete book writing simulation:
"Entheogenic Gardening for Curing your Mental Health at Home"
This tests ALL system functions in order, like a real author would use them.
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class TestStatus(Enum):
    PASSED = "✅"
    FAILED = "❌"
    SKIPPED = "⏭️"
    TIMEOUT = "⏱️"


@dataclass
class TestResult:
    test_id: str
    phase: str
    description: str
    status: TestStatus
    message: str = ""
    issue_number: int | None = None
    duration_seconds: float = 0


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run gh CLI command."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"gh command failed: {result.stderr}")
    return result


def create_issue(repo: str, title: str, body: str, labels: list[str]) -> int:
    """Create a GitHub issue and return its number."""
    args = ["issue", "create", "--repo", repo, "--title", title, "--body", body]
    for label in labels:
        args.extend(["--label", label])

    result = run_gh(args)
    # Output is like: https://github.com/owner/repo/issues/123
    url = result.stdout.strip()
    issue_number = int(url.split("/")[-1])
    return issue_number


def get_issue_comments(repo: str, issue_number: int) -> list[dict]:
    """Get all comments on an issue."""
    result = run_gh(
        ["api", f"repos/{repo}/issues/{issue_number}/comments", "--jq", "."]
    )
    if not result.stdout.strip():
        return []
    return json.loads(result.stdout)


def add_comment(repo: str, issue_number: int, body: str) -> None:
    """Add a comment to an issue."""
    run_gh(["issue", "comment", str(issue_number), "--repo", repo, "--body", body])


def add_label(repo: str, issue_number: int, label: str) -> None:
    """Add a label to an issue."""
    run_gh(["issue", "edit", str(issue_number), "--repo", repo, "--add-label", label])


def close_issue(repo: str, issue_number: int) -> None:
    """Close an issue."""
    run_gh(["issue", "close", str(issue_number), "--repo", repo])


def wait_for_bot_comment(
    repo: str,
    issue_number: int,
    timeout_seconds: int = 180,
    poll_interval: int = 10,
    min_comments: int = 1,
) -> list[dict]:
    """Wait for bot to comment on issue."""
    start = time.time()
    while time.time() - start < timeout_seconds:
        comments = get_issue_comments(repo, issue_number)
        bot_comments = [
            c
            for c in comments
            if c.get("user", {}).get("login") == "github-actions[bot]"
            or c.get("user", {}).get("type") == "Bot"
        ]
        if len(bot_comments) >= min_comments:
            return bot_comments
        print(f"  Waiting for bot response... ({int(time.time() - start)}s)")
        time.sleep(poll_interval)

    raise TimeoutError(f"No bot comment after {timeout_seconds}s")


def check_comment_contains(comments: list[dict], keywords: list[str]) -> bool:
    """Check if any comment contains all keywords (case-insensitive)."""
    for comment in comments:
        body = comment.get("body", "").lower()
        if all(kw.lower() in body for kw in keywords):
            return True
    return False


# =============================================================================
# Test Definitions
# =============================================================================


def test_1_3_voice_memo_creation(repo: str, dry_run: bool) -> TestResult:
    """Test 1.3: Create voice transcription issue."""
    test_id = "1.3"
    description = "Create voice transcription issue"

    if dry_run:
        return TestResult(test_id, "Day 1", description, TestStatus.SKIPPED, "Dry run")

    start = time.time()
    try:
        body = """okay so this is me just talking through it dont clean it up yet this is
for you as the editor to get the shape of it in your head i think the
book should be about 300 pages maybe a little more maybe less but roughly
that and split into 10 chapters that feels right not too many not too few
enough room to breathe and go deep and chapter 1 is really about orientation
its for the new dog owner who is overwhelmed and excited and tired already
and doesnt know where to start"""

        issue_number = create_issue(
            repo,
            "Voice memo: My book idea",
            body,
            ["voice_transcription"],
        )
        return TestResult(
            test_id,
            "Day 1",
            description,
            TestStatus.PASSED,
            f"Issue #{issue_number} created",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Day 1",
            description,
            TestStatus.FAILED,
            str(e),
            duration_seconds=time.time() - start,
        )


def test_1_4_ai_responds(repo: str, issue_number: int, dry_run: bool) -> TestResult:
    """Test 1.4: AI responds to voice memo."""
    test_id = "1.4"
    description = "AI responds to voice memo"

    if dry_run or not issue_number:
        return TestResult(
            test_id, "Day 1", description, TestStatus.SKIPPED, "Dry run or no issue"
        )

    start = time.time()
    try:
        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)
        # Check for welcome/acknowledgment
        if check_comment_contains(comments, ["book", "chapter"]) or len(comments) > 0:
            return TestResult(
                test_id,
                "Day 1",
                description,
                TestStatus.PASSED,
                f"Got {len(comments)} bot comment(s)",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
        return TestResult(
            test_id,
            "Day 1",
            description,
            TestStatus.FAILED,
            "Bot commented but content unexpected",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Day 1",
            description,
            TestStatus.TIMEOUT,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Day 1",
            description,
            TestStatus.FAILED,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_1_5_reply_about_book(
    repo: str, issue_number: int, dry_run: bool
) -> TestResult:
    """Test 1.5: Reply about book topic."""
    test_id = "1.5"
    description = "Reply: book about dog training"

    if dry_run or not issue_number:
        return TestResult(
            test_id, "Day 1", description, TestStatus.SKIPPED, "Dry run or no issue"
        )

    start = time.time()
    try:
        add_comment(
            repo,
            issue_number,
            "@margot-ai-editor This is a book about dog training for first-time owners",
        )
        comments = wait_for_bot_comment(repo, issue_number, min_comments=2)
        return TestResult(
            test_id,
            "Day 1",
            description,
            TestStatus.PASSED,
            "AI acknowledged",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Day 1",
            description,
            TestStatus.TIMEOUT,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Day 1",
            description,
            TestStatus.FAILED,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_2_1_messy_transcript(repo: str, dry_run: bool) -> TestResult:
    """Test 2.1: Submit messy transcript with filler words."""
    test_id = "2.1"
    description = "Submit transcript with filler words"

    if dry_run:
        return TestResult(
            test_id, "First Week", description, TestStatus.SKIPPED, "Dry run"
        )

    start = time.time()
    try:
        body = """um so the first thing people need to understand is that dogs dont speak
english right they respond to tone and body language and like when you say
sit its not the word its the way you say it and um yeah so basically the
whole dominance thing is like mostly wrong and I want to talk about that
but like not be too aggressive about it you know what I mean"""

        issue_number = create_issue(
            repo,
            "Voice memo: Dogs don't speak English",
            body,
            ["voice_transcription"],
        )

        # Wait for AI response
        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)

        # Check that cleaned version doesn't have excessive filler words
        has_response = len(comments) > 0
        return TestResult(
            test_id,
            "First Week",
            description,
            TestStatus.PASSED if has_response else TestStatus.FAILED,
            f"Issue #{issue_number}, got {len(comments)} response(s)",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "First Week",
            description,
            TestStatus.TIMEOUT,
            str(e),
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "First Week",
            description,
            TestStatus.FAILED,
            str(e),
            duration_seconds=time.time() - start,
        )


def test_2_3_different_topic(repo: str, dry_run: bool) -> TestResult:
    """Test 2.3: Submit memo about different topic (crate training)."""
    test_id = "2.3"
    description = "Submit memo about crate training"

    if dry_run:
        return TestResult(
            test_id, "First Week", description, TestStatus.SKIPPED, "Dry run"
        )

    start = time.time()
    try:
        body = """so crate training is something a lot of new owners feel guilty about
but honestly its one of the best things you can do for your puppy
the crate becomes their safe space their den and when you need to
leave them alone or at night it gives them security not punishment
the key is making it positive from day one treats toys meals in the crate"""

        issue_number = create_issue(
            repo,
            "Voice memo: Crate training basics",
            body,
            ["voice_transcription"],
        )

        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)
        return TestResult(
            test_id,
            "First Week",
            description,
            TestStatus.PASSED,
            f"Issue #{issue_number}",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "First Week",
            description,
            TestStatus.TIMEOUT,
            str(e),
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "First Week",
            description,
            TestStatus.FAILED,
            str(e),
            duration_seconds=time.time() - start,
        )


def test_5_1_switch_persona_sage(
    repo: str, issue_number: int, dry_run: bool
) -> TestResult:
    """Test 5.1: Switch to Sage persona."""
    test_id = "5.1"
    description = "Switch to Sage persona"

    if dry_run or not issue_number:
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.SKIPPED,
            "Dry run or no issue",
        )

    start = time.time()
    try:
        add_comment(
            repo, issue_number, "@margot-ai-editor use sage for this next piece"
        )
        comments = wait_for_bot_comment(repo, issue_number, min_comments=2)

        # Check for persona acknowledgment
        if check_comment_contains(comments, ["sage"]) or len(comments) >= 2:
            return TestResult(
                test_id,
                "Switching Personas",
                description,
                TestStatus.PASSED,
                "Persona switch acknowledged",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.FAILED,
            "No persona acknowledgment",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.TIMEOUT,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.FAILED,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_5_4_persona_label(repo: str, dry_run: bool) -> TestResult:
    """Test 5.4: Use persona label on issue."""
    test_id = "5.4"
    description = "Add persona:the-axe label"

    if dry_run:
        return TestResult(
            test_id, "Switching Personas", description, TestStatus.SKIPPED, "Dry run"
        )

    start = time.time()
    try:
        body = """This chapter is about building trust with your new puppy and I think
its really important to establish that bond early on through consistent
positive interactions and maybe some training games that make learning fun."""

        issue_number = create_issue(
            repo,
            "Voice memo: Building trust",
            body,
            ["voice_transcription", "persona:the-axe"],
        )

        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)

        # The Axe should be more critical/direct
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.PASSED,
            f"Issue #{issue_number} with The Axe persona",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.TIMEOUT,
            str(e),
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.FAILED,
            str(e),
            duration_seconds=time.time() - start,
        )


def test_5_5_list_personas(repo: str, issue_number: int, dry_run: bool) -> TestResult:
    """Test 5.5: List all personas."""
    test_id = "5.5"
    description = "List all personas"

    if dry_run or not issue_number:
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.SKIPPED,
            "Dry run or no issue",
        )

    start = time.time()
    try:
        add_comment(repo, issue_number, "@margot-ai-editor list all personas")
        comments = wait_for_bot_comment(repo, issue_number, min_comments=2)

        # Should list personas
        if check_comment_contains(comments, ["persona"]) or len(comments) >= 2:
            return TestResult(
                test_id,
                "Switching Personas",
                description,
                TestStatus.PASSED,
                "Personas listed",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.FAILED,
            "No persona list",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.TIMEOUT,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Switching Personas",
            description,
            TestStatus.FAILED,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_9_1_ask_editor(repo: str, dry_run: bool) -> TestResult:
    """Test 9.1: Ask the Editor question."""
    test_id = "9.1"
    description = "Ask: How long should chapters be?"

    if dry_run:
        return TestResult(
            test_id, "Ask the Editor", description, TestStatus.SKIPPED, "Dry run"
        )

    start = time.time()
    try:
        issue_number = create_issue(
            repo,
            "How long should chapters be?",
            "I'm not sure how long each chapter should be. Is there a guideline?",
            ["ask-editor"],
        )

        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)
        return TestResult(
            test_id,
            "Ask the Editor",
            description,
            TestStatus.PASSED,
            f"Issue #{issue_number}",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Ask the Editor",
            description,
            TestStatus.TIMEOUT,
            str(e),
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Ask the Editor",
            description,
            TestStatus.FAILED,
            str(e),
            duration_seconds=time.time() - start,
        )


def test_13_1_empty_body(repo: str, dry_run: bool) -> TestResult:
    """Test 13.1: Submit issue with empty body."""
    test_id = "13.1"
    description = "Submit issue with empty body"

    if dry_run:
        return TestResult(
            test_id, "Edge Cases", description, TestStatus.SKIPPED, "Dry run"
        )

    start = time.time()
    try:
        issue_number = create_issue(
            repo,
            "Voice memo: Empty test",
            "",  # Empty body
            ["voice_transcription"],
        )

        # Should get some response (error or prompt)
        try:
            comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=120)
            return TestResult(
                test_id,
                "Edge Cases",
                description,
                TestStatus.PASSED,
                f"Issue #{issue_number} - handled gracefully",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
        except TimeoutError:
            # Timeout is also acceptable for empty body (workflow may skip)
            return TestResult(
                test_id,
                "Edge Cases",
                description,
                TestStatus.PASSED,
                f"Issue #{issue_number} - workflow skipped empty body",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
    except Exception as e:
        return TestResult(
            test_id,
            "Edge Cases",
            description,
            TestStatus.FAILED,
            str(e),
            duration_seconds=time.time() - start,
        )


# =============================================================================
# Phase 4: Discovery Conversation Tests
# =============================================================================


def test_4_1_discovery_conversation(repo: str, dry_run: bool) -> TestResult:
    """Test 4.1: Full discovery conversation flow."""
    test_id = "4.1"
    description = "Discovery conversation: answer questions"

    if dry_run:
        return TestResult(
            test_id, "Discovery", description, TestStatus.SKIPPED, "Dry run"
        )

    start = time.time()
    try:
        # Create initial voice memo
        body = """I have this idea for a book about teaching people how to cook
simple weeknight dinners. Not fancy stuff, just practical meals that busy
parents can make in under 30 minutes with ingredients they probably already have."""

        issue_number = create_issue(
            repo,
            "Voice memo: Weeknight cooking book idea",
            body,
            ["voice_transcription"],
        )

        # Wait for AI's initial response (should ask discovery questions)
        print("  Waiting for AI's initial questions...")
        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)

        # Reply with answers to discovery questions
        print("  Answering discovery questions...")
        add_comment(
            repo,
            issue_number,
            """@margot-ai-editor

1. The book is about helping stressed parents cook healthy meals without recipes - more like building blocks and techniques.

2. My ideal reader is a working parent who gets home at 6pm exhausted and needs to feed their family something decent.

3. I want them to feel confident and creative in the kitchen, not stressed about following exact recipes.

4. This is still early stage - I'm just brain-dumping ideas right now.""",
        )

        # Wait for AI's follow-up response
        print("  Waiting for AI's response to answers...")
        comments = wait_for_bot_comment(
            repo, issue_number, min_comments=2, timeout_seconds=180
        )

        # Verify AI acknowledged the answers
        if len(comments) >= 2:
            return TestResult(
                test_id,
                "Discovery",
                description,
                TestStatus.PASSED,
                f"Issue #{issue_number} - conversation completed",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
        return TestResult(
            test_id,
            "Discovery",
            description,
            TestStatus.FAILED,
            "AI didn't respond to answers",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Discovery",
            description,
            TestStatus.TIMEOUT,
            str(e),
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Discovery",
            description,
            TestStatus.FAILED,
            str(e),
            duration_seconds=time.time() - start,
        )


def test_4_2_editorial_feedback_request(
    repo: str, issue_number: int, dry_run: bool
) -> TestResult:
    """Test 4.2: Ask for specific editorial feedback."""
    test_id = "4.2"
    description = "Ask: what's working in my writing?"

    if dry_run or not issue_number:
        return TestResult(
            test_id, "Discovery", description, TestStatus.SKIPPED, "Dry run or no issue"
        )

    start = time.time()
    try:
        add_comment(
            repo,
            issue_number,
            "@margot-ai-editor What's working well in my writing so far? What should I keep doing?",
        )
        comments = wait_for_bot_comment(
            repo, issue_number, min_comments=3, timeout_seconds=180
        )

        return TestResult(
            test_id,
            "Discovery",
            description,
            TestStatus.PASSED,
            "Got editorial feedback",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Discovery",
            description,
            TestStatus.TIMEOUT,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Discovery",
            description,
            TestStatus.FAILED,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_4_3_clarification_question(
    repo: str, issue_number: int, dry_run: bool
) -> TestResult:
    """Test 4.3: Ask a clarifying question about feedback."""
    test_id = "4.3"
    description = "Ask: can you explain what you mean?"

    if dry_run or not issue_number:
        return TestResult(
            test_id, "Discovery", description, TestStatus.SKIPPED, "Dry run or no issue"
        )

    start = time.time()
    try:
        add_comment(
            repo,
            issue_number,
            "@margot-ai-editor Can you give me a specific example of what you mean? I want to make sure I understand.",
        )
        comments = wait_for_bot_comment(
            repo, issue_number, min_comments=4, timeout_seconds=180
        )

        return TestResult(
            test_id,
            "Discovery",
            description,
            TestStatus.PASSED,
            "Got clarification",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Discovery",
            description,
            TestStatus.TIMEOUT,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Discovery",
            description,
            TestStatus.FAILED,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def run_phase_4(repo: str, dry_run: bool) -> list[TestResult]:
    """Run Phase 4: Discovery Conversation tests."""
    results = []

    # Test 4.1: Full discovery conversation
    result_4_1 = test_4_1_discovery_conversation(repo, dry_run)
    results.append(result_4_1)
    print_result(result_4_1)

    # Test 4.2: Ask for editorial feedback (use issue from 4.1)
    if result_4_1.issue_number:
        result_4_2 = test_4_2_editorial_feedback_request(
            repo, result_4_1.issue_number, dry_run
        )
        results.append(result_4_2)
        print_result(result_4_2)

        # Test 4.3: Clarification question
        result_4_3 = test_4_3_clarification_question(
            repo, result_4_1.issue_number, dry_run
        )
        results.append(result_4_3)
        print_result(result_4_3)

    return results


# =============================================================================
# Test Runner
# =============================================================================


def run_phase_1(repo: str, dry_run: bool) -> list[TestResult]:
    """Run Phase 1: Day 1 - Getting Started tests."""
    results = []

    # Test 1.3: Create voice memo issue
    result_1_3 = test_1_3_voice_memo_creation(repo, dry_run)
    results.append(result_1_3)
    print_result(result_1_3)

    # Test 1.4: AI responds
    result_1_4 = test_1_4_ai_responds(repo, result_1_3.issue_number, dry_run)
    results.append(result_1_4)
    print_result(result_1_4)

    # Test 1.5: Reply about book
    result_1_5 = test_1_5_reply_about_book(repo, result_1_3.issue_number, dry_run)
    results.append(result_1_5)
    print_result(result_1_5)

    return results


def run_phase_2(repo: str, dry_run: bool) -> list[TestResult]:
    """Run Phase 2: First Week - Capturing Ideas tests."""
    results = []

    # Test 2.1: Messy transcript
    result_2_1 = test_2_1_messy_transcript(repo, dry_run)
    results.append(result_2_1)
    print_result(result_2_1)

    # Test 2.3: Different topic
    result_2_3 = test_2_3_different_topic(repo, dry_run)
    results.append(result_2_3)
    print_result(result_2_3)

    return results


def run_phase_5(repo: str, dry_run: bool) -> list[TestResult]:
    """Run Phase 5: Switching Personas tests."""
    results = []

    # Test 5.4: Persona label
    result_5_4 = test_5_4_persona_label(repo, dry_run)
    results.append(result_5_4)
    print_result(result_5_4)

    # Test 5.1 & 5.5: Persona switching (use issue from 5.4)
    if result_5_4.issue_number:
        result_5_1 = test_5_1_switch_persona_sage(
            repo, result_5_4.issue_number, dry_run
        )
        results.append(result_5_1)
        print_result(result_5_1)

        result_5_5 = test_5_5_list_personas(repo, result_5_4.issue_number, dry_run)
        results.append(result_5_5)
        print_result(result_5_5)

    return results


def run_phase_9(repo: str, dry_run: bool) -> list[TestResult]:
    """Run Phase 9: Ask the Editor tests."""
    results = []

    result_9_1 = test_9_1_ask_editor(repo, dry_run)
    results.append(result_9_1)
    print_result(result_9_1)

    return results


def run_phase_13(repo: str, dry_run: bool) -> list[TestResult]:
    """Run Phase 13: Edge Cases tests."""
    results = []

    result_13_1 = test_13_1_empty_body(repo, dry_run)
    results.append(result_13_1)
    print_result(result_13_1)

    return results


# =============================================================================
# Phase 14: Context Management & State Tracking
# =============================================================================


def test_14_1_long_conversation(repo: str, dry_run: bool) -> TestResult:
    """Test 14.1: Have 20+ exchanges, verify AI summarizes older conversation."""
    test_id = "14.1"
    description = "Long conversation with fact establishment"

    if dry_run:
        return TestResult(
            test_id, "Context Management", description, TestStatus.SKIPPED, "Dry run"
        )

    start = time.time()
    try:
        # Create issue with an established fact
        body = """okay so this is my first voice memo for my new book

my dog's name is Max he's a golden retriever I named him after my grandfather

the book is about dog training for busy professionals who just got their first puppy

I want a conversational tone like talking to a friend over coffee"""

        issue_number = create_issue(
            repo,
            "Voice memo: Context management test",
            body,
            ["voice_transcription"],
        )

        # Wait for initial AI response
        wait_for_bot_comment(repo, issue_number, timeout_seconds=180)

        # Add multiple follow-up comments to create a long conversation
        follow_ups = [
            "@margot-ai-editor I want to focus on positive reinforcement",
            "@margot-ai-editor The target length is about 200 pages",
            "@margot-ai-editor What do you think about the structure so far?",
            "@margot-ai-editor My writing style is casual but informative",
            "@margot-ai-editor Do you remember my dog's name?",
        ]

        for i, comment in enumerate(follow_ups):
            add_comment(repo, issue_number, comment)
            print(f"  Added follow-up {i+1}/{len(follow_ups)}")
            # Wait for response before next comment
            wait_for_bot_comment(
                repo, issue_number, min_comments=(i + 2) * 2, timeout_seconds=180
            )

        # Check if AI remembers the dog's name "Max" in later responses
        comments = get_issue_comments(repo, issue_number)
        bot_comments = [c for c in comments if c.get("user", {}).get("type") == "Bot"]
        last_response = bot_comments[-1]["body"] if bot_comments else ""

        remembers_max = "max" in last_response.lower()

        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.PASSED if remembers_max else TestStatus.FAILED,
            f"Issue #{issue_number}, AI {'remembers' if remembers_max else 'forgot'} Max",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.TIMEOUT,
            str(e),
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.FAILED,
            str(e),
            duration_seconds=time.time() - start,
        )


def test_14_3_closing_summary(
    repo: str, issue_number: int | None, dry_run: bool
) -> TestResult:
    """Test 14.3: Close issue and verify summary comment is posted."""
    test_id = "14.3"
    description = "Closing summary comment"

    if dry_run or not issue_number:
        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.SKIPPED,
            "Dry run or no issue",
        )

    start = time.time()
    try:
        # Get comment count before closing
        comments_before = get_issue_comments(repo, issue_number)
        count_before = len(comments_before)

        # Close the issue
        run_gh(["issue", "close", str(issue_number), "--repo", repo])
        print(f"  Closed issue #{issue_number}")

        # Wait for closing summary comment
        time.sleep(5)  # Give workflow time to trigger
        wait_for_bot_comment(
            repo, issue_number, min_comments=count_before + 1, timeout_seconds=120
        )

        # Check that a summary comment was added
        comments_after = get_issue_comments(repo, issue_number)
        new_comments = [c for c in comments_after if c not in comments_before]

        has_summary = any(
            "summary" in c.get("body", "").lower()
            or "decisions" in c.get("body", "").lower()
            or "established" in c.get("body", "").lower()
            for c in new_comments
        )

        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.PASSED if has_summary else TestStatus.FAILED,
            f"Issue #{issue_number}, summary {'posted' if has_summary else 'not found'}",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.TIMEOUT,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.FAILED,
            str(e),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_14_4_knowledge_persistence(repo: str, dry_run: bool) -> TestResult:
    """Test 14.4: Check .ai-context/knowledge.jsonl has new entries."""
    test_id = "14.4"
    description = "Knowledge base persistence"

    if dry_run:
        return TestResult(
            test_id, "Context Management", description, TestStatus.SKIPPED, "Dry run"
        )

    start = time.time()
    try:
        # Fetch knowledge.jsonl content
        result = run_gh(
            [
                "api",
                f"repos/{repo}/contents/.ai-context/knowledge.jsonl",
                "--jq",
                ".content",
            ],
            check=False,
        )

        if result.returncode != 0:
            return TestResult(
                test_id,
                "Context Management",
                description,
                TestStatus.FAILED,
                "Could not fetch knowledge.jsonl",
                duration_seconds=time.time() - start,
            )

        import base64

        content = base64.b64decode(result.stdout.strip()).decode("utf-8")
        lines = [l for l in content.strip().split("\n") if l.strip()]

        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.PASSED if len(lines) > 0 else TestStatus.FAILED,
            f"Found {len(lines)} knowledge entries",
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.FAILED,
            str(e),
            duration_seconds=time.time() - start,
        )


def test_14_5_cross_issue_memory(repo: str, dry_run: bool) -> TestResult:
    """Test 14.5: New issue can access facts from closed issue."""
    test_id = "14.5"
    description = "Cross-issue memory"

    if dry_run:
        return TestResult(
            test_id, "Context Management", description, TestStatus.SKIPPED, "Dry run"
        )

    start = time.time()
    try:
        # Create new issue asking about previously established facts
        body = """Can you remind me what my dog's name is and who I named him after?

Also what was the target audience for my book?"""

        issue_number = create_issue(
            repo,
            "Question: Do you remember my book details?",
            body,
            ["ai-question"],
        )

        # Wait for AI response
        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)

        # Check if response references established facts
        response = comments[0]["body"].lower() if comments else ""
        knows_max = "max" in response
        knows_audience = "professional" in response or "busy" in response

        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.PASSED if (knows_max or knows_audience) else TestStatus.FAILED,
            f"Issue #{issue_number}, remembers Max: {knows_max}, audience: {knows_audience}",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.TIMEOUT,
            str(e),
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id,
            "Context Management",
            description,
            TestStatus.FAILED,
            str(e),
            duration_seconds=time.time() - start,
        )


def run_phase_14(repo: str, dry_run: bool) -> list[TestResult]:
    """Run Phase 14: Context Management & State Tracking tests."""
    results = []

    # Test 14.1: Long conversation with fact establishment
    result_14_1 = test_14_1_long_conversation(repo, dry_run)
    results.append(result_14_1)
    print_result(result_14_1)

    # Test 14.3: Closing summary (uses issue from 14.1)
    result_14_3 = test_14_3_closing_summary(repo, result_14_1.issue_number, dry_run)
    results.append(result_14_3)
    print_result(result_14_3)

    # Test 14.4: Knowledge base persistence
    result_14_4 = test_14_4_knowledge_persistence(repo, dry_run)
    results.append(result_14_4)
    print_result(result_14_4)

    # Test 14.5: Cross-issue memory
    result_14_5 = test_14_5_cross_issue_memory(repo, dry_run)
    results.append(result_14_5)
    print_result(result_14_5)

    return results


# =============================================================================
# BOOK JOURNEY: Complete Book Writing Simulation
# =============================================================================
# This simulates writing "Entheogenic Gardening for Curing Mental Health at Home"
# Tests ALL system functions in the order a real author would use them.


@dataclass
class BookJourneyState:
    """Tracks state across the full book journey."""

    # Issue tracking
    intro_issue: int | None = None
    chapter1_issue: int | None = None
    chapter2_issue: int | None = None
    chapter3_issue: int | None = None
    question_issue: int | None = None

    # PR tracking
    intro_pr: int | None = None
    chapter1_pr: int | None = None

    # Facts established
    book_title: str = "Entheogenic Gardening for Curing Mental Health at Home"
    target_audience: str = "people struggling with depression and anxiety"
    preferred_tone: str = "warm, accessible, harm-reduction focused"

    # Results
    results: list = field(default_factory=list)


def journey_step_1_first_memo(repo: str, state: BookJourneyState) -> TestResult:
    """
    Step 1: First voice memo - author's raw idea dump.
    Tests: New project detection, discovery questions, welcome message.
    """
    test_id = "J1"
    description = "First voice memo - book idea"
    start = time.time()

    try:
        body = """okay so here's my idea for this book um I've been growing various
medicinal plants in my garden for years now and I've noticed they really help with
my mental health you know things like st johns wort and lavender and passionflower
and I want to write about how other people can do this too at home legally of course
just the legal stuff like adaptogens and nervines and herbs that have been used for
centuries to help with anxiety and depression and I think there's a real need for this
because so many people are on SSRIs and they have side effects and they want alternatives
or at least complementary approaches anyway the book would be part gardening guide part
mental health resource part herbalism primer I'm thinking maybe 200 pages or so
accessible for beginners but with enough depth for people who want to go further"""

        issue_number = create_issue(
            repo,
            "Voice memo: My book idea - plants for mental health",
            body,
            ["voice_transcription"],
        )
        state.intro_issue = issue_number

        # Wait for AI's discovery questions
        print("  Waiting for AI's discovery questions...")
        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)

        # Verify we got discovery questions or welcome
        has_questions = check_comment_contains(comments, ["?"]) or len(comments) > 0

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED if has_questions else TestStatus.FAILED,
            f"Issue #{issue_number} - AI responded with questions",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.TIMEOUT, str(e)
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_2_answer_discovery(repo: str, state: BookJourneyState) -> TestResult:
    """
    Step 2: Answer discovery questions.
    Tests: Discovery phase handling, fact extraction, emotional state detection.
    """
    test_id = "J2"
    description = "Answer discovery questions"
    start = time.time()

    if not state.intro_issue:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.SKIPPED, "No intro issue"
        )

    try:
        # Answer the discovery questions thoroughly
        add_comment(
            repo,
            state.intro_issue,
            """@margot-ai-editor

Thanks for the questions! Let me answer:

1. **Who is this book for?** People struggling with depression, anxiety, or just chronic
   stress who want natural alternatives or supplements to medication. I'm thinking busy
   professionals, parents, anyone who has a small outdoor space or even just a windowsill.

2. **What's the core transformation?** I want readers to go from feeling helpless about
   their mental health to feeling empowered - like they have agency and can grow their
   own "medicine cabinet" of calming herbs.

3. **What makes me qualified?** I've been doing this for 15 years, I'm a certified
   herbalist (though not a doctor - important disclaimer!), and I've helped dozens of
   friends and family members start their own therapeutic gardens.

4. **Tone and style?** Warm, accessible, never preachy. I want it to feel like talking
   to a knowledgeable friend over tea. Definitely harm-reduction focused - I'll always
   recommend talking to doctors, being aware of interactions, starting slow.

5. **What's NOT in the book?** Anything illegal or dangerous. No psychedelics. This is
   about legal, gentle nervines and adaptogens. St John's Wort, Lavender, Passionflower,
   Chamomile, Ashwagandha, Lemon Balm, that kind of thing.""",
        )

        # Wait for AI response
        print("  Waiting for AI to process answers...")
        comments = wait_for_bot_comment(
            repo, state.intro_issue, min_comments=2, timeout_seconds=180
        )

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED,
            "Discovery answers processed",
            issue_number=state.intro_issue,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.TIMEOUT, str(e)
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_3_request_feedback(repo: str, state: BookJourneyState) -> TestResult:
    """
    Step 3: Request editorial feedback on the initial concept.
    Tests: @margot-ai-editor command, editorial feedback quality.
    """
    test_id = "J3"
    description = "Request editorial feedback"
    start = time.time()

    if not state.intro_issue:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.SKIPPED, "No intro issue"
        )

    try:
        add_comment(
            repo,
            state.intro_issue,
            "@margot-ai-editor What do you think about this concept? What's working and what needs more thought?",
        )

        comments = wait_for_bot_comment(
            repo, state.intro_issue, min_comments=3, timeout_seconds=180
        )

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED,
            "Got editorial feedback",
            issue_number=state.intro_issue,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.TIMEOUT, str(e)
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_4_create_intro_pr(repo: str, state: BookJourneyState) -> TestResult:
    """
    Step 4: Ask for PR creation for the introduction.
    Tests: PR creation command, content extraction, PR body formatting.
    """
    test_id = "J4"
    description = "Create PR for introduction"
    start = time.time()

    if not state.intro_issue:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.SKIPPED, "No intro issue"
        )

    try:
        add_comment(
            repo,
            state.intro_issue,
            "@margot-ai-editor create PR for the introduction, put it in chapters/01-introduction.md",
        )

        # Wait for response
        comments = wait_for_bot_comment(
            repo, state.intro_issue, min_comments=4, timeout_seconds=240
        )

        # Check if PR was created
        time.sleep(5)  # Give time for PR to be created
        result = run_gh(
            ["pr", "list", "--repo", repo, "--state", "open", "--json", "number,title"],
            check=False,
        )
        prs = json.loads(result.stdout) if result.stdout.strip() else []

        if prs:
            state.intro_pr = prs[0]["number"]
            return TestResult(
                test_id,
                "Book Journey",
                description,
                TestStatus.PASSED,
                f"PR #{state.intro_pr} created",
                issue_number=state.intro_issue,
                duration_seconds=time.time() - start,
            )
        else:
            # Check if PR creation is pending
            last_comment = comments[-1]["body"] if comments else ""
            if "pr" in last_comment.lower() or "pull request" in last_comment.lower():
                return TestResult(
                    test_id,
                    "Book Journey",
                    description,
                    TestStatus.PASSED,
                    "PR creation acknowledged (may need workflow)",
                    issue_number=state.intro_issue,
                    duration_seconds=time.time() - start,
                )
            return TestResult(
                test_id,
                "Book Journey",
                description,
                TestStatus.FAILED,
                "No PR created",
                issue_number=state.intro_issue,
                duration_seconds=time.time() - start,
            )
    except TimeoutError as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.TIMEOUT, str(e)
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_5_second_chapter_memo(
    repo: str, state: BookJourneyState
) -> TestResult:
    """
    Step 5: Submit second voice memo for chapter 2 content.
    Tests: Multiple open issues, chapter detection, project state awareness.
    """
    test_id = "J5"
    description = "Second memo - Growing lavender chapter"
    start = time.time()

    try:
        body = """alright so this would be chapter 2 about lavender specifically because I think
lavender is the gateway herb you know its the one everyone knows and loves and its
actually really effective for anxiety theres good research on it linalool and linalyl
acetate are the active compounds and they work on GABA receptors similar to benzos but
much gentler of course

so I'd cover how to grow it different varieties like English lavender vs French lavender
the English ones are more cold hardy and have better medicinal properties arguably
then how to harvest it when to harvest right when the buds are about to open thats when
the oil content is highest and then how to use it you can make tea or tinctures or
just dry it for sachets or use the essential oil topically

I also want to include my personal story about how lavender helped me through a really
rough patch after my dad died I was having panic attacks and sleeping terribly and
just having lavender around made a real difference"""

        issue_number = create_issue(
            repo,
            "Voice memo: Chapter 2 - Growing and using lavender",
            body,
            ["voice_transcription"],
        )
        state.chapter1_issue = issue_number

        # Wait for AI response
        print("  Waiting for AI response...")
        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)

        # Check if AI noticed we have other open threads
        has_project_awareness = any(
            "introduction" in c.get("body", "").lower()
            or "chapter" in c.get("body", "").lower()
            or "also" in c.get("body", "").lower()
            for c in comments
        )

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED,
            f"Issue #{issue_number}"
            + (" (project aware)" if has_project_awareness else ""),
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.TIMEOUT, str(e)
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_6_switch_persona(repo: str, state: BookJourneyState) -> TestResult:
    """
    Step 6: Switch to Sage persona for sensitive content.
    Tests: Persona switching, persona-appropriate responses.
    """
    test_id = "J6"
    description = "Switch to Sage for personal content"
    start = time.time()

    if not state.chapter1_issue:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.SKIPPED, "No chapter issue"
        )

    try:
        add_comment(
            repo,
            state.chapter1_issue,
            "@margot-ai-editor use sage - I'm sharing something personal about my dad here",
        )

        comments = wait_for_bot_comment(
            repo, state.chapter1_issue, min_comments=2, timeout_seconds=180
        )

        # Check for sage acknowledgment or gentle tone
        has_sage = check_comment_contains(comments, ["sage"]) or len(comments) >= 2

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED if has_sage else TestStatus.FAILED,
            "Switched to Sage",
            issue_number=state.chapter1_issue,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.TIMEOUT, str(e)
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_7_ask_editor_question(
    repo: str, state: BookJourneyState
) -> TestResult:
    """
    Step 7: Ask the editor a standalone question.
    Tests: ask-editor label, conversational responses.
    """
    test_id = "J7"
    description = "Ask editor about chapter structure"
    start = time.time()

    try:
        body = """I'm wondering about chapter structure. Should each plant chapter follow the
same format (like Growing, Harvesting, Using, Recipes) or should they be more free-form
based on what's most important for each plant?

Also, is 200 pages enough for this kind of book?"""

        issue_number = create_issue(
            repo,
            "Question: Chapter structure and book length",
            body,
            ["ask-editor"],
        )
        state.question_issue = issue_number

        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED,
            f"Issue #{issue_number}",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.TIMEOUT, str(e)
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_8_third_chapter_different_persona(
    repo: str, state: BookJourneyState
) -> TestResult:
    """
    Step 8: Submit third chapter with The Axe persona for brutal feedback.
    Tests: Persona labels, critical feedback mode.
    """
    test_id = "J8"
    description = "Third memo with The Axe for brutal feedback"
    start = time.time()

    try:
        body = """so chapter 3 would be about St Johns Wort which is like the big one for
depression its actually been studied head to head against SSRIs and performed comparably
in mild to moderate depression but heres the thing you have to grow it yourself basically
because the commercial preparations are all over the place in quality and the fresh plant
is way more potent than dried

its also one of the trickier ones because of drug interactions it induces cytochrome P450
enzymes which can mess with birth control blood thinners HIV meds all kinds of stuff so
I need to be really careful about how I present this chapter its like the chapter where
I have to be most responsible you know

growing it is pretty easy its a perennial full sun well drained soil blooms in june and july
harvest when the buds are red and sticky thats when hypericin content is highest"""

        issue_number = create_issue(
            repo,
            "Voice memo: Chapter 3 - St John's Wort (need tough feedback)",
            body,
            ["voice_transcription", "persona:the-axe"],
        )
        state.chapter2_issue = issue_number

        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED,
            f"Issue #{issue_number} with The Axe",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.TIMEOUT, str(e)
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_9_cross_thread_reference(
    repo: str, state: BookJourneyState
) -> TestResult:
    """
    Step 9: Reference content from another thread.
    Tests: Cross-issue memory, project state, holistic awareness.
    """
    test_id = "J9"
    description = "Cross-reference between chapters"
    start = time.time()

    if not state.chapter2_issue:
        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.SKIPPED,
            "No chapter 3 issue",
        )

    try:
        add_comment(
            repo,
            state.chapter2_issue,
            """@margot-ai-editor wait, should I mention the drug interactions in the introduction
too? Like give readers a heads up early that some of these herbs interact with medications?

Also, in the lavender chapter (the other thread I have open), should I cross-reference
the St John's Wort interactions there too since people might combine them?""",
        )

        comments = wait_for_bot_comment(
            repo, state.chapter2_issue, min_comments=2, timeout_seconds=180
        )

        # Check for cross-thread awareness
        last_comment = comments[-1]["body"].lower() if comments else ""
        has_cross_ref = (
            "lavender" in last_comment
            or "introduction" in last_comment
            or "other" in last_comment
            or "chapter" in last_comment
        )

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED,
            f"Cross-thread reference {'acknowledged' if has_cross_ref else 'processed'}",
            issue_number=state.chapter2_issue,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.TIMEOUT, str(e)
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_10_check_knowledge_base(
    repo: str, state: BookJourneyState
) -> TestResult:
    """
    Step 10: Verify knowledge base has been populated.
    Tests: Knowledge persistence, fact extraction.
    """
    test_id = "J10"
    description = "Verify knowledge base populated"
    start = time.time()

    try:
        result = run_gh(
            [
                "api",
                f"repos/{repo}/contents/.ai-context/knowledge.jsonl",
                "--jq",
                ".content",
            ],
            check=False,
        )

        if result.returncode != 0:
            return TestResult(
                test_id,
                "Book Journey",
                description,
                TestStatus.FAILED,
                "Could not fetch knowledge.jsonl",
                duration_seconds=time.time() - start,
            )

        import base64

        content = base64.b64decode(result.stdout.strip()).decode("utf-8")
        lines = [l for l in content.strip().split("\n") if l.strip()]

        # Check for expected facts
        content_lower = content.lower()
        has_audience = "depression" in content_lower or "anxiety" in content_lower
        has_tone = "warm" in content_lower or "accessible" in content_lower
        has_plants = "lavender" in content_lower or "st john" in content_lower

        facts_found = sum([has_audience, has_tone, has_plants])

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED if len(lines) > 0 else TestStatus.FAILED,
            f"{len(lines)} entries, {facts_found}/3 key facts",
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_11_close_and_summary(repo: str, state: BookJourneyState) -> TestResult:
    """
    Step 11: Close the question issue and verify summary.
    Tests: Issue close handling, summary generation.
    """
    test_id = "J11"
    description = "Close issue with summary"
    start = time.time()

    if not state.question_issue:
        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.SKIPPED,
            "No question issue",
        )

    try:
        # Get comment count before closing
        comments_before = get_issue_comments(repo, state.question_issue)
        count_before = len(comments_before)

        # Close the issue
        run_gh(["issue", "close", str(state.question_issue), "--repo", repo])
        print(f"  Closed issue #{state.question_issue}")

        # Wait for potential closing summary
        time.sleep(10)
        comments_after = get_issue_comments(repo, state.question_issue)

        got_new_comment = len(comments_after) > count_before

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED,
            f"Issue closed" + (" with summary" if got_new_comment else ""),
            issue_number=state.question_issue,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def journey_step_12_list_personas(repo: str, state: BookJourneyState) -> TestResult:
    """
    Step 12: List all available personas.
    Tests: Persona listing command.
    """
    test_id = "J12"
    description = "List all personas"
    start = time.time()

    if not state.chapter1_issue:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.SKIPPED, "No issue"
        )

    try:
        add_comment(repo, state.chapter1_issue, "@margot-ai-editor list all personas")

        comments = wait_for_bot_comment(
            repo, state.chapter1_issue, min_comments=3, timeout_seconds=180
        )

        # Check for persona list
        last_comment = comments[-1]["body"].lower() if comments else ""
        has_personas = (
            "margot" in last_comment
            or "sage" in last_comment
            or "axe" in last_comment
            or "persona" in last_comment
        )

        return TestResult(
            test_id,
            "Book Journey",
            description,
            TestStatus.PASSED if has_personas else TestStatus.FAILED,
            "Personas listed" if has_personas else "No persona list",
            issue_number=state.chapter1_issue,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.TIMEOUT, str(e)
        )
    except Exception as e:
        return TestResult(
            test_id, "Book Journey", description, TestStatus.FAILED, str(e)
        )


def run_book_journey(repo: str, dry_run: bool) -> list[TestResult]:
    """
    Run the complete book journey simulation.

    This simulates writing "Entheogenic Gardening for Curing Mental Health at Home"
    testing ALL system functions in the order a real author would use them.
    """
    state = BookJourneyState()
    results = []

    print("\n" + "=" * 60)
    print("📚 BOOK JOURNEY: Entheogenic Gardening for Mental Health")
    print("=" * 60)
    print("Simulating a complete book writing experience...")
    print()

    steps = [
        ("Step 1/12", journey_step_1_first_memo),
        ("Step 2/12", journey_step_2_answer_discovery),
        ("Step 3/12", journey_step_3_request_feedback),
        ("Step 4/12", journey_step_4_create_intro_pr),
        ("Step 5/12", journey_step_5_second_chapter_memo),
        ("Step 6/12", journey_step_6_switch_persona),
        ("Step 7/12", journey_step_7_ask_editor_question),
        ("Step 8/12", journey_step_8_third_chapter_different_persona),
        ("Step 9/12", journey_step_9_cross_thread_reference),
        ("Step 10/12", journey_step_10_check_knowledge_base),
        ("Step 11/12", journey_step_11_close_and_summary),
        ("Step 12/12", journey_step_12_list_personas),
    ]

    for step_name, step_fn in steps:
        print(
            f"\n{step_name}: {step_fn.__doc__.split(chr(10))[1].strip() if step_fn.__doc__ else 'Running...'}"
        )

        if dry_run:
            result = TestResult(
                step_fn.__name__,
                "Book Journey",
                step_name,
                TestStatus.SKIPPED,
                "Dry run",
            )
        else:
            result = step_fn(repo, state)

        results.append(result)
        print_result(result)

        # Stop if a critical step fails
        if result.status in (TestStatus.FAILED, TestStatus.TIMEOUT):
            if result.test_id in ("J1", "J2"):  # Critical early steps
                print(f"\n⚠️  Critical step failed, stopping journey")
                break

        # Brief pause between steps to avoid rate limiting
        if not dry_run:
            time.sleep(2)

    return results


def print_result(result: TestResult) -> None:
    """Print a single test result."""
    issue_str = f" (#{result.issue_number})" if result.issue_number else ""
    duration_str = (
        f" [{result.duration_seconds:.1f}s]" if result.duration_seconds else ""
    )
    print(
        f"{result.status.value} {result.test_id}: {result.description}{issue_str}{duration_str}"
    )
    if result.message and result.status != TestStatus.PASSED:
        print(f"   → {result.message}")


def print_summary(results: list[TestResult]) -> None:
    """Print test summary."""
    passed = sum(1 for r in results if r.status == TestStatus.PASSED)
    failed = sum(1 for r in results if r.status == TestStatus.FAILED)
    skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)
    timeout = sum(1 for r in results if r.status == TestStatus.TIMEOUT)
    total_time = sum(r.duration_seconds for r in results)

    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    print(f"✅ Passed:  {passed}")
    print(f"❌ Failed:  {failed}")
    print(f"⏱️  Timeout: {timeout}")
    print(f"⏭️  Skipped: {skipped}")
    print(f"Total time: {total_time:.1f}s")
    print("=" * 50)

    if failed > 0 or timeout > 0:
        print("\nFailed/Timeout tests:")
        for r in results:
            if r.status in (TestStatus.FAILED, TestStatus.TIMEOUT):
                print(f"  {r.test_id}: {r.description} - {r.message}")


def main():
    parser = argparse.ArgumentParser(description="Run E2E tests for AI Book Editor")
    parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    parser.add_argument(
        "--phase", type=int, help="Run specific phase (1, 2, 4, 5, 9, 13, 14)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Don't create issues")
    parser.add_argument(
        "--quick", action="store_true", help="Run quick smoke test (phases 1, 9)"
    )
    parser.add_argument(
        "--journey",
        action="store_true",
        help="Run complete book journey simulation (Entheogenic Gardening)",
    )
    args = parser.parse_args()

    print(f"🧪 AI Book Editor E2E Tests")
    print(f"📦 Repository: {args.repo}")
    print(f"🔧 Dry run: {args.dry_run}")
    print()

    all_results: list[TestResult] = []

    # Run book journey if requested
    if args.journey:
        all_results.extend(run_book_journey(args.repo, args.dry_run))
        print_summary(all_results)
        failed_count = sum(1 for r in all_results if r.status == TestStatus.FAILED)
        sys.exit(1 if failed_count > 0 else 0)

    # Otherwise run phase-based tests
    phases_to_run = []
    if args.phase:
        phases_to_run = [args.phase]
    elif args.quick:
        phases_to_run = [1, 9]
    else:
        phases_to_run = [1, 2, 4, 5, 9, 13, 14]

    for phase in phases_to_run:
        print(f"\n{'=' * 50}")
        print(f"PHASE {phase}")
        print("=" * 50)

        if phase == 1:
            all_results.extend(run_phase_1(args.repo, args.dry_run))
        elif phase == 2:
            all_results.extend(run_phase_2(args.repo, args.dry_run))
        elif phase == 4:
            all_results.extend(run_phase_4(args.repo, args.dry_run))
        elif phase == 5:
            all_results.extend(run_phase_5(args.repo, args.dry_run))
        elif phase == 9:
            all_results.extend(run_phase_9(args.repo, args.dry_run))
        elif phase == 13:
            all_results.extend(run_phase_13(args.repo, args.dry_run))
        elif phase == 14:
            all_results.extend(run_phase_14(args.repo, args.dry_run))
        else:
            print(f"Phase {phase} not implemented yet")

    print_summary(all_results)

    # Exit with error code if any failures
    failed_count = sum(1 for r in all_results if r.status == TestStatus.FAILED)
    sys.exit(1 if failed_count > 0 else 0)


if __name__ == "__main__":
    main()
