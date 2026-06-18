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
  - `godot-tugcan` — second Godot-targeted server
    [`@tugcantopaloglu/godot-mcp`](https://github.com/tugcantopaloglu/godot-mcp),
    run via `npx -y @tugcantopaloglu/godot-mcp` (npm-published, bin `godot-mcp`;
    needs Node ≥18). Exposes a much larger tool set (~149: scene/node editing,
    run/debug output, screenshots, plus rendering/physics/audio/animation).
    Same `GODOT_PATH` resolution and `prefetch`/headless config as `godot`. Its
    runtime `game_*` tools require a `McpInteractionServer` autoload the
    benchmark projects don't ship, so only the headless tools apply; prompt
    guidance steers agents to those. Manual warm-up:
    `npx -y @tugcantopaloglu/godot-mcp < /dev/null`.
    ⚠️ Like `godot`, GUI-opening tools should run under `xvfb-run -a …` on Linux.
  - `godot-ai` — [`hi-godot/godot-ai`](https://github.com/hi-godot/godot-ai),
    structurally different from the others: it's a Godot **editor plugin** (not a
    standalone stdio server) that spawns a Python FastMCP server the agent
    reaches over **HTTP**, bridged to a *live editor* over a WebSocket. So the
    spec uses `transport="http"` + `needs_godot_editor=True`; `command`/`args`
    (`uvx godot-ai==<ver>`) only prime the package cache in `warm_up`. For each
    task the OpenHands solver runs a per-task editor lifecycle via
    `godot_ai_editor.py`: cache the pinned addon (shallow clone of tag `v<ver>`,
    reused across runs; override the cache dir with `GAMEDEVBENCH_GODOT_AI_CACHE`)
    **patched so its server ports come from env vars** (stock godot-ai reads
    them only from global EditorSettings), install it into the sandbox + enable
    the plugin, launch the editor under `xvfb-run` on a **per-task free port pair
    with `XDG_CONFIG_HOME`/`XDG_DATA_HOME` isolated** to a throwaway dir, poll
    `editor_state` until `readiness==ready` (the agent's MCP URL is the session's
    `http_url`), then tear down: killpg the editor group (reaps the `Xvfb` that
    `xvfb-run` would orphan), **explicitly reap the detached server** via its
    `user://godot_ai_server.pid` pid-file under the isolated data dir (the editor's
    killpg doesn't reach it), and **strip the plugin footprint** from the sandbox
    — the addon dir, the `[editor_plugins]` enable entry, and the
    `_mcp_game_helper` autoload the plugin injects into `project.godot` — so the
    agent's work is scored in a clean project (that autoload otherwise runs during
    headless validation). Exposes ~41 tools / ~120 ops (scene/node/script/signal
    editing, run+debug, screenshot, UI/material/animation/etc.) operating on the
    live editor. **Runs in parallel** (`--workers N`): each task's editor has its
    own ports + isolated editor state, so unlike the screenshot baseline it does
    NOT force `--workers 1`. Notes: its server **phones home telemetry** by
    default — the spec env sets `GODOT_AI_DISABLE_TELEMETRY=1`/`DISABLE_TELEMETRY=1`;
    the plugin self-disables under a true `--headless` editor unless
    `GODOT_AI_ALLOW_HEADLESS=1` (so we use `xvfb`). Each worker runs a full Godot
    editor GUI under xvfb + a Python server, so it's heavy — moderate `--workers`
    (e.g. 4–8), not 64. Manual warm-up: `uvx --from godot-ai==<ver> godot-ai --version`.
  - The `godot` server's `launch_editor` tool opens a real Godot **editor GUI window** (agents
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
  `--encourage-verification`, `--skip-display`, `--run-name`, `--resume[-from]`,
  `--workers`) + subcommands `list` / `open` /
  `validate` / `run`. `--gt` operates on ground-truth tasks.
  - `--encourage-verification` is a **prompt-only experiment condition**
    (orthogonal to MCP — combine with baseline or any server, isolate with
    `--run-name`). It appends a *light, open-ended* nudge
    (`VERIFICATION_NUDGE_GUIDANCE` in `utils/prompts.py`) telling the agent to
    turn the spec into observable behaviours, write a throwaway GDScript test,
    run it headlessly, and fix the implementation until it passes — but
    deliberately ships **no script template or introspection idioms**, so a
    measured effect is attributable to the verification behaviour rather than to
    teaching the validator's technique. Motivation: baseline trajectories show
    agents almost never self-verify (~84% only compile-check; the real
    `test.tscn` grader is withheld from the sandbox by `should_skip_file`), and
    ~95% of failures are runnable-but-wrong code. Gated to solvers with
    `SUPPORTS_VERIFICATION_NUDGE` (**OpenHands only** — DeepSeek's path);
    requesting it for any other agent fails fast. Example: `--agent openhands
    --model deepseek-v4-pro --encourage-verification --run-name
    deepseek-verify`.
  - **Sandbox import cache:** `_create_sandbox_environment` ends by calling
    `_build_sandbox_import_cache`, a one-time headless `--editor --quit` warm-up
    (`SANDBOX_IMPORT_TIMEOUT`, best-effort) that builds the sandbox's `.godot/`
    (imported-asset cache + `global_script_class_cache.cfg`). A fresh sandbox
    has none (starters don't ship it; dot-dirs are skipped on copy), so without
    this an agent's own `godot --headless` run hits missing imported assets and
    unresolved custom-`class_name` scene roots ("scene fails to load"). This
    matters most for the `--encourage-verification` condition, which induces
    agents to load scenes headless. ⚠️ It changes the agent's environment for
    **all** runs, so pass@1 may shift vs. historical baselines (re-run the
    baseline on the warmed sandbox for a clean A/B). Verified empirically:
    cold load emits `Unable to open file: res://.godot/imported/…` /
    `[ext_resource] referenced non-existent resource`; after warm-up the same
    scene loads clean.
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
  cap — a step already inside one LLM/tool call finishes first). A step wedged
  inside a child subprocess (e.g. a hung MCP/godot tool call) never reaches a
  loop boundary, so a second **hard cap** `HARD_CAP_GRACE` seconds later (30s,
  in `constants.py`) kills the worker's descendant process tree
  (`_terminate_process_tree`, via `psutil`); closing those pipes unwedges
  `run()` so one hung subprocess can't strand the worker — and the whole
  `ProcessPoolExecutor` — indefinitely. Timed-out runs return `success=False`;
  their partial sandbox work is still validated.
- `mcp_registry.py` — registry of selectable MCP servers (`MCPServerSpec` +
  `get_mcp_server`/`available_mcp_servers`). `--mcp-server` picks one; solvers
  read `self.mcp_spec` to build their config and prompt guidance. Specs carry
  `prefetch` (one-time `warm_up()` before dispatch); `transport`
  (`"stdio"`/`"http"`) + `http_url` for how the agent reaches the server; and
  `needs_godot_editor` for plugin-backed servers. `requires_single_worker`
  (true only for `exclusive_display`) forces `--workers 1` — `needs_godot_editor`
  servers run in parallel (per-task ports + isolated editor state).
- `godot_ai_editor.py` — per-task editor lifecycle for the `godot-ai` server
  (`ensure_addon` + `_patch_addon_env_ports`, `install_addon`/`enable_plugin_text`,
  `free_port`, `wait_until_ready`, `cleanup_project_footprint`, `_reap_servers`,
  `GodotAiEditorSession`): caches+patches+installs the addon, launches the editor
  under `xvfb` on a per-task free port pair with isolated `XDG_CONFIG_HOME`/
  `XDG_DATA_HOME`, waits for `editor_state` readiness, and on exit killpg's the
  editor group, reaps the detached server by pid-file, and strips the footprint.
  Driven by the OpenHands solver; the runner pre-clones the addon once (parallel
  workers don't race the clone).
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
