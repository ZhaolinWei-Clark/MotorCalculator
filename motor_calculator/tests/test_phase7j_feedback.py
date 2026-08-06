from __future__ import annotations

import json
from pathlib import Path

import pytest

from motor_calculator.validation.feedback_aggregation import (
    aggregate_feedback,
    build_validation_summary,
    compare_feedback_to_uncertainty_envelope,
)
from motor_calculator.validation.feedback_models import (
    BiasCandidateStatus,
    DuplicateStatus,
    EnvelopePosition,
    EvidenceQuality,
    ExternalValidationCoverage,
    FeedbackComparability,
    FeedbackFormModel,
    FeedbackModelIdentity,
    FeedbackOperatingPoint,
    FeedbackSubmission,
    MetricSemantics,
    ValidationEvidenceType,
)
from motor_calculator.validation.feedback_service import (
    assess_metric_compatibility,
    hash_input_snapshot,
    load_feedback_records,
    serialize_feedback,
    submit_feedback,
)
from motor_calculator.validation.phase7j_feedback_demo import run_phase7j_demo


ROOT = Path(__file__).resolve().parents[2]
CALCULATIONS_PATH = ROOT / "motor_calculator" / "motor_core" / "calculations.py"
LEGACY_PATH = ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json"


def _semantics(**changes) -> MetricSemantics:
    values = {
        "quantity_scope": "phase",
        "rms_peak_semantics": "rms",
        "waveform_semantics": "sinusoidal",
        "torque_boundary": "not_applicable",
        "current_basis": "phase_rms",
    }
    values.update(changes)
    return MetricSemantics(**values)


def _submission(**changes) -> FeedbackSubmission:
    values = {
        "metric_name": "back_emf_phase_fundamental_rms_v",
        "predicted_value": 33.0,
        "reference_value": 30.0,
        "predicted_unit": "V",
        "reference_unit": "V",
        "predicted_semantics": _semantics(),
        "reference_semantics": _semantics(),
        "operating_point": FeedbackOperatingPoint(1000.0, current_a=0.0, temperature_c=20.0),
        "evidence_type": ValidationEvidenceType.BENCH_MEASUREMENT,
        "model_identity": FeedbackModelIdentity(
            calculator_version="test-calculator",
            model_version="test-model-v1",
            model_track="advanced_afpm_sandbox",
            topology="SSDR",
            software_version="test-software",
            git_commit="abc123",
            model_family="advanced_afpm",
            calculation_mode="no_load_back_emf",
            origin="sandbox",
            formula_version="test-formula-v1",
        ),
        "full_input_snapshot": {
            "topology": "SSDR",
            "pole_pairs": 5,
            "turns_per_phase": 100,
            "winding_connection": "Y",
            "winding_factor": 0.933,
            "magnet_remanence_t": 1.2,
            "air_gap_m": 0.001,
            "magnet_thickness_m": 0.005,
            "rated_speed_rpm": 1000.0,
        },
        "source_name": "Traceable laboratory",
        "source_reference": "Test report TR-001",
        "notes": "Controlled test fixture evidence.",
    }
    values.update(changes)
    return FeedbackSubmission(**values)


def _store(tmp_path: Path) -> Path:
    return tmp_path / "feedback_records.jsonl"


def test_feedback_record_creation_preserves_identity_and_snapshot(tmp_path: Path):
    result = submit_feedback(_submission(), _store(tmp_path), record_id="record-001")
    record = result.record
    assert record.record_id == "record-001"
    assert record.model_version == "test-model-v1"
    assert record.full_input_snapshot["pole_pairs"] == 5
    assert record.comparability is FeedbackComparability.DIRECT
    assert len(record.input_snapshot_hash) == len(record.record_content_hash) == 64


def test_feedback_error_calculation_is_signed_and_near_zero_safe(tmp_path: Path):
    record = submit_feedback(_submission(), _store(tmp_path)).record
    assert record.signed_error == pytest.approx(3.0)
    assert record.absolute_error == pytest.approx(3.0)
    assert record.relative_error == pytest.approx(0.1)
    assert record.absolute_percentage_error == pytest.approx(10.0)

    zero = submit_feedback(
        _submission(reference_value=0.0, source_reference="TR-zero"), _store(tmp_path)
    ).record
    assert zero.signed_error == pytest.approx(33.0)
    assert zero.relative_error is None
    assert zero.absolute_percentage_error is None


