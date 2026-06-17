#!/usr/bin/env python3
"""Stop hook: remind the agent to commit each feature individually and keep
CLAUDE.md current before ending the turn.

Fires at most once per stop cycle (guarded by stop_hook_active) and only when
the working tree has uncommitted changes. Stdlib only.
"""
import json
import subprocess
import sys
from pathlib import Path

CLAUDE_MD_SOFT_LIMIT = 400  # lines; beyond this, suggest splitting into docs/


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Avoid loops: if we already reminded once this cycle, let the agent stop.
    if data.get("stop_hook_active"):
        sys.exit(0)

    cwd = data.get("cwd") or "."
    try:
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=cwd, timeout=15,
        ).stdout.strip()
    except Exception:
        sys.exit(0)  # not a git repo / git unavailable -> don't block

    if not porcelain:
        sys.exit(0)  # clean tree, nothing to remind about

    changed = [ln[3:] for ln in porcelain.splitlines() if ln[3:]]
    preview = ", ".join(changed[:8]) + (" ..." if len(changed) > 8 else "")

    lines = [
        "Uncommitted changes before stopping (project convention):",
        f"  Changed: {preview}",
        "  - Commit each feature on its own as a focused, individual commit.",
        "  - Update CLAUDE.md in the SAME commit when the feature changes how the",
        "    project is built, run, or extended (new agent/solver, new MCP, new flow).",
    ]

    claude_md = Path(cwd) / "CLAUDE.md"
    try:
        n = sum(1 for _ in claude_md.open(encoding="utf-8"))
        if n > CLAUDE_MD_SOFT_LIMIT:
            lines.append(
                f"  - CLAUDE.md is {n} lines (> {CLAUDE_MD_SOFT_LIMIT}). Move detailed "
                "reference into docs/*.md and keep CLAUDE.md a lean index."
            )
    except OSError:
        pass

    lines.append("  If already committed or intentionally WIP, just stop again.")
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)  # exit 2 => block stop, feed the reminder back to the agent


if __name__ == "__main__":
    main()
