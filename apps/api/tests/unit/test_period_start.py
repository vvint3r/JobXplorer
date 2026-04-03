"""Unit tests for the _period_start helper in application_logs router."""

from datetime import UTC, datetime, timedelta

import pytest

# Import directly from the router module (no DB needed — pure function)
from src.routers.application_logs import _period_start


class TestPeriodStart:
    def test_today_is_midnight(self):
        result = _period_start("today")
        assert result is not None
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_week_is_roughly_7_days_ago(self):
        now = datetime.now(UTC)
        result = _period_start("week")
        assert result is not None
        delta = now - result
        assert 6 <= delta.days <= 7

    def test_month_is_roughly_30_days_ago(self):
        now = datetime.now(UTC)
        result = _period_start("month")
        assert result is not None
        delta = now - result
        assert 29 <= delta.days <= 30

    def test_3mo_is_roughly_90_days_ago(self):
        now = datetime.now(UTC)
        result = _period_start("3mo")
        assert result is not None
        delta = now - result
        assert 89 <= delta.days <= 90

    def test_ytd_is_jan_1_this_year(self):
        result = _period_start("ytd")
        assert result is not None
        assert result.month == 1
        assert result.day == 1
        assert result.year == datetime.now(UTC).year

    def test_all_returns_none(self):
        assert _period_start("all") is None

    def test_unknown_returns_none(self):
        assert _period_start("bogus") is None

    def test_result_is_utc(self):
        for period in ("today", "week", "month", "3mo", "ytd"):
            result = _period_start(period)
            assert result is not None
            assert result.tzinfo is not None
