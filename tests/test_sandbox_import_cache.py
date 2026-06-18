"""Tests for the sandbox import-cache warm-up.

A freshly-copied sandbox has no `.godot/`, so an agent's own headless runs
(e.g. self-written verification scripts) fail to load assets / custom-class
scenes on a cold cache. `_build_sandbox_import_cache` runs a one-time headless
editor pass to build it. These tests are offline: `subprocess.run` is mocked,
so no Godot is launched.

Covers: the warm-up issues the right editor command; timeouts and errors are
non-fatal; and `_create_sandbox_environment` invokes it once per sandbox.
"""
import json
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import gamedevbench.src.benchmark_runner as br
from gamedevbench.src.benchmark_runner import GodotBenchmarkRunner
from gamedevbench.src.utils.constants import SANDBOX_IMPORT_TIMEOUT


def _runner():
    return GodotBenchmarkRunner(use_gt=False, agent=None)


def test_import_cache_invokes_headless_editor():
    runner = _runner()
    sandbox = Path("/tmp/some_sandbox")
    with mock.patch.object(br.subprocess, "run") as run:
        runner._build_sandbox_import_cache(sandbox)
    run.assert_called_once()
    cmd = run.call_args.args[0]
    # Editor warm-up that builds .godot/ for the specific sandbox.
    assert runner.godot_path == cmd[0]
    assert "--headless" in cmd and "--editor" in cmd
    assert "--path" in cmd and str(sandbox) in cmd
    assert run.call_args.kwargs["timeout"] == SANDBOX_IMPORT_TIMEOUT


def test_import_cache_timeout_is_non_fatal():
    runner = _runner()
    with mock.patch.object(
        br.subprocess, "run", side_effect=subprocess.TimeoutExpired("godot", 1)
    ):
        # Must not raise: a partial cache is still useful.
        runner._build_sandbox_import_cache(Path("/tmp/x"))


def test_import_cache_error_is_non_fatal():
    runner = _runner()
    with mock.patch.object(br.subprocess, "run", side_effect=OSError("no godot")):
        runner._build_sandbox_import_cache(Path("/tmp/x"))


def test_create_sandbox_warms_import_cache_once(tmp_path):
    runner = _runner()
    # Minimal starter task: project file + a scene + config with answers.
    task_dir = tmp_path / "task_0001"
    (task_dir / "scenes").mkdir(parents=True)
    (task_dir / "project.godot").write_text("[application]\n")
    (task_dir / "scenes" / "main.tscn").write_text("[gd_scene]\n")
    (task_dir / "task_config.json").write_text(
        json.dumps({"instruction": "do the thing", "task_id": 1, "answer": "secret"})
    )

    with mock.patch.object(runner, "_build_sandbox_import_cache") as warm:
        sandbox = runner._create_sandbox_environment(task_dir)
    try:
        # Warm-up runs exactly once, on the created sandbox.
        warm.assert_called_once_with(sandbox)
        # Sanity: the sandbox was actually populated and answers stripped.
        assert (sandbox / "project.godot").exists()
        assert (sandbox / "scenes" / "main.tscn").exists()
        cfg = json.loads((sandbox / "task_config.json").read_text())
        assert cfg == {"instruction": "do the thing"}
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
