#!/usr/bin/env python3
"""PreToolUse guard: block access to secrets and edits to packaged task archives.

Reads the hook payload from stdin, inspects the target path, and blocks
(exit code 2) when the tool would touch a protected file. Stdlib only so it
runs under any system Python without the project venv.
"""
import json
import sys
from pathlib import PurePath


def _deny(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)  # exit 2 => block the tool call, feed stderr back to the agent


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # never block on a malformed payload

    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    raw = ti.get("file_path") or ti.get("notebook_path") or ""
    if not raw:
        sys.exit(0)

    p = PurePath(str(raw).replace("\\", "/"))
    name = p.name
    parts = set(p.parts)

    # 1) Secrets: block any access to .env (the committed .env.example is fine).
    if name == ".env" or (name.startswith(".env") and not name.endswith(".example")):
        _deny(
            f"Blocked: '{name}' holds live API keys (gitignored). Do not read or "
            "edit it. Use .env.example as the template instead."
        )

    # 2) Benchmark integrity: block edits to the packaged task/ground-truth zips.
    is_write = tool in ("Edit", "Write", "MultiEdit", "NotebookEdit")
    if is_write and name.endswith(".zip") and ({"tasks", "tasks_gt"} & parts):
        _deny(
            f"Blocked: '{p}' is a packaged benchmark task (ground-truth boundary). "
            "Editing it risks data leakage/contamination. Work on an unzipped copy "
            "and re-zip deliberately, or author a NEW task via the new-task skill."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
