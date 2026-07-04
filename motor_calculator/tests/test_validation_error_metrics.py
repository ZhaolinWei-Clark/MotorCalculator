from __future__ import annotations

import math

from motor_core import calculate_from_legacy_params
from motor_core.validation_comparison import compare_validation_record
from motor_core.validation_loader import load_validation_record_from_dict

from helpers import build_sample_legacy_params, build_sample_validation_record_dict


def test_absolute_and_relative_error_are_computed_correctly() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params())
    expected_value = result.performance.legacy_rated_torque_nm + 0.5
    record = build_sample_validation_record_dict()
    record["expected_outputs"]["rated_torque_nm"]["value"] = expected_value

    report = compare_validation_record(load_validation_record_from_dict(record), result, result)
    metric = report.metric_results[0]

    assert math.isclose(metric.absolute_error_legacy or 0.0, result.performance.legacy_rated_torque_nm - expected_value)
    assert math.isclose(
        metric.relative_error_legacy or 0.0,
        (result.performance.legacy_rated_torque_nm - expected_value) / expected_value,
    )
    assert math.isclose(metric.absolute_error_revised or 0.0, result.performance.revised_rated_torque_nm - expected_value)


def test_relative_error_handles_zero_expected_value_safely() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params())
    record = build_sample_validation_record_dict()
    record["expected_outputs"]["rated_torque_nm"]["value"] = 0.0

    report = compare_validation_record(load_validation_record_from_dict(record), result, result)
    metric = report.metric_results[0]

    assert metric.absolute_error_legacy == result.performance.legacy_rated_torque_nm
    assert metric.relative_error_legacy is None


def test_explicit_unit_conversion_allows_ke_comparison() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params())
    record = build_sample_validation_record_dict()
    record["expected_outputs"] = {
        "back_emf_constant_line_rms_v_per_krpm": {
            "metric_name": "back_emf_constant_line_rms_v_per_krpm",
            "status": "provided",
            "value": result.electrical.revised_back_emf_constant_line_rms_v_per_rad_s,
            "unit": "V/(rad/s)",
            "quantity_scope": "line",
            "value_kind": "rms",
            "current_basis": None,
            "notes": "测试显式单位换算。"
        }
    }

    report = compare_validation_record(load_validation_record_from_dict(record), result, result)
    metric = report.metric_results[0]

    assert metric.conversion_log
    assert math.isclose(
        metric.predicted_revised_value or 0.0,
        metric.expected_value or 0.0,
        rel_tol=1e-12,
    )
