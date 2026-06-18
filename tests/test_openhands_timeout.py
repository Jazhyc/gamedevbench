"""The OpenHands solver must enforce its wall-clock timeout.

OpenHands' agent loop is bounded by an iteration count, not seconds, so a hard
task can run for tens of minutes. The solver installs a watchdog that calls
conversation.pause() at the deadline. These tests mock the SDK collaborators and
drive a fake conversation whose run() loops until paused.
"""
import time

import pytest

pytest.importorskip("openhands.sdk")

import gamedevbench.src.openhands_solver as ohs
from gamedevbench.src.openhands_solver import OpenHandsSolver


class _FakeConversation:
    """run() blocks until pause() is called (simulates a long agent loop)."""

    def __init__(self, *a, finishes_quickly=False, **k):
        self._paused = False
        self._finishes_quickly = finishes_quickly
        self.conversation_stats = None

    def set_confirmation_policy(self, policy):
        pass

    def send_message(self, message):
        pass

    def pause(self):
        self._paused = True

    def run(self):
        if self._finishes_quickly:
            return
        # Busy-wait (bounded) until the watchdog pauses us.
        for _ in range(500):
            if self._paused:
                return
            time.sleep(0.01)


def _patch_sdk(monkeypatch, conversation_factory):
    """Stub out everything solve_task touches except the watchdog logic."""
    monkeypatch.setattr(ohs, "LLM", lambda **k: type("L", (), {"model_copy": lambda self, **kw: self})())
    monkeypatch.setattr(ohs, "Agent", lambda **k: object())
    monkeypatch.setattr(ohs, "get_default_tools", lambda **k: [])
    monkeypatch.setattr(ohs, "get_default_condenser", lambda **k: None)
    monkeypatch.setattr(ohs, "resolve_provider_api_key", lambda model: ("fake-key", "DEEPSEEK_API_KEY"))
    monkeypatch.setattr(ohs, "Conversation", conversation_factory)


def _make_solver(monkeypatch, timeout_seconds):
    solver = OpenHandsSolver(timeout_seconds=timeout_seconds, model="deepseek-v4-pro")
    monkeypatch.setattr(solver, "load_config", lambda: {"task_id": "t", "instruction": "do", "name": "n"})
    monkeypatch.setattr(solver, "get_task_prompt", lambda config: "PROMPT")
    return solver


def test_solver_times_out_and_marks_failure(monkeypatch):
    _patch_sdk(monkeypatch, lambda **k: _FakeConversation(**k))
    solver = _make_solver(monkeypatch, timeout_seconds=0.3)

    result = solver.solve_task()

    assert result.success is False
    assert "timed out" in result.message.lower()
    # The watchdog should fire close to the deadline, not after the full loop.
    assert result.duration_seconds < 3.0


def test_solver_completes_before_timeout(monkeypatch):
    _patch_sdk(monkeypatch, lambda **k: _FakeConversation(finishes_quickly=True, **k))
    solver = _make_solver(monkeypatch, timeout_seconds=30)

    result = solver.solve_task()

    assert result.success is True
    assert result.message == "Task completed"
