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


def test_deepseek_litellm_id_uses_deepseek_rate_not_default():
    # Regression: deepseek/ models had no pricing entry and were billed at the
    # default ($3/$15) rate, ~10x DeepSeek's actual cost.
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    # deepseek-v4-pro: input 0.435 + output 0.87
    assert round(usage.calculate_cost("deepseek/deepseek-v4-pro"), 4) == 1.305


def test_deepseek_pro_not_shadowed_by_flash():
    pro = TokenUsage(input_tokens=1_000_000, output_tokens=0)
    flash = TokenUsage(input_tokens=1_000_000, output_tokens=0)
    assert round(pro.calculate_cost("deepseek/deepseek-v4-pro"), 4) == 0.435
    assert round(flash.calculate_cost("deepseek/deepseek-v4-flash"), 4) == 0.14


def test_validation_result_to_dict_roundtrip():
    d = ValidationResult(success=False, message="boom").to_dict()
    assert d["success"] is False
    assert d["message"] == "boom"
    assert "timestamp" in d
