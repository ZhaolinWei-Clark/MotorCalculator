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


def test_creator_pmsm_license_note_does_not_claim_commercial_reuse() -> None:
    draft = _load_creator_pmsm_draft()
    license_note = draft["source_metadata"]["license_or_usage_note"]

    assert "CC BY-NC 4.0" in license_note
    assert "commercial use allowed" not in license_note


def test_creator_pmsm_draft_explicitly_blocks_accuracy_overclaim() -> None:
    draft = _load_creator_pmsm_draft()
    assertions = draft["no_overclaim_assertions"]

    assert assertions["does_not_validate_entire_project"] is True
    assert assertions["does_not_validate_bldc"] is True
    assert assertions["does_not_validate_afpm_by_default"] is True
    assert assertions["not_ready_for_accuracy_claims"] is True


def test_creator_pmsm_supporting_docs_state_no_blcd_or_afpm_extrapolation() -> None:
    report_path = validation_data_root().parent / "docs" / "creator_pmsm_import_report_zh.md"
    content = report_path.read_text(encoding="utf-8")

    assert "不能外推到 `BLDC`" in content
    assert "`AFPM`" in content
