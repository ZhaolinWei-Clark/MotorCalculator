"""Read-only accuracy metrics for compatible validation comparisons."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class AccuracyMetricStatus(str, Enum):
    VALID = "valid"
    NEAR_ZERO_REFERENCE = "near_zero_reference"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AccuracyMetrics:
    prediction: float | None
    reference: float | None
    status: AccuracyMetricStatus
    absolute_error: float | None
    absolute_error_magnitude: float | None
    relative_error: float | None
    absolute_percentage_error: float | None
    symmetric_percentage_error: float | None
    notes: str | None = None


def _require_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return value


def compute_accuracy_metrics(
    prediction: float | None,
    reference: float | None,
    *,
    near_zero_threshold: float = 1e-12,
) -> AccuracyMetrics:
    """Compute error metrics without mutating either source value.

    Percentage errors are intentionally unavailable for a near-zero reference.
    Symmetric percentage error is retained when its denominator is stable.
    """

    if near_zero_threshold < 0.0 or not math.isfinite(near_zero_threshold):
        raise ValueError("near_zero_threshold must be a finite non-negative number.")
    if prediction is None or reference is None:
        return AccuracyMetrics(
            prediction=prediction,
            reference=reference,
            status=AccuracyMetricStatus.UNAVAILABLE,
            absolute_error=None,
            absolute_error_magnitude=None,
            relative_error=None,
            absolute_percentage_error=None,
            symmetric_percentage_error=None,
            notes="Prediction or reference is unavailable.",
        )

    prediction_value = _require_finite("prediction", prediction)
    reference_value = _require_finite("reference", reference)
    absolute_error = prediction_value - reference_value
    absolute_error_magnitude = abs(absolute_error)
    symmetric_denominator = abs(prediction_value) + abs(reference_value)
    symmetric_percentage_error = (
        200.0 * absolute_error_magnitude / symmetric_denominator
        if symmetric_denominator > near_zero_threshold
        else None
    )

    if abs(reference_value) <= near_zero_threshold:
        return AccuracyMetrics(
            prediction=prediction_value,
            reference=reference_value,
            status=AccuracyMetricStatus.NEAR_ZERO_REFERENCE,
            absolute_error=absolute_error,
            absolute_error_magnitude=absolute_error_magnitude,
            relative_error=None,
            absolute_percentage_error=None,
            symmetric_percentage_error=symmetric_percentage_error,
            notes="Reference is near zero; relative and conventional percentage errors are unstable.",
        )

    relative_error = absolute_error / reference_value
    return AccuracyMetrics(
        prediction=prediction_value,
        reference=reference_value,
        status=AccuracyMetricStatus.VALID,
        absolute_error=absolute_error,
        absolute_error_magnitude=absolute_error_magnitude,
        relative_error=relative_error,
        absolute_percentage_error=100.0 * absolute_error_magnitude / abs(reference_value),
        symmetric_percentage_error=symmetric_percentage_error,
    )
