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


def test_creator_pmsm_draft_blocks_direct_bldc_and_topology_comparisons() -> None:
    draft = _load_creator_pmsm_draft()
    blockers = draft["comparability_precheck"]["blocked_fields"]

    assert "BLDC" in blockers["motor_type_boundary"]
    assert "AFPM" in blockers["topology_boundary"]


def test_creator_pmsm_draft_blocks_phase_line_and_rms_peak_mismatches() -> None:
    draft = _load_creator_pmsm_draft()
    blockers = draft["comparability_precheck"]["blocked_fields"]

    assert "Phase vs line" in blockers["phase_line_boundary"]
    assert "RMS vs peak" in blockers["rms_peak_boundary"]


def test_creator_pmsm_draft_records_metric_level_exclusion_reasons() -> None:
    draft = _load_creator_pmsm_draft()
    excluded = draft["comparability_precheck"]["excluded_comparisons"]

    assert "current_basis" in excluded["torque_constant_nm_per_a"]
    assert "phase/line" in excluded["back_emf_line_rms_v"]
    assert "required_voltage_v" in excluded["required_voltage_v"]
