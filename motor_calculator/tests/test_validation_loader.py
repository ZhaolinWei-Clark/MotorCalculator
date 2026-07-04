from __future__ import annotations

import pytest

from motor_core.validation_loader import convert_value_between_units, load_validation_record_from_dict
from motor_core.validation_records import ValidationRecordError

from helpers import build_sample_validation_record_dict


def test_valid_record_can_be_loaded_from_dict() -> None:
    record = load_validation_record_from_dict(build_sample_validation_record_dict())

    assert record.validation_id == "sample_validation_record"
    assert record.input_parameters["winding_connection"].value == "Y"


def test_missing_external_provenance_rejects_accuracy_style_external_claims() -> None:
    record = build_sample_validation_record_dict(
        source_type="published_benchmark",
        evidence_level="LEVEL_2_PUBLISHED_OR_FEA",
        synthetic=False,
        not_for_accuracy_claims=False,
        source_identifier=None,
        source_file=None,
        source_page_or_section=None,
    )

    with pytest.raises(ValidationRecordError, match="至少提供 source_identifier、source_file 或 source_page_or_section"):
        load_validation_record_from_dict(record)


def test_waveform_must_match_control_mode() -> None:
    record = build_sample_validation_record_dict()
    record["input_parameters"]["back_emf_waveform"]["value"] = "trapezoidal"

    with pytest.raises(ValidationRecordError, match="PMSM 记录只能与 sinusoidal"):
        load_validation_record_from_dict(record)


def test_supported_unit_conversion_is_explicit() -> None:
    converted, note = convert_value_between_units(1.0, "V/(rad/s)", "V/krpm")

    assert converted > 0.0
    assert "显式单位转换" in note
