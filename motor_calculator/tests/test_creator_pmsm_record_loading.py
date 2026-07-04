from __future__ import annotations

import json

from helpers import validation_data_root


def _load_creator_pmsm_draft() -> dict:
    draft_path = (
        validation_data_root()
        / "source_notes"
        / "creator_pmsm"
        / "creator_pmsm_initial_record_draft.json"
    )
    return json.loads(draft_path.read_text(encoding="utf-8"))


def test_creator_pmsm_draft_contains_traceable_source_metadata() -> None:
    draft = _load_creator_pmsm_draft()
    metadata = draft["source_metadata"]

    assert draft["record_creation_blocked"] is True
    assert metadata["source_title"] == "CREATOR Case: Permanent Magnet Synchronous Motor Data"
    assert metadata["motor_type"] == "PMSM"
    assert metadata["doi"] == "10.3217/sns1d-77m43"
    assert metadata["repository_url"] == "https://repository.tugraz.at/records/sns1d-77m43"
    assert metadata["license_or_usage_note"]
    assert metadata["access_date"] == "2026-07-04"


def test_creator_pmsm_unknown_fields_are_not_encoded_as_zero() -> None:
    draft = _load_creator_pmsm_draft()
    unknown_like_statuses = {
        "unavailable",
        "not_applicable",
        "needs_manual_extraction",
        "needs_semantics_check",
        "needs_unit_conversion",
        "license_restricted",
    }

    for section_name in ("input_parameters", "expected_outputs"):
        for field_name, payload in draft[section_name].items():
            if payload["status"] in unknown_like_statuses:
                assert payload["value"] is None, f"{section_name}.{field_name} must keep unknowns as null"


def test_creator_pmsm_formal_record_is_not_created_before_numeric_traceability_exists() -> None:
    draft = _load_creator_pmsm_draft()
    formal_record_path = validation_data_root().parent / draft["formal_record_path"]

    assert draft["formal_record_ready"] is False
    assert formal_record_path.exists() is False
