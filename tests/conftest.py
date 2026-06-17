"""Shared pytest fixtures.

The whole suite is offline: no Godot, no API keys, no real display. Anything
that would touch those is mocked in the individual test modules.
"""
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
