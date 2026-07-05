from __future__ import annotations

import json

from motor_core import calculate_from_legacy_params
from motor_core.validation_comparison import compare_validation_record
from motor_core.validation_loader import load_validation_record, load_validation_record_from_dict
from motor_core.validation_records import ValidationComparabilityStatus

from helpers import build_sample_legacy_params, validation_data_root


def _creator_record_path():
    return validation_data_root() / "imported" / "creator_pmsm_initial_record.json"


def _load_creator_record_dict() -> dict:
    return json.loads(_creator_record_path().read_text(encoding="utf-8"))


def test_creator_pmsm_formal_record_is_blocked_by_topology_mismatch() -> None:
    record = load_validation_record(_creator_record_path())
    result = calculate_from_legacy_params(build_sample_legacy_params(waveform="pmsm_sinusoidal"))
    report = compare_validation_record(record, result, result)
    statuses = {item.metric_name: item.comparability_status for item in report.metric_results}

    assert statuses["rated_torque_nm"] is ValidationComparabilityStatus.TOPOLOGY_MISMATCH
    assert statuses["back_emf_phase_peak_v"] is ValidationComparabilityStatus.TOPOLOGY_MISMATCH
    assert statuses["phase_resistance_ohm"] is ValidationComparabilityStatus.TOPOLOGY_MISMATCH
    assert statuses["rated_current_a"] is ValidationComparabilityStatus.TOPOLOGY_MISMATCH


def test_creator_pmsm_record_cannot_be_compared_directly_with_bldc_result() -> None:
    record = load_validation_record(_creator_record_path())
    bldc_result = calculate_from_legacy_params(build_sample_legacy_params(waveform="bldc_120_degree"))
    report = compare_validation_record(record, bldc_result, bldc_result)

    assert report.metric_results[0].comparability_status is ValidationComparabilityStatus.CONTROL_STRATEGY_MISMATCH


def test_creator_pmsm_forced_phase_line_and_rms_peak_mismatches_stay_blocked() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params(waveform="pmsm_sinusoidal"))

    phase_line_record = _load_creator_record_dict()
    phase_line_record["topology"] = "双转子、单定子、双气隙"
    phase_line_record["excluded_comparisons"] = {}
    phase_line_record["expected_outputs"] = {
        "back_emf_line_rms_v": {
            "metric_name": "back_emf_line_rms_v",
            "status": "provided",
            "value": 10.0,
            "unit": "V",
            "quantity_scope": "phase",
            "value_kind": "rms",
            "current_basis": None,
            "notes": "Intentional mismatch for test."
        }
    }
    phase_line_report = compare_validation_record(load_validation_record_from_dict(phase_line_record), result, result)

    rms_peak_record = _load_creator_record_dict()
    rms_peak_record["topology"] = "双转子、单定子、双气隙"
    rms_peak_record["excluded_comparisons"] = {}
    rms_peak_record["expected_outputs"] = {
        "back_emf_phase_peak_v": {
            "metric_name": "back_emf_phase_peak_v",
            "status": "provided",
            "value": 10.0,
            "unit": "V",
            "quantity_scope": "phase",
            "value_kind": "rms",
            "current_basis": None,
            "notes": "Intentional mismatch for test."
        }
    }
    rms_peak_report = compare_validation_record(load_validation_record_from_dict(rms_peak_record), result, result)

    assert phase_line_report.metric_results[0].comparability_status is ValidationComparabilityStatus.SEMANTICS_MISMATCH
    assert rms_peak_report.metric_results[0].comparability_status is ValidationComparabilityStatus.SEMANTICS_MISMATCH


def test_creator_pmsm_unavailable_fields_produce_exclusion_reasons() -> None:
    record = load_validation_record(_creator_record_path())
    result = calculate_from_legacy_params(build_sample_legacy_params(waveform="pmsm_sinusoidal"))
    report = compare_validation_record(record, result, result)
    metric_results = {item.metric_name: item for item in report.metric_results}

    assert metric_results["phase_inductance_h"].comparability_status is ValidationComparabilityStatus.NOT_AVAILABLE
    assert metric_results["phase_inductance_h"].exclusion_reason
    assert metric_results["required_voltage_v"].comparability_status is ValidationComparabilityStatus.NOT_AVAILABLE
    assert metric_results["required_voltage_v"].exclusion_reason


def test_creator_pmsm_comparison_does_not_modify_production_outputs() -> None:
    record = load_validation_record(_creator_record_path())
    result = calculate_from_legacy_params(build_sample_legacy_params(waveform="pmsm_sinusoidal"))
    before = (
        result.performance.required_voltage_v,
        result.performance.copper_loss_w,
        result.performance.efficiency_percent,
        result.electrical.legacy_back_emf_constant_line_rms_v_per_krpm,
    )

    compare_validation_record(record, result, result)
    after = (
        result.performance.required_voltage_v,
        result.performance.copper_loss_w,
        result.performance.efficiency_percent,
        result.electrical.legacy_back_emf_constant_line_rms_v_per_krpm,
    )

    assert before == after
