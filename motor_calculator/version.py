"""Application and runtime schema version metadata."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


APPLICATION_NAME = "Motor Calculator"
APPLICATION_VERSION = "0.8.0"
RELEASE_CHANNEL = "engineering-preview"
RUNTIME_SCHEMA_VERSION = "phase8a.runtime.v1"


def get_git_commit(repository_root: Path | None = None) -> str | None:
    """Return the checked-out commit when Git metadata is genuinely available."""

    if getattr(sys, "frozen", False):
        return None
    root = Path(repository_root) if repository_root is not None else Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip().lower()
    if len(commit) == 40 and all(character in "0123456789abcdef" for character in commit):
        return commit
    return None


def application_version_label() -> str:
    return f"{APPLICATION_VERSION} ({RELEASE_CHANNEL})"
