"""Tests for environment-driven configuration constants."""
import importlib
import os

import gamedevbench.src.utils.constants as constants


def _reload_with_env(monkeypatch, value):
    """Reload the constants module with GODOT_EXEC_PATH set (or unset)."""
    if value is None:
        monkeypatch.delenv("GODOT_EXEC_PATH", raising=False)
    else:
        monkeypatch.setenv("GODOT_EXEC_PATH", value)
    return importlib.reload(constants)


def test_godot_exec_path_defaults_to_godot(monkeypatch):
    reloaded = _reload_with_env(monkeypatch, None)
    try:
        assert reloaded.GODOT_EXEC_PATH == "godot"
    finally:
        importlib.reload(constants)  # restore real environment for other tests


def test_godot_exec_path_honors_env_override(monkeypatch):
    custom = os.path.join("D:", "Games", "Godot", "Godot_console.exe")
    reloaded = _reload_with_env(monkeypatch, custom)
    try:
        assert reloaded.GODOT_EXEC_PATH == custom
    finally:
        importlib.reload(constants)
