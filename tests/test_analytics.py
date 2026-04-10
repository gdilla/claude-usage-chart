"""Tests for claude_usage_analytics."""

from claude_usage_analytics import (
    resolve_model_name,
    get_record_cost,
    API_PRICING,
)
from claude_usage_analytics import compute_burn_rate
from tests.conftest import make_record


class TestModelMatching:
    def test_opus_full_name(self):
        assert resolve_model_name("claude-opus-4-6") == "opus"

    def test_opus_with_date(self):
        assert resolve_model_name("claude-opus-4-6-20250514") == "opus"

    def test_sonnet(self):
        assert resolve_model_name("claude-sonnet-4-6") == "sonnet"

    def test_haiku(self):
        assert resolve_model_name("claude-haiku-4-5-20251001") == "haiku"

    def test_synthetic(self):
        assert resolve_model_name("<synthetic>") == "unknown"

    def test_empty(self):
        assert resolve_model_name("") == "unknown"

    def test_unknown_model(self):
        assert resolve_model_name("claude-future-99") == "unknown"


class TestRecordCost:
    def test_sonnet_cost(self):
        rec = make_record(
            model="claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_creation=0,
            cache_read=0,
        )
        cost = get_record_cost(rec)
        # Sonnet: $3/1M input + $15/1M output = $18
        assert abs(cost - 18.0) < 0.01

    def test_opus_cost(self):
        rec = make_record(
            model="claude-opus-4-6",
            input_tokens=1_000_000,
            output_tokens=0,
            cache_creation=0,
            cache_read=0,
        )
        cost = get_record_cost(rec)
        # Opus: $15/1M input
        assert abs(cost - 15.0) < 0.01

    def test_cache_cost(self):
        rec = make_record(
            model="claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
            cache_creation=1_000_000,
            cache_read=1_000_000,
        )
        cost = get_record_cost(rec)
        # Sonnet cache: $3.75/1M write + $0.30/1M read = $4.05
        assert abs(cost - 4.05) < 0.01

    def test_synthetic_zero_cost(self):
        rec = make_record(model="<synthetic>", input_tokens=1_000_000, output_tokens=1_000_000)
        cost = get_record_cost(rec)
        assert cost == 0.0


class TestBurnRate:
    def test_daily_avg(self, sample_records):
        stats = compute_burn_rate(sample_records, metric="output", days=14)
        assert stats["daily_avg"] > 0
        assert stats["total"] == sum(
            r["output_tokens"] for r in sample_records
        )

    def test_weekday_higher_than_weekend(self, sample_records):
        stats = compute_burn_rate(sample_records, metric="output", days=14)
        assert stats["weekday_avg"] > stats["weekend_avg"]

    def test_weekly_avg(self, sample_records):
        stats = compute_burn_rate(sample_records, metric="output", days=14)
        assert abs(stats["weekly_avg"] - stats["daily_avg"] * 7) < 1

    def test_trend(self, sample_records):
        stats = compute_burn_rate(sample_records, metric="output", days=14)
        # Fixture increases tokens each day (day_offset * 50 on output)
        assert stats["trend_pct"] > 0

    def test_total_metric(self, sample_records):
        stats = compute_burn_rate(sample_records, metric="total", days=14)
        expected = sum(
            r["input_tokens"] + r["output_tokens"] for r in sample_records
        )
        assert stats["total"] == expected

    def test_empty(self, empty_records):
        stats = compute_burn_rate(empty_records, metric="output", days=14)
        assert stats["total"] == 0
        assert stats["daily_avg"] == 0


from claude_usage_analytics import compute_session_stats, compute_hourly_breakdown


class TestSessionStats:
    def test_session_count(self, sample_records):
        stats = compute_session_stats(sample_records, metric="output", days=14)
        # Fixture: 10 weekdays * 5 sessions + 4 weekend days * 2 sessions = 58
        assert stats["count"] == 58

    def test_avg_tokens(self, sample_records):
        stats = compute_session_stats(sample_records, metric="output", days=14)
        assert stats["avg"] > 0
        total = sum(r["output_tokens"] for r in sample_records)
        assert abs(stats["avg"] * stats["count"] - total) < 1

    def test_largest_session(self, sample_records):
        stats = compute_session_stats(sample_records, metric="output", days=14)
        assert stats["largest_tokens"] > 0
        assert isinstance(stats["largest_project"], str)

    def test_sessions_per_day(self, sample_records):
        stats = compute_session_stats(sample_records, metric="output", days=14)
        assert abs(stats["sessions_per_day"] - 58 / 14) < 0.1

    def test_empty(self, empty_records):
        stats = compute_session_stats(empty_records, metric="output", days=14)
        assert stats["count"] == 0
        assert stats["avg"] == 0


