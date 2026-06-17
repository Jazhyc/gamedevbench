"""Tests for validate_tasks.py helpers (the e2e validation driver)."""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# validate_tasks.py lives at the repo root, not inside the gamedevbench package,
# so load it by path rather than importing it as a module.
_spec = importlib.util.spec_from_file_location(
    "validate_tasks", REPO / "validate_tasks.py"
)
assert _spec is not None and _spec.loader is not None
validate_tasks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_tasks)


def test_needs_import_true_when_no_cache(tmp_path):
    # Fresh task dir with no .godot cache -> import warmup is needed.
    assert validate_tasks.needs_import(tmp_path) is True


def test_needs_import_false_when_cache_present(tmp_path):
    (tmp_path / ".godot").mkdir()
    assert validate_tasks.needs_import(tmp_path) is False


def test_needs_import_true_when_godot_is_a_file_not_dir(tmp_path):
    # A stray `.godot` file (not the cache dir) should not be mistaken for cache.
    (tmp_path / ".godot").write_text("not a cache dir")
    assert validate_tasks.needs_import(tmp_path) is True
