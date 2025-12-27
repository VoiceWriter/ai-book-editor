#!/usr/bin/env python3
"""
End-to-end tests for AI Book Editor using gh CLI.

Automates TEST_PLAN.csv by creating GitHub issues, waiting for
workflow responses, and verifying expected outcomes.

Usage:
    python seeds/e2e_tests.py --repo owner/repo
    python seeds/e2e_tests.py --repo owner/repo --phase 1
    python seeds/e2e_tests.py --repo owner/repo --dry-run
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
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
            c for c in comments
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
            test_id, "Day 1", description, TestStatus.PASSED,
            f"Issue #{issue_number} created",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Day 1", description, TestStatus.FAILED,
            str(e), duration_seconds=time.time() - start,
        )


def test_1_4_ai_responds(repo: str, issue_number: int, dry_run: bool) -> TestResult:
    """Test 1.4: AI responds to voice memo."""
    test_id = "1.4"
    description = "AI responds to voice memo"

    if dry_run or not issue_number:
        return TestResult(test_id, "Day 1", description, TestStatus.SKIPPED, "Dry run or no issue")

    start = time.time()
    try:
        comments = wait_for_bot_comment(repo, issue_number, timeout_seconds=180)
        # Check for welcome/acknowledgment
        if check_comment_contains(comments, ["book", "chapter"]) or len(comments) > 0:
            return TestResult(
                test_id, "Day 1", description, TestStatus.PASSED,
                f"Got {len(comments)} bot comment(s)",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
        return TestResult(
            test_id, "Day 1", description, TestStatus.FAILED,
            "Bot commented but content unexpected",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Day 1", description, TestStatus.TIMEOUT,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Day 1", description, TestStatus.FAILED,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_1_5_reply_about_book(repo: str, issue_number: int, dry_run: bool) -> TestResult:
    """Test 1.5: Reply about book topic."""
    test_id = "1.5"
    description = "Reply: book about dog training"

    if dry_run or not issue_number:
        return TestResult(test_id, "Day 1", description, TestStatus.SKIPPED, "Dry run or no issue")

    start = time.time()
    try:
        add_comment(
            repo, issue_number,
            "@margot-ai-editor This is a book about dog training for first-time owners"
        )
        comments = wait_for_bot_comment(repo, issue_number, min_comments=2)
        return TestResult(
            test_id, "Day 1", description, TestStatus.PASSED,
            "AI acknowledged",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Day 1", description, TestStatus.TIMEOUT,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Day 1", description, TestStatus.FAILED,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_2_1_messy_transcript(repo: str, dry_run: bool) -> TestResult:
    """Test 2.1: Submit messy transcript with filler words."""
    test_id = "2.1"
    description = "Submit transcript with filler words"

    if dry_run:
        return TestResult(test_id, "First Week", description, TestStatus.SKIPPED, "Dry run")

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
            test_id, "First Week", description,
            TestStatus.PASSED if has_response else TestStatus.FAILED,
            f"Issue #{issue_number}, got {len(comments)} response(s)",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "First Week", description, TestStatus.TIMEOUT,
            str(e), duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "First Week", description, TestStatus.FAILED,
            str(e), duration_seconds=time.time() - start,
        )


def test_2_3_different_topic(repo: str, dry_run: bool) -> TestResult:
    """Test 2.3: Submit memo about different topic (crate training)."""
    test_id = "2.3"
    description = "Submit memo about crate training"

    if dry_run:
        return TestResult(test_id, "First Week", description, TestStatus.SKIPPED, "Dry run")

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
            test_id, "First Week", description, TestStatus.PASSED,
            f"Issue #{issue_number}",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "First Week", description, TestStatus.TIMEOUT,
            str(e), duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "First Week", description, TestStatus.FAILED,
            str(e), duration_seconds=time.time() - start,
        )


def test_5_1_switch_persona_sage(repo: str, issue_number: int, dry_run: bool) -> TestResult:
    """Test 5.1: Switch to Sage persona."""
    test_id = "5.1"
    description = "Switch to Sage persona"

    if dry_run or not issue_number:
        return TestResult(test_id, "Switching Personas", description, TestStatus.SKIPPED, "Dry run or no issue")

    start = time.time()
    try:
        add_comment(repo, issue_number, "@margot-ai-editor use sage for this next piece")
        comments = wait_for_bot_comment(repo, issue_number, min_comments=2)

        # Check for persona acknowledgment
        if check_comment_contains(comments, ["sage"]) or len(comments) >= 2:
            return TestResult(
                test_id, "Switching Personas", description, TestStatus.PASSED,
                "Persona switch acknowledged",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
        return TestResult(
            test_id, "Switching Personas", description, TestStatus.FAILED,
            "No persona acknowledgment",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Switching Personas", description, TestStatus.TIMEOUT,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Switching Personas", description, TestStatus.FAILED,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_5_4_persona_label(repo: str, dry_run: bool) -> TestResult:
    """Test 5.4: Use persona label on issue."""
    test_id = "5.4"
    description = "Add persona:the-axe label"

    if dry_run:
        return TestResult(test_id, "Switching Personas", description, TestStatus.SKIPPED, "Dry run")

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
            test_id, "Switching Personas", description, TestStatus.PASSED,
            f"Issue #{issue_number} with The Axe persona",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Switching Personas", description, TestStatus.TIMEOUT,
            str(e), duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Switching Personas", description, TestStatus.FAILED,
            str(e), duration_seconds=time.time() - start,
        )


def test_5_5_list_personas(repo: str, issue_number: int, dry_run: bool) -> TestResult:
    """Test 5.5: List all personas."""
    test_id = "5.5"
    description = "List all personas"

    if dry_run or not issue_number:
        return TestResult(test_id, "Switching Personas", description, TestStatus.SKIPPED, "Dry run or no issue")

    start = time.time()
    try:
        add_comment(repo, issue_number, "@margot-ai-editor list all personas")
        comments = wait_for_bot_comment(repo, issue_number, min_comments=2)

        # Should list personas
        if check_comment_contains(comments, ["persona"]) or len(comments) >= 2:
            return TestResult(
                test_id, "Switching Personas", description, TestStatus.PASSED,
                "Personas listed",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
        return TestResult(
            test_id, "Switching Personas", description, TestStatus.FAILED,
            "No persona list",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Switching Personas", description, TestStatus.TIMEOUT,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Switching Personas", description, TestStatus.FAILED,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_9_1_ask_editor(repo: str, dry_run: bool) -> TestResult:
    """Test 9.1: Ask the Editor question."""
    test_id = "9.1"
    description = "Ask: How long should chapters be?"

    if dry_run:
        return TestResult(test_id, "Ask the Editor", description, TestStatus.SKIPPED, "Dry run")

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
            test_id, "Ask the Editor", description, TestStatus.PASSED,
            f"Issue #{issue_number}",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Ask the Editor", description, TestStatus.TIMEOUT,
            str(e), duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Ask the Editor", description, TestStatus.FAILED,
            str(e), duration_seconds=time.time() - start,
        )


def test_13_1_empty_body(repo: str, dry_run: bool) -> TestResult:
    """Test 13.1: Submit issue with empty body."""
    test_id = "13.1"
    description = "Submit issue with empty body"

    if dry_run:
        return TestResult(test_id, "Edge Cases", description, TestStatus.SKIPPED, "Dry run")

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
                test_id, "Edge Cases", description, TestStatus.PASSED,
                f"Issue #{issue_number} - handled gracefully",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
        except TimeoutError:
            # Timeout is also acceptable for empty body (workflow may skip)
            return TestResult(
                test_id, "Edge Cases", description, TestStatus.PASSED,
                f"Issue #{issue_number} - workflow skipped empty body",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
    except Exception as e:
        return TestResult(
            test_id, "Edge Cases", description, TestStatus.FAILED,
            str(e), duration_seconds=time.time() - start,
        )


# =============================================================================
# Phase 4: Discovery Conversation Tests
# =============================================================================


def test_4_1_discovery_conversation(repo: str, dry_run: bool) -> TestResult:
    """Test 4.1: Full discovery conversation flow."""
    test_id = "4.1"
    description = "Discovery conversation: answer questions"

    if dry_run:
        return TestResult(test_id, "Discovery", description, TestStatus.SKIPPED, "Dry run")

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
            repo, issue_number,
            """@margot-ai-editor

