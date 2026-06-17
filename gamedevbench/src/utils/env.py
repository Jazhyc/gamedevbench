#!/usr/bin/env python3
"""Load the project's .env so the keys documented in .env.example actually
land in os.environ. The harness reads credentials (and GODOT_EXEC_PATH)
straight from the environment, so without this a .env file is ignored.
"""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# .../gamedevbench/src/utils/env.py -> parents[3] is the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_project_env(path: Optional[Path] = None) -> bool:
    """Load KEY=VALUE pairs from the project's .env into os.environ.

    Existing environment variables win (override=False), so an explicitly
    exported variable is never clobbered by .env. Returns True if a .env file
    was found and read.
    """
    env_path = Path(path) if path is not None else _PROJECT_ROOT / ".env"
    return load_dotenv(dotenv_path=env_path, override=False)
