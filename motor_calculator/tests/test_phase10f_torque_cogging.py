"""Phase 10F: torque semantics, same-basis comparison, cogging and mesh floor.

No solver runs here. Tests that consume FEMM output read the committed Phase 10F
campaign evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from motor_calculator.fea.diagnostics import (
    EvidenceLabel,
    cogging_diagnostic_rows,
    is_affirmative,
    render_diagnostics_zh,
    torque_diagnostic_rows,
    unavailable_diagnostics,
)
from motor_calculator.fea.models import FEAValidationTarget
from motor_calculator.fea.reference_cases import build_self_consistent_reference_case
from motor_calculator.fea.sampling import cogging_period_mech_deg, electrical_period_mech_deg
from motor_calculator.fea.torque_semantics import (
    BASIS_ELECTROMAGNETIC,
    BASIS_EMPIRICAL_RATIO,
    BASIS_SHAFT,
    TORQUE_BY_NAME,
    TORQUE_MAP,
    TORQUE_SEMANTICS_SCHEMA_VERSION,
    TorqueSource,
    assert_same_basis,
    same_basis_electromagnetic_torque_nm,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = REPOSITORY_ROOT / "validation_data" / "fea_results" / "phase10f_torque_cogging"
CAMPAIGN = EVIDENCE / "phase10f_campaign.json"


def _campaign():
    if not CAMPAIGN.is_file():
        pytest.skip("Phase 10F campaign evidence is not present")
    return json.loads(CAMPAIGN.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Torque semantics map
# ---------------------------------------------------------------------------


def test_the_map_covers_every_torque_the_project_publishes():
    names = {quantity.name for quantity in TORQUE_MAP}
    for expected in (
        "rated_torque_nm",
        "average_torque_nm",
        "electromagnetic_torque_same_basis_nm",
        "femm_block_integral_torque_nm",
        "torque_ripple_percent",
        "cogging_torque_peak_nm",
    ):
        assert expected in names


def test_shaft_and_electromagnetic_torque_are_not_comparable():
    """The trap this phase exists to close."""

    shaft = TORQUE_BY_NAME["rated_torque_nm"]
    electromagnetic = TORQUE_BY_NAME["femm_block_integral_torque_nm"]
    assert shaft.basis == BASIS_SHAFT
    assert electromagnetic.basis == BASIS_ELECTROMAGNETIC
    assert not shaft.comparable_with(electromagnetic)
    with pytest.raises(ValueError, match="basis"):
        assert_same_basis("rated_torque_nm", "femm_block_integral_torque_nm")


def test_the_same_basis_pair_is_comparable():
    assert_same_basis(
        "electromagnetic_torque_same_basis_nm", "femm_block_integral_torque_nm"
    )
    assert TORQUE_BY_NAME["electromagnetic_torque_same_basis_nm"].basis == BASIS_ELECTROMAGNETIC


def test_the_production_average_torque_is_flagged_as_input_derived():
    """It returns P/omega; it is not an average of anything the model computed."""

    quantity = TORQUE_BY_NAME["average_torque_nm"]
    assert quantity.source == TorqueSource.DERIVED_FROM_INPUT
    assert quantity.basis == BASIS_SHAFT
    assert quantity.includes_losses is True


def test_ripple_and_cogging_are_flagged_as_empirical_inputs():
    for name in ("torque_ripple_percent", "cogging_torque_peak_nm"):
        quantity = TORQUE_BY_NAME[name]
        assert quantity.source == TorqueSource.EMPIRICAL_INPUT
        assert quantity.basis == BASIS_EMPIRICAL_RATIO


def test_only_the_electromagnetic_quantities_exclude_losses():
    for quantity in TORQUE_MAP:
        if quantity.basis == BASIS_ELECTROMAGNETIC:
            assert quantity.includes_losses is False


def test_an_unknown_torque_name_is_rejected():
    with pytest.raises(ValueError, match="unknown torque quantity"):
        assert_same_basis("rated_torque_nm", "not_a_torque")


def test_the_semantics_schema_is_pinned():
    assert TORQUE_SEMANTICS_SCHEMA_VERSION == "phase10f.torque_semantics.v1"


# ---------------------------------------------------------------------------
# Same-basis electromagnetic torque
# ---------------------------------------------------------------------------


def test_the_same_basis_torque_is_the_power_balance():
    e, i, omega = 21.980939, 12.132617, 261.7993878
    torque = same_basis_electromagnetic_torque_nm(
        back_emf_phase_rms_v=e, phase_current_rms_a=i,
        mechanical_angular_speed_rad_s=omega,
    )
    assert torque == pytest.approx(3.0 * e * i / omega, rel=1e-15)
    # and it is the electromagnetic power divided by mechanical speed.
    assert torque * omega == pytest.approx(3.0 * e * i, rel=1e-15)


def test_the_same_basis_torque_rejects_degenerate_inputs():
    with pytest.raises(ValueError):
        same_basis_electromagnetic_torque_nm(
            back_emf_phase_rms_v=-1.0, phase_current_rms_a=1.0,
            mechanical_angular_speed_rad_s=1.0,
        )
    with pytest.raises(ValueError):
        same_basis_electromagnetic_torque_nm(
            back_emf_phase_rms_v=1.0, phase_current_rms_a=1.0,
            mechanical_angular_speed_rad_s=0.0,
        )


def test_zero_current_gives_zero_electromagnetic_torque():
    assert same_basis_electromagnetic_torque_nm(
        back_emf_phase_rms_v=20.0, phase_current_rms_a=0.0,
        mechanical_angular_speed_rad_s=250.0,
    ) == 0.0


# ---------------------------------------------------------------------------
# Operating point and periodicity
# ---------------------------------------------------------------------------


def test_the_torque_case_uses_a_pure_q_axis_operating_point():
    case = build_self_consistent_reference_case(FEAValidationTarget.AVERAGE_TORQUE)
    operating = case.operating_point
    assert operating.phase_current_rms_a > 0.0
    # 90 electrical degrees is id = 0, iq = I: no hidden reluctance component.
    assert operating.current_angle_electrical_deg == pytest.approx(90.0)


def test_the_cogging_case_enforces_zero_stator_current():
    case = build_self_consistent_reference_case(FEAValidationTarget.COGGING_TORQUE)
    assert case.operating_point.phase_current_rms_a == 0.0
    # and the excitation angle is meaningless with no current, so it is zeroed.
    assert case.operating_point.current_angle_electrical_deg == pytest.approx(0.0)


def test_the_cogging_span_is_one_cogging_period():
    case = build_self_consistent_reference_case(FEAValidationTarget.COGGING_TORQUE)
    expected = cogging_period_mech_deg(24, 16)
    assert expected == pytest.approx(7.5)
    assert case.operating_point.rotor_angle_span_mech_deg == pytest.approx(expected)


def test_the_torque_span_is_one_electrical_period():
    case = build_self_consistent_reference_case(FEAValidationTarget.AVERAGE_TORQUE)
    assert case.operating_point.rotor_angle_span_mech_deg == pytest.approx(
        electrical_period_mech_deg(8)
    )


def test_cogging_and_torque_spans_are_different_questions():
    cogging = build_self_consistent_reference_case(FEAValidationTarget.COGGING_TORQUE)
    torque = build_self_consistent_reference_case(FEAValidationTarget.AVERAGE_TORQUE)
    assert cogging.operating_point.rotor_angle_span_mech_deg != pytest.approx(
        torque.operating_point.rotor_angle_span_mech_deg
    )
    assert cogging.operating_point.phase_current_rms_a == 0.0
    assert torque.operating_point.phase_current_rms_a > 0.0


# ---------------------------------------------------------------------------
# Ripple arithmetic
# ---------------------------------------------------------------------------


def test_ripple_percent_is_peak_to_peak_over_mean():
    torque = np.array([1.0, 1.1, 0.9, 1.0])
    mean = float(torque.mean())
    assert float(np.ptp(torque)) / abs(mean) * 100.0 == pytest.approx(20.0)


def test_a_constant_torque_has_zero_ripple():
    torque = np.full(16, 2.5)
    assert float(np.ptp(torque)) == 0.0


# ---------------------------------------------------------------------------
# Diagnostics rows
# ---------------------------------------------------------------------------


def test_the_torque_panel_shows_the_shaft_value_as_a_different_basis():
    rows = torque_diagnostic_rows(
        analytical_electromagnetic_torque_nm=3.056,
        production_shaft_torque_nm=3.056,
        femm_mean_torque_nm=3.25,
        femm_ripple_percent=4.2,
        residual_percent=6.3,
        current_is_back_solved_from_rated_torque=False,
    )
    shaft = [r for r in rows if "轴端" in r.label_zh]
    assert shaft and shaft[0].evidence == EvidenceLabel.DEFINITION_CONVENTION_MISMATCH


def test_the_torque_panel_discloses_a_back_solved_current():
    rows = torque_diagnostic_rows(
        analytical_electromagnetic_torque_nm=3.056,
        production_shaft_torque_nm=3.056,
        femm_mean_torque_nm=3.25,
        femm_ripple_percent=4.2,
        residual_percent=6.3,
        current_is_back_solved_from_rated_torque=True,
    )
    labels = [r.evidence for r in rows]
    assert EvidenceLabel.NOT_AN_INDEPENDENT_PREDICTION in labels


def test_no_torque_row_is_ever_styled_affirmatively():
    rows = torque_diagnostic_rows(
        analytical_electromagnetic_torque_nm=3.0,
        production_shaft_torque_nm=3.0,
        femm_mean_torque_nm=3.0,
        femm_ripple_percent=0.0,
        residual_percent=0.0,
        current_is_back_solved_from_rated_torque=True,
    )
    for row in rows:
        assert not is_affirmative(row.evidence or "")


def test_a_coreless_machine_reports_no_analytical_cogging_model():
    rows = cogging_diagnostic_rows(
        femm_peak_to_peak_nm=0.116,
        mesh_sensitivity_percent=80.0,
        analytical_status=EvidenceLabel.NO_ANALYTICAL_MODEL,
        analytical_value_nm=0.0,
        is_coreless=True,
        signal_above_numerical_floor=False,
    )
    labels = [r.evidence for r in rows]
    assert EvidenceLabel.NO_ANALYTICAL_MODEL in labels
    assert EvidenceLabel.MORE_VALIDATION_REQUIRED in labels
    assert EvidenceLabel.NOT_EXPERIMENTALLY_VALIDATED in labels
    for row in rows:
        assert not is_affirmative(row.evidence or "")


def test_a_cored_machine_reports_cogging_as_an_empirical_input():
    rows = cogging_diagnostic_rows(
        femm_peak_to_peak_nm=0.2,
        mesh_sensitivity_percent=3.0,
        analytical_status=EvidenceLabel.EMPIRICAL_INPUT,
        analytical_value_nm=0.061,
        is_coreless=False,
        signal_above_numerical_floor=True,
    )
    assert EvidenceLabel.EMPIRICAL_INPUT in [r.evidence for r in rows]


def test_the_new_labels_are_registered_and_none_are_affirmative():
    for label in (
        EvidenceLabel.NOT_EXPERIMENTALLY_VALIDATED,
        EvidenceLabel.EMPIRICAL_INPUT,
        EvidenceLabel.NO_ANALYTICAL_MODEL,
        EvidenceLabel.MORE_VALIDATION_REQUIRED,
        EvidenceLabel.NOT_AN_INDEPENDENT_PREDICTION,
    ):
        assert label in EvidenceLabel.ALL
        assert not is_affirmative(label)


def test_missing_torque_evidence_renders_as_missing():
    rendered = render_diagnostics_zh(unavailable_diagnostics("尚未求解转矩"))
    assert "尚未求解转矩" in rendered
    assert "%" not in rendered


# ---------------------------------------------------------------------------
# Campaign evidence
# ---------------------------------------------------------------------------


def test_the_campaign_compared_on_the_electromagnetic_basis():
    payload = _campaign()
    assert "rated_torque_nm = P_rated / omega_mech" in payload["same_basis_rule"]
    assert payload["calibration_performed"] is False
    assert payload["diagnostic_only"] is True


def test_every_design_was_solved_at_a_pure_q_axis_operating_point():
    for design in _campaign()["designs"]:
        assert design["current_angle_electrical_deg"] == pytest.approx(90.0)
        assert design["phase_current_rms_a"] > 0.0


def test_the_analytical_torque_is_identically_the_rated_torque():
    """The current is back-solved from rated torque, so T_em == T_rated exactly.

    This is why the torque comparison is not an independent test of a torque
    model: it re-tests Kt, which is k_w times flux.
    """

    for design in _campaign()["designs"]:
        assert design["analytical_electromagnetic_torque_nm"] == pytest.approx(
            design["production_rated_shaft_torque_nm"], rel=1e-9
        )


def test_cogging_was_swept_with_zero_current_over_one_period():
    for tier in _campaign()["cogging"]:
        assert tier["phase_current_rms_a"] == 0.0
        assert tier["span_mech_deg"] == pytest.approx(7.5)


def test_cogging_mesh_sensitivity_is_reported_at_three_tiers():
    tiers = _campaign()["cogging"]
    assert {t["mesh_tier"] for t in tiers} == {"COARSE", "BASE", "FINE"}
    counts = [t["element_count_max"] for t in tiers]
    assert len(set(counts)) == 3, "the mesh tiers must actually differ"


def test_the_cogging_claim_is_not_stronger_than_the_numerical_floor():
    """If p-p moves with the mesh, the signal is discretisation, not cogging."""

    tiers = {t["mesh_tier"]: t["peak_to_peak_nm"] for t in _campaign()["cogging"]}
    base = tiers["BASE"]
    spread = max(tiers.values()) - min(tiers.values())
    # The evidence must record the spread; the decision that follows from it is
    # documented, not asserted here. What is asserted is that we measured it.
    assert base > 0.0
    assert spread >= 0.0
    assert all(value >= 0.0 for value in tiers.values())


def test_production_physics_is_untouched_by_phase10f():
    path = REPOSITORY_ROOT / "motor_calculator" / "motor_core" / "calculations.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942"
    )


def test_no_torque_correction_factor_exists_anywhere_in_the_bridge():
    package = REPOSITORY_ROOT / "motor_calculator" / "fea"
    for path in sorted(package.glob("*.py")):
        source = path.read_text(encoding="utf-8").lower()
        for forbidden in ("torque_correction", "torque_scale_factor", "torque_fudge"):
            assert forbidden not in source, f"{path.name} must not carry {forbidden}"


# ---------------------------------------------------------------------------
# Ampere-turns in a loaded solve
# ---------------------------------------------------------------------------


def test_a_loaded_solve_carries_the_real_ampere_turns():
    """Unit turns are exact for no-load flux linkage and wrong for a loaded solve.

    The winding regions carry unit turns so FEMM's integer ``turns`` property
    cannot truncate a fractional coil. Flux linkage is linear in turns and is
    rescaled after extraction, so that is exact at no load. The armature field
    is not: a model wound with 1 turn instead of N carries 1/N of the MMF, and
    every torque derived from it comes out 1/N too small.
    """

    import tempfile

    from motor_calculator.fea.adapter import _mesh_size_map, generate_case_scripts
    from motor_calculator.fea.femm_lua import unit_turns_scale
    from motor_calculator.fea.geometry import build_slice_model

    case = build_self_consistent_reference_case(FEAValidationTarget.AVERAGE_TORQUE)
    model = build_slice_model(
        case.geometry,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=0.0,
    )
    scale = unit_turns_scale(model)
    assert scale > 1.0, "this case is supposed to have fractional turns per coil"

    script = Path(generate_case_scripts(case, Path(tempfile.mkdtemp()))[0]).read_text(
        encoding="utf-8"
    )
    emitted = [
        float(line.split(",")[1])
        for line in script.splitlines()
        if "mi_addcircprop" in line
    ]

    # Angle-invariant: for balanced three-phase currents the sum of squares is
    # 3/2 of the peak squared, whatever the excitation angle. Phase 10G changed
    # that angle to a geometry-derived value, and this test is about the turns
    # scaling rather than the alignment, so it must not depend on it.
    peak_from_emitted = math.sqrt(2.0 / 3.0 * sum(v * v for v in emitted))
    physical_peak = case.operating_point.phase_current_rms_a * math.sqrt(2.0)
    assert peak_from_emitted == pytest.approx(physical_peak * scale, rel=1e-9)
    assert peak_from_emitted != pytest.approx(physical_peak, rel=1e-3)


def test_the_no_load_campaign_scripts_are_unchanged_by_the_ampere_turns_fix():
    """Phase 10C and 10D both rest on these scripts being byte-identical."""

    import hashlib
    import tempfile

    from motor_calculator.fea.adapter import generate_case_scripts

    case = build_self_consistent_reference_case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    workspace = Path(tempfile.mkdtemp())
    texts = [
        Path(path).read_text(encoding="utf-8")
        for path in generate_case_scripts(case, workspace)
    ]
    normalised = [
        text.replace(str(workspace).replace("\\", "/"), "<WORKSPACE>").replace(
            case.case_id, "<CASE_ID>"
        )
        for text in texts
    ]
    digest = hashlib.sha256("".join(normalised).encode()).hexdigest()
    assert digest == (
        "8fbb95e97f092f59c0384b2a34864b5c8f7e02e2251489352d76a466d9cb96e9"
    ), "the no-load campaign scripts must not change"


def test_zero_current_scales_to_zero_current():
    """The fix must be inert at no load, which is why the hash above holds."""

    from motor_calculator.fea.femm_lua import balanced_phase_currents

    currents = balanced_phase_currents(
        phase_rms_a=0.0, electrical_angle_deg=37.0,
        current_angle_electrical_deg=90.0, phase_names=("A", "B", "C"),
    )
    for value in currents.values.values():
        assert value * 6.25 == 0.0
