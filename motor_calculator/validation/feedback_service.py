"""Local submission, compatibility, hashing, and JSONL storage for feedback."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from motor_calculator.runtime.paths import resolve_runtime_paths

from .accuracy_metrics import AccuracyMetrics, compute_accuracy_metrics
from .feedback_models import (
    DuplicateStatus,
    EvidenceQuality,
    FeedbackComparability,
    FeedbackSubmission,
    FeedbackSubmissionResult,
    MetricSemantics,
    ValidationEvidenceType,
    ValidationFeedbackRecord,
)


FEEDBACK_SCHEMA_VERSION = "phase7j.feedback.v1"
DEFAULT_FEEDBACK_STORE = resolve_runtime_paths().feedback_store
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class CompatibilityAssessment:
    status: FeedbackComparability
    normalized_reference_value: float | None
    normalized_unit: str
    safe_transformation: str
    messages: tuple[str, ...]


@dataclass(frozen=True)
class FeedbackValidationResult:
    evidence_quality: EvidenceQuality
    compatibility: CompatibilityAssessment
    validation_messages: tuple[str, ...]


def _finite(name: str, value: float | None, *, required: bool = False) -> float | None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value.strip()


def _normalized(value: str | None) -> str | None:
    return value.strip().lower() if isinstance(value, str) and value.strip() else None


def _normalize_snapshot(snapshot: Mapping[str, Any] | None, name: str) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    if not isinstance(snapshot, Mapping):
        raise ValueError(f"{name} must be a mapping")
    try:
        return json.loads(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain only finite JSON-compatible values") from exc


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def hash_input_snapshot(snapshot: Mapping[str, Any]) -> str:
    normalized = _normalize_snapshot(snapshot, "full_input_snapshot")
    if normalized is None:
        raise ValueError("full_input_snapshot is required")
    return _sha256_payload(normalized)


def _required_semantic_fields(metric_name: str) -> tuple[str, ...]:
    metric = metric_name.lower()
    required: list[str] = []
    if "back_emf" in metric or "voltage" in metric:
        required.extend(("quantity_scope", "rms_peak_semantics", "waveform_semantics"))
    if "torque" in metric:
        required.append("torque_boundary")
    if "current" in metric or "torque_constant" in metric or metric.startswith("kt"):
        required.append("current_basis")
    if "inductance" in metric or metric in {"ld", "lq"}:
        required.append("quantity_scope")
    return tuple(dict.fromkeys(required))


def _missing_semantics(metric_name: str, semantics: MetricSemantics) -> tuple[str, ...]:
    return tuple(
        field_name
        for field_name in _required_semantic_fields(metric_name)
        if _normalized(getattr(semantics, field_name)) is None
    )


def _same_semantics(left: MetricSemantics, right: MetricSemantics) -> bool:
    return all(
        _normalized(getattr(left, name)) == _normalized(getattr(right, name))
        for name in (
            "quantity_scope",
            "rms_peak_semantics",
            "waveform_semantics",
            "torque_boundary",
            "current_basis",
        )
    )


def assess_metric_compatibility(submission: FeedbackSubmission) -> CompatibilityAssessment:
    """Gate error computation without discarding incompatible evidence."""

    metric_name = _required_text("metric_name", submission.metric_name)
    prediction_unit = _required_text("predicted_unit", submission.predicted_unit)
    reference_unit = _required_text("reference_unit", submission.reference_unit)
    missing_prediction = _missing_semantics(metric_name, submission.predicted_semantics)
    missing_reference = _missing_semantics(metric_name, submission.reference_semantics)
    messages: list[str] = []
    if missing_prediction:
        messages.append("Prediction semantics missing: " + ", ".join(missing_prediction))
    if missing_reference:
        messages.append("Reference semantics missing: " + ", ".join(missing_reference))
    if messages:
        return CompatibilityAssessment(
            FeedbackComparability.BLOCKED, None, prediction_unit, "none", tuple(messages)
        )

    if prediction_unit == reference_unit and _same_semantics(
        submission.predicted_semantics, submission.reference_semantics
    ):
        return CompatibilityAssessment(
            FeedbackComparability.DIRECT,
            float(submission.reference_value),
            prediction_unit,
            "identity",
            ("Prediction and reference units and semantics match directly.",),
        )

    predicted = submission.predicted_semantics
    reference = submission.reference_semantics
    same_waveform = _normalized(predicted.waveform_semantics) == _normalized(reference.waveform_semantics)
    sinusoidal = _normalized(reference.waveform_semantics) == "sinusoidal"
    same_boundary = _normalized(predicted.torque_boundary) == _normalized(reference.torque_boundary)
    same_current = _normalized(predicted.current_basis) == _normalized(reference.current_basis)
    voltage_units = {prediction_unit, reference_unit} <= {"V", "V phase RMS", "V phase peak", "V line RMS"}

    if (
        voltage_units
        and same_waveform
        and sinusoidal
        and same_boundary
        and same_current
        and _normalized(predicted.quantity_scope) == _normalized(reference.quantity_scope)
        and _normalized(predicted.rms_peak_semantics) == "peak"
        and _normalized(reference.rms_peak_semantics) == "rms"
    ):
        return CompatibilityAssessment(
            FeedbackComparability.SAFE_TRANSFORM,
            float(submission.reference_value) * math.sqrt(2.0),
            prediction_unit,
            "phase_rms_to_phase_peak_sinusoidal",
            ("Explicit sinusoidal RMS-to-peak conversion applied to the reference.",),
        )

    winding_connection = _normalized(str(submission.full_input_snapshot.get("winding_connection", "")))
    if (
        voltage_units
        and same_waveform
        and sinusoidal
        and same_boundary
        and same_current
        and _normalized(predicted.quantity_scope) == "line"
        and _normalized(reference.quantity_scope) == "phase"
        and _normalized(predicted.rms_peak_semantics) == "rms"
        and _normalized(reference.rms_peak_semantics) == "rms"
        and winding_connection in {"y", "wye", "star"}
    ):
        return CompatibilityAssessment(
            FeedbackComparability.SAFE_TRANSFORM,
            float(submission.reference_value) * math.sqrt(3.0),
            prediction_unit,
            "phase_rms_to_line_rms_y_sinusoidal",
            ("Explicit Y-connected sinusoidal phase-to-line RMS conversion applied.",),
        )

    return CompatibilityAssessment(
        FeedbackComparability.BLOCKED,
        None,
        prediction_unit,
        "none",
        (
            "Units or metric semantics are incompatible; no numerical error was computed.",
            "Unknown waveform RMS/peak, torque-boundary, current-basis, and inductance-axis conversions remain blocked.",
        ),
    )


def classify_evidence_quality(
    submission: FeedbackSubmission,
    compatibility: CompatibilityAssessment,
) -> EvidenceQuality:
    evidence_label = " ".join(filter(None, (
        submission.source_name,
        submission.source_reference,
        submission.notes,
    ))).lower()
    if "synthetic" in evidence_label or "demo" in evidence_label:
        return EvidenceQuality.UNVERIFIED
    traceable = bool(
        submission.source_name
        and submission.source_name.strip()
        and submission.source_reference
        and submission.source_reference.strip()
    )
    complete_snapshot = bool(submission.full_input_snapshot)
    complete_semantics = not _missing_semantics(
        submission.metric_name, submission.reference_semantics
    )
    explicit_operating_point = math.isfinite(float(submission.operating_point.speed_rpm))

    if (
        submission.evidence_type in {
            ValidationEvidenceType.BENCH_MEASUREMENT,
            ValidationEvidenceType.PUBLISHED_EXPERIMENT,
        }
        and traceable
        and complete_snapshot
        and complete_semantics
        and explicit_operating_point
        and compatibility.status is not FeedbackComparability.BLOCKED
    ):
        return EvidenceQuality.HIGH
    if (
        submission.evidence_type in {
            ValidationEvidenceType.FEA,
            ValidationEvidenceType.MANUFACTURER_DATA,
            ValidationEvidenceType.PUBLISHED_EXPERIMENT,
            ValidationEvidenceType.ANALYTICAL_REFERENCE,
        }
        and traceable
        and complete_snapshot
        and complete_semantics
    ):
        return EvidenceQuality.MEDIUM
    if traceable or complete_snapshot:
        return EvidenceQuality.LOW
    return EvidenceQuality.UNVERIFIED


def validate_feedback(submission: FeedbackSubmission) -> FeedbackValidationResult:
    _required_text("metric_name", submission.metric_name)
    _required_text("predicted_unit", submission.predicted_unit)
    _required_text("reference_unit", submission.reference_unit)
    _finite("predicted_value", submission.predicted_value, required=True)
    _finite("reference_value", submission.reference_value, required=True)
    _finite("speed_rpm", submission.operating_point.speed_rpm, required=True)
    for name in ("current_a", "voltage_v", "temperature_c", "load_torque_nm"):
        _finite(name, getattr(submission.operating_point, name))
    if float(submission.operating_point.speed_rpm) < 0.0:
        raise ValueError("speed_rpm must be non-negative")
    for name in ("current_a", "voltage_v"):
        value = getattr(submission.operating_point, name)
        if value is not None and float(value) < 0.0:
            raise ValueError(f"{name} must be non-negative")
    for field_name, value in submission.model_identity.to_dict().items():
        if field_name == "git_commit":
            continue
        _required_text(field_name, str(value))
    normalized_snapshot = _normalize_snapshot(submission.full_input_snapshot, "full_input_snapshot")
    if not normalized_snapshot:
        raise ValueError("full_input_snapshot must preserve the calculation input configuration")
    _normalize_snapshot(submission.uncertainty_snapshot, "uncertainty_snapshot")
    if submission.source_file_hash and not _SHA256_PATTERN.fullmatch(submission.source_file_hash):
        raise ValueError("source_file_hash must be a 64-character SHA-256 hex digest")

    compatibility = assess_metric_compatibility(submission)
    quality = classify_evidence_quality(submission, compatibility)
    messages = list(compatibility.messages)
    if quality in {EvidenceQuality.LOW, EvidenceQuality.UNVERIFIED}:
        messages.append(
            "Evidence was retained with limited quality; it must not be treated as calibration authority."
        )
    return FeedbackValidationResult(quality, compatibility, tuple(messages))


def compute_feedback_error(
    submission: FeedbackSubmission,
    assessment: CompatibilityAssessment | None = None,
) -> AccuracyMetrics:
    compatibility = assessment or assess_metric_compatibility(submission)
    if compatibility.status is FeedbackComparability.BLOCKED:
        return compute_accuracy_metrics(None, None)
    return compute_accuracy_metrics(
        submission.predicted_value, compatibility.normalized_reference_value
    )


def _record_payload(record: ValidationFeedbackRecord, *, include_content_hash: bool) -> dict[str, Any]:
    payload = asdict(record)
    payload["evidence_type"] = record.evidence_type.value
    payload["evidence_quality"] = record.evidence_quality.value
    payload["comparability"] = record.comparability.value
    payload["duplicate_status"] = record.duplicate_status.value
    if not include_content_hash:
        payload.pop("record_content_hash", None)
    return payload


def serialize_feedback(record: ValidationFeedbackRecord) -> str:
    return _canonical_json(_record_payload(record, include_content_hash=True))


def _deserialize_feedback(payload: Mapping[str, Any]) -> ValidationFeedbackRecord:
    raw = dict(payload)
    raw["evidence_type"] = ValidationEvidenceType(raw["evidence_type"])
    raw["evidence_quality"] = EvidenceQuality(raw["evidence_quality"])
    raw["comparability"] = FeedbackComparability(raw["comparability"])
    raw["duplicate_status"] = DuplicateStatus(raw["duplicate_status"])
    raw["validation_messages"] = tuple(raw.get("validation_messages", ()))
    return ValidationFeedbackRecord(**raw)


def load_feedback_records(
    store_path: Path | None = None,
    *,
    verify_integrity: bool = True,
) -> tuple[ValidationFeedbackRecord, ...]:
    path = Path(store_path) if store_path is not None else resolve_runtime_paths().feedback_store
    if not path.exists():
        return ()
    records: list[ValidationFeedbackRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = _deserialize_feedback(json.loads(line))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid feedback JSONL record at line {line_number}") from exc
        if verify_integrity:
            expected_snapshot_hash = hash_input_snapshot(record.full_input_snapshot)
            expected_content_hash = _sha256_payload(
                _record_payload(record, include_content_hash=False)
            )
            if record.input_snapshot_hash != expected_snapshot_hash:
                raise ValueError(f"input snapshot hash mismatch at line {line_number}")
            if record.record_content_hash != expected_content_hash:
                raise ValueError(f"record content hash mismatch at line {line_number}")
        records.append(record)
    return tuple(records)


def _possible_duplicate(
    record: ValidationFeedbackRecord,
    existing_records: Iterable[ValidationFeedbackRecord],
) -> bool:
    return any(
        candidate.input_snapshot_hash == record.input_snapshot_hash
        and candidate.metric_name == record.metric_name
        and candidate.speed_rpm == record.speed_rpm
        and candidate.current_a == record.current_a
        and candidate.voltage_v == record.voltage_v
        and candidate.temperature_c == record.temperature_c
        and candidate.reference_value == record.reference_value
        and candidate.source_name == record.source_name
        and candidate.source_reference == record.source_reference
        for candidate in existing_records
    )


def _append_record(path: Path, record: ValidationFeedbackRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded_line = (serialize_feedback(record) + "\n").encode("utf-8")
    with path.open("ab") as stream:
        stream.write(encoded_line)
        stream.flush()
        os.fsync(stream.fileno())


def submit_feedback(
    submission: FeedbackSubmission,
    store_path: Path | None = None,
    *,
    record_id: str | None = None,
    created_at: str | None = None,
) -> FeedbackSubmissionResult:
    validation = validate_feedback(submission)
    metrics = compute_feedback_error(submission, validation.compatibility)
    snapshot = _normalize_snapshot(submission.full_input_snapshot, "full_input_snapshot")
    uncertainty = _normalize_snapshot(submission.uncertainty_snapshot, "uncertainty_snapshot")
    assert snapshot is not None
    path = Path(store_path) if store_path is not None else resolve_runtime_paths().feedback_store
    existing = load_feedback_records(path)
    identifier = record_id or str(uuid.uuid4())
    _required_text("record_id", identifier)
    if any(candidate.record_id == identifier for candidate in existing):
        raise ValueError(f"record_id already exists: {identifier}")
    timestamp = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    _required_text("created_at", timestamp)
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("created_at must be an ISO-8601 timestamp") from exc
    identity = submission.model_identity
    predicted = submission.predicted_semantics
    reference = submission.reference_semantics
    operating = submission.operating_point
    record = ValidationFeedbackRecord(
        schema_version=FEEDBACK_SCHEMA_VERSION,
        record_id=identifier,
        created_at=timestamp,
        calculator_version=identity.calculator_version,
        model_version=identity.model_version,
        model_track=identity.model_track,
        topology=identity.topology,
        software_version=identity.software_version,
        git_commit=identity.git_commit,
        model_family=identity.model_family,
        calculation_mode=identity.calculation_mode,
        origin=identity.origin,
        formula_version=identity.formula_version,
        metric_name=submission.metric_name,
        predicted_value=float(submission.predicted_value),
        reference_value=float(submission.reference_value),
        normalized_reference_value=validation.compatibility.normalized_reference_value,
        unit=validation.compatibility.normalized_unit,
        reference_unit=submission.reference_unit,
        quantity_scope=predicted.quantity_scope,
        rms_peak_semantics=predicted.rms_peak_semantics,
        waveform_semantics=predicted.waveform_semantics,
        torque_boundary=predicted.torque_boundary,
        current_basis=predicted.current_basis,
        reference_quantity_scope=reference.quantity_scope,
        reference_rms_peak_semantics=reference.rms_peak_semantics,
        reference_waveform_semantics=reference.waveform_semantics,
        reference_torque_boundary=reference.torque_boundary,
        reference_current_basis=reference.current_basis,
        speed_rpm=float(operating.speed_rpm),
        current_a=_finite("current_a", operating.current_a),
        voltage_v=_finite("voltage_v", operating.voltage_v),
        temperature_c=_finite("temperature_c", operating.temperature_c),
        load_torque_nm=_finite("load_torque_nm", operating.load_torque_nm),
        evidence_type=submission.evidence_type,
        source_name=submission.source_name,
        source_reference=submission.source_reference,
        notes=submission.notes,
        evidence_quality=validation.evidence_quality,
        full_input_snapshot=snapshot,
        uncertainty_snapshot=uncertainty,
        comparability=validation.compatibility.status,
        safe_transformation=validation.compatibility.safe_transformation,
        validation_messages=validation.validation_messages,
        signed_error=metrics.absolute_error,
        absolute_error=metrics.absolute_error_magnitude,
        relative_error=metrics.relative_error,
        absolute_percentage_error=metrics.absolute_percentage_error,
        duplicate_status=DuplicateStatus.UNIQUE,
        input_snapshot_hash=hash_input_snapshot(snapshot),
        record_content_hash="",
        source_file_hash=submission.source_file_hash,
    )
    duplicate_status = (
        DuplicateStatus.POSSIBLE_DUPLICATE
        if _possible_duplicate(record, existing)
        else DuplicateStatus.UNIQUE
    )
    record = replace(record, duplicate_status=duplicate_status)
    content_hash = _sha256_payload(_record_payload(record, include_content_hash=False))
    record = replace(record, record_content_hash=content_hash)
    _append_record(path, record)
    return FeedbackSubmissionResult(record, duplicate_status)
