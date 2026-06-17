"""Tests for loading the project's .env into os.environ."""
import os

from gamedevbench.src.utils.env import load_project_env


def test_loads_keys_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GDB_TEST_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("GDB_TEST_KEY=from_dotenv\n")

    found = load_project_env(path=env_file)

    assert found is True
    assert os.environ["GDB_TEST_KEY"] == "from_dotenv"


def test_existing_env_var_is_not_overridden(tmp_path, monkeypatch):
    # An explicitly exported variable must win over .env (override=False).
    monkeypatch.setenv("GDB_TEST_KEY", "from_shell")
    env_file = tmp_path / ".env"
    env_file.write_text("GDB_TEST_KEY=from_dotenv\n")

    load_project_env(path=env_file)

    assert os.environ["GDB_TEST_KEY"] == "from_shell"


def test_missing_env_file_is_a_noop(tmp_path):
    found = load_project_env(path=tmp_path / "does_not_exist.env")
    assert found is False
