---
name: run-benchmark
description: Run GameDevBench against an agent/model on a task list, or validate ground truths. Use when asked to run the benchmark, evaluate an agent/model, score tasks, or compare configurations (e.g. Godot-specific MCP vs generic tools).
disable-model-invocation: true
---

# Run GameDevBench

Evaluate an agent on the 333 Godot tasks. **User-only** — these commands launch
long, billable agent runs.

## Preconditions
- Tasks unzipped: `bash unzip_tasks.sh` (creates `tasks/task_XXXX/` and `tasks_gt/task_XXXX/`).
- Godot 4.x on `PATH` or `GODOT_EXEC_PATH` set.
- API keys in `.env` (copied from `.env.example`) for whichever agent you run.
- Dependencies synced: `uv sync`.

## Canonical run

```bash
uv run python gamedevbench/src/benchmark_runner.py \
  --agent AGENT --model MODEL \
  run --task-list tasks.yaml
```

`--agent` choices come from the solver registry: `claude-code`, `codex`,
`gemini-cli`, `mini-swe`, and `openhands` (Python 3.12+ only). A single task:
`run task_0002` instead of `run --task-list tasks.yaml`.

### Flags that matter
| Flag | Effect |
|------|--------|
| `--model` | claude-code: model id; mini-swe: `claude`/`gpt`; openhands/gemini-cli: model id; ignored for codex |
| `--enable-mcp` | Enable an MCP server for supported solvers (`SUPPORTS_MCP`). The bundled screenshot server is **cross-platform** (Windows/macOS/Linux via mss). This is the flag to use when comparing Godot-specific MCPs vs generic tooling — see CLAUDE.md. |
| `--use-runtime-video` | Append Godot runtime (render-to-image/movie) instructions to the prompt |
| `--skip-display` | Skip tasks with `requires_display=true` |
| `--run-name NAME` | Isolate outputs under `results/<NAME>/` — use a descriptive name per config so runs don't collide |
| `--resume` / `--resume-from FILE` | Continue a prior run; `--resume-from` redoes only failed tasks |

> When benchmarking a new MCP integration, give each configuration its own
> `--run-name` (e.g. `--run-name godot-mcp` vs `--run-name baseline`) so results
> stay comparable.

## Validate ground truths (cheap sanity check, no agent/API)
Every ground truth must PASS. Run after install or when changing the harness:

```bash
uv run python validate_tasks.py            # all 333 in parallel
uv run python validate_tasks.py --tasks task_0002 task_0021
```

## Results
One JSON per task in `results/` (or `results/<run_name>/`) with success,
tokens, cost, duration; `results/leaderboard.csv` summarizes configurations.
