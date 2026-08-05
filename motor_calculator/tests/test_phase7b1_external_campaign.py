from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from validation.external_metric_comparison import ComparabilityStatus, ComparisonOutcome
from validation.phase7b1_campaign import build_phase7b1_campaign, render_phase7b1_report


REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_campaign_has_one_narrow_direct_external_afpm_row() -> None:
    result = build_phase7b1_campaign()
    direct = [row for row in result.rows if row.evidence.comparability_status is ComparabilityStatus.DIRECT]

    assert len(result.rows) == 21
    assert len(direct) == 1
    assert direct[0].evidence.source_id == "parviainen_2005_afpm_prototype"
    assert direct[0].evidence.metric_name == "rated_torque_nm"
    assert direct[0].model_prediction == pytest.approx(159.15494309189535)
    assert direct[0].normalized_reference == 159.0
    assert direct[0].metrics.absolute_percentage_error == pytest.approx(0.09744848546877132)
    assert direct[0].outcome is ComparisonOutcome.PASS
    assert "not electromagnetic torque-current validation" in direct[0].evidence.notes


def test_campaign_counts_blockers_without_downgrading_them() -> None:
    result = build_phase7b1_campaign()

    assert result.comparability_counts == {
        "DIRECT": 1,
        "SAFE_TRANSFORM": 0,
        "APPROXIMATE": 0,
        "BLOCKED": 14,
        "UNAVAILABLE": 6,
    }
    assert result.outcome_counts == {
        "PASS": 1,
        "WARNING": 0,
        "FAIL": 0,
        "APPROXIMATE": 0,
        "BLOCKED": 14,
        "UNAVAILABLE": 6,
    }


def test_campaign_and_report_are_deterministic() -> None:
    first = build_phase7b1_campaign()
    second = build_phase7b1_campaign()

    assert first == second
    assert render_phase7b1_report(first) == render_phase7b1_report(second)
    assert "Parviainen" in render_phase7b1_report(first)


def test_campaign_preserves_production_and_legacy_files() -> None:
    protected = (
        REPO_ROOT / "motor_calculator" / "motor_core" / "calculations.py",
        REPO_ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json",
    )
    before = tuple(_sha256(path) for path in protected)

    build_phase7b1_campaign()

    assert tuple(_sha256(path) for path in protected) == before
    assert before[1] == "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"


def test_each_row_keeps_field_level_provenance() -> None:
    result = build_phase7b1_campaign()

    assert all(row.evidence.provenance.source_url.startswith("http") for row in result.rows)
    assert all(row.evidence.provenance.page for row in result.rows)
    assert all(row.evidence.provenance.location for row in result.rows)
    assert all(row.evidence.provenance.extraction_note for row in result.rows)
    assert all(row.evidence.confidence for row in result.rows)
