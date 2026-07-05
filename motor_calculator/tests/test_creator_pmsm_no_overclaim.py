from __future__ import annotations

from motor_core.validation_loader import load_validation_record

from helpers import validation_data_root


def _creator_record_path():
    return validation_data_root() / "imported" / "creator_pmsm_initial_record.json"


def test_creator_pmsm_license_note_does_not_claim_commercial_reuse() -> None:
    record = load_validation_record(_creator_record_path())

    assert "CC BY-NC 4.0" in record.license_or_usage_note
    assert "commercial use allowed" not in record.license_or_usage_note


def test_creator_pmsm_formal_record_explicitly_blocks_accuracy_overclaim() -> None:
    record = load_validation_record(_creator_record_path())

    assert record.synthetic is False
    assert record.not_for_accuracy_claims is True
    assert "does not validate the full project" in record.data_quality_notes
    assert "does not validate BLDC" in record.data_quality_notes
    assert "does not validate AFPM" in record.data_quality_notes


def test_creator_pmsm_supporting_docs_state_no_bldc_or_afpm_extrapolation() -> None:
    report_path = validation_data_root().parent / "docs" / "creator_pmsm_import_report_zh.md"
    content = report_path.read_text(encoding="utf-8")

    assert "来源机型是 `PMSM`，不是 `BLDC`" in content
    assert "来源机器是径向 PMSM，不是当前项目默认 `AFPM`" in content
    assert "当前不可用于整体准确度声明" in content
