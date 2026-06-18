"""Tests for task-prompt construction and config loading."""
import json

from gamedevbench.src.utils import prompts


def test_basic_prompt_contains_instruction():
    out = prompts.create_task_prompt({"instruction": "Add a double jump."})
    assert "Add a double jump." in out
    assert "without any further assistance" in out
    assert "godot" in out.lower()


def test_runtime_video_guidance_appended_only_when_requested():
    with_video = prompts.create_task_prompt({"instruction": "x"}, use_runtime_video=True)
    without = prompts.create_task_prompt({"instruction": "x"})
    assert "--write-movie" in with_video
    assert "--write-movie" not in without


def test_mcp_guidance_appended_only_when_requested():
    with_mcp = prompts.create_task_prompt({"instruction": "x"}, use_mcp=True)
    without = prompts.create_task_prompt({"instruction": "x"})
    # Defaults to the screenshot baseline guidance.
    assert "godot-screenshot" in with_mcp
    assert "godot-screenshot" not in without


def test_explicit_mcp_guidance_overrides_default():
    custom = "\n\nUse the run_project tool to verify."
    out = prompts.create_task_prompt(
        {"instruction": "x"}, use_mcp=True, mcp_guidance=custom
    )
    assert "run_project" in out
    # The custom guidance replaces the screenshot baseline text.
    assert "godot-screenshot" not in out


def test_mcp_guidance_ignored_when_mcp_disabled():
    out = prompts.create_task_prompt(
        {"instruction": "x"}, use_mcp=False, mcp_guidance="should not appear"
    )
    assert "should not appear" not in out


def test_verification_nudge_appended_only_when_requested():
    with_nudge = prompts.create_task_prompt(
        {"instruction": "x"}, encourage_verification=True
    )
    without = prompts.create_task_prompt({"instruction": "x"})
    # Light nudge: tells the agent to verify behaviour and run a headless check,
    # but ships no script template / introspection idioms and no import/invocation
    # mechanics (the sandbox import-cache warm-up handles that environmentally).
    assert "verify" in with_nudge.lower()
    assert "godot --headless --script" in with_nudge
    assert "--import" not in with_nudge  # mechanics live in the sandbox warm-up
    assert "verify" not in without.lower()


def test_verification_nudge_is_independent_of_mcp_and_video():
    # Orthogonal flags can be combined; each block appears exactly once.
    out = prompts.create_task_prompt(
        {"instruction": "x"},
        use_runtime_video=True,
        use_mcp=True,
        encourage_verification=True,
    )
    assert "--write-movie" in out
    assert "godot-screenshot" in out
    assert out.count("godot --headless --script") == 1


def test_invalid_config_returns_empty_string():
    assert prompts.create_task_prompt({}) == ""
    assert prompts.create_task_prompt(None) == ""


def test_load_task_config_reads_cwd(tmp_path, monkeypatch):
    (tmp_path / "task_config.json").write_text(
        json.dumps({"instruction": "hi", "task_id": 7})
    )
    monkeypatch.chdir(tmp_path)
    cfg = prompts.load_task_config()
    assert cfg["task_id"] == 7


def test_load_task_config_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert prompts.load_task_config() is None
