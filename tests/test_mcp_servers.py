"""Tests for the per-run MCP server registry.

Locks in the contract that benchmark_runner/solvers rely on: the baseline
screenshot server stays the default, the Godot-targeted server is selectable,
and each spec carries the launch command + prompt guidance.
"""
import pytest

from gamedevbench.src import mcp_servers


def test_baseline_is_default():
    assert mcp_servers.DEFAULT_MCP_SERVER == "screenshot"
    spec = mcp_servers.get_mcp_server(None)
    assert spec.name == "screenshot"
    assert spec.server_id == "godot-screenshot"
    assert spec.command == "uv"
    assert spec.args == ("run", "gamedevbench-mcp")


def test_godot_server_registered():
    names = mcp_servers.available_mcp_servers()
    assert "godot" in names
    assert "screenshot" in names
    assert names == sorted(names)


def test_godot_server_launches_via_npx():
    spec = mcp_servers.get_mcp_server("godot")
    assert spec.command == "npx"
    # -y so npx never blocks on an interactive install prompt mid-run.
    assert "-y" in spec.args
    assert "@coding-solo/godot-mcp" in spec.args


def test_unknown_server_raises():
    with pytest.raises(ValueError, match="Unknown MCP server"):
        mcp_servers.get_mcp_server("does-not-exist")


def test_each_server_has_distinct_guidance():
    screenshot = mcp_servers.get_mcp_server("screenshot").prompt_guidance
    godot = mcp_servers.get_mcp_server("godot").prompt_guidance
    assert screenshot != godot
    assert "godot-screenshot" in screenshot
    # godot-mcp exposes run/debug tools the screenshot baseline doesn't.
    assert "run_project" in godot


def test_godot_env_uses_godot_exec_path(monkeypatch):
    monkeypatch.setenv("GODOT_EXEC_PATH", "/opt/godot/godot")
    env = mcp_servers.get_mcp_server("godot").env()
    assert env["GODOT_PATH"] == "/opt/godot/godot"


def test_godot_env_omits_path_when_unresolvable(monkeypatch):
    monkeypatch.delenv("GODOT_EXEC_PATH", raising=False)
    monkeypatch.delenv("GODOT_PATH", raising=False)
    monkeypatch.setattr(mcp_servers.shutil, "which", lambda _: None)
    # No path found -> no GODOT_PATH key (let godot-mcp self-detect).
    assert "GODOT_PATH" not in mcp_servers.get_mcp_server("godot").env()


def test_screenshot_server_has_no_extra_env():
    assert mcp_servers.get_mcp_server("screenshot").env() == {}