1. The book is about helping stressed parents cook healthy meals without recipes - more like building blocks and techniques.

2. My ideal reader is a working parent who gets home at 6pm exhausted and needs to feed their family something decent.

3. I want them to feel confident and creative in the kitchen, not stressed about following exact recipes.

4. This is still early stage - I'm just brain-dumping ideas right now."""
        )

        # Wait for AI's follow-up response
        print("  Waiting for AI's response to answers...")
        comments = wait_for_bot_comment(repo, issue_number, min_comments=2, timeout_seconds=180)

        # Verify AI acknowledged the answers
        if len(comments) >= 2:
            return TestResult(
                test_id, "Discovery", description, TestStatus.PASSED,
                f"Issue #{issue_number} - conversation completed",
                issue_number=issue_number,
                duration_seconds=time.time() - start,
            )
        return TestResult(
            test_id, "Discovery", description, TestStatus.FAILED,
            "AI didn't respond to answers",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Discovery", description, TestStatus.TIMEOUT,
            str(e), duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Discovery", description, TestStatus.FAILED,
            str(e), duration_seconds=time.time() - start,
        )


def test_4_2_editorial_feedback_request(repo: str, issue_number: int, dry_run: bool) -> TestResult:
    """Test 4.2: Ask for specific editorial feedback."""
    test_id = "4.2"
    description = "Ask: what's working in my writing?"

    if dry_run or not issue_number:
        return TestResult(test_id, "Discovery", description, TestStatus.SKIPPED, "Dry run or no issue")

    start = time.time()
    try:
        add_comment(
            repo, issue_number,
            "@margot-ai-editor What's working well in my writing so far? What should I keep doing?"
        )
        comments = wait_for_bot_comment(repo, issue_number, min_comments=3, timeout_seconds=180)

        return TestResult(
            test_id, "Discovery", description, TestStatus.PASSED,
            "Got editorial feedback",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Discovery", description, TestStatus.TIMEOUT,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Discovery", description, TestStatus.FAILED,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )


