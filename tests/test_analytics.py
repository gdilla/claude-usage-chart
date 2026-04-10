"""Tests for claude_usage_analytics."""

from claude_usage_analytics import (
    resolve_model_name,
    get_record_cost,
    API_PRICING,
)
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
