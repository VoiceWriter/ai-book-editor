"""Tests for seed data and seeding functionality."""

from pathlib import Path


class TestSeedData:
    """Tests for seed data integrity."""

    def test_seed_file_exists(self):
        """Seed file should exist."""
        seed_file = Path(__file__).parent.parent / "seeds/issues.json"
        assert seed_file.exists(), "seeds/issues.json not found"

    def test_seed_file_valid_json(self, seed_data):
        """Seed file should contain valid JSON."""
        assert "issues" in seed_data
        assert "labels" in seed_data

    def test_seed_issues_have_required_fields(self, seed_data):
        """Each seed issue should have required fields."""
        for issue in seed_data["issues"]:
            assert "title" in issue, f"Issue missing title: {issue}"
            assert "body" in issue, f"Issue missing body: {issue}"
            assert "labels" in issue, f"Issue missing labels: {issue}"

    def test_seed_labels_have_required_fields(self, seed_data):
        """Each seed label should have required fields."""
        for label in seed_data["labels"]:
            assert "name" in label, f"Label missing name: {label}"
            assert "color" in label, f"Label missing color: {label}"

    def test_voice_memo_issues_have_correct_label(self, seed_data):
        """Voice memo issues should have voice_transcription label."""
        voice_memos = [i for i in seed_data["issues"] if "Voice memo:" in i["title"]]
        assert len(voice_memos) > 0, "No voice memo issues found"

        for issue in voice_memos:
            assert (
                "voice_transcription" in issue["labels"]
            ), f"Voice memo missing label: {issue['title']}"

    def test_ai_question_issues_have_correct_label(self, seed_data):
        """AI question issues should have ai-question label."""
        ai_questions = [i for i in seed_data["issues"] if "[AI" in i["title"]]
        assert len(ai_questions) > 0, "No AI question issues found"

        for issue in ai_questions:
            assert "ai-question" in issue["labels"], f"AI question missing label: {issue['title']}"


class TestSeedScript:
    """Tests for seed.py script functionality."""

    def test_load_seeds_function(self):
        """load_seeds should return seed data."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "seeds"))
        from seed import load_seeds

        data = load_seeds()
        assert "issues" in data
        assert "labels" in data

    def test_seed_labels_are_unique(self, seed_data):
        """All label names should be unique."""
        label_names = [lbl["name"] for lbl in seed_data["labels"]]
        assert len(label_names) == len(set(label_names)), "Duplicate label names found"

    def test_label_colors_are_valid_hex(self, seed_data):
        """Label colors should be valid 6-character hex codes."""
        import re

        hex_pattern = re.compile(r"^[0-9A-Fa-f]{6}$")

        for label in seed_data["labels"]:
            assert hex_pattern.match(
                label["color"]
            ), f"Invalid color for {label['name']}: {label['color']}"
