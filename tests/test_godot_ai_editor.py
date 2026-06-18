"""Tests for the godot-ai per-task editor lifecycle helpers.

Covers the pure/mockable pieces — addon caching, plugin enablement, readiness
polling, and command building — without Godot, a display, or the network.
"""
from pathlib import Path

import pytest

from gamedevbench.src import godot_ai_editor as gae


def test_addon_tag_prefixes_v():
    assert gae.addon_tag("2.7.5") == "v2.7.5"


def test_addon_cache_dir_honors_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GAMEDEVBENCH_GODOT_AI_CACHE", str(tmp_path))
    assert gae.addon_cache_dir("2.7.5") == tmp_path / "gamedevbench_godot_ai_2.7.5"


def test_parse_host_port():
    assert gae.parse_host_port("http://127.0.0.1:8000/mcp") == ("127.0.0.1", 8000)
    assert gae.parse_host_port("http://localhost:18000/mcp") == ("localhost", 18000)


# --- enable_plugin_text -----------------------------------------------------

def test_enable_plugin_appends_section_when_absent():
    out = gae.enable_plugin_text("[application]\nconfig/name=\"X\"\n")
    assert "[editor_plugins]" in out
    assert 'enabled=PackedStringArray("res://addons/godot_ai/plugin.cfg")' in out


def test_enable_plugin_merges_existing_members():
    src = (
        "[editor_plugins]\n\n"
        'enabled=PackedStringArray("res://addons/other/plugin.cfg")\n'
    )
    out = gae.enable_plugin_text(src)
    assert '"res://addons/other/plugin.cfg"' in out
    assert '"res://addons/godot_ai/plugin.cfg"' in out
    # Single merged array, not a second section.
    assert out.count("enabled=PackedStringArray(") == 1
    assert out.count("[editor_plugins]") == 1


def test_enable_plugin_is_idempotent():
    once = gae.enable_plugin_text("[application]\n")
    twice = gae.enable_plugin_text(once)
    assert once == twice


def test_enable_plugin_fills_empty_section():
    out = gae.enable_plugin_text("[editor_plugins]\n")
    assert 'enabled=PackedStringArray("res://addons/godot_ai/plugin.cfg")' in out
    assert out.count("[editor_plugins]") == 1


# --- strip_plugin_text / cleanup --------------------------------------------

def test_strip_removes_added_section_round_trip():
    original = '[application]\nconfig/name="X"\n'
    enabled = gae.enable_plugin_text(original)
    assert "[editor_plugins]" in enabled
    # Stripping a section we created restores the original byte-for-byte.
    assert gae.strip_plugin_text(enabled) == original


def test_strip_removes_game_helper_autoload_keeps_others():
    text = (
        "[autoload]\n\n"
        'QuestManager="*res://addons/quest_manager/QuestManager.gd"\n'
        '_mcp_game_helper="*res://addons/godot_ai/runtime/game_helper.gd"\n'
    )
    out = gae.strip_plugin_text(text)
    assert "_mcp_game_helper" not in out
    assert "res://addons/godot_ai/" not in out
    # The project's real autoload is untouched.
    assert 'QuestManager="*res://addons/quest_manager/QuestManager.gd"' in out


def test_strip_preserves_other_editor_plugins():
    text = (
        "[editor_plugins]\n\n"
        'enabled=PackedStringArray("res://addons/other/plugin.cfg", '
        '"res://addons/godot_ai/plugin.cfg")\n'
    )
    out = gae.strip_plugin_text(text)
    assert '"res://addons/other/plugin.cfg"' in out
    assert "godot_ai" not in out
    assert "[editor_plugins]" in out  # section kept — another plugin remains


def test_strip_is_idempotent_on_clean_project():
    clean = '[application]\nconfig/name="X"\n'
    assert gae.strip_plugin_text(clean) == clean


def test_cleanup_project_footprint_removes_addon_and_entries(tmp_path):
    (tmp_path / "addons" / "godot_ai").mkdir(parents=True)
    (tmp_path / "addons" / "godot_ai" / "plugin.cfg").write_text("[plugin]\n")
    (tmp_path / "project.godot").write_text(
        "[autoload]\n\n"
        'QuestManager="*res://addons/quest_manager/QuestManager.gd"\n'
        '_mcp_game_helper="*res://addons/godot_ai/runtime/game_helper.gd"\n\n'
        "[editor_plugins]\n\n"
        'enabled=PackedStringArray("res://addons/godot_ai/plugin.cfg")\n'
    )

    gae.cleanup_project_footprint(tmp_path)

    assert not (tmp_path / "addons" / "godot_ai").exists()
    text = (tmp_path / "project.godot").read_text()
    assert "godot_ai" not in text
    assert "_mcp_game_helper" not in text
    assert "QuestManager" in text  # the project's own autoload survives


def test_full_install_then_cleanup_restores_project(tmp_path):
    addon_src = tmp_path / "src" / "godot_ai"
    addon_src.mkdir(parents=True)
    (addon_src / "plugin.cfg").write_text("[plugin]\n")
    project = tmp_path / "proj"
    project.mkdir()
    original = '[application]\nconfig/name="P"\n'
    (project / "project.godot").write_text(original)

    gae.install_addon(project, addon_src)
    gae.cleanup_project_footprint(project)

    assert not (project / "addons" / "godot_ai").exists()
    assert (project / "project.godot").read_text() == original


# --- install_addon ----------------------------------------------------------

