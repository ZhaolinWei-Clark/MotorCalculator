from __future__ import annotations

from motor_core import calculate_from_legacy_params
from motor_core.validation_comparison import compare_validation_record
from motor_core.validation_loader import load_validation_record_from_dict

from helpers import build_sample_legacy_params, build_sample_validation_record_dict


def test_validation_comparison_does_not_modify_production_outputs() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params())
    before = (
        result.performance.required_voltage_v,
        result.performance.copper_loss_w,
        result.performance.efficiency_percent,
        result.electrical.legacy_back_emf_constant_line_rms_v_per_krpm,
    )

    report = compare_validation_record(load_validation_record_from_dict(build_sample_validation_record_dict()), result, result)
    after = (
        result.performance.required_voltage_v,
        result.performance.copper_loss_w,
        result.performance.efficiency_percent,
        result.electrical.legacy_back_emf_constant_line_rms_v_per_krpm,
    )

    assert report.metric_results
    assert before == after
