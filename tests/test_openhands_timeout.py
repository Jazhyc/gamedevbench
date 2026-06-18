"""The OpenHands solver must enforce its wall-clock timeout.

OpenHands' agent loop is bounded by an iteration count, not seconds, so a hard
task can run for tens of minutes. The solver installs a watchdog that calls
conversation.pause() at the deadline. A step wedged inside a child subprocess
never reaches a loop boundary, so pause() can't land — a second, hard cap then
kills the worker's descendant processes to unwedge it. These tests mock the SDK
collaborators and drive a fake conversation whose run() loops until paused.
"""
import os
import threading
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


class _WedgedConversation:
    """run() ignores pause() — simulates a step blocked inside a tool call.

    It only returns once ``released`` is set, mimicking the hard cap killing the
    child subprocess and unblocking the stdio read.
    """

    def __init__(self, *a, **k):
        self.released = threading.Event()
        self.conversation_stats = None

    def set_confirmation_policy(self, policy):
        pass

    def send_message(self, message):
        pass

    def pause(self):
        pass  # ignored — the loop boundary is never reached

    def run(self):
        self.released.wait(timeout=5)


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


def test_hard_cap_kills_subprocesses_when_pause_ignored(monkeypatch):
    """When the soft pause can't land, the hard cap kills the process tree."""
    conv = _WedgedConversation()
    _patch_sdk(monkeypatch, lambda **k: conv)

    killed = {}

    def fake_terminate(pid, **kwargs):
        killed["pid"] = pid
        conv.released.set()  # killing the child unblocks the wedged run()
        return 1

    monkeypatch.setattr(ohs, "_terminate_process_tree", fake_terminate)
    monkeypatch.setattr(ohs, "HARD_CAP_GRACE", 0.2)
    solver = _make_solver(monkeypatch, timeout_seconds=0.2)

    result = solver.solve_task()

    assert result.success is False
    assert "hard cap" in result.message.lower()
    # The hard cap targets this worker's own descendants, nothing else.
    assert killed["pid"] == os.getpid()
    assert result.duration_seconds < 4.0


def test_terminate_process_tree_kills_descendants():
    """_terminate_process_tree reaps a real descendant subprocess."""
    import subprocess
    import sys

    psutil = pytest.importorskip("psutil")
    # Parent sleeps; it spawns a child that also sleeps. We reap the parent's
    # descendants (the child) without touching the test process's own children.
    code = (
        "import subprocess,sys,time;"
        "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        "time.sleep(60)"
    )
    parent = subprocess.Popen([sys.executable, "-c", code])
    try:
        deadline = time.time() + 5
        victims = []
        while time.time() < deadline:
            victims = psutil.Process(parent.pid).children(recursive=True)
            if victims:
                break
            time.sleep(0.05)
        assert victims, "expected the parent to have spawned a descendant"

        n = ohs._terminate_process_tree(parent.pid)
        assert n >= 1

        # The victim is killed but, since its still-sleeping parent never reaps
        # it, lingers as a zombie rather than disappearing — so "terminated"
        # means gone or zombie, not absent from the process table.
        def _terminated(proc):
            try:
                return proc.status() == psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                return True

        deadline = time.time() + 5
        while time.time() < deadline and not all(_terminated(v) for v in victims):
            time.sleep(0.05)
        assert all(_terminated(v) for v in victims)
    finally:
        parent.kill()
        parent.wait(timeout=5)
