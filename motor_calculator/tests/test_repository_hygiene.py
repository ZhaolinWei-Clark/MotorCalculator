"""Repository hygiene: solver artifacts must never enter the history.

Phase 10D and Phase 10E each staged tens of megabytes of FEMM workspace before
the mistake was caught by eye. The ignore rules were per-phase, so every new
phase re-opened the same hole. These tests close it: the rules are now a glob,
and the invariant is asserted rather than remembered.

The repository's own release strategy states the boundary -- derived evidence is
committed, binaries and solver artifacts are not -- so this is enforcing a stated
policy, not inventing one.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: Extensions a solver produces that must never be tracked.
SOLVER_ARTIFACT_SUFFIXES = (".ans", ".fem")

#: Anything tracked above this is almost certainly an artifact rather than
#: source, evidence or documentation.
LARGE_FILE_BYTES = 1_500_000


def _tracked_files() -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(REPOSITORY_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("git is unavailable in this environment")
    return tuple(
        REPOSITORY_ROOT / name
        for name in result.stdout.split("\0")
        if name
    )


def test_no_solver_artifact_is_tracked():
    offenders = [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in _tracked_files()
        if path.suffix.lower() in SOLVER_ARTIFACT_SUFFIXES
    ]
    assert not offenders, f"solver artifacts must not be committed: {offenders}"


def test_no_femm_workspace_directory_is_tracked():
    offenders = [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in _tracked_files()
        if "femm_workspace" in path.as_posix()
    ]
    assert not offenders, f"solver workspaces must not be committed: {offenders}"


def test_the_ignore_rule_is_a_glob_not_one_entry_per_phase():
    """A per-phase rule silently stops protecting the next phase."""

    ignore = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "work/*/femm_workspace/" in ignore
    for suffix in SOLVER_ARTIFACT_SUFFIXES:
        assert f"*{suffix}" in ignore


def test_a_new_phase_workspace_would_be_ignored_without_any_edit():
    """The rule must already cover a phase that does not exist yet."""

    candidate = "work/phase99z/femm_workspace/scratch.csv"
    result = subprocess.run(
        ["git", "check-ignore", "-q", candidate],
        cwd=str(REPOSITORY_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 128:
        pytest.skip("git is unavailable in this environment")
    assert result.returncode == 0, f"{candidate} would not be ignored"


def test_no_tracked_file_is_unexpectedly_large():
    offenders = [
        (path.relative_to(REPOSITORY_ROOT).as_posix(), path.stat().st_size)
        for path in _tracked_files()
        if path.is_file() and path.stat().st_size > LARGE_FILE_BYTES
    ]
    assert not offenders, (
        "large files inflate the history permanently; use GitHub Releases or "
        f"keep them local: {offenders}"
    )
