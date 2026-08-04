from __future__ import annotations

import pytest

from validation.accuracy_metrics import AccuracyMetricStatus, compute_accuracy_metrics


def test_absolute_and_relative_errors_are_correct() -> None:
    metrics = compute_accuracy_metrics(11.0, 10.0)

    assert metrics.status is AccuracyMetricStatus.VALID
    assert metrics.absolute_error == pytest.approx(1.0)
    assert metrics.absolute_error_magnitude == pytest.approx(1.0)
    assert metrics.relative_error == pytest.approx(0.1)
    assert metrics.absolute_percentage_error == pytest.approx(10.0)
    assert metrics.symmetric_percentage_error == pytest.approx(200.0 / 21.0)


def test_near_zero_reference_does_not_emit_unstable_percentage_error() -> None:
    metrics = compute_accuracy_metrics(0.1, 0.0)

    assert metrics.status is AccuracyMetricStatus.NEAR_ZERO_REFERENCE
    assert metrics.absolute_error == pytest.approx(0.1)
    assert metrics.relative_error is None
    assert metrics.absolute_percentage_error is None
    assert metrics.symmetric_percentage_error == pytest.approx(200.0)


def test_unavailable_comparison_stays_unavailable() -> None:
    metrics = compute_accuracy_metrics(None, 10.0)

    assert metrics.status is AccuracyMetricStatus.UNAVAILABLE
    assert metrics.absolute_error is None
    assert metrics.relative_error is None


def test_non_finite_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        compute_accuracy_metrics(float("nan"), 1.0)
