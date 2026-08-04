from __future__ import annotations

import hashlib
from pathlib import Path

from validation.phase7a_baseline import BaselineOutcome, build_phase7a_baseline, render_phase7a_report


REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_creator_topology_mismatch_stays_blocked() -> None:
    result = build_phase7a_baseline(REPO_ROOT)
    creator_rows = [row for row in result.rows if row.benchmark == "creator_pmsm_initial_record"]

    assert creator_rows
    assert all(row.outcome is BaselineOutcome.BLOCKED for row in creator_rows)
    assert any("Topology mismatch" in row.notes for row in creator_rows)
    assert all(row.metrics.prediction is None for row in creator_rows)


def test_baseline_does_not_mutate_source_data_or_legacy_baseline() -> None:
    root = REPO_ROOT
    monitored = (
        root / "validation_data" / "imported" / "creator_pmsm_initial_record.json",
        root / "motor_calculator" / "tests" / "fixtures" / "pmsm_reference_cases.json",
        root / "motor_calculator" / "tests" / "fixtures" / "bldc_reference_cases.json",
        root / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json",
    )
    before = tuple(_sha256(path) for path in monitored)

    build_phase7a_baseline(root)

    assert tuple(_sha256(path) for path in monitored) == before


def test_baseline_runner_is_deterministic() -> None:
    first = build_phase7a_baseline(REPO_ROOT)
    second = build_phase7a_baseline(REPO_ROOT)

    assert first == second
    assert render_phase7a_report(first) == render_phase7a_report(second)


def test_internal_references_pass_without_becoming_external_claims() -> None:
    result = build_phase7a_baseline(REPO_ROOT)
    internal_rows = [row for row in result.rows if row.outcome is BaselineOutcome.INTERNAL_PASS]

    assert len(internal_rows) == 24
    assert all("not external accuracy evidence" in row.notes for row in internal_rows)
