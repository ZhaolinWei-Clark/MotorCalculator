from __future__ import annotations

from motor_core import calculate_from_legacy_params
from motor_core.validation_comparison import compare_validation_record
from motor_core.validation_loader import load_validation_record_from_dict

from helpers import build_sample_legacy_params, build_sample_validation_record_dict


def test_uncertainty_band_is_recorded_separately_from_model_error() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params())
    report = compare_validation_record(load_validation_record_from_dict(build_sample_validation_record_dict()), result, result)
    metric = report.metric_results[0]

    assert metric.uncertainty_band["absolute"] == 0.05
    assert metric.uncertainty_band["relative"] == 0.02
    assert metric.absolute_error_legacy is not None


def test_tolerance_flags_are_computed_without_merging_uncertainty_into_error() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params())
    record = build_sample_validation_record_dict()
    record["expected_outputs"]["rated_torque_nm"]["value"] = result.performance.legacy_rated_torque_nm + 1.0
    record["tolerances"]["rated_torque_nm"]["absolute"] = 0.1

    report = compare_validation_record(load_validation_record_from_dict(record), result, result)
    metric = report.metric_results[0]

    assert metric.within_tolerance_legacy is False
