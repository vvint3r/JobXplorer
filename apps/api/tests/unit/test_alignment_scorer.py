"""Unit tests for pure functions in alignment_scorer.py.

No database, no HTTP — these run entirely in-process.
"""

import pytest

from src.core.job_extraction.alignment_scorer import GRADE_THRESHOLDS, TextMatcher, score_to_grade


# ── score_to_grade ────────────────────────────────────────────────────────────

class TestScoreToGrade:
    def test_perfect_score_is_a_plus(self):
        assert score_to_grade(1.0) == "A+"

    def test_exactly_at_a_plus_threshold(self):
        assert score_to_grade(0.90) == "A+"

    def test_just_below_a_plus_is_a(self):
        assert score_to_grade(0.89) == "A"

    def test_exactly_at_a_threshold(self):
        assert score_to_grade(0.85) == "A"

    def test_a_minus(self):
        assert score_to_grade(0.80) == "A-"

    def test_b_plus(self):
        assert score_to_grade(0.75) == "B+"

    def test_b(self):
        assert score_to_grade(0.70) == "B"

    def test_b_minus(self):
        assert score_to_grade(0.65) == "B-"

    def test_c_plus(self):
        assert score_to_grade(0.55) == "C+"

    def test_c(self):
        assert score_to_grade(0.45) == "C"

    def test_c_minus(self):
        assert score_to_grade(0.35) == "C-"

    def test_d_plus(self):
        assert score_to_grade(0.25) == "D+"

    def test_zero_score_is_d(self):
        assert score_to_grade(0.0) == "D"

    def test_very_low_score_is_d(self):
        assert score_to_grade(0.01) == "D"

    def test_all_thresholds_covered(self):
        """Every threshold boundary should return its declared grade."""
        for threshold, expected_grade in GRADE_THRESHOLDS:
            assert score_to_grade(threshold) == expected_grade, (
                f"score={threshold} expected {expected_grade}"
            )

    def test_monotone_decreasing(self):
        """Higher scores should never produce a worse grade."""
        grades = [score_to_grade(s / 100) for s in range(0, 101)]
        grade_order = ["D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]
        for i in range(len(grades) - 1):
            idx_a = grade_order.index(grades[i])
            idx_b = grade_order.index(grades[i + 1])
            assert idx_b >= idx_a, (
                f"score {i/100:.2f}→{(i+1)/100:.2f} went {grades[i]}→{grades[i+1]} (worse)"
            )


# ── TextMatcher ───────────────────────────────────────────────────────────────

class TestTextMatcher:
    """Tests for TextMatcher.matches()."""

    def setup_method(self):
        self.matcher = TextMatcher()

    def _inp(self, term: str, aliases: list[str] | None = None) -> dict:
        return {"input": term, "aliases": aliases or []}

    def test_direct_match(self):
        assert self.matcher.matches(self._inp("python"), "We use Python for backend work.")

    def test_case_insensitive_match(self):
        assert self.matcher.matches(self._inp("Python"), "we use python daily")

    def test_alias_match(self):
        inp = self._inp("machine learning", aliases=["ML", "deep learning"])
        assert self.matcher.matches(inp, "Experience with ML required")

    def test_no_match(self):
        assert not self.matcher.matches(self._inp("kubernetes"), "We use Docker and AWS")

    def test_empty_text(self):
        assert not self.matcher.matches(self._inp("python"), "")

    def test_empty_term_matches_everything(self):
        """An empty input string is a substring of every non-empty string."""
        assert self.matcher.matches(self._inp(""), "any text")

    def test_alias_case_insensitive(self):
        inp = self._inp("sql", aliases=["PostgreSQL"])
        assert self.matcher.matches(inp, "experience with postgresql preferred")

    def test_partial_word_match(self):
        """'python' should match inside 'pythonista'."""
        assert self.matcher.matches(self._inp("python"), "pythonista developer")

    def test_multiple_aliases_first_wins(self):
        inp = self._inp("react", aliases=["ReactJS", "React.js"])
        assert self.matcher.matches(inp, "built with reactjs")

    def test_no_aliases_no_match(self):
        inp = self._inp("golang")
        assert not self.matcher.matches(inp, "typescript and rust preferred")
