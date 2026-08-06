"""GUI-neutral engineering confidence summary and local export formatting."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .confidence_explanation import build_confidence_reasons
from .feedback_aggregation import build_validation_summary
from .feedback_models import ExternalValidationCoverage, ValidationSummary
from .feedback_service import load_feedback_records
from .uncertainty_models import (
    AccuracyEnvelopeResult,
    ModelFormUncertaintyStatus,
    ResultConfidence,
)


class UncertaintyDimensionStatus(str, Enum):
    QUANTIFIED = "QUANTIFIED"
    GOOD = "GOOD"
    LIMITED = "LIMITED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class EngineeringConfidenceSummary:
    metric_name: str
    nominal_value: float | None
    unit: str
    parameter_bound_min: float | None
    parameter_bound_max: float | None
    p10: float | None
    p50: float | None
    p90: float | None
    monte_carlo_available: bool
    confidence_level: ResultConfidence
    confidence_reasons: tuple[str, ...]
    external_validation_coverage: ExternalValidationCoverage
    compatible_validation_records: int
    high_quality_validation_records: int
    parameter_uncertainty_status: UncertaintyDimensionStatus
    numerical_uncertainty_status: UncertaintyDimensionStatus
    model_form_uncertainty_status: ModelFormUncertaintyStatus
    dominant_uncertainty_parameters: tuple[str, ...]
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]
    source_label: str


def load_validation_summary_safely(
    store_path: Path,
    *,
    metric_name: str | None = None,
    topology: str | None = None,
) -> tuple[ValidationSummary, str | None]:
    """Return an empty summary rather than breaking calculation UX on store errors."""

    try:
        records = load_feedback_records(store_path)
    except (OSError, ValueError) as exc:
        return (
            build_validation_summary(()),
            f"Local validation database is unavailable: {exc}",
        )
    if metric_name is not None:
        records = tuple(record for record in records if record.metric_name == metric_name)
    if topology is not None:
        records = tuple(record for record in records if record.topology == topology)
    return build_validation_summary(records), None


def build_engineering_confidence_summary(
    envelope: AccuracyEnvelopeResult,
    validation_summary: ValidationSummary | None = None,
    *,
    source_label: str = "validation uncertainty result",
) -> EngineeringConfidenceSummary:
    coverage = (
        validation_summary.validation_coverage
        if validation_summary is not None
        else ExternalValidationCoverage.NONE
    )
    compatible = validation_summary.compatible_records if validation_summary else 0
    high_quality = validation_summary.high_quality_records if validation_summary else 0
    if envelope.numerical_uncertainty is None:
        numerical_status = UncertaintyDimensionStatus.UNAVAILABLE
    elif envelope.numerical_uncertainty <= 1.0:
        numerical_status = UncertaintyDimensionStatus.GOOD
    else:
        numerical_status = UncertaintyDimensionStatus.LIMITED
    warnings = list(envelope.warnings)
    if validation_summary is not None:
        warnings.extend(validation_summary.warnings)
    return EngineeringConfidenceSummary(
        metric_name=envelope.metric_name,
        nominal_value=envelope.nominal_value,
        unit=envelope.unit,
        parameter_bound_min=envelope.parameter_bound_min,
        parameter_bound_max=envelope.parameter_bound_max,
        p10=envelope.p10,
        p50=envelope.p50,
        p90=envelope.p90,
        monte_carlo_available=envelope.monte_carlo_available,
        confidence_level=envelope.confidence_level,
        confidence_reasons=build_confidence_reasons(envelope, validation_summary),
        external_validation_coverage=coverage,
        compatible_validation_records=compatible,
        high_quality_validation_records=high_quality,
        parameter_uncertainty_status=UncertaintyDimensionStatus.QUANTIFIED,
        numerical_uncertainty_status=numerical_status,
        model_form_uncertainty_status=envelope.model_form_uncertainty_status,
        dominant_uncertainty_parameters=envelope.dominant_uncertainty_parameters,
        warnings=tuple(dict.fromkeys(warnings)),
        assumptions=envelope.assumptions,
        source_label=source_label,
    )


def build_unavailable_confidence_summary(
    *,
    metric_name: str,
    nominal_value: float | None,
    unit: str,
    validation_summary: ValidationSummary | None = None,
    reason: str = "Uncertainty estimate not available for this result.",
    source_label: str = "current calculator result",
) -> EngineeringConfidenceSummary:
    coverage = (
        validation_summary.validation_coverage
        if validation_summary is not None
        else ExternalValidationCoverage.NONE
    )
    return EngineeringConfidenceSummary(
        metric_name=metric_name,
        nominal_value=nominal_value,
        unit=unit,
        parameter_bound_min=None,
        parameter_bound_max=None,
        p10=None,
        p50=None,
        p90=None,
        monte_carlo_available=False,
        confidence_level=ResultConfidence.INSUFFICIENT,
        confidence_reasons=(
            reason,
            "No uncertainty interval is inferred from decimal precision.",
        ),
        external_validation_coverage=coverage,
        compatible_validation_records=(validation_summary.compatible_records if validation_summary else 0),
        high_quality_validation_records=(validation_summary.high_quality_records if validation_summary else 0),
        parameter_uncertainty_status=UncertaintyDimensionStatus.UNAVAILABLE,
        numerical_uncertainty_status=UncertaintyDimensionStatus.UNAVAILABLE,
        model_form_uncertainty_status=ModelFormUncertaintyStatus.UNQUANTIFIED,
        dominant_uncertainty_parameters=(),
        warnings=(
            reason,
            "External AFPM electromagnetic validation remains limited; model-form error is not quantified.",
        ),
        assumptions=(),
        source_label=source_label,
    )


def confidence_summary_to_dict(summary: EngineeringConfidenceSummary) -> dict[str, Any]:
    payload = asdict(summary)
    payload["confidence_level"] = summary.confidence_level.value
    payload["external_validation_coverage"] = summary.external_validation_coverage.value
    payload["parameter_uncertainty_status"] = summary.parameter_uncertainty_status.value
    payload["numerical_uncertainty_status"] = summary.numerical_uncertainty_status.value
    payload["model_form_uncertainty_status"] = summary.model_form_uncertainty_status.value
    return payload


def render_confidence_summary_text(summary: EngineeringConfidenceSummary) -> str:
    nominal = "unavailable" if summary.nominal_value is None else f"{summary.nominal_value:.6f} {summary.unit}"
    parameter_range = (
        "unavailable"
        if summary.parameter_bound_min is None or summary.parameter_bound_max is None
        else f"{summary.parameter_bound_min:.6f} - {summary.parameter_bound_max:.6f} {summary.unit}"
    )
    p10_p90 = (
        "unavailable"
        if summary.p10 is None or summary.p90 is None
        else f"{summary.p10:.6f} - {summary.p90:.6f} {summary.unit}"
    )
    lines = [
        "Engineering Confidence & Validation Summary",
        f"Source: {summary.source_label}",
        f"Metric: {summary.metric_name}",
        f"Nominal prediction: {nominal}",
        f"Estimated parameter-driven range: {parameter_range}",
        f"Monte Carlo P10-P90: {p10_p90}",
        f"Overall engineering confidence: {summary.confidence_level.value}",
        f"External validation coverage: {summary.external_validation_coverage.value}",
        f"Compatible validation records: {summary.compatible_validation_records}",
        f"High-quality validation records: {summary.high_quality_validation_records}",
        f"Parameter uncertainty: {summary.parameter_uncertainty_status.value}",
        f"Numerical convergence: {summary.numerical_uncertainty_status.value}",
        f"Model-form uncertainty: {summary.model_form_uncertainty_status.value}",
        "",
        "Why:",
    ]
    lines.extend(f"- {reason}" for reason in summary.confidence_reasons)
    lines.extend(("", "Dominant uncertainty parameters:"))
    if summary.dominant_uncertainty_parameters:
        lines.extend(f"- {name}" for name in summary.dominant_uncertainty_parameters)
    else:
        lines.append("- unavailable")
    lines.extend(("", "Warnings:"))
    lines.extend(f"- {warning}" for warning in summary.warnings)
    lines.extend((
        "",
        "These are parameter-driven uncertainty estimates, not guaranteed real-world error bounds.",
    ))
    return "\n".join(lines) + "\n"


def render_confidence_summary_json(summary: EngineeringConfidenceSummary) -> str:
    return json.dumps(
        confidence_summary_to_dict(summary),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def export_confidence_summary(
    summary: EngineeringConfidenceSummary,
    path: Path,
    *,
    format_name: str,
) -> Path:
    destination = Path(path)
    normalized_format = format_name.strip().lower()
    if normalized_format == "json":
        content = render_confidence_summary_json(summary)
    elif normalized_format in {"text", "txt"}:
        content = render_confidence_summary_text(summary)
    else:
        raise ValueError("format_name must be 'json' or 'text'")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination
