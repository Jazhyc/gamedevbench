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

# Grace period (seconds) after the soft timeout before the hard cap forcibly
# terminates the solver's child process tree. The OpenHands soft cap is a
# cooperative conversation.pause() that only takes effect between agent steps;
# a step wedged inside a child subprocess (e.g. a hung MCP/godot process holding
# a stdio read) never reaches that boundary, so the hard cap kills those
# descendants to unwedge it. See openhands_solver.
HARD_CAP_GRACE = 30