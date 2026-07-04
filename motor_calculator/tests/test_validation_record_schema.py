from __future__ import annotations

import pytest

from motor_core.validation_loader import load_validation_record, load_validation_record_from_dict
from motor_core.validation_records import (
    SUPPORTED_VALIDATION_METRICS,
    ValidationMetricMaturity,
    ValidationSourceType,
)
from motor_core.validation_records import ValidationRecordError

from helpers import build_sample_validation_record_dict, validation_data_root


def test_synthetic_example_schema_loads_with_expected_provenance_flags() -> None:
    record = load_validation_record(validation_data_root() / "templates" / "example_synthetic_record.json")

    assert record.source_type is ValidationSourceType.ANALYTICAL_REFERENCE
    assert record.synthetic is True
    assert record.not_for_accuracy_claims is True
    assert (
        SUPPORTED_VALIDATION_METRICS["rated_torque_nm"]
        is ValidationMetricMaturity.REVISED_DEFINED_PARALLEL
    )
    assert (
        SUPPORTED_VALIDATION_METRICS["phase_inductance_h"]
        is ValidationMetricMaturity.LEGACY_OR_PROVISIONAL
    )


def test_unknown_values_must_not_be_encoded_as_zero_placeholders() -> None:
    record = build_sample_validation_record_dict()
    record["input_parameters"]["air_gap_m"] = {
        "status": "unavailable",
        "value": 0,
        "unit": "m",
        "notes": "错误示例。"
    }

    with pytest.raises(ValidationRecordError, match="不能用 0"):
        load_validation_record_from_dict(record)