def test_incompatible_metric_semantics_are_stored_but_error_is_blocked(tmp_path: Path):
    submission = _submission(
        reference_semantics=_semantics(
            quantity_scope="line",
            waveform_semantics="unknown",
        )
    )
    record = submit_feedback(submission, _store(tmp_path)).record
    assert record.comparability is FeedbackComparability.BLOCKED
    assert record.normalized_reference_value is None
    assert record.signed_error is None
    assert any("incompatible" in message for message in record.validation_messages)


def test_approved_sinusoidal_safe_transform_is_explicit():
    submission = _submission(
        predicted_semantics=_semantics(rms_peak_semantics="peak"),
        reference_semantics=_semantics(rms_peak_semantics="rms"),
    )
    result = assess_metric_compatibility(submission)
    assert result.status is FeedbackComparability.SAFE_TRANSFORM
    assert result.safe_transformation == "phase_rms_to_phase_peak_sinusoidal"
    assert result.normalized_reference_value == pytest.approx(30.0 * 2.0 ** 0.5)


def test_input_snapshot_hash_is_order_independent_and_deterministic():
    first = {"b": 2, "a": {"y": 4, "x": 3}}
    second = {"a": {"x": 3, "y": 4}, "b": 2}
    assert hash_input_snapshot(first) == hash_input_snapshot(second)


def test_generated_record_ids_are_unique(tmp_path: Path):
    first = submit_feedback(_submission(), _store(tmp_path)).record
    second = submit_feedback(
        _submission(source_reference="TR-002"), _store(tmp_path)
    ).record
    assert first.record_id != second.record_id


def test_jsonl_storage_appends_without_overwriting_and_round_trips(tmp_path: Path):
    path = _store(tmp_path)
    first = submit_feedback(_submission(), path, record_id="append-1").record
    first_serialized = serialize_feedback(first)
    submit_feedback(
        _submission(source_reference="TR-append-2"), path, record_id="append-2"
    )
    assert path.read_text(encoding="utf-8").splitlines()[0] == first_serialized
    loaded = load_feedback_records(path)
    assert [record.record_id for record in loaded] == ["append-1", "append-2"]


def test_duplicate_detection_warns_without_deleting_evidence(tmp_path: Path):
    path = _store(tmp_path)
    first = submit_feedback(_submission(), path, record_id="duplicate-1")
    second = submit_feedback(_submission(), path, record_id="duplicate-2")
    assert first.duplicate_status is DuplicateStatus.UNIQUE
    assert second.duplicate_status is DuplicateStatus.POSSIBLE_DUPLICATE
    assert len(load_feedback_records(path)) == 2


def test_existing_record_id_is_rejected_without_overwrite(tmp_path: Path):
    path = _store(tmp_path)
    submit_feedback(_submission(), path, record_id="fixed-id")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="record_id already exists"):
        submit_feedback(_submission(), path, record_id="fixed-id")
    assert path.read_bytes() == before


def test_record_content_hash_detects_tampering(tmp_path: Path):
    path = _store(tmp_path)
    submit_feedback(_submission(), path, record_id="tamper-test")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["reference_value"] = 999.0
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="record content hash mismatch"):
        load_feedback_records(path)


def test_evidence_quality_logic_preserves_unverified_demo_and_high_traceable_data(tmp_path: Path):
    high = submit_feedback(_submission(), _store(tmp_path)).record
    demo = submit_feedback(
        _submission(
            source_name="SYNTHETIC_DEMO_ONLY",
            source_reference="demo",
            notes="Synthetic demo",
        ),
        _store(tmp_path),
    ).record
    assert high.evidence_quality is EvidenceQuality.HIGH
    assert demo.evidence_quality is EvidenceQuality.UNVERIFIED


