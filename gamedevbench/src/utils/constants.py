#!/usr/bin/env python3

import os
from pathlib import Path

# Directory paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
TASKS_DIR = PROJECT_ROOT / "tasks"
GT_TASKS_DIR = PROJECT_ROOT / "tasks_gt"
RESULTS_FOLDER = PROJECT_ROOT / "results"

# Godot configuration
# Honor GODOT_EXEC_PATH from the environment (as documented in CLAUDE.md and
# .env.example); fall back to "godot" on PATH. On Windows this must point at the
# real .exe — a .cmd/.bat shim cannot be launched via subprocess without a shell.
GODOT_EXEC_PATH = os.environ.get("GODOT_EXEC_PATH", "godot")
GODOT_PROJECT_NAME = "project.godot"
TEST_SCENE_NAME = "res://scenes/test.tscn"

# Execution settings
TIMEOUT = 600