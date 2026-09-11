"""Application and runtime schema version metadata."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import re


APPLICATION_NAME = "MotorCalculator"
APPLICATION_DISPLAY_NAME_ZH_CN = "电机设计计算器"
APPLICATION_PUBLISHER = "MotorCalculator Project"
APPLICATION_ID = "{A5F90D43-686B-4DDB-9F67-CF96B7A4A33D}"
APPLICATION_VERSION = "1.0.0-rc4"
RELEASE_CHANNEL = "release-candidate"
RUNTIME_SCHEMA_VERSION = "phase8a.runtime.v1"
RELEASE_MANIFEST_SCHEMA_VERSION = 1


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


def windows_version_tuple() -> tuple[int, int, int, int]:
    """Return the numeric Windows resource version derived from the app version."""

    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-rc(\d+))?", APPLICATION_VERSION)
    if match is None:
        raise ValueError(f"Unsupported application version: {APPLICATION_VERSION}")
    major, minor, patch, release_candidate = match.groups()
    return int(major), int(minor), int(patch), int(release_candidate or 0)
