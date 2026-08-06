"""Read-only aggregation and uncertainty-envelope checks for feedback evidence."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from typing import Callable, Iterable

from .feedback_models import (
    BiasCandidate,
    BiasCandidateStatus,
    EnvelopeComparison,
    EnvelopePosition,
    EvidenceQuality,
    ExternalValidationCoverage,
    FeedbackAggregate,
    FeedbackComparability,
    ValidationFeedbackRecord,
    ValidationSummary,
)
from .uncertainty_models import AccuracyEnvelopeResult


def _percentile(values: tuple[float, ...], percentile: float) -> float:
    ordered = tuple(sorted(values))
    if not ordered:
        raise ValueError("percentile requires at least one value")
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _speed_range(speed_rpm: float) -> str:
    lower = int(speed_rpm // 1000.0) * 1000
    return f"{lower}-{lower + 999} rpm"


def _temperature_range(temperature_c: float | None) -> str:
    if temperature_c is None:
        return "temperature unavailable"
    lower = int(math.floor(temperature_c / 20.0)) * 20
    return f"{lower}-{lower + 19} C"


def _group_key(record: ValidationFeedbackRecord, group_by: str) -> str:
    selectors: dict[str, Callable[[ValidationFeedbackRecord], str]] = {
        "metric": lambda item: item.metric_name,
        "metric_name": lambda item: item.metric_name,
        "topology": lambda item: item.topology,
        "model_version": lambda item: item.model_version,
        "evidence_type": lambda item: item.evidence_type.value,
        "evidence_quality": lambda item: item.evidence_quality.value,
        "confidence": lambda item: item.evidence_quality.value,
        "speed_range": lambda item: _speed_range(item.speed_rpm),
        "temperature_range": lambda item: _temperature_range(item.temperature_c),
    }
    if group_by not in selectors:
        raise ValueError(f"unsupported feedback grouping: {group_by}")
    return selectors[group_by](record)


def detect_bias_candidate(
    group_key: str,
    signed_percentage_errors: Iterable[float],
) -> BiasCandidate:
    values = tuple(float(value) for value in signed_percentage_errors)
    if len(values) < 3:
        return BiasCandidate(
            group_key,
            BiasCandidateStatus.INSUFFICIENT_EVIDENCE,
            len(values),
            statistics.median(values) if values else None,
            "Fewer than three compatible records; no aggregate bias interpretation.",
        )
    median = statistics.median(values)
    positive_fraction = sum(value > 0.0 for value in values) / len(values)
    negative_fraction = sum(value < 0.0 for value in values) / len(values)
    if median > 0.0 and positive_fraction >= 0.75:
        status = BiasCandidateStatus.POSSIBLE_POSITIVE_BIAS
        notes = "BIAS_CANDIDATE only; no correction factor is created or applied."
    elif median < 0.0 and negative_fraction >= 0.75:
        status = BiasCandidateStatus.POSSIBLE_NEGATIVE_BIAS
        notes = "BIAS_CANDIDATE only; no correction factor is created or applied."
    else:
        status = BiasCandidateStatus.NO_CLEAR_BIAS
        notes = "The available signed errors do not show a consistent direction."
    return BiasCandidate(group_key, status, len(values), median, notes)


def _aggregate_warnings(record_count: int) -> tuple[str, ...]:
    if record_count < 3:
        return ("INSUFFICIENT_FOR_AGGREGATE_INTERPRETATION",)
    if record_count < 10:
        return ("VERY_LIMITED_EVIDENCE",)
    return (
        "PROJECT_GOVERNANCE_THRESHOLD_MET",
        "N >= 10 does not by itself establish validation or representativeness.",
    )


def aggregate_feedback(
    records: Iterable[ValidationFeedbackRecord],
    *,
    group_by: str = "metric_name",
) -> tuple[FeedbackAggregate, ...]:
    groups: dict[str, list[ValidationFeedbackRecord]] = defaultdict(list)
    for record in records:
        if (
            record.comparability is not FeedbackComparability.BLOCKED
            and record.relative_error is not None
            and record.absolute_percentage_error is not None
        ):
            groups[_group_key(record, group_by)].append(record)

    aggregates: list[FeedbackAggregate] = []
    for key in sorted(groups):
        group = groups[key]
        signed = tuple(float(record.relative_error) * 100.0 for record in group)
        absolute = tuple(float(record.absolute_percentage_error) for record in group)
        aggregates.append(FeedbackAggregate(
            group_key=key,
            record_count=len(group),
            mean_signed_percentage_error=statistics.fmean(signed),
            median_signed_percentage_error=statistics.median(signed),
            mean_absolute_percentage_error=statistics.fmean(absolute),
            median_absolute_percentage_error=statistics.median(absolute),
            minimum_signed_percentage_error=min(signed),
            maximum_signed_percentage_error=max(signed),
            p10_signed_percentage_error=_percentile(signed, 0.10),
            p50_signed_percentage_error=_percentile(signed, 0.50),
            p90_signed_percentage_error=_percentile(signed, 0.90),
            bias_candidate=detect_bias_candidate(key, signed),
            warnings=_aggregate_warnings(len(group)),
        ))
    return tuple(aggregates)


def compare_feedback_to_uncertainty_envelope(
    record: ValidationFeedbackRecord,
    envelope: AccuracyEnvelopeResult,
) -> EnvelopeComparison:
    notes: list[str] = []
    if record.comparability is FeedbackComparability.BLOCKED:
        notes.append("Feedback comparison is blocked by metric semantics.")
    if record.metric_name != envelope.metric_name:
        notes.append("Feedback metric does not match the uncertainty-envelope metric.")
    if record.unit != envelope.unit:
        notes.append("Feedback unit does not match the uncertainty-envelope unit.")
    reference = record.normalized_reference_value
    if notes or reference is None:
        return EnvelopeComparison(
            record.metric_name, reference, record.unit, EnvelopePosition.UNAVAILABLE, tuple(notes)
        )
    if envelope.p10 is not None and envelope.p90 is not None and envelope.p10 <= reference <= envelope.p90:
        position = EnvelopePosition.INSIDE_MONTE_CARLO_P10_P90
        notes.append("Reference lies inside the declared Monte Carlo P10-P90 interval.")
    elif envelope.parameter_bound_min <= reference <= envelope.parameter_bound_max:
        position = EnvelopePosition.INSIDE_PARAMETER_BOUNDS_ONLY
        notes.append("Reference lies outside P10-P90 but inside the parameter-bound envelope.")
    else:
        position = EnvelopePosition.OUTSIDE_BOTH
        notes.extend((
            "Reference lies outside both declared intervals.",
            "This does not by itself prove model failure; model form, assumptions, measurement, and operating point remain possible causes.",
        ))
    return EnvelopeComparison(record.metric_name, reference, record.unit, position, tuple(notes))


def classify_validation_coverage(
    records: Iterable[ValidationFeedbackRecord],
) -> ExternalValidationCoverage:
    compatible = tuple(
        record for record in records
        if record.comparability is not FeedbackComparability.BLOCKED
    )
    if not compatible:
        return ExternalValidationCoverage.NONE
    credible_all = tuple(
        record for record in compatible
        if record.evidence_quality in {EvidenceQuality.HIGH, EvidenceQuality.MEDIUM}
    )
    topology_groups: dict[str, list[ValidationFeedbackRecord]] = defaultdict(list)
    for record in credible_all:
        topology_groups[record.topology].append(record)
    credible = tuple(max(topology_groups.values(), key=len)) if topology_groups else ()
    sources = {
        record.source_reference or record.source_name
        for record in credible
        if record.source_reference or record.source_name
    }
    speed_ranges = {_speed_range(record.speed_rpm) for record in credible}
    high_quality_count = sum(
        record.evidence_quality is EvidenceQuality.HIGH for record in credible
    )
    if (
        len(credible) >= 25
        and high_quality_count >= 10
        and len(sources) >= 3
        and len(speed_ranges) >= 3
    ):
        return ExternalValidationCoverage.STRONG
    if len(credible) >= 10 and len(sources) >= 2 and len(speed_ranges) >= 2:
        return ExternalValidationCoverage.MODERATE
    if len(credible) >= 3:
        return ExternalValidationCoverage.LIMITED
    return ExternalValidationCoverage.VERY_LIMITED


def build_validation_summary(
    records: Iterable[ValidationFeedbackRecord],
    *,
    recent_limit: int = 5,
) -> ValidationSummary:
    all_records = tuple(records)
    compatible = tuple(
        record for record in all_records
        if record.comparability is not FeedbackComparability.BLOCKED
    )
    aggregates = aggregate_feedback(all_records, group_by="metric_name")
    median_by_metric = {
        aggregate.group_key: aggregate.median_signed_percentage_error
        for aggregate in aggregates
    }
    bias_candidates = tuple(
        aggregate.bias_candidate
        for aggregate in aggregates
        if aggregate.bias_candidate.status in {
            BiasCandidateStatus.POSSIBLE_POSITIVE_BIAS,
            BiasCandidateStatus.POSSIBLE_NEGATIVE_BIAS,
        }
    )
    coverage = classify_validation_coverage(all_records)
    warnings = [
        "Coverage is a project governance summary, not a statistical validation claim.",
        "Feedback never updates model parameters automatically.",
    ]
    if len(compatible) < 3:
        warnings.append("INSUFFICIENT_FOR_AGGREGATE_INTERPRETATION")
    return ValidationSummary(
        total_records=len(all_records),
        compatible_records=len(compatible),
        blocked_records=len(all_records) - len(compatible),
        high_quality_records=sum(
            record.evidence_quality is EvidenceQuality.HIGH for record in all_records
        ),
        metric_counts=dict(sorted(Counter(record.metric_name for record in all_records).items())),
        median_error_by_metric=median_by_metric,
        validation_coverage=coverage,
        bias_candidates=bias_candidates,
        recent_records=tuple(sorted(all_records, key=lambda item: item.created_at, reverse=True)[:recent_limit]),
        warnings=tuple(warnings),
    )
