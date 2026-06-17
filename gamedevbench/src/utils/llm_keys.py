#!/usr/bin/env python3
"""Resolve the API key for a litellm-format model id by its provider prefix.

Kept free of heavy SDK imports (e.g. openhands) so it stays unit-testable on
the offline suite, which runs on Python versions where openhands isn't
installed.
"""

import os
from typing import Optional, Tuple

# litellm provider prefix -> environment variable holding that provider's key.
# Order doesn't matter (prefixes are disjoint); the gemini variants share a key.
_PREFIX_TO_ENV = {
    "openrouter/": "OPENROUTER_API_KEY",
    "anthropic/": "ANTHROPIC_API_KEY",
    "deepseek/": "DEEPSEEK_API_KEY",
    "google/": "GEMINI_API_KEY",
    "gemini/": "GEMINI_API_KEY",
}

# Provider used when no known prefix matches (OpenAI-compatible default).
_DEFAULT_ENV = "OPENAI_API_KEY"


def resolve_provider_api_key(model: str) -> Tuple[Optional[str], str]:
    """Return (api_key, key_name) for a litellm model id.

    key_name is the human-readable env var name, used for error messages when
    the key is missing. Gemini accepts either GEMINI_API_KEY or GOOGLE_API_KEY.
    """
    for prefix, env_name in _PREFIX_TO_ENV.items():
        if model.startswith(prefix):
            if env_name == "GEMINI_API_KEY":
                key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                return key, "GEMINI_API_KEY or GOOGLE_API_KEY"
            return os.environ.get(env_name), env_name
    return os.environ.get(_DEFAULT_ENV), _DEFAULT_ENV
