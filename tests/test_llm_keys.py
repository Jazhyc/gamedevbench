"""Tests for provider API-key resolution by litellm model prefix."""
from gamedevbench.src.utils.llm_keys import resolve_provider_api_key

# Every provider env var the resolver may read, cleared before each case so a
# stray real key in the environment can't make a test pass/fail spuriously.
_ALL_KEYS = [
    "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
]


def _clear(monkeypatch):
    for k in _ALL_KEYS:
        monkeypatch.delenv(k, raising=False)


def test_deepseek_prefix_uses_deepseek_key(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-secret")
    key, name = resolve_provider_api_key("deepseek/deepseek-v4-pro")
    assert key == "ds-secret"
    assert name == "DEEPSEEK_API_KEY"


def test_deepseek_does_not_fall_back_to_openai(monkeypatch):
    # Regression: before the deepseek branch, a deepseek/ model wrongly grabbed
    # OPENAI_API_KEY via the default fallback.
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "oai-secret")
    key, name = resolve_provider_api_key("deepseek/deepseek-chat")
    assert key is None
    assert name == "DEEPSEEK_API_KEY"


def test_openrouter_prefix(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-secret")
    key, name = resolve_provider_api_key("openrouter/deepseek/deepseek-chat:free")
    assert key == "or-secret"
    assert name == "OPENROUTER_API_KEY"


def test_anthropic_prefix(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "an-secret")
    key, name = resolve_provider_api_key("anthropic/claude-sonnet-4-20250514")
    assert key == "an-secret"
    assert name == "ANTHROPIC_API_KEY"


def test_gemini_accepts_either_key(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GOOGLE_API_KEY", "g-secret")
    key, name = resolve_provider_api_key("gemini/gemini-2.0-flash")
    assert key == "g-secret"
    assert "GOOGLE_API_KEY" in name


def test_unknown_prefix_defaults_to_openai(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "oai-secret")
    key, name = resolve_provider_api_key("gpt-4o")
    assert key == "oai-secret"
    assert name == "OPENAI_API_KEY"
