"""Metric-level external evidence comparison for the Phase 7B.1 sandbox."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from enum import Enum

from .accuracy_metrics import AccuracyMetricStatus, AccuracyMetrics, compute_accuracy_metrics


class ComparabilityStatus(str, Enum):
    DIRECT = "DIRECT"
    SAFE_TRANSFORM = "SAFE_TRANSFORM"
    APPROXIMATE = "APPROXIMATE"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"


class ComparisonOutcome(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    APPROXIMATE = "APPROXIMATE"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"


class EvidenceType(str, Enum):
    MEASURED = "measured"
    FEA = "fea"
    ANALYTICAL = "analytical"
    PUBLISHED_PROTOTYPE_SPECIFICATION = "published_prototype_specification"


class SafeTransformation(str, Enum):
    IDENTITY = "identity"
    RPM_TO_RAD_PER_S = "rpm_to_rad_per_s"
    PHASE_RMS_TO_PHASE_PEAK_SINUSOIDAL = "phase_rms_to_phase_peak_sinusoidal"
    PHASE_RMS_TO_LINE_RMS_Y_SINUSOIDAL = "phase_rms_to_line_rms_y_sinusoidal"


@dataclass(frozen=True)
class MetricProvenance:
    source_url: str
    page: str
    location: str
    extraction_note: str
    access_status: str = "full_text_accessed"

    def __post_init__(self) -> None:
        for name in ("source_url", "page", "location", "extraction_note", "access_status"):
            if not getattr(self, name).strip():
                raise ValueError(f"provenance.{name} must not be empty")


@dataclass(frozen=True)
class ExternalMetricEvidence:
    source_id: str
    source_title: str
    topology: str
    metric_name: str
    value: float | None
    unit: str
    operating_point: str
    quantity_scope: str
    value_kind: str
    waveform: str
    winding_connection: str
    current_basis: str
    provenance: MetricProvenance
    evidence_type: EvidenceType
    uncertainty: str
    comparability_status: ComparabilityStatus
    notes: str
    confidence: str = "medium"

    def __post_init__(self) -> None:
        required = (
            "source_id", "source_title", "topology", "metric_name", "unit",
            "operating_point", "quantity_scope", "value_kind", "waveform",
            "winding_connection", "current_basis", "uncertainty", "notes", "confidence",
        )
        for name in required:
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty; use explicit 'unavailable' text")
        if self.value is not None and not math.isfinite(float(self.value)):
            raise ValueError("evidence value must be finite when provided")
        if self.comparability_status in {
            ComparabilityStatus.DIRECT,
            ComparabilityStatus.SAFE_TRANSFORM,
            ComparabilityStatus.APPROXIMATE,
        } and self.value is None:
            raise ValueError("comparable or approximate evidence requires a source value")
        if self.comparability_status is ComparabilityStatus.UNAVAILABLE and self.value is not None:
            raise ValueError("UNAVAILABLE evidence must not use a placeholder value")


@dataclass(frozen=True)
class ExternalMetricComparison:
    evidence: ExternalMetricEvidence
    model_prediction: float | None
    prediction_unit: str
    normalized_reference: float | None
    normalized_unit: str
    transformation: SafeTransformation
    transformation_notes: str
    metrics: AccuracyMetrics
    tolerance: str
    outcome: ComparisonOutcome


@dataclass(frozen=True)
class ExternalValidationCampaignResult:
    rows: tuple[ExternalMetricComparison, ...]

    @property
    def comparability_counts(self) -> dict[str, int]:
        counts = Counter(row.evidence.comparability_status.value for row in self.rows)
        return {status.value: counts.get(status.value, 0) for status in ComparabilityStatus}

    @property
    def outcome_counts(self) -> dict[str, int]:
        counts = Counter(row.outcome.value for row in self.rows)
        return {outcome.value: counts.get(outcome.value, 0) for outcome in ComparisonOutcome}


def _safe_transform(
    evidence: ExternalMetricEvidence,
    transformation: SafeTransformation,
) -> tuple[float, str, str]:
    if evidence.value is None:
        raise ValueError("a safe transformation cannot infer a missing source value")
    value = float(evidence.value)
    if transformation is SafeTransformation.IDENTITY:
        return value, evidence.unit, "No unit or semantic transformation applied."
    if transformation is SafeTransformation.RPM_TO_RAD_PER_S:
        if evidence.unit != "rpm":
            raise ValueError("rpm_to_rad_per_s requires a source unit of rpm")
        return value * 2.0 * math.pi / 60.0, "rad/s", "Explicit SI conversion: rpm * 2*pi/60."
    if transformation is SafeTransformation.PHASE_RMS_TO_PHASE_PEAK_SINUSOIDAL:
        if evidence.unit != "V phase RMS" or evidence.waveform != "sinusoidal":
            raise ValueError("phase RMS to phase peak requires an explicitly sinusoidal phase voltage")
        return value * math.sqrt(2.0), "V phase peak", "Sinusoidal phase RMS multiplied by sqrt(2)."
    if transformation is SafeTransformation.PHASE_RMS_TO_LINE_RMS_Y_SINUSOIDAL:
        if (
            evidence.unit != "V phase RMS"
            or evidence.waveform != "sinusoidal"
            or evidence.winding_connection != "Y"
        ):
            raise ValueError("phase RMS to line RMS requires sinusoidal waveform and known Y connection")
        return value * math.sqrt(3.0), "V line RMS", "Y-connected sinusoidal phase RMS multiplied by sqrt(3)."
    raise ValueError(f"unsupported safe transformation: {transformation}")


def _tolerance(metric_name: str) -> tuple[float, float, str]:
    normalized = metric_name.lower()
    if any(token in normalized for token in ("loss", "efficiency", "temperature")):
        return 10.0, 20.0, "PASS <= 10%; WARNING <= 20%; FAIL > 20%"
    return 5.0, 10.0, "PASS <= 5%; WARNING <= 10%; FAIL > 10%"


def compare_external_metric(
    evidence: ExternalMetricEvidence,
    model_prediction: float | None,
    prediction_unit: str,
    *,
    transformation: SafeTransformation = SafeTransformation.IDENTITY,
) -> ExternalMetricComparison:
    """Compare one external metric without mutating or filling missing evidence."""

    if not prediction_unit.strip():
        raise ValueError("prediction_unit must not be empty")
    if model_prediction is not None and not math.isfinite(float(model_prediction)):
        raise ValueError("model_prediction must be finite when provided")

    status = evidence.comparability_status
    if status in {ComparabilityStatus.BLOCKED, ComparabilityStatus.UNAVAILABLE}:
        outcome = (
            ComparisonOutcome.BLOCKED
            if status is ComparabilityStatus.BLOCKED
            else ComparisonOutcome.UNAVAILABLE
        )
        reference = evidence.value
        return ExternalMetricComparison(
            evidence=evidence,
            model_prediction=None,
            prediction_unit=prediction_unit,
            normalized_reference=reference,
            normalized_unit=evidence.unit,
            transformation=SafeTransformation.IDENTITY,
            transformation_notes="Comparison not attempted; source evidence remains unmodified.",
            metrics=compute_accuracy_metrics(None, reference),
            tolerance="not applied: comparison blocked" if reference is not None else "not applied: source value unavailable",
            outcome=outcome,
        )

    if model_prediction is None:
        raise ValueError("DIRECT, SAFE_TRANSFORM, or APPROXIMATE comparison requires a model prediction")
    if status is ComparabilityStatus.DIRECT and transformation is not SafeTransformation.IDENTITY:
        raise ValueError("DIRECT evidence must not require a transformation")
    if status is ComparabilityStatus.SAFE_TRANSFORM and transformation is SafeTransformation.IDENTITY:
        raise ValueError("SAFE_TRANSFORM evidence requires an explicit approved transformation")

    reference, normalized_unit, transformation_notes = _safe_transform(evidence, transformation)
    if prediction_unit != normalized_unit:
        raise ValueError(
            f"prediction unit {prediction_unit!r} does not match normalized source unit {normalized_unit!r}"
        )
    metrics = compute_accuracy_metrics(model_prediction, reference)
    pass_limit, warning_limit, tolerance = _tolerance(evidence.metric_name)
    if status is ComparabilityStatus.APPROXIMATE:
        outcome = ComparisonOutcome.APPROXIMATE
        tolerance = f"{tolerance}; approximate evidence cannot create an accuracy PASS claim"
    elif metrics.status is not AccuracyMetricStatus.VALID or metrics.absolute_percentage_error is None:
        outcome = ComparisonOutcome.WARNING
    elif metrics.absolute_percentage_error <= pass_limit:
        outcome = ComparisonOutcome.PASS
    elif metrics.absolute_percentage_error <= warning_limit:
        outcome = ComparisonOutcome.WARNING
    else:
        outcome = ComparisonOutcome.FAIL

    return ExternalMetricComparison(
        evidence=evidence,
        model_prediction=float(model_prediction),
        prediction_unit=prediction_unit,
        normalized_reference=reference,
        normalized_unit=normalized_unit,
        transformation=transformation,
        transformation_notes=transformation_notes,
        metrics=metrics,
        tolerance=tolerance,
        outcome=outcome,
    )
