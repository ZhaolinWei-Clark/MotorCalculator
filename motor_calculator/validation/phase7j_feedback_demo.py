"""Reproducible synthetic demonstration of the Phase 7J feedback workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .feedback_aggregation import (
    aggregate_feedback,
    build_validation_summary,
    compare_feedback_to_uncertainty_envelope,
)
from .feedback_models import (
    EnvelopeComparison,
    FeedbackAggregate,
    FeedbackModelIdentity,
    FeedbackOperatingPoint,
    FeedbackSubmission,
    FeedbackSubmissionResult,
    MetricSemantics,
    ValidationEvidenceType,
    ValidationSummary,
)
from .feedback_service import load_feedback_records, submit_feedback
from .phase7i_uncertainty_report import run_phase7i_demonstration


@dataclass(frozen=True)
class Phase7JDemoResult:
    submission_result: FeedbackSubmissionResult
    aggregate: FeedbackAggregate
    summary: ValidationSummary
    envelope_comparison: EnvelopeComparison


def build_phase7j_demo_submission(repository_root: Path) -> FeedbackSubmission:
    phase7i = run_phase7i_demonstration(
        Path(repository_root), monte_carlo_sample_count=250, random_seed=20260701
    )
    nominal = phase7i.accuracy_envelope.nominal_value
    semantics = MetricSemantics(
        quantity_scope="phase",
        rms_peak_semantics="rms",
        waveform_semantics="sinusoidal",
        torque_boundary="not_applicable",
        current_basis="not_applicable",
    )
    input_snapshot = dict(phase7i.specification.nominal_values())
    input_snapshot.update({
        "topology": "SSDR controlled AFPM reference",
        "pole_pairs": 5,
        "turns_per_phase": 100,
        "winding_connection": "Y",
        "rated_speed_rpm": 1000.0,
        "phase_current_a": 0.0,
        "voltage_v": None,
        "temperature_c": 20.0,
        "phase_resistance_ohm": "not_applicable_to_no_load_back_emf_demo",
        "phase_inductance_h": "not_applicable_to_no_load_back_emf_demo",
    })
    return FeedbackSubmission(
        metric_name="back_emf_phase_fundamental_rms_v",
        predicted_value=nominal,
        reference_value=31.8,
        predicted_unit="V",
        reference_unit="V",
        predicted_semantics=semantics,
        reference_semantics=semantics,
        operating_point=FeedbackOperatingPoint(
            speed_rpm=1000.0,
            current_a=0.0,
            temperature_c=20.0,
        ),
        evidence_type=ValidationEvidenceType.BENCH_MEASUREMENT,
        model_identity=FeedbackModelIdentity(
            calculator_version="phase7j-demo",
            model_version="phase7h-controlled-ssdr-v1",
            model_track="advanced_afpm_sandbox",
            topology="SSDR controlled AFPM reference",
            software_version="phase7j",
            git_commit=None,
            model_family="advanced_afpm_radial_slice",
            calculation_mode="no_load_back_emf",
            origin="sandbox",
            formula_version="phase7h-frozen",
        ),
        full_input_snapshot=input_snapshot,
        uncertainty_snapshot={
            "specification_id": phase7i.specification.specification_id,
            "assumption_label": phase7i.specification.assumption_label,
        },
        source_name="SYNTHETIC_DEMO_ONLY",
        source_reference="Phase 7J workflow demonstration; not a real measurement",
        notes="Synthetic demo evidence. Never use for accuracy or calibration claims.",
    )


def run_phase7j_demo(repository_root: Path, store_path: Path) -> Phase7JDemoResult:
    submission = build_phase7j_demo_submission(repository_root)
    result = submit_feedback(
        submission,
        store_path,
        record_id="phase7j-synthetic-demo-001",
        created_at="2026-07-01T00:00:00+00:00",
    )
    records = load_feedback_records(store_path)
    aggregate = aggregate_feedback(records)[0]
    summary = build_validation_summary(records)
    envelope = run_phase7i_demonstration(
        Path(repository_root), monte_carlo_sample_count=250, random_seed=20260701
    ).accuracy_envelope
    comparison = compare_feedback_to_uncertainty_envelope(result.record, envelope)
    return Phase7JDemoResult(result, aggregate, summary, comparison)
