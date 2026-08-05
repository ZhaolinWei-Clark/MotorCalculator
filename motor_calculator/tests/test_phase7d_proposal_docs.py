from __future__ import annotations

import hashlib
from pathlib import Path

from validation.phase7c_reconstruction import build_phase7c_result


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_doc(name: str) -> str:
    return (DOCS_DIR / name).read_text(encoding="utf-8")


def test_gap_matrix_covers_every_phase7c_blocked_row() -> None:
    matrix = _read_doc("phase7d_afpm_model_capability_gap_matrix_zh.md")
    result = build_phase7c_result(REPO_ROOT)
    source_labels = {
        "abdelli_2026_dssr_afpm": "Abdelli 2026",
        "price_2009_coreless_afpm_generator": "Price 2009",
        "parviainen_2005_afpm_prototype": "Parviainen 2005",
        "hosseini_2008_coreless_afpm_generator": "Hosseini 2008",
    }

    assert len(result.blockers) == 14
    for row in result.blockers:
        expected_row_prefix = f"| {source_labels[row.source_id]} | {row.metric} |"
        assert expected_row_prefix in matrix


def test_proposal_covers_required_capabilities_and_priorities() -> None:
    gap_matrix = _read_doc("phase7d_afpm_model_capability_gap_matrix_zh.md")
    impact = _read_doc("phase7d_capability_impact_analysis_zh.md")
    proposal = _read_doc("phase7d_model_upgrade_proposal_zh.md")
    combined = "\n".join((gap_matrix, impact, proposal))

    for required_term in (
        "AFPMTopologyType",
        "SSDR",
        "DSSR",
        "SINGLE_SIDED",
        "AFPMWindingSpec",
        "back-EMF",
        "Ld/Lq",
        "torque boundary",
        "P0",
        "P1",
        "P2",
    ):
        assert required_term in combined

    assert "immediate unlock" in impact
    assert "Phase 7E" in proposal
    assert "P0 schema foundation" in proposal
    assert "sandbox-only" in proposal
    assert "no physics、no formula、no GUI、no calibration" in proposal
    assert "不能被 `motor_core/calculations.py`" in proposal


def test_reading_phase7d_proposals_does_not_mutate_protected_files() -> None:
    calculations = REPO_ROOT / "motor_calculator" / "motor_core" / "calculations.py"
    legacy = REPO_ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json"
    before = (_sha256(calculations), _sha256(legacy))

    for name in (
        "phase7d_afpm_model_capability_gap_matrix_zh.md",
        "phase7d_capability_impact_analysis_zh.md",
        "phase7d_model_upgrade_proposal_zh.md",
    ):
        assert _read_doc(name)

    assert (_sha256(calculations), _sha256(legacy)) == before
    assert before[1] == "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"
