from __future__ import annotations

import hashlib
from pathlib import Path

from validation.external_metric_comparison import (
    ComparabilityStatus,
    EvidenceType,
    ExternalMetricEvidence,
    MetricProvenance,
    SafeTransformation,
    compare_external_metric,
)
from validation.phase7c_reconstruction import build_phase7c_result, render_phase7c_report


REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_phase7c_inventory_covers_all_fourteen_blocked_rows() -> None:
    result = build_phase7c_result(REPO_ROOT)

    assert len(result.blockers) == 14
    assert result.before_counts == result.after_counts == {
        "DIRECT": 1,
        "SAFE_TRANSFORM": 0,
        "APPROXIMATE": 0,
        "BLOCKED": 14,
        "UNAVAILABLE": 6,
    }
    assert result.new_direct_rows == ()
    assert result.new_safe_transform_rows == ()


def test_price_current_and_torque_boundary_blockers_are_resolved_but_model_gap_remains() -> None:
    result = build_phase7c_result(REPO_ROOT)
    row = next(item for item in result.blockers if item.source_id.startswith("price") and item.metric == "torque_nm")

    before = {category.value for category in row.categories_before}
    after = {category.value for category in row.categories_after}
    assert "current_basis_unknown" in before
    assert "torque_boundary_unknown" in before
    assert after == {"model_input_not_supported"}
    assert row.fundamentally_blocked


def test_nonsinusoidal_rms_peak_conversion_remains_blocked() -> None:
    evidence = ExternalMetricEvidence(
        source_id="parviainen",
        source_title="Parviainen prototype",
        topology="DSSR AFPM",
        metric_name="back_emf_phase_rms_v",
        value=211.0,
        unit="V phase RMS",
        operating_point="300 rpm",
        quantity_scope="PM-induced phase voltage",
        value_kind="measured",
        waveform="flattened non-sinusoidal",
        winding_connection="star",
        current_basis="not applicable",
        provenance=MetricProvenance(
            source_url="https://lutpub.lut.fi/handle/10024/31185",
            page="p. 78",
            location="Figure 3.6",
            extraction_note="Measured waveform visibly flattened.",
        ),
        evidence_type=EvidenceType.MEASURED,
        uncertainty="not reported",
        comparability_status=ComparabilityStatus.SAFE_TRANSFORM,
        notes="test",
    )

    try:
        compare_external_metric(
            evidence, 298.0, "V phase peak",
            transformation=SafeTransformation.PHASE_RMS_TO_PHASE_PEAK_SINUSOIDAL,
        )
    except ValueError as exc:
        assert "sinusoidal" in str(exc)
    else:
        raise AssertionError("non-sinusoidal RMS/peak conversion must remain blocked")


def test_phase7c_generation_is_deterministic_and_does_not_mutate_production() -> None:
    protected = (
        REPO_ROOT / "motor_calculator" / "motor_core" / "calculations.py",
        REPO_ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json",
    )
    before = tuple(_sha256(path) for path in protected)
    first = build_phase7c_result(REPO_ROOT)
    second = build_phase7c_result(REPO_ROOT)

    assert first == second
    assert render_phase7c_report(first) == render_phase7c_report(second)
    assert tuple(_sha256(path) for path in protected) == before
    assert before[1] == "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"
