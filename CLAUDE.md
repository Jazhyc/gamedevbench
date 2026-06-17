# GameDevBench

Benchmark for evaluating LLM agents on **Godot 4.x** game-development tasks (333
tasks, ICML 2026). The harness runs a pluggable *agent* (Claude Code, Codex,
Gemini CLI, OpenHands, mini-SWE) against each task and scores it by running a
headless Godot validation scene. Python 3.10+ (3.12+ for OpenHands), managed
with `uv`.

## Active goal: Godot-specific MCP servers vs. generic tooling

We are extending the harness to support **MCP servers that specifically target
Godot development** and measuring how they stack up against generic, non-Godot
tooling. Concretely:

- The current `--enable-mcp` path wires in one bundled, cross-platform
  screenshot MCP server (`gamedevbench/src/mcp_server.py`, capture via `mss`).
  Treat that as the *baseline* MCP integration to generalize from.
- New Godot-targeted MCP servers should be selectable per run and isolated with
  `--run-name` so each configuration's `results/` are directly comparable
  against a generic/no-MCP baseline.
- When you add an MCP integration, record what it exposes and how to run it
  here (or in `docs/` — see Conventions) so comparisons stay reproducible.

## Setup & commands

```bash
uv sync                                   # install deps
uv sync --extra dev                       # + test deps (pytest, pytest-mock)
bash unzip_tasks.sh                       # tasks/task_XXXX/ + tasks_gt/task_XXXX/
uv run pytest                             # fast offline regression suite (no Godot/API/display)
uv run python validate_tasks.py           # sanity: all 333 ground truths must PASS
```

`tests/` holds the offline unit suite (solver factory, prompts, validation
parsing, cost math, the cross-platform mss capture with mss mocked, and the
guardrail hooks). It needs no Godot, API keys, or display — run it before every
commit to catch regressions. Heavier end-to-end checks stay in
`validate_tasks.py` (needs Godot).

Run the benchmark (long, billable — prefer the **/run-benchmark** skill):

```bash
uv run python gamedevbench/src/benchmark_runner.py \
  --agent AGENT --model MODEL run --task-list tasks.yaml
```

Godot must be on `PATH` or `GODOT_EXEC_PATH`. API keys live in `.env` (template:
`.env.example`). Authoring a new task: use the **/new-task** skill.

## Architecture

- `gamedevbench/src/benchmark_runner.py` — CLI + orchestration. Global flags
  (`--agent`, `--model`, `--enable-mcp`, `--use-runtime-video`, `--skip-display`,
  `--run-name`, `--resume[-from]`, `--workers`) + subcommands `list` / `open` /
  `validate` / `run`. `--gt` operates on ground-truth tasks.
  - `--workers N` (default 8) runs a `run --task-list` over **N tasks
    concurrently, each in its own process** — required because the agent solve
    step does a process-global `os.chdir` into its sandbox, so threads can't
    isolate it. Per-task sandboxes/validation dirs are already unique, and
    progress is checkpointed after each task (resume-safe). Forced to 1 when
    `--enable-mcp` is set (the screenshot server grabs a whole monitor, so
    parallel runs would collide). DeepSeek-text runs have no display contention,
    so 8 is safe there.
- `base_solver.py` — `BaseSolver` ABC. Subclasses set `SUPPORTS_MCP` /
  `SUPPORTS_SYSTEM_PROMPT` and implement `solve_task()` + `is_rate_limit_error()`.
- `solver_factory.py` — `SolverFactory._SOLVER_REGISTRY` maps agent name → solver
  class. **Add a new agent here** (or via `register_solver`). OpenHands is
  registered only on Python 3.12+.
- `*_solver.py` — one per agent (`claude_code`, `codex`, `gemini`, `openhands`,
  `mini_swe`).
- `mcp_server.py` — the bundled Godot screenshot MCP server. Launches the editor
  fullscreen on a screen and captures that monitor; cross-platform via `mss`
  (`GODOT_SCREENSHOT_DISPLAY`, 1-indexed, falls back to primary).
- `utils/prompts.py` — `load_task_config()` + `create_task_prompt()`; prompt
  text for runtime-video and MCP guidance is injected here.
- `utils/validation.py` — `ValidationParser` greps Godot output for
  `VALIDATION_PASSED:` / `VALIDATION_FAILED:` markers.

### Task layout
`tasks/task_XXXX.zip` (starter) and `tasks_gt/task_XXXX.zip` (ground truth) each
extract to `task_XXXX/` containing `project.godot`, `task_config.json`
(`task_id`, `name`, `instruction`, `metadata`), the game scenes/scripts/assets,
and a `scenes/test.tscn` + `scripts/test.gd` validation harness. `tasks.yaml`
lists the active task ids. Tasks ship zipped to prevent train/eval leakage.

## Conventions

- **Commit each feature individually.** One focused commit per feature/change,
  not a batch. When a feature changes how the project is built, run, or extended
  (new agent/solver, new MCP integration, new flag/flow), **update CLAUDE.md in
  the same commit**. A Stop hook reminds you if you try to finish with
  uncommitted changes.
- **Test every new feature.** When adding a feature, add or update tests in
  `tests/` for it and run `uv run pytest` (must pass) before committing — keep
  it green so the suite stays a reliable regression guard.
- **Keep CLAUDE.md lean.** When it grows past ~400 lines, move detailed
  reference into `docs/*.md` and leave a one-line pointer here. The Stop hook
  flags this automatically.
- **Never read or edit `.env`** (live API keys, gitignored) — use `.env.example`.
  **Never edit the packaged `tasks/` or `tasks_gt/` zips in place** — author new
  tasks via the new-task skill and re-zip from a working dir. A PreToolUse guard
  hook (`.claude/hooks/guard_sensitive.py`) blocks both.
- Ground truths are the integrity baseline: after any harness change, run
  `validate_tasks.py` and keep all 333 passing.