class TestHourlyBreakdown:
    def test_peak_window(self, sample_records):
        stats = compute_hourly_breakdown(sample_records, metric="output")
        assert 0 <= stats["peak_window_start"] < 24
        assert 0 < stats["peak_window_pct"] <= 100

    def test_hour_totals(self, sample_records):
        stats = compute_hourly_breakdown(sample_records, metric="output")
        assert stats["hour_totals"].get(9, 0) > 0
        assert stats["hour_totals"].get(3, 0) == 0

    def test_weekday_weekend_split(self, sample_records):
        stats = compute_hourly_breakdown(sample_records, metric="output")
        weekday_total = sum(stats["weekday_hours"].values())
        weekend_total = sum(stats["weekend_hours"].values())
        assert weekday_total > weekend_total

    def test_empty(self, empty_records):
        stats = compute_hourly_breakdown(empty_records, metric="output")
        assert stats["peak_window_pct"] == 0


import pytest
from claude_usage_analytics import (
    compute_model_mix,
    compute_project_rankings,
    compute_api_cost,
)


class TestModelMix:
    def test_three_models(self, sample_records):
        stats = compute_model_mix(sample_records)
        names = [m["name"] for m in stats["models"]]
        assert "opus" in names
        assert "sonnet" in names
        assert "haiku" in names

    def test_percentages_sum_100(self, sample_records):
        stats = compute_model_mix(sample_records)
        total_pct = sum(m["pct"] for m in stats["models"])
        assert abs(total_pct - 100.0) < 0.5

    def test_cost_positive(self, sample_records):
        stats = compute_model_mix(sample_records)
        for m in stats["models"]:
            assert m["est_cost"] >= 0

    def test_empty(self, empty_records):
        stats = compute_model_mix(empty_records)
        assert stats["models"] == []


class TestProjectRankings:
    def test_top_n(self, sample_records):
        rankings = compute_project_rankings(
            sample_records, metric="output", top_n=2
        )
        assert len(rankings) <= 2

    def test_has_fields(self, sample_records):
        rankings = compute_project_rankings(
            sample_records, metric="output", top_n=5
        )
        for r in rankings:
            assert "name" in r
            assert "total_tokens" in r
            assert "session_count" in r
            assert "primary_model" in r
            assert "est_cost" in r

    def test_sorted_descending(self, sample_records):
        rankings = compute_project_rankings(
            sample_records, metric="output", top_n=5
        )
        totals = [r["total_tokens"] for r in rankings]
        assert totals == sorted(totals, reverse=True)


class TestApiCost:
    def test_total_positive(self, sample_records):
        stats = compute_api_cost(sample_records, days=14)
        assert stats["total"] > 0

    def test_per_day(self, sample_records):
        stats = compute_api_cost(sample_records, days=14)
        assert abs(stats["per_day_avg"] - stats["total"] / 14) < 0.01

    def test_by_project(self, sample_records):
        stats = compute_api_cost(sample_records, days=14)
        assert sum(stats["by_project"].values()) == pytest.approx(
            stats["total"], abs=0.01
        )

    def test_by_model(self, sample_records):
        stats = compute_api_cost(sample_records, days=14)
        assert sum(stats["by_model"].values()) == pytest.approx(
            stats["total"], abs=0.01
        )

    def test_empty(self, empty_records):
        stats = compute_api_cost(empty_records, days=14)
        assert stats["total"] == 0.0


from claude_usage_analytics import compute_all


class TestComputeAll:
    def test_has_all_sections(self, sample_records):
        stats = compute_all(sample_records, metric="output", days=14, top_n=5)
        assert "burn_rate" in stats
        assert "sessions" in stats
        assert "hours" in stats
        assert "model_mix" in stats
        assert "projects" in stats
        assert "cost" in stats

    def test_empty(self, empty_records):
        stats = compute_all(empty_records, metric="output", days=14, top_n=5)
        assert stats["burn_rate"]["total"] == 0
        assert stats["sessions"]["count"] == 0
