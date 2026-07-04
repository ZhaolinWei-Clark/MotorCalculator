from __future__ import annotations

from motor_core import calculate_from_legacy_params
from motor_core.validation_comparison import compare_validation_record
from motor_core.validation_loader import load_validation_record_from_dict
from motor_core.validation_records import ValidationComparabilityStatus

from helpers import build_sample_legacy_params, build_sample_validation_record_dict


def test_phase_line_mismatch_blocks_comparison() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params())
    record = build_sample_validation_record_dict()
    record["expected_outputs"] = {
        "back_emf_line_rms_v": {
            "metric_name": "back_emf_line_rms_v",
            "status": "provided",
            "value": 24.0,
            "unit": "V",
            "quantity_scope": "phase",
            "value_kind": "rms",
            "current_basis": None,
            "notes": "故意错误的 phase/line 语义。"
        }
    }
    report = compare_validation_record(load_validation_record_from_dict(record), result, result)

    assert report.metric_results[0].comparability_status is ValidationComparabilityStatus.SEMANTICS_MISMATCH


def test_rms_peak_mismatch_blocks_comparison() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params())
    record = build_sample_validation_record_dict()
    record["expected_outputs"] = {
        "back_emf_phase_rms_v": {
            "metric_name": "back_emf_phase_rms_v",
            "status": "provided",
            "value": 10.0,
            "unit": "V",
            "quantity_scope": "phase",
            "value_kind": "peak",
            "current_basis": None,
            "notes": "故意错误的 RMS/peak 语义。"
        }
    }
    report = compare_validation_record(load_validation_record_from_dict(record), result, result)

    assert report.metric_results[0].comparability_status is ValidationComparabilityStatus.SEMANTICS_MISMATCH


def test_pmsm_bldc_mode_mismatch_blocks_comparison() -> None:
    pmsm_result = calculate_from_legacy_params(build_sample_legacy_params(waveform="正弦波"))
    record = build_sample_validation_record_dict(control_mode="bldc_120_degree")
    record["input_parameters"]["back_emf_waveform"]["value"] = "trapezoidal"
    report = compare_validation_record(load_validation_record_from_dict(record), pmsm_result, pmsm_result)

    assert report.metric_results[0].comparability_status is ValidationComparabilityStatus.CONTROL_STRATEGY_MISMATCH


def test_y_delta_mismatch_blocks_comparison() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params())
    record = build_sample_validation_record_dict()
    record["input_parameters"]["winding_connection"]["value"] = "Delta"
    report = compare_validation_record(load_validation_record_from_dict(record), result, result)

    assert report.metric_results[0].comparability_status is ValidationComparabilityStatus.SEMANTICS_MISMATCH