def test_aggregation_statistics_and_small_sample_warning(tmp_path: Path):
    path = _store(tmp_path)
    records = [
        submit_feedback(
            _submission(reference_value=reference, source_reference=f"TR-{index}"),
            path,
            record_id=f"aggregate-{index}",
        ).record
        for index, reference in enumerate((30.0, 31.0, 32.0), start=1)
    ]
    aggregate = aggregate_feedback(records)[0]
    assert aggregate.record_count == 3
    assert aggregate.mean_absolute_percentage_error is not None
    assert aggregate.p10_signed_percentage_error <= aggregate.p50_signed_percentage_error
    assert aggregate.p50_signed_percentage_error <= aggregate.p90_signed_percentage_error
    assert aggregate.warnings == ("VERY_LIMITED_EVIDENCE",)
    assert aggregate.bias_candidate.status is BiasCandidateStatus.POSSIBLE_POSITIVE_BIAS


def test_single_record_is_insufficient_for_aggregate_interpretation(tmp_path: Path):
    record = submit_feedback(_submission(), _store(tmp_path)).record
    aggregate = aggregate_feedback((record,))[0]
    assert aggregate.warnings == ("INSUFFICIENT_FOR_AGGREGATE_INTERPRETATION",)
    assert aggregate.bias_candidate.status is BiasCandidateStatus.INSUFFICIENT_EVIDENCE


def test_bias_candidate_never_mutates_inputs_or_creates_correction(tmp_path: Path):
    snapshot = dict(_submission().full_input_snapshot)
    records = tuple(
        submit_feedback(
            _submission(
                full_input_snapshot=snapshot,
                reference_value=29.0 + index,
                source_reference=f"BIAS-{index}",
            ),
            _store(tmp_path),
        ).record
        for index in range(3)
    )
    candidate = aggregate_feedback(records)[0].bias_candidate
    assert candidate.status is BiasCandidateStatus.POSSIBLE_POSITIVE_BIAS
    assert snapshot == _submission().full_input_snapshot
    assert "correction" in candidate.notes.lower()


def test_feedback_compares_to_phase7i_envelope_without_overclaim(tmp_path: Path):
    result = run_phase7j_demo(ROOT, _store(tmp_path))
    assert result.envelope_comparison.position is EnvelopePosition.INSIDE_PARAMETER_BOUNDS_ONLY
    assert result.summary.validation_coverage is ExternalValidationCoverage.VERY_LIMITED
    assert result.submission_result.record.evidence_quality is EvidenceQuality.UNVERIFIED


def test_validation_summary_is_read_only_dashboard_data(tmp_path: Path):
    record = submit_feedback(_submission(), _store(tmp_path)).record
    summary = build_validation_summary((record,))
    assert summary.total_records == summary.compatible_records == 1
    assert summary.blocked_records == 0
    assert summary.metric_counts == {record.metric_name: 1}
    assert "INSUFFICIENT_FOR_AGGREGATE_INTERPRETATION" in summary.warnings


def test_feedback_modules_have_no_network_or_upload_implementation():
    for filename in ("feedback_models.py", "feedback_service.py", "feedback_aggregation.py"):
        source = (ROOT / "motor_calculator" / "validation" / filename).read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import socket" not in source
        assert "http.client" not in source


def test_submission_does_not_mutate_production_inputs_or_frozen_files(tmp_path: Path):
    calculations_before = CALCULATIONS_PATH.read_bytes()
    legacy_before = LEGACY_PATH.read_bytes()
    mutable_snapshot = dict(_submission().full_input_snapshot)
    submission = _submission(full_input_snapshot=mutable_snapshot)
    record = submit_feedback(submission, _store(tmp_path)).record
    mutable_snapshot["pole_pairs"] = 999
    assert record.full_input_snapshot["pole_pairs"] == 5
    assert CALCULATIONS_PATH.read_bytes() == calculations_before
    assert LEGACY_PATH.read_bytes() == legacy_before


def test_feedback_form_model_returns_user_readable_validation_messages():
    form = FeedbackFormModel(metric="", predicted_value="abc", reference_value="", speed_rpm="")
    messages = form.validate_for_display()
    assert "请选择要验证的指标。" in messages
    assert "预测值必须是数值。" in messages
    assert "参考值不能为空。" in messages
