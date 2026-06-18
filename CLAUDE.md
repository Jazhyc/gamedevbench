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

- `--enable-mcp` turns MCP on; `--mcp-server NAME` selects *which* server from
  the registry in `gamedevbench/src/mcp_registry.py` (default `screenshot`). Each
  entry is an `MCPServerSpec` (launch command/args/env + server id + prompt
  guidance); solvers translate a spec into their own config format. Add a new
  Godot-targeted server here so it's selectable and comparable against the
  baseline. Isolate each configuration's `results/` with `--run-name`.
- Registered servers:
  - `screenshot` — bundled, cross-platform baseline
    (`gamedevbench/src/mcp_server.py`, capture via `mss`). One tool,
    `godot-screenshot`.
  - `godot` — third-party Godot-targeted server
    [`@coding-solo/godot-mcp`](https://github.com/Coding-Solo/godot-mcp), run via
    `npx -y @coding-solo/godot-mcp` (needs Node ≥18). Exposes ~13 tools
    (run/stop project, get debug output, scene/node editing, version/project
    info, mesh-library export, UID management). `GODOT_PATH` is set from
    `GODOT_EXEC_PATH`/`GODOT_PATH`/`which godot`. Marked `prefetch=True`: the
    runner calls `MCPServerSpec.warm_up()` once (launches it with stdin closed;
    the stdio server exits on EOF) before dispatching workers so the npx
    download happens once, not per-worker, and isn't charged to a task timeout.
    Manual warm-up: `npx -y @coding-solo/godot-mcp < /dev/null`.
    ⚠️ Its `launch_editor` tool opens a real Godot **editor GUI window** (agents
    do call it); the windows pop onto the host display, can collide with a
    project you have open, and leak as orphaned processes. They're sandboxed
    (`cwd` under `/tmp/gamedevbench_sandbox_*`, not the repo) and safe to
    `pkill -f 'godot --editor'`. Run godot-mcp under `xvfb-run -a …` on Linux so
    those windows go to a throwaway virtual display.
- **Only the OpenHands solver honors a non-default `--mcp-server` so far** (it's
  DeepSeek's path); the other solvers still hardcode the `screenshot` baseline,
  so pairing `--mcp-server godot` with any other agent fails fast. Example:
  `--agent openhands --model deepseek-v4-pro --enable-mcp --mcp-server godot
  --run-name deepseek-godotmcp`.
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
  (`--agent`, `--model`, `--enable-mcp`, `--mcp-server`, `--use-runtime-video`,
  `--skip-display`, `--run-name`, `--resume[-from]`, `--workers`) + subcommands `list` / `open` /
  `validate` / `run`. `--gt` operates on ground-truth tasks.
  - `--workers N` (default 8) runs a `run --task-list` over **N tasks
    concurrently, each in its own process** — required because the agent solve
    step does a process-global `os.chdir` into its sandbox, so threads can't
    isolate it. Per-task sandboxes/validation dirs are already unique, and
    progress is checkpointed after each task (resume-safe). Forced to 1 only
    when the selected MCP server grabs a shared monitor
    (`MCPServerSpec.exclusive_display`, true for the `screenshot` baseline);
    headless servers like `godot` run as independent per-task processes, so
    parallelism stays on. DeepSeek-text runs have no display contention, so 8 is
    safe there too.
- `base_solver.py` — `BaseSolver` ABC. Subclasses set `SUPPORTS_MCP` /
  `SUPPORTS_SYSTEM_PROMPT` and implement `solve_task()` + `is_rate_limit_error()`.
- `solver_factory.py` — `SolverFactory._SOLVER_REGISTRY` maps agent name → solver
  class. **Add a new agent here** (or via `register_solver`). OpenHands is
  registered only on Python 3.12+.
- `*_solver.py` — one per agent (`claude_code`, `codex`, `gemini`, `openhands`,
  `mini_swe`). Solvers must honor `timeout_seconds` (= `TIMEOUT`, 600s): the
  OpenHands agent loop is bounded only by iteration count, so `openhands_solver`
  installs a watchdog that calls `conversation.pause()` at the deadline (a soft
  cap — a step already inside one LLM/tool call finishes first). Timed-out runs
  return `success=False`; their partial sandbox work is still validated.
- `mcp_registry.py` — registry of selectable MCP servers (`MCPServerSpec` +
  `get_mcp_server`/`available_mcp_servers`). `--mcp-server` picks one; solvers
  read `self.mcp_spec` to build their config and prompt guidance. Specs carry
  `exclusive_display` (forces `--workers 1`) and `prefetch` (one-time
  `warm_up()` before dispatch).
- `mcp_server.py` — the bundled Godot screenshot MCP server (registry entry
  `screenshot`). Launches the editor fullscreen on a screen and captures that
  monitor; cross-platform via `mss` (`GODOT_SCREENSHOT_DISPLAY`, 1-indexed,
  falls back to primary).
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
