"""Tests for token cost calculation and result serialization."""
from gamedevbench.src.utils.data_types import TokenUsage, ValidationResult


def test_cost_matches_model_by_substring():
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    # gpt-4o rates: input 2.50 + output 10.00 per 1M
    assert round(usage.calculate_cost("my-gpt-4o-run"), 4) == 12.50


def test_cached_input_is_cheaper():
    plain = TokenUsage(input_tokens=1_000_000, output_tokens=0)
    cached = TokenUsage(input_tokens=1_000_000, output_tokens=0,
                        cache_read_tokens=1_000_000)
    assert cached.calculate_cost("gpt-4o") < plain.calculate_cost("gpt-4o")


def test_unknown_model_falls_back_to_default_rate():
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=0)
    assert usage.calculate_cost("totally-unknown-model") == 3.00  # default input rate


def test_validation_result_to_dict_roundtrip():
    d = ValidationResult(success=False, message="boom").to_dict()
    assert d["success"] is False
    assert d["message"] == "boom"
    assert "timestamp" in d
