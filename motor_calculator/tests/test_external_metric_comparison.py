from __future__ import annotations

import math

import pytest

from validation.external_metric_comparison import (
    ComparabilityStatus,
    ComparisonOutcome,
    EvidenceType,
    ExternalMetricEvidence,
    MetricProvenance,
    SafeTransformation,
    compare_external_metric,
)


def _evidence(**overrides) -> ExternalMetricEvidence:
    values = dict(
        source_id="source",
        source_title="Published AFPM source",
        topology="dual-rotor/single-stator AFPM",
        metric_name="back_emf_phase_rms_v",
        value=10.0,
        unit="V phase RMS",
        operating_point="600 rpm, no load",
        quantity_scope="phase back-EMF",
        value_kind="measured",
        waveform="sinusoidal",
        winding_connection="Y",
        current_basis="not applicable",
        provenance=MetricProvenance(
            source_url="https://example.test/paper",
            page="p. 5",
            location="Table 2",
            extraction_note="Transcribed from the table.",
        ),
        evidence_type=EvidenceType.MEASURED,
        uncertainty="not reported",
        comparability_status=ComparabilityStatus.DIRECT,
        notes="test evidence",
        confidence="high",
    )
    values.update(overrides)
    return ExternalMetricEvidence(**values)


def test_direct_metric_computes_accuracy_without_mutating_evidence() -> None:
    evidence = _evidence(unit="V phase RMS")
    result = compare_external_metric(evidence, 10.4, "V phase RMS")

    assert result.outcome is ComparisonOutcome.PASS
    assert result.metrics.absolute_percentage_error == pytest.approx(4.0)
    assert evidence.value == 10.0
    assert result.evidence.provenance.location == "Table 2"
    assert result.evidence.confidence == "high"


def test_safe_transform_requires_explicit_semantics() -> None:
    evidence = _evidence(comparability_status=ComparabilityStatus.SAFE_TRANSFORM)
    result = compare_external_metric(
        evidence,
        10.0 * math.sqrt(3.0),
        "V line RMS",
        transformation=SafeTransformation.PHASE_RMS_TO_LINE_RMS_Y_SINUSOIDAL,
    )

    assert result.outcome is ComparisonOutcome.PASS
    assert result.normalized_reference == pytest.approx(10.0 * math.sqrt(3.0))


def test_ambiguous_waveform_is_rejected_instead_of_converted() -> None:
    evidence = _evidence(
        comparability_status=ComparabilityStatus.SAFE_TRANSFORM,
        waveform="harmonic waveform",
    )
    with pytest.raises(ValueError, match="sinusoidal"):
        compare_external_metric(
            evidence,
            14.0,
            "V phase peak",
            transformation=SafeTransformation.PHASE_RMS_TO_PHASE_PEAK_SINUSOIDAL,
        )


def test_blocked_metric_preserves_source_value_and_provenance() -> None:
    evidence = _evidence(comparability_status=ComparabilityStatus.BLOCKED)
    result = compare_external_metric(evidence, None, "V phase RMS")

    assert result.outcome is ComparisonOutcome.BLOCKED
    assert result.normalized_reference == 10.0
    assert result.model_prediction is None
    assert result.evidence.provenance.page == "p. 5"


def test_missing_source_value_cannot_be_inferred() -> None:
    evidence = _evidence(
        value=None,
        comparability_status=ComparabilityStatus.UNAVAILABLE,
        value_kind="unavailable",
    )
    result = compare_external_metric(evidence, None, "V phase RMS")

    assert result.normalized_reference is None
    assert result.metrics.reference is None
    assert result.outcome is ComparisonOutcome.UNAVAILABLE


def test_approximate_evidence_never_creates_pass_claim() -> None:
    evidence = _evidence(comparability_status=ComparabilityStatus.APPROXIMATE)
    result = compare_external_metric(evidence, 10.0, "V phase RMS")

    assert result.metrics.absolute_percentage_error == 0.0
    assert result.outcome is ComparisonOutcome.APPROXIMATE
    assert "cannot create an accuracy PASS" in result.tolerance
