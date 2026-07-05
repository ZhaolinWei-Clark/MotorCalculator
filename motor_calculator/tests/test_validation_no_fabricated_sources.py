from __future__ import annotations

from pathlib import Path

import pytest

from motor_core.validation_loader import load_validation_record, load_validation_record_from_dict
from motor_core.validation_records import ValidationEvidenceLevel, ValidationRecordError, ValidationSourceType

from helpers import build_sample_validation_record_dict, validation_data_root


def test_synthetic_example_is_never_marked_as_external_experimental_evidence() -> None:
    record = load_validation_record(validation_data_root() / "templates" / "example_synthetic_record.json")

    assert record.source_type is ValidationSourceType.ANALYTICAL_REFERENCE
    assert record.evidence_level is ValidationEvidenceLevel.LEVEL_1_ANALYTICAL
    assert record.synthetic is True
    assert record.not_for_accuracy_claims is True


def test_imported_directory_contains_no_fabricated_json_payloads() -> None:
    imported_dir = validation_data_root() / "imported"
    imported_json = sorted(path.name for path in imported_dir.glob("*.json"))

    assert imported_dir.exists()
    assert imported_json == ["creator_pmsm_initial_record.json"]

    record = load_validation_record(imported_dir / "creator_pmsm_initial_record.json")
    assert record.synthetic is False
    assert record.source_type is ValidationSourceType.PUBLISHED_BENCHMARK
    assert record.source_identifier == "DOI: 10.3217/sns1d-77m43"


def test_manufacturer_data_cannot_pretend_to_be_controlled_measurement() -> None:
    record = build_sample_validation_record_dict(
        source_type="manufacturer_data",
        evidence_level="LEVEL_3_CONTROLLED_MEASUREMENT",
        synthetic=False,
        not_for_accuracy_claims=False,
    )

    with pytest.raises(ValidationRecordError, match="source_type=manufacturer_data 不允许 evidence_level=LEVEL_3_CONTROLLED_MEASUREMENT"):
        load_validation_record_from_dict(record)
