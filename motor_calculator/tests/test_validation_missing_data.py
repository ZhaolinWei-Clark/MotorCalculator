from __future__ import annotations

import pytest

from motor_core import calculate_from_legacy_params
from motor_core.validation_comparison import compare_validation_record
from motor_core.validation_loader import load_validation_record_from_dict
from motor_core.validation_records import ValidationComparabilityStatus, ValidationRecordError

from helpers import build_sample_legacy_params, build_sample_validation_record_dict


def test_unknown_values_are_not_silently_converted_to_zero() -> None:
    record = build_sample_validation_record_dict()
    record["expected_outputs"]["rated_torque_nm"]["status"] = "unavailable"
    record["expected_outputs"]["rated_torque_nm"]["value"] = 0

    with pytest.raises(ValidationRecordError, match="不能把未知 expected 写成 0"):
        load_validation_record_from_dict(record)


def test_missing_current_basis_prevents_torque_constant_comparison() -> None:
    result = calculate_from_legacy_params(build_sample_legacy_params())
    record = build_sample_validation_record_dict()
    record["expected_outputs"] = {
        "torque_constant_nm_per_a": {
            "metric_name": "torque_constant_nm_per_a",
            "status": "provided",
            "value": 0.2,
            "unit": "Nm/A",
            "quantity_scope": "phase",
            "value_kind": "rms",
            "current_basis": None,
            "notes": "故意缺失 current_basis。"
        }
    }

    report = compare_validation_record(load_validation_record_from_dict(record), result, result)

    assert report.metric_results[0].comparability_status is ValidationComparabilityStatus.INSUFFICIENT_INPUT_DATA
