"""Tests for the Claude Code guardrail hooks.

The hooks are stdlib-only scripts driven by a JSON payload on stdin; we exercise
them as subprocesses (exactly how Claude Code invokes them) and assert exit
codes: 0 = allow, 2 = block.
"""
import json
import subprocess
import sys

import pytest


def _run(script, payload, cwd=None):
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=cwd,
    )


@pytest.fixture
def hooks_dir(repo_root):
    return repo_root / ".claude" / "hooks"


# --- guard_sensitive.py -----------------------------------------------------

def test_guard_blocks_env_access(hooks_dir):
    p = _run(hooks_dir / "guard_sensitive.py",
             {"tool_name": "Read", "tool_input": {"file_path": "/proj/.env"}})
    assert p.returncode == 2
    assert ".env" in p.stderr


def test_guard_allows_env_example(hooks_dir):
    p = _run(hooks_dir / "guard_sensitive.py",
             {"tool_name": "Read", "tool_input": {"file_path": ".env.example"}})
    assert p.returncode == 0


def test_guard_blocks_task_zip_edit(hooks_dir):
    p = _run(hooks_dir / "guard_sensitive.py",
             {"tool_name": "Edit", "tool_input": {"file_path": "tasks/task_0002.zip"}})
    assert p.returncode == 2


def test_guard_blocks_gt_zip_edit(hooks_dir):
    p = _run(hooks_dir / "guard_sensitive.py",
             {"tool_name": "Write", "tool_input": {"file_path": "tasks_gt/task_0002.zip"}})
    assert p.returncode == 2


def test_guard_allows_task_zip_read(hooks_dir):
    p = _run(hooks_dir / "guard_sensitive.py",
             {"tool_name": "Read", "tool_input": {"file_path": "tasks/task_0002.zip"}})
    assert p.returncode == 0


def test_guard_allows_normal_source_edit(hooks_dir):
    p = _run(hooks_dir / "guard_sensitive.py",
             {"tool_name": "Edit",
              "tool_input": {"file_path": "gamedevbench/src/base_solver.py"}})
    assert p.returncode == 0


def test_guard_malformed_payload_does_not_block(hooks_dir):
    p = subprocess.run([sys.executable, str(hooks_dir / "guard_sensitive.py")],
                       input="not json", text=True, capture_output=True)
    assert p.returncode == 0


# --- commit_reminder.py -----------------------------------------------------

def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def temp_git_repo(tmp_path):
    _git(["init", "-q"], tmp_path)
    _git(["config", "user.email", "t@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    return tmp_path


def test_reminder_blocks_on_dirty_tree(hooks_dir, temp_git_repo):
    (temp_git_repo / "feature.py").write_text("x = 1\n")
    p = _run(hooks_dir / "commit_reminder.py",
             {"stop_hook_active": False, "cwd": str(temp_git_repo)})
    assert p.returncode == 2
    assert "Uncommitted changes" in p.stderr


def test_reminder_loop_guard_allows_stop(hooks_dir, temp_git_repo):
    (temp_git_repo / "feature.py").write_text("x = 1\n")
    p = _run(hooks_dir / "commit_reminder.py",
             {"stop_hook_active": True, "cwd": str(temp_git_repo)})
    assert p.returncode == 0


def test_reminder_clean_tree_allows_stop(hooks_dir, temp_git_repo):
    p = _run(hooks_dir / "commit_reminder.py",
             {"stop_hook_active": False, "cwd": str(temp_git_repo)})
    assert p.returncode == 0


def test_reminder_outside_git_does_not_block(hooks_dir, tmp_path):
    p = _run(hooks_dir / "commit_reminder.py",
             {"stop_hook_active": False, "cwd": str(tmp_path)})
    assert p.returncode == 0
