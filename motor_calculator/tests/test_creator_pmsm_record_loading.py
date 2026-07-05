from __future__ import annotations

import json

from motor_core.validation_loader import load_validation_record
from motor_core.validation_records import ValidationEvidenceLevel, ValidationSourceType

from helpers import validation_data_root


def _creator_record_path():
    return validation_data_root() / "imported" / "creator_pmsm_initial_record.json"


def _load_creator_pmsm_record_json() -> dict:
    return json.loads(_creator_record_path().read_text(encoding="utf-8"))


def test_creator_pmsm_formal_record_loads_with_traceable_source_metadata() -> None:
    record = load_validation_record(_creator_record_path())

    assert record.source_type is ValidationSourceType.PUBLISHED_BENCHMARK
    assert record.evidence_level is ValidationEvidenceLevel.LEVEL_2_PUBLISHED_OR_FEA
    assert record.motor_type == "PMSM"
    assert record.validation_id == "creator_pmsm_initial_record"
    assert record.source_title == "CREATOR Case: Permanent Magnet Synchronous Motor Data"
    assert record.source_identifier == "DOI: 10.3217/sns1d-77m43"
    assert "CC BY-NC 4.0" in record.license_or_usage_note


def test_creator_pmsm_unavailable_fields_are_not_encoded_as_zero() -> None:
    record = _load_creator_pmsm_record_json()

    for section_name in ("input_parameters", "expected_outputs"):
        for field_name, payload in record[section_name].items():
            if payload["status"] in {"unavailable", "not_applicable"}:
                assert payload["value"] is None, f"{section_name}.{field_name} must keep unknowns as null"


def test_creator_pmsm_formal_record_exists_and_keeps_accuracy_claims_disabled() -> None:
    record = load_validation_record(_creator_record_path())

    assert _creator_record_path().exists() is True
    assert record.synthetic is False
    assert record.not_for_accuracy_claims is True
