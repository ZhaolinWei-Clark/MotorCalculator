"""Reproducible synthetic confidence-and-feedback UX data scenario."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .confidence_summary import EngineeringConfidenceSummary, build_engineering_confidence_summary
from .feedback_aggregation import compare_feedback_to_uncertainty_envelope
from .feedback_models import EnvelopeComparison, ValidationFeedbackRecord
from .phase7i_uncertainty_report import run_phase7i_demonstration
from .phase7j_feedback_demo import run_phase7j_demo


@dataclass(frozen=True)
class Phase7KConfidenceDemo:
    confidence_summary: EngineeringConfidenceSummary
    feedback_record: ValidationFeedbackRecord
    envelope_comparison: EnvelopeComparison


def run_phase7k_confidence_demo(
    repository_root: Path,
    temporary_feedback_store: Path,
) -> Phase7KConfidenceDemo:
    root = Path(repository_root)
    phase7i = run_phase7i_demonstration(root)
    phase7j = run_phase7j_demo(root, Path(temporary_feedback_store))
    summary = build_engineering_confidence_summary(
        phase7i.accuracy_envelope,
        phase7j.summary,
        source_label="SYNTHETIC PHASE 7K UX DEMO",
    )
    record = phase7j.submission_result.record
    comparison = compare_feedback_to_uncertainty_envelope(record, phase7i.accuracy_envelope)
    return Phase7KConfidenceDemo(summary, record, comparison)
