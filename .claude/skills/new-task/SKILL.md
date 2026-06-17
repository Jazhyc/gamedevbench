---
name: new-task
description: Author a new GameDevBench task (starter project + ground truth + validation harness) and wire it into the suite. Use when asked to add, create, or author a benchmark task.
---

# Author a new GameDevBench task

A task is a small Godot 4.x project shipped as a **zip pair**:
- `tasks/task_XXXX.zip` — the **starter** the agent receives (no solution).
- `tasks_gt/task_XXXX.zip` — the **ground-truth** solution (must validate PASS).

Each zip extracts to a top-level `task_XXXX/` folder. Pick the next free
`task_XXXX` id (zero-padded, 4 digits) above the current max in `tasks/`.

## Required contents (inside `task_XXXX/`)
| Path | Purpose |
|------|---------|
| `project.godot` | Godot project file |
| `task_config.json` | Task metadata + instruction (schema below) |
| `scenes/test.tscn` + `scripts/test.gd` | Validation harness, run headless |
| scenes / scripts / assets | The actual game content |

`.gd.uid` sidecar files are part of the project — keep them.

### `task_config.json`
```json
{
  "task_id": 2,
  "name": "Short human title",
  "instruction": "Imperative description of exactly what to build. This is the agent's prompt.",
  "metadata": {
    "tutorial_source": "...", "video_id": "...", "github_repo": "...",
    "expected_nodes": ["Area2D:Projectile", "Node:Projectile/QMStepTracker"],
    "key_properties": {"Projectile/QMStepTracker.step_type": "incremental_step"}
  }
}
```

### Validation harness (`scripts/test.gd`)
- Attached to `scenes/test.tscn`; runs on `_ready()`.
- Exercises the expected behavior, then prints exactly one marker line:
  - `print("VALIDATION_PASSED: <msg>")` on success
  - `print("VALIDATION_FAILED: <reason>")` on failure
- The harness greps these markers (`ValidationParser`); no marker => FAIL.
- It must be **deterministic and self-contained** — instantiate scenes, call
  methods directly, assert state. Avoid wall-clock/random dependence.

## Workflow
1. Build the **ground-truth** project under a working dir, get `test.gd` to
   print `VALIDATION_PASSED` headlessly:
   `godot --headless --path <dir> res://scenes/test.tscn`
2. Derive the **starter** by removing the solution (the code/scene changes the
   instruction asks for) while keeping `test.gd` identical. Starter must FAIL.
3. Zip each as `task_XXXX/...` into `tasks_gt/task_XXXX.zip` and
   `tasks/task_XXXX.zip` (do not edit the zips in place — the guard hook blocks
   that; zip from the working dir).
4. Append `- task_XXXX` to `tasks.yaml`.
5. Verify: `uv run python validate_tasks.py --tasks task_XXXX` — ground truth
   must PASS.

> Tasks ship zipped specifically to prevent accidental train/eval leakage. Keep
> solutions out of the starter zip.