def test_install_addon_copies_and_enables(tmp_path):
    addon_src = tmp_path / "src" / "godot_ai"
    addon_src.mkdir(parents=True)
    (addon_src / "plugin.cfg").write_text("[plugin]\nname=\"Godot AI\"\n")

    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.godot").write_text("[application]\nconfig/name=\"P\"\n")

    gae.install_addon(project, addon_src)

    assert (project / "addons" / "godot_ai" / "plugin.cfg").exists()
    text = (project / "project.godot").read_text()
    assert '"res://addons/godot_ai/plugin.cfg"' in text


# --- wait_until_ready -------------------------------------------------------

def test_wait_until_ready_returns_true_immediately():
    assert gae.wait_until_ready(
        "http://x", probe=lambda _u: {"readiness": "ready"},
        sleep=lambda _s: None,
    )


def test_wait_until_ready_polls_until_ready():
    states = [None, {"readiness": "starting"}, {"readiness": "ready"}]

    def probe(_url):
        return states.pop(0)

    assert gae.wait_until_ready(
        "http://x", probe=probe, sleep=lambda _s: None, poll_interval=0,
    )


def test_wait_until_ready_times_out():
    clock = {"t": 0.0}

    def fake_now():
        return clock["t"]

    def fake_sleep(_s):
        clock["t"] += 1.0

    assert not gae.wait_until_ready(
        "http://x", timeout=3.0, poll_interval=1.0,
        probe=lambda _u: {"readiness": "starting"},
        sleep=fake_sleep, now=fake_now,
    )


# --- build_editor_command ---------------------------------------------------

def test_build_editor_command_prefers_xvfb():
    cmd, env = gae.build_editor_command(
        "/bin/godot", Path("/proj"), have_xvfb=True, allow_headless=True,
    )
    assert cmd[:2] == ["xvfb-run", "-a"]
    assert "--editor" in cmd and "--headless" not in cmd
    assert env == {}


def test_build_editor_command_headless_fallback():
    cmd, env = gae.build_editor_command(
        "/bin/godot", Path("/proj"), have_xvfb=False, allow_headless=True,
    )
    assert cmd[0] == "/bin/godot"
    assert "--headless" in cmd
    # The plugin self-disables under --headless unless this opt-in is set.
    assert env == {"GODOT_AI_ALLOW_HEADLESS": "1"}


# --- ensure_addon -----------------------------------------------------------

def test_ensure_addon_skips_clone_when_cached(monkeypatch, tmp_path):
    monkeypatch.setenv("GAMEDEVBENCH_GODOT_AI_CACHE", str(tmp_path))
    addon = tmp_path / "gamedevbench_godot_ai_2.7.5" / "addon" / "godot_ai"
    addon.mkdir(parents=True)
    (addon / "plugin.cfg").write_text("[plugin]\n")

    def boom(*a, **k):
        raise AssertionError("ensure_addon must not clone when cached")

    assert gae.ensure_addon("2.7.5", runner=boom) == addon


def test_ensure_addon_clones_when_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("GAMEDEVBENCH_GODOT_AI_CACHE", str(tmp_path))
    cache = tmp_path / "gamedevbench_godot_ai_2.7.5"

    def fake_clone(cmd, **kwargs):
        # Materialize the addon where the real clone would put it.
        dest = Path(cmd[-1]) / gae._ADDON_SUBPATH
        dest.mkdir(parents=True)
        (dest / "plugin.cfg").write_text("[plugin]\n")
        return _completed(0)

    addon = gae.ensure_addon("2.7.5", runner=fake_clone)
    assert addon == cache / "addon" / "godot_ai"
    assert (addon / "plugin.cfg").exists()


def test_ensure_addon_raises_on_clone_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("GAMEDEVBENCH_GODOT_AI_CACHE", str(tmp_path))

    def fail_clone(cmd, **kwargs):
        return _completed(128, stderr="fatal: repository not found")

    with pytest.raises(RuntimeError, match="Failed to clone godot-ai"):
        gae.ensure_addon("2.7.5", runner=fail_clone)


class _completed:
    """Minimal subprocess.CompletedProcess stand-in for the clone runner."""

    def __init__(self, returncode, stderr=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


# --- GodotAiEditorSession orchestration (mocked subprocess) -----------------

class _FakeProc:
    def __init__(self):
        self.pid = 4242
        self._alive = True

    def poll(self):
        return None if self._alive else 0


def _patch_session(monkeypatch, *, ready):
    """Stub out the side-effecting pieces of a session; record teardown calls."""
    monkeypatch.setattr(gae, "install_addon", lambda *a, **k: None)
    monkeypatch.setattr(gae.subprocess, "Popen", lambda *a, **k: _FakeProc())
    monkeypatch.setattr(gae, "wait_until_ready", lambda *a, **k: ready)
    killed = []
    monkeypatch.setattr(gae, "_terminate_tree", lambda pid, **k: killed.append(pid))
    return killed


def _session(tmp_path):
    return gae.GodotAiEditorSession(
        project_dir=tmp_path,
        godot_path="/bin/godot",
        http_url="http://127.0.0.1:8000/mcp",
        addon_src=tmp_path / "addon",
        ready_timeout=1.0,
    )


def test_session_enters_when_ready(monkeypatch, tmp_path):
    killed = _patch_session(monkeypatch, ready=True)
    with _session(tmp_path) as sess:
        assert sess.http_url.endswith("/mcp")
    # Teardown runs exactly once on normal exit.
    assert killed == [4242]


def test_session_raises_and_tears_down_when_never_ready(monkeypatch, tmp_path):
    killed = _patch_session(monkeypatch, ready=False)
    with pytest.raises(RuntimeError, match="never became ready"):
        with _session(tmp_path):
            pass
    # Failed start still kills the editor (once on the failure path; __exit__
    # is not reached because __enter__ raised).
    assert killed == [4242]