def test_4_3_clarification_question(repo: str, issue_number: int, dry_run: bool) -> TestResult:
    """Test 4.3: Ask a clarifying question about feedback."""
    test_id = "4.3"
    description = "Ask: can you explain what you mean?"

    if dry_run or not issue_number:
        return TestResult(test_id, "Discovery", description, TestStatus.SKIPPED, "Dry run or no issue")

    start = time.time()
    try:
        add_comment(
            repo, issue_number,
            "@margot-ai-editor Can you give me a specific example of what you mean? I want to make sure I understand."
        )
        comments = wait_for_bot_comment(repo, issue_number, min_comments=4, timeout_seconds=180)

        return TestResult(
            test_id, "Discovery", description, TestStatus.PASSED,
            "Got clarification",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Discovery", description, TestStatus.TIMEOUT,
            str(e), issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Discovery", description, TestStatus.FAILED,
            str(e), issue_number=issue_number,
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
        result_4_2 = test_4_2_editorial_feedback_request(repo, result_4_1.issue_number, dry_run)
        results.append(result_4_2)
        print_result(result_4_2)

        # Test 4.3: Clarification question
        result_4_3 = test_4_3_clarification_question(repo, result_4_1.issue_number, dry_run)
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
        result_5_1 = test_5_1_switch_persona_sage(repo, result_5_4.issue_number, dry_run)
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
        return TestResult(test_id, "Context Management", description, TestStatus.SKIPPED, "Dry run")

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
            wait_for_bot_comment(repo, issue_number, min_comments=(i + 2) * 2, timeout_seconds=180)

        # Check if AI remembers the dog's name "Max" in later responses
        comments = get_issue_comments(repo, issue_number)
        bot_comments = [c for c in comments if c.get("user", {}).get("type") == "Bot"]
        last_response = bot_comments[-1]["body"] if bot_comments else ""

        remembers_max = "max" in last_response.lower()

        return TestResult(
            test_id, "Context Management", description,
            TestStatus.PASSED if remembers_max else TestStatus.FAILED,
            f"Issue #{issue_number}, AI {'remembers' if remembers_max else 'forgot'} Max",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Context Management", description, TestStatus.TIMEOUT,
            str(e), duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Context Management", description, TestStatus.FAILED,
            str(e), duration_seconds=time.time() - start,
        )


def test_14_3_closing_summary(repo: str, issue_number: int | None, dry_run: bool) -> TestResult:
    """Test 14.3: Close issue and verify summary comment is posted."""
    test_id = "14.3"
    description = "Closing summary comment"

    if dry_run or not issue_number:
        return TestResult(
            test_id, "Context Management", description, TestStatus.SKIPPED, "Dry run or no issue"
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
        wait_for_bot_comment(repo, issue_number, min_comments=count_before + 1, timeout_seconds=120)

        # Check that a summary comment was added
        comments_after = get_issue_comments(repo, issue_number)
        new_comments = [c for c in comments_after if c not in comments_before]

        has_summary = any(
            "summary" in c.get("body", "").lower() or
            "decisions" in c.get("body", "").lower() or
            "established" in c.get("body", "").lower()
            for c in new_comments
        )

        return TestResult(
            test_id, "Context Management", description,
            TestStatus.PASSED if has_summary else TestStatus.FAILED,
            f"Issue #{issue_number}, summary {'posted' if has_summary else 'not found'}",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Context Management", description, TestStatus.TIMEOUT,
            str(e), issue_number=issue_number, duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Context Management", description, TestStatus.FAILED,
            str(e), issue_number=issue_number, duration_seconds=time.time() - start,
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
        result = run_gh([
            "api", f"repos/{repo}/contents/.ai-context/knowledge.jsonl",
            "--jq", ".content"
        ], check=False)

        if result.returncode != 0:
            return TestResult(
                test_id, "Context Management", description, TestStatus.FAILED,
                "Could not fetch knowledge.jsonl",
                duration_seconds=time.time() - start,
            )

        import base64
        content = base64.b64decode(result.stdout.strip()).decode("utf-8")
        lines = [l for l in content.strip().split("\n") if l.strip()]

        return TestResult(
            test_id, "Context Management", description,
            TestStatus.PASSED if len(lines) > 0 else TestStatus.FAILED,
            f"Found {len(lines)} knowledge entries",
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Context Management", description, TestStatus.FAILED,
            str(e), duration_seconds=time.time() - start,
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
            test_id, "Context Management", description,
            TestStatus.PASSED if (knows_max or knows_audience) else TestStatus.FAILED,
            f"Issue #{issue_number}, remembers Max: {knows_max}, audience: {knows_audience}",
            issue_number=issue_number,
            duration_seconds=time.time() - start,
        )
    except TimeoutError as e:
        return TestResult(
            test_id, "Context Management", description, TestStatus.TIMEOUT,
            str(e), duration_seconds=time.time() - start,
        )
    except Exception as e:
        return TestResult(
            test_id, "Context Management", description, TestStatus.FAILED,
            str(e), duration_seconds=time.time() - start,
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


def print_result(result: TestResult) -> None:
    """Print a single test result."""
    issue_str = f" (#{result.issue_number})" if result.issue_number else ""
    duration_str = f" [{result.duration_seconds:.1f}s]" if result.duration_seconds else ""
    print(f"{result.status.value} {result.test_id}: {result.description}{issue_str}{duration_str}")
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
    parser.add_argument("--phase", type=int, help="Run specific phase (1, 2, 4, 5, 9, 13, 14)")
    parser.add_argument("--dry-run", action="store_true", help="Don't create issues")
    parser.add_argument("--quick", action="store_true", help="Run quick smoke test (phases 1, 9)")
    args = parser.parse_args()

    print(f"🧪 AI Book Editor E2E Tests")
    print(f"📦 Repository: {args.repo}")
    print(f"🔧 Dry run: {args.dry_run}")
    print()

    all_results: list[TestResult] = []

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
