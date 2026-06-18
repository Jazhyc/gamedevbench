"""The OpenHands solver must drive the godot-ai editor + HTTP transport.

For the godot-ai server the agent reaches a plugin-spawned server over HTTP, and
a live Godot editor must run for the duration of the task. These tests mock the
SDK collaborators and the editor session to assert the solver (a) builds an HTTP
mcpServers entry and (b) starts the editor before the run and tears it down
after — on success and on failure.
"""
import pytest

pytest.importorskip("openhands.sdk")

import gamedevbench.src.openhands_solver as ohs
import gamedevbench.src.godot_ai_editor as gae
from gamedevbench.src.openhands_solver import OpenHandsSolver


class _FakeConversation:
    def __init__(self, *a, **k):
        self.conversation_stats = None

    def set_confirmation_policy(self, policy):
        pass

    def send_message(self, message):
        pass

    def pause(self):
        pass

    def run(self):
        return


class _FakeEditorSession:
    """Records enter/exit and the http_url the solver wired in."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.entered = False
        self.exited = False
        type(self).instances.append(self)

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *exc):
        self.exited = True


def _patch_sdk(monkeypatch, captured):
    monkeypatch.setattr(ohs, "LLM", lambda **k: type("L", (), {"model_copy": lambda self, **kw: self})())

    def fake_agent(**k):
        captured["mcp_config"] = k.get("mcp_config")
        return object()

    monkeypatch.setattr(ohs, "Agent", fake_agent)
    monkeypatch.setattr(ohs, "get_default_tools", lambda **k: [])
    monkeypatch.setattr(ohs, "get_default_condenser", lambda **k: None)
    monkeypatch.setattr(ohs, "resolve_provider_api_key", lambda model: ("fake-key", "DEEPSEEK_API_KEY"))
    monkeypatch.setattr(ohs, "Conversation", lambda **k: _FakeConversation(**k))


def _patch_editor(monkeypatch):
    _FakeEditorSession.instances = []
    monkeypatch.setattr(gae, "ensure_addon", lambda *a, **k: "/cache/godot_ai")
    monkeypatch.setattr(gae, "GodotAiEditorSession", _FakeEditorSession)


def _make_solver(monkeypatch):
    solver = OpenHandsSolver(
        timeout_seconds=30, model="deepseek-v4-pro",
        use_mcp=True, mcp_server="godot-ai",
    )
    monkeypatch.setattr(solver, "load_config", lambda: {"task_id": "t", "instruction": "do", "name": "n"})
    monkeypatch.setattr(solver, "get_task_prompt", lambda config: "PROMPT")
    return solver


def test_godot_ai_builds_http_config_and_runs_editor(monkeypatch):
    captured = {}
    _patch_sdk(monkeypatch, captured)
    _patch_editor(monkeypatch)
    solver = _make_solver(monkeypatch)

    result = solver.solve_task()

    assert result.success is True
    # HTTP transport entry, not stdio command/args.
    server_cfg = captured["mcp_config"]["mcpServers"]["godot-ai"]
    assert server_cfg["transport"] == "http"
    assert server_cfg["url"] == solver.mcp_spec.http_url
    assert "command" not in server_cfg
    # The editor was started and torn down exactly once.
    assert len(_FakeEditorSession.instances) == 1
    sess = _FakeEditorSession.instances[0]
    assert sess.entered and sess.exited
    assert sess.kwargs["http_url"] == solver.mcp_spec.http_url


def test_godot_ai_editor_torn_down_on_failure(monkeypatch):
    captured = {}
    _patch_sdk(monkeypatch, captured)
    _patch_editor(monkeypatch)

    # Make the conversation blow up mid-run; the editor must still be torn down.
    class _Boom(_FakeConversation):
        def run(self):
            raise RuntimeError("kaboom")

    monkeypatch.setattr(ohs, "Conversation", lambda **k: _Boom(**k))
    solver = _make_solver(monkeypatch)

    result = solver.solve_task()

    assert result.success is False
    sess = _FakeEditorSession.instances[0]
    assert sess.entered and sess.exited
